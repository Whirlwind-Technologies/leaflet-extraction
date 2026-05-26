"""
PDF Processing Module.

This module handles PDF file processing including:
- PDF validation and integrity checks
- Conversion of PDF pages to high-resolution images
- Thumbnail generation
- Metadata extraction

Example Usage:
    from app.core.intake.pdf_processor import PDFProcessor
    
    processor = PDFProcessor()
    result = await processor.process_pdf(
        pdf_content=pdf_bytes,
        leaflet_id="LEAF_2025_001234"
    )
    
    print(f"Processed {result['page_count']} pages")
"""

import asyncio
import io
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional, Union

from PIL import Image

from app.config import settings
from app.utils.storage import (
    get_storage_backend,
    generate_page_path,
    generate_thumbnail_path,
    generate_storage_path,
)

logger = logging.getLogger(__name__)

# Thread pool for CPU-bound operations
_executor = ThreadPoolExecutor(max_workers=4)


@dataclass
class PageResult:
    """Result of processing a single PDF page."""
    page_number: int
    image_path: str
    thumbnail_path: str
    image_url: Optional[str]
    thumbnail_url: Optional[str]
    width: int
    height: int
    file_size: int
    format: str


@dataclass
class PDFProcessingResult:
    """Result of processing a complete PDF."""
    leaflet_id: str
    page_count: int
    pages: list[PageResult]
    source_path: str
    pdf_type: str  # 'text' or 'image'
    metadata: dict
    success: bool
    error_message: Optional[str] = None


