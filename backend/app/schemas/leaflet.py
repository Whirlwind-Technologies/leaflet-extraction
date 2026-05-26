"""
Leaflet Pydantic Schemas.

This module provides schemas for leaflet upload and management.

Example Usage:
    from app.schemas.leaflet import LeafletCreate, LeafletResponse
    
    # Upload leaflet
    leaflet = LeafletCreate(
        filename="promo.pdf",
        retailer="SuperMart",
        country="DE"
    )
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.models.leaflet import LeafletStatus
from app.schemas.common import BaseSchema, IDSchema, PaginationParams, TimestampSchema


class LeafletBase(BaseSchema):
    """
    Base leaflet schema with common fields.
    
    Attributes:
        retailer: Retailer name
        country: Country code (ISO 3166-1 alpha-2)
        language: Language code (ISO 639-1)
        currency: Currency code (ISO 4217)
    """
    
    retailer: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Retailer name"
    )
    country: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Country code (ISO 3166-1 alpha-2)"
    )
    language: Optional[str] = Field(
        default=None,
        max_length=5,
        description="Language code (ISO 639-1)"
    )
    currency: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Currency code (ISO 4217)"
    )


class LeafletCreate(LeafletBase):
    """
    Schema for creating/uploading a leaflet.
    
    Used when uploading a new PDF leaflet.
    
    Attributes:
        filename: Original filename
        retailer: Retailer name (optional, can be detected)
        country: Country code (optional)
        language: Language code (optional)
        currency: Currency code (optional)
        valid_from: Validity start date
        valid_until: Validity end date
        
    Example:
        >>> leaflet = LeafletCreate(
        ...     filename="weekly_deals.pdf",
        ...     retailer="SuperMart",
        ...     country="DE",
        ...     currency="EUR"
        ... )
    """
    
    filename: str = Field(max_length=255, description="Original filename")
    valid_from: Optional[datetime] = Field(
        default=None,
        description="Validity start date"
    )
    valid_until: Optional[datetime] = Field(
        default=None,
        description="Validity end date"
    )
    
    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename has .pdf extension."""
        if not v.lower().endswith(".pdf"):
            raise ValueError("File must be a PDF")
        return v


class LeafletUpdate(LeafletBase):
    """
    Schema for updating leaflet metadata.
    
    All fields are optional.
    
    Attributes:
        retailer: Updated retailer name
        country: Updated country code
        language: Updated language code
        currency: Updated currency code
        valid_from: Updated validity start
        valid_until: Updated validity end
    """
    
    valid_from: Optional[datetime] = Field(default=None)
    valid_until: Optional[datetime] = Field(default=None)


class LeafletResponse(LeafletBase, IDSchema, TimestampSchema):
    """
    Schema for leaflet response data.
    
    Attributes:
        id: Unique identifier
        leaflet_id: Human-readable leaflet ID
        filename: Original filename
        file_size: File size in bytes
        page_count: Number of pages
        status: Processing status
        progress: Processing progress (0.0 to 1.0)
        overall_confidence: Extraction confidence score
        products_count: Number of extracted products
        auto_approved_count: Auto-approved products
        review_required_count: Products needing review
        
    Example:
        >>> response = LeafletResponse(
        ...     id=uuid4(),
        ...     leaflet_id="LEAF_2025_001234",
        ...     filename="promo.pdf",
        ...     page_count=12,
        ...     status=LeafletStatus.COMPLETED
        ... )
    """
    
    leaflet_id: str = Field(description="Human-readable ID")
    filename: str = Field(description="Original filename")
    file_size: Optional[int] = Field(default=None, description="File size in bytes")
    page_count: Optional[int] = Field(default=None, description="Number of pages")
    status: LeafletStatus = Field(description="Processing status")
    status_message: Optional[str] = Field(default=None, description="Status message")
    progress: float = Field(default=0.0, description="Processing progress")
    current_step: Optional[str] = Field(default=None, description="Current step")
    overall_confidence: Optional[float] = Field(
        default=None,
        description="Extraction confidence"
    )
    products_count: Optional[int] = Field(
        default=None,
        description="Total products extracted"
    )
    auto_approved_count: int = Field(default=0, description="Auto-approved products")
    review_required_count: int = Field(
        default=0,
        description="Products needing review"
    )
    valid_from: Optional[datetime] = Field(default=None)
    valid_until: Optional[datetime] = Field(default=None)
    processing_started_at: Optional[datetime] = Field(default=None)
    processing_completed_at: Optional[datetime] = Field(default=None)


