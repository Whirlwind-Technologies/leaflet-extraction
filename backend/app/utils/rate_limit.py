"""
Authentication Rate Limiting Utility.

This module provides Redis-based rate limiting for authentication endpoints
to prevent brute-force attacks and credential stuffing. It implements a
multi-window approach (per-minute and per-hour) with IP-based tracking.

Rate limits are enforced per client IP address using Redis INCR + TTL.
When behind a reverse proxy (Nginx), the real client IP is extracted from
the X-Forwarded-For header.

Example Usage:
    from app.utils.rate_limit import create_auth_rate_limit_dependency

    # In your router:
    @router.post("/login")
    async def login(
        _rate_limit: None = Depends(
            create_auth_rate_limit_dependency("login", per_minute=5, per_hour=20)
        ),
        ...
    ):
        ...
"""

import logging
from typing import Optional, Tuple

from fastapi import Request
from redis.exceptions import RedisError

from app.config import settings
from app.utils.cache import get_redis_client
from app.utils.exceptions import RateLimitError

logger = logging.getLogger(__name__)

# Rate limit window durations in seconds
WINDOW_MINUTE = 60
WINDOW_HOUR = 3600

# Redis key prefix for auth rate limiting
AUTH_RATE_LIMIT_PREFIX = "rate_limit:auth"


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP address from the request.

    When running behind a reverse proxy (e.g., Nginx), the client IP is
    forwarded via the X-Forwarded-For header. This function checks that
    header first, falling back to request.client.host.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The client IP address as a string. Returns "unknown" if the IP
        cannot be determined.
    """
    # Check X-Forwarded-For header (set by Nginx / load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may contain multiple IPs: client, proxy1, proxy2
        # The first IP is the original client
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip

    # Fall back to direct connection IP
    if request.client and request.client.host:
        return request.client.host

    return "unknown"


async def _check_window(
    endpoint: str,
    client_ip: str,
    window_name: str,
    window_seconds: int,
    max_requests: int,
) -> Tuple[bool, int, int]:
    """Check a single rate limit window against Redis.

    Uses Redis INCR to atomically increment the counter and EXPIRE to set
    the TTL on first access. This is a fixed-window approach that is simple,
    efficient, and sufficient for auth endpoint protection.

    Args:
        endpoint: The endpoint name (e.g., "login", "register").
        client_ip: The client IP address.
        window_name: Human-readable window name ("minute" or "hour").
        window_seconds: The window duration in seconds.
        max_requests: Maximum allowed requests in this window.

    Returns:
        A tuple of (is_allowed, remaining_requests, retry_after_seconds).
        If Redis is unavailable, returns (True, max_requests, 0) to
        fail open and not block legitimate users.
    """
    redis_client = get_redis_client()
    if redis_client is None:
        # Fail open: if Redis is down, allow the request
        return True, max_requests, 0

    key = f"{AUTH_RATE_LIMIT_PREFIX}:{endpoint}:{client_ip}:{window_name}"

    try:
        # Atomically increment the counter
        current_count = await redis_client.incr(key)

        # Set TTL on first request in this window
        if current_count == 1:
            await redis_client.expire(key, window_seconds)

        remaining = max(0, max_requests - current_count)
        is_allowed = current_count <= max_requests

        if not is_allowed:
            # Get the TTL to calculate retry_after
            ttl = await redis_client.ttl(key)
            retry_after = max(1, ttl) if ttl > 0 else window_seconds
            return False, 0, retry_after

        return True, remaining, 0

    except RedisError as exc:
        logger.warning(
            f"Auth rate limit check failed, allowing request: endpoint={endpoint} ip={client_ip} error={exc}"
        )
        # Fail open on Redis errors
        return True, max_requests, 0


async def check_auth_rate_limit(
    request: Request,
    endpoint: str,
    per_minute: int,
    per_hour: Optional[int] = None,
) -> None:
    """Check authentication rate limits for the given endpoint and IP.

    Enforces both per-minute and per-hour (optional) rate limits. If either
    window is exceeded, raises a RateLimitError with an appropriate
    Retry-After value.

    This function is called by the dependency functions created via
    create_auth_rate_limit_dependency().

    Args:
        request: The incoming FastAPI request.
        endpoint: The endpoint identifier (e.g., "login", "register").
        per_minute: Maximum requests allowed per minute per IP.
        per_hour: Maximum requests allowed per hour per IP. If None,
            only the per-minute limit is enforced.

    Raises:
        RateLimitError: If the rate limit is exceeded for any window.
    """
    if not settings.rate_limit_enabled:
        return

    client_ip = _get_client_ip(request)

    # Check per-minute window first (tighter limit, shorter retry)
    is_allowed, remaining, retry_after = await _check_window(
        endpoint=endpoint,
        client_ip=client_ip,
        window_name="minute",
        window_seconds=WINDOW_MINUTE,
        max_requests=per_minute,
    )

    if not is_allowed:
        logger.warning(
            f"Auth rate limit exceeded (per-minute): endpoint={endpoint} ip={client_ip} limit={per_minute} retry_after={retry_after}"
        )
        raise RateLimitError(
            message=(
                f"Too many {endpoint} attempts. "
                f"Please try again in {retry_after} seconds."
            ),
            retry_after=retry_after,
        )

    # Check per-hour window if configured
    if per_hour is not None:
        is_allowed, remaining, retry_after = await _check_window(
            endpoint=endpoint,
            client_ip=client_ip,
            window_name="hour",
            window_seconds=WINDOW_HOUR,
            max_requests=per_hour,
        )

        if not is_allowed:
            logger.warning(
                f"Auth rate limit exceeded (per-hour): endpoint={endpoint} ip={client_ip} limit={per_hour} retry_after={retry_after}"
            )
            raise RateLimitError(
                message=(
                    f"Too many {endpoint} attempts. "
                    f"Hourly limit exceeded. Please try again in "
                    f"{retry_after // 60} minutes."
                ),
                retry_after=retry_after,
            )


def create_auth_rate_limit_dependency(
    endpoint: str,
    per_minute: int,
    per_hour: Optional[int] = None,
):
    """Create a FastAPI dependency that enforces auth rate limits.

    Returns an async dependency function that can be injected into endpoint
    signatures via Depends(). The dependency extracts the client IP from
    the request and checks both per-minute and per-hour rate limits.

    Args:
        endpoint: A short identifier for the endpoint (e.g., "login").
            Used in Redis keys and log messages.
        per_minute: Maximum requests allowed per minute per IP address.
        per_hour: Maximum requests allowed per hour per IP address.
            If None, only the per-minute limit is enforced.

    Returns:
        An async function suitable for use with FastAPI's Depends().

    Example:
        >>> login_rate_limit = create_auth_rate_limit_dependency(
        ...     "login", per_minute=5, per_hour=20
        ... )
        >>>
        >>> @router.post("/login")
        >>> async def login(
        ...     _rate_limit: None = Depends(login_rate_limit),
        ...     login_data: LoginRequest = ...,
        ... ):
        ...     ...
    """

    async def _rate_limit_dependency(request: Request) -> None:
        """FastAPI dependency that checks auth rate limits.

        Args:
            request: The incoming FastAPI request (injected by FastAPI).

        Raises:
            RateLimitError: If the rate limit is exceeded.
        """
        await check_auth_rate_limit(
            request=request,
            endpoint=endpoint,
            per_minute=per_minute,
            per_hour=per_hour,
        )

    return _rate_limit_dependency
