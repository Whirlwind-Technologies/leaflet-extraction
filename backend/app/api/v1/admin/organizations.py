"""
Admin Organization Management Endpoints.

Superuser-only endpoints for managing organization-level platform settings,
including the platform AI provider leaflet extraction limit.

These endpoints are mounted at ``/api/v1/admin/organizations/``.
"""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_superuser, get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.platform_quota import (
    OrganizationPlatformSettingsResponse,
    OrganizationPlatformSettingsUpdate,
)
from app.utils.exceptions import AuthorizationError, NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response schema for GET /api/v1/admin/organizations/
# ---------------------------------------------------------------------------


class OrganizationListItem(BaseModel):
    """Schema for an organization in the admin list view."""

    id: str = Field(..., description="Organization UUID.")
    name: str = Field(..., description="Organization display name.")
    slug: str = Field(..., description="URL-safe organization slug.")
    status: str = Field(..., description="Organization status (e.g. ACTIVE, PENDING_APPROVAL).")
    platform_leaflet_limit: int = Field(
        ...,
        ge=0,
        description="Maximum platform extractions allowed (0 = unlimited).",
    )
    platform_leaflets_used: int = Field(
        ...,
        ge=0,
        description="Number of platform extractions consumed so far.",
    )
    created_at: str = Field(..., description="ISO 8601 creation timestamp.")

    model_config = ConfigDict(from_attributes=True)


class PaginatedOrganizationList(BaseModel):
    """Paginated response for the organization list endpoint."""

    items: List[OrganizationListItem] = Field(..., description="List of organizations.")
    total: int = Field(..., ge=0, description="Total number of matching organizations.")
    page: int = Field(..., ge=1, description="Current page number.")
    page_size: int = Field(..., ge=1, description="Number of items per page.")


@router.get(
    "/",
    response_model=PaginatedOrganizationList,
    summary="List all organizations with platform quota info",
    description=(
        "Returns a paginated list of organizations with their platform extraction "
        "limits and usage counts. Superuser only."
    ),
)
async def list_organizations(
    page: int = Query(1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)."),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> PaginatedOrganizationList:
    """List all organizations with platform quota information.

    Args:
        page: Page number (1-indexed).
        page_size: Number of items per page (1-100, default 50).
        current_user: Authenticated superuser from dependency injection.
        db: Async database session.

    Returns:
        Paginated list of organizations with id, name, slug, status,
        and quota fields.
    """
    # Count total organizations
    count_result = await db.execute(select(func.count(Organization.id)))
    total = count_result.scalar_one()

    # Fetch paginated results
    result = await db.execute(
        select(Organization)
        .order_by(Organization.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    orgs = result.scalars().all()

    items = [
        OrganizationListItem(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            status=org.status.value if hasattr(org.status, "value") else str(org.status),
            platform_leaflet_limit=org.platform_leaflet_limit,
            platform_leaflets_used=org.platform_leaflets_used,
            created_at=org.created_at.isoformat(),
        )
        for org in orgs
    ]

    return PaginatedOrganizationList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/{org_id}",
    response_model=OrganizationPlatformSettingsResponse,
    summary="Update organization platform settings",
    description=(
        "Update an organization's platform settings such as the platform AI "
        "provider leaflet extraction limit. Superuser only."
    ),
)
async def update_organization_platform_settings(
    org_id: UUID,
    data: OrganizationPlatformSettingsUpdate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> OrganizationPlatformSettingsResponse:
    """Update organization platform settings.

    Allows superusers to adjust the platform AI provider leaflet limit
    for a specific organization. Setting the limit to 0 grants the
    organization unlimited platform extractions.

    Args:
        org_id: UUID of the organization to update.
        data: Request body with the new platform settings.
        current_user: Authenticated superuser from dependency injection.
        db: Async database session.

    Returns:
        OrganizationPlatformSettingsResponse with updated values and
        a confirmation message.

    Raises:
        NotFoundError: If the organization does not exist.
        AuthorizationError: If the caller is not a superuser (handled by dep).
    """
    # Find the organization
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise NotFoundError("Organization", str(org_id))

    # Apply updates
    if data.platform_leaflet_limit is not None:
        old_limit = org.platform_leaflet_limit
        org.platform_leaflet_limit = data.platform_leaflet_limit
        logger.info(
            f"Superuser {current_user.email} updated platform_leaflet_limit for "
            f"org '{org.name}' (id={org_id}): {old_limit} -> {data.platform_leaflet_limit}"
        )

    await db.commit()
    await db.refresh(org)

    # Build confirmation message
    message = (
        f"Platform limit updated to {org.platform_leaflet_limit}"
        f" ({'unlimited' if org.platform_leaflet_limit == 0 else f'{org.platform_leaflet_limit} extractions'})"
    )

    return OrganizationPlatformSettingsResponse(
        id=str(org.id),
        name=org.name,
        platform_leaflet_limit=org.platform_leaflet_limit,
        platform_leaflets_used=org.platform_leaflets_used,
        message=message,
    )
