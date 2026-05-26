"""
API Version 1 Router.

This module aggregates all v1 API routers into a single router.

Example Usage:
    from app.api.v1 import router
    
    app.include_router(router, prefix="/api/v1")
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.leaflets import router as leaflets_router
from app.api.v1.product_export import router as product_export_router
from app.api.v1.products import router as products_router
from app.api.v1.export import router as export_router
from app.api.v1.websocket import router as websocket_router
from app.api.v1.admin import router as admin_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.vlm_providers import router as vlm_providers_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.retailers import router as retailers_router
from app.api.v1.registrations import router as registrations_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.invitations import router as invitations_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.categories import router as categories_router
from app.api.v1.contact import router as contact_router

router = APIRouter()

# Include all routers
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(registrations_router)  # No prefix - uses /registrations from router
router.include_router(organizations_router)  # No prefix - uses /organizations from router
router.include_router(invitations_router)  # No prefix - uses /invitations from router (public)
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(leaflets_router, prefix="/leaflets", tags=["Leaflets"])
router.include_router(product_export_router, prefix="/products", tags=["Product Export"])
router.include_router(products_router, prefix="/products", tags=["Products"])
router.include_router(export_router, prefix="/export", tags=["Export"])
router.include_router(websocket_router, prefix="/ws", tags=["WebSocket"])
router.include_router(admin_router, prefix="/admin", tags=["Admin"])
router.include_router(api_keys_router, prefix="/api-keys", tags=["API Keys"])
router.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])
router.include_router(vlm_providers_router, prefix="/vlm-providers", tags=["VLM Providers"])
router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
router.include_router(retailers_router, prefix="/retailers", tags=["Retailers"])
router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
router.include_router(categories_router, prefix="/categories", tags=["Categories"])
router.include_router(contact_router, tags=["Contact"])