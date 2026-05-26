"""
API Dependencies Module.

This module provides dependency injection functions for FastAPI endpoints,
including authentication, database sessions, and common utilities.

Example Usage:
    from app.api.deps import get_current_user, get_db
    
    @router.get("/me")
    async def get_profile(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        return current_user
"""

import logging
from datetime import datetime
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.models.api_key import APIKey
from app.models.organization import Organization
from app.models.organization_user import OrganizationUser, OrganizationRole
from app.utils.cache import RateLimiter, get_cache, set_cache
from app.utils.database import get_db, get_sync_db_session
from app.utils.exceptions import (
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
)
from app.utils.security import decode_token, is_token_revoked, verify_api_key

logger = logging.getLogger(__name__)

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    This dependency validates the JWT token and returns the associated user.
    
    Args:
        credentials: HTTP Bearer credentials from request
        db: Database session
        
    Returns:
        Authenticated User instance
        
    Raises:
        AuthenticationError: If token is invalid or user not found
        
    Example:
        >>> @router.get("/me")
        >>> async def get_profile(user: User = Depends(get_current_user)):
        ...     return user
    """
    if credentials is None:
        raise AuthenticationError("Authentication required")
    
    token = credentials.credentials
    
    # Decode and validate token
    payload = decode_token(token)
    if payload is None:
        raise AuthenticationError("Invalid or expired token")

    # Check token type
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    # Reject blacklisted tokens (logged out / explicitly revoked)
    if await is_token_revoked(payload):
        raise AuthenticationError("Token has been revoked")

    # Get user ID from token
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Invalid token payload")
    
    # Try to get user from cache
    cache_key = f"user:{user_id}"
    cached_user = await get_cache(cache_key)
    
    if cached_user:
        # Reconstruct user from cache (basic validation only)
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise AuthenticationError("Invalid user ID")
    else:
        # Fetch user from database
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise AuthenticationError("Invalid user ID")
        
        result = await db.execute(
            select(User).where(User.id == user_uuid)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            raise AuthenticationError("User not found")
        
        if not user.is_active:
            raise AuthenticationError("User account is inactive")
        
        # Cache user for future requests
        await set_cache(
            cache_key,
            {"id": str(user.id), "email": user.email},
            ttl=300  # 5 minutes
        )
        
        return user
    
    # If we got here from cache, fetch the full user
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise AuthenticationError("User not found")
    
    if not user.is_active:
        raise AuthenticationError("User account is inactive")
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify they are active.
    
    Args:
        current_user: User from get_current_user dependency
        
    Returns:
        Active User instance
        
    Raises:
        AuthorizationError: If user is inactive
    """
    if not current_user.is_active:
        raise AuthorizationError("Inactive user")
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify they are a superuser.

    Args:
        current_user: User from get_current_user dependency

    Returns:
        Superuser instance

    Raises:
        AuthorizationError: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise AuthorizationError("Superuser privileges required")
    return current_user


# Organization-based authorization dependencies


