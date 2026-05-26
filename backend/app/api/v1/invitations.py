"""
Public Invitation Endpoints.

This module handles public invitation operations (no authentication required).
Users can accept invitations via token link.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_user import OrganizationUser, OrganizationRole
from app.models.organization_invitation import OrganizationInvitation, InvitationStatus
from app.schemas.organization import (
    InvitationAcceptResponse,
)
from app.utils.exceptions import NotFoundError, ValidationException
from app.utils.security import hash_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations", tags=["Invitations"])


@router.get(
    "/{token}",
    summary="Get invitation details",
    description="Get invitation details by token (public endpoint)",
)
async def get_invitation_details(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get invitation details without accepting it.

    Used to display invitation info before user accepts.
    """
    # Find invitation by token
    result = await db.execute(
        select(OrganizationInvitation).where(OrganizationInvitation.token == token)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise NotFoundError("Invitation", token)

    # Check if expired
    if invitation.is_expired:
        raise ValidationException("This invitation has expired")

    if invitation.status != InvitationStatus.PENDING:
        raise ValidationException(f"This invitation is {invitation.status.value}")

    # Get organization details
    result = await db.execute(
        select(Organization).where(Organization.id == invitation.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise NotFoundError("Organization", str(invitation.organization_id))

    # Check if user already exists
    result = await db.execute(
        select(User).where(User.email == invitation.email.lower())
    )
    existing_user = result.scalar_one_or_none()

    return {
        "email": invitation.email,
        "organization_name": org.name,
        "organization_type": org.organization_type.value,
        "role": invitation.role.value,
        "expires_at": invitation.expires_at,
        "user_exists": existing_user is not None,
    }


@router.post(
    "/{token}/accept",
    response_model=InvitationAcceptResponse,
    summary="Accept organization invitation",
    description="Accept an invitation to join an organization (public endpoint)",
)
async def accept_invitation(
    token: str,
    full_name: Optional[str] = Body(None),
    password: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
) -> InvitationAcceptResponse:
    """
    Accept organization invitation.

    If user doesn't exist, they must provide full_name and password to create account.
    If user exists, they can accept directly (no credentials needed - link authentication).

    Args:
        token: Invitation token from email link
        full_name: Full name (required if new user)
        password: Password (required if new user)

    Returns:
        InvitationAcceptResponse with organization details
    """

    # Find invitation by token
    result = await db.execute(
        select(OrganizationInvitation).where(OrganizationInvitation.token == token)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise NotFoundError("Invitation", "Invalid invitation token")

    # Validate invitation
    if not invitation.can_be_accepted:
        if invitation.is_expired:
            raise ValidationException("This invitation has expired")
        elif invitation.is_revoked:
            raise ValidationException("This invitation has been revoked")
        elif invitation.is_accepted:
            raise ValidationException("This invitation has already been accepted")
        else:
            raise ValidationException("This invitation cannot be accepted")

    # Get organization
    result = await db.execute(
        select(Organization).where(Organization.id == invitation.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise NotFoundError("Organization", str(invitation.organization_id))

    # Check if organization is active
    if not org.is_active:
        raise ValidationException("This organization is not active")

    # Find or create user
    result = await db.execute(
        select(User).where(User.email == invitation.email.lower())
    )
    user = result.scalar_one_or_none()

    is_new_user = False

    if not user:
        # New user - require full_name and password
        if not full_name or not password:
            raise ValidationException(
                "Full name and password are required for new users"
            )

        # Validate password strength
        if len(password) < 8:
            raise ValidationException("Password must be at least 8 characters")
        if not any(c.isupper() for c in password):
            raise ValidationException("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in password):
            raise ValidationException("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValidationException("Password must contain at least one digit")

        # Create new user
        user = User(
            email=invitation.email.lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            is_active=True,
            is_verified=True,  # Email verified via invitation
            default_organization_id=invitation.organization_id,
        )
        db.add(user)
        await db.flush()  # Get user ID
        is_new_user = True

        logger.info(
            f"Created new user {user.email} via invitation to org {org.name}"
        )

    # Check if user is already a member
    result = await db.execute(
        select(OrganizationUser).where(
            and_(
                OrganizationUser.organization_id == invitation.organization_id,
                OrganizationUser.user_id == user.id,
            )
        )
    )
    existing_membership = result.scalar_one_or_none()

    if existing_membership:
        raise ValidationException("You are already a member of this organization")

    # Create organization membership
    membership = OrganizationUser(
        organization_id=invitation.organization_id,
        user_id=user.id,
        role=invitation.role,
        is_active=True,
        invited_by_user_id=invitation.invited_by_user_id,
        joined_at=datetime.now(timezone.utc),
    )
    db.add(membership)

    # If user doesn't have a default organization, set this one
    if not user.default_organization_id:
        user.default_organization_id = invitation.organization_id

    # Mark invitation as accepted
    invitation.accept(user.id)

    await db.commit()

    logger.info(
        f"User {user.email} accepted invitation to org {org.name} "
        f"as {invitation.role.value} (new_user={is_new_user})"
    )

    return InvitationAcceptResponse(
        organization_id=org.id,
        organization_name=org.name,
        role=invitation.role.value,
        message=f"Successfully joined {org.name}!",
        is_new_user=is_new_user,
    )