class LeafletDetail(LeafletResponse):
    """
    Detailed leaflet response with additional information.
    
    Includes processing metadata and quality metrics.
    
    Attributes:
        processing_metadata: Additional processing data
        api_tokens_used: Total API tokens consumed
        processing_cost: Estimated processing cost
        pages: List of page information
    """
    
    processing_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Processing metadata"
    )
    api_tokens_used: int = Field(default=0, description="API tokens used")
    processing_cost: float = Field(default=0.0, description="Processing cost")
    pages: List["LeafletPageResponse"] = Field(
        default_factory=list,
        description="Page information"
    )


class LeafletPageResponse(IDSchema, TimestampSchema):
    """
    Schema for leaflet page response.
    
    Attributes:
        page_number: Page number (1-indexed)
        image_url: URL to page image
        thumbnail_url: URL to thumbnail
        width: Image width in pixels
        height: Image height in pixels
        products_count: Products on this page
        is_processed: Whether page has been processed
    """
    
    page_number: int = Field(description="Page number")
    image_url: Optional[str] = Field(default=None, description="Page image URL")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail URL")
    width: Optional[int] = Field(default=None, description="Image width")
    height: Optional[int] = Field(default=None, description="Image height")
    products_count: int = Field(default=0, description="Products on page")
    is_processed: bool = Field(default=False, description="Processing complete")
    extraction_confidence: Optional[float] = Field(
        default=None,
        description="Page extraction confidence"
    )


class LeafletListParams(PaginationParams):
    """
    Parameters for listing leaflets.
    
    Extends pagination with filtering options.
    
    Attributes:
        status: Filter by status
        retailer: Filter by retailer
        country: Filter by country
        from_date: Filter by created after date
        to_date: Filter by created before date
    """
    
    status: Optional[LeafletStatus] = Field(default=None, description="Filter by status")
    retailer: Optional[str] = Field(default=None, description="Filter by retailer")
    country: Optional[str] = Field(default=None, description="Filter by country")
    from_date: Optional[datetime] = Field(default=None, description="Created after")
    to_date: Optional[datetime] = Field(default=None, description="Created before")
    search: Optional[str] = Field(default=None, description="Search filename")


class LeafletUploadResponse(BaseSchema):
    """
    Response after uploading a leaflet.
    
    Attributes:
        leaflet_id: Assigned leaflet ID
        message: Status message
        status: Initial status
    """
    
    leaflet_id: str = Field(description="Assigned leaflet ID")
    message: str = Field(description="Status message")
    status: LeafletStatus = Field(description="Initial status")


class LeafletProcessingStatus(BaseSchema):
    """
    Schema for processing status updates.
    
    Used for WebSocket status updates.
    
    Attributes:
        leaflet_id: Leaflet being processed
        status: Current status
        progress: Progress percentage
        current_step: Current processing step
        message: Status message
        pages_processed: Pages processed so far
        products_found: Products found so far
    """
    
    leaflet_id: str = Field(description="Leaflet ID")
    status: LeafletStatus = Field(description="Current status")
    progress: float = Field(ge=0, le=1, description="Progress (0.0 to 1.0)")
    current_step: Optional[str] = Field(default=None, description="Current step")
    message: Optional[str] = Field(default=None, description="Status message")
    pages_processed: int = Field(default=0, description="Pages processed")
    products_found: int = Field(default=0, description="Products found")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Update timestamp"
    )


class LeafletQualityMetrics(BaseSchema):
    """
    Quality metrics for a processed leaflet.
    
    Attributes:
        total_products: Total products extracted
        products_with_codes: Products with product codes
        product_code_rate: Product code extraction rate
        products_with_discounts: Products with discounts
        discount_calculation_accuracy: Discount calculation accuracy
        avg_discount_percentage: Average discount
        auto_approval_rate: Auto-approval rate
        validation_pass_rate: Validation pass rate
    """
    
    total_products: int = Field(description="Total products")
    products_with_codes: int = Field(description="Products with codes")
    product_code_rate: float = Field(description="Code extraction rate")
    products_with_discounts: int = Field(description="Products with discounts")
    discount_calculation_accuracy: float = Field(description="Discount accuracy")
    avg_discount_percentage: Optional[float] = Field(
        default=None,
        description="Average discount"
    )
    discount_range: Optional[dict] = Field(default=None, description="Discount range")
    auto_approval_rate: float = Field(description="Auto-approval rate")
    validation_pass_rate: float = Field(description="Validation pass rate")
    field_completeness: Dict[str, float] = Field(
        default_factory=dict,
        description="Per-field completeness"
    )


# Update forward references
LeafletDetail.model_rebuild()