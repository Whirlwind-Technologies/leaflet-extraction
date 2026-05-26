"""
Pydantic schemas for Platform VLM Management System.

These schemas handle request/response validation for platform provider management,
organization usage reporting, budget alerts, and audit logging.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum

from app.models.platform_vlm_provider import PlatformVLMProviderType
from app.models.budget_alert import AlertType, AlertPeriod
from app.models.vlm_audit_log import AuditEventType, AuditEventStatus, ErrorCategory
from app.models.system_notification import NotificationType, NotificationSeverity


# Platform Provider Schemas
class PlatformProviderCreate(BaseModel):
    """Schema for creating a new platform provider."""
    name: str = Field(..., min_length=1, max_length=100, description="Provider name")
    provider_type: PlatformVLMProviderType = Field(..., description="Provider type")
    model_name: Optional[str] = Field(None, description="Model name (uses default if not specified)")
    api_key: str = Field(..., min_length=1, description="API key for the provider")
    api_endpoint: Optional[str] = Field(None, description="Custom API endpoint")
    priority: int = Field(1, ge=1, le=999, description="Provider priority (1=highest)")
    monthly_budget: Optional[Decimal] = Field(None, ge=0, description="Monthly budget limit")
    daily_budget: Optional[Decimal] = Field(None, ge=0, description="Daily budget limit")
    hourly_rate_limit: Optional[int] = Field(None, ge=0, description="Hourly request rate limit")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum tokens per request")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Model temperature")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional configuration")
    is_active: bool = Field(True, description="Whether provider is active")

    @validator('api_key')
    def validate_api_key(cls, v):
        """Ensure API key is not empty."""
        if not v or not v.strip():
            raise ValueError("API key cannot be empty")
        return v.strip()


class PlatformProviderUpdate(BaseModel):
    """Schema for updating an existing platform provider."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    model_name: Optional[str] = Field(None)
    api_key: Optional[str] = Field(None, description="New API key (leave empty to keep current)")
    api_endpoint: Optional[str] = Field(None)
    priority: Optional[int] = Field(None, ge=1, le=999)
    monthly_budget: Optional[Decimal] = Field(None, ge=0)
    daily_budget: Optional[Decimal] = Field(None, ge=0)
    hourly_rate_limit: Optional[int] = Field(None, ge=0)
    max_tokens: Optional[int] = Field(None, ge=1)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    config: Optional[Dict[str, Any]] = Field(None)
    is_active: Optional[bool] = Field(None)


