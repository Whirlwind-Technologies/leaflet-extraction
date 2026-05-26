"""
Retailer Model

Organization-scoped retailer registry for managing default metadata during leaflet uploads.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Retailer(Base):
    """
    Retailer model for organization-scoped retailer registry.

    Stores retailer information with default metadata values that can be
    auto-filled during leaflet upload.

    Attributes:
        id: Unique retailer identifier
        organization_id: Organization that owns this retailer
        name: Retailer name (unique per organization)
        country: Default country code (ISO 3166-1 alpha-2)
        currency: Default currency code (ISO 4217)
        language: Default language code (ISO 639-1)
        logo_url: Optional retailer logo URL
        external_id: Optional external identifier for integrations
        is_active: Whether retailer is active (soft delete)
        created_at: Creation timestamp
        updated_at: Last update timestamp

    Constraints:
        - Unique (organization_id, name) to prevent duplicates per org

    Example:
        >>> retailer = Retailer(
        ...     organization_id=org.id,
        ...     name="SuperMart",
        ...     country="US",
        ...     currency="USD",
        ...     language="en"
        ... )
    """

    __tablename__ = "retailers"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Unique retailer identifier",
    )

    # Organization ownership (multi-tenant)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this retailer",
    )

    # Retailer Information
    name = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Retailer name",
    )

    country = Column(
        String(2),
        nullable=True,
        comment="Default country code (ISO 3166-1 alpha-2)",
    )

    currency = Column(
        String(3),
        nullable=True,
        comment="Default currency code (ISO 4217)",
    )

    language = Column(
        String(5),
        nullable=True,
        comment="Default language code (ISO 639-1)",
    )

    logo_url = Column(
        String(500),
        nullable=True,
        comment="Optional retailer logo URL",
    )

    external_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Optional external identifier for integration with other systems",
    )

    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether retailer is active (False = soft deleted)",
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
    organization = relationship(
        "Organization",
        back_populates="retailers",
        doc="Organization that owns this retailer",
    )

    leaflets = relationship(
        "Leaflet",
        back_populates="retailer_ref",
        doc="Leaflets associated with this retailer",
    )

    # Indexes and Constraints
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "name",
            name="uq_retailer_org_name",
        ),
        Index("idx_retailer_org_active", "organization_id", "is_active"),
        Index("idx_retailer_name_lower", "name"),
    )

    def __repr__(self) -> str:
        """String representation of Retailer."""
        return f"<Retailer(id={self.id}, name='{self.name}', org={self.organization_id})>"

    @property
    def display_name(self) -> str:
        """Get display name with country/currency info."""
        parts = [self.name]
        if self.country or self.currency:
            meta = "/".join(filter(None, [self.country, self.currency]))
            parts.append(f"({meta})")
        return " ".join(parts)
