"""
Extraction Schemas Module.

This module defines Pydantic models for VLM extraction input/output,
including product data structures and validation.

Example Usage:
    from app.core.extraction.schemas import ExtractedProduct, ExtractionResult
    
    product = ExtractedProduct(
        bounding_box=BoundingBox(x=50, y=100, width=280, height=350),
        brand="Coca-Cola",
        product_name="Coca-Cola Zero Sugar 2L",
        discounted_price=1.99,
        confidence_score=0.95
    )
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class BoundingBox(BaseModel):
    """
    Bounding box coordinates for a product on a page.
    
    Coordinates are in pixels from top-left origin.
    
    Attributes:
        x: X coordinate of top-left corner
        y: Y coordinate of top-left corner
        width: Width of bounding box
        height: Height of bounding box
    """
    x: int = Field(..., ge=0, description="X coordinate (top-left)")
    y: int = Field(..., ge=0, description="Y coordinate (top-left)")
    width: int = Field(..., gt=0, description="Width in pixels")
    height: int = Field(..., gt=0, description="Height in pixels")
    
    @property
    def area(self) -> int:
        """Calculate bounding box area."""
        return self.width * self.height
    
    @property
    def center(self) -> tuple[int, int]:
        """Get center point of bounding box."""
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    def contains_point(self, px: int, py: int) -> bool:
        """Check if a point is inside the bounding box."""
        return (
            self.x <= px <= self.x + self.width and
            self.y <= py <= self.y + self.height
        )
    
    def overlaps(self, other: "BoundingBox") -> bool:
        """Check if this bounding box overlaps with another."""
        return not (
            self.x + self.width < other.x or
            other.x + other.width < self.x or
            self.y + self.height < other.y or
            other.y + other.height < self.y
        )


class FieldConfidence(BaseModel):
    """
    Per-field confidence scores from VLM extraction.

    All scores are between 0.0 and 1.0.
    """
    brand: Optional[float] = Field(None, ge=0, le=1)
    product_code: Optional[float] = Field(None, ge=0, le=1)
    product_name: Optional[float] = Field(None, ge=0, le=1)
    quantity: Optional[float] = Field(None, ge=0, le=1)
    units: Optional[float] = Field(None, ge=0, le=1)
    regular_price: Optional[float] = Field(None, ge=0, le=1)
    discounted_price: Optional[float] = Field(None, ge=0, le=1)
    discount_percentage: Optional[float] = Field(None, ge=0, le=1)
    currency: Optional[float] = Field(None, ge=0, le=1)
    product_id: Optional[float] = Field(None, ge=0, le=1)
    suggested_category: Optional[float] = Field(None, ge=0, le=1)

    def average(self) -> float:
        """Calculate average confidence across all fields."""
        scores = [v for v in self.model_dump().values() if v is not None]
        return sum(scores) / len(scores) if scores else 0.0


class ExtractedProduct(BaseModel):
    """
    A single product extracted from a leaflet page.

    Contains all extracted fields plus confidence scores
    and uncertainty flags.

    NOTE: bounding_box is optional during VLM extraction and is filled in
    by OCR-based post-processing. The VLM provides position_hint instead.

    Attributes:
        bounding_box: Location on page (filled by OCR post-processing)
        position_hint: VLM's description of where product is on page
        brand: Product brand name
        product_code: SKU, item number, reference code
        product_name: Full product description
        quantity: Numeric quantity
        units: Unit of measurement
        regular_price: Original price (if shown)
        discounted_price: Current/promotional price
        discount_percentage: Calculated or displayed discount
        currency: Currency symbol/code
        product_id: Barcode/EAN if visible
        promotional_info: Badges, deals, conditions
        confidence_score: Overall extraction confidence
        field_confidence: Per-field confidence scores
        uncertainty_flags: List of uncertain elements
    """
    bounding_box: Optional[BoundingBox] = Field(
        None,
        description="Location on page (filled by OCR post-processing)"
    )
    position_hint: Optional[str] = Field(
        None,
        max_length=200,
        description="VLM's description of product location (e.g., 'top-left', 'middle row, second from right')"
    )
    brand: Optional[str] = Field(None, max_length=200)
    product_code: Optional[str] = Field(None, max_length=100)
    product_name: str = Field(..., min_length=1, max_length=500)
    quantity: Optional[float] = Field(None, gt=0)
    units: Optional[str] = Field(None, max_length=20)
    size: Optional[str] = Field(None, max_length=50)
    regular_price: Optional[float] = Field(None, ge=0)
    discounted_price: Optional[float] = Field(None, ge=0)
    discount_percentage: Optional[float] = Field(None, ge=0, le=100)
    currency: Optional[str] = Field(None, max_length=10)
    product_id: Optional[str] = Field(None, max_length=100)
    promotional_info: Optional[str] = Field(None, max_length=500)
    suggested_category: Optional[str] = Field(
        None,
        max_length=100,
        description="AI-suggested product category"
    )
    category_confidence: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        description="Confidence in category suggestion"
    )
    category_alternatives: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Alternative category suggestions with confidence scores"
    )
    confidence_score: float = Field(..., ge=0, le=1)
    field_confidence: Optional[FieldConfidence] = None
    uncertainty_flags: List[str] = Field(default_factory=list)
    is_split_product: bool = Field(
        default=False,
        description="Whether this product was merged from split parts"
    )
    merged_from_pages: Optional[List[Any]] = Field(
        default=None,
        description="Original bounding boxes if merged from split product"
    )
    source_page: Optional[int] = Field(
        default=None,
        description="Original page number before reconciliation"
    )
    
    @field_validator('brand', 'product_name', 'product_code', mode='before')
    @classmethod
    def clean_string_fields(cls, v):
        """Clean string fields by stripping whitespace."""
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v
    
    @model_validator(mode='after')
    def calculate_discount_if_missing(self):
        """Calculate discount percentage if not provided but prices are."""
        if (
            self.discount_percentage is None and
            self.regular_price is not None and
            self.discounted_price is not None and
            self.regular_price > 0 and
            self.regular_price > self.discounted_price
        ):
            self.discount_percentage = (
                ((self.regular_price - self.discounted_price) / self.regular_price) * 100
            )
        return self
    
    @model_validator(mode='after')
    def validate_prices(self):
        """Validate that regular price >= discounted price."""
        if (
            self.regular_price is not None and
            self.discounted_price is not None and
            self.regular_price < self.discounted_price
        ):
            # Swap prices if they appear reversed
            self.regular_price, self.discounted_price = (
                self.discounted_price,
                self.regular_price
            )
            if 'prices_swapped' not in self.uncertainty_flags:
                self.uncertainty_flags.append('prices_swapped')
        return self


class PageExtractionResult(BaseModel):
    """
    Result of extracting products from a single page.
    
    Attributes:
        page_number: Page that was processed
        products: List of extracted products
        page_notes: VLM notes about the page
        continuation_detected: Whether page continues to next
        processing_time_ms: Time taken to process
        tokens_used: API tokens consumed
    """
    page_number: int = Field(..., ge=1)
    products: List[ExtractedProduct] = Field(default_factory=list)
    page_notes: Optional[str] = None
    continuation_detected: bool = False
    processing_time_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def product_count(self) -> int:
        """Get number of products extracted."""
        return len(self.products)
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence across all products."""
        if not self.products:
            return 0.0
        return sum(p.confidence_score for p in self.products) / len(self.products)


