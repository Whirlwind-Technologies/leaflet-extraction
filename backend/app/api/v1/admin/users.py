"""
Admin User Management and System Statistics Endpoints.

This module provides administrative endpoints for user management,
system statistics, deletion request handling, and user approval/rejection.

Example Usage:
    POST /api/v1/admin/users/{user_id}/approve  - Approve a pending user
    POST /api/v1/admin/users/{user_id}/reject   - Reject a pending user
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_superuser, get_db
from app.models.user import User
from app.models.leaflet import Leaflet, LeafletStatus
from app.models.product import Product
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_user import OrganizationUser
from app.models.deletion_request import DeletionRequest, DeletionRequestStatus
from app.schemas.organization import (
    DeletionRequestResponse,
    DeletionRequestReview,
)
from app.utils.security import get_password_hash
from app.utils.exceptions import NotFoundError, ValidationException
from app.services.email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Schemas ---

class UserCreate(BaseModel):
    """Schema for creating a user."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8)
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    """Schema for resetting a user's password via admin endpoint."""
    new_password: str = Field(..., min_length=8)


class UserRejectRequest(BaseModel):
    """Schema for rejecting a user registration."""
    rejection_reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Reason for rejecting the registration",
    )


class OrganizationInfo(BaseModel):
    """Simple organization info for user response."""
    id: UUID
    name: str
    slug: str


class UserResponse(BaseModel):
    """Schema for user response."""
    id: UUID
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    is_verified: bool
    last_login: Optional[datetime]
    created_at: datetime

    # Organization memberships
    organizations: List[OrganizationInfo] = []

    # Stats
    leaflet_count: int = 0
    product_count: int = 0
    total_cost: float = 0.0

    class Config:
        from_attributes = True


class SystemStats(BaseModel):
    """System-wide statistics."""
    total_users: int
    active_users: int
    total_leaflets: int
    total_products: int
    total_cost: float
    leaflets_today: int
    leaflets_this_week: int
    leaflets_this_month: int
    avg_products_per_leaflet: float
    processing_success_rate: float


# --- User Management Endpoints ---

