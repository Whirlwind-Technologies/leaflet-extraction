"""
Middleware Package.

This package contains custom middleware for the FastAPI application.
"""

from app.middleware.tenant_scope import TenantScopeMiddleware

__all__ = [
    "TenantScopeMiddleware",
]