class ExtractionResult(BaseModel):
    """
    Complete extraction result for a leaflet.
    
    Contains all extracted products across all pages
    plus metadata and quality metrics.
    
    Attributes:
        leaflet_id: ID of processed leaflet
        page_results: Results for each page
        total_products: Total products extracted
        total_pages: Number of pages processed
        overall_confidence: Average confidence
        processing_time_ms: Total processing time
        tokens_used: Total API tokens consumed
        success: Whether extraction succeeded
        error_message: Error message if failed
    """
    leaflet_id: str
    page_results: List[PageExtractionResult] = Field(default_factory=list)
    total_products: int = 0
    total_pages: int = 0
    overall_confidence: float = 0.0
    processing_time_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = True
    error_message: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def all_products(self) -> List[ExtractedProduct]:
        """Get flat list of all products from all pages."""
        products = []
        for page_result in self.page_results:
            products.extend(page_result.products)
        return products
    
    @property
    def estimated_cost(self) -> float:
        """Estimate API cost based on token usage.
        
        Using Claude Sonnet pricing as of 2024:
        - Input: $3 per 1M tokens
        - Output: $15 per 1M tokens
        """
        input_cost = (self.input_tokens / 1_000_000) * 3.0
        output_cost = (self.output_tokens / 1_000_000) * 15.0
        return round(input_cost + output_cost, 4)
    
    def calculate_metrics(self):
        """Calculate aggregate metrics from page results."""
        self.total_products = sum(pr.product_count for pr in self.page_results)
        self.total_pages = len(self.page_results)
        self.input_tokens = sum(pr.input_tokens for pr in self.page_results)
        self.output_tokens = sum(pr.output_tokens for pr in self.page_results)
        self.processing_time_ms = sum(pr.processing_time_ms for pr in self.page_results)
        
        if self.page_results:
            self.overall_confidence = sum(
                pr.average_confidence for pr in self.page_results
            ) / len(self.page_results)
    
    def add_page_result(self, page_result: 'PageExtractionResult'):
        """Add a page extraction result and update metrics."""
        self.page_results.append(page_result)
        self.total_products += page_result.product_count
        self.total_pages = len(self.page_results)
        self.input_tokens += page_result.input_tokens
        self.output_tokens += page_result.output_tokens
        
        # Recalculate overall confidence
        if self.page_results:
            self.overall_confidence = sum(
                pr.average_confidence for pr in self.page_results
            ) / len(self.page_results)
    
    def add_error(self, error_message: str):
        """Add an error message. Marks result as failed if first error."""
        if self.error_message:
            self.error_message += f"; {error_message}"
        else:
            self.error_message = error_message
            self.success = False


