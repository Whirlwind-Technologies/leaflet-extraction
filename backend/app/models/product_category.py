"""
Product Category Model.

Stores system-wide product categories with hierarchical support.
All categories are available to all organizations.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class ProductCategory(Base):
    """
    System-wide product category for classification during extraction and review.

    All categories are available to all organizations (system-level).
    Supports hierarchical structure via parent_id for fallback categories.

    Attributes:
        id: Unique category identifier
        name: Category name (e.g., "Table Salt")
        description: Detailed description with include/exclude rules
        parent_id: Parent category ID for hierarchical structure
        is_active: Whether category is active (soft delete)
        is_fallback: True if this is a fallback/parent category
        sort_order: Display order within parent group
        created_at: Creation timestamp
        updated_at: Last update timestamp

    Example:
        >>> cat = ProductCategory(
        ...     name="Table Salt",
        ...     description="Refined kitchen salt...",
        ...     is_fallback=False
        ... )
    """

    __tablename__ = "product_categories"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Unique category identifier",
    )

    # Category Information
    name = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Category name (unique system-wide)",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Detailed description with include/exclude rules for AI",
    )

    # Hierarchical Structure
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent category for hierarchical structure",
    )

    # Category Type
    is_fallback = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="True if this is a fallback/parent category",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether category is active (False = soft deleted)",
    )

    # Display Order
    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order within parent group",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        comment="Creation timestamp",
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Last update timestamp",
    )

    # Relationships
    parent = relationship(
        "ProductCategory",
        remote_side=[id],
        back_populates="children",
        doc="Parent category",
    )

    children = relationship(
        "ProductCategory",
        back_populates="parent",
        doc="Child categories",
    )

    # Indexes
    __table_args__ = (
        Index("idx_category_parent", "parent_id", "sort_order"),
        Index("idx_category_active", "is_active", "sort_order"),
    )

    def __repr__(self) -> str:
        """String representation of ProductCategory."""
        return f"<ProductCategory(id={self.id}, name='{self.name}')>"

    @property
    def vlm_format(self) -> str:
        """Format for VLM prompt with guidance."""
        if self.is_fallback:
            return f"- {self.name} (FALLBACK): {self.description or ''}"
        return f"- {self.name}: {self.description or ''}"

    @property
    def full_path(self) -> str:
        """Get full category path (e.g., 'Salt > Table Salt')."""
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
