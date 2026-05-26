"""
Enhanced VLM Extractor Module.

This module provides an enhanced VLM extractor that integrates with the platform
provider system, supporting automatic failover, budget monitoring, audit logging,
and organization-based cost tracking.

Example Usage:
    from app.core.extraction.enhanced_vlm_extractor import EnhancedVLMExtractor

    extractor = EnhancedVLMExtractor(db_session, user_id, organization_id)
    result = await extractor.extract_page(image_data, page_number, total_pages, leaflet_id)
"""

import asyncio
import base64
import json
import logging
import re
import time
import uuid
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.extraction.prompt_builder import PromptBuilder, get_prompt_builder
from app.core.extraction.schemas import (
    BoundingBox,
    ExtractionContext,
    ExtractionResult,
    ExtractedProduct,
    FieldConfidence,
    PageExtractionResult,
)
from app.core.extraction.multi_provider_client import (
    MultiProviderVLMClient,
    VLMClientError,
    APIError,
    BudgetExceededError,
    InsufficientCreditsError,
    ProviderNotSupportedError,
)

# Import our new services
from app.services.platform_vlm_service import PlatformVLMProviderService, ProviderFailoverError
from app.services.notification_service import NotificationService
from app.services.budget_monitoring_service import BudgetMonitoringService
from app.services.vlm_audit_service import VLMAuditService

from app.models.platform_vlm_provider import PlatformVLMProvider
from app.models.vlm_provider import VLMProvider, VLMProviderType
from app.models.vlm_audit_log import AuditEventType, AuditEventStatus, ErrorCategory
from app.models.user import User

logger = logging.getLogger(__name__)