class ExtractionContext(BaseModel):
    """
    Context information passed to VLM for better extraction.
    
    Attributes:
        leaflet_id: Leaflet identifier
        retailer: Retailer name if known
        country: Country code (defaults to settings.default_country)
        language: Expected language (defaults to settings.default_language)
        currency: Expected currency (defaults to settings.default_currency)
        page_count: Total pages in leaflet
        previous_page_notes: Notes from previous page
        image_width: Width of the page image in pixels (CRITICAL for bounding boxes)
        image_height: Height of the page image in pixels (CRITICAL for bounding boxes)
    """
    leaflet_id: str
    leaflet_uuid: Optional[uuid.UUID] = None  # Actual UUID PK, used for audit logging FK
    retailer: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    currency: Optional[str] = None
    page_count: int = 1
    previous_page_notes: Optional[str] = None
    has_previous_page: bool = False
    has_next_page: bool = False
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    request_ip: Optional[str] = None  # Client IP address for audit logging

    @classmethod
    def with_defaults(
        cls,
        leaflet_id: str,
        retailer: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        currency: Optional[str] = None,
        **kwargs
    ) -> "ExtractionContext":
        """
        Create ExtractionContext with defaults from settings.
        
        Args:
            leaflet_id: Leaflet identifier
            retailer: Retailer name (optional)
            country: Country code (defaults to settings.default_country)
            language: Language code (defaults to settings.default_language)
            currency: Currency code (defaults to settings.default_currency)
            **kwargs: Additional context fields
            
        Returns:
            ExtractionContext with default values filled in
        """
        from app.config import settings
        
        return cls(
            leaflet_id=leaflet_id,
            retailer=retailer,
            country=country or settings.default_country,
            language=language if language and language != "auto" else None,
            currency=currency or settings.default_currency,
            **kwargs
        )


class ValidationError(BaseModel):
    """
    A single validation error for a product.
    
    Attributes:
        field: Field with error
        error_type: Type of error
        message: Human-readable message
        severity: Error severity level
    """
    field: str
    error_type: str
    message: str
    severity: str = "medium"  # low, medium, high
    
    
class ValidationResult(BaseModel):
    """
    Result of validating an extracted product.
    
    Attributes:
        is_valid: Whether all validations passed
        errors: List of validation errors
        warnings: List of warnings (non-blocking)
        auto_approve: Whether product can be auto-approved
    """
    is_valid: bool = True
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)
    auto_approve: bool = False
    
    def add_error(
        self,
        field: str,
        error_type: str,
        message: str,
        severity: str = "medium"
    ):
        """Add a validation error."""
        self.errors.append(ValidationError(
            field=field,
            error_type=error_type,
            message=message,
            severity=severity
        ))
        self.is_valid = False
        self.auto_approve = False
    
    def add_warning(
        self,
        field: str,
        error_type: str,
        message: str
    ):
        """Add a validation warning."""
        self.warnings.append(ValidationError(
            field=field,
            error_type=error_type,
            message=message,
            severity="low"
        ))