"""
Product Model Module.

This module defines the Product model for storing extracted product data
from leaflets, including pricing, images, and validation status.

Example Usage:
    from app.models.product import Product, ReviewStatus
    
    # Create a new product
    product = Product(
        leaflet_id=leaflet.id,
        page_number=3,
        brand="Coca-Cola",
        product_name="Coca-Cola Zero Sugar 2L",
        discounted_price=1.99
    )
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin


class ReviewStatus(str, Enum):
    """
    Enumeration of product review statuses.
    
    Attributes:
        PENDING: Awaiting review
        AUTO_APPROVED: Automatically approved (high confidence)
        APPROVED: Manually approved by reviewer
        REJECTED: Rejected by reviewer
        NEEDS_CORRECTION: Requires correction
    """
    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CORRECTION = "needs_correction"


class Product(BaseModel, TimestampMixin):
    """
    Product model for storing extracted product data.
    
    Stores all product information extracted from leaflets including
    pricing, images, bounding boxes, and validation status.
    
    Attributes:
        id: Unique identifier (UUID)
        leaflet_id: Parent leaflet ID
        page_number: Page where product was found
        brand: Product brand name
        product_code: SKU, item number, reference code
        product_name: Full product description
        quantity: Numeric quantity
        units: Unit of measurement
        regular_price: Original price (if shown)
        discounted_price: Current/promotional price
        discount_percentage: Calculated or displayed discount
        currency: Currency code
        product_id: Barcode/EAN if visible
        promotional_info: Any badges, deals, or conditions
        confidence: Overall extraction confidence
        review_status: Current review status
        
    Relationships:
        leaflet: Parent leaflet
        reviews: Review history for this product
        
    Example:
        >>> product = Product(
        ...     leaflet_id=leaflet.id,
        ...     page_number=3,
        ...     brand="Coca-Cola",
        ...     product_code="CC-ZS-2L",
        ...     product_name="Coca-Cola Zero Sugar",
        ...     quantity=2.0,
        ...     units="L",
        ...     regular_price=2.99,
        ...     discounted_price=1.99,
        ...     discount_percentage=33.4,
        ...     currency="EUR"
        ... )
    """
    
    __tablename__ = "products"
    
    # Parent leaflet
    leaflet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leaflets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent leaflet ID"
    )

    # Organization ownership (denormalized for query performance)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this product (denormalized for performance)"
    )

    # Location in leaflet
    page_number = Column(
        Integer,
        nullable=False,
        index=True,
        comment="Page number where product was found"
    )
    
    # Product identification
    brand = Column(
        String(200),
        nullable=True,
        index=True,
        comment="Product brand name"
    )
    product_code = Column(
        String(100),
        nullable=True,
        index=True,
        comment="SKU, item number, reference code"
    )
    product_name = Column(
        Text,
        nullable=False,
        comment="Full product description"
    )
    product_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Barcode/EAN if visible"
    )
    
    # Quantity and units
    quantity = Column(
        Float,
        nullable=True,
        comment="Numeric quantity"
    )
    units = Column(
        String(20),
        nullable=True,
        comment="Unit of measurement (g, kg, ml, L, pcs, pack)"
    )
    size = Column(
        String(50),
        nullable=True,
        comment="Product size description"
    )
    
    # Pricing
    regular_price = Column(
        Float,
        nullable=True,
        comment="Original price if shown"
    )
    discounted_price = Column(
        Float,
        nullable=True,
        comment="Current/promotional price"
    )
    discount_percentage = Column(
        Float,
        nullable=True,
        comment="Calculated or displayed discount percentage"
    )
    currency = Column(
        String(10),
        nullable=True,
        comment="Currency code (ISO 4217)"
    )
    
    # Promotional information
    promotional_info = Column(
        Text,
        nullable=True,
        comment="Any badges, deals, or conditions"
    )

    # Category fields
    suggested_category = Column(
        String(100),
        nullable=True,
        index=True,
        comment="AI-suggested product category (immutable after extraction)"
    )
    category = Column(
        String(100),
        nullable=True,
        index=True,
        comment="User-confirmed/corrected category"
    )
    category_confidence = Column(
        Float,
        nullable=True,
        comment="Category confidence score (0.0 to 1.0)"
    )
    category_alternatives = Column(
        JSONB,
        nullable=True,
        comment="Alternative category suggestions with confidence scores"
    )

    # Bounding box coordinates
    bbox_x = Column(
        Integer,
        nullable=False,
        comment="Bounding box X coordinate (top-left)"
    )
    bbox_y = Column(
        Integer,
        nullable=False,
        comment="Bounding box Y coordinate (top-left)"
    )
    bbox_width = Column(
        Integer,
        nullable=False,
        comment="Bounding box width in pixels"
    )
    bbox_height = Column(
        Integer,
        nullable=False,
        comment="Bounding box height in pixels"
    )

    # Image storage
    image_storage_type = Column(
        String(10),
        nullable=True,
        comment="Storage type: 'base64' or 'file'"
    )
    image_base64 = Column(
        Text,
        nullable=True,
        comment="Base64 encoded image data"
    )
    image_url = Column(
        String(500),
        nullable=True,
        comment="URL to product image"
    )
    image_path = Column(
        String(500),
        nullable=True,
        comment="File path to product image"
    )
    image_format = Column(
        String(10),
        nullable=True,
        comment="Image format (PNG, JPEG)"
    )
    image_width = Column(
        Integer,
        nullable=True,
        comment="Extracted image width"
    )
    image_height = Column(
        Integer,
        nullable=True,
        comment="Extracted image height"
    )
    image_size_bytes = Column(
        Integer,
        nullable=True,
        comment="Image file size in bytes"
    )
    image_quality_score = Column(
        Float,
        nullable=True,
        comment="Image quality score (0.0 to 1.0)"
    )
    
    # Confidence scores
    confidence = Column(
        Float,
        nullable=True,
        comment="Overall extraction confidence (0.0 to 1.0)"
    )
    field_confidence = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Per-field confidence scores"
    )
    uncertainty_flags = Column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of uncertainty flags from VLM"
    )
    
    # Review status
    review_status = Column(
        SQLEnum(
            ReviewStatus,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
            create_constraint=False,
        ),
        default=ReviewStatus.PENDING,
        nullable=False,
        index=True,
        comment="Current review status"
    )
    review_priority = Column(
        Integer,
        default=0,
        nullable=False,
        index=True,
        comment="Review priority (higher = more urgent)"
    )
    reviewed_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID of reviewer who approved/rejected"
    )
    reviewed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When product was reviewed"
    )
    review_notes = Column(
        Text,
        nullable=True,
        comment="Notes from reviewer"
    )
    
    # Validation
    validation_passed = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether validation rules passed"
    )
    validation_errors = Column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of validation errors"
    )
    
    # Correction tracking
    is_corrected = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether product was manually corrected"
    )
    original_data = Column(
        JSONB,
        nullable=True,
        comment="Original VLM extraction data before corrections"
    )
    correction_type = Column(
        String(50),
        nullable=True,
        comment="Type of correction applied"
    )
    
    # Cross-page handling
    is_split_product = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether product spans multiple pages"
    )
    merged_from = Column(
        JSONB,
        nullable=True,
        comment="IDs of products merged into this one"
    )
    
    # Relationships
    leaflet = relationship("Leaflet", back_populates="products")
    reviews = relationship(
        "ProductReview",
        back_populates="product",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ProductReview.created_at.desc()"
    )
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name={self.product_name[:30]}...)>"
    
    @property
    def bounding_box(self) -> dict:
        """Get bounding box as dictionary."""
        return {
            "x": self.bbox_x,
            "y": self.bbox_y,
            "width": self.bbox_width,
            "height": self.bbox_height,
        }
    
    @property
    def image(self) -> Optional[dict]:
        """Get image data as dictionary for serialization."""
        if not self.image_storage_type:
            return None
        return {
            "storage_type": self.image_storage_type,
            "data": self.image_base64,
            "url": self.image_url,
            "format": self.image_format or "PNG",
            "dimensions": {
                "width": self.image_width or 0,
                "height": self.image_height or 0,
            },
            "size_bytes": self.image_size_bytes,
            "quality_score": self.image_quality_score,
        }
    
    @property
    def has_discount(self) -> bool:
        """Check if product has a discount."""
        return (
            self.regular_price is not None
            and self.discounted_price is not None
            and self.regular_price > self.discounted_price
        )
    
    @property
    def calculated_discount(self) -> Optional[float]:
        """Calculate discount percentage from prices."""
        if self.has_discount and self.regular_price > 0:
            return (
                ((self.regular_price - self.discounted_price) / self.regular_price) * 100
            )
        return None
    
    @property
    def is_auto_approved(self) -> bool:
        """Check if product was auto-approved."""
        return self.review_status == ReviewStatus.AUTO_APPROVED
    
    @property
    def needs_review(self) -> bool:
        """Check if product needs human review."""
        return self.review_status in [
            ReviewStatus.PENDING,
            ReviewStatus.NEEDS_CORRECTION,
        ]


class ProductReview(BaseModel, TimestampMixin):
    """
    Product review history model.
    
    Stores the history of reviews and corrections for a product.
    
    Attributes:
        id: Unique identifier
        product_id: Product being reviewed
        reviewer_id: User who performed the review
        action: Review action taken
        previous_data: Product data before review
        new_data: Product data after review
        notes: Reviewer notes
        
    Example:
        >>> review = ProductReview(
        ...     product_id=product.id,
        ...     reviewer_id=user.id,
        ...     action="approved",
        ...     notes="All data verified correct"
        ... )
    """
    
    __tablename__ = "product_reviews"
    
    # Product being reviewed
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Product being reviewed"
    )
    
    # Reviewer
    reviewer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who performed the review"
    )
    
    # Review details
    action = Column(
        String(50),
        nullable=False,
        comment="Review action: approved, rejected, corrected"
    )
    
    # Data tracking
    previous_data = Column(
        JSONB,
        nullable=True,
        comment="Product data before review"
    )
    new_data = Column(
        JSONB,
        nullable=True,
        comment="Product data after review"
    )
    changed_fields = Column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of fields that were changed"
    )
    
    # Notes and metadata
    notes = Column(
        Text,
        nullable=True,
        comment="Reviewer notes"
    )
    time_spent_seconds = Column(
        Integer,
        nullable=True,
        comment="Time spent on review in seconds"
    )
    
    # Relationships
    product = relationship("Product", back_populates="reviews")
    
    def __repr__(self) -> str:
        return f"<ProductReview(id={self.id}, action={self.action})>"