@router.get(
    "/organizations",
    response_model=List[OrganizationInfo],
    summary="List all organizations",
    description="Get a list of all organizations for filtering (admin only).",
)
async def list_all_organizations(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> List[OrganizationInfo]:
    """List all organizations for admin filtering."""
    result = await db.execute(
        select(Organization).order_by(Organization.name)
    )
    orgs = result.scalars().all()
    return [
        OrganizationInfo(id=org.id, name=org.name, slug=org.slug)
        for org in orgs
    ]


@router.get(
    "",
    response_model=List[UserResponse],
    summary="List all users",
    description="Get a list of all users (admin only).",
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by email or name"),
    is_active: Optional[bool] = Query(None),
    is_superuser: Optional[bool] = Query(None, description="Filter by role (superuser)"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> List[UserResponse]:
    """List all users with optional filtering."""
    query = select(User)

    if search:
        query = query.where(
            User.email.ilike(f"%{search}%") |
            User.full_name.ilike(f"%{search}%")
        )

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    if is_superuser is not None:
        query = query.where(User.is_superuser == is_superuser)

    # Filter by organization membership
    if organization_id is not None:
        query = query.where(
            User.id.in_(
                select(OrganizationUser.user_id).where(
                    OrganizationUser.organization_id == organization_id
                )
            )
        )

    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    # Get stats for each user (across all their organizations)
    responses = []
    for user in users:
        # Get user's organizations with full info
        org_memberships_result = await db.execute(
            select(Organization).join(
                OrganizationUser, Organization.id == OrganizationUser.organization_id
            ).where(
                OrganizationUser.user_id == user.id
            )
        )
        user_orgs = org_memberships_result.scalars().all()
        user_org_ids = [org.id for org in user_orgs]

        # Build organization info list
        org_infos = [
            OrganizationInfo(id=org.id, name=org.name, slug=org.slug)
            for org in user_orgs
        ]

        # Leaflet count (across user's orgs)
        if user_org_ids:
            leaflet_result = await db.execute(
                select(func.count(Leaflet.id)).where(
                    Leaflet.organization_id.in_(user_org_ids)
                )
            )
            leaflet_count = leaflet_result.scalar() or 0

            # Product count
            product_result = await db.execute(
                select(func.count(Product.id)).where(
                    Product.organization_id.in_(user_org_ids)
                )
            )
            product_count = product_result.scalar() or 0

            # Total cost from leaflets processing_cost
            cost_result = await db.execute(
                select(func.sum(Leaflet.processing_cost)).where(
                    Leaflet.organization_id.in_(user_org_ids)
                )
            )
            total_cost = cost_result.scalar() or 0.0
        else:
            leaflet_count = 0
            product_count = 0
            total_cost = 0.0

        responses.append(UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            is_verified=user.is_verified,
            last_login=user.last_login,
            created_at=user.created_at,
            organizations=org_infos,
            leaflet_count=leaflet_count,
            product_count=product_count,
            total_cost=float(total_cost or 0),
        ))

    return responses


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
    description="Create a new user (admin only).",
)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user."""
    # Check if email exists
    existing = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing.scalar_one_or_none():
        raise ValidationException([{"field": "email", "message": "User with this email already exists"}])

    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        is_active=user_data.is_active,
        is_superuser=user_data.is_superuser,
        is_verified=user_data.is_verified,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"Admin {current_user.email} created user {user.email}")

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        last_login=user.last_login,
        created_at=user.created_at,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user details",
    description="Get details for a specific user (admin only).",
)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get user details."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", str(user_id))

    # Get user's organizations with full info
    org_memberships_result = await db.execute(
        select(Organization).join(
            OrganizationUser, Organization.id == OrganizationUser.organization_id
        ).where(
            OrganizationUser.user_id == user.id
        )
    )
    user_orgs = org_memberships_result.scalars().all()
    user_org_ids = [org.id for org in user_orgs]

    # Build organization info list
    org_infos = [
        OrganizationInfo(id=org.id, name=org.name, slug=org.slug)
        for org in user_orgs
    ]

    if user_org_ids:
        leaflet_result = await db.execute(
            select(func.count(Leaflet.id)).where(
                Leaflet.organization_id.in_(user_org_ids)
            )
        )
        leaflet_count = leaflet_result.scalar() or 0

        product_result = await db.execute(
            select(func.count(Product.id)).where(
                Product.organization_id.in_(user_org_ids)
            )
        )
        product_count = product_result.scalar() or 0

        # Use Leaflet.processing_cost to match the user list endpoint
        cost_result = await db.execute(
            select(func.sum(Leaflet.processing_cost)).where(
                Leaflet.organization_id.in_(user_org_ids)
            )
        )
        total_cost = cost_result.scalar() or 0.0
    else:
        leaflet_count = 0
        product_count = 0
        total_cost = 0.0

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        last_login=user.last_login,
        created_at=user.created_at,
        organizations=org_infos,
        leaflet_count=leaflet_count,
        product_count=product_count,
        total_cost=float(total_cost or 0),
    )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Update a user's details (admin only).",
)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update user details."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", str(user_id))

    # Update fields
    if user_data.email is not None:
        existing = await db.execute(
            select(User).where(
                and_(User.email == user_data.email, User.id != user_id)
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationException([{"field": "email", "message": "Email already in use"}])
        user.email = user_data.email

    if user_data.password is not None:
        user.hashed_password = get_password_hash(user_data.password)

    if user_data.full_name is not None:
        user.full_name = user_data.full_name

    if user_data.is_active is not None:
        user.is_active = user_data.is_active

    if user_data.is_superuser is not None:
        user.is_superuser = user_data.is_superuser

    if user_data.is_verified is not None:
        user.is_verified = user_data.is_verified

    await db.commit()
    await db.refresh(user)

    logger.info(f"Admin {current_user.email} updated user {user.email}")

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        last_login=user.last_login,
        created_at=user.created_at,
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Delete a user (admin only).",
)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", str(user_id))

    if user.id == current_user.id:
        raise ValidationException([{"field": "user_id", "message": "Cannot delete yourself"}])

    if user.is_superuser:
        raise ValidationException([{"field": "user_id", "message": "Cannot delete a superuser account. Revoke superuser status first."}])

    email = user.email
    await db.delete(user)
    await db.commit()

    logger.info(f"Admin {current_user.email} deleted user {email}")


@router.post(
    "/{user_id}/reset-password",
    summary="Reset user password",
    description="Reset a user's password (admin only).",
)
async def reset_user_password(
    user_id: UUID,
    body: ResetPasswordRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", str(user_id))

    user.hashed_password = get_password_hash(body.new_password)
    await db.commit()

    logger.info(f"Admin {current_user.email} reset password for {user.email}")

    return {"message": "Password reset successfully"}


@router.post(
    "/{user_id}/toggle-active",
    summary="Toggle user active status",
    description="Enable or disable a user account (admin only).",
)
async def toggle_user_active(
    user_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Toggle user active status."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", str(user_id))

    if user.id == current_user.id:
        raise ValidationException([{"field": "user_id", "message": "Cannot deactivate yourself"}])

    user.is_active = not user.is_active
    await db.commit()

    status_str = "activated" if user.is_active else "deactivated"
    logger.info(f"Admin {current_user.email} {status_str} user {user.email}")

    return {
        "message": f"User {status_str} successfully",
        "is_active": user.is_active,
    }


@router.post(
    "/{user_id}/approve",
    summary="Approve a pending user registration",
    description=(
        "Approve a user whose account is pending admin approval. "
        "Sets the user as active and verified, and sends an approval email."
    ),
)
async def approve_user(
    user_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Approve a pending user registration.

    Activates the user account, marks it as verified, and dispatches
    an approval notification email. For business users, also activates
    the organization and the user's membership.

    Args:
        user_id: UUID of the user to approve.
        current_user: Authenticated superuser performing the approval.
        db: Async database session.

    Returns:
        Success message with updated user status.

    Raises:
        NotFoundError: If user does not exist.
        ValidationException: If user is already active.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", str(user_id))

    # Prevent self-approval
    if user.id == current_user.id:
        raise ValidationException([{"field": "user_id", "message": "Cannot approve your own account"}])

    # Idempotency guard: prevent duplicate approvals (and duplicate emails)
    if user.is_active and user.is_verified:
        raise ValidationException([{"field": "user", "message": "User is already approved and active"}])

    # Activate user
    user.is_active = True
    user.is_verified = True

    # If the user has an organization, activate it and the membership too
    organization = None
    if user.default_organization_id:
        org_result = await db.execute(
            select(Organization).where(Organization.id == user.default_organization_id)
        )
        organization = org_result.scalar_one_or_none()

        if organization and organization.status == OrganizationStatus.PENDING_APPROVAL:
            organization.status = OrganizationStatus.ACTIVE
            organization.approved_by_user_id = current_user.id
            organization.approved_at = datetime.now(timezone.utc)

        # Activate user's membership in the organization
        membership_result = await db.execute(
            select(OrganizationUser).where(
                OrganizationUser.user_id == user.id,
                OrganizationUser.organization_id == user.default_organization_id,
            )
        )
        membership = membership_result.scalar_one_or_none()
        if membership and not membership.is_active:
            membership.is_active = True

    await db.commit()
    await db.refresh(user)

    logger.info(
        f"Admin {current_user.email} approved user {user.email} (id={user_id})"
    )

    # Send approval email to the user (fire-and-forget)
    if organization:
        try:
            await email_service.send_registration_approved(
                organization=organization,
                owner=user,
                approved_by=current_user,
            )
        except Exception as exc:
            logger.error(
                f"Failed to send approval email to {user.email}: {exc}",
                exc_info=True,
            )

    return {
        "message": f"User {user.email} has been approved and activated",
        "user_id": str(user.id),
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


@router.post(
    "/{user_id}/reject",
    summary="Reject a pending user registration",
    description=(
        "Reject a user whose account is pending admin approval. "
        "The user record is kept for audit purposes but remains inactive. "
        "A rejection email is sent with an optional reason."
    ),
)
async def reject_user(
    user_id: UUID,
    reject_data: UserRejectRequest = None,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reject a pending user registration.

    Keeps the user record inactive for audit purposes and optionally
    stores the rejection reason on the organization. Sends a rejection
    notification email to the user.

    Args:
        user_id: UUID of the user to reject.
        reject_data: Optional body with rejection_reason.
        current_user: Authenticated superuser performing the rejection.
        db: Async database session.

    Returns:
        Success message confirming rejection.

    Raises:
        NotFoundError: If user does not exist.
        ValidationException: If user is already active (approve first, then deactivate).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", str(user_id))

    # Prevent rejecting superuser accounts to avoid locking out administration
    if user.is_superuser:
        raise ValidationException([{"field": "user", "message": "Cannot reject a superuser account"}])

    if user.is_active:
        raise ValidationException([{"field": "user", "message": "Cannot reject an active user. Use the deactivate endpoint instead."}])

    rejection_reason = (
        reject_data.rejection_reason
        if reject_data and reject_data.rejection_reason
        else "Your registration was not approved."
    )

    # Mark the organization as suspended with rejection reason
    organization = None
    if user.default_organization_id:
        org_result = await db.execute(
            select(Organization).where(Organization.id == user.default_organization_id)
        )
        organization = org_result.scalar_one_or_none()

        if organization:
            organization.status = OrganizationStatus.SUSPENDED
            organization.rejection_reason = rejection_reason

    await db.commit()

    logger.info(
        f"Admin {current_user.email} rejected user {user.email} "
        f"(id={user_id}): {rejection_reason}"
    )

    # Send rejection email to the user (fire-and-forget)
    if organization:
        try:
            await email_service.send_registration_rejected(
                organization=organization,
                owner=user,
                rejection_reason=rejection_reason,
            )
        except Exception as exc:
            logger.error(
                f"Failed to send rejection email to {user.email}: {exc}",
                exc_info=True,
            )

    return {
        "message": f"User {user.email} registration has been rejected",
        "user_id": str(user.id),
        "rejection_reason": rejection_reason,
    }
