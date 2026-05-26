"""
Organization User Model

Junction table for user-organization membership with roles.
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class OrganizationRole(str, enum.Enum):
    """Organization role enumeration with hierarchy."""

    OWNER = "owner"  # Original registrant, cannot be removed, highest privileges
    ADMIN = "admin"  # Full organization control (manage users, settings, data)
    MEMBER = "member"  # Can upload, review, export data (standard user)
    VIEWER = "viewer"  # Future: Read-only access to data

    @classmethod
    def get_hierarchy_level(cls, role: "OrganizationRole") -> int:
        """
        Get numeric hierarchy level for role comparison.

        Higher number = more privileges.

        Args:
            role: Organization role

        Returns:
            Hierarchy level (0-3)
        """
        hierarchy = {
            cls.VIEWER: 0,
            cls.MEMBER: 1,
            cls.ADMIN: 2,
            cls.OWNER: 3,
        }
        return hierarchy.get(role, 0)

    def has_permission_level(self, required_role: "OrganizationRole") -> bool:
        """
        Check if this role has at least the required permission level.

        Args:
            required_role: Minimum required role

        Returns:
            True if this role has sufficient privileges
        """
        return self.get_hierarchy_level(self) >= self.get_hierarchy_level(
            required_role
        )


class OrganizationUser(Base):
    """
    Organization membership with role-based access control.

    Junction table linking users to organizations with specific roles.
    Enforces data isolation and permission management.

    Attributes:
        id: Unique membership record ID
        organization_id: Organization this membership belongs to
        user_id: User who is a member
        role: User's role in the organization
        is_active: Whether membership is currently active

        invited_by_user_id: Who invited this user (null for owners)
        joined_at: Timestamp when user accepted invitation
        created_at: Record creation timestamp
        updated_at: Last update timestamp

    Example:
        >>> membership = OrganizationUser(
        ...     organization_id=org.id,
        ...     user_id=user.id,
        ...     role=OrganizationRole.MEMBER,
        ...     invited_by_user_id=admin.id
        ... )
    """

    __tablename__ = "organization_users"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Unique membership record identifier",
    )

    # Foreign Keys
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this membership belongs to",
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who is a member of the organization",
    )

    # Role & Permissions
    role = Column(
        Enum(
            OrganizationRole,
            create_type=False,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        default=OrganizationRole.MEMBER,
        comment="User's role in the organization",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this membership is currently active",
    )

    # Invitation Tracking
    invited_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who invited this member (null for owners/founders)",
    )

    joined_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        comment="Timestamp when user joined the organization",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        comment="Record creation timestamp",
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
        back_populates="organization_users",
        doc="Organization this membership belongs to",
    )

    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="organization_memberships",
        doc="User who is a member",
    )

    invited_by = relationship(
        "User",
        foreign_keys=[invited_by_user_id],
        doc="User who invited this member",
    )

    # Constraints & Indexes
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_user",
        ),
        Index("idx_org_user_role", "organization_id", "role"),
        Index("idx_org_user_active", "organization_id", "is_active"),
        Index("idx_user_orgs", "user_id", "organization_id"),
    )

    def __repr__(self) -> str:
        """String representation of OrganizationUser."""
        return f"<OrganizationUser(user_id={self.user_id}, org_id={self.organization_id}, role={self.role.value})>"

    @property
    def is_owner(self) -> bool:
        """Check if this user is an owner."""
        return self.role == OrganizationRole.OWNER

    @property
    def is_admin(self) -> bool:
        """Check if this user is an admin or owner."""
        return self.role in [OrganizationRole.OWNER, OrganizationRole.ADMIN]

    @property
    def is_member(self) -> bool:
        """Check if this user is a regular member."""
        return self.role == OrganizationRole.MEMBER

    @property
    def can_manage_users(self) -> bool:
        """Check if this user can invite/remove other users."""
        return self.is_admin and self.is_active

    @property
    def can_modify_settings(self) -> bool:
        """Check if this user can modify organization settings."""
        return self.is_admin and self.is_active

    @property
    def can_delete_organization(self) -> bool:
        """Check if this user can request organization deletion."""
        return self.is_admin and self.is_active

    def has_role(self, required_role: OrganizationRole) -> bool:
        """
        Check if user has at least the required role level.

        Args:
            required_role: Minimum required role

        Returns:
            True if user's role is equal or higher in hierarchy
        """
        if not self.is_active:
            return False
        return self.role.has_permission_level(required_role)
