"""
Admin API endpoints for Platform VLM Management System.

This module aggregates all admin API routers for super admin functionality,
including user management, system stats, platform provider management,
usage reporting, audit logs, and budget alert configuration.
"""

from fastapi import APIRouter

# Import sub-module routers
from app.api.v1.admin import users
from app.api.v1.admin import stats
from app.api.v1.admin import deletion_requests
from app.api.v1.admin import notifications
from app.api.v1.admin import registrations
from app.api.v1.admin import platform_providers
from app.api.v1.admin import usage_reports
from app.api.v1.admin import budget_alerts
from app.api.v1.admin import audit_logs
from app.api.v1.admin import provider_backups
from app.api.v1.admin import vlm_models
from app.api.v1.admin import system_health
from app.api.v1.admin import organizations

router = APIRouter()

# Core admin endpoints
router.include_router(users.router, prefix="/users", tags=["Admin - Users"])
router.include_router(stats.router, prefix="/stats", tags=["Admin - Stats"])
router.include_router(deletion_requests.router, prefix="/deletion-requests", tags=["Admin - Deletion Requests"])
router.include_router(notifications.router, prefix="/notifications", tags=["Admin - Notifications"])

# Feature-specific admin endpoints
router.include_router(registrations.router, prefix="/registrations", tags=["Admin - Registrations"])
router.include_router(platform_providers.router, prefix="/platform-providers", tags=["Admin - Platform Providers"])
router.include_router(usage_reports.router, prefix="/usage-reports", tags=["Admin - Usage Reports"])
router.include_router(budget_alerts.router, prefix="/budget-alerts", tags=["Admin - Budget Alerts"])
router.include_router(audit_logs.router, prefix="/audit-logs", tags=["Admin - Audit Logs"])
router.include_router(provider_backups.router, prefix="/provider-backups", tags=["Admin - Provider Backups"])
router.include_router(vlm_models.router, tags=["Admin - VLM Models"])
router.include_router(system_health.router, prefix="/system", tags=["Admin - System Health"])
router.include_router(organizations.router, prefix="/organizations", tags=["Admin - Organizations"])
