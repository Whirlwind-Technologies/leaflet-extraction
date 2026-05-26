"""
Image Processing Module.

This module handles individual image processing for leaflet page uploads,
shared by both ZIP extraction and direct image upload flows.

Example Usage:
    from app.core.intake.image_processor import ImageProcessor

    processor = ImageProcessor()
    result = await processor.process_image(
        image_bytes=image_data,
        filename="page1.jpg",
        leaflet_id="LEAF_2025_001234",
        page_number=1
    )
"""

import asyncio
import io
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple

from PIL import Image

from app.config import settings
from app.utils.storage import (
    get_storage_backend,
    generate_page_path,
    generate_thumbnail_path,
)

logger = logging.getLogger(__name__)

# Thread pool for CPU-bound operations
_executor = ThreadPoolExecutor(max_workers=4)


# Image format magic bytes for validation
IMAGE_MAGIC_BYTES = {
    b'\xff\xd8\xff': 'JPEG',
    b'\x89PNG\r\n\x1a\n': 'PNG',
    b'RIFF': 'WEBP',  # WEBP starts with RIFF
    b'GIF87a': 'GIF',
    b'GIF89a': 'GIF',
    b'MM\x00*': 'TIFF',  # Big-endian TIFF
    b'II*\x00': 'TIFF',  # Little-endian TIFF
    b'BM': 'BMP',
}


@dataclass
class ImagePageResult:
    """Result of processing a single uploaded image."""
    page_number: int
    original_filename: str
    image_path: str
    thumbnail_path: str
    image_url: Optional[str]
    thumbnail_url: Optional[str]
    width: int
    height: int
    file_size: int
    format: str


@dataclass
class ImageProcessingResult:
    """Result of processing multiple images into a leaflet."""
    leaflet_id: str
    page_count: int
    pages: List[ImagePageResult]
    success: bool
    error_message: Optional[str] = None
    failed_images: Optional[List[dict]] = None


