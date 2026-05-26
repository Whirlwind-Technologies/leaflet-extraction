"""
Categories API Router.

Provides endpoints for managing system-wide product categories.
"""

import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_read, require_admin, get_db
from app.models.user import User
from app.models.product_category import ProductCategory
from app.core.categories import get_category_loader, reload_category_loader

logger = logging.getLogger(__name__)

router = APIRouter(tags=["categories"])


# ============================================================================
# Schemas
# ============================================================================

class CategoryResponse(BaseModel):
    """Category response schema."""
    id: UUID
    name: str
    description: Optional[str] = None
    is_fallback: bool
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    """Category list response."""
    categories: List[CategoryResponse]
    total: int
    returned: int
    has_more: bool


class CategoryCreate(BaseModel):
    """Schema for creating a category."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_fallback: bool = False
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_fallback: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "",
    response_model=CategoryListResponse,
    summary="List categories",
    description="Get all system-defined product categories.",
)
async def list_categories(
    search: Optional[str] = Query(None, description="Search by name or description"),
    include_inactive: bool = Query(False, description="Include inactive categories"),
    fallback_only: bool = Query(False, description="Return only fallback categories"),
    limit: int = Query(100, ge=1, le=500, description="Maximum categories to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_read),
) -> CategoryListResponse:
    """
    Get system-defined product categories.

    Categories are used for product classification during extraction and review.
    """
    # Build query
    query = select(ProductCategory)

    if not include_inactive:
        query = query.where(ProductCategory.is_active == True)

    if fallback_only:
        query = query.where(ProductCategory.is_fallback == True)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (ProductCategory.name.ilike(search_pattern)) |
            (ProductCategory.description.ilike(search_pattern))
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(ProductCategory.sort_order, ProductCategory.name)
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    categories = result.scalars().all()

    return CategoryListResponse(
        categories=[CategoryResponse.model_validate(c) for c in categories],
        total=total,
        returned=len(categories),
        has_more=offset + len(categories) < total,
    )


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Get category",
    description="Get a single category by ID.",
)
async def get_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_read),
) -> CategoryResponse:
    """Get a category by ID."""
    result = await db.execute(
        select(ProductCategory).where(ProductCategory.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    return CategoryResponse.model_validate(category)


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create category",
    description="Create a new product category (superuser only).",
)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> CategoryResponse:
    """Create a new category. Superuser only."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can create categories",
        )

    # Check for duplicate name
    existing = await db.execute(
        select(ProductCategory).where(ProductCategory.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category '{data.name}' already exists",
        )

    category = ProductCategory(
        name=data.name,
        description=data.description,
        is_fallback=data.is_fallback,
        sort_order=data.sort_order,
        is_active=True,
    )

    db.add(category)
    await db.commit()
    await db.refresh(category)

    # Reload the category loader cache
    reload_category_loader()

    logger.info(f"Category created: {category.name} by {current_user.email}")

    return CategoryResponse.model_validate(category)


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Update category",
    description="Update a product category (superuser only).",
)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> CategoryResponse:
    """Update a category. Superuser only."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can update categories",
        )

    result = await db.execute(
        select(ProductCategory).where(ProductCategory.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # Check for duplicate name if name is being changed
    if data.name and data.name != category.name:
        existing = await db.execute(
            select(ProductCategory).where(ProductCategory.name == data.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category '{data.name}' already exists",
            )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    await db.commit()
    await db.refresh(category)

    # Reload the category loader cache
    reload_category_loader()

    logger.info(f"Category updated: {category.name} by {current_user.email}")

    return CategoryResponse.model_validate(category)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete category",
    description="Soft-delete a product category (superuser only).",
)
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    """Soft-delete a category. Superuser only."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can delete categories",
        )

    result = await db.execute(
        select(ProductCategory).where(ProductCategory.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # Soft delete
    category.is_active = False
    await db.commit()

    # Reload the category loader cache
    reload_category_loader()

    logger.info(f"Category deleted: {category.name} by {current_user.email}")


@router.post(
    "/reload",
    summary="Reload category cache",
    description="Reload the category cache from database (superuser only).",
)
async def reload_categories(
    current_user: User = Depends(require_admin),
) -> dict:
    """Reload categories from database. Superuser only."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can reload categories",
        )

    count = reload_category_loader()

    logger.info(f"Categories reloaded by {current_user.email}: {count} categories")

    return {
        "success": True,
        "message": f"Reloaded {count} categories",
        "category_count": count,
    }
