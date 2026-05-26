"""
Tenant Scope Middleware Module.

This middleware automatically injects organization context into requests,
enabling multi-tenant data isolation at the middleware level.

Example Usage:
    from app.middleware.tenant_scope import TenantScopeMiddleware

    app.add_middleware(TenantScopeMiddleware)
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.security import decode_token

logger = logging.getLogger(__name__)


class TenantScopeMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically injects organization context into requests.

    This middleware:
    1. Extracts organization ID from JWT token or X-Organization-ID header
    2. Adds org_id to request.state for use in endpoints
    3. Adds user_role to request.state (if JWT contains role)
    4. Logs organization context for auditing

    The middleware does NOT enforce authorization - it only extracts context.
    Authorization is enforced by the get_current_organization dependency.

    Request State Variables Set:
        request.state.org_id: UUID or None - Organization ID from token/header
        request.state.user_role: str or None - User's role in organization
        request.state.tenant_source: str - Source of org_id ("jwt", "header", or "none")

    Example:
        In endpoint:
        >>> @router.get("/data")
        >>> async def get_data(request: Request):
        ...     org_id = request.state.org_id  # May be None
        ...     return {"org_id": str(org_id) if org_id else None}
    """

    async def dispatch(self, request: Request, call_next):
        """
        Process request and inject organization context.

        Args:
            request: Incoming FastAPI request
            call_next: Next middleware/handler in chain

        Returns:
            Response from downstream handlers
        """
        org_id: Optional[UUID] = None
        user_role: Optional[str] = None
        tenant_source: str = "none"

        try:
            # 1. Try to extract org_id from JWT token
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
                payload = decode_token(token)

                if payload:
                    # Extract org_id from token
                    if "org_id" in payload:
                        try:
                            org_id = UUID(payload["org_id"])
                            tenant_source = "jwt"
                            logger.debug(f"Extracted org_id from JWT: {org_id}")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid org_id in JWT token: {payload.get('org_id')}, error: {e}")

                    # Extract role from token
                    if "role" in payload:
                        user_role = payload["role"]
                        logger.debug(f"Extracted role from JWT: {user_role}")

            # 2. Fallback to X-Organization-ID header (only if JWT didn't have org_id)
            if org_id is None:
                org_id_header = request.headers.get("x-organization-id")
                if org_id_header:
                    try:
                        org_id = UUID(org_id_header)
                        tenant_source = "header"
                        logger.debug(f"Extracted org_id from header: {org_id}")
                    except ValueError as e:
                        logger.warning(f"Invalid org_id in X-Organization-ID header: {org_id_header}, error: {e}")

            # 3. Set request state variables
            request.state.org_id = org_id
            request.state.user_role = user_role
            request.state.tenant_source = tenant_source

            # Log tenant context for auditing (only if org_id is present)
            if org_id:
                logger.info(
                    f"Tenant context: org_id={org_id}, role={user_role}, "
                    f"source={tenant_source}, path={request.url.path}, method={request.method}"
                )

        except Exception as e:
            # Don't fail the request if middleware has issues
            # Just log and continue without tenant context
            logger.error(f"Error in TenantScopeMiddleware: {e}", exc_info=True)
            request.state.org_id = None
            request.state.user_role = None
            request.state.tenant_source = "error"

        # Continue to next middleware/handler
        response = await call_next(request)

        # Add organization ID to response headers for debugging (optional)
        if org_id:
            response.headers["X-Current-Organization"] = str(org_id)

        return response
