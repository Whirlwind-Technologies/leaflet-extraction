"""
Deletion Request Model

Model for managing organization and user deletion requests requiring super admin approval.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class DeletionRequestType(str, enum.Enum):
    """Type of deletion request."""

    ORGANIZATION = "organization"  # Request to delete entire organization
    USER = "user"  # Request to delete user account (future use)


class DeletionRequestStatus(str, enum.Enum):
    """Deletion request status."""

    PENDING = "pending"  # Awaiting super admin review
    APPROVED = "approved"  # Approved and processed
    REJECTED = "rejected"  # Rejected by super admin


class DeletionRequest(Base):
    """
    Deletion request model for org admin to request organization deletion.

    Organization admins cannot directly delete organizations - they must
    submit a request for super admin approval. This prevents accidental
    data loss and provides an audit trail.

    Attributes:
        id: Unique request identifier
        request_type: Type of deletion (organization or user)

        organization_id: Organization to delete (if applicable)
        user_id: User to delete (if applicable)

        requested_by_user_id: Who submitted the request
        reason: Explanation for deletion request

        status: Current request status
        reviewed_by_user_id: Super admin who reviewed
        reviewed_at: Review timestamp
        review_notes: Admin's notes on the decision

        created_at: Request creation timestamp
        updated_at: Last update timestamp

    Example:
        >>> request = DeletionRequest(
        ...     request_type=DeletionRequestType.ORGANIZATION,
        ...     organization_id=org.id,
        ...     requested_by_user_id=admin.id,
        ...     reason="Company is shutting down"
        ... )
    """

    __tablename__ = "deletion_requests"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Unique deletion request identifier",
    )

    # Request Type
    request_type = Column(
        Enum(DeletionRequestType, create_type=False),
        nullable=False,
        index=True,
        comment="Type of deletion request (organization or user)",
    )

    # What to Delete
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Organization to delete (if request_type is ORGANIZATION)",
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="User to delete (if request_type is USER)",
    )

    # Requester
    requested_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who submitted the deletion request",
    )

    reason = Column(
        Text,
        nullable=True,
        comment="Explanation for why deletion is requested",
    )

    # Status & Review
    status = Column(
        Enum(DeletionRequestStatus, create_type=False),
        nullable=False,
        default=DeletionRequestStatus.PENDING,
        index=True,
        comment="Current request status",
    )

    reviewed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Super admin who reviewed this request",
    )

    reviewed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when request was reviewed",
    )

    review_notes = Column(
        Text,
        nullable=True,
        comment="Super admin's notes on the decision",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        comment="Request creation timestamp",
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
        foreign_keys=[organization_id],
        doc="Organization to be deleted",
    )

    user = relationship(
        "User",
        foreign_keys=[user_id],
        doc="User to be deleted",
    )

    requested_by = relationship(
        "User",
        foreign_keys=[requested_by_user_id],
        doc="User who submitted the request",
    )

    reviewed_by = relationship(
        "User",
        foreign_keys=[reviewed_by_user_id],
        doc="Super admin who reviewed the request",
    )

    # Indexes
    __table_args__ = (
        Index("idx_deletion_type_status", "request_type", "status"),
        Index("idx_deletion_org_status", "organization_id", "status"),
        Index("idx_deletion_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        """String representation of DeletionRequest."""
        return f"<DeletionRequest(type={self.request_type.value}, status={self.status.value}, org_id={self.organization_id})>"

    @property
    def is_pending(self) -> bool:
        """Check if request is pending review."""
        return self.status == DeletionRequestStatus.PENDING

    @property
    def is_approved(self) -> bool:
        """Check if request was approved."""
        return self.status == DeletionRequestStatus.APPROVED

    @property
    def is_rejected(self) -> bool:
        """Check if request was rejected."""
        return self.status == DeletionRequestStatus.REJECTED

    @property
    def is_organization_deletion(self) -> bool:
        """Check if this is an organization deletion request."""
        return self.request_type == DeletionRequestType.ORGANIZATION

    @property
    def is_user_deletion(self) -> bool:
        """Check if this is a user deletion request."""
        return self.request_type == DeletionRequestType.USER

    def approve(self, reviewed_by_user_id: uuid.UUID, review_notes: Optional[str] = None) -> None:
        """
        Approve the deletion request.

        Args:
            reviewed_by_user_id: Super admin who approved
            review_notes: Optional notes on the decision
        """
        self.status = DeletionRequestStatus.APPROVED
        self.reviewed_by_user_id = reviewed_by_user_id
        self.reviewed_at = datetime.now(timezone.utc)
        self.review_notes = review_notes

    def reject(self, reviewed_by_user_id: uuid.UUID, review_notes: str) -> None:
        """
        Reject the deletion request.

        Args:
            reviewed_by_user_id: Super admin who rejected
            review_notes: Reason for rejection
        """
        self.status = DeletionRequestStatus.REJECTED
        self.reviewed_by_user_id = reviewed_by_user_id
        self.reviewed_at = datetime.now(timezone.utc)
        self.review_notes = review_notes

    @classmethod
    def create_organization_deletion(
        cls,
        organization_id: uuid.UUID,
        requested_by_user_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> "DeletionRequest":
        """
        Create an organization deletion request.

        Args:
            organization_id: Organization to delete
            requested_by_user_id: Org admin making the request
            reason: Explanation for deletion

        Returns:
            New DeletionRequest instance
        """
        return cls(
            request_type=DeletionRequestType.ORGANIZATION,
            organization_id=organization_id,
            requested_by_user_id=requested_by_user_id,
            reason=reason,
            status=DeletionRequestStatus.PENDING,
        )

    @classmethod
    def create_user_deletion(
        cls,
        user_id: uuid.UUID,
        requested_by_user_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> "DeletionRequest":
        """
        Create a user deletion request.

        Args:
            user_id: User to delete
            requested_by_user_id: User making the request (usually same as user_id)
            reason: Explanation for deletion

        Returns:
            New DeletionRequest instance
        """
        return cls(
            request_type=DeletionRequestType.USER,
            user_id=user_id,
            requested_by_user_id=requested_by_user_id,
            reason=reason,
            status=DeletionRequestStatus.PENDING,
        )
