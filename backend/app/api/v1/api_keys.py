"""
API Keys Management Endpoints.

This module provides endpoints for managing API keys for
programmatic access to the platform.

Example Usage:
    POST /api/v1/api-keys - Create new API key
    GET /api/v1/api-keys - List API keys
    DELETE /api/v1/api-keys/{id} - Revoke API key
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_organization, get_db
from app.models.organization import Organization
from app.models.api_key import APIKey, APIKeyScope
from app.models.user import User
from app.utils.exceptions import NotFoundError, ValidationException

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Schemas ---

class APIKeyCreate(BaseModel):
    """Schema for creating an API key."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    scopes: List[str] = Field(default=["read"])
    rate_limit: int = Field(default=60, ge=1, le=1000)
    daily_limit: Optional[int] = Field(None, ge=1)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    allowed_ips: Optional[List[str]] = None


class APIKeyResponse(BaseModel):
    """Schema for API key response (without the actual key)."""
    id: UUID
    name: str
    description: Optional[str]
    key_prefix: str
    scopes: List[str]
    rate_limit: int
    daily_limit: Optional[int]
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    total_requests: int
    requests_today: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class APIKeyCreateResponse(BaseModel):
    """Schema for API key creation response (includes the key once)."""
    id: UUID
    name: str
    key: str  # Only returned on creation
    key_prefix: str
    scopes: List[str]
    rate_limit: int
    expires_at: Optional[datetime]
    message: str
    
    class Config:
        from_attributes = True


class APIKeyUsageStats(BaseModel):
    """API key usage statistics."""
    total_requests: int
    requests_today: int
    requests_this_week: int
    requests_this_month: int
    last_used_at: Optional[datetime]
    last_used_ip: Optional[str]
    avg_requests_per_day: float


# --- Endpoints ---

@router.post(
    "/",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Create a new API key for programmatic access.",
)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreateResponse:
    """
    Create a new API key.

    **Important**: The API key is only shown once. Save it securely.
    """
    # Validate scopes
    valid_scopes = {s.value for s in APIKeyScope}
    for scope in key_data.scopes:
        if scope not in valid_scopes:
            raise ValidationException(f"Invalid scope: {scope}")

    # Check key limit per organization (max 10)
    existing_count = await db.execute(
        select(APIKey).where(APIKey.organization_id == current_org.id)
    )
    if len(existing_count.scalars().all()) >= 10:
        raise ValidationException("Maximum number of API keys (10) reached for this organization")

    # Create the key
    api_key, raw_key = APIKey.create_key(
        user_id=current_user.id,
        organization_id=current_org.id,
        name=key_data.name,
        scopes=key_data.scopes,
        rate_limit=key_data.rate_limit,
        daily_limit=key_data.daily_limit,
        expires_in_days=key_data.expires_in_days,
        description=key_data.description,
        allowed_ips=key_data.allowed_ips,
    )
    
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    logger.info(f"User {current_user.email} created API key: {api_key.name} (prefix: {api_key.key_prefix})")
    logger.debug(f"API key hash: {api_key.key_hash[:16]}...")
    
    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        rate_limit=api_key.rate_limit,
        expires_at=api_key.expires_at,
        message="Save this key securely - it won't be shown again!",
    )


@router.get(
    "/",
    response_model=List[APIKeyResponse],
    summary="List API keys",
    description="List all API keys for the current user.",
)
async def list_api_keys(
    include_inactive: bool = Query(False, description="Include inactive keys"),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[APIKeyResponse]:
    """List all API keys for the current organization."""
    query = select(APIKey).where(APIKey.organization_id == current_org.id)
    
    if not include_inactive:
        query = query.where(APIKey.is_active == True)
    
    query = query.order_by(APIKey.created_at.desc())
    
    result = await db.execute(query)
    keys = result.scalars().all()
    
    return [
        APIKeyResponse(
            id=key.id,
            name=key.name,
            description=key.description,
            key_prefix=key.key_prefix,
            scopes=key.scopes,
            rate_limit=key.rate_limit,
            daily_limit=key.daily_limit,
            is_active=key.is_active,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            total_requests=key.total_requests,
            requests_today=key.requests_today,
            created_at=key.created_at,
        )
        for key in keys
    ]


@router.get(
    "/{key_id}",
    response_model=APIKeyResponse,
    summary="Get API key details",
    description="Get details for a specific API key.",
)
async def get_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    """Get API key details."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.organization_id == current_org.id,
        )
    )
    key = result.scalar_one_or_none()
    
    if not key:
        raise NotFoundError("API Key", str(key_id))
    
    return APIKeyResponse(
        id=key.id,
        name=key.name,
        description=key.description,
        key_prefix=key.key_prefix,
        scopes=key.scopes,
        rate_limit=key.rate_limit,
        daily_limit=key.daily_limit,
        is_active=key.is_active,
        expires_at=key.expires_at,
        last_used_at=key.last_used_at,
        total_requests=key.total_requests,
        requests_today=key.requests_today,
        created_at=key.created_at,
    )


@router.get(
    "/{key_id}/stats",
    response_model=APIKeyUsageStats,
    summary="Get API key usage stats",
    description="Get usage statistics for an API key.",
)
async def get_api_key_stats(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> APIKeyUsageStats:
    """Get API key usage statistics."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.organization_id == current_org.id,
        )
    )
    key = result.scalar_one_or_none()
    
    if not key:
        raise NotFoundError("API Key", str(key_id))
    
    # Calculate average requests per day
    if key.created_at:
        days_active = max((datetime.utcnow() - key.created_at).days, 1)
        avg_per_day = key.total_requests / days_active
    else:
        avg_per_day = 0
    
    return APIKeyUsageStats(
        total_requests=key.total_requests,
        requests_today=key.requests_today,
        requests_this_week=0,  # Would need additional tracking
        requests_this_month=0,  # Would need additional tracking
        last_used_at=key.last_used_at,
        last_used_ip=key.last_used_ip,
        avg_requests_per_day=round(avg_per_day, 2),
    )