class ImageProcessor:
    """
    Handles image validation, standardization, and storage for leaflet pages.

    This class provides methods for:
    - Validating image files (format, dimensions)
    - Resizing images that are too large
    - Generating thumbnails
    - Uploading to storage

    Attributes:
        max_dimension: Maximum image dimension before resizing (default: 4096)
        output_format: Output format for processed images (default: PNG)
        thumbnail_size: Maximum thumbnail dimensions (default: 200x283)
        jpeg_quality: JPEG quality for thumbnails (default: 85)
    """

    ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP', 'TIFF', 'GIF', 'BMP'}
    MAX_DIMENSION = 4096
    MIN_DIMENSION = 100
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB per image

    def __init__(
        self,
        max_dimension: int = None,
        output_format: str = "PNG",
        thumbnail_size: Tuple[int, int] = (200, 283),
        jpeg_quality: int = 85,
    ):
        """
        Initialize image processor.

        Args:
            max_dimension: Max dimension before resizing
            output_format: Output format for images
            thumbnail_size: Max thumbnail dimensions
            jpeg_quality: JPEG quality for thumbnails
        """
        self.max_dimension = max_dimension or self.MAX_DIMENSION
        self.output_format = output_format
        self.thumbnail_size = thumbnail_size
        self.jpeg_quality = jpeg_quality
        self.storage = get_storage_backend()

    async def validate_image(
        self,
        image_bytes: bytes,
        filename: str,
    ) -> dict:
        """
        Validate an image file.

        Args:
            image_bytes: Image content as bytes
            filename: Original filename

        Returns:
            Dict with 'valid' boolean and optional 'error' message
        """
        try:
            # Check file size
            if len(image_bytes) > self.MAX_FILE_SIZE:
                return {
                    'valid': False,
                    'error': f'Image too large: {len(image_bytes) / (1024*1024):.1f}MB (max {self.MAX_FILE_SIZE / (1024*1024)}MB)'
                }

            if len(image_bytes) < 1000:
                return {
                    'valid': False,
                    'error': f'Image too small: {filename}'
                }

            # Check magic bytes
            detected_format = self._detect_format(image_bytes)
            if not detected_format:
                return {
                    'valid': False,
                    'error': f'Unsupported or invalid image format: {filename}'
                }

            # Try to open with PIL
            loop = asyncio.get_event_loop()

            def _validate():
                img = Image.open(io.BytesIO(image_bytes))
                img.verify()  # Verify image integrity

                # Re-open after verify (verify closes the file)
                img = Image.open(io.BytesIO(image_bytes))

                width, height = img.size

                if width < self.MIN_DIMENSION or height < self.MIN_DIMENSION:
                    raise ValueError(
                        f'Image too small: {width}x{height}px (minimum {self.MIN_DIMENSION}x{self.MIN_DIMENSION})'
                    )

                if width > 10000 or height > 10000:
                    raise ValueError(
                        f'Image too large: {width}x{height}px (maximum 10000x10000)'
                    )

                return {
                    'format': img.format,
                    'width': width,
                    'height': height,
                    'mode': img.mode,
                }

            result = await loop.run_in_executor(_executor, _validate)

            return {
                'valid': True,
                **result,
            }

        except Exception as e:
            return {
                'valid': False,
                'error': f'Invalid image {filename}: {str(e)}'
            }

    def _detect_format(self, image_bytes: bytes) -> Optional[str]:
        """Detect image format from magic bytes."""
        for magic, fmt in IMAGE_MAGIC_BYTES.items():
            if image_bytes.startswith(magic):
                return fmt
        # Special case for WEBP (RIFF....WEBP)
        if image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:12]:
            return 'WEBP'
        return None

    async def process_image(
        self,
        image_bytes: bytes,
        filename: str,
        leaflet_id: str,
        page_number: int,
    ) -> ImagePageResult:
        """
        Process a single image: validate, standardize, thumbnail, upload.

        Args:
            image_bytes: Image content as bytes
            filename: Original filename
            leaflet_id: Leaflet identifier
            page_number: Page number (1-indexed)

        Returns:
            ImagePageResult with paths and metadata

        Raises:
            ValueError: If image is invalid
        """
        # Validate first
        validation = await self.validate_image(image_bytes, filename)
        if not validation['valid']:
            raise ValueError(validation['error'])

        loop = asyncio.get_event_loop()

        # Process the image
        def _process():
            img = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if necessary (for PNG with transparency, etc.)
            if img.mode in ('RGBA', 'P', 'LA'):
                # Create white background for transparency
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            original_size = img.size

            # Resize if too large
            if max(img.size) > self.max_dimension:
                img.thumbnail(
                    (self.max_dimension, self.max_dimension),
                    Image.Resampling.LANCZOS
                )
                logger.info(
                    f"Resized image {filename} from {original_size} to {img.size}"
                )

            # Save as PNG
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            processed_bytes = buffer.getvalue()

            # Generate thumbnail
            thumb = img.copy()
            thumb.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
            if thumb.mode != 'RGB':
                thumb = thumb.convert('RGB')
            thumb_buffer = io.BytesIO()
            thumb.save(thumb_buffer, format='JPEG', quality=self.jpeg_quality, optimize=True)
            thumbnail_bytes = thumb_buffer.getvalue()

            return {
                'processed_bytes': processed_bytes,
                'thumbnail_bytes': thumbnail_bytes,
                'width': img.width,
                'height': img.height,
            }

        result = await loop.run_in_executor(_executor, _process)

        # Upload to storage
        image_path = generate_page_path(leaflet_id, page_number, 'png')
        thumbnail_path = generate_thumbnail_path(leaflet_id, page_number, 'jpg')

        # Upload concurrently
        image_url, thumbnail_url = await asyncio.gather(
            self.storage.upload_file(
                file_content=result['processed_bytes'],
                file_path=image_path,
                content_type="image/png",
            ),
            self.storage.upload_file(
                file_content=result['thumbnail_bytes'],
                file_path=thumbnail_path,
                content_type="image/jpeg",
            ),
        )

        logger.debug(f"Processed image {filename} as page {page_number} for leaflet {leaflet_id}")

        return ImagePageResult(
            page_number=page_number,
            original_filename=filename,
            image_path=image_path,
            thumbnail_path=thumbnail_path,
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            width=result['width'],
            height=result['height'],
            file_size=len(result['processed_bytes']),
            format='PNG',
        )

    async def process_images(
        self,
        images: List[Tuple[bytes, str]],
        leaflet_id: str,
    ) -> ImageProcessingResult:
        """
        Process multiple images into leaflet pages.

        Args:
            images: List of (content, filename) tuples in page order
            leaflet_id: Leaflet identifier

        Returns:
            ImageProcessingResult with all page results
        """
        if not images:
            return ImageProcessingResult(
                leaflet_id=leaflet_id,
                page_count=0,
                pages=[],
                success=False,
                error_message="No images provided",
            )

        pages = []
        failed_images = []

        for page_num, (image_bytes, filename) in enumerate(images, start=1):
            try:
                page_result = await self.process_image(
                    image_bytes=image_bytes,
                    filename=filename,
                    leaflet_id=leaflet_id,
                    page_number=page_num,
                )
                pages.append(page_result)
            except Exception as e:
                logger.error(f"Failed to process image {filename}: {e}")
                failed_images.append({
                    'index': page_num - 1,
                    'filename': filename,
                    'error': str(e),
                })

        # If all images failed, return error
        if not pages:
            return ImageProcessingResult(
                leaflet_id=leaflet_id,
                page_count=0,
                pages=[],
                success=False,
                error_message="All images failed to process",
                failed_images=failed_images,
            )

        logger.info(
            f"Processed {len(pages)} images for leaflet {leaflet_id}"
            + (f" ({len(failed_images)} failed)" if failed_images else "")
        )

        return ImageProcessingResult(
            leaflet_id=leaflet_id,
            page_count=len(pages),
            pages=pages,
            success=True,
            failed_images=failed_images if failed_images else None,
        )


# Singleton instance
_image_processor: Optional[ImageProcessor] = None


def get_image_processor() -> ImageProcessor:
    """Get the image processor instance."""
    global _image_processor
    if _image_processor is None:
        _image_processor = ImageProcessor()
    return _image_processor


def reset_image_processor():
    """Reset the image processor (useful for testing)."""
    global _image_processor
    _image_processor = None
