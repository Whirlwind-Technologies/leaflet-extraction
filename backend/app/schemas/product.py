"""
Product Pydantic Schemas.

This module provides schemas for product data and review operations.

Example Usage:
    from app.schemas.product import ProductResponse, ProductReviewCreate
    
    # Get product
    product = ProductResponse(...)
    
    # Review product
    review = ProductReviewCreate(action="approved")
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.models.product import ReviewStatus
from app.schemas.common import (
    BaseSchema,
    BoundingBox,
    FieldConfidence,
    IDSchema,
    ImageData,
    PaginationParams,
    TimestampSchema,
)


class ProductBase(BaseSchema):
    """
    Base product schema with common fields.
    
    Attributes:
        brand: Product brand name
        product_code: SKU or reference code
        product_name: Full product description
        quantity: Numeric quantity
        units: Unit of measurement
        regular_price: Original price
        discounted_price: Promotional price
        discount_percentage: Calculated discount
        currency: Currency code
        promotional_info: Promotional details
    """
    
    brand: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Product brand name"
    )
    product_code: Optional[str] = Field(
        default=None,
        max_length=100,
        description="SKU, item number, reference code"
    )
    product_name: str = Field(
        max_length=1000,
        description="Full product description"
    )
    quantity: Optional[float] = Field(default=None, ge=0, description="Quantity")
    units: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Unit of measurement"
    )
    size: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Product size"
    )
    regular_price: Optional[float] = Field(
        default=None,
        ge=0,
        description="Original price"
    )
    discounted_price: Optional[float] = Field(
        default=None,
        ge=0,
        description="Promotional price"
    )
    discount_percentage: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Discount percentage"
    )
    currency: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Currency code"
    )
    product_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Barcode/EAN"
    )
    promotional_info: Optional[str] = Field(
        default=None,
        description="Promotional details"
    )
    suggested_category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="AI-suggested product category"
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="User-confirmed product category"
    )
    category_confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Category confidence score"
    )
    category_alternatives: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Alternative category suggestions"
    )


class ProductCreate(ProductBase):
    """
    Schema for creating a product manually.
    
    Used for manual product entry or corrections.
    
    Attributes:
        leaflet_id: Parent leaflet ID
        page_number: Page number in leaflet
        bounding_box: Product location coordinates
    """
    
    leaflet_id: UUID = Field(description="Parent leaflet ID")
    page_number: int = Field(ge=1, description="Page number")
    bounding_box: BoundingBox = Field(description="Product location")


class ProductUpdate(BaseSchema):
    """
    Schema for updating product data.

    All fields optional - only provided fields updated.
    """

    brand: Optional[str] = Field(default=None, max_length=200)
    product_code: Optional[str] = Field(default=None, max_length=100)
    product_name: Optional[str] = Field(default=None, max_length=1000)
    quantity: Optional[float] = Field(default=None, ge=0)
    units: Optional[str] = Field(default=None, max_length=20)
    size: Optional[str] = Field(default=None, max_length=50)
    regular_price: Optional[float] = Field(default=None, ge=0)
    discounted_price: Optional[float] = Field(default=None, ge=0)
    discount_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    currency: Optional[str] = Field(default=None, max_length=10)
    product_id: Optional[str] = Field(default=None, max_length=100)
    promotional_info: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None, max_length=100)
    bounding_box: Optional[BoundingBox] = Field(default=None)
    skip_review_history: Optional[bool] = Field(default=False, description="Skip creating review history entry (used when review will be submitted separately)")


class ProductResponse(ProductBase, IDSchema, TimestampSchema):
    """
    Schema for product response data.
    
    Attributes:
        id: Unique identifier
        leaflet_id: Parent leaflet ID
        page_number: Page number
        bounding_box: Product location
        image: Product image data
        confidence: Extraction confidence
        field_confidence: Per-field confidence
        uncertainty_flags: Extraction uncertainties
        review_status: Review status
        review_priority: Review priority
        validation_passed: Validation result
        validation_errors: Validation error list
        
    Example:
        >>> product = ProductResponse(
        ...     id=uuid4(),
        ...     product_name="Coca-Cola Zero 2L",
        ...     page_number=3,
        ...     confidence=0.95
        ... )
    """
    
    leaflet_id: UUID = Field(description="Parent leaflet ID")
    page_number: int = Field(description="Page number")
    bounding_box: BoundingBox = Field(description="Product location")
    
    # Image fields - both new structured format and legacy fields for compatibility
    image: Optional[ImageData] = Field(default=None, description="Product image")
    image_storage_type: Optional[str] = Field(default=None, description="Storage type")
    image_base64: Optional[str] = Field(default=None, description="Base64 image data")
    image_url: Optional[str] = Field(default=None, description="Image URL")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail URL")
    image_width: Optional[int] = Field(default=None, description="Image width")
    image_height: Optional[int] = Field(default=None, description="Image height")
    image_size_bytes: Optional[int] = Field(default=None, description="Image size")
    image_quality_score: Optional[float] = Field(default=None, description="Quality score")
    
    # Extraction quality
    confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Overall confidence"
    )
    field_confidence: Optional[FieldConfidence] = Field(
        default=None,
        description="Per-field confidence"
    )
    uncertainty_flags: List[str] = Field(
        default_factory=list,
        description="Uncertainty flags"
    )
    
    # Review status
    review_status: ReviewStatus = Field(description="Review status")
    review_priority: int = Field(default=0, description="Review priority")
    reviewed_by: Optional[UUID] = Field(default=None, description="Reviewer ID")
    reviewed_at: Optional[datetime] = Field(default=None, description="Review time")
    review_notes: Optional[str] = Field(default=None, description="Review notes")
    
    # Validation
    validation_passed: bool = Field(default=True, description="Validation result")
    validation_errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Validation errors"
    )
    
    # Flags
    is_corrected: bool = Field(default=False, description="Was corrected")
    is_split_product: bool = Field(
        default=False,
        description="Spans multiple pages"
    )


class ProductListResponse(ProductBase, IDSchema):
    """
    Simplified product response for list views.
    
    Contains essential fields for display in lists.
    """
    
    leaflet_id: UUID = Field(description="Parent leaflet ID")
    page_number: int = Field(description="Page number")
    bounding_box: BoundingBox = Field(description="Product location")
    
    # Image fields - both new structured format and legacy fields for compatibility
    image: Optional[ImageData] = Field(default=None, description="Product image")
    image_storage_type: Optional[str] = Field(default=None, description="Storage type")
    image_base64: Optional[str] = Field(default=None, description="Base64 image data")
    image_url: Optional[str] = Field(default=None, description="Image URL")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail URL")
    image_width: Optional[int] = Field(default=None, description="Image width")
    image_height: Optional[int] = Field(default=None, description="Image height")
    image_size_bytes: Optional[int] = Field(default=None, description="Image size")
    image_quality_score: Optional[float] = Field(default=None, description="Quality score")
    
    # Extraction quality
    confidence: Optional[float] = Field(default=None, description="Confidence")
    field_confidence: Optional[FieldConfidence] = Field(default=None, description="Per-field confidence")
    uncertainty_flags: List[str] = Field(default_factory=list, description="Uncertainty flags")
    
    # Review status
    review_status: ReviewStatus = Field(description="Review status")
    review_priority: int = Field(default=0, description="Review priority")
    reviewed_by: Optional[UUID] = Field(default=None, description="Reviewer ID")
    reviewed_at: Optional[datetime] = Field(default=None, description="Review time")
    
    # Validation
    validation_passed: bool = Field(default=True, description="Validation OK")
    validation_errors: List[Dict[str, Any]] = Field(default_factory=list, description="Validation errors")
    
    # Flags
    is_corrected: bool = Field(default=False, description="Was corrected")
    is_split_product: bool = Field(default=False, description="Spans pages")
    
    # Timestamps
    created_at: datetime = Field(description="Created timestamp")
    updated_at: datetime = Field(description="Updated timestamp")


class ProductListParams(PaginationParams):
    """
    Parameters for listing products.
    
    Attributes:
        leaflet_id: Filter by leaflet
        page_number: Filter by page
        review_status: Filter by review status
        brand: Filter by brand
        min_confidence: Minimum confidence filter
        validation_passed: Filter by validation status
        search: Search product name
    """
    
    leaflet_id: Optional[UUID] = Field(default=None, description="Filter by leaflet")
    page_number: Optional[int] = Field(default=None, description="Filter by page")
    review_status: Optional[ReviewStatus] = Field(
        default=None,
        description="Filter by review status"
    )
    brand: Optional[str] = Field(default=None, description="Filter by brand")
    min_confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Minimum confidence"
    )
    validation_passed: Optional[bool] = Field(
        default=None,
        description="Filter by validation"
    )
    search: Optional[str] = Field(default=None, description="Search product name")
    category: Optional[str] = Field(default=None, description="Filter by category")


# Review Schemas

class ProductReviewCreate(BaseSchema):
    """
    Schema for creating a product review.
    
    Attributes:
        action: Review action (approved, rejected, corrected)
        corrections: Field corrections (if any)
        notes: Reviewer notes
        bounding_box: Corrected bounding box (if adjusted)
        
    Example:
        >>> review = ProductReviewCreate(
        ...     action="approved",
        ...     notes="All data verified correct"
        ... )
        
        >>> review = ProductReviewCreate(
        ...     action="corrected",
        ...     corrections={"regular_price": 2.99},
        ...     notes="Fixed price"
        ... )
    """
    
    action: str = Field(
        description="Review action: approved, rejected, corrected"
    )
    corrections: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Field corrections"
    )
    notes: Optional[str] = Field(default=None, description="Reviewer notes")
    bounding_box: Optional[BoundingBox] = Field(
        default=None,
        description="Corrected bounding box"
    )
    time_spent_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Time spent reviewing"
    )
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action is one of allowed values."""
        allowed = {"approved", "rejected", "corrected", "needs_correction"}
        if v.lower() not in allowed:
            raise ValueError(f"Action must be one of: {allowed}")
        return v.lower()


