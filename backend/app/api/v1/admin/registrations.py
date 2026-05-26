"""
Admin Registration Approval Endpoints
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_superuser, get_db
from app.config import settings
from app.models.organization import Organization, OrganizationStatus, OrganizationType
from app.models.organization_user import OrganizationUser
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/",
    summary="List pending registrations",
    description="Get all pending business registrations (superuser only)",
)
async def list_pending_registrations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all pending business registrations."""
    
    # Build query
    query = select(Organization).where(
        Organization.organization_type == OrganizationType.BUSINESS
    )
    
    # Filter by status
    if status_filter:
        try:
            status_enum = OrganizationStatus(status_filter)
            query = query.where(Organization.status == status_enum)
        except ValueError:
            pass
    # If no status filter provided, show all statuses
    
    query = query.order_by(Organization.created_at.desc())
    
    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    organizations = result.scalars().all()
    
    # Get requested_by user info for each
    registrations = []
    for org in organizations:
        # Get requesting user
        user_result = await db.execute(
            select(User).where(User.id == org.requested_by_user_id)
        )
        requesting_user = user_result.scalar_one_or_none()
        
        registrations.append({
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "status": org.status.value,
            "business_email": org.business_email,
            "business_phone": org.business_phone,
            "requested_by": {
                "id": str(requesting_user.id) if requesting_user else None,
                "email": requesting_user.email if requesting_user else None,
                "full_name": requesting_user.full_name if requesting_user else None,
            } if requesting_user else None,
            "created_at": org.created_at.isoformat(),
            "approved_at": org.approved_at.isoformat() if org.approved_at else None,
        })
    
    pages = (total + page_size - 1) // page_size
    
    return {
        "items": registrations,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1,
    }


