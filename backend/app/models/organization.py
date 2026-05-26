"""
Organization Model

Multi-tenant organization model for business accounts and personal workspaces.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class OrganizationStatus(str, enum.Enum):
    """Organization status enumeration."""

    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class OrganizationType(str, enum.Enum):
    """Organization type enumeration."""

    BUSINESS = "business"  # Business/company account
    PERSONAL = "personal"  # Personal workspace (for backward compatibility)


class Organization(Base):
    """
    Organization model for multi-tenancy.

    Represents a business or personal workspace that owns data
    (leaflets, products, etc.) and has multiple users with roles.

    Attributes:
        id: Unique organization identifier
        name: Organization display name
        slug: URL-safe unique identifier
        organization_type: Business or personal workspace
        status: Current approval/active status

        business_name: Official registered business name
        business_email: Primary business contact email
        business_phone: Business phone number
        business_address: Physical business address
        tax_id: Tax identification number (VAT, EIN, etc.)

        logo_url: URL to organization logo
        settings: JSON settings and preferences

        requested_by_user_id: User who created the registration
        approved_by_user_id: Super admin who approved
        approved_at: Timestamp of approval
        rejection_reason: Reason for rejection if suspended

        created_at: Creation timestamp
        updated_at: Last update timestamp
        deleted_at: Soft delete timestamp

    Example:
        >>> org = Organization(
        ...     name="Acme Corp",
        ...     slug="acme-corp",
        ...     organization_type=OrganizationType.BUSINESS,
        ...     business_email="contact@acme.com"
        ... )
    """

    __tablename__ = "organizations"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Unique organization identifier",
    )

    # Core Fields
    name = Column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
        comment="Organization display name (must be unique)",
    )

    slug = Column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
        comment="URL-safe unique identifier for the organization",
    )

    organization_type = Column(
        Enum(OrganizationType, create_type=False),
        nullable=False,
        default=OrganizationType.BUSINESS,
        comment="Type of organization (business or personal)",
    )

    status = Column(
        Enum(OrganizationStatus, create_type=False),
        nullable=False,
        default=OrganizationStatus.PENDING_APPROVAL,
        index=True,
        comment="Current approval/active status",
    )

    # Business Information
    business_name = Column(
        String(300),
        nullable=True,
        comment="Official registered business name (may differ from display name)",
    )

    business_email = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Primary business contact email",
    )

    business_phone = Column(
        String(50),
        nullable=True,
        comment="Business phone number",
    )

    business_address = Column(
        Text,
        nullable=True,
        comment="Physical business address",
    )

    tax_id = Column(
        String(100),
        nullable=True,
        comment="Tax identification number (VAT, EIN, etc.)",
    )

    # Settings & Customization
    logo_url = Column(
        String(500),
        nullable=True,
        comment="URL to organization logo",
    )

    settings = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Organization settings and preferences (JSON)",
    )

    # Platform AI Provider Quota
    platform_leaflet_limit = Column(
        Integer,
        nullable=False,
        default=10,
        server_default="10",
        comment="Max leaflets this org can extract using the platform shared AI provider (0 = unlimited)",
    )

    platform_leaflets_used = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Denormalized count of leaflets that used the platform provider",
    )

    # Approval Workflow
    requested_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who created the registration request",
    )

    approved_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Super admin who approved the registration",
    )

    approved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when organization was approved",
    )

    rejection_reason = Column(
        Text,
        nullable=True,
        comment="Reason for rejection if status is SUSPENDED",
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

    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Soft delete timestamp",
    )

    # Relationships
    users = relationship(
        "User",
        secondary="organization_users",
        primaryjoin="Organization.id==foreign(OrganizationUser.organization_id)",
        secondaryjoin="User.id==foreign(OrganizationUser.user_id)",
        back_populates="organizations",
        viewonly=True,
        doc="Users who are members of this organization",
    )

    organization_users = relationship(
        "OrganizationUser",
        back_populates="organization",
        cascade="all, delete-orphan",
        doc="Organization membership records with roles",
    )

    leaflets = relationship(
        "Leaflet",
        back_populates="organization",
        cascade="all, delete-orphan",
        doc="Leaflets owned by this organization",
    )

    invitations = relationship(
        "OrganizationInvitation",
        back_populates="organization",
        cascade="all, delete-orphan",
        doc="Pending user invitations for this organization",
    )

    retailers = relationship(
        "Retailer",
        back_populates="organization",
        cascade="all, delete-orphan",
        doc="Retailers registered by this organization",
    )

    requested_by = relationship(
        "User",
        foreign_keys=[requested_by_user_id],
        doc="User who created this organization registration",
    )

    approved_by = relationship(
        "User",
        foreign_keys=[approved_by_user_id],
        doc="Super admin who approved this organization",
    )

    # Indexes
    __table_args__ = (
        Index("idx_org_status_created", "status", "created_at"),
        Index("idx_org_type_status", "organization_type", "status"),
        Index("idx_org_business_email", "business_email"),
    )

    def __repr__(self) -> str:
        """String representation of Organization."""
        return f"<Organization(id={self.id}, name='{self.name}', type={self.organization_type.value}, status={self.status.value})>"

    @property
    def is_active(self) -> bool:
        """Check if organization is active and approved."""
        return self.status == OrganizationStatus.ACTIVE

    @property
    def is_pending(self) -> bool:
        """Check if organization is pending approval."""
        return self.status == OrganizationStatus.PENDING_APPROVAL

    @property
    def is_business(self) -> bool:
        """Check if this is a business organization."""
        return self.organization_type == OrganizationType.BUSINESS

    @property
    def is_personal(self) -> bool:
        """Check if this is a personal workspace."""
        return self.organization_type == OrganizationType.PERSONAL

    @property
    def has_platform_quota_remaining(self) -> bool:
        """Check if organization can still use the platform shared AI provider.

        Returns True if:
        - platform_leaflet_limit is 0 (unlimited, superuser override)
        - platform_leaflets_used < platform_leaflet_limit
        """
        if self.platform_leaflet_limit == 0:
            return True
        return self.platform_leaflets_used < self.platform_leaflet_limit

    @property
    def platform_quota_remaining(self) -> Optional[int]:
        """Get number of platform provider extractions remaining.

        Returns None if unlimited (limit == 0), otherwise the remaining count.
        """
        if self.platform_leaflet_limit == 0:
            return None
        return max(0, self.platform_leaflet_limit - self.platform_leaflets_used)

    async def get_member_count(self, db_session) -> int:
        """
        Get the number of active members in this organization.

        Args:
            db_session: SQLAlchemy async database session

        Returns:
            Count of active organization members
        """
        from app.models.organization_user import OrganizationUser

        result = await db_session.execute(
            select(func.count(OrganizationUser.id)).where(
                OrganizationUser.organization_id == self.id,
                OrganizationUser.is_active == True,
            )
        )
        return result.scalar() or 0

    async def get_admin_count(self, db_session) -> int:
        """
        Get the number of admins/owners in this organization.

        Args:
            db_session: SQLAlchemy async database session

        Returns:
            Count of admin/owner members
        """
        from app.models.organization_user import OrganizationRole, OrganizationUser

        result = await db_session.execute(
            select(func.count(OrganizationUser.id)).where(
                OrganizationUser.organization_id == self.id,
                OrganizationUser.is_active == True,
                OrganizationUser.role.in_(
                    [OrganizationRole.OWNER, OrganizationRole.ADMIN]
                ),
            )
        )
        return result.scalar() or 0
