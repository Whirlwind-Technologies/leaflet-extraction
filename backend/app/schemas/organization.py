"""
Organization Pydantic Schemas.

This module provides schemas for organization registration, management,
invitations, and deletion requests.

Example Usage:
    from app.schemas.organization import (
        BusinessRegistrationRequest,
        OrganizationResponse,
        OrganizationInvitationCreate
    )
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import BaseSchema, IDSchema, TimestampSchema


# Organization Schemas

class OrganizationBase(BaseSchema):
    """
    Base organization schema with common fields.

    Attributes:
        name: Organization name
        business_name: Legal business name
        business_email: Business contact email
        business_phone: Business phone number
        business_address: Business address
        tax_id: Tax identification number
    """

    name: str = Field(
        min_length=2,
        max_length=200,
        description="Organization display name"
    )
    business_name: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Legal business name"
    )
    business_email: EmailStr = Field(
        description="Primary business email"
    )
    business_phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Business phone number"
    )
    business_address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Business address"
    )
    tax_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Tax identification number"
    )


class BusinessRegistrationRequest(BaseSchema):
    """
    Schema for business registration request.

    Used when a business self-registers through the marketing site or app.
    Creates both an Organization (PENDING_APPROVAL) and a User account.

    Attributes:
        organization_name: Name for the organization
        business_name: Legal business name
        business_email: Business contact email
        business_phone: Optional phone number
        business_address: Optional business address
        tax_id: Optional tax ID
        user_full_name: Full name of the registrant
        user_email: Email of the registrant (will become OWNER)
        user_password: Password for the registrant's account

    Example:
        >>> registration = BusinessRegistrationRequest(
        ...     organization_name="Acme Corp",
        ...     business_name="Acme Corporation Inc.",
        ...     business_email="contact@acme.com",
        ...     user_full_name="John Doe",
        ...     user_email="john@acme.com",
        ...     user_password="SecurePass123!"
        ... )
    """

    # Organization fields
    organization_name: str = Field(
        min_length=2,
        max_length=200,
        description="Organization display name"
    )
    business_name: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Legal business name (if different from organization name)"
    )
    business_email: EmailStr = Field(
        description="Primary business contact email"
    )
    business_phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Business phone number"
    )
    business_address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Business address"
    )
    tax_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Tax identification number"
    )

    # User fields
    user_full_name: str = Field(
        min_length=2,
        max_length=255,
        description="Full name of the person registering"
    )
    user_email: EmailStr = Field(
        description="Email address for the user account"
    )
    user_password: str = Field(
        min_length=8,
        max_length=100,
        description="Password for the user account"
    )

    @field_validator("user_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class BusinessRegistrationResponse(BaseSchema):
    """
    Response after business registration.

    Attributes:
        registration_id: Organization ID (for checking status)
        status: Registration status (always "pending_approval" initially)
        message: Human-readable message
        organization_name: Name of the registered organization
        created_at: Registration timestamp
    """

    registration_id: UUID = Field(description="Organization ID (use for status checks)")
    status: str = Field(description="Registration status")
    message: str = Field(description="Status message")
    organization_name: str = Field(description="Organization name")
    created_at: datetime = Field(description="Registration timestamp")


class RegistrationStatusResponse(BaseSchema):
    """
    Response for checking registration status.

    Attributes:
        registration_id: Organization ID
        organization_name: Organization name
        status: Current status (pending_approval, active, suspended, rejected)
        submitted_at: When registration was submitted
        approved_at: When approved (if approved)
        approved_by: Who approved (if approved)
        rejection_reason: Why rejected (if rejected)
    """

    registration_id: UUID = Field(description="Organization ID")
    organization_name: str = Field(description="Organization name")
    status: str = Field(description="Registration status")
    submitted_at: datetime = Field(description="Submission timestamp")
    approved_at: Optional[datetime] = Field(
        default=None,
        description="Approval timestamp"
    )
    approved_by: Optional[str] = Field(
        default=None,
        description="Approver's name"
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Rejection reason"
    )


class OrganizationResponse(OrganizationBase, IDSchema, TimestampSchema):
    """
    Schema for organization response data.

    Attributes:
        id: Organization unique identifier
        slug: URL-safe slug
        organization_type: Type (business/personal)
        status: Current status
        logo_url: Optional logo URL
        member_count: Number of active members
        is_active: Whether organization is active
        role: User's role in the organization (owner, admin, member, viewer)
    """

    slug: str = Field(description="URL-safe slug")
    organization_type: str = Field(description="Organization type")
    status: str = Field(description="Organization status")
    logo_url: Optional[str] = Field(default=None, description="Logo URL")
    member_count: int = Field(default=0, description="Active member count")
    is_active: bool = Field(description="Whether organization is active")
    role: Optional[str] = Field(default=None, description="User's role in the organization")


class OrganizationUpdate(BaseSchema):
    """
    Schema for updating organization information.

    All fields are optional - only provided fields will be updated.
    Requires ADMIN or OWNER role.
    """

    name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=200,
        description="New organization name"
    )
    business_name: Optional[str] = Field(
        default=None,
        max_length=300,
        description="New business name"
    )
    business_email: Optional[EmailStr] = Field(
        default=None,
        description="New business email"
    )
    business_phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="New phone number"
    )
    business_address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="New address"
    )
    logo_url: Optional[str] = Field(
        default=None,
        description="New logo URL"
    )
    settings: Optional[dict] = Field(
        default=None,
        description="Organization settings"
    )


# Organization Member Schemas

class OrganizationMemberResponse(BaseSchema):
    """
    Schema for organization member information.

    Attributes:
        user_id: User's unique identifier
        full_name: User's full name
        email: User's email
        role: Organization role (owner/admin/member)
        is_active: Whether membership is active
        joined_at: When user joined organization
    """

    user_id: UUID = Field(description="User ID")
    full_name: Optional[str] = Field(description="Full name")
    email: EmailStr = Field(description="Email address")
    role: str = Field(description="Organization role")
    is_active: bool = Field(description="Whether membership is active")
    joined_at: datetime = Field(description="Join timestamp")


class OrganizationMemberUpdate(BaseSchema):
    """
    Schema for updating organization member.

    Requires ADMIN or OWNER role.
    """

    role: Optional[str] = Field(
        default=None,
        description="New role (admin/member)"
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Activate or deactivate membership"
    )


# Invitation Schemas

class OrganizationInvitationCreate(BaseSchema):
    """
    Schema for creating an organization invitation.

    Attributes:
        email: Email address to invite
        role: Role to assign (default: member)
        expiration_days: Days until invitation expires (default: 7)

    Example:
        >>> invitation = OrganizationInvitationCreate(
        ...     email="newuser@acme.com",
        ...     role="member"
        ... )
    """

    email: EmailStr = Field(description="Email address to invite")
    role: str = Field(
        default="member",
        description="Role to assign (member/admin)"
    )
    expiration_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days until invitation expires"
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is allowed for invitations."""
        allowed_roles = ["member", "admin"]
        if v.lower() not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v.lower()


