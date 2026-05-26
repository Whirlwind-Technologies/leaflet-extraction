"""
Models Package.

This package contains all SQLAlchemy models for the Leaflet Data Extraction Platform.

Example Usage:
    from app.models import User, Leaflet, Product, LeafletStatus, ReviewStatus
    
    # Create a user
    user = User(email="user@example.com", hashed_password="...")
    
    # Create a leaflet
    leaflet = Leaflet(
        leaflet_id="LEAF_2025_001234",
        user_id=user.id,
        filename="promo.pdf"
    )
    
    # Create a product
    product = Product(
        leaflet_id=leaflet.id,
        page_number=1,
        product_name="Test Product",
        bbox_x=0, bbox_y=0, bbox_width=100, bbox_height=100
    )
"""

from app.models.base import Base, BaseModel, TimestampMixin
from app.models.user import User
from app.models.organization import Organization, OrganizationStatus, OrganizationType
from app.models.retailer import Retailer
from app.models.organization_user import OrganizationUser, OrganizationRole
from app.models.organization_invitation import OrganizationInvitation, InvitationStatus
from app.models.deletion_request import DeletionRequest, DeletionRequestType, DeletionRequestStatus
from app.models.leaflet import Leaflet, LeafletPage, LeafletStatus
from app.models.product import Product, ProductReview, ReviewStatus
from app.models.vlm_provider import VLMProvider, VLMProviderType, DEFAULT_MODELS
from app.models.vlm_model import VLMModel, DEFAULT_VLM_MODELS
from app.models.api_key import APIKey, APIKeyScope
from app.models.webhook import Webhook, WebhookDelivery, WebhookEvent
from app.models.analytics import (
    UsageMetrics,
    CostTracking,
    ProcessingStats,
    FeedbackLog,
    ErrorPattern,
)

# Platform VLM Management System
from app.models.platform_vlm_provider import (
    PlatformVLMProvider,
    PlatformVLMProviderType,
    PLATFORM_DEFAULT_MODELS,
)
from app.models.system_notification import (
    SystemNotification,
    NotificationPreference,
    NotificationType,
    NotificationSeverity,
    NotificationSource,
)
from app.models.organization_usage import (
    OrganizationVLMUsage,
    OrganizationUsageSummary,
)
from app.models.budget_alert import (
    BudgetAlert,
    AlertHistory,
    AlertType,
    AlertPeriod,
)
from app.models.vlm_audit_log import (
    VLMProviderAuditLog,
    AuditEventType,
    AuditEventStatus,
    ErrorCategory,
)
from app.models.vlm_provider_backup import (
    VLMProviderBackup,
    BackupType,
    BackupStatus,
    DEFAULT_RETENTION_DAYS,
)
from app.models.product_category import ProductCategory
from app.models.export_job import ExportJob

__all__ = [
    # Base
    "Base",
    "BaseModel",
    "TimestampMixin",
    # User
    "User",
    # Organization
    "Organization",
    "OrganizationStatus",
    "OrganizationType",
    "Retailer",
    "OrganizationUser",
    "OrganizationRole",
    "OrganizationInvitation",
    "InvitationStatus",
    "DeletionRequest",
    "DeletionRequestType",
    "DeletionRequestStatus",
    # Leaflet
    "Leaflet",
    "LeafletPage",
    "LeafletStatus",
    # Product
    "Product",
    "ProductReview",
    "ReviewStatus",
    # VLM Provider
    "VLMProvider",
    "VLMProviderType",
    "DEFAULT_MODELS",
    # VLM Model Registry
    "VLMModel",
    "DEFAULT_VLM_MODELS",
    # API Key
    "APIKey",
    "APIKeyScope",
    # Webhook
    "Webhook",
    "WebhookDelivery",
    "WebhookEvent",
    # Analytics
    "UsageMetrics",
    "CostTracking",
    "ProcessingStats",
    "FeedbackLog",
    "ErrorPattern",
    # Platform VLM Management System
    "PlatformVLMProvider",
    "PlatformVLMProviderType",
    "PLATFORM_DEFAULT_MODELS",
    "SystemNotification",
    "NotificationPreference",
    "NotificationType",
    "NotificationSeverity",
    "NotificationSource",
    "OrganizationVLMUsage",
    "OrganizationUsageSummary",
    "BudgetAlert",
    "AlertHistory",
    "AlertType",
    "AlertPeriod",
    "VLMProviderAuditLog",
    "AuditEventType",
    "AuditEventStatus",
    "ErrorCategory",
    "VLMProviderBackup",
    "BackupType",
    "BackupStatus",
    "DEFAULT_RETENTION_DAYS",
    # Product Category
    "ProductCategory",
    # Export Job
    "ExportJob",
]