class ProductReviewResponse(IDSchema, TimestampSchema):
    """
    Schema for product review history response.
    
    Attributes:
        product_id: Product that was reviewed
        reviewer_id: User who reviewed
        action: Review action taken
        previous_data: Data before review
        new_data: Data after review
        changed_fields: Fields that were changed
        notes: Reviewer notes
    """
    
    product_id: UUID = Field(description="Product ID")
    reviewer_id: Optional[UUID] = Field(default=None, description="Reviewer ID")
    action: str = Field(description="Review action")
    previous_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Data before review"
    )
    new_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Data after review"
    )
    changed_fields: List[str] = Field(
        default_factory=list,
        description="Changed fields"
    )
    notes: Optional[str] = Field(default=None, description="Reviewer notes")
    time_spent_seconds: Optional[int] = Field(
        default=None,
        description="Time spent"
    )


class ProductBatchFetchRequest(BaseSchema):
    """
    Schema for batch product fetch.

    Attributes:
        product_ids: List of product UUIDs to fetch (max 20)
    """

    product_ids: List[UUID] = Field(
        min_length=1,
        max_length=20,
        description="Product IDs to fetch"
    )


class ProductBatchReviewCreate(BaseSchema):
    """
    Schema for batch review operations.
    
    Attributes:
        product_ids: List of product IDs to review
        action: Review action for all products
        notes: Notes for all reviews
        
    Example:
        >>> batch = ProductBatchReviewCreate(
        ...     product_ids=[uuid1, uuid2, uuid3],
        ...     action="approved",
        ...     notes="Batch approved after spot check"
        ... )
    """
    
    product_ids: List[UUID] = Field(
        min_length=1,
        max_length=100,
        description="Product IDs to review"
    )
    action: str = Field(description="Review action for all")
    notes: Optional[str] = Field(default=None, description="Notes for all")
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action is one of allowed values."""
        allowed = {"approved", "rejected"}
        if v.lower() not in allowed:
            raise ValueError(f"Batch action must be one of: {allowed}")
        return v.lower()


class ProductBatchReviewResponse(BaseSchema):
    """
    Response for batch review operation.
    
    Attributes:
        processed: Number of products processed
        succeeded: Number of successful reviews
        failed: Number of failed reviews
        errors: List of errors for failed reviews
    """
    
    processed: int = Field(description="Products processed")
    succeeded: int = Field(description="Successful reviews")
    failed: int = Field(description="Failed reviews")
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Errors for failed reviews"
    )


# Export Schemas

class ProductExportParams(BaseSchema):
    """
    Parameters for product export.
    
    Attributes:
        format: Export format (json, csv, excel)
        image_storage: Image storage preference
        image_quality: Image quality setting
        include_thumbnails: Include thumbnail images
        include_page_images: Include full page images
        fields: Specific fields to include
    """
    
    format: str = Field(
        default="json",
        pattern="^(json|csv|excel)$",
        description="Export format"
    )
    image_storage: str = Field(
        default="url",
        pattern="^(base64|url|both|none)$",
        description="Image storage preference"
    )
    image_quality: str = Field(
        default="medium",
        pattern="^(low|medium|high)$",
        description="Image quality"
    )
    include_thumbnails: bool = Field(
        default=False,
        description="Include thumbnails"
    )
    include_page_images: bool = Field(
        default=False,
        description="Include page images"
    )
    include_product_codes: bool = Field(
        default=True,
        description="Include product codes"
    )
    calculate_discounts: bool = Field(
        default=True,
        description="Calculate discounts"
    )
    fields: Optional[List[str]] = Field(
        default=None,
        description="Specific fields to include"
    )


class VLMExtractionResult(BaseSchema):
    """
    Schema for VLM extraction result.
    
    Represents raw extraction data from VLM.
    
    Attributes:
        page_number: Page that was processed
        products: Extracted products
        page_notes: Notes about page layout
        continuation_detected: Whether page continues
    """
    
    page_number: int = Field(description="Page number")
    products: List[Dict[str, Any]] = Field(description="Extracted products")
    page_notes: Optional[str] = Field(default=None, description="Page notes")
    continuation_detected: bool = Field(
        default=False,
        description="Continuation detected"
    )