class OrganizationInvitationResponse(IDSchema, TimestampSchema):
    """
    Schema for organization invitation response.

    Attributes:
        id: Invitation ID
        email: Invited email address
        role: Role to be assigned
        status: Invitation status (pending/accepted/expired/revoked)
        expires_at: Expiration timestamp
        invited_by: Name of person who sent invitation
        email_sent: Whether the invitation email was sent successfully
        email_error: Error message if email sending failed
    """

    email: EmailStr = Field(description="Invited email")
    role: str = Field(description="Role to assign")
    status: str = Field(description="Invitation status")
    expires_at: datetime = Field(description="Expiration time")
    invited_by: Optional[str] = Field(
        default=None,
        description="Name of inviter"
    )
    resend_count: int = Field(
        default=0,
        description="Number of times the invitation email has been resent"
    )
    email_sent: bool = Field(
        default=False,
        description="Whether the invitation email was sent successfully"
    )
    email_error: Optional[str] = Field(
        default=None,
        description="Error message if email sending failed (null when email was sent)"
    )


class InvitationAcceptRequest(BaseSchema):
    """
    Schema for accepting an organization invitation.

    If user doesn't exist, they must provide registration details.

    Attributes:
        token: Invitation token from email link
        full_name: Full name (required if new user)
        password: Password (required if new user)
    """

    token: str = Field(description="Invitation token")
    full_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Full name (required for new users)"
    )
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=100,
        description="Password (required for new users)"
    )


