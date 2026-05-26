"""
Business Registration API Endpoints.

This module handles business registration workflow:
- Self-registration for businesses
- Registration status checking

Public endpoints that do not require authentication.
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrganizationStatus, OrganizationType
from app.models.organization_user import OrganizationUser, OrganizationRole
from app.models.organization_invitation import OrganizationInvitation
from app.models.user import User
from app.schemas.organization import (
    BusinessRegistrationRequest,
    BusinessRegistrationResponse,
    RegistrationStatusResponse,
    InvitationAcceptRequest,
    InvitationAcceptResponse,
)
from app.utils.database import get_db
from app.utils.security import hash_password
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/registrations", tags=["Business Registration"])


@router.post(
    "",
    response_model=BusinessRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Business",
    description="""
    Register a new business organization.

    This endpoint:
    1. Creates an Organization with PENDING_APPROVAL status
    2. Creates a User account for the registrant
    3. Links the user as OWNER (inactive until approved)
    4. Sends confirmation email to the applicant and notification
       emails to support and every super admin (best effort)

    The registration must be approved by a super admin before the
    organization becomes active and the owner can log in.
    """,
)
async def register_business(
    registration: BusinessRegistrationRequest,
    db: AsyncSession = Depends(get_db),
) -> BusinessRegistrationResponse:
    """
    Register a new business organization.

    Args:
        registration: Business registration details
        db: Database session

    Returns:
        BusinessRegistrationResponse with registration ID and status

    Raises:
        ValidationException: If email already exists or organization name taken
    """
    logger.info(
        f"Business registration request: {registration.organization_name} "
        f"({registration.user_email})"
    )

    # Check if user email already exists
    result = await db.execute(
        select(User).where(User.email == registration.user_email.lower())
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.warning(f"Registration failed: email already exists ({registration.user_email})")
        raise ValidationException(
            message="Email address already registered",
            errors={"user_email": "This email address is already in use"}
        )

    # Check if organization name already exists
    result = await db.execute(
        select(Organization).where(
            Organization.name == registration.organization_name
        )
    )
    existing_org = result.scalar_one_or_none()

    if existing_org:
        logger.warning(
            f"Registration failed: organization name taken ({registration.organization_name})"
        )
        raise ValidationException(
            message="Organization name already taken",
            errors={"organization_name": "This organization name is already in use"}
        )

    # Generate URL-safe slug from organization name
    slug = registration.organization_name.lower().replace(" ", "-")
    # Remove special characters
    slug = "".join(c for c in slug if c.isalnum() or c == "-")

    # Check if slug exists and append number if needed
    slug_suffix = 1
    original_slug = slug
    while True:
        result = await db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        if result.scalar_one_or_none() is None:
            break
        slug = f"{original_slug}-{slug_suffix}"
        slug_suffix += 1

    try:
        # Create Organization (PENDING_APPROVAL status)
        organization = Organization(
            name=registration.organization_name,
            slug=slug,
            organization_type=OrganizationType.BUSINESS,
            status=OrganizationStatus.PENDING_APPROVAL,
            business_name=registration.business_name or registration.organization_name,
            business_email=registration.business_email.lower(),
            business_phone=registration.business_phone,
            business_address=registration.business_address,
            tax_id=registration.tax_id,
            # requested_by_user_id will be set after creating user
        )
        db.add(organization)
        await db.flush()  # Get organization ID

        # Create User account
        user = User(
            email=registration.user_email.lower(),
            hashed_password=hash_password(registration.user_password),
            full_name=registration.user_full_name,
            is_active=False,  # Inactive until approved
            is_verified=False,
            is_superuser=False,
            default_organization_id=organization.id,
        )
        db.add(user)
        await db.flush()  # Get user ID

        # Update organization with requested_by_user_id
        organization.requested_by_user_id = user.id

        # Create OrganizationUser (OWNER role, inactive until approved)
        org_user = OrganizationUser(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.OWNER,
            is_active=False,  # Will be activated upon approval
            invited_by_user_id=None,  # Self-registered
            joined_at=datetime.utcnow(),
        )
        db.add(org_user)

        await db.commit()
        await db.refresh(organization)

        logger.info(
            f"Business registration created: {organization.name} "
            f"(ID: {organization.id}, User: {user.email})"
        )

        # Send notification emails
        try:
            from app.config import settings as app_settings
            from app.services.email_service import email_service

            # Send confirmation email to applicant
            await email_service.send_registration_received(organization, user)
            logger.info(f"Sent registration confirmation email to {user.email}")

            # Send registration alert to support_email (info@leafxtract.com)
            support_email = app_settings.support_email
            if support_email:
                try:
                    await email_service.send_registration_alert_to_support(
                        organization=organization,
                        owner=user,
                        support_email=support_email,
                    )
                    logger.info(
                        f"Sent registration alert to support email: {support_email}"
                    )
                except Exception as support_exc:
                    logger.error(
                        f"Failed to send registration alert to support "
                        f"({support_email}): {support_exc}",
                        exc_info=True,
                    )

            # Notify each super admin individually so the approval
            # workflow shows up in their inbox, not just on the dashboard.
            try:
                super_admin_result = await db.execute(
                    select(User).where(User.is_superuser == True)  # noqa: E712
                )
                super_admins = list(super_admin_result.scalars().all())
                if super_admins:
                    await email_service.send_registration_notification(
                        organization=organization,
                        owner=user,
                        super_admins=super_admins,
                    )
            except Exception as super_exc:
                logger.error(
                    f"Failed to send super admin registration notification: {super_exc}",
                    exc_info=True,
                )

        except Exception as e:
            # Log error but don't fail registration
            logger.error(f"Failed to send registration emails: {e}", exc_info=True)

        return BusinessRegistrationResponse(
            registration_id=organization.id,
            status=OrganizationStatus.PENDING_APPROVAL.value,
            message=(
                "Registration submitted successfully. "
                "You will receive an email once your application is reviewed. "
                "This typically takes 1-2 business days."
            ),
            organization_name=organization.name,
            created_at=organization.created_at,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Business registration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again later."
        )


@router.get(
    "/{registration_id}/status",
    response_model=RegistrationStatusResponse,
    summary="Check Registration Status",
    description="""
    Check the status of a business registration.

    Public endpoint that allows checking registration status using
    the registration ID provided after submitting the registration.

    Possible statuses:
    - pending_approval: Awaiting admin review
    - active: Approved and active
    - suspended: Rejected or suspended
    """,
)
async def get_registration_status(
    registration_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RegistrationStatusResponse:
    """
    Get registration status.

    Args:
        registration_id: Organization ID (from registration response)
        db: Database session

    Returns:
        RegistrationStatusResponse with current status

    Raises:
        HTTPException: If registration not found
    """
    # Find organization
    result = await db.execute(
        select(Organization)
        .where(Organization.id == registration_id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration not found"
        )

    # Get approved_by user if approved
    approved_by_name = None
    if organization.approved_by_user_id:
        result = await db.execute(
            select(User).where(User.id == organization.approved_by_user_id)
        )
        approved_by_user = result.scalar_one_or_none()
        if approved_by_user:
            approved_by_name = approved_by_user.full_name or approved_by_user.email

    return RegistrationStatusResponse(
        registration_id=organization.id,
        organization_name=organization.name,
        status=organization.status.value,
        submitted_at=organization.created_at,
        approved_at=organization.approved_at,
        approved_by=approved_by_name,
        rejection_reason=organization.rejection_reason,
    )


@router.post(
    "/invitations/accept",
    response_model=InvitationAcceptResponse,
    summary="Accept organization invitation",
    description="""
    Accept an organization invitation using the token from the email link.

    If the user doesn't have an account, one will be created.
    If the user exists, they will be added to the organization.
    """,
)
async def accept_invitation(
    request_data: InvitationAcceptRequest,
    db: AsyncSession = Depends(get_db),
) -> InvitationAcceptResponse:
    """
    Accept organization invitation.

    Args:
        request_data: Invitation acceptance data with token
        db: Database session

    Returns:
        InvitationAcceptResponse with organization details

    Raises:
        ValidationException: If invitation is invalid, expired, or already used
    """
    # Find invitation by token
    result = await db.execute(
        select(OrganizationInvitation).where(
            OrganizationInvitation.token == request_data.token
        )
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise ValidationException("Invalid invitation token")

    # Check if invitation can be accepted
    if not invitation.can_be_accepted:
        if invitation.is_expired:
            raise ValidationException("Invitation has expired")
        elif invitation.status.value == "accepted":
            raise ValidationException("Invitation has already been accepted")
        elif invitation.status.value == "revoked":
            raise ValidationException("Invitation has been revoked")
        else:
            raise ValidationException(f"Invitation cannot be accepted (status: {invitation.status.value})")

    # Get organization
    result = await db.execute(
        select(Organization).where(Organization.id == invitation.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise ValidationException("Organization not found")

    # Check if organization is active
    if org.status != OrganizationStatus.ACTIVE:
        raise ValidationException("Organization is not active")

    # Check if user exists
    result = await db.execute(
        select(User).where(User.email == invitation.email.lower())
    )
    user = result.scalar_one_or_none()

    is_new_user = False

    if not user:
        # Create new user
        if not request_data.full_name or not request_data.password:
            raise ValidationException(
                "full_name and password are required for new users"
            )

        user = User(
            email=invitation.email.lower(),
            hashed_password=hash_password(request_data.password),
            full_name=request_data.full_name,
            is_active=True,
            is_verified=True,  # Auto-verify invited users
            is_superuser=False,
            default_organization_id=org.id,
        )
        db.add(user)
        await db.flush()
        is_new_user = True

        logger.info(f"Created new user account for invited user: {user.email}")
    else:
        # Check if user is already a member
        result = await db.execute(
            select(OrganizationUser).where(
                and_(
                    OrganizationUser.organization_id == org.id,
                    OrganizationUser.user_id == user.id,
                )
            )
        )
        existing_membership = result.scalar_one_or_none()
        if existing_membership:
            raise ValidationException("User is already a member of this organization")

        # If user doesn't have a default organization, set it
        if not user.default_organization_id:
            user.default_organization_id = org.id

    # Create organization membership
    org_membership = OrganizationUser(
        organization_id=org.id,
        user_id=user.id,
        role=invitation.role,
        is_active=True,
        invited_by_user_id=invitation.invited_by_user_id,
        joined_at=datetime.utcnow(),
    )
    db.add(org_membership)

    # Mark invitation as accepted
    invitation.accept(user.id)

    await db.commit()

    logger.info(
        f"User {user.email} accepted invitation to organization {org.name} "
        f"(Role: {invitation.role.value}, New user: {is_new_user})"
    )

    return InvitationAcceptResponse(
        organization_id=org.id,
        organization_name=org.name,
        role=invitation.role.value,
        message=(
            f"Successfully joined {org.name}! "
            f"{'Your account has been created and ' if is_new_user else ''}"
            "You can now log in and start using the platform."
        ),
        is_new_user=is_new_user,
    )