@router.patch(
    "/{key_id}",
    response_model=APIKeyResponse,
    summary="Update API key",
    description="Update an API key's settings.",
)
async def update_api_key(
    key_id: UUID,
    name: Optional[str] = None,
    description: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    rate_limit: Optional[int] = Query(None, ge=1, le=1000),
    daily_limit: Optional[int] = Query(None, ge=1),
    allowed_ips: Optional[List[str]] = None,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    """Update API key settings."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.organization_id == current_org.id,
        )
    )
    key = result.scalar_one_or_none()
    
    if not key:
        raise NotFoundError("API Key", str(key_id))
    
    # Update fields
    if name is not None:
        key.name = name
    if description is not None:
        key.description = description
    if scopes is not None:
        valid_scopes = {s.value for s in APIKeyScope}
        for scope in scopes:
            if scope not in valid_scopes:
                raise ValidationException(f"Invalid scope: {scope}")
        key.scopes = scopes
    if rate_limit is not None:
        key.rate_limit = rate_limit
    if daily_limit is not None:
        key.daily_limit = daily_limit
    if allowed_ips is not None:
        key.allowed_ips = allowed_ips
    
    await db.commit()
    await db.refresh(key)
    
    logger.info(f"User {current_user.email} updated API key: {key.name}")
    
    return APIKeyResponse(
        id=key.id,
        name=key.name,
        description=key.description,
        key_prefix=key.key_prefix,
        scopes=key.scopes,
        rate_limit=key.rate_limit,
        daily_limit=key.daily_limit,
        is_active=key.is_active,
        expires_at=key.expires_at,
        last_used_at=key.last_used_at,
        total_requests=key.total_requests,
        requests_today=key.requests_today,
        created_at=key.created_at,
    )


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API key",
    description="Revoke (deactivate) an API key.",
)
async def revoke_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.organization_id == current_org.id,
        )
    )
    key = result.scalar_one_or_none()
    
    if not key:
        raise NotFoundError("API Key", str(key_id))
    
    key.revoke()
    await db.commit()
    
    logger.info(f"User {current_user.email} revoked API key: {key.name}")


@router.post(
    "/{key_id}/regenerate",
    response_model=APIKeyCreateResponse,
    summary="Regenerate API key",
    description="Regenerate an API key (revokes old, creates new).",
)
async def regenerate_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreateResponse:
    """Regenerate an API key."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.organization_id == current_org.id,
        )
    )
    old_key = result.scalar_one_or_none()

    if not old_key:
        raise NotFoundError("API Key", str(key_id))

    # Revoke old key
    old_key.revoke()

    # Create new key with same settings
    new_key, raw_key = APIKey.create_key(
        user_id=current_user.id,
        organization_id=current_org.id,
        name=old_key.name,
        scopes=old_key.scopes,
        rate_limit=old_key.rate_limit,
        daily_limit=old_key.daily_limit,
        description=old_key.description,
        allowed_ips=old_key.allowed_ips,
    )
    
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    
    logger.info(f"User {current_user.email} regenerated API key: {new_key.name}")
    
    return APIKeyCreateResponse(
        id=new_key.id,
        name=new_key.name,
        key=raw_key,
        key_prefix=new_key.key_prefix,
        scopes=new_key.scopes,
        rate_limit=new_key.rate_limit,
        expires_at=new_key.expires_at,
        message="Save this key securely - it won't be shown again!",
    )


@router.get(
    "/test",
    summary="Test API key authentication",
    description="Verify that your API key is working correctly.",
)
async def test_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Test endpoint to verify API key authentication.
    
    Returns information about the authenticated user and API key.
    """
    from app.api.deps import _verify_api_key_and_get_user, get_current_user
    
    # Try JWT first
    if credentials is not None:
        try:
            user = await get_current_user(credentials, db)
            return {
                "success": True,
                "auth_method": "jwt",
                "user_email": user.email,
                "message": "JWT authentication successful"
            }
        except Exception:
            pass
    
    # Try API key
    if api_key is not None:
        try:
            user, api_key_record = await _verify_api_key_and_get_user(request, api_key, db)
            return {
                "success": True,
                "auth_method": "api_key",
                "user_email": user.email,
                "api_key_name": api_key_record.name,
                "api_key_scopes": api_key_record.scopes,
                "api_key_rate_limit": api_key_record.rate_limit,
                "total_requests": api_key_record.total_requests,
                "message": "API key authentication successful"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "API key authentication failed"
            }
    
    return {
        "success": False,
        "message": "No authentication provided. Use X-API-Key header or Bearer token."
    }