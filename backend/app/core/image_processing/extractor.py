"""
Image Extractor Module.

Extracts product images from page images using bounding box coordinates.
Handles cropping, padding, and basic image adjustments.

Example Usage:
    from app.core.image_processing.extractor import ImageExtractor
    
    extractor = ImageExtractor()
    result = extractor.extract_product_image(
        page_image_path="/path/to/page.png",
        bounding_box={"x": 50, "y": 120, "width": 280, "height": 350},
        product_id="prod_001"
    )
"""

import logging
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from PIL import Image, ImageEnhance, ImageFilter

from app.core.extraction.schemas import BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """
    Result of image extraction operation.
    
    Attributes:
        success: Whether extraction succeeded
        image: Extracted PIL Image (if successful)
        width: Image width in pixels
        height: Image height in pixels
        original_bbox: Original bounding box
        adjusted_bbox: Adjusted bounding box (after padding/clipping)
        error: Error message (if failed)
    """
    success: bool
    image: Optional[Image.Image] = None
    width: int = 0
    height: int = 0
    original_bbox: Optional[BoundingBox] = None
    adjusted_bbox: Optional[BoundingBox] = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class ImageExtractor:
    """
    Extracts product images from page images.
    
    Uses bounding box coordinates to crop product regions
    from full page images. Supports padding, enhancement,
    and format conversion.
    
    Attributes:
        padding: Padding to add around bounding box (pixels)
        enhance: Whether to apply image enhancement
        min_size: Minimum dimension for extracted images
        max_size: Maximum dimension for extracted images
        
    Example:
        >>> extractor = ImageExtractor(padding=5, enhance=True)
        >>> result = extractor.extract_product_image(
        ...     "page_01.png",
        ...     BoundingBox(x=50, y=100, width=200, height=300),
        ...     "product_001"
        ... )
        >>> if result.success:
        ...     result.image.save("product_001.png")
    """
    
    # Default configuration
    DEFAULT_PADDING = 2
    MIN_SIZE = 50
    MAX_SIZE = 2000
    
    def __init__(
        self,
        padding: int = DEFAULT_PADDING,
        enhance: bool = True,
        min_size: int = MIN_SIZE,
        max_size: int = MAX_SIZE,
    ):
        """
        Initialize the image extractor.
        
        Args:
            padding: Pixels to add around bounding box
            enhance: Whether to apply automatic enhancement
            min_size: Minimum allowed dimension
            max_size: Maximum allowed dimension
        """
        self.padding = padding
        self.enhance = enhance
        self.min_size = min_size
        self.max_size = max_size
    
    def extract_product_image(
        self,
        page_image_path: Union[str, Path],
        bounding_box: Union[BoundingBox, Dict],
        product_id: str,
        enhance: Optional[bool] = None,
    ) -> ExtractionResult:
        """
        Extract a product image from a page image.
        
        Args:
            page_image_path: Path to the page image
            bounding_box: Bounding box coordinates
            product_id: Product identifier for logging
            enhance: Override default enhancement setting
            
        Returns:
            ExtractionResult with extracted image or error
        """
        try:
            # Convert dict to BoundingBox if needed
            if isinstance(bounding_box, dict):
                bounding_box = BoundingBox(**bounding_box)
            
            # Load page image
            page_image = self._load_image(page_image_path)
            if page_image is None:
                return ExtractionResult(
                    success=False,
                    error=f"Failed to load page image: {page_image_path}",
                    original_bbox=bounding_box,
                )
            
            page_width, page_height = page_image.size
            
            # Adjust bounding box with padding and clipping
            adjusted_bbox = self._adjust_bounding_box(
                bounding_box,
                page_width,
                page_height,
            )
            
            # Validate adjusted box
            if not self._validate_bbox(adjusted_bbox):
                return ExtractionResult(
                    success=False,
                    error="Invalid bounding box dimensions",
                    original_bbox=bounding_box,
                    adjusted_bbox=adjusted_bbox,
                )
            
            # Crop the image
            cropped = self._crop_image(page_image, adjusted_bbox)
            
            # Apply enhancement if enabled
            should_enhance = enhance if enhance is not None else self.enhance
            if should_enhance:
                cropped = self._enhance_image(cropped)
            
            # Resize if too large
            if cropped.width > self.max_size or cropped.height > self.max_size:
                cropped = self._resize_image(cropped, self.max_size)
            
            logger.debug(
                f"Extracted product image {product_id}: "
                f"{cropped.width}x{cropped.height}px"
            )
            
            return ExtractionResult(
                success=True,
                image=cropped,
                width=cropped.width,
                height=cropped.height,
                original_bbox=bounding_box,
                adjusted_bbox=adjusted_bbox,
                metadata={
                    "page_size": (page_width, page_height),
                    "enhanced": should_enhance,
                    "product_id": product_id,
                },
            )
            
        except Exception as e:
            logger.error(f"Failed to extract product image {product_id}: {e}")
            return ExtractionResult(
                success=False,
                error=str(e),
                original_bbox=bounding_box if isinstance(bounding_box, BoundingBox) else None,
            )
    
    def extract_batch(
        self,
        page_image_path: Union[str, Path],
        products: list,
    ) -> Dict[str, ExtractionResult]:
        """
        Extract multiple product images from a single page.
        
        More efficient than calling extract_product_image
        multiple times as it loads the page image once.
        
        Args:
            page_image_path: Path to the page image
            products: List of dicts with 'product_id' and 'bounding_box'
            
        Returns:
            Dict mapping product_id to ExtractionResult
        """
        results = {}
        
        try:
            # Load page image once
            page_image = self._load_image(page_image_path)
            if page_image is None:
                for product in products:
                    product_id = product.get("product_id", "unknown")
                    results[product_id] = ExtractionResult(
                        success=False,
                        error=f"Failed to load page image: {page_image_path}",
                    )
                return results
            
            page_width, page_height = page_image.size
            
            # Extract each product
            for product in products:
                product_id = product.get("product_id", "unknown")
                bbox = product.get("bounding_box")
                
                if bbox is None:
                    results[product_id] = ExtractionResult(
                        success=False,
                        error="Missing bounding box",
                    )
                    continue
                
                # Convert dict to BoundingBox if needed
                if isinstance(bbox, dict):
                    bbox = BoundingBox(**bbox)
                
                # Adjust and validate bbox
                adjusted_bbox = self._adjust_bounding_box(
                    bbox, page_width, page_height
                )
                
                if not self._validate_bbox(adjusted_bbox):
                    results[product_id] = ExtractionResult(
                        success=False,
                        error="Invalid bounding box",
                        original_bbox=bbox,
                        adjusted_bbox=adjusted_bbox,
                    )
                    continue
                
                # Crop and process
                cropped = self._crop_image(page_image, adjusted_bbox)
                
                if self.enhance:
                    cropped = self._enhance_image(cropped)
                
                if cropped.width > self.max_size or cropped.height > self.max_size:
                    cropped = self._resize_image(cropped, self.max_size)
                
                results[product_id] = ExtractionResult(
                    success=True,
                    image=cropped,
                    width=cropped.width,
                    height=cropped.height,
                    original_bbox=bbox,
                    adjusted_bbox=adjusted_bbox,
                    metadata={
                        "page_size": (page_width, page_height),
                        "enhanced": self.enhance,
                        "product_id": product_id,
                    },
                )
            
        except Exception as e:
            logger.error(f"Batch extraction failed: {e}")
            for product in products:
                product_id = product.get("product_id", "unknown")
                if product_id not in results:
                    results[product_id] = ExtractionResult(
                        success=False,
                        error=str(e),
                    )
        
        return results
    
    def _load_image(self, path: Union[str, Path]) -> Optional[Image.Image]:
        """Load an image from path."""
        try:
            path = Path(path)
            if not path.exists():
                logger.error(f"Image not found: {path}")
                return None
            
            image = Image.open(path)
            
            # Convert to RGB if needed (handles RGBA, P mode, etc.)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            
            return image
            
        except Exception as e:
            logger.error(f"Failed to load image {path}: {e}")
            return None
    
    def _adjust_bounding_box(
        self,
        bbox: BoundingBox,
        page_width: int,
        page_height: int,
    ) -> BoundingBox:
        """
        Adjust bounding box with padding and clip to page bounds.
        
        Args:
            bbox: Original bounding box
            page_width: Page width in pixels
            page_height: Page height in pixels
            
        Returns:
            Adjusted bounding box
        """
        # Apply padding
        x = max(0, bbox.x - self.padding)
        y = max(0, bbox.y - self.padding)
        
        # Calculate new dimensions
        width = bbox.width + (2 * self.padding)
        height = bbox.height + (2 * self.padding)
        
        # Clip to page bounds
        if x + width > page_width:
            width = page_width - x
        if y + height > page_height:
            height = page_height - y
        
        return BoundingBox(x=x, y=y, width=width, height=height)
    
    def _validate_bbox(self, bbox: BoundingBox) -> bool:
        """Validate bounding box dimensions."""
        return (
            bbox.width >= self.min_size and
            bbox.height >= self.min_size and
            bbox.x >= 0 and
            bbox.y >= 0
        )
    
    def _crop_image(
        self,
        image: Image.Image,
        bbox: BoundingBox,
    ) -> Image.Image:
        """Crop image using bounding box coordinates."""
        left = bbox.x
        top = bbox.y
        right = bbox.x + bbox.width
        bottom = bbox.y + bbox.height
        
        return image.crop((left, top, right, bottom))
    
    def _enhance_image(self, image: Image.Image) -> Image.Image:
        """
        Apply automatic image enhancement.
        
        Applies mild sharpening, contrast adjustment,
        and brightness normalization.
        """
        try:
            # Sharpen slightly
            image = image.filter(ImageFilter.SHARPEN)
            
            # Enhance contrast (1.1 = 10% increase)
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.1)
            
            # Adjust brightness if needed
            # (mild auto-adjustment for dark images)
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.02)
            
            return image
            
        except Exception as e:
            logger.warning(f"Image enhancement failed: {e}")
            return image
    
    def _resize_image(
        self,
        image: Image.Image,
        max_dimension: int,
    ) -> Image.Image:
        """
        Resize image while maintaining aspect ratio.
        
        Args:
            image: Image to resize
            max_dimension: Maximum width or height
            
        Returns:
            Resized image
        """
        width, height = image.size
        
        if width > height:
            new_width = max_dimension
            new_height = int(height * (max_dimension / width))
        else:
            new_height = max_dimension
            new_width = int(width * (max_dimension / height))
        
        return image.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )


