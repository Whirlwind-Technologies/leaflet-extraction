"""
Organization Management API Endpoints.

This module handles organization CRUD operations, member management,
invitations, and deletion requests.

Requires authentication and appropriate organization role.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_current_organization,
    get_current_org_admin,
    get_current_org_membership,
    get_db,
)
from app.models.user import User
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_user import OrganizationUser, OrganizationRole
from app.models.organization_invitation import OrganizationInvitation, InvitationStatus
from app.models.deletion_request import DeletionRequest, DeletionRequestType
from app.schemas.organization import (
    OrganizationResponse,
    OrganizationUpdate,
    OrganizationMemberResponse,
    OrganizationMemberUpdate,
    OrganizationInvitationCreate,
    OrganizationInvitationResponse,
    InvitationAcceptRequest,
    InvitationAcceptResponse,
    DeletionRequestCreate,
    DeletionRequestResponse,
)
from app.models.vlm_provider import VLMProvider
from app.schemas.platform_quota import PlatformQuotaResponse
from app.utils.exceptions import NotFoundError, ValidationException, AuthorizationError
from app.utils.security import hash_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


# --- Organization Endpoints ---


@router.get(
    "",
    response_model=List[OrganizationResponse],
    summary="List user's organizations",
    description="Get all organizations the current user belongs to.",
)
async def list_user_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[OrganizationResponse]:
    """
    List all organizations the user is a member of.

    Returns organization details including role and member count.
    """
    # Get user's organization memberships
    result = await db.execute(
        select(OrganizationUser)
        .where(
            and_(
                OrganizationUser.user_id == current_user.id,
                OrganizationUser.is_active == True,
            )
        )
    )
    memberships = result.scalars().all()

    responses = []
    for membership in memberships:
        # Get organization
        result = await db.execute(
            select(Organization).where(Organization.id == membership.organization_id)
        )
        org = result.scalar_one_or_none()

        if org:
            # Get member count
            member_count = await org.get_member_count(db)

            responses.append(
                OrganizationResponse(
                    id=org.id,
                    name=org.name,
                    slug=org.slug,
                    organization_type=org.organization_type.value,
                    status=org.status.value,
                    business_name=org.business_name,
                    business_email=org.business_email,
                    business_phone=org.business_phone,
                    business_address=org.business_address,
                    tax_id=org.tax_id,
                    logo_url=org.logo_url,
                    member_count=member_count,
                    is_active=org.is_active,
                    role=membership.role.value,
                    created_at=org.created_at,
                    updated_at=org.updated_at,
                )
            )

    logger.info(f"User {current_user.email} listed {len(responses)} organizations")
    return responses


# --- Platform Quota Endpoint ---
# IMPORTANT: This must be registered BEFORE /{org_id} to avoid FastAPI path collision.


@router.get(
    "/current/platform-quota",
    response_model=PlatformQuotaResponse,
    summary="Get platform AI provider quota",
    description=(
        "Returns the current organization's usage and remaining quota for the "
        "platform shared AI provider. When the organization has its own active "
        "VLM provider configured, the platform limit does not apply."
    ),
)
async def get_platform_quota(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> PlatformQuotaResponse:
    """Get the current organization's platform AI provider quota.

    Checks whether the organization has any active VLM providers of its own.
    If so, the platform limit is irrelevant and ``is_unlimited`` is True.
    If the organization relies on the platform provider, returns the
    configured limit and current usage.

    Args:
        current_user: Authenticated user from JWT token.
        current_org: Current organization from dependency injection.
        db: Async database session.

    Returns:
        PlatformQuotaResponse with limit, used, remaining, and provider status.
    """
    # Check if org has any active own VLM provider
    result = await db.execute(
        select(VLMProvider).where(
            VLMProvider.organization_id == current_org.id,
            VLMProvider.is_active.is_(True),
        ).limit(1)
    )
    has_own_provider = result.scalar_one_or_none() is not None

    limit = current_org.platform_leaflet_limit
    used = current_org.platform_leaflets_used
    is_unlimited = has_own_provider or limit == 0

    logger.info(
        f"Platform quota check for org {current_org.name}: "
        f"limit={limit}, used={used}, has_own_provider={has_own_provider}, "
        f"is_unlimited={is_unlimited}"
    )

    return PlatformQuotaResponse(
        limit=limit,
        used=used,
        remaining=None if is_unlimited else max(0, limit - used),
        has_own_provider=has_own_provider,
        is_unlimited=is_unlimited,
    )


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization details",
    description="Get detailed information about an organization.",
)
async def get_organization(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """Get organization details."""
    # Get organization
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise NotFoundError("Organization", str(org_id))

    # Verify user is a member
    result = await db.execute(
        select(OrganizationUser).where(
            and_(
                OrganizationUser.organization_id == org_id,
                OrganizationUser.user_id == current_user.id,
                OrganizationUser.is_active == True,
            )
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise AuthorizationError("You are not a member of this organization")

    # Get member count
    member_count = await org.get_member_count(db)

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        organization_type=org.organization_type.value,
        status=org.status.value,
        business_name=org.business_name,
        business_email=org.business_email,
        business_phone=org.business_phone,
        business_address=org.business_address,
        tax_id=org.tax_id,
        logo_url=org.logo_url,
        member_count=member_count,
        is_active=org.is_active,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization",
    description="Update organization details (requires admin/owner role).",
)
async def update_organization(
    org_id: UUID,
    update_data: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """Update organization details."""
    # Get organization
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise NotFoundError("Organization", str(org_id))

    # Verify user has admin/owner role
    result = await db.execute(
        select(OrganizationUser).where(
            and_(
                OrganizationUser.organization_id == org_id,
                OrganizationUser.user_id == current_user.id,
                OrganizationUser.is_active == True,
            )
        )
    )
    membership = result.scalar_one_or_none()

    if not membership or membership.role not in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
        raise AuthorizationError("Admin or owner role required")

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if hasattr(org, field):
            setattr(org, field, value)

    org.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(org)

    logger.info(f"User {current_user.email} updated organization {org.name}")

    # Get member count
    member_count = await org.get_member_count(db)

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        organization_type=org.organization_type.value,
        status=org.status.value,
        business_name=org.business_name,
        business_email=org.business_email,
        business_phone=org.business_phone,
        business_address=org.business_address,
        tax_id=org.tax_id,
        logo_url=org.logo_url,
        member_count=member_count,
        is_active=org.is_active,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@router.post(
    "/{org_id}/switch",
    summary="Switch active organization",
    description="Set this organization as the user's default/active organization.",
)
async def switch_organization(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Switch to a different organization.

    Updates user's default_organization_id.
    Future: Could also generate new JWT token with updated org_id.
    """
    # Verify user is a member
    result = await db.execute(
        select(OrganizationUser).where(
            and_(
                OrganizationUser.organization_id == org_id,
                OrganizationUser.user_id == current_user.id,
                OrganizationUser.is_active == True,
            )
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise AuthorizationError("You are not a member of this organization")

    # Update user's default organization
    current_user.default_organization_id = org_id
    await db.commit()

    logger.info(f"User {current_user.email} switched to organization {org_id}")

    # Issue a fresh access token carrying the new org_id so subsequent
    # requests resolve to the right tenant immediately (the existing
    # token still carries the old org_id until it expires).
    from app.utils.security import create_access_token

    new_token = create_access_token({
        "sub": str(current_user.id),
        "org_id": str(org_id),
        "role": membership.role.value,
    })

    return {
        "message": "Organization switched successfully",
        "organization_id": str(org_id),
        "access_token": new_token,
        "token_type": "bearer",
    }


@router.post(
    "/{org_id}/deletion-request",
    response_model=DeletionRequestResponse,
    summary="Request organization deletion",
    description="Create a deletion request (requires admin/owner approval from super admin).",
)
async def create_organization_deletion_request(
    org_id: UUID,
    request_data: DeletionRequestCreate,
    current_user: User = Depends(get_current_user),
    admin_membership: OrganizationUser = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> DeletionRequestResponse:
    """
    Request organization deletion.

    Requires admin/owner role. Super admin must approve the request.
    """
    # Get organization
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise NotFoundError("Organization", str(org_id))

    # Check if there's already a pending request
    result = await db.execute(
        select(DeletionRequest).where(
            and_(
                DeletionRequest.organization_id == org_id,
                DeletionRequest.status == "pending",
            )
        )
    )
    existing_request = result.scalar_one_or_none()

    if existing_request:
        raise ValidationException("A deletion request is already pending for this organization")

    # Create deletion request
    deletion_request = DeletionRequest.create_organization_deletion(
        organization_id=org_id,
        requested_by_user_id=current_user.id,
        reason=request_data.reason,
    )
    db.add(deletion_request)
    await db.commit()
    await db.refresh(deletion_request)

    logger.warning(
        f"User {current_user.email} requested deletion of organization {org.name} "
        f"(ID: {org_id})"
    )

    # Notify all super admins via email (best-effort — failures here
    # must not prevent the deletion request from being persisted).
    try:
        from app.services.email_service import email_service

        super_admin_result = await db.execute(
            select(User).where(User.is_superuser == True)  # noqa: E712
        )
        super_admins = list(super_admin_result.scalars().all())
        if super_admins:
            await email_service.send_deletion_request_notification(
                deletion_request=deletion_request,
                organization=org,
                requested_by=current_user,
                super_admins=super_admins,
            )
    except Exception as e:
        logger.error(f"Failed to send deletion notification to super admins: {e}")

    return DeletionRequestResponse(
        id=deletion_request.id,
        request_type=deletion_request.request_type.value,
        organization_name=org.name,
        user_email=None,
        status=deletion_request.status.value,
        reason=deletion_request.reason,
        requested_by=current_user.full_name or current_user.email,
        reviewed_by=None,
        reviewed_at=None,
        review_notes=None,
        created_at=deletion_request.created_at,
        updated_at=deletion_request.updated_at,
    )


# --- Member Management Endpoints ---


@router.get(
    "/{org_id}/members",
    response_model=List[OrganizationMemberResponse],
    summary="List organization members",
    description="Get all members of the organization.",
)
async def list_organization_members(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[OrganizationMemberResponse]:
    """List all members of an organization."""
    # Verify user is a member
    result = await db.execute(
        select(OrganizationUser).where(
            and_(
                OrganizationUser.organization_id == org_id,
                OrganizationUser.user_id == current_user.id,
                OrganizationUser.is_active == True,
            )
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise AuthorizationError("You are not a member of this organization")

    # Get all members
    result = await db.execute(
        select(OrganizationUser).where(OrganizationUser.organization_id == org_id)
    )
    memberships = result.scalars().all()

    responses = []
    for member in memberships:
        # Get user details
        result = await db.execute(
            select(User).where(User.id == member.user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            responses.append(
                OrganizationMemberResponse(
                    user_id=user.id,
                    full_name=user.full_name,
                    email=user.email,
                    role=member.role.value,
                    is_active=member.is_active,
                    joined_at=member.joined_at,
                )
            )

    return responses


@router.put(
    "/{org_id}/members/{user_id}",
    response_model=OrganizationMemberResponse,
    summary="Update organization member",
    description="Update member's role or status (requires admin/owner role).",
)
async def update_organization_member(
    org_id: UUID,
    user_id: UUID,
    update_data: OrganizationMemberUpdate,
    current_user: User = Depends(get_current_user),
    admin_membership: OrganizationUser = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMemberResponse:
    """Update organization member."""
    # Get member
    result = await db.execute(
        select(OrganizationUser).where(
            and_(
                OrganizationUser.organization_id == org_id,
                OrganizationUser.user_id == user_id,
            )
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        raise NotFoundError("Member", str(user_id))

    # Prevent modifying owner role (only owner can change own role)
    if member.role == OrganizationRole.OWNER and admin_membership.role != OrganizationRole.OWNER:
        raise AuthorizationError("Only owners can modify owner roles")

    # Prevent removing last admin
    if update_data.role and update_data.role != "admin" and update_data.role != "owner":
        admin_count = await db.scalar(
            select(func.count(OrganizationUser.id)).where(
                and_(
                    OrganizationUser.organization_id == org_id,
                    OrganizationUser.role.in_([OrganizationRole.ADMIN, OrganizationRole.OWNER]),
                    OrganizationUser.is_active == True,
                )
            )
        )
        if admin_count <= 1:
            raise ValidationException("Cannot remove the last admin from the organization")

    # Update fields
    if update_data.role:
        member.role = OrganizationRole(update_data.role)
    if update_data.is_active is not None:
        member.is_active = update_data.is_active

    await db.commit()
    await db.refresh(member)

    # Get user details
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    logger.info(
        f"Admin {current_user.email} updated member {user.email} in org {org_id}"
    )

    return OrganizationMemberResponse(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=member.role.value,
        is_active=member.is_active,
        joined_at=member.joined_at,
    )


@router.delete(
    "/{org_id}/members/{user_id}",
    summary="Remove organization member",
    description="Remove a member from the organization (requires admin/owner role).",
)
async def remove_organization_member(
    org_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    admin_membership: OrganizationUser = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove member from organization."""
    # Get member
    result = await db.execute(
        select(OrganizationUser).where(
            and_(
                OrganizationUser.organization_id == org_id,
                OrganizationUser.user_id == user_id,
            )
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        raise NotFoundError("Member", str(user_id))

    # Prevent removing owner
    if member.role == OrganizationRole.OWNER:
        raise AuthorizationError("Cannot remove organization owner")

    # Prevent removing last admin
    admin_count = await db.scalar(
        select(func.count(OrganizationUser.id)).where(
            and_(
                OrganizationUser.organization_id == org_id,
                OrganizationUser.role.in_([OrganizationRole.ADMIN, OrganizationRole.OWNER]),
                OrganizationUser.is_active == True,
            )
        )
    )
    if member.role in [OrganizationRole.ADMIN, OrganizationRole.OWNER] and admin_count <= 1:
        raise ValidationException("Cannot remove the last admin from the organization")

    # Get user for logging
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    # Fetch the organization name for the notification email
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    organization = org_result.scalar_one_or_none()
    org_name = organization.name if organization else str(org_id)

    # Delete membership
    await db.delete(member)
    await db.commit()

    logger.info(
        f"Admin {current_user.email} removed member {user.email if user else user_id} "
        f"from org {org_id}"
    )

    # Notify the removed member via email (best-effort — failures here
    # must not prevent the removal from succeeding).
    if user:
        try:
            from app.services.email_service import email_service

            subject = f"You have been removed from {org_name}"
            html_body = (
                f"<p>Hello {user.full_name or user.email},</p>"
                f"<p>You have been removed from the organization "
                f"<b>{org_name}</b> by an administrator.</p>"
                f"<p>If you believe this is an error, please contact "
                f"your organization administrator or our support team.</p>"
            )
            await email_service._send_email(
                to_email=user.email,
                to_name=user.full_name,
                subject=subject,
                html_body=html_body,
            )
        except Exception as e:
            logger.error(
                f"Failed to send member removal notification to {user.email}: {e}"
            )

    return {"message": "Member removed successfully"}


# --- Invitation Endpoints ---


@router.get(
    "/{org_id}/invitations",
    response_model=List[OrganizationInvitationResponse],
    summary="List organization invitations",
    description="Get all pending invitations (requires admin/owner role).",
)
async def list_organization_invitations(
    org_id: UUID,
    status_filter: Optional[str] = Query(default="pending", description="Filter by status"),
    current_user: User = Depends(get_current_user),
    admin_membership: OrganizationUser = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> List[OrganizationInvitationResponse]:
    """List organization invitations."""
    query = select(OrganizationInvitation).where(
        OrganizationInvitation.organization_id == org_id
    )

    if status_filter != "all":
        status_enum = InvitationStatus(status_filter.lower())
        query = query.where(OrganizationInvitation.status == status_enum)

    query = query.order_by(OrganizationInvitation.created_at.desc())

    result = await db.execute(query)
    invitations = result.scalars().all()

    responses = []
    for invitation in invitations:
        # Get inviter name
        inviter_name = None
        if invitation.invited_by_user_id:
            result = await db.execute(
                select(User).where(User.id == invitation.invited_by_user_id)
            )
            inviter = result.scalar_one_or_none()
            if inviter:
                inviter_name = inviter.full_name or inviter.email

        responses.append(
            OrganizationInvitationResponse(
                id=invitation.id,
                email=invitation.email,
                role=invitation.role.value,
                status=invitation.status.value,
                expires_at=invitation.expires_at,
                invited_by=inviter_name,
                resend_count=invitation.resend_count or 0,
                created_at=invitation.created_at,
                updated_at=invitation.updated_at,
            )
        )

    return responses


@router.post(
    "/{org_id}/invitations",
    response_model=OrganizationInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create invitation",
    description="Invite a user to the organization (requires admin/owner role).",
)
async def create_organization_invitation(
    org_id: UUID,
    invitation_data: OrganizationInvitationCreate,
    current_user: User = Depends(get_current_user),
    admin_membership: OrganizationUser = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationInvitationResponse:
    """Create organization invitation."""
    # Check if user is already a member
    result = await db.execute(
        select(User).where(User.email == invitation_data.email.lower())
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # Check if already a member
        result = await db.execute(
            select(OrganizationUser).where(
                and_(
                    OrganizationUser.organization_id == org_id,
                    OrganizationUser.user_id == existing_user.id,
                )
            )
        )
        existing_membership = result.scalar_one_or_none()
        if existing_membership:
            raise ValidationException("User is already a member of this organization")

    # Check for existing pending invitation
    result = await db.execute(
        select(OrganizationInvitation).where(
            and_(
                OrganizationInvitation.organization_id == org_id,
                OrganizationInvitation.email == invitation_data.email.lower(),
                OrganizationInvitation.status == InvitationStatus.PENDING,
            )
        )
    )
    existing_invitation = result.scalar_one_or_none()
    if existing_invitation:
        raise ValidationException("An invitation is already pending for this email")

    # Get organization for email
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    # Create invitation
    invitation = OrganizationInvitation.create(
        organization_id=org_id,
        email=invitation_data.email,
        role=OrganizationRole(invitation_data.role),
        invited_by_user_id=current_user.id,
        expiration_days=invitation_data.expiration_days,
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    logger.info(
        f"User {current_user.email} invited {invitation_data.email} to org {org_id}"
    )

    # Send invitation email (don't fail the invitation creation if email fails)
    email_sent = False
    email_error = None
    try:
        from app.services.email_service import email_service
        email_sent = await email_service.send_invitation(invitation, org, current_user)
        if email_sent:
            logger.info(f"Invitation email sent to {invitation_data.email}")
        else:
            logger.warning(
                f"Invitation email not sent to {invitation_data.email} "
                f"(email sending may be disabled)"
            )
    except Exception as e:
        email_error = str(e)
        logger.error(
            f"Failed to send invitation email to {invitation_data.email}: {e}",
            exc_info=True,
        )

    return OrganizationInvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role.value,
        status=invitation.status.value,
        expires_at=invitation.expires_at,
        invited_by=current_user.full_name or current_user.email,
        email_sent=email_sent,
        email_error=email_error if not email_sent else None,
        resend_count=invitation.resend_count or 0,
        created_at=invitation.created_at,
        updated_at=invitation.updated_at,
    )


@router.delete(
    "/{org_id}/invitations/{invitation_id}",
    summary="Revoke invitation",
    description="Revoke a pending invitation (requires admin/owner role).",
)
async def revoke_organization_invitation(
    org_id: UUID,
    invitation_id: UUID,
    current_user: User = Depends(get_current_user),
    admin_membership: OrganizationUser = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
):
    """Revoke invitation."""
    result = await db.execute(
        select(OrganizationInvitation).where(
            and_(
                OrganizationInvitation.id == invitation_id,
                OrganizationInvitation.organization_id == org_id,
            )
        )
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise NotFoundError("Invitation", str(invitation_id))

    invitation.revoke()
    await db.commit()

    logger.info(f"User {current_user.email} revoked invitation {invitation_id}")

    return {"message": "Invitation revoked successfully"}


# Maximum number of times an invitation email can be resent
MAX_INVITATION_RESENDS = 3

# Minimum seconds between resend attempts for the same invitation
RESEND_COOLDOWN_SECONDS = 60


@router.post(
    "/{org_id}/invitations/{invitation_id}/resend",
    response_model=OrganizationInvitationResponse,
    summary="Resend invitation email",
    description="Resend the invitation email for a pending invitation (requires admin/owner role). "
    "Rate limited to a maximum of 3 resends with a 60-second cooldown between attempts.",
)
async def resend_organization_invitation(
    org_id: UUID,
    invitation_id: UUID,
    current_user: User = Depends(get_current_user),
    admin_membership: OrganizationUser = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationInvitationResponse:
    """Resend invitation email for a pending invitation.

    Finds the pending invitation, verifies it has not exceeded the maximum
    number of resends, and sends the invitation email again.

    Args:
        org_id: Organization UUID.
        invitation_id: Invitation UUID to resend.
        current_user: Authenticated user from JWT token.
        admin_membership: Verified admin/owner membership from dependency.
        db: Async database session.

    Returns:
        OrganizationInvitationResponse with email_sent status.

    Raises:
        NotFoundError: If invitation does not exist.
        ValidationException: If invitation is not pending, is expired,
            or resend limit has been reached.
    """
    # Fetch the invitation
    result = await db.execute(
        select(OrganizationInvitation).where(
            and_(
                OrganizationInvitation.id == invitation_id,
                OrganizationInvitation.organization_id == org_id,
            )
        )
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise NotFoundError("Invitation", str(invitation_id))

    # Verify invitation is still pending and not expired
    if not invitation.is_pending:
        raise ValidationException(
            f"Cannot resend invitation with status '{invitation.status.value}'. "
            f"Only pending invitations can be resent."
        )

    if invitation.is_expired:
        invitation.mark_expired()
        await db.commit()
        raise ValidationException(
            "This invitation has expired. Please create a new invitation."
        )

    # Check max resend limit
    if invitation.resend_count >= MAX_INVITATION_RESENDS:
        raise ValidationException(
            [{"field": "invitation_id", "message": f"Maximum resend limit ({MAX_INVITATION_RESENDS}) reached. Create a new invitation instead."}],
            message=f"Maximum resend limit ({MAX_INVITATION_RESENDS}) reached",
        )

    # Rate limiting: enforce a cooldown period between resend attempts.
    now = datetime.utcnow()
    if invitation.updated_at:
        seconds_since_last_update = (now - invitation.updated_at.replace(tzinfo=None)).total_seconds()
        if seconds_since_last_update < RESEND_COOLDOWN_SECONDS:
            raise ValidationException(
                f"Please wait at least {RESEND_COOLDOWN_SECONDS} seconds between "
                f"resend attempts. Try again in "
                f"{int(RESEND_COOLDOWN_SECONDS - seconds_since_last_update)} seconds."
            )

    # Fetch the organization for the email template
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise NotFoundError("Organization", str(org_id))

    # Send the invitation email
    email_sent = False
    email_error = None
    try:
        from app.services.email_service import email_service
        email_sent = await email_service.send_invitation(invitation, org, current_user)
        if email_sent:
            logger.info(
                f"Invitation email resent to {invitation.email} "
                f"for org {org.name} by {current_user.email}"
            )
        else:
            logger.warning(
                f"Invitation email resend to {invitation.email} not sent "
                f"(email sending may be disabled)"
            )
    except Exception as e:
        email_error = str(e)
        logger.error(
            f"Failed to resend invitation email to {invitation.email}: {e}",
            exc_info=True,
        )

    # Increment resend counter and touch updated_at for cooldown enforcement
    invitation.resend_count = (invitation.resend_count or 0) + 1
    invitation.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(invitation)

    # Get inviter name
    inviter_name = current_user.full_name or current_user.email

    return OrganizationInvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role.value,
        status=invitation.status.value,
        expires_at=invitation.expires_at,
        invited_by=inviter_name,
        email_sent=email_sent,
        email_error=email_error if not email_sent else None,
        resend_count=invitation.resend_count or 0,
        created_at=invitation.created_at,
        updated_at=invitation.updated_at,
    )


@router.post(
    "/{org_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add member directly",
    description="Add an existing user to the organization directly (requires admin/owner role).",
)
async def add_organization_member_directly(
    org_id: UUID,
    user_email: str,
    role: str = "member",
    current_user: User = Depends(get_current_user),
    admin_membership: OrganizationUser = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMemberResponse:
    """
    Add an existing user to the organization directly without an invitation.

    This bypasses the invitation flow and adds the user immediately.
    Requires admin/owner role.
    """
    # Verify organization exists
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise NotFoundError("Organization", str(org_id))

    # Find the user by email
    result = await db.execute(
        select(User).where(User.email == user_email.lower())
    )
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", user_email)

    # Check if user is already a member
    result = await db.execute(
        select(OrganizationUser).where(
            and_(
                OrganizationUser.organization_id == org_id,
                OrganizationUser.user_id == user.id,
            )
        )
    )
    existing_membership = result.scalar_one_or_none()

    if existing_membership:
        raise ValidationException("User is already a member of this organization")

    # Validate role
    try:
        member_role = OrganizationRole(role.lower())
    except ValueError:
        raise ValidationException(f"Invalid role: {role}")

    # Prevent creating owner through this endpoint
    if member_role == OrganizationRole.OWNER:
        raise ValidationException("Cannot create owner through direct addition. Transfer ownership instead.")

    # Create membership
    membership = OrganizationUser(
        organization_id=org_id,
        user_id=user.id,
        role=member_role,
        is_active=True,
        invited_by_user_id=current_user.id,
        joined_at=datetime.utcnow(),
    )

    db.add(membership)

    # Set as user's default organization if they don't have one
    if not user.default_organization_id:
        user.default_organization_id = org_id

    await db.commit()
    await db.refresh(membership)

    logger.info(
        f"Admin {current_user.email} added {user.email} directly to org {org.name} "
        f"with role {member_role.value}"
    )

    return OrganizationMemberResponse(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=membership.role.value,
        is_active=membership.is_active,
        joined_at=membership.joined_at,
    )