class PlatformProviderResponse(BaseModel):
    """Schema for platform provider response."""
    id: UUID
    name: str
    provider_type: PlatformVLMProviderType
    model_name: str
    api_endpoint: Optional[str] = None
    priority: int
    monthly_budget: Optional[Decimal] = None
    daily_budget: Optional[Decimal] = None
    max_requests_per_hour: Optional[int] = None
    max_tokens: int
    temperature: float
    config: Dict[str, Any] = {}
    is_active: bool
    is_default: bool = False
    last_used_at: Optional[datetime] = None
    total_spent: float = 0.0
    current_month_spent: float = 0.0
    current_day_spent: float = 0.0
    current_hour_requests: int = 0
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    created_at: datetime
    updated_at: datetime
    created_by_user_id: Optional[UUID] = None

    # Computed fields
    api_key_preview: str = Field(default="sk-***...***", description="Masked API key preview")
    provider_display_name: str = Field(default="Unknown", description="Human-readable provider type name")

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle computed fields."""
        data = {
            'id': obj.id,
            'name': obj.name,
            'provider_type': obj.provider_type,
            'model_name': obj.model_name,
            'api_endpoint': obj.api_endpoint,
            'priority': obj.priority,
            'monthly_budget': obj.monthly_budget,
            'daily_budget': obj.daily_budget,
            'max_requests_per_hour': obj.max_requests_per_hour,
            'max_tokens': obj.max_tokens,
            'temperature': obj.temperature,
            'config': obj.config or {},
            'is_active': obj.is_active,
            'is_default': obj.is_default,
            'last_used_at': obj.last_used_at,
            'total_spent': float(obj.total_spent or 0),
            'current_month_spent': float(obj.current_month_spent or 0),
            'current_day_spent': float(obj.current_day_spent or 0),
            'current_hour_requests': obj.current_hour_requests or 0,
            'total_requests': obj.total_requests or 0,
            'total_input_tokens': obj.total_input_tokens or 0,
            'total_output_tokens': obj.total_output_tokens or 0,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
            'created_by_user_id': obj.created_by_user_id,
            'api_key_preview': obj.get_masked_api_key() if hasattr(obj, 'get_masked_api_key') else "sk-***...***",
            'provider_display_name': obj.provider_display_name if hasattr(obj, 'provider_display_name') else "Unknown",
        }
        return cls(**data)


class PlatformProviderListResponse(BaseModel):
    """Schema for paginated list of platform providers."""
    providers: List[PlatformProviderResponse]
    total: int
    skip: int
    limit: int


# Provider Testing Schemas
class ProviderTestResponse(BaseModel):
    """Schema for provider test results."""
    provider_id: UUID
    provider_name: str
    success: bool
    response_time_ms: int
    response_text: str
    tokens_used: int
    cost_estimate: float
    error_message: Optional[str]
    tested_at: datetime


class ProviderHealthCheck(BaseModel):
    """Schema for provider health check results."""
    provider_id: UUID
    provider_name: str
    checked_at: datetime
    status: str = Field(..., description="healthy, degraded, unhealthy, or unknown")
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    budget_status: Dict[str, Any] = Field(default_factory=dict)
    recent_errors: List[str] = Field(default_factory=list)
    performance_metrics: Dict[str, float] = Field(default_factory=dict)


# Provider Statistics Schemas
class ProviderStatsResponse(BaseModel):
    """Schema for provider usage statistics."""
    provider_id: UUID
    provider_name: str
    stats_period_days: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: Decimal
    average_response_time_ms: float
    organizations_using: int
    success_rate: float = Field(..., description="Success rate as percentage")
    daily_stats: List[Dict[str, Any]] = Field(default_factory=list)


# Bulk Operations Schemas
class BulkProviderOperation(BaseModel):
    """Schema for bulk provider operations."""
    operation: str = Field(..., description="Operation type: activate, deactivate, test_all, update_priority")
    provider_ids: List[UUID] = Field(..., min_items=1, description="List of provider IDs")
    priority_updates: Optional[Dict[str, int]] = Field(None, description="Priority updates for update_priority operation")

    @validator('operation')
    def validate_operation(cls, v):
        allowed = ['activate', 'deactivate', 'test_all', 'update_priority']
        if v not in allowed:
            raise ValueError(f"Operation must be one of: {', '.join(allowed)}")
        return v


# Organization Usage Reporting Schemas
class OrganizationUsageFilter(BaseModel):
    """Schema for filtering organization usage reports."""
    organization_ids: Optional[List[UUID]] = Field(None, description="Filter by organization IDs")
    provider_ids: Optional[List[UUID]] = Field(None, description="Filter by platform provider IDs")
    date_from: Optional[datetime] = Field(None, description="Start date for filtering")
    date_to: Optional[datetime] = Field(None, description="End date for filtering")
    min_cost: Optional[Decimal] = Field(None, ge=0, description="Minimum cost threshold")
    max_cost: Optional[Decimal] = Field(None, ge=0, description="Maximum cost threshold")


class OrganizationUsageReport(BaseModel):
    """Schema for organization usage report."""
    organization_id: UUID
    organization_name: str
    period_start: datetime
    period_end: datetime
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: Decimal
    average_cost_per_request: Decimal
    providers_used: List[Dict[str, Any]]
    daily_breakdown: List[Dict[str, Any]]


class UsageReportResponse(BaseModel):
    """Schema for usage report response."""
    reports: List[OrganizationUsageReport]
    summary: Dict[str, Any]
    generated_at: datetime
    period_days: int
    total_organizations: int


# Budget Alert Configuration Schemas
class BudgetAlertCreate(BaseModel):
    """Schema for creating budget alerts."""
    platform_provider_id: UUID = Field(..., description="Platform provider ID (required)")
    organization_id: Optional[UUID] = Field(None, description="Organization ID (null for global)")
    alert_type: AlertType = Field(..., description="Type of budget alert")
    threshold_percentage: int = Field(..., ge=1, le=100, description="Threshold percentage")
    period: AlertPeriod = Field(AlertPeriod.MONTHLY, description="Alert period")
    is_active: bool = Field(True, description="Whether alert is active")
    # Notification settings
    notify_super_admins: bool = Field(True, description="Notify super admins")
    notify_org_admins: bool = Field(False, description="Notify organization admins")
    email_recipients: List[str] = Field(default_factory=list, description="Additional email recipients")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")
    slack_webhook_url: Optional[str] = Field(None, description="Slack webhook URL")
    # Rate limiting
    cooldown_minutes: int = Field(60, ge=1, description="Minutes between repeat alerts")
    max_triggers_per_day: int = Field(10, ge=1, description="Maximum triggers per day")
    custom_message: Optional[str] = Field(None, description="Custom alert message template")


class BudgetAlertUpdate(BaseModel):
    """Schema for updating budget alerts."""
    alert_type: Optional[AlertType] = Field(None)
    threshold_percentage: Optional[int] = Field(None, ge=1, le=100)
    period: Optional[AlertPeriod] = Field(None)
    is_active: Optional[bool] = Field(None)
    # Notification settings
    notify_super_admins: Optional[bool] = Field(None)
    notify_org_admins: Optional[bool] = Field(None)
    email_recipients: Optional[List[str]] = Field(None)
    webhook_url: Optional[str] = Field(None)
    slack_webhook_url: Optional[str] = Field(None)
    # Rate limiting
    cooldown_minutes: Optional[int] = Field(None, ge=1)
    max_triggers_per_day: Optional[int] = Field(None, ge=1)
    custom_message: Optional[str] = Field(None)


class BudgetAlertResponse(BaseModel):
    """Schema for budget alert response."""
    id: UUID
    platform_provider_id: UUID
    organization_id: Optional[UUID]
    # Provider and org names for display
    provider_name: Optional[str] = None
    organization_name: Optional[str] = None
    # Alert config
    alert_type: AlertType
    threshold_percentage: int
    period: AlertPeriod
    is_active: bool
    # Notification settings
    notify_super_admins: bool
    notify_org_admins: bool
    email_recipients: List[str]
    webhook_url: Optional[str]
    slack_webhook_url: Optional[str]
    # Rate limiting
    cooldown_minutes: int
    max_triggers_per_day: int
    custom_message: Optional[str]
    # Status
    last_triggered_at: Optional[datetime]
    trigger_count: int
    can_trigger: bool = True
    # Timestamps
    created_at: datetime
    updated_at: datetime
    # Metadata
    alert_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# Audit Log Schemas
class AuditLogFilter(BaseModel):
    """Schema for filtering audit logs."""
    user_ids: Optional[List[UUID]] = Field(None, description="Filter by user IDs")
    organization_ids: Optional[List[UUID]] = Field(None, description="Filter by organization IDs")
    event_types: Optional[List[AuditEventType]] = Field(None, description="Filter by event types")
    event_status: Optional[AuditEventStatus] = Field(None, description="Filter by event status")
    error_categories: Optional[List[ErrorCategory]] = Field(None, description="Filter by error categories")
    date_from: Optional[datetime] = Field(None, description="Start date")
    date_to: Optional[datetime] = Field(None, description="End date")
    provider_ids: Optional[List[UUID]] = Field(None, description="Filter by provider IDs")
    session_ids: Optional[List[str]] = Field(None, description="Filter by session IDs")


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""
    id: UUID
    user_id: Optional[UUID]
    organization_id: Optional[UUID]
    event_type: AuditEventType
    event_status: AuditEventStatus
    session_id: Optional[str]
    provider_type: Optional[str]
    provider_id: Optional[UUID]
    platform_provider_id: Optional[UUID]
    model_name: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    cost: Optional[Decimal]
    processing_time_ms: Optional[int]
    error_category: Optional[ErrorCategory]
    error_message: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_metadata: Optional[Dict[str, Any]]
    response_metadata: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log response."""
    logs: List[AuditLogResponse]
    total: int
    skip: int
    limit: int
    filters_applied: Dict[str, Any]


