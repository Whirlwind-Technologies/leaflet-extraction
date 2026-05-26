"""
Intake Module.

This module handles PDF upload, validation, and preprocessing.

Components:
    - pdf_processor: PDF to image conversion
    - validator: PDF validation rules
"""

from app.core.intake.pdf_processor import (
    PDFProcessor,
    PDFProcessingResult,
    PageResult,
    get_pdf_processor,
)

__all__ = [
    "PDFProcessor",
    "PDFProcessingResult",
    "PageResult",
    "get_pdf_processor",
]