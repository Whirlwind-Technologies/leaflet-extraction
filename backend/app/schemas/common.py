"""
Common Pydantic Schemas.

This module provides base schemas and common schema patterns used
across the application.

Example Usage:
    from app.schemas.common import PaginatedResponse, SuccessResponse
    
    # Create paginated response
    response = PaginatedResponse(
        items=[...],
        total=100,
        page=1,
        page_size=20
    )
"""

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Generic type for paginated responses
T = TypeVar("T")


class BaseSchema(BaseModel):
    """
    Base schema with common configuration.
    
    All schemas should inherit from this class for consistent behavior.
    """
    
    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM mode
        populate_by_name=True,  # Allow field aliases
        str_strip_whitespace=True,  # Strip whitespace from strings
        validate_assignment=True,  # Validate on attribute assignment
    )


class TimestampSchema(BaseSchema):
    """
    Schema mixin for timestamp fields.
    
    Attributes:
        created_at: When record was created
        updated_at: When record was last updated
    """
    
    created_at: datetime = Field(description="When record was created")
    updated_at: datetime = Field(description="When record was last updated")


class IDSchema(BaseSchema):
    """
    Schema mixin for ID field.
    
    Attributes:
        id: Unique identifier (UUID)
    """
    
    id: UUID = Field(description="Unique identifier")


class SuccessResponse(BaseSchema):
    """
    Generic success response schema.
    
    Attributes:
        success: Always True
        message: Success message
        data: Optional response data
        
    Example:
        >>> SuccessResponse(message="Operation completed", data={"id": "123"})
    """
    
    success: bool = Field(default=True, description="Success indicator")
    message: str = Field(description="Success message")
    data: Optional[dict] = Field(default=None, description="Response data")


class ErrorDetail(BaseSchema):
    """
    Error detail schema.
    
    Attributes:
        field: Field that caused the error (optional)
        message: Error message
        code: Error code (optional)
    """
    
    field: Optional[str] = Field(default=None, description="Field name")
    message: str = Field(description="Error message")
    code: Optional[str] = Field(default=None, description="Error code")


class ErrorResponse(BaseSchema):
    """
    Generic error response schema.
    
    Attributes:
        error: Error information
        
    Example:
        >>> ErrorResponse(error={"code": "NOT_FOUND", "message": "Resource not found"})
    """
    
    error: dict = Field(description="Error information")


class PaginationParams(BaseSchema):
    """
    Pagination parameters schema.
    
    Attributes:
        page: Page number (1-indexed)
        page_size: Number of items per page
        sort_by: Field to sort by
        sort_order: Sort direction (asc/desc)
        
    Example:
        >>> params = PaginationParams(page=1, page_size=20, sort_by="created_at")
    """
    
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Items per page"
    )
    sort_by: Optional[str] = Field(default=None, description="Sort field")
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort order"
    )
    
    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseSchema, Generic[T]):
    """
    Generic paginated response schema.
    
    Attributes:
        items: List of items
        total: Total number of items
        page: Current page number
        page_size: Items per page
        pages: Total number of pages
        has_next: Whether there's a next page
        has_prev: Whether there's a previous page
        
    Example:
        >>> response = PaginatedResponse[UserSchema](
        ...     items=[user1, user2],
        ...     total=100,
        ...     page=1,
        ...     page_size=20
        ... )
    """
    
    items: List[Any] = Field(description="List of items")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there's a next page")
    has_prev: bool = Field(description="Whether there's a previous page")
    
    @classmethod
    def create(
        cls,
        items: List[Any],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse":
        """
        Create a paginated response.
        
        Args:
            items: List of items for current page
            total: Total number of items
            page: Current page number
            page_size: Items per page
            
        Returns:
            PaginatedResponse instance
        """
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )


class BoundingBox(BaseSchema):
    """
    Bounding box coordinates schema.
    
    Attributes:
        x: X coordinate (top-left)
        y: Y coordinate (top-left)
        width: Box width in pixels
        height: Box height in pixels
        
    Example:
        >>> bbox = BoundingBox(x=50, y=120, width=280, height=350)
    """
    
    x: int = Field(ge=0, description="X coordinate (top-left)")
    y: int = Field(ge=0, description="Y coordinate (top-left)")
    width: int = Field(gt=0, description="Width in pixels")
    height: int = Field(gt=0, description="Height in pixels")


class ImageData(BaseSchema):
    """
    Image data schema for product images.
    
    Attributes:
        storage_type: How image is stored (base64 or file)
        data: Base64 encoded image data (if base64)
        url: URL to image (if file storage)
        format: Image format (PNG, JPEG)
        dimensions: Image dimensions
        size_bytes: File size in bytes
        quality_score: Image quality score
        
    Example:
        >>> image = ImageData(
        ...     storage_type="base64",
        ...     data="iVBORw0KGgo...",
        ...     format="PNG",
        ...     dimensions={"width": 280, "height": 350}
        ... )
    """
    
    storage_type: str = Field(description="Storage type: base64 or file")
    data: Optional[str] = Field(default=None, description="Base64 data")
    url: Optional[str] = Field(default=None, description="Image URL")
    format: str = Field(description="Image format")
    dimensions: dict = Field(description="Width and height")
    size_bytes: Optional[int] = Field(default=None, description="File size")
    quality_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Quality score"
    )


class FieldConfidence(BaseSchema):
    """
    Per-field confidence scores schema.
    
    Attributes:
        brand: Confidence for brand extraction
        product_code: Confidence for product code
        product_name: Confidence for product name
        quantity: Confidence for quantity
        regular_price: Confidence for regular price
        discounted_price: Confidence for discounted price
        discount_percentage: Confidence for discount percentage
        
    Example:
        >>> confidence = FieldConfidence(
        ...     brand=0.98,
        ...     product_name=0.96,
        ...     discounted_price=0.97
        ... )
    """
    
    brand: Optional[float] = Field(default=None, ge=0, le=1)
    product_code: Optional[float] = Field(default=None, ge=0, le=1)
    product_name: Optional[float] = Field(default=None, ge=0, le=1)
    quantity: Optional[float] = Field(default=None, ge=0, le=1)
    regular_price: Optional[float] = Field(default=None, ge=0, le=1)
    discounted_price: Optional[float] = Field(default=None, ge=0, le=1)
    discount_percentage: Optional[float] = Field(default=None, ge=0, le=1)


class HealthResponse(BaseSchema):
    """
    Health check response schema.
    
    Attributes:
        status: Overall health status
        version: Application version
        environment: Deployment environment
        database: Database connection status
        redis: Redis connection status
        timestamp: Check timestamp
    """
    
    status: str = Field(description="Overall health status")
    version: str = Field(description="Application version")
    environment: str = Field(description="Deployment environment")
    database: str = Field(description="Database status")
    redis: str = Field(description="Redis status")
    timestamp: float = Field(description="Unix timestamp")