class PDFProcessor:
    """
    Handles PDF to image conversion and processing.
    
    This class provides methods for:
    - Validating PDF files
    - Converting PDF pages to PNG images
    - Generating thumbnails
    - Extracting PDF metadata
    
    Attributes:
        dpi: Resolution for rendering PDF pages (default: 300)
        output_format: Output image format (default: PNG)
        thumbnail_size: Maximum thumbnail dimensions (default: 200x283)
        jpeg_quality: JPEG quality for thumbnails (default: 85)
    """

    def __init__(
        self,
        dpi: int = None,
        output_format: str = None,
        thumbnail_size: tuple[int, int] = (200, 283),
        jpeg_quality: int = 85,
    ):
        """
        Initialize PDF processor.
        
        Args:
            dpi: DPI for rendering (default from settings)
            output_format: Output format (default from settings)
            thumbnail_size: Max thumbnail dimensions
            jpeg_quality: JPEG quality for thumbnails
        """
        self.dpi = dpi or settings.pdf_dpi
        self.output_format = output_format or settings.pdf_output_format
        self.thumbnail_size = thumbnail_size
        self.jpeg_quality = jpeg_quality
        self.storage = get_storage_backend()

    async def process_pdf(
        self,
        pdf_content: Union[bytes, BinaryIO],
        leaflet_id: str,
        save_source: bool = True,
    ) -> PDFProcessingResult:
        """
        Process a PDF file and convert all pages to images.
        
        This method:
        1. Validates the PDF
        2. Saves the source PDF (optional)
        3. Converts each page to a high-resolution image
        4. Generates thumbnails for each page
        5. Uploads all files to storage
        
        Args:
            pdf_content: PDF file content as bytes or file-like object
            leaflet_id: Unique identifier for the leaflet
            save_source: Whether to save the source PDF
            
        Returns:
            PDFProcessingResult with page information
            
        Raises:
            ValueError: If PDF is invalid or cannot be processed
        """
        try:
            # Convert to bytes if needed
            if isinstance(pdf_content, bytes):
                pdf_bytes = pdf_content
            else:
                pdf_bytes = pdf_content.read()

            # Validate PDF
            validation_result = await self._validate_pdf(pdf_bytes)
            if not validation_result['valid']:
                return PDFProcessingResult(
                    leaflet_id=leaflet_id,
                    page_count=0,
                    pages=[],
                    source_path="",
                    pdf_type="unknown",
                    metadata={},
                    success=False,
                    error_message=validation_result['error'],
                )

            # Save source PDF
            source_path = ""
            if save_source:
                source_path = await self._save_source_pdf(pdf_bytes, leaflet_id)

            # Extract metadata
            metadata = await self._extract_metadata(pdf_bytes)

            # Detect PDF type (text-based or image-based)
            pdf_type = await self._detect_pdf_type(pdf_bytes)

            # Convert pages to images
            pages = await self._convert_pages(pdf_bytes, leaflet_id)

            logger.info(
                f"Successfully processed PDF {leaflet_id}: "
                f"{len(pages)} pages, type={pdf_type}"
            )

            return PDFProcessingResult(
                leaflet_id=leaflet_id,
                page_count=len(pages),
                pages=pages,
                source_path=source_path,
                pdf_type=pdf_type,
                metadata=metadata,
                success=True,
            )

        except Exception as e:
            logger.error(f"Error processing PDF {leaflet_id}: {e}")
            return PDFProcessingResult(
                leaflet_id=leaflet_id,
                page_count=0,
                pages=[],
                source_path="",
                pdf_type="unknown",
                metadata={},
                success=False,
                error_message=str(e),
            )

    async def _validate_pdf(self, pdf_bytes: bytes) -> dict:
        """
        Validate PDF file integrity.
        
        Args:
            pdf_bytes: PDF content as bytes
            
        Returns:
            Dict with 'valid' boolean and optional 'error' message
        """
        try:
            # Check PDF magic bytes
            if not pdf_bytes.startswith(b'%PDF'):
                return {'valid': False, 'error': 'Invalid PDF: missing PDF header'}

            # Check minimum size
            if len(pdf_bytes) < 100:
                return {'valid': False, 'error': 'Invalid PDF: file too small'}

            # Check for EOF marker
            if b'%%EOF' not in pdf_bytes[-1024:]:
                logger.warning("PDF missing EOF marker, may be corrupted")

            # Try to open with pypdf to validate structure
            loop = asyncio.get_event_loop()
            
            def _validate():
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(pdf_bytes))
                page_count = len(reader.pages)
                
                if page_count == 0:
                    raise ValueError("PDF has no pages")
                
                if page_count > settings.pdf_max_pages:
                    raise ValueError(
                        f"PDF has too many pages ({page_count}). "
                        f"Maximum is {settings.pdf_max_pages}"
                    )
                
                return page_count

            page_count = await loop.run_in_executor(_executor, _validate)
            
            return {'valid': True, 'page_count': page_count}

        except Exception as e:
            return {'valid': False, 'error': f'Invalid PDF: {str(e)}'}

    async def _extract_metadata(self, pdf_bytes: bytes) -> dict:
        """
        Extract metadata from PDF.
        
        Args:
            pdf_bytes: PDF content as bytes
            
        Returns:
            Dict with PDF metadata
        """
        loop = asyncio.get_event_loop()

        def _extract():
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            
            metadata = {}
            
            # Get document info
            if reader.metadata:
                for key in ['/Title', '/Author', '/Subject', '/Creator', 
                           '/Producer', '/CreationDate', '/ModDate']:
                    value = reader.metadata.get(key)
                    if value:
                        # Clean key name
                        clean_key = key.lstrip('/').lower()
                        metadata[clean_key] = str(value)
            
            # Get page info
            metadata['page_count'] = len(reader.pages)
            
            # Get first page dimensions
            if reader.pages:
                first_page = reader.pages[0]
                media_box = first_page.mediabox
                metadata['page_width'] = float(media_box.width)
                metadata['page_height'] = float(media_box.height)
            
            return metadata

        return await loop.run_in_executor(_executor, _extract)

    async def _detect_pdf_type(self, pdf_bytes: bytes) -> str:
        """
        Detect if PDF is text-based or image-based.
        
        Args:
            pdf_bytes: PDF content as bytes
            
        Returns:
            'text' if text-based, 'image' if scanned/image-based
        """
        loop = asyncio.get_event_loop()

        def _detect():
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            
            # Check first few pages for text content
            text_found = False
            pages_to_check = min(3, len(reader.pages))
            
            for i in range(pages_to_check):
                page = reader.pages[i]
                text = page.extract_text()
                if text and len(text.strip()) > 50:
                    text_found = True
                    break
            
            return 'text' if text_found else 'image'

        return await loop.run_in_executor(_executor, _detect)

    async def _save_source_pdf(self, pdf_bytes: bytes, leaflet_id: str) -> str:
        """
        Save the source PDF to storage.
        
        Args:
            pdf_bytes: PDF content as bytes
            leaflet_id: Leaflet identifier
            
        Returns:
            Storage path of saved PDF
        """
        source_path = generate_storage_path(leaflet_id, "original.pdf", "source")
        await self.storage.upload_file(
            file_content=pdf_bytes,
            file_path=source_path,
            content_type="application/pdf",
        )
        return source_path

    async def _convert_pages(
        self,
        pdf_bytes: bytes,
        leaflet_id: str,
    ) -> list[PageResult]:
        """
        Convert all PDF pages to images.
        
        Args:
            pdf_bytes: PDF content as bytes
            leaflet_id: Leaflet identifier
            
        Returns:
            List of PageResult objects
        """
        loop = asyncio.get_event_loop()

        # Convert PDF to images using pdf2image (CPU-bound)
        def _convert_to_images():
            from pdf2image import convert_from_bytes
            
            images = convert_from_bytes(
                pdf_bytes,
                dpi=self.dpi,
                fmt=self.output_format.lower(),
                thread_count=2,
            )
            return images

        logger.debug(f"Converting PDF {leaflet_id} to images at {self.dpi} DPI")
        images = await loop.run_in_executor(_executor, _convert_to_images)

        # Process each page
        pages = []
        for page_num, image in enumerate(images, start=1):
            page_result = await self._process_page(
                image=image,
                leaflet_id=leaflet_id,
                page_number=page_num,
            )
            pages.append(page_result)

        return pages

    async def _process_page(
        self,
        image: Image.Image,
        leaflet_id: str,
        page_number: int,
    ) -> PageResult:
        """
        Process a single page image.
        
        Args:
            image: PIL Image of the page
            leaflet_id: Leaflet identifier
            page_number: Page number (1-indexed)
            
        Returns:
            PageResult with paths and metadata
        """
        loop = asyncio.get_event_loop()

        # Convert image to bytes
        def _image_to_bytes(img: Image.Image, fmt: str, quality: int = 95) -> bytes:
            buffer = io.BytesIO()
            if fmt.upper() == 'PNG':
                img.save(buffer, format='PNG', optimize=True)
            else:
                # Convert to RGB for JPEG
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(buffer, format='JPEG', quality=quality, optimize=True)
            return buffer.getvalue()

        # Generate full-size image
        image_bytes = await loop.run_in_executor(
            _executor,
            lambda: _image_to_bytes(image, self.output_format)
        )

        # Generate thumbnail
        def _create_thumbnail(img: Image.Image) -> bytes:
            thumb = img.copy()
            thumb.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
            # Convert to RGB for JPEG thumbnail
            if thumb.mode in ('RGBA', 'P'):
                thumb = thumb.convert('RGB')
            buffer = io.BytesIO()
            thumb.save(buffer, format='JPEG', quality=self.jpeg_quality, optimize=True)
            return buffer.getvalue()

        thumbnail_bytes = await loop.run_in_executor(
            _executor,
            lambda: _create_thumbnail(image)
        )

        # Upload to storage
        image_path = generate_page_path(leaflet_id, page_number, self.output_format.lower())
        thumbnail_path = generate_thumbnail_path(leaflet_id, page_number, 'jpg')

        # Upload concurrently
        image_url_task = self.storage.upload_file(
            file_content=image_bytes,
            file_path=image_path,
            content_type=f"image/{self.output_format.lower()}",
        )
        thumbnail_url_task = self.storage.upload_file(
            file_content=thumbnail_bytes,
            file_path=thumbnail_path,
            content_type="image/jpeg",
        )

        image_url, thumbnail_url = await asyncio.gather(
            image_url_task,
            thumbnail_url_task,
        )

        logger.debug(f"Processed page {page_number} for leaflet {leaflet_id}")

        return PageResult(
            page_number=page_number,
            image_path=image_path,
            thumbnail_path=thumbnail_path,
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            width=image.width,
            height=image.height,
            file_size=len(image_bytes),
            format=self.output_format.upper(),
        )

    async def get_page_count(self, pdf_content: Union[bytes, BinaryIO]) -> int:
        """
        Get the number of pages in a PDF without full processing.
        
        Args:
            pdf_content: PDF content as bytes or file-like object
            
        Returns:
            Number of pages in the PDF
        """
        if isinstance(pdf_content, bytes):
            pdf_bytes = pdf_content
        else:
            pdf_bytes = pdf_content.read()

        loop = asyncio.get_event_loop()

        def _count_pages():
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            return len(reader.pages)

        return await loop.run_in_executor(_executor, _count_pages)

    async def extract_page(
        self,
        pdf_content: Union[bytes, BinaryIO],
        page_number: int,
    ) -> Image.Image:
        """
        Extract a single page from a PDF as an image.
        
        Args:
            pdf_content: PDF content as bytes or file-like object
            page_number: Page number to extract (1-indexed)
            
        Returns:
            PIL Image of the page
        """
        if isinstance(pdf_content, bytes):
            pdf_bytes = pdf_content
        else:
            pdf_bytes = pdf_content.read()

        loop = asyncio.get_event_loop()

        def _extract_page():
            from pdf2image import convert_from_bytes
            
            images = convert_from_bytes(
                pdf_bytes,
                dpi=self.dpi,
                first_page=page_number,
                last_page=page_number,
                fmt=self.output_format.lower(),
            )
            return images[0] if images else None

        return await loop.run_in_executor(_executor, _extract_page)


# Singleton instance
_pdf_processor: Optional[PDFProcessor] = None


def get_pdf_processor() -> PDFProcessor:
    """Get the PDF processor instance."""
    global _pdf_processor
    if _pdf_processor is None:
        _pdf_processor = PDFProcessor()
    return _pdf_processor


def reset_pdf_processor():
    """Reset the PDF processor (useful for testing)."""
    global _pdf_processor
    _pdf_processor = None