async def get_current_organization(
    request: Request,
    org_id_header: Optional[str] = Header(None, alias="X-Organization-ID"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key_header: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """
    Get the current active organization for the user.

    Determines organization context using this priority:
    1. API key's organization_id (if using API key auth)
    2. org_id from JWT token (if present)
    3. X-Organization-ID header (if provided)
    4. User's default_organization_id

    After determining org_id, verifies the user is a member of that organization
    (skipped for API key auth since the key is already scoped to the org).

    Args:
        request: FastAPI request object
        org_id_header: Optional organization ID from header
        credentials: Bearer token credentials (for extracting org_id from JWT)
        api_key_header: API key from header
        db: Database session

    Returns:
        Organization instance

    Raises:
        AuthorizationError: If user is not a member of the organization
        AuthenticationError: If organization not found

    Example:
        >>> @router.get("/data")
        >>> async def get_data(
        ...     org: Organization = Depends(get_current_organization)
        ... ):
        ...     return {"org_id": org.id}
    """
    org_id = None
    current_user = None
    using_api_key = False

    # 1. Check if using API key authentication - get org from the key
    if api_key_header and api_key_header.startswith("lep_"):
        try:
            user, api_key_record = await _verify_api_key_and_get_user(request, api_key_header, db)
            org_id = api_key_record.organization_id
            current_user = user
            using_api_key = True
            logger.debug(f"Using org_id from API key: {org_id}")
        except (AuthenticationError, RateLimitError) as e:
            # Log the failure so silent auth fallthrough is diagnosable
            logger.warning(f"API key organization resolution failed: {e}")
            # API key auth failed, will try other methods

    # 2. Try to get org_id from JWT token
    if org_id is None and credentials:
        payload = decode_token(credentials.credentials)
        if payload:
            # Get user from JWT
            user_id = payload.get("sub")
            if user_id:
                try:
                    user_uuid = UUID(user_id)
                    result = await db.execute(select(User).where(User.id == user_uuid))
                    current_user = result.scalar_one_or_none()
                except ValueError:
                    pass

            if "org_id" in payload:
                try:
                    org_id = UUID(payload["org_id"])
                    logger.debug(f"Using org_id from JWT: {org_id}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid org_id in JWT token: {payload.get('org_id')}")

    # 3. Fallback to X-Organization-ID header
    if org_id is None and org_id_header:
        try:
            org_id = UUID(org_id_header)
            logger.debug(f"Using org_id from header: {org_id}")
        except ValueError:
            raise AuthenticationError("Invalid organization ID in header")

    # 4. Fallback to user's default organization
    if org_id is None and current_user:
        if current_user.default_organization_id:
            org_id = current_user.default_organization_id
            logger.debug(f"Using user's default org_id: {org_id}")

    if org_id is None:
        raise AuthenticationError(
            "No organization context available. Please set default organization or provide X-Organization-ID header."
        )

    # Fetch the organization
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        raise AuthenticationError("Organization not found")

    # For API key auth, skip membership check (key is already scoped to org)
    # For JWT auth, verify user is a member of this organization
    if not using_api_key and current_user:
        result = await db.execute(
            select(OrganizationUser).where(
                OrganizationUser.organization_id == org_id,
                OrganizationUser.user_id == current_user.id,
                OrganizationUser.is_active == True,
            )
        )
        membership = result.scalar_one_or_none()

        if membership is None:
            raise AuthorizationError(
                "You are not a member of this organization or your membership is inactive"
            )

        logger.info(
            f"Organization context: {organization.name} (user: {current_user.email}, role: {membership.role.value})"
        )
    else:
        logger.info(
            f"Organization context: {organization.name} (via API key)"
        )

    # Check organization status
    if not organization.is_active:
        raise AuthorizationError(
            f"Organization is not active (status: {organization.status.value})"
        )

    return organization


async def get_current_org_membership(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> OrganizationUser:
    """
    Get the current user's membership record in the current organization.

    Args:
        current_user: Authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        OrganizationUser membership record

    Raises:
        AuthorizationError: If membership not found (should not happen after get_current_organization)
    """
    result = await db.execute(
        select(OrganizationUser).where(
            OrganizationUser.organization_id == current_org.id,
            OrganizationUser.user_id == current_user.id,
            OrganizationUser.is_active == True,
        )
    )
    membership = result.scalar_one_or_none()

    if membership is None:
        raise AuthorizationError("Organization membership not found")

    return membership


def require_org_role(*required_roles: OrganizationRole):
    """
    Dependency factory that requires specific organization roles.

    Checks if user has one of the required roles using role hierarchy:
    OWNER > ADMIN > MEMBER > VIEWER

    Args:
        *required_roles: One or more required roles (user must have at least one)

    Returns:
        Async dependency function that returns OrganizationUser membership

    Raises:
        AuthorizationError: If user doesn't have any of the required roles

    Example:
        >>> @router.post("/data")
        >>> async def create_data(
        ...     membership: OrganizationUser = Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.OWNER))
        ... ):
        ...     return {"role": membership.role}
    """
    async def check_role(
        membership: OrganizationUser = Depends(get_current_org_membership),
    ) -> OrganizationUser:
        """Check if user has required role."""
        if membership.role not in required_roles:
            # Check role hierarchy - higher roles can access lower permissions
            user_level = OrganizationRole.get_hierarchy_level(membership.role)
            required_levels = [OrganizationRole.get_hierarchy_level(r) for r in required_roles]

            if user_level < max(required_levels):
                raise AuthorizationError(
                    f"Insufficient permissions. Required role: {', '.join(r.value for r in required_roles)}"
                )

        return membership

    return check_role


async def get_current_org_admin(
    membership: OrganizationUser = Depends(
        require_org_role(OrganizationRole.ADMIN, OrganizationRole.OWNER)
    ),
) -> OrganizationUser:
    """
    Shorthand dependency for requiring ADMIN or OWNER role.

    Args:
        membership: Organization membership from require_org_role

    Returns:
        OrganizationUser with ADMIN or OWNER role

    Example:
        >>> @router.put("/organization/settings")
        >>> async def update_settings(
        ...     admin: OrganizationUser = Depends(get_current_org_admin)
        ... ):
        ...     return {"role": admin.role}
    """
    return membership


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.
    
    Use this for endpoints that work both authenticated and anonymously.
    
    Args:
        credentials: HTTP Bearer credentials (optional)
        db: Database session
        
    Returns:
        User instance if authenticated, None otherwise
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except AuthenticationError:
        return None


async def _verify_api_key_and_get_user(
    request: Request,
    api_key: str,
    db: AsyncSession,
) -> tuple[User, APIKey]:
    """
    Internal function to verify API key and return user + key record.
    
    Args:
        request: FastAPI request object (for IP tracking)
        api_key: API key string
        db: Database session
        
    Returns:
        Tuple of (User, APIKey)
        
    Raises:
        AuthenticationError: If API key is invalid
        RateLimitError: If rate limit exceeded
    """
    # Validate key format
    if not api_key.startswith("lep_"):
        logger.warning(f"Invalid API key format attempted")
        raise AuthenticationError("Invalid API key format")
    
    # Get key prefix for lookup (first 12 characters to match stored prefix)
    key_prefix = api_key[:12]
    logger.debug(f"Looking up API key with prefix: {key_prefix}")
    
    # Find API key by prefix
    result = await db.execute(
        select(APIKey).where(
            APIKey.key_prefix == key_prefix,
            APIKey.is_active == True,
        )
    )
    api_key_record = result.scalar_one_or_none()
    
    if api_key_record is None:
        logger.warning(f"API key not found for prefix: {key_prefix}")
        raise AuthenticationError("Invalid API key")
    
    # Verify the full key using SHA-256
    if not verify_api_key(api_key, api_key_record.key_hash):
        logger.warning(f"API key hash mismatch for key: {key_prefix}...")
        raise AuthenticationError("Invalid API key")
    
    # Check if expired
    if api_key_record.is_expired:
        logger.warning(f"Expired API key used: {api_key_record.name}")
        raise AuthenticationError("API key has expired")
    
    # Check IP whitelist if configured
    client_ip = request.client.host if request.client else None
    if api_key_record.allowed_ips and client_ip:
        if client_ip not in api_key_record.allowed_ips:
            logger.warning(f"API key {api_key_record.name} used from unauthorized IP: {client_ip}")
            raise AuthenticationError("IP address not allowed for this API key")
    
    # Check daily limit
    if not api_key_record.check_daily_limit():
        logger.warning(f"API key {api_key_record.name} exceeded daily limit")
        raise RateLimitError("Daily API request limit exceeded")
    
    # Get the associated user
    result = await db.execute(
        select(User).where(User.id == api_key_record.user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        logger.warning(f"API key {api_key_record.name} belongs to inactive/missing user")
        raise AuthenticationError("User not found or inactive")
    
    # Record usage
    api_key_record.record_usage(ip=client_ip)
    await db.commit()
    
    logger.info(f"API key authenticated: {api_key_record.name} (user: {user.email})")
    
    return user, api_key_record


def _required_scopes_for_request(request: Request) -> list[str]:
    """
    Determine which API-key scopes a request requires based on
    its HTTP method and path.

    Order matters: path-based scopes (export, upload) are checked first
    so that a key without the relevant scope is rejected even if it
    holds "write".
    """
    method = request.method.upper()
    path = request.url.path.lower()

    required: list[str] = []

    # Path-specific scopes
    if "/export" in path:
        required.append("export")
    if "/upload" in path and method in {"POST", "PUT"}:
        required.append("upload")

    # Method-based scopes
    if method in {"GET", "HEAD", "OPTIONS"}:
        required.append("read")
    elif method == "DELETE":
        required.append("delete")
    elif method in {"POST", "PUT", "PATCH"}:
        # Already handled by upload path above, but generic mutations need write
        if "upload" not in required:
            required.append("write")

    return required


def _enforce_api_key_scopes(request: Request, api_key: APIKey) -> None:
    """
    Verify the API key has every scope required for this request.

    `admin` scope satisfies all requirements.
    """
    if api_key.has_scope("admin"):
        return

    for scope in _required_scopes_for_request(request):
        if not api_key.has_scope(scope):
            raise AuthorizationError(
                f"API key does not have required scope: {scope}"
            )


async def get_current_user_or_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Authenticate using either JWT token or API key.

    Tries JWT first, then API key. When authentication succeeds via
    API key, the key's scopes are enforced against the request's
    HTTP method and path (read/write/delete/export/upload). JWT
    sessions are not subject to scope checks because they represent
    a logged-in human user.

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials
        api_key: API key from header
        db: Database session

    Returns:
        Authenticated User instance

    Raises:
        AuthenticationError: If neither method succeeds
        AuthorizationError: If the API key lacks a required scope
    """
    # Try JWT first
    if credentials is not None:
        try:
            return await get_current_user(credentials, db)
        except AuthenticationError:
            pass

    # Try API key
    if api_key is not None:
        try:
            user, key_record = await _verify_api_key_and_get_user(request, api_key, db)
            _enforce_api_key_scopes(request, key_record)
            return user
        except (AuthenticationError, RateLimitError):
            raise

    raise AuthenticationError("Authentication required")


async def get_current_user_and_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, Optional[APIKey]]:
    """
    Authenticate and return both user and API key (if used).
    
    Useful when you need to check API key scopes.
    
    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials
        api_key: API key from header
        db: Database session
        
    Returns:
        Tuple of (User, APIKey or None)
        
    Raises:
        AuthenticationError: If authentication fails
    """
    # Try JWT first
    if credentials is not None:
        try:
            user = await get_current_user(credentials, db)
            return user, None  # No API key used
        except AuthenticationError:
            pass
    
    # Try API key
    if api_key is not None:
        try:
            return await _verify_api_key_and_get_user(request, api_key, db)
        except (AuthenticationError, RateLimitError):
            raise
    
    raise AuthenticationError("Authentication required")


def require_scope(required_scope: str):
    """
    Dependency factory that checks if API key has required scope.
    
    For JWT auth, all scopes are allowed.
    For API key auth, checks the scopes list.
    
    Usage:
        @router.get("/data")
        async def get_data(
            auth: tuple = Depends(require_scope("read"))
        ):
            user, api_key = auth
            ...
    """
    async def check_scope(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
        api_key_header: Optional[str] = Header(None, alias="X-API-Key"),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[User, Optional[APIKey]]:
        user, api_key = await get_current_user_and_api_key(
            request, credentials, api_key_header, db
        )
        
        # JWT auth has all permissions
        if api_key is None:
            return user, None
        
        # Check API key scope
        if not api_key.has_scope(required_scope):
            raise AuthorizationError(
                f"API key does not have required scope: {required_scope}"
            )
        
        return user, api_key
    
    return check_scope


# ---------------------------------------------------------------------------
# Scope-enforcing user dependencies (drop-in replacements for
# get_current_user_or_api_key that additionally check API-key scopes).
#
# JWT-authenticated requests pass through unchanged — scopes only
# restrict API-key callers.
# ---------------------------------------------------------------------------

def _scoped_user_dependency(scope: str):
    _check = require_scope(scope)

    async def _dep(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
        api_key_header: Optional[str] = Header(None, alias="X-API-Key"),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        user, _api_key = await _check(request, credentials, api_key_header, db)
        return user

    return _dep


require_read = _scoped_user_dependency("read")
require_write = _scoped_user_dependency("write")
require_export = _scoped_user_dependency("export")
require_webhook = _scoped_user_dependency("webhook")
require_admin = _scoped_user_dependency("admin")


# Rate limiting dependencies

# Create rate limiters
api_rate_limiter = RateLimiter(
    "api",
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window,
)

upload_rate_limiter = RateLimiter(
    "upload",
    max_requests=10,
    window_seconds=60,
)


async def check_rate_limit(
    request: Request,
    user: Optional[User] = Depends(get_optional_user),
) -> None:
    """
    Check API rate limit for the request.
    
    Rate limits are tracked per user ID (if authenticated) or IP address.
    
    Args:
        request: FastAPI request object
        user: Optional authenticated user
        
    Raises:
        RateLimitError: If rate limit exceeded
    """
    if not settings.rate_limit_enabled:
        return
    
    # Use user ID or IP address as identifier
    if user:
        identifier = str(user.id)
    else:
        identifier = request.client.host if request.client else "unknown"
    
    if not await api_rate_limiter.is_allowed(identifier):
        remaining = await api_rate_limiter.get_remaining(identifier)
        raise RateLimitError(
            message="Rate limit exceeded",
            retry_after=settings.rate_limit_window,
        )


async def check_upload_rate_limit(
    request: Request,
    user: User = Depends(get_current_user),
) -> None:
    """
    Check upload rate limit for the request.
    
    More restrictive rate limit for file uploads.
    
    Args:
        request: FastAPI request object
        user: Authenticated user
        
    Raises:
        RateLimitError: If upload rate limit exceeded
    """
    identifier = str(user.id)
    
    if not await upload_rate_limiter.is_allowed(identifier):
        raise RateLimitError(
            message="Upload rate limit exceeded",
            retry_after=60,
        )


# WebSocket authentication dependency


async def get_current_user_ws(token: str, db: AsyncSession) -> User:
    """
    Authenticate a WebSocket connection using JWT token from query param.

    Unlike HTTP endpoints, WebSocket connections pass the token as a query
    parameter since they cannot use Authorization headers reliably.

    Args:
        token: JWT access token from query parameter.
        db: Async database session.

    Returns:
        Authenticated User instance.

    Raises:
        AuthenticationError: If token is invalid or user not found.

    Example:
        >>> user = await get_current_user_ws(token="eyJ...", db=session)
        >>> print(user.email)
    """
    payload = decode_token(token)
    if payload is None:
        raise AuthenticationError("Invalid or expired token")

    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Invalid token payload")

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise AuthenticationError("Invalid user ID")

    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    return user


# Pagination dependency

from app.schemas.common import PaginationParams


def get_pagination(
    page: int = 1,
    page_size: int = 20,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
) -> PaginationParams:
    """
    Get pagination parameters from query string.
    
    Args:
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        sort_by: Field to sort by
        sort_order: Sort direction (asc/desc)
        
    Returns:
        PaginationParams instance
    """
    return PaginationParams(
        page=max(1, page),
        page_size=min(max(1, page_size), 100),
        sort_by=sort_by,
        sort_order=sort_order if sort_order in ("asc", "desc") else "desc",
    )


# Admin-specific dependencies for sync operations

def get_current_super_admin_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    """
    Get current user and verify they are a super admin (synchronous version).

    This dependency is specifically designed for admin API endpoints that use
    synchronous database operations.

    Args:
        credentials: HTTP Bearer credentials from request

    Returns:
        Superuser instance

    Raises:
        AuthenticationError: If token is invalid or user not found
        AuthorizationError: If user is not a superuser
    """
    from sqlalchemy import select

    if credentials is None:
        raise AuthenticationError("Authentication required")

    token = credentials.credentials

    # Decode and validate token
    payload = decode_token(token)
    if payload is None:
        raise AuthenticationError("Invalid or expired token")

    # Check token type
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    # Get user ID from token
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Invalid token payload")

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise AuthenticationError("Invalid user ID")

    # Get sync database session
    db = get_sync_db_session()

    try:
        # Fetch user from database
        result = db.execute(
            select(User).where(User.id == user_uuid)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise AuthenticationError("User not found")

        if not user.is_active:
            raise AuthenticationError("User account is inactive")

        if not user.is_superuser:
            raise AuthorizationError("Super admin privileges required")

        return user

    finally:
        db.close()