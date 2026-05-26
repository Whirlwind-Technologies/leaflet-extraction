"""
Users API Endpoints.

This module provides endpoints for user management including
profile updates and API key management.

Example Usage:
    GET /api/v1/users/me - Get current user profile
    PUT /api/v1/users/me - Update profile
    POST /api/v1/users/me/api-keys - Create API key
"""

import logging
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_superuser, get_current_organization, get_db
from app.models.user import User
from app.models.api_key import APIKey
from app.models.organization import Organization
from app.models.leaflet import Leaflet, LeafletStatus
from app.models.product import Product, ReviewStatus
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.user import (
    APIKeyCreate,
    APIKeyCreated,
    APIKeyResponse,
    UserResponse,
    UserUpdate,
)
from app.utils.exceptions import NotFoundError
from app.utils.security import generate_api_key, hash_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the currently authenticated user's profile.",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user's profile.
    
    Args:
        current_user: Currently authenticated user
        
    Returns:
        User profile
    """
    return current_user


@router.get(
    "/me/stats",
    summary="Get current user stats",
    description="Returns leaflet/product counts for the current user's organization.",
)
async def get_current_user_stats(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get aggregate stats for the current user's organization.

    Returns:
        Dict with total_leaflets, total_products, completed_leaflets,
        pending_reviews — scoped to the user's current organization.
    """
    leaflet_query = select(
        func.count(Leaflet.id),
        func.count(case((Leaflet.status == LeafletStatus.COMPLETED, 1))),
    ).where(Leaflet.organization_id == current_org.id)
    leaflet_result = await db.execute(leaflet_query)
    total_leaflets, completed_leaflets = leaflet_result.one()

    product_query = select(
        func.count(Product.id),
        func.count(
            case(
                (
                    Product.review_status.in_(
                        [ReviewStatus.PENDING, ReviewStatus.NEEDS_CORRECTION]
                    ),
                    1,
                )
            )
        ),
    ).where(Product.organization_id == current_org.id)
    product_result = await db.execute(product_query)
    total_products, pending_reviews = product_result.one()

    return {
        "total_leaflets": total_leaflets or 0,
        "completed_leaflets": completed_leaflets or 0,
        "total_products": total_products or 0,
        "pending_reviews": pending_reviews or 0,
    }


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update profile",
    description="Update the current user's profile information.",
)
async def update_current_user(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Update current user's profile.
    
    Args:
        update_data: Fields to update
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Updated user profile
    """
    # Update only provided fields
    update_dict = update_data.model_dump(exclude_unset=True)
    
    # Handle password separately
    if "password" in update_dict:
        from app.utils.security import hash_password
        current_user.hashed_password = hash_password(update_dict.pop("password"))
    
    # Update other fields
    for field, value in update_dict.items():
        setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    logger.info(f"User profile updated: {current_user.email}")
    
    return current_user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete account",
    description="Delete the current user's account.",
)
async def delete_current_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete current user's account.
    
    Args:
        current_user: Currently authenticated user
        db: Database session
    """
    email = current_user.email
    await db.delete(current_user)
    await db.commit()
    
    logger.info(f"User account deleted: {email}")


# API Key Management

@router.get(
    "/me/api-keys",
    response_model=List[APIKeyResponse],
    summary="List API keys",
    description="List all API keys for the current user.",
)
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[APIKey]:
    """
    List user's API keys.
    
    Args:
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        List of API keys (without actual key values)
    """
    result = await db.execute(
        select(APIKey)
        .where(APIKey.organization_id == current_org.id)
        .order_by(APIKey.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/me/api-keys",
    response_model=APIKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Create a new API key. The full key is only shown once.",
)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Create a new API key.
    
    The full API key is only returned once during creation.
    Store it securely as it cannot be retrieved later.
    
    Args:
        key_data: API key configuration
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Created API key with full key value
    """
    # Generate new key
    plain_key = generate_api_key()
    key_prefix = plain_key[:8]
    hashed_key = hash_api_key(plain_key)
    
    # Calculate expiration
    expires_at = None
    if key_data.expires_in_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)
    
    # Create API key record
    api_key = APIKey(
        key_hash=hashed_key,
        key_prefix=key_prefix,
        name=key_data.name,
        description=key_data.description,
        user_id=current_user.id,
        scopes=key_data.scopes,
        expires_at=expires_at,
    )
    
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    logger.info(f"API key created for user: {current_user.email}")
    
    # Return with full key (only time it's shown)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": plain_key,
        "key_prefix": key_prefix,
        "description": api_key.description,
        "scopes": api_key.scopes,
        "is_active": api_key.is_active,
        "last_used": api_key.last_used,
        "expires_at": api_key.expires_at,
        "created_at": api_key.created_at,
        "updated_at": api_key.updated_at,
    }


@router.delete(
    "/me/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete API key",
    description="Delete an API key.",
)
async def delete_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete an API key.
    
    Args:
        key_id: ID of the API key to delete
        current_user: Currently authenticated user
        db: Database session
        
    Raises:
        NotFoundError: If API key not found
    """
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.organization_id == current_org.id,
        )
    )
    api_key = result.scalar_one_or_none()
    
    if api_key is None:
        raise NotFoundError("API Key", str(key_id))
    
    await db.delete(api_key)
    await db.commit()
    
    logger.info(f"API key deleted: {key_id}")


# Admin endpoints (superuser only)

@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="List all users (admin)",
    description="List all users in the system. Requires superuser privileges.",
)
async def list_users(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List all users (admin only).
    
    Args:
        page: Page number
        page_size: Items per page
        current_user: Current superuser
        db: Database session
        
    Returns:
        Paginated list of users
    """
    # Get total count
    from sqlalchemy import func
    
    count_result = await db.execute(select(func.count(User.id)))
    total = count_result.scalar()
    
    # Get users
    offset = (page - 1) * page_size
    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    users = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    ).model_dump()


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID (admin)",
    description="Get a specific user by ID. Requires superuser privileges.",
)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get user by ID (admin only).
    
    Args:
        user_id: User ID
        current_user: Current superuser
        db: Database session
        
    Returns:
        User profile
        
    Raises:
        NotFoundError: If user not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise NotFoundError("User", str(user_id))
    
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user (admin)",
    description="Delete a user. Requires superuser privileges.",
)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete user by ID (admin only).
    
    Args:
        user_id: User ID to delete
        current_user: Current superuser
        db: Database session
        
    Raises:
        NotFoundError: If user not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise NotFoundError("User", str(user_id))
    
    # Prevent self-deletion
    if user.id == current_user.id:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account through this endpoint",
        )
    
    email = user.email
    await db.delete(user)
    await db.commit()
    
    logger.info(f"User deleted by admin: {email}")