# System Notification Schemas
class SystemNotificationCreate(BaseModel):
    """Schema for creating system notifications."""
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    notification_type: NotificationType = Field(...)
    severity: NotificationSeverity = Field(...)
    target_user_id: Optional[UUID] = Field(None, description="Specific user (null for broadcast)")
    target_organization_id: Optional[UUID] = Field(None, description="Specific organization")
    target_role: Optional[str] = Field(None, description="Target user role")
    expires_at: Optional[datetime] = Field(None, description="Expiration time")
    action_url: Optional[str] = Field(None, description="Action URL for notification")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SystemNotificationResponse(BaseModel):
    """Schema for system notification response."""
    id: UUID
    title: str
    message: str
    notification_type: NotificationType
    severity: NotificationSeverity
    target_user_id: Optional[UUID]
    target_organization_id: Optional[UUID]
    target_role: Optional[str]
    is_read: bool
    expires_at: Optional[datetime]
    action_url: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schema for paginated notification response."""
    notifications: List[SystemNotificationResponse]
    total: int
    unread_count: int
    skip: int
    limit: int


# Backup Management Schemas
class ProviderBackupResponse(BaseModel):
    """Schema for provider backup response."""
    id: UUID
    platform_provider_id: UUID
    backup_type: str
    backup_reason: str
    backup_size_bytes: int
    integrity_hash: str
    retention_until: datetime
    created_at: datetime
    created_by: UUID

    class Config:
        from_attributes = True


class BackupListResponse(BaseModel):
    """Schema for backup list response."""
    backups: List[ProviderBackupResponse]
    total: int
    skip: int
    limit: int


class BackupRestoreRequest(BaseModel):
    """Schema for backup restore request."""
    backup_id: UUID
    restore_reason: str = Field(..., min_length=1, max_length=500)
    confirm_overwrite: bool = Field(False, description="Confirm overwrite of existing provider")