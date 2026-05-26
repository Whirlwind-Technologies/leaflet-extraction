"""
Organization Invitation Model

Model for managing user invitations to join organizations.
"""

import enum
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.organization_user import OrganizationRole


class InvitationStatus(str, enum.Enum):
    """Invitation status enumeration."""

    PENDING = "pending"  # Invitation sent, awaiting acceptance
    ACCEPTED = "accepted"  # User accepted and joined organization
    EXPIRED = "expired"  # Invitation expired (not accepted in time)
    REVOKED = "revoked"  # Admin cancelled the invitation


class OrganizationInvitation(Base):
    """
    Organization user invitation model.

    Manages the invitation workflow for adding new users to organizations.
    Uses secure tokens with expiration for invitation links.

    Attributes:
        id: Unique invitation identifier
        organization_id: Organization user is invited to
        invited_by_user_id: Admin who sent the invitation

        email: Email address of invitee
        role: Role the user will have when they accept

        token: Secure random token for invitation link
        status: Current invitation status
        expires_at: Expiration timestamp (7 days default)

        accepted_at: Timestamp when invitation was accepted
        accepted_by_user_id: User who accepted (may differ if email already registered)

        created_at: Invitation creation timestamp
        updated_at: Last update timestamp

    Example:
        >>> invitation = OrganizationInvitation.create(
        ...     organization_id=org.id,
        ...     email="newuser@example.com",
        ...     role=OrganizationRole.MEMBER,
        ...     invited_by_user_id=admin.id
        ... )
    """

    __tablename__ = "organization_invitations"

    # Default expiration: 7 days
    DEFAULT_EXPIRATION_DAYS = 7

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Unique invitation identifier",
    )

    # Foreign Keys
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization user is being invited to",
    )

    invited_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who sent this invitation (admin/owner)",
    )

    # Invitee Information
    email = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Email address of the person being invited",
    )

    role = Column(
        Enum(
            OrganizationRole,
            create_type=False,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        default=OrganizationRole.MEMBER,
        comment="Role the user will have when they accept",
    )

    # Token & Security
    token = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="Secure random token for invitation link",
    )

    # Status & Expiration
    status = Column(
        Enum(InvitationStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=InvitationStatus.PENDING,
        index=True,
        comment="Current invitation status",
    )

    resend_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of times the invitation email has been resent",
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Expiration timestamp for this invitation",
    )

    # Acceptance Tracking
    accepted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when invitation was accepted",
    )

    accepted_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who accepted this invitation",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        comment="Invitation creation timestamp",
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
        back_populates="invitations",
        doc="Organization this invitation is for",
    )

    invited_by = relationship(
        "User",
        foreign_keys=[invited_by_user_id],
        doc="User who sent this invitation",
    )

    accepted_by = relationship(
        "User",
        foreign_keys=[accepted_by_user_id],
        doc="User who accepted this invitation",
    )

    # Indexes
    __table_args__ = (
        Index("idx_invitation_email_status", "email", "status"),
        Index("idx_invitation_org_status", "organization_id", "status"),
        Index("idx_invitation_expires", "expires_at", "status"),
    )

    def __repr__(self) -> str:
        """String representation of OrganizationInvitation."""
        return f"<OrganizationInvitation(email='{self.email}', org_id={self.organization_id}, status={self.status.value})>"

    @classmethod
    def create(
        cls,
        organization_id: uuid.UUID,
        email: str,
        role: OrganizationRole,
        invited_by_user_id: uuid.UUID,
        expiration_days: int = DEFAULT_EXPIRATION_DAYS,
    ) -> "OrganizationInvitation":
        """
        Create a new organization invitation with secure token.

        Args:
            organization_id: Organization ID
            email: Invitee email address
            role: Role to assign when accepted
            invited_by_user_id: User who is sending the invitation
            expiration_days: Days until expiration (default: 7)

        Returns:
            New OrganizationInvitation instance
        """
        token = secrets.token_urlsafe(48)  # 64 character URL-safe token
        expires_at = datetime.now(timezone.utc) + timedelta(days=expiration_days)

        return cls(
            organization_id=organization_id,
            email=email.lower().strip(),  # Normalize email
            role=role,
            invited_by_user_id=invited_by_user_id,
            token=token,
            status=InvitationStatus.PENDING,
            expires_at=expires_at,
        )

    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        if self.status == InvitationStatus.EXPIRED:
            return True
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return True
        return False

    @property
    def is_pending(self) -> bool:
        """Check if invitation is still pending."""
        return self.status == InvitationStatus.PENDING and not self.is_expired

    @property
    def is_accepted(self) -> bool:
        """Check if invitation was accepted."""
        return self.status == InvitationStatus.ACCEPTED

    @property
    def is_revoked(self) -> bool:
        """Check if invitation was revoked."""
        return self.status == InvitationStatus.REVOKED

    @property
    def can_be_accepted(self) -> bool:
        """Check if invitation can still be accepted."""
        return self.is_pending and not self.is_expired

    def accept(self, user_id: uuid.UUID) -> None:
        """
        Mark invitation as accepted.

        Args:
            user_id: ID of user who accepted the invitation
        """
        self.status = InvitationStatus.ACCEPTED
        self.accepted_at = datetime.now(timezone.utc)
        self.accepted_by_user_id = user_id

    def revoke(self) -> None:
        """Mark invitation as revoked."""
        self.status = InvitationStatus.REVOKED
        self.updated_at = datetime.now(timezone.utc)

    def mark_expired(self) -> None:
        """Mark invitation as expired."""
        self.status = InvitationStatus.EXPIRED
        self.updated_at = datetime.now(timezone.utc)

    def get_invitation_link(self, base_url: str) -> str:
        """
        Generate the full invitation link URL.

        Args:
            base_url: Base URL of the application

        Returns:
            Full invitation link
        """
        return f"{base_url}/invitations/{self.token}"
