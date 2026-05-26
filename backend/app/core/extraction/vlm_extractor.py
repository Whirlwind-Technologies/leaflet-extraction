"""
VLM Extractor Module.

This module provides the core VLM extraction functionality using
Anthropic Claude's vision capabilities to extract product data
from leaflet page images.

NOTE: This base class requires an explicit API key. For production use,
prefer `VLMExtractorService` which automatically selects providers
from the database (organization-level or platform-level).

Example Usage:
    from app.core.extraction.vlm_extractor import VLMExtractor

    extractor = VLMExtractor(api_key="your-api-key")
    result = await extractor.extract_page(
        image_data=base64_image,
        page_number=1,
        total_pages=12
    )
"""

import asyncio
import base64
import json
import logging
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.core.extraction.prompt_builder import PromptBuilder, get_prompt_builder
from app.core.extraction.schemas import (
    BoundingBox,
    ExtractionContext,
    ExtractionResult,
    ExtractedProduct,
    FieldConfidence,
    PageExtractionResult,
)

logger = logging.getLogger(__name__)


class VLMExtractorError(Exception):
    """Base exception for VLM extraction errors."""
    pass


class APIError(VLMExtractorError):
    """Error from the Claude API."""
    pass


class ParseError(VLMExtractorError):
    """Error parsing VLM response."""
    pass


