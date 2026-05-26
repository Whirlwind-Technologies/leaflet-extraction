"""
Leaflet Model Module.

This module defines the Leaflet model for storing uploaded PDF leaflets
and their processing metadata.

Example Usage:
    from app.models.leaflet import Leaflet, LeafletStatus
    
    # Create a new leaflet
    leaflet = Leaflet(
        leaflet_id="LEAF_2025_001234",
        user_id=user.id,
        filename="promo_leaflet.pdf",
        page_count=12
    )
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin


class LeafletStatus(str, Enum):
    """
    Enumeration of leaflet processing statuses.

    Attributes:
        PENDING: Awaiting processing
        UPLOADING: File is being uploaded
        PROCESSING: PDF conversion in progress
        EXTRACTING: VLM extraction in progress
        VALIDATING: Validation in progress
        REVIEWING: Awaiting human review
        COMPLETED: Processing complete
        FAILED: Processing failed
        CANCELLED: Processing cancelled by user
    """
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LeafletSourceType(str, Enum):
    """
    Enumeration of leaflet source types.

    Attributes:
        PDF: Source is a PDF file
        IMAGES: Source is individual images (from ZIP or direct upload)
    """
    PDF = "pdf"
    IMAGES = "images"


class Leaflet(BaseModel, TimestampMixin):
    """
    Leaflet model for storing uploaded PDF leaflets.
    
    Stores metadata about uploaded PDF files, their processing status,
    and references to extracted products.
    
    Attributes:
        id: Unique identifier (UUID)
        leaflet_id: Human-readable leaflet ID (e.g., LEAF_2025_001234)
        user_id: ID of user who uploaded the leaflet
        filename: Original filename
        file_size: File size in bytes
        file_hash: SHA256 hash of the file
        page_count: Number of pages in PDF
        status: Current processing status
        retailer: Detected or specified retailer name
        country: Country code (ISO 3166-1 alpha-2)
        language: Language code (ISO 639-1)
        currency: Currency code (ISO 4217)
        
    Relationships:
        user: User who uploaded the leaflet
        products: Products extracted from this leaflet
        pages: Page images for this leaflet
        
    Example:
        >>> leaflet = Leaflet(
        ...     leaflet_id="LEAF_2025_001234",
        ...     user_id=user.id,
        ...     filename="weekly_deals.pdf",
        ...     page_count=12,
        ...     retailer="SuperMart"
        ... )
    """
    
    __tablename__ = "leaflets"
    
    # Identifiers
    leaflet_id = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Human-readable leaflet ID"
    )
    
    # Owner
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID of user who uploaded the leaflet"
    )

    # Organization ownership (multi-tenant)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this leaflet (for multi-tenant data isolation)"
    )

    # Optional retailer reference
    retailer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("retailers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Reference to retailer record (optional)"
    )

    # File metadata
    filename = Column(
        String(255),
        nullable=False,
        comment="Original filename"
    )
    file_size = Column(
        Integer,
        nullable=True,
        comment="File size in bytes"
    )
    file_hash = Column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA256 hash of the file"
    )
    mime_type = Column(
        String(100),
        default="application/pdf",
        nullable=False,
        comment="MIME type of the file"
    )
    source_type = Column(
        SQLEnum(
            LeafletSourceType,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
            create_constraint=False,
        ),
        default=LeafletSourceType.PDF,
        nullable=False,
        comment="Source type: pdf or images (from ZIP or direct upload)"
    )

    # PDF metadata
    page_count = Column(
        Integer,
        nullable=True,
        comment="Number of pages in PDF"
    )
    pdf_type = Column(
        String(20),
        nullable=True,
        comment="PDF type: text-based or image-based"
    )
    
    # Processing status - use native_enum=False to store as VARCHAR
    status = Column(
        SQLEnum(
            LeafletStatus,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
            create_constraint=False,
        ),
        default=LeafletStatus.PENDING,
        nullable=False,
        index=True,
        comment="Current processing status"
    )
    status_message = Column(
        Text,
        nullable=True,
        comment="Status message or error details"
    )
    
    # Processing progress
    progress = Column(
        Float,
        default=0.0,
        nullable=False,
        comment="Processing progress (0.0 to 1.0)"
    )
    current_step = Column(
        String(50),
        nullable=True,
        comment="Current processing step"
    )
    
    # Leaflet metadata
    retailer = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Retailer name"
    )
    country = Column(
        String(2),
        nullable=True,
        index=True,
        comment="Country code (ISO 3166-1 alpha-2)"
    )
    language = Column(
        String(5),
        nullable=True,
        comment="Language code (ISO 639-1)"
    )
    currency = Column(
        String(3),
        nullable=True,
        comment="Currency code (ISO 4217)"
    )
    
    # Validity dates
    valid_from = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Leaflet validity start date"
    )
    valid_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Leaflet validity end date"
    )
    
    # Storage paths
    source_path = Column(
        String(500),
        nullable=True,
        comment="Path to original PDF file"
    )
    storage_bucket = Column(
        String(100),
        nullable=True,
        comment="Storage bucket name"
    )
    
    # Quality metrics
    overall_confidence = Column(
        Float,
        nullable=True,
        comment="Overall extraction confidence (0.0 to 1.0)"
    )
    auto_approved_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of auto-approved products"
    )
    review_required_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of products requiring review"
    )
    
    # Processing timestamps
    processing_started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing started"
    )
    processing_completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing completed"
    )
    
    # Processing metadata
    processing_metadata = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Additional processing metadata"
    )
    
    # Cost tracking
    api_tokens_used = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Total API tokens consumed"
    )
    processing_cost = Column(
        Numeric(10, 4),
        default=Decimal("0"),
        nullable=False,
        comment="Estimated processing cost"
    )

    # Platform provider tracking
    used_platform_provider = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether extraction used the platform shared API key (not org's own provider)"
    )
    
    # Relationships
    user = relationship("User", back_populates="leaflets")
    organization = relationship("Organization", back_populates="leaflets")
    retailer_ref = relationship("Retailer", back_populates="leaflets")
    products = relationship(
        "Product",
        back_populates="leaflet",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    pages = relationship(
        "LeafletPage",
        back_populates="leaflet",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="LeafletPage.page_number"
    )
    
    def __repr__(self) -> str:
        return f"<Leaflet(id={self.id}, leaflet_id={self.leaflet_id}, status={self.status})>"
    
    @property
    def is_processing(self) -> bool:
        """Check if leaflet is currently being processed."""
        return self.status in [
            LeafletStatus.UPLOADING,
            LeafletStatus.PROCESSING,
            LeafletStatus.EXTRACTING,
            LeafletStatus.VALIDATING,
        ]
    
    @property
    def is_complete(self) -> bool:
        """Check if processing is complete."""
        return self.status == LeafletStatus.COMPLETED
    
    @property
    def needs_review(self) -> bool:
        """Check if leaflet has products needing review."""
        return self.review_required_count > 0
    
    @property
    def processing_duration(self) -> Optional[float]:
        """Get processing duration in seconds."""
        if self.processing_started_at and self.processing_completed_at:
            delta = self.processing_completed_at - self.processing_started_at
            return delta.total_seconds()
        return None


class LeafletPage(BaseModel, TimestampMixin):
    """
    Leaflet page model for storing rendered page images.
    
    Stores metadata and paths for each page of a leaflet.
    
    Attributes:
        id: Unique identifier
        leaflet_id: Parent leaflet ID
        page_number: Page number (1-indexed)
        image_path: Path to full-resolution image
        thumbnail_path: Path to thumbnail image
        width: Image width in pixels
        height: Image height in pixels
        
    Example:
        >>> page = LeafletPage(
        ...     leaflet_id=leaflet.id,
        ...     page_number=1,
        ...     image_path="/storage/pages/LEAF_001_page_001.png"
        ... )
    """
    
    __tablename__ = "leaflet_pages"
    
    # Parent leaflet
    leaflet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leaflets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent leaflet ID"
    )
    
    # Page info
    page_number = Column(
        Integer,
        nullable=False,
        comment="Page number (1-indexed)"
    )
    
    # Image paths
    image_path = Column(
        String(500),
        nullable=True,
        comment="Path to full-resolution image"
    )
    thumbnail_path = Column(
        String(500),
        nullable=True,
        comment="Path to thumbnail image"
    )
    image_url = Column(
        String(500),
        nullable=True,
        comment="Public URL for image"
    )
    
    # Image metadata
    width = Column(
        Integer,
        nullable=True,
        comment="Image width in pixels"
    )
    height = Column(
        Integer,
        nullable=True,
        comment="Image height in pixels"
    )
    file_size = Column(
        Integer,
        nullable=True,
        comment="Image file size in bytes"
    )
    format = Column(
        String(10),
        default="PNG",
        nullable=False,
        comment="Image format"
    )
    
    # Processing status
    is_processed = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether page has been processed by VLM"
    )
    products_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of products extracted from this page"
    )
    
    # VLM extraction results
    extraction_data = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Raw VLM extraction data"
    )
    extraction_confidence = Column(
        Float,
        nullable=True,
        comment="Page-level extraction confidence"
    )
    
    # Page notes from VLM
    page_notes = Column(
        Text,
        nullable=True,
        comment="Notes from VLM about page layout"
    )
    continuation_detected = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether page continues from previous"
    )
    
    # Relationships
    leaflet = relationship("Leaflet", back_populates="pages")
    
    def __repr__(self) -> str:
        return f"<LeafletPage(leaflet_id={self.leaflet_id}, page={self.page_number})>"