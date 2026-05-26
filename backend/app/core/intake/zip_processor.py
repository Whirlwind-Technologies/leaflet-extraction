"""
ZIP Processing Module.

This module handles ZIP file extraction and processing for leaflet uploads
containing page images.

Example Usage:
    from app.core.intake.zip_processor import ZIPProcessor

    processor = ZIPProcessor()
    result = await processor.process_zip(
        zip_content=zip_bytes,
        leaflet_id="LEAF_2025_001234"
    )
"""

import asyncio
import io
import logging
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.intake.image_processor import (
    ImageProcessor,
    ImagePageResult,
    get_image_processor,
)
from app.utils.storage import (
    get_storage_backend,
    generate_storage_path,
)

logger = logging.getLogger(__name__)

# Thread pool for CPU-bound operations
_executor = ThreadPoolExecutor(max_workers=4)


@dataclass
class ZIPProcessingResult:
    """Result of processing a ZIP file with images."""
    leaflet_id: str
    page_count: int
    pages: List[ImagePageResult]
    source_path: str
    success: bool
    error_message: Optional[str] = None
    failed_images: Optional[List[dict]] = None
    skipped_files: Optional[List[str]] = None


class ZIPProcessor:
    """
    Handles ZIP file extraction and image processing for leaflet pages.

    This class provides methods for:
    - Validating ZIP files
    - Extracting image files
    - Filtering out Mac OS metadata files
    - Sorting images by natural filename order
    - Processing images via ImageProcessor

    Attributes:
        image_processor: ImageProcessor instance for image handling
    """

    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.tif'}
    IGNORED_PREFIXES = ('__MACOSX/', '__MACOSX\\', '._', '.DS_Store')
    MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_IMAGES = 100

    def __init__(self, image_processor: ImageProcessor = None):
        """
        Initialize ZIP processor.

        Args:
            image_processor: Optional ImageProcessor instance
        """
        self.image_processor = image_processor or get_image_processor()
        self.storage = get_storage_backend()

    async def process_zip(
        self,
        zip_content: bytes,
        leaflet_id: str,
        save_source: bool = True,
    ) -> ZIPProcessingResult:
        """
        Process a ZIP file containing leaflet page images.

        This method:
        1. Validates the ZIP file
        2. Saves the source ZIP (optional)
        3. Extracts and filters image files
        4. Sorts images by natural filename order
        5. Processes each image via ImageProcessor

        Args:
            zip_content: ZIP file content as bytes
            leaflet_id: Unique identifier for the leaflet
            save_source: Whether to save the source ZIP

        Returns:
            ZIPProcessingResult with page information
        """
        try:
            # Validate ZIP
            validation = await self._validate_zip(zip_content)
            if not validation['valid']:
                return ZIPProcessingResult(
                    leaflet_id=leaflet_id,
                    page_count=0,
                    pages=[],
                    source_path="",
                    success=False,
                    error_message=validation['error'],
                )

            # Save source ZIP
            source_path = ""
            if save_source:
                source_path = await self._save_source_zip(zip_content, leaflet_id)

            # Extract and sort images
            images, skipped = await self._extract_and_sort_images(zip_content)

            if not images:
                return ZIPProcessingResult(
                    leaflet_id=leaflet_id,
                    page_count=0,
                    pages=[],
                    source_path=source_path,
                    success=False,
                    error_message="ZIP contains no valid image files",
                    skipped_files=skipped,
                )

            if len(images) > self.MAX_IMAGES:
                return ZIPProcessingResult(
                    leaflet_id=leaflet_id,
                    page_count=0,
                    pages=[],
                    source_path=source_path,
                    success=False,
                    error_message=f"ZIP contains too many images ({len(images)}). Maximum is {self.MAX_IMAGES}",
                )

            # Process images via ImageProcessor
            result = await self.image_processor.process_images(images, leaflet_id)

            logger.info(
                f"Processed ZIP {leaflet_id}: {result.page_count} pages"
                + (f" ({len(skipped)} files skipped)" if skipped else "")
            )

            return ZIPProcessingResult(
                leaflet_id=leaflet_id,
                page_count=result.page_count,
                pages=result.pages,
                source_path=source_path,
                success=result.success,
                error_message=result.error_message,
                failed_images=result.failed_images,
                skipped_files=skipped if skipped else None,
            )

        except Exception as e:
            logger.error(f"Error processing ZIP {leaflet_id}: {e}")
            return ZIPProcessingResult(
                leaflet_id=leaflet_id,
                page_count=0,
                pages=[],
                source_path="",
                success=False,
                error_message=str(e),
            )

    async def _validate_zip(self, zip_content: bytes) -> dict:
        """
        Validate ZIP file integrity.

        Args:
            zip_content: ZIP content as bytes

        Returns:
            Dict with 'valid' boolean and optional 'error' message
        """
        try:
            # Check magic bytes (PK\x03\x04 for ZIP)
            if not zip_content.startswith(b'PK\x03\x04'):
                return {'valid': False, 'error': 'Invalid ZIP: missing ZIP header'}

            # Check size
            if len(zip_content) > self.MAX_ZIP_SIZE:
                return {
                    'valid': False,
                    'error': f'ZIP too large: {len(zip_content) / (1024*1024):.1f}MB (max {self.MAX_ZIP_SIZE / (1024*1024)}MB)'
                }

            if len(zip_content) < 100:
                return {'valid': False, 'error': 'Invalid ZIP: file too small'}

            # Try to open as ZIP
            loop = asyncio.get_event_loop()

            def _validate():
                with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zf:
                    # Check for corruption
                    bad_file = zf.testzip()
                    if bad_file:
                        raise zipfile.BadZipFile(f"Corrupted file in archive: {bad_file}")

                    # Count valid image files
                    image_count = 0
                    for name in zf.namelist():
                        if self._is_valid_image_file(name):
                            image_count += 1

                    return image_count

            image_count = await loop.run_in_executor(_executor, _validate)

            if image_count == 0:
                return {'valid': False, 'error': 'ZIP contains no valid image files'}

            return {'valid': True, 'image_count': image_count}

        except zipfile.BadZipFile as e:
            return {'valid': False, 'error': f'Invalid ZIP: {str(e)}'}
        except Exception as e:
            return {'valid': False, 'error': f'Error validating ZIP: {str(e)}'}

    def _should_skip_file(self, filename: str) -> bool:
        """
        Check if file should be skipped (Mac metadata, hidden files).

        Args:
            filename: File path within ZIP

        Returns:
            True if file should be skipped
        """
        # Normalize path separators
        normalized = filename.replace('\\', '/')

        # Check prefixes
        for prefix in self.IGNORED_PREFIXES:
            if normalized.startswith(prefix) or f'/{prefix}' in normalized:
                return True

        # Check for hidden files (starting with .)
        basename = Path(normalized).name
        if basename.startswith('.'):
            return True

        return False

    def _is_valid_image_file(self, filename: str) -> bool:
        """
        Check if file is a valid image file.

        Args:
            filename: File path within ZIP

        Returns:
            True if file has supported image extension
        """
        if self._should_skip_file(filename):
            return False

        ext = Path(filename).suffix.lower()
        return ext in self.SUPPORTED_EXTENSIONS

    def _natural_sort_key(self, filename: str) -> List:
        """
        Natural sort key for filenames.

        Handles filenames like:
        - 1.jpg, 2.jpg, 10.jpg, 11.jpg -> sorted as 1, 2, 10, 11
        - page_1.png, page_2.png, page_10.png -> sorted correctly
        - dis1.jpg, dis2.jpg, dis3.jpg -> sorted correctly

        Args:
            filename: Filename to create sort key for

        Returns:
            Sort key list for natural sorting
        """
        # Get just the filename without path
        name = Path(filename).stem

        # Split into text and numeric parts
        parts = re.split(r'(\d+)', name)

        # Convert numeric parts to integers for proper sorting
        return [int(part) if part.isdigit() else part.lower() for part in parts]

    async def _extract_and_sort_images(
        self,
        zip_content: bytes,
    ) -> Tuple[List[Tuple[bytes, str]], List[str]]:
        """
        Extract images from ZIP and sort by natural filename order.

        Args:
            zip_content: ZIP content as bytes

        Returns:
            Tuple of (list of (image_bytes, filename) tuples, list of skipped files)
        """
        loop = asyncio.get_event_loop()

        def _extract():
            images = []
            skipped = []

            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zf:
                for name in zf.namelist():
                    # Skip directories
                    if name.endswith('/') or name.endswith('\\'):
                        continue

                    # Skip non-image files
                    if not self._is_valid_image_file(name):
                        if not self._should_skip_file(name):
                            # Only log non-metadata skipped files
                            skipped.append(name)
                        continue

                    try:
                        image_bytes = zf.read(name)
                        # Get just the filename for display
                        display_name = Path(name).name
                        images.append((name, image_bytes, display_name))
                    except Exception as e:
                        logger.warning(f"Failed to extract {name}: {e}")
                        skipped.append(name)

            # Sort by natural order
            images.sort(key=lambda x: self._natural_sort_key(x[0]))

            # Return just (bytes, filename) tuples in sorted order
            return [(img[1], img[2]) for img in images], skipped

        return await loop.run_in_executor(_executor, _extract)

    async def _save_source_zip(self, zip_content: bytes, leaflet_id: str) -> str:
        """
        Save the source ZIP to storage.

        Args:
            zip_content: ZIP content as bytes
            leaflet_id: Leaflet identifier

        Returns:
            Storage path of saved ZIP
        """
        source_path = generate_storage_path(leaflet_id, "original.zip", "source")
        await self.storage.upload_file(
            file_content=zip_content,
            file_path=source_path,
            content_type="application/zip",
        )
        return source_path

    async def get_image_count(self, zip_content: bytes) -> int:
        """
        Get the number of images in a ZIP without full processing.

        Args:
            zip_content: ZIP content as bytes

        Returns:
            Number of valid image files in the ZIP
        """
        loop = asyncio.get_event_loop()

        def _count():
            count = 0
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zf:
                for name in zf.namelist():
                    if self._is_valid_image_file(name):
                        count += 1
            return count

        return await loop.run_in_executor(_executor, _count)


# Singleton instance
_zip_processor: Optional[ZIPProcessor] = None


def get_zip_processor() -> ZIPProcessor:
    """Get the ZIP processor instance."""
    global _zip_processor
    if _zip_processor is None:
        _zip_processor = ZIPProcessor()
    return _zip_processor


def reset_zip_processor():
    """Reset the ZIP processor (useful for testing)."""
    global _zip_processor
    _zip_processor = None