@router.post(
    "/{registration_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Approve registration",
    description="Approve a pending business registration (superuser only)",
)
async def approve_registration(
    registration_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Approve a pending business registration."""

    # Get organization
    result = await db.execute(
        select(Organization).where(Organization.id == registration_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise NotFoundError("Organization", "id", str(registration_id))

    # Allow approving both PENDING_APPROVAL and SUSPENDED (previously rejected) organizations
    if organization.status not in [OrganizationStatus.PENDING_APPROVAL, OrganizationStatus.SUSPENDED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization cannot be approved (current status: {organization.status.value})"
        )

    # Update organization status
    organization.status = OrganizationStatus.ACTIVE
    organization.approved_by_user_id = current_user.id
    organization.approved_at = datetime.now(timezone.utc)
    organization.rejection_reason = None  # Clear rejection reason if it was previously rejected
    
    # Activate the organization owner's user account
    result = await db.execute(
        select(User).where(User.id == organization.requested_by_user_id)
    )
    owner_user = result.scalar_one_or_none()
    
    if owner_user:
        owner_user.is_active = True
        owner_user.is_verified = True
    
    # Activate organization membership
    result = await db.execute(
        select(OrganizationUser).where(
            OrganizationUser.organization_id == organization.id,
            OrganizationUser.user_id == organization.requested_by_user_id
        )
    )
    membership = result.scalar_one_or_none()
    
    if membership:
        membership.is_active = True
    
    await db.commit()
    await db.refresh(organization)

    logger.info(f"Organization approved: {organization.name} by admin: {current_user.email}")

    # Send approval email to owner
    if owner_user:
        try:
            from app.services.email_service import email_service
            await email_service.send_registration_approved(
                organization, owner_user, current_user
            )
            logger.info(f"Sent approval email to {owner_user.email}")
        except Exception as e:
            # Log error but don't fail the approval
            logger.error(f"Failed to send approval email: {e}", exc_info=True)

    return {
        "success": True,
        "message": "Organization approved successfully",
        "organization_id": str(organization.id),
        "status": organization.status.value,
    }


from pydantic import BaseModel

class RejectRequest(BaseModel):
    rejection_reason: Optional[str] = None

@router.post(
    "/{registration_id}/reject",
    status_code=status.HTTP_200_OK,
    summary="Reject registration",
    description="Reject a pending business registration (superuser only)",
)
async def reject_registration(
    registration_id: UUID,
    reject_data: RejectRequest = None,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reject a pending business registration."""

    # Get organization
    result = await db.execute(
        select(Organization).where(Organization.id == registration_id)
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise NotFoundError("Organization", "id", str(registration_id))

    if organization.status != OrganizationStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization is not pending approval (current status: {organization.status.value})"
        )

    # Update organization status
    organization.status = OrganizationStatus.SUSPENDED
    rejection_reason = reject_data.rejection_reason if reject_data else "No reason provided"
    organization.rejection_reason = rejection_reason

    # Get the owner user for email notification
    result = await db.execute(
        select(User).where(User.id == organization.requested_by_user_id)
    )
    owner_user = result.scalar_one_or_none()

    await db.commit()

    logger.info(f"Organization rejected: {organization.name} by admin: {current_user.email}")

    # Send rejection email to owner
    if owner_user:
        try:
            from app.services.email_service import email_service
            await email_service.send_registration_rejected(
                organization, owner_user, rejection_reason
            )
            logger.info(f"Sent rejection email to {owner_user.email}")
        except Exception as e:
            # Log error but don't fail the rejection
            logger.error(f"Failed to send rejection email: {e}", exc_info=True)

    return {
        "success": True,
        "message": "Organization rejected",
        "organization_id": str(organization.id),
        "status": organization.status.value,
    }


@router.post(
    "/{registration_id}/suspend",
    status_code=status.HTTP_200_OK,
    summary="Suspend organization",
    description="Suspend an approved organization and deactivate users (superuser only)",
)
async def suspend_organization(
    registration_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Suspend an approved organization."""

    # Get organization
    result = await db.execute(
        select(Organization).where(Organization.id == registration_id)
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise NotFoundError("Organization", "id", str(registration_id))

    if organization.status != OrganizationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization is not active (current status: {organization.status.value})"
        )

    # Update organization status
    organization.status = OrganizationStatus.SUSPENDED

    # Deactivate all users in the organization
    result = await db.execute(
        select(OrganizationUser).where(
            OrganizationUser.organization_id == organization.id,
            OrganizationUser.is_active == True
        )
    )
    memberships = result.scalars().all()

    user_ids = [m.user_id for m in memberships]
    if user_ids:
        result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = result.scalars().all()

        for user in users:
            user.is_active = False

    # Deactivate memberships
    for membership in memberships:
        membership.is_active = False

    await db.commit()

    logger.info(f"Organization suspended: {organization.name} by admin: {current_user.email}. Deactivated {len(user_ids)} users.")

    # Notify the organization owner that their account has been suspended.
    # Best-effort — a failure here must not roll back the suspension.
    try:
        owner_result = await db.execute(
            select(User).where(User.id == organization.requested_by_user_id)
        )
        owner_user = owner_result.scalar_one_or_none()
        if owner_user:
            from app.services.email_service import email_service

            subject = f"Your organization has been suspended: {organization.name}"
            html_body = (
                f"<p>Hello {owner_user.full_name or owner_user.email},</p>"
                f"<p>Your organization <b>{organization.name}</b> has been "
                f"suspended by a platform administrator. While suspended, "
                f"members cannot sign in or use the platform.</p>"
                f"<p>If you believe this is an error, please contact support.</p>"
            )
            await email_service._send_email(
                to_email=owner_user.email,
                to_name=owner_user.full_name,
                subject=subject,
                html_body=html_body,
            )
    except Exception as e:
        logger.error(
            f"Failed to send suspension email for organization {organization.id}: {e}"
        )

    # Notify super admins about the suspension (best-effort — failures
    # here must not affect the suspension outcome).
    try:
        from app.services.email_service import email_service

        super_admin_result = await db.execute(
            select(User).where(User.is_superuser == True)  # noqa: E712
        )
        super_admins = list(super_admin_result.scalars().all())

        for admin in super_admins:
            # Skip the admin who performed the suspension — they already know.
            if admin.id == current_user.id:
                continue
            try:
                subject = f"Organization Suspended: {organization.name}"
                html_body = (
                    f"<p>Hello {admin.full_name or admin.email},</p>"
                    f"<p>The organization <b>{organization.name}</b> has been "
                    f"suspended by {current_user.full_name or current_user.email}.</p>"
                    f"<p>{len(user_ids)} user(s) have been deactivated.</p>"
                    f"<p>View details in the "
                    f"<a href=\"{settings.frontend_url}/admin/users\">admin panel</a>.</p>"
                )
                await email_service._send_email(
                    to_email=admin.email,
                    to_name=admin.full_name,
                    subject=subject,
                    html_body=html_body,
                )
            except Exception as e:
                logger.error(
                    f"Failed to send suspension notification to admin {admin.email}: {e}"
                )
    except Exception as e:
        logger.error(
            f"Failed to send suspension admin notifications for organization {organization.id}: {e}"
        )

    return {
        "success": True,
        "message": "Organization suspended successfully",
        "organization_id": str(organization.id),
        "status": organization.status.value,
        "deactivated_users": len(user_ids),
    }


@router.delete(
    "/{registration_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete organization permanently",
    description="Permanently delete an organization and all associated data (superuser only)",
)
async def delete_organization(
    registration_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Permanently delete an organization and all associated data.

    WARNING: This action is irreversible and will delete:
    - The organization record
    - All organization memberships
    - All users belonging only to this organization
    - All leaflets uploaded by the organization
    - All products extracted from those leaflets
    - All API keys for the organization
    - All webhooks for the organization

    Args:
        registration_id: Organization UUID
        current_user: Super user performing the deletion
        db: Database session

    Returns:
        Success message with deletion summary
    """
    from app.models.leaflet import Leaflet
    from app.models.product import Product
    from app.models.api_key import APIKey

    # Get organization
    result = await db.execute(
        select(Organization).where(Organization.id == registration_id)
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise NotFoundError("Organization", "id", str(registration_id))

    org_name = organization.name

    # Count what will be deleted
    leaflets_result = await db.execute(
        select(func.count(Leaflet.id)).where(Leaflet.organization_id == organization.id)
    )
    leaflet_count = leaflets_result.scalar() or 0

    products_result = await db.execute(
        select(func.count(Product.id)).where(Product.organization_id == organization.id)
    )
    product_count = products_result.scalar() or 0

    memberships_result = await db.execute(
        select(OrganizationUser).where(OrganizationUser.organization_id == organization.id)
    )
    memberships = memberships_result.scalars().all()
    user_ids = [m.user_id for m in memberships]

    # Delete organization (CASCADE will handle related records)
    # This will automatically delete:
    # - organization_users (CASCADE)
    # - leaflets (CASCADE)
    # - products (CASCADE via leaflet)
    # - api_keys (CASCADE)
    # - webhooks (CASCADE)
    await db.delete(organization)

    # Delete users who belonged only to this organization
    deleted_users = 0
    if user_ids:
        from sqlalchemy import text, delete as sql_delete

        for user_id in user_ids:
            # Check if user has other organization memberships
            other_orgs_result = await db.execute(
                select(func.count(OrganizationUser.id)).where(
                    OrganizationUser.user_id == user_id,
                    OrganizationUser.organization_id != organization.id
                )
            )
            other_org_count = other_orgs_result.scalar() or 0

            # Only delete user if they have no other organizations
            if other_org_count == 0:
                # Check if user is superuser (never delete superusers)
                is_superuser_result = await db.execute(
                    select(User.is_superuser).where(User.id == user_id)
                )
                is_superuser = is_superuser_result.scalar()

                if not is_superuser:
                    # Use raw DELETE to avoid loading user relationships
                    await db.execute(
                        sql_delete(User).where(User.id == user_id)
                    )
                    deleted_users += 1

    await db.commit()

    logger.warning(
        f"Organization DELETED: {org_name} by admin: {current_user.email}. "
        f"Deleted: {leaflet_count} leaflets, {product_count} products, {deleted_users} users."
    )

    return {
        "success": True,
        "message": "Organization deleted permanently",
        "organization_name": org_name,
        "deleted_leaflets": leaflet_count,
        "deleted_products": product_count,
        "deleted_users": deleted_users,
    }