def extract_product_from_page(
    page_image: Union[str, Path, Image.Image],
    bounding_box: Union[BoundingBox, Dict],
    padding: int = 2,
) -> Tuple[Optional[Image.Image], Optional[str]]:
    """
    Convenience function to extract a product image.
    
    Args:
        page_image: Page image path or PIL Image
        bounding_box: Bounding box coordinates
        padding: Padding to add around box
        
    Returns:
        Tuple of (extracted_image, error_message)
    """
    extractor = ImageExtractor(padding=padding)
    
    if isinstance(page_image, (str, Path)):
        result = extractor.extract_product_image(
            page_image,
            bounding_box,
            "temp_product",
        )
    else:
        # Direct image processing
        if isinstance(bounding_box, dict):
            bounding_box = BoundingBox(**bounding_box)
        
        page_width, page_height = page_image.size
        adjusted = extractor._adjust_bounding_box(
            bounding_box, page_width, page_height
        )
        
        if not extractor._validate_bbox(adjusted):
            return None, "Invalid bounding box"
        
        try:
            cropped = extractor._crop_image(page_image, adjusted)
            if extractor.enhance:
                cropped = extractor._enhance_image(cropped)
            return cropped, None
        except Exception as e:
            return None, str(e)
    
    if result.success:
        return result.image, None
    return None, result.error