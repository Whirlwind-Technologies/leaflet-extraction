"""
Retailer Management API Endpoints.

CRUD operations for organization retailers.
Requires authentication and organization membership.

Example Usage:
    # List retailers
    GET /api/v1/retailers?search=super

    # Create retailer
    POST /api/v1/retailers
    {
        "name": "SuperMart",
        "country": "US",
        "currency": "USD"
    }
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_current_organization,
    get_db,
)
from app.models.organization import Organization
from app.models.retailer import Retailer
from app.models.user import User
from app.schemas.retailer import (
    RetailerCreate,
    RetailerResponse,
    RetailerUpdate,
)
from app.utils.exceptions import NotFoundError, ValidationException

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Retailers"])


@router.get(
    "",
    response_model=List[RetailerResponse],
    summary="List retailers",
    description="Get all retailers for the current organization.",
)
async def list_retailers(
    search: Optional[str] = Query(
        default=None,
        description="Search by retailer name"
    ),
    is_active: Optional[bool] = Query(
        default=None,
        description="Filter by active status"
    ),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[RetailerResponse]:
    """
    List all retailers for the organization.

    Args:
        search: Optional search term for retailer name
        is_active: Optional filter by active status
        current_user: Authenticated user
        current_org: Current organization context
        db: Database session

    Returns:
        List of retailer response objects
    """
    query = select(Retailer).where(
        Retailer.organization_id == current_org.id
    )

    if search:
        query = query.where(
            Retailer.name.ilike(f"%{search}%")
        )

    if is_active is not None:
        query = query.where(Retailer.is_active == is_active)

    query = query.order_by(Retailer.name.asc())

    result = await db.execute(query)
    retailers = result.scalars().all()

    return [
        RetailerResponse(
            id=r.id,
            organization_id=r.organization_id,
            name=r.name,
            country=r.country,
            currency=r.currency,
            language=r.language,
            logo_url=r.logo_url,
            external_id=r.external_id,
            is_active=r.is_active,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in retailers
    ]


@router.post(
    "",
    response_model=RetailerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create retailer",
    description="Create a new retailer for the organization.",
)
async def create_retailer(
    data: RetailerCreate,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> RetailerResponse:
    """
    Create a new retailer.

    Args:
        data: Retailer creation data
        current_user: Authenticated user
        current_org: Current organization context
        db: Database session

    Returns:
        Created retailer response

    Raises:
        ValidationException: If retailer name already exists in org
    """
    # Check for duplicate name (case-insensitive) among active retailers only
    existing = await db.execute(
        select(Retailer).where(
            and_(
                Retailer.organization_id == current_org.id,
                func.lower(Retailer.name) == data.name.lower(),
                Retailer.is_active == True,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise ValidationException(
            errors=[{"field": "name", "message": f"Retailer '{data.name}' already exists"}],
            message=f"Retailer '{data.name}' already exists"
        )

    retailer = Retailer(
        organization_id=current_org.id,
        name=data.name.strip(),
        country=data.country,
        currency=data.currency,
        language=data.language,
        logo_url=data.logo_url,
        external_id=data.external_id,
        is_active=True,
    )

    db.add(retailer)
    await db.commit()
    await db.refresh(retailer)

    logger.info(
        f"User {current_user.email} created retailer '{data.name}' "
        f"in org {current_org.id}"
    )

    return RetailerResponse(
        id=retailer.id,
        organization_id=retailer.organization_id,
        name=retailer.name,
        country=retailer.country,
        currency=retailer.currency,
        language=retailer.language,
        logo_url=retailer.logo_url,
        external_id=retailer.external_id,
        is_active=retailer.is_active,
        created_at=retailer.created_at,
        updated_at=retailer.updated_at,
    )


@router.get(
    "/{retailer_id}",
    response_model=RetailerResponse,
    summary="Get retailer",
    description="Get a specific retailer by ID.",
)
async def get_retailer(
    retailer_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> RetailerResponse:
    """
    Get retailer details by ID.

    Args:
        retailer_id: UUID of the retailer
        current_user: Authenticated user
        current_org: Current organization context
        db: Database session

    Returns:
        Retailer response

    Raises:
        NotFoundError: If retailer not found
    """
    result = await db.execute(
        select(Retailer).where(
            and_(
                Retailer.id == retailer_id,
                Retailer.organization_id == current_org.id,
            )
        )
    )
    retailer = result.scalar_one_or_none()

    if not retailer:
        raise NotFoundError("Retailer", str(retailer_id))

    return RetailerResponse(
        id=retailer.id,
        organization_id=retailer.organization_id,
        name=retailer.name,
        country=retailer.country,
        currency=retailer.currency,
        language=retailer.language,
        logo_url=retailer.logo_url,
        external_id=retailer.external_id,
        is_active=retailer.is_active,
        created_at=retailer.created_at,
        updated_at=retailer.updated_at,
    )


@router.put(
    "/{retailer_id}",
    response_model=RetailerResponse,
    summary="Update retailer",
    description="Update retailer details.",
)
async def update_retailer(
    retailer_id: UUID,
    data: RetailerUpdate,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> RetailerResponse:
    """
    Update retailer details.

    Args:
        retailer_id: UUID of the retailer
        data: Update data
        current_user: Authenticated user
        current_org: Current organization context
        db: Database session

    Returns:
        Updated retailer response

    Raises:
        NotFoundError: If retailer not found
        ValidationException: If new name conflicts with existing retailer
    """
    result = await db.execute(
        select(Retailer).where(
            and_(
                Retailer.id == retailer_id,
                Retailer.organization_id == current_org.id,
            )
        )
    )
    retailer = result.scalar_one_or_none()

    if not retailer:
        raise NotFoundError("Retailer", str(retailer_id))

    # Check for duplicate name if name is being changed (among active retailers only)
    if data.name and data.name.lower() != retailer.name.lower():
        existing = await db.execute(
            select(Retailer).where(
                and_(
                    Retailer.organization_id == current_org.id,
                    func.lower(Retailer.name) == data.name.lower(),
                    Retailer.id != retailer_id,
                    Retailer.is_active == True,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationException(
                errors=[{"field": "name", "message": f"Retailer '{data.name}' already exists"}],
                message=f"Retailer '{data.name}' already exists"
            )

    # Update fields
    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None or field in ("logo_url", "external_id"):  # Allow clearing these fields
            setattr(retailer, field, value)

    await db.commit()
    await db.refresh(retailer)

    logger.info(
        f"User {current_user.email} updated retailer {retailer_id}"
    )

    return RetailerResponse(
        id=retailer.id,
        organization_id=retailer.organization_id,
        name=retailer.name,
        country=retailer.country,
        currency=retailer.currency,
        language=retailer.language,
        logo_url=retailer.logo_url,
        external_id=retailer.external_id,
        is_active=retailer.is_active,
        created_at=retailer.created_at,
        updated_at=retailer.updated_at,
    )


@router.delete(
    "/{retailer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete retailer",
    description="Delete a retailer (soft delete by default).",
)
async def delete_retailer(
    retailer_id: UUID,
    hard_delete: bool = Query(
        default=False,
        description="Hard delete instead of soft delete"
    ),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete retailer.

    By default, performs a soft delete (sets is_active=False).
    Use hard_delete=true to permanently remove the record.

    Args:
        retailer_id: UUID of the retailer
        hard_delete: Whether to permanently delete
        current_user: Authenticated user
        current_org: Current organization context
        db: Database session

    Raises:
        NotFoundError: If retailer not found
    """
    result = await db.execute(
        select(Retailer).where(
            and_(
                Retailer.id == retailer_id,
                Retailer.organization_id == current_org.id,
            )
        )
    )
    retailer = result.scalar_one_or_none()

    if not retailer:
        raise NotFoundError("Retailer", str(retailer_id))

    if hard_delete:
        await db.delete(retailer)
        logger.info(
            f"User {current_user.email} hard deleted retailer {retailer_id}"
        )
    else:
        retailer.is_active = False
        logger.info(
            f"User {current_user.email} soft deleted retailer {retailer_id}"
        )

    await db.commit()