class InvitationAcceptResponse(BaseSchema):
    """
    Response after accepting invitation.

    Attributes:
        organization_id: Organization joined
        organization_name: Organization name
        role: Assigned role
        message: Success message
        is_new_user: Whether user account was created
    """

    organization_id: UUID = Field(description="Organization ID")
    organization_name: str = Field(description="Organization name")
    role: str = Field(description="Assigned role")
    message: str = Field(description="Success message")
    is_new_user: bool = Field(description="Whether user was created")


# Deletion Request Schemas

class DeletionRequestCreate(BaseSchema):
    """
    Schema for creating a deletion request.

    Organization admins must request deletion approval from super admins.

    Attributes:
        request_type: Type (organization/user)
        reason: Reason for deletion
    """

    request_type: str = Field(description="Type: organization or user")
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Reason for deletion"
    )

    @field_validator("request_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate request type."""
        allowed_types = ["organization", "user"]
        if v.lower() not in allowed_types:
            raise ValueError(f"Type must be one of: {', '.join(allowed_types)}")
        return v.lower()


class DeletionRequestResponse(IDSchema, TimestampSchema):
    """
    Schema for deletion request response.

    Attributes:
        id: Request ID
        request_type: Type (organization/user)
        organization_name: Organization name (if org deletion)
        user_email: User email (if user deletion)
        status: Request status (pending/approved/rejected)
        reason: Reason for deletion
        requested_by: Who requested
        reviewed_by: Who reviewed (if reviewed)
        reviewed_at: When reviewed (if reviewed)
        review_notes: Admin notes (if reviewed)
    """

    request_type: str = Field(description="Request type")
    organization_name: Optional[str] = Field(
        default=None,
        description="Organization name"
    )
    user_email: Optional[str] = Field(
        default=None,
        description="User email"
    )
    status: str = Field(description="Request status")
    reason: Optional[str] = Field(default=None, description="Deletion reason")
    requested_by: str = Field(description="Requester name")
    reviewed_by: Optional[str] = Field(
        default=None,
        description="Reviewer name"
    )
    reviewed_at: Optional[datetime] = Field(
        default=None,
        description="Review timestamp"
    )
    review_notes: Optional[str] = Field(
        default=None,
        description="Admin review notes"
    )


class DeletionRequestReview(BaseSchema):
    """
    Schema for reviewing a deletion request (approve/reject).

    Requires superuser privileges.

    Attributes:
        review_notes: Notes from the reviewer
    """

    review_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Review notes"
    )


# Admin Approval Schemas

class RegistrationApprovalRequest(BaseSchema):
    """
    Schema for approving a business registration.

    Attributes:
        notes: Optional approval notes
    """

    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Approval notes"
    )


class RegistrationRejectionRequest(BaseSchema):
    """
    Schema for rejecting a business registration.

    Attributes:
        reason: Reason for rejection (required)
    """

    reason: str = Field(
        min_length=10,
        max_length=1000,
        description="Reason for rejection"
    )


class PendingRegistrationResponse(IDSchema, TimestampSchema):
    """
    Schema for pending registration in admin dashboard.

    Attributes:
        id: Organization ID
        organization_name: Organization name
        business_name: Legal business name
        business_email: Business email
        business_phone: Phone number
        tax_id: Tax ID
        requested_by_name: Registrant's name
        requested_by_email: Registrant's email
        status: Current status
        submitted_at: Submission timestamp
    """

    organization_name: str = Field(description="Organization name")
    business_name: Optional[str] = Field(
        default=None,
        description="Business name"
    )
    business_email: EmailStr = Field(description="Business email")
    business_phone: Optional[str] = Field(
        default=None,
        description="Phone number"
    )
    tax_id: Optional[str] = Field(default=None, description="Tax ID")
    requested_by_name: str = Field(description="Registrant name")
    requested_by_email: EmailStr = Field(description="Registrant email")
    status: str = Field(description="Status")
    submitted_at: datetime = Field(description="Submission time")