class VLMExtractor:
    """
    Vision-Language Model extractor using Anthropic Claude.
    
    Extracts structured product data from leaflet page images
    using Claude's vision capabilities.
    
    Attributes:
        model: Claude model to use
        max_tokens: Maximum output tokens
        temperature: Sampling temperature
        
    Example:
        >>> extractor = VLMExtractor()
        >>> result = await extractor.extract_page(image_bytes, 1, 12)
        >>> print(f"Found {len(result.products)} products")
    """
    
    # Default model configuration
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    DEFAULT_MAX_TOKENS = 8192
    DEFAULT_TEMPERATURE = 0.1
    
    # Supported image formats
    SUPPORTED_FORMATS = {"png", "jpg", "jpeg", "gif", "webp"}
    
    # Maximum image size (in pixels) - resize larger images
    MAX_IMAGE_DIMENSION = 4096
    
    # Maximum image size in bytes for API (5MB limit, but we use 4.5MB for safety margin)
    MAX_IMAGE_SIZE_BYTES = 4_500_000
    
    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        prompt_builder: Optional[PromptBuilder] = None,
    ):
        """
        Initialize the VLM extractor.

        Args:
            api_key: Anthropic API key (REQUIRED - no environment fallback)
            model: Claude model to use
            max_tokens: Maximum output tokens
            temperature: Sampling temperature (lower = more deterministic)
            prompt_builder: Custom prompt builder instance

        Note:
            For production use with database-configured providers,
            use `UserAwareVLMExtractor` instead.
        """
        if not api_key:
            raise ValueError(
                "Anthropic API key is required. For production, use UserAwareVLMExtractor "
                "which automatically selects providers from the database."
            )
        self.api_key = api_key
        
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.prompt_builder = prompt_builder or get_prompt_builder()
        
        # Initialize client lazily
        self._client = None
        self._async_client = None
        
        logger.info(f"VLMExtractor initialized with model: {self.model}")
    
    @property
    def client(self):
        """Get synchronous Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package is required. "
                    "Install with: pip install anthropic"
                )
        return self._client
    
    @property
    def async_client(self):
        """Get async Anthropic client."""
        if self._async_client is None:
            try:
                from anthropic import AsyncAnthropic
                self._async_client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package is required. "
                    "Install with: pip install anthropic"
                )
        return self._async_client
    
    async def extract_page(
        self,
        image_data: Union[bytes, str, Path],
        page_number: int,
        total_pages: int,
        context: Optional[ExtractionContext] = None,
        image_format: str = "png",
    ) -> PageExtractionResult:
        """
        Extract products from a single page image.
        
        Args:
            image_data: Image as bytes, base64 string, or file path
            page_number: Current page number (1-indexed)
            total_pages: Total pages in leaflet
            context: Optional extraction context
            image_format: Image format (png, jpg, etc.)
            
        Returns:
            PageExtractionResult with extracted products
            
        Raises:
            APIError: If API call fails
            ParseError: If response parsing fails
        """
        start_time = time.time()
        
        # Prepare image
        base64_image, media_type = await self._prepare_image(
            image_data, image_format
        )
        
        # Build prompt
        prompt = self.prompt_builder.build_extraction_prompt(
            page_number=page_number,
            total_pages=total_pages,
            context=context,
        )
        
        # Call API with retry
        response = await self._call_api_with_retry(
            base64_image=base64_image,
            media_type=media_type,
            prompt=prompt,
        )
        
        # Parse response
        result = self._parse_response(response, page_number)
        
        # Calculate processing time
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            f"Extracted {result.product_count} products from page {page_number} "
            f"in {result.processing_time_ms}ms"
        )
        
        return result
    
    async def extract_leaflet(
        self,
        page_images: List[Union[bytes, str]],
        leaflet_id: str,
        context: Optional[ExtractionContext] = None,
        parallel: bool = True,
        max_concurrent: int = 4,
    ) -> ExtractionResult:
        """
        Extract products from all pages in a leaflet.
        
        Args:
            page_images: List of page images (bytes or base64)
            leaflet_id: Leaflet identifier
            context: Optional extraction context
            parallel: Process pages in parallel
            max_concurrent: Max concurrent API calls
            
        Returns:
            ExtractionResult with all extracted products
        """
        start_time = time.time()
        total_pages = len(page_images)
        
        # Create context if not provided, using defaults from settings
        if context is None:
            context = ExtractionContext.with_defaults(
                leaflet_id=leaflet_id,
                page_count=total_pages,
            )
        
        result = ExtractionResult(leaflet_id=leaflet_id)
        
        if parallel:
            # Process pages in parallel with concurrency limit
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def extract_with_semaphore(idx: int, image: Union[bytes, str]):
                async with semaphore:
                    # Create page-specific context, excluding fields we'll override
                    base_context = context.model_dump(exclude={'has_previous_page', 'has_next_page', 'previous_page_notes'})
                    page_context = ExtractionContext(
                        **base_context,
                        has_previous_page=idx > 0,
                        has_next_page=idx < total_pages - 1,
                    )
                    return await self.extract_page(
                        image_data=image,
                        page_number=idx + 1,
                        total_pages=total_pages,
                        context=page_context,
                    )
            
            tasks = [
                extract_with_semaphore(idx, image)
                for idx, image in enumerate(page_images)
            ]
            
            page_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for idx, page_result in enumerate(page_results):
                if isinstance(page_result, Exception):
                    logger.error(f"Failed to extract page {idx + 1}: {page_result}")
                    result.page_results.append(PageExtractionResult(
                        page_number=idx + 1,
                        products=[],
                        page_notes=f"Extraction failed: {str(page_result)}",
                    ))
                else:
                    result.page_results.append(page_result)
        else:
            # Process pages sequentially
            previous_notes = None
            for idx, image in enumerate(page_images):
                # Create page-specific context, excluding fields we'll override
                base_context = context.model_dump(exclude={'has_previous_page', 'has_next_page', 'previous_page_notes'})
                page_context = ExtractionContext(
                    **base_context,
                    has_previous_page=idx > 0,
                    has_next_page=idx < total_pages - 1,
                    previous_page_notes=previous_notes,
                )
                
                try:
                    page_result = await self.extract_page(
                        image_data=image,
                        page_number=idx + 1,
                        total_pages=total_pages,
                        context=page_context,
                    )
                    result.page_results.append(page_result)
                    previous_notes = page_result.page_notes
                except Exception as e:
                    logger.error(f"Failed to extract page {idx + 1}: {e}")
                    result.page_results.append(PageExtractionResult(
                        page_number=idx + 1,
                        products=[],
                        page_notes=f"Extraction failed: {str(e)}",
                    ))
        
        # Calculate aggregate metrics
        result.calculate_metrics()
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            f"Extracted {result.total_products} products from "
            f"{result.total_pages} pages in {result.processing_time_ms}ms"
        )
        
        return result
    
    async def _prepare_image(
        self,
        image_data: Union[bytes, str, Path],
        image_format: str = "png",
    ) -> tuple[str, str]:
        """
        Prepare image for API call.
        
        Converts image to base64 and determines media type.
        Resizes if necessary.
        
        Args:
            image_data: Image data in various formats
            image_format: Expected image format
            
        Returns:
            Tuple of (base64_string, media_type)
        """
        # Handle different input types
        if isinstance(image_data, Path):
            image_data = image_data.read_bytes()
            image_format = image_data.suffix.lstrip('.')
        elif isinstance(image_data, str):
            if image_data.startswith('data:'):
                # Extract base64 from data URL
                match = re.match(r'data:image/(\w+);base64,(.+)', image_data)
                if match:
                    return match.group(2), f"image/{match.group(1)}"
            
            if len(image_data) > 1000 and not image_data.startswith('/'):
                # Assume it's already base64
                return image_data, f"image/{image_format}"
            
            # Assume it's a file path
            image_data = Path(image_data).read_bytes()
        
        # At this point, image_data should be bytes
        if not isinstance(image_data, bytes):
            raise ValueError(f"Invalid image data type: {type(image_data)}")
        
        # Check original size
        original_size = len(image_data)
        
        # Resize/compress if necessary
        image_data = await self._resize_if_needed(image_data)
        
        # Encode to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Determine media type - if we compressed, it's now JPEG
        if len(image_data) < original_size or original_size > self.MAX_IMAGE_SIZE_BYTES:
            # Image was compressed, it's now JPEG
            media_type = 'image/jpeg'
        else:
            media_type = f"image/{image_format.lower()}"
            if image_format.lower() == 'jpg':
                media_type = 'image/jpeg'
        
        return base64_image, media_type
    
    async def _resize_if_needed(self, image_bytes: bytes) -> bytes:
        """
        Resize and compress image if it exceeds maximum dimensions or file size.
        
        Args:
            image_bytes: Original image bytes
            
        Returns:
            Resized/compressed image bytes (or original if no resize needed)
        """
        loop = asyncio.get_event_loop()
        
        def _resize_and_compress():
            img = Image.open(BytesIO(image_bytes))
            original_format = img.format or 'PNG'
            
            # Convert RGBA to RGB for JPEG compression
            if img.mode == 'RGBA':
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Check if dimension resize needed
            needs_resize = (
                img.width > self.MAX_IMAGE_DIMENSION or
                img.height > self.MAX_IMAGE_DIMENSION
            )
            
            if needs_resize:
                # Calculate new size maintaining aspect ratio
                ratio = min(
                    self.MAX_IMAGE_DIMENSION / img.width,
                    self.MAX_IMAGE_DIMENSION / img.height,
                )
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.debug(f"Resized image to {new_size}")
            
            # Try to save with progressively lower quality until under size limit
            for quality in [95, 85, 75, 65, 55, 45]:
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=quality, optimize=True)
                result_bytes = buffer.getvalue()
                
                if len(result_bytes) <= self.MAX_IMAGE_SIZE_BYTES:
                    if quality < 95:
                        logger.info(
                            f"Compressed image from {len(image_bytes):,} to {len(result_bytes):,} bytes "
                            f"(quality={quality})"
                        )
                    return result_bytes
            
            # If still too large, resize further
            for scale in [0.8, 0.6, 0.5, 0.4]:
                new_size = (int(img.width * scale), int(img.height * scale))
                scaled_img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                buffer = BytesIO()
                scaled_img.save(buffer, format='JPEG', quality=75, optimize=True)
                result_bytes = buffer.getvalue()
                
                if len(result_bytes) <= self.MAX_IMAGE_SIZE_BYTES:
                    logger.info(
                        f"Resized and compressed image from {len(image_bytes):,} to {len(result_bytes):,} bytes "
                        f"(scale={scale})"
                    )
                    return result_bytes
            
            # Last resort: very aggressive compression
            logger.warning(
                f"Image still too large after compression, using minimum quality"
            )
            buffer = BytesIO()
            final_img = img.resize((int(img.width * 0.3), int(img.height * 0.3)), Image.Resampling.LANCZOS)
            final_img.save(buffer, format='JPEG', quality=50, optimize=True)
            return buffer.getvalue()
        
        # Check if compression might be needed (quick size check)
        if len(image_bytes) <= self.MAX_IMAGE_SIZE_BYTES:
            # Still check dimensions
            img = Image.open(BytesIO(image_bytes))
            if (
                img.width <= self.MAX_IMAGE_DIMENSION and
                img.height <= self.MAX_IMAGE_DIMENSION
            ):
                return image_bytes
        
        return await loop.run_in_executor(None, _resize_and_compress)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((APIError,)),
        reraise=True,
    )
    async def _call_api_with_retry(
        self,
        base64_image: str,
        media_type: str,
        prompt: str,
    ) -> Dict[str, Any]:
        """
        Call Claude API with retry logic.
        
        Args:
            base64_image: Base64 encoded image
            media_type: Image media type
            prompt: Extraction prompt
            
        Returns:
            API response dict with content and usage
            
        Raises:
            APIError: If API call fails after retries
        """
        try:
            message = await self.async_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_image,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )
            
            return {
                "content": message.content[0].text,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
                "model": message.model,
                "stop_reason": message.stop_reason,
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"API call failed: {error_msg}")
            
            # Check for specific error types
            if "rate_limit" in error_msg.lower():
                raise APIError(f"Rate limit exceeded: {error_msg}")
            elif "invalid_api_key" in error_msg.lower():
                raise APIError(f"Invalid API key: {error_msg}")
            elif "overloaded" in error_msg.lower():
                raise APIError(f"API overloaded: {error_msg}")
            else:
                raise APIError(f"API error: {error_msg}")
    
    def _parse_response(
        self,
        response: Dict[str, Any],
        page_number: int,
    ) -> PageExtractionResult:
        """
        Parse VLM response into structured result.
        
        Args:
            response: Raw API response
            page_number: Expected page number
            
        Returns:
            Parsed PageExtractionResult
            
        Raises:
            ParseError: If parsing fails
        """
        content = response.get("content", "")
        
        # Extract JSON from response
        json_data = self._extract_json(content)
        
        if json_data is None:
            logger.error(f"Failed to parse JSON from response: {content[:500]}")
            return PageExtractionResult(
                page_number=page_number,
                products=[],
                page_notes="Failed to parse VLM response",
                input_tokens=response.get("input_tokens", 0),
                output_tokens=response.get("output_tokens", 0),
            )
        
        # Parse products
        products = []
        raw_products = json_data.get("products", [])
        
        for raw_product in raw_products:
            try:
                product = self._parse_product(raw_product)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Failed to parse product: {e}")
                continue
        
        return PageExtractionResult(
            page_number=json_data.get("page_number", page_number),
            products=products,
            page_notes=json_data.get("page_notes"),
            continuation_detected=json_data.get("continuation_detected", False),
            input_tokens=response.get("input_tokens", 0),
            output_tokens=response.get("output_tokens", 0),
        )
    
    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from VLM response content.
        
        Handles various formats including code blocks.
        
        Args:
            content: Raw response content
            
        Returns:
            Parsed JSON dict or None
        """
        # Try direct JSON parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Try to extract from code block
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'\{[\s\S]*\}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    json_str = match.group(1) if '```' in pattern else match.group(0)
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def _parse_product(self, raw: Dict[str, Any]) -> Optional[ExtractedProduct]:
        """
        Parse a single product from raw VLM output.
        
        Args:
            raw: Raw product dict from VLM
            
        Returns:
            ExtractedProduct or None if parsing fails
        """
        # Product name is required
        product_name = raw.get("product_name")
        if not product_name or not product_name.strip():
            return None
        
        # Parse bounding box
        bbox_data = raw.get("bounding_box", {})
        try:
            bounding_box = BoundingBox(
                x=int(bbox_data.get("x", 0)),
                y=int(bbox_data.get("y", 0)),
                width=int(bbox_data.get("width", 100)),
                height=int(bbox_data.get("height", 100)),
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid bounding box: {e}")
            bounding_box = BoundingBox(x=0, y=0, width=100, height=100)
        
        # Parse field confidence
        field_conf_data = raw.get("field_confidence", {})
        field_confidence = None
        if field_conf_data:
            try:
                field_confidence = FieldConfidence(**field_conf_data)
            except Exception:
                pass
        
        # Parse category fields
        suggested_category = raw.get("suggested_category")
        category_confidence = self._parse_float(raw.get("category_confidence"))
        category_alternatives = raw.get("category_alternatives")

        # Validate and normalize category_alternatives
        # VLM may return list of strings or list of dicts - normalize to list of dicts
        if category_alternatives:
            if not isinstance(category_alternatives, list):
                category_alternatives = None
            else:
                normalized_alts = []
                for alt in category_alternatives:
                    if isinstance(alt, str):
                        # Convert string to dict format
                        normalized_alts.append({"name": alt, "confidence": None})
                    elif isinstance(alt, dict):
                        normalized_alts.append(alt)
                    # Skip invalid entries
                category_alternatives = normalized_alts if normalized_alts else None

        # Build product
        try:
            product = ExtractedProduct(
                bounding_box=bounding_box,
                brand=raw.get("brand"),
                product_code=raw.get("product_code"),
                product_name=product_name,
                quantity=self._parse_float(raw.get("quantity")),
                units=raw.get("units"),
                size=raw.get("size"),
                regular_price=self._parse_float(raw.get("regular_price")),
                discounted_price=self._parse_float(raw.get("discounted_price")),
                discount_percentage=self._parse_float(raw.get("discount_percentage")),
                currency=raw.get("currency"),
                product_id=raw.get("product_id"),
                promotional_info=raw.get("promotional_info"),
                suggested_category=suggested_category,
                category_confidence=category_confidence,
                category_alternatives=category_alternatives if category_alternatives else None,
                confidence_score=self._parse_float(
                    raw.get("confidence_score", 0.8)
                ) or 0.8,
                field_confidence=field_confidence,
                uncertainty_flags=raw.get("uncertainty_flags", []),
            )
            return product
        except Exception as e:
            logger.warning(f"Failed to create ExtractedProduct: {e}")
            return None
    
    def _parse_float(self, value: Any) -> Optional[float]:
        """Safely parse a float value."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


# Singleton extractor instance
_extractor: Optional[VLMExtractor] = None


def get_extractor() -> VLMExtractor:
    """Get or create the VLM extractor singleton."""
    global _extractor
    if _extractor is None:
        _extractor = VLMExtractor()
    return _extractor


def reset_extractor():
    """Reset the extractor singleton (useful for testing)."""
    global _extractor
    _extractor = None