class EnhancedVLMExtractor:
    """
    Enhanced VLM extractor with platform provider support and monitoring.

    This extractor provides:
    - Automatic provider selection (organization keys -> platform keys)
    - Smart failover when providers fail or exceed budgets
    - Comprehensive audit logging for compliance
    - Real-time budget monitoring and alerts
    - Organization-based cost tracking
    - Performance analytics and error handling

    Attributes:
        db: Database session
        user_id: User ID for context
        organization_id: Organization ID for cost tracking
        prompt_builder: Prompt builder instance
        services: Injected service instances
    """

    def __init__(
        self,
        db: Session,
        user_id: str,
        organization_id: str,
        prompt_builder: Optional[PromptBuilder] = None,
        platform_service: Optional[PlatformVLMProviderService] = None,
        notification_service: Optional[NotificationService] = None,
        audit_service: Optional[VLMAuditService] = None
    ):
        """
        Initialize the enhanced VLM extractor.

        Args:
            db: Database session
            user_id: User ID for context and audit logging
            organization_id: Organization ID for cost tracking
            prompt_builder: Optional custom prompt builder
            platform_service: Platform provider service (optional, will create if not provided)
            notification_service: Notification service (optional)
            audit_service: Audit logging service (optional)
        """
        self.db = db
        self.user_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        self.organization_id = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        self.prompt_builder = prompt_builder or get_prompt_builder()

        # Initialize services
        self.platform_service = platform_service or PlatformVLMProviderService(db)
        self.notification_service = notification_service or NotificationService(db)
        self.audit_service = audit_service or VLMAuditService(db)

        # Track usage across extractions
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

        # Current provider state
        self._current_provider: Optional[PlatformVLMProvider] = None
        self._current_client: Optional[MultiProviderVLMClient] = None
        self._operation_id = str(uuid.uuid4())  # Unique ID for tracking related operations

    async def extract_page(
        self,
        image_data: Union[bytes, str],
        page_number: int,
        total_pages: int,
        leaflet_id: str,
        context: Optional[ExtractionContext] = None,
        image_format: str = "png",
        max_retries: int = 3
    ) -> PageExtractionResult:
        """
        Extract products from a single page image with enhanced monitoring.

        Args:
            image_data: Image as bytes or base64 string
            page_number: Current page number (1-indexed)
            total_pages: Total pages in leaflet
            leaflet_id: Leaflet ID for audit logging
            context: Optional extraction context
            image_format: Image format (png, jpg, etc.)
            max_retries: Maximum retry attempts

        Returns:
            PageExtractionResult: Extraction result with products and metadata

        Raises:
            ProviderFailoverError: If all providers fail
            VLMClientError: If extraction fails after retries
        """
        start_time = time.time()
        leaflet_uuid = uuid.UUID(leaflet_id)

        # Generate unique operation ID for this request
        operation_id = f"{self._operation_id}_{page_number}"

        # Prepare image and get dimensions
        base64_image, media_type, img_width, img_height = await self._prepare_image_with_dimensions(
            image_data, image_format
        )

        # Update context with image dimensions
        if context is not None:
            context = ExtractionContext(
                leaflet_id=context.leaflet_id,
                leaflet_uuid=context.leaflet_uuid,
                retailer=context.retailer,
                country=context.country,
                language=context.language,
                currency=context.currency,
                page_count=context.page_count,
                previous_page_notes=context.previous_page_notes,
                has_previous_page=context.has_previous_page,
                has_next_page=context.has_next_page,
                image_width=img_width,
                image_height=img_height,
            )
        else:
            context = ExtractionContext(
                leaflet_id=leaflet_id,
                page_count=total_pages,
                image_width=img_width,
                image_height=img_height,
            )

        logger.info(f"Extracting page {page_number}: image dimensions {img_width}x{img_height}")

        # Try extraction with automatic failover
        for attempt in range(max_retries + 1):
            try:
                # Get best available provider
                provider = await self._get_active_provider()

                # Build prompt
                prompt = self.prompt_builder.build_extraction_prompt(
                    page_number=page_number,
                    total_pages=total_pages,
                    context=context,
                )

                # Create client for this provider
                client = MultiProviderVLMClient(provider)

                # Make extraction request
                result = await client.extract_from_image(
                    image_data=base64_image,
                    prompt=prompt,
                    media_type=media_type,
                )

                # Track usage
                self.total_input_tokens += result.input_tokens
                self.total_output_tokens += result.output_tokens
                self.total_cost += result.cost

                # Record usage in platform service
                await self.platform_service.record_usage(
                    provider_id=provider.id,
                    organization_id=self.organization_id,
                    usage_data={
                        'request_count': 1,
                        'input_tokens': result.input_tokens,
                        'output_tokens': result.output_tokens,
                        'cost': result.cost,
                        'leaflet_count': 0,  # Will be updated at leaflet level
                        'page_count': 1,
                        'product_count': 0,  # Will be updated after parsing
                        'confidence_score': None  # Will be updated after parsing
                    }
                )

                # Parse the response
                parsed_result = self._parse_response(
                    {
                        "content": result.content,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                    },
                    page_number,
                    image_width=img_width,
                    image_height=img_height,
                )

                # Set processing time
                parsed_result.processing_time_ms = int((time.time() - start_time) * 1000)

                # Log successful extraction
                await self.audit_service.log_extraction_attempt(
                    provider_id=provider.id,
                    organization_id=self.organization_id,
                    user_id=self.user_id,
                    leaflet_id=leaflet_uuid,
                    status=AuditEventStatus.SUCCESS,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cost=result.cost,
                    latency_ms=parsed_result.processing_time_ms,
                    provider_type=provider.provider_type.value,
                    model_name=provider.model_name,
                    operation_id=operation_id,
                    metadata={
                        'page_number': page_number,
                        'total_pages': total_pages,
                        'products_found': parsed_result.product_count,
                        'attempt': attempt + 1
                    }
                )

                logger.info(
                    f"Extracted {parsed_result.product_count} products from page {page_number} "
                    f"in {parsed_result.processing_time_ms}ms using {provider.name} (cost: ${result.cost:.4f})"
                )

                return parsed_result

            except (BudgetExceededError, InsufficientCreditsError) as e:
                logger.warning(f"Budget/credits exhausted for provider {provider.name if provider else 'unknown'}: {e}")

                # Log the budget issue
                await self.audit_service.log_extraction_attempt(
                    provider_id=provider.id if provider else None,
                    organization_id=self.organization_id,
                    user_id=self.user_id,
                    leaflet_id=leaflet_uuid,
                    status=AuditEventStatus.FAILURE,
                    error_type=ErrorCategory.BUDGET_LIMIT,
                    error_message=str(e),
                    operation_id=operation_id,
                    metadata={'page_number': page_number, 'attempt': attempt + 1}
                )

                # Trigger failover
                if attempt < max_retries:
                    next_provider = await self.platform_service.trigger_failover(
                        failed_provider_id=provider.id,
                        organization_id=self.organization_id,
                        failure_reason=str(e),
                        error_category=ErrorCategory.BUDGET_LIMIT
                    )
                    if next_provider:
                        logger.info(f"Failed over to provider: {next_provider.name}")
                        continue
                    else:
                        logger.error("No alternative providers available for failover")
                        raise ProviderFailoverError("All providers exhausted or unavailable")

            except (APIError, VLMClientError) as e:
                logger.warning(f"API error on attempt {attempt + 1}: {e}")

                # Determine error category
                error_category = ErrorCategory.PROVIDER_ERROR
                if "rate limit" in str(e).lower():
                    error_category = ErrorCategory.RATE_LIMIT
                elif "authentication" in str(e).lower() or "invalid" in str(e).lower():
                    error_category = ErrorCategory.AUTHENTICATION
                elif "timeout" in str(e).lower():
                    error_category = ErrorCategory.TIMEOUT

                # Log the API error
                await self.audit_service.log_extraction_attempt(
                    provider_id=provider.id if provider else None,
                    organization_id=self.organization_id,
                    user_id=self.user_id,
                    leaflet_id=leaflet_uuid,
                    status=AuditEventStatus.FAILURE,
                    error_type=error_category,
                    error_message=str(e),
                    retry_count=attempt,
                    operation_id=operation_id,
                    metadata={'page_number': page_number, 'attempt': attempt + 1}
                )

                # Trigger failover for certain error types
                if attempt < max_retries and error_category in [ErrorCategory.RATE_LIMIT, ErrorCategory.AUTHENTICATION]:
                    next_provider = await self.platform_service.trigger_failover(
                        failed_provider_id=provider.id,
                        organization_id=self.organization_id,
                        failure_reason=str(e),
                        error_category=error_category
                    )
                    if next_provider:
                        logger.info(f"Failed over to provider: {next_provider.name}")
                        continue

                # If this is the last attempt or no failover, raise the error
                if attempt == max_retries:
                    raise

            except Exception as e:
                logger.exception(f"Unexpected error on attempt {attempt + 1}: {e}")

                # Log the unexpected error
                await self.audit_service.log_extraction_attempt(
                    provider_id=provider.id if provider else None,
                    organization_id=self.organization_id,
                    user_id=self.user_id,
                    leaflet_id=leaflet_uuid,
                    status=AuditEventStatus.ERROR,
                    error_type=ErrorCategory.SYSTEM_ERROR,
                    error_message=str(e),
                    retry_count=attempt,
                    operation_id=operation_id,
                    metadata={'page_number': page_number, 'attempt': attempt + 1}
                )

                if attempt == max_retries:
                    raise VLMClientError(f"Extraction failed after {max_retries + 1} attempts: {e}")

        # Should never reach here
        raise VLMClientError(f"Extraction failed after {max_retries + 1} attempts")

    async def extract_leaflet(
        self,
        page_images: List[Union[bytes, str]],
        leaflet_id: str,
        context: Optional[ExtractionContext] = None,
        parallel: bool = True,
        max_concurrent: int = 2,  # Reduced default to be more conservative
    ) -> ExtractionResult:
        """
        Extract products from all pages in a leaflet with enhanced monitoring.

        Args:
            page_images: List of page images (bytes or base64)
            leaflet_id: Leaflet identifier for tracking
            context: Optional extraction context
            parallel: Process pages in parallel
            max_concurrent: Max concurrent API calls

        Returns:
            ExtractionResult: Combined results from all pages
        """
        start_time = time.time()
        total_pages = len(page_images)
        leaflet_uuid = uuid.UUID(leaflet_id)

        if context is None:
            context = ExtractionContext(
                leaflet_id=leaflet_id,
                page_count=total_pages,
            )

        result = ExtractionResult(leaflet_id=leaflet_id)

        # Log leaflet extraction start
        await self.audit_service.log_provider_event(
            event_type=AuditEventType.EXTRACTION,
            status=AuditEventStatus.SUCCESS,
            organization_id=self.organization_id,
            user_id=self.user_id,
            metadata={
                'leaflet_id': leaflet_id,
                'total_pages': total_pages,
                'operation_id': self._operation_id,
                'parallel': parallel,
                'max_concurrent': max_concurrent
            }
        )

        try:
            if parallel and total_pages > 1:
                # Process pages in parallel with concurrency limit
                semaphore = asyncio.Semaphore(max_concurrent)

                async def extract_with_limit(page_num: int, image: Union[bytes, str]):
                    async with semaphore:
                        return await self.extract_page(
                            image_data=image,
                            page_number=page_num,
                            total_pages=total_pages,
                            leaflet_id=leaflet_id,
                            context=context,
                        )

                tasks = [
                    extract_with_limit(i + 1, img)
                    for i, img in enumerate(page_images)
                    if img is not None
                ]

                page_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for i, page_result in enumerate(page_results):
                    if isinstance(page_result, Exception):
                        logger.error(f"Page {i+1} extraction failed: {page_result}")
                        result.add_error(f"Page {i+1}: {str(page_result)}")
                    else:
                        result.add_page_result(page_result)

            else:
                # Process pages sequentially
                for i, image in enumerate(page_images):
                    if image is None:
                        continue
                    try:
                        page_result = await self.extract_page(
                            image_data=image,
                            page_number=i + 1,
                            total_pages=total_pages,
                            leaflet_id=leaflet_id,
                            context=context,
                        )
                        result.add_page_result(page_result)
                    except Exception as e:
                        logger.error(f"Page {i+1} extraction failed: {e}")
                        result.add_error(f"Page {i+1}: {str(e)}")

            # Set totals
            result.input_tokens = self.total_input_tokens
            result.output_tokens = self.total_output_tokens
            result.processing_time_ms = int((time.time() - start_time) * 1000)

            # Update usage with final leaflet metrics
            if self._current_provider:
                # Calculate overall confidence
                total_products = sum(len(pr.products) for pr in result.page_results)
                overall_confidence = None
                if total_products > 0:
                    confidence_scores = [
                        p.confidence_score for pr in result.page_results
                        for p in pr.products if p.confidence_score is not None
                    ]
                    if confidence_scores:
                        overall_confidence = sum(confidence_scores) / len(confidence_scores)

                await self.platform_service.record_usage(
                    provider_id=self._current_provider.id,
                    organization_id=self.organization_id,
                    usage_data={
                        'request_count': 0,  # Don't double-count requests
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'cost': 0.0,
                        'leaflet_count': 1,
                        'page_count': 0,  # Don't double-count pages
                        'product_count': total_products,
                        'confidence_score': overall_confidence
                    }
                )

            logger.info(
                f"Leaflet extraction complete: {result.total_products} products, "
                f"{len(result.page_results)} pages, {result.processing_time_ms}ms, "
                f"${self.total_cost:.4f} total cost"
            )

            return result

        except Exception as e:
            # Log leaflet extraction failure
            await self.audit_service.log_provider_event(
                event_type=AuditEventType.EXTRACTION,
                status=AuditEventStatus.ERROR,
                organization_id=self.organization_id,
                user_id=self.user_id,
                error_type=ErrorCategory.SYSTEM_ERROR,
                error_message=str(e),
                metadata={
                    'leaflet_id': leaflet_id,
                    'operation_id': self._operation_id,
                    'error_during': 'leaflet_extraction'
                }
            )
            raise

    async def _get_active_provider(self) -> PlatformVLMProvider:
        """
        Get the active provider, trying organization keys first, then platform keys.

        Returns:
            PlatformVLMProvider: Active provider ready for use

        Raises:
            ProviderFailoverError: If no providers are available
        """
        try:
            # First, try to get organization's own VLM provider
            org_provider = await self._get_organization_provider()
            if org_provider:
                logger.debug(f"Using organization provider: {org_provider.name}")
                self._current_provider = org_provider
                return org_provider

            # Fall back to platform provider
            platform_provider = await self.platform_service.get_active_provider(self.organization_id)
            logger.debug(f"Using platform provider: {platform_provider.name}")
            self._current_provider = platform_provider
            return platform_provider

        except Exception as e:
            logger.error(f"Failed to get active provider: {e}")
            raise ProviderFailoverError(f"No VLM providers available: {e}")

    async def _get_organization_provider(self) -> Optional[PlatformVLMProvider]:
        """
        Check if organization has its own VLM provider configured.

        This method checks the traditional vlm_providers table for organization-specific keys.
        If found, it converts them to platform provider format for unified handling.

        Returns:
            Optional[PlatformVLMProvider]: Organization provider if available
        """
        try:
            # Check if organization has its own VLM provider
            from app.models.vlm_provider import VLMProvider

            if hasattr(self.db, 'execute'):
                result = await self.db.execute(
                    select(VLMProvider).where(
                        VLMProvider.organization_id == self.organization_id,
                        VLMProvider.is_active == True
                    ).order_by(
                        VLMProvider.is_default.desc(),
                        VLMProvider.created_at.desc()
                    ).limit(1)
                )
            else:
                result = self.db.execute(
                    select(VLMProvider).where(
                        VLMProvider.organization_id == self.organization_id,
                        VLMProvider.is_active == True
                    ).order_by(
                        VLMProvider.is_default.desc(),
                        VLMProvider.created_at.desc()
                    ).limit(1)
                )

            org_vlm_provider = result.scalar_one_or_none()

            if org_vlm_provider and org_vlm_provider.check_budget():
                # Convert to platform provider format for unified handling
                # This is a temporary adapter until organizations migrate to platform providers

                # Create a temporary platform provider object for API compatibility
                class OrganizationProviderAdapter:
                    def __init__(self, vlm_provider: VLMProvider):
                        self.id = vlm_provider.id
                        self.name = vlm_provider.name
                        self.provider_type = vlm_provider.provider_type  # Assuming compatible enum
                        self.model_name = vlm_provider.model_name
                        self.max_tokens = vlm_provider.max_tokens
                        self.temperature = vlm_provider.temperature
                        self.api_endpoint = vlm_provider.api_endpoint
                        self.config = vlm_provider.config
                        self.monthly_budget = vlm_provider.monthly_budget
                        self.current_month_spent = vlm_provider.current_month_spent
                        self._vlm_provider = vlm_provider

                    def get_api_key(self):
                        return self._vlm_provider.get_api_key()

                    def check_budget(self):
                        return self._vlm_provider.check_budget()

                    def record_usage(self, input_tokens, output_tokens, cost):
                        return self._vlm_provider.record_usage(input_tokens, output_tokens, cost)

                return OrganizationProviderAdapter(org_vlm_provider)

        except Exception as e:
            logger.warning(f"Error checking organization provider: {e}")

        return None

    async def _prepare_image_with_dimensions(
        self,
        image_data: Union[bytes, str],
        image_format: str,
    ) -> tuple:
        """
        Prepare image for API call and extract dimensions.

        Returns:
            Tuple of (base64_image, media_type, width, height)
        """
        # Default dimensions (A4 at 300 DPI)
        width, height = 2480, 3508

        try:
            # Get image bytes for dimension detection
            if isinstance(image_data, str):
                # Decode base64 to bytes for PIL
                image_bytes = base64.b64decode(image_data)
                base64_image = image_data
            else:
                image_bytes = image_data
                base64_image = base64.b64encode(image_data).decode()

            # Open image to get dimensions
            img = Image.open(BytesIO(image_bytes))
            width, height = img.size
            img.close()

            logger.debug(f"Detected image dimensions: {width}x{height}")

        except Exception as e:
            logger.warning(f"Failed to detect image dimensions, using defaults: {e}")

        # Determine media type
        format_to_mime = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        media_type = format_to_mime.get(image_format.lower(), "image/png")

        return base64_image, media_type, width, height

    def _parse_response(
        self,
        response: Dict[str, Any],
        page_number: int,
        image_width: int = 2480,
        image_height: int = 3508,
    ) -> PageExtractionResult:
        """
        Parse VLM response into structured result.

        This method reuses the existing parsing logic from UserAwareVLMExtractor
        but could be enhanced with additional validation and error handling.
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

        # Parse products with image dimensions for validation
        products = []
        raw_products = json_data.get("products", [])

        logger.info(f"Page {page_number}: Parsing {len(raw_products)} products from VLM response")

        for idx, raw_product in enumerate(raw_products):
            try:
                product = self._parse_product(raw_product, image_width, image_height)
                if product:
                    products.append(product)
                    logger.debug(
                        f"  Product {idx+1}: '{product.product_name[:40]}' "
                        f"bbox=({product.bounding_box.x},{product.bounding_box.y},"
                        f"{product.bounding_box.width}x{product.bounding_box.height})"
                    )
            except Exception as e:
                logger.warning(f"Failed to parse product {idx+1}: {e}")
                continue

        logger.info(f"Page {page_number}: Successfully parsed {len(products)} products")

        return PageExtractionResult(
            page_number=json_data.get("page_number", page_number),
            products=products,
            page_notes=json_data.get("page_notes"),
            continuation_detected=json_data.get("continuation_detected", False),
            input_tokens=response.get("input_tokens", 0),
            output_tokens=response.get("output_tokens", 0),
        )

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from VLM response content."""
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

    def _parse_product(
        self,
        raw: Dict[str, Any],
        image_width: int = 2480,
        image_height: int = 3508,
    ) -> Optional[ExtractedProduct]:
        """Parse a single product from raw VLM output."""
        product_name = raw.get("product_name")
        if not product_name or not product_name.strip():
            return None

        # Parse position hint (new field for OCR-based bbox detection)
        position_hint = raw.get("position_hint")

        # Bounding box is now optional - will be filled by OCR post-processing
        bounding_box = None
        bbox_data = raw.get("bounding_box")
        if bbox_data and isinstance(bbox_data, dict):
            try:
                x = int(bbox_data.get("x", 0))
                y = int(bbox_data.get("y", 0))
                width = int(bbox_data.get("width", 0))
                height = int(bbox_data.get("height", 0))

                if width > 0 and height > 0:
                    x, y, width, height = self._validate_and_fix_bbox(
                        x, y, width, height, image_width, image_height, product_name
                    )
                    bounding_box = BoundingBox(x=x, y=y, width=width, height=height)
            except (ValueError, TypeError):
                pass  # Leave bounding_box as None - OCR will fill it in later

        # Parse field confidence
        field_conf_data = raw.get("field_confidence", {})
        field_confidence = None
        if field_conf_data:
            try:
                field_confidence = FieldConfidence(**field_conf_data)
            except Exception:
                pass

        # Build product
        try:
            return ExtractedProduct(
                bounding_box=bounding_box,
                position_hint=position_hint,
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
                confidence_score=self._parse_float(raw.get("confidence_score", 0.8)) or 0.8,
                field_confidence=field_confidence,
                uncertainty_flags=raw.get("uncertainty_flags", []),
            )
        except Exception as e:
            logger.warning(f"Failed to create ExtractedProduct: {e}")
            return None

    def _validate_and_fix_bbox(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        image_width: int,
        image_height: int,
        product_name: str,
    ) -> tuple:
        """Validate and fix bounding box coordinates."""
        original = (x, y, width, height)
        fixed = False

        # Fix negative coordinates
        if x < 0:
            x = 0
            fixed = True
        if y < 0:
            y = 0
            fixed = True

        # Fix coordinates beyond image bounds
        if x >= image_width:
            x = image_width - 100
            fixed = True
        if y >= image_height:
            y = image_height - 100
            fixed = True

        # Ensure minimum dimensions (typical product card is at least 150x200)
        min_width = max(150, image_width // 10)
        min_height = max(200, image_height // 10)

        if width < min_width:
            width = min_width
            fixed = True
        if height < min_height:
            height = min_height
            fixed = True

        # Ensure bounding box doesn't extend beyond image
        if x + width > image_width:
            width = image_width - x
            fixed = True
        if y + height > image_height:
            height = image_height - y
            fixed = True

        # Log if we had to fix anything
        if fixed:
            logger.info(
                f"Fixed bounding box for '{product_name[:30]}': "
                f"original={original} -> fixed=({x}, {y}, {width}, {height})"
            )

        return x, y, width, height

    def _parse_float(self, value: Any) -> Optional[float]:
        """Safely parse a float value."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @property
    def provider_info(self) -> Dict[str, Any]:
        """Get information about the current provider being used."""
        if self._current_provider:
            return {
                "type": "platform_provider",
                "provider_id": str(self._current_provider.id),
                "provider_name": self._current_provider.name,
                "provider_type": self._current_provider.provider_type.value if hasattr(self._current_provider.provider_type, 'value') else str(self._current_provider.provider_type),
                "model": self._current_provider.model_name,
                "is_organization_provider": hasattr(self._current_provider, '_vlm_provider'),
                "budget_status": self._current_provider.get_budget_status() if hasattr(self._current_provider, 'get_budget_status') else None
            }
        else:
            return {
                "type": "none",
                "message": "No provider currently selected"
            }