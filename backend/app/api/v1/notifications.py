"""
User Notifications Endpoints.

This module provides endpoints for users to view and manage their notifications,
including notification preferences management.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.system_notification import (
    SystemNotification,
    NotificationType,
    NotificationPreference,
    NotificationSeverity,
)
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
router = APIRouter()


class NotificationResponse(BaseModel):
    """Response schema for notifications."""
    id: UUID
    notification_type: str
    title: str
    message: str
    severity: str
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True


class NotificationPreferencesResponse(BaseModel):
    """Response schema for notification preferences."""
    user_id: UUID
    enabled_types: List[str]
    email_enabled: bool
    email_digest_frequency: str
    show_success_notifications: bool
    auto_dismiss_after_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationPreferencesUpdate(BaseModel):
    """Schema for updating notification preferences."""
    enabled_types: Optional[List[str]] = Field(None, description="List of enabled notification types")
    email_enabled: Optional[bool] = Field(None, description="Enable email notifications")
    email_digest_frequency: Optional[str] = Field(None, description="Email digest frequency: immediate, daily, weekly, never")
    show_success_notifications: Optional[bool] = Field(None, description="Show success notifications in bell")
    auto_dismiss_after_seconds: Optional[int] = Field(None, ge=0, description="Auto-dismiss timeout in seconds (0 = never)")


# =============================================================================
# Fixed path routes (must come before parameterized routes)
# =============================================================================

@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="List user notifications",
    description="Get notifications for the current user.",
)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[NotificationResponse]:
    """List notifications for the current user."""
    # Get notifications for the user or their organization, or global notifications
    query = select(SystemNotification).where(
        or_(
            SystemNotification.user_id == current_user.id,
            SystemNotification.organization_id == current_user.default_organization_id,
            # Global notifications (no specific user or org)
            (SystemNotification.user_id.is_(None)) & (SystemNotification.organization_id.is_(None))
        )
    )

    if is_read is not None:
        query = query.where(SystemNotification.is_read == is_read)

    query = query.order_by(SystemNotification.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return [
        NotificationResponse(
            id=n.id,
            notification_type=n.notification_type.value,
            title=n.title,
            message=n.message,
            severity=n.severity.value,
            is_read=n.is_read,
            created_at=n.created_at,
            read_at=None,  # Model doesn't have read_at field
            metadata=n.notification_metadata,
        )
        for n in notifications
    ]


@router.get(
    "/unread-count",
    summary="Get unread notification count",
    description="Get count of unread notifications for the current user.",
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get unread notification count for the current user."""
    result = await db.execute(
        select(func.count(SystemNotification.id)).where(
            SystemNotification.is_read == False,
            or_(
                SystemNotification.user_id == current_user.id,
                SystemNotification.organization_id == current_user.default_organization_id,
                (SystemNotification.user_id.is_(None)) & (SystemNotification.organization_id.is_(None))
            )
        )
    )
    count = result.scalar() or 0
    return {"unread_count": count}


@router.post(
    "/mark-all-read",
    summary="Mark all notifications as read",
    description="Mark all notifications as read for the current user.",
)
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark all notifications as read for the current user."""
    result = await db.execute(
        select(SystemNotification).where(
            SystemNotification.is_read == False,
            or_(
                SystemNotification.user_id == current_user.id,
                SystemNotification.organization_id == current_user.default_organization_id,
                (SystemNotification.user_id.is_(None)) & (SystemNotification.organization_id.is_(None))
            )
        )
    )
    notifications = result.scalars().all()

    for notification in notifications:
        notification.is_read = True

    await db.commit()

    return {"message": f"Marked {len(notifications)} notifications as read"}


# =============================================================================
# Notification Preferences Endpoints (fixed paths)
# =============================================================================

@router.get(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Get notification preferences",
    description="Get the current user's notification preferences.",
)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Get notification preferences for the current user."""
    notification_service = NotificationService(db)
    preferences = await notification_service.get_user_preferences(current_user.id)

    return NotificationPreferencesResponse(
        user_id=preferences.user_id,
        enabled_types=preferences.enabled_types or [],
        email_enabled=preferences.email_enabled,
        email_digest_frequency=preferences.email_digest_frequency or "daily",
        show_success_notifications=preferences.show_success_notifications,
        auto_dismiss_after_seconds=preferences.auto_dismiss_after_seconds,
        created_at=preferences.created_at,
        updated_at=preferences.updated_at,
    )


@router.put(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Update notification preferences",
    description="Update the current user's notification preferences.",
)
async def update_preferences(
    preferences_data: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Update notification preferences for the current user."""
    notification_service = NotificationService(db)

    # Validate enabled_types if provided
    if preferences_data.enabled_types is not None:
        valid_types = [t.value for t in NotificationType]
        for t in preferences_data.enabled_types:
            if t not in valid_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid notification type: {t}. Valid types: {valid_types}"
                )

    # Validate email_digest_frequency if provided
    if preferences_data.email_digest_frequency is not None:
        valid_frequencies = ["immediate", "daily", "weekly", "never"]
        if preferences_data.email_digest_frequency not in valid_frequencies:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid frequency: {preferences_data.email_digest_frequency}. Valid: {valid_frequencies}"
            )

    preferences = await notification_service.update_user_preferences(
        user_id=current_user.id,
        enabled_types=preferences_data.enabled_types,
        email_enabled=preferences_data.email_enabled,
        email_digest_frequency=preferences_data.email_digest_frequency,
        show_success_notifications=preferences_data.show_success_notifications,
        auto_dismiss_after_seconds=preferences_data.auto_dismiss_after_seconds,
    )

    return NotificationPreferencesResponse(
        user_id=preferences.user_id,
        enabled_types=preferences.enabled_types or [],
        email_enabled=preferences.email_enabled,
        email_digest_frequency=preferences.email_digest_frequency or "daily",
        show_success_notifications=preferences.show_success_notifications,
        auto_dismiss_after_seconds=preferences.auto_dismiss_after_seconds,
        created_at=preferences.created_at,
        updated_at=preferences.updated_at,
    )


@router.get(
    "/types",
    summary="Get notification types",
    description="Get list of all available notification types.",
)
async def get_notification_types(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get all available notification types."""
    return {
        "types": [
            {
                "value": t.value,
                "name": t.name.replace("_", " ").title(),
                "description": _get_notification_type_description(t)
            }
            for t in NotificationType
        ]
    }


# =============================================================================
# Parameterized routes (must come after fixed path routes)
# =============================================================================

@router.post(
    "/{notification_id}/read",
    summary="Mark notification as read",
    description="Mark a notification as read.",
)
async def mark_as_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a notification as read."""
    result = await db.execute(
        select(SystemNotification).where(
            SystemNotification.id == notification_id,
            or_(
                SystemNotification.user_id == current_user.id,
                SystemNotification.organization_id == current_user.default_organization_id,
                (SystemNotification.user_id.is_(None)) & (SystemNotification.organization_id.is_(None))
            )
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    notification.is_read = True
    await db.commit()

    return {"message": "Notification marked as read"}


@router.post(
    "/{notification_id}/dismiss",
    summary="Dismiss notification",
    description="Dismiss a notification (hide from list).",
)
async def dismiss_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dismiss a notification."""
    result = await db.execute(
        select(SystemNotification).where(
            SystemNotification.id == notification_id,
            or_(
                SystemNotification.user_id == current_user.id,
                SystemNotification.organization_id == current_user.default_organization_id,
                (SystemNotification.user_id.is_(None)) & (SystemNotification.organization_id.is_(None))
            )
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    notification.is_dismissed = True
    notification.is_read = True
    await db.commit()

    return {"message": "Notification dismissed"}


# =============================================================================
# Helper functions
# =============================================================================

def _get_notification_type_description(notification_type: NotificationType) -> str:
    """Get description for a notification type."""
    descriptions = {
        NotificationType.BUDGET_WARNING: "Alerts when platform provider budget thresholds are exceeded",
        NotificationType.PROVIDER_FAILOVER: "Notifications when a VLM provider fails and switches to backup",
        NotificationType.SYSTEM_ALERT: "General system alerts and announcements",
        NotificationType.MAINTENANCE: "Scheduled maintenance notifications",
        NotificationType.SECURITY_ALERT: "Security-related notifications",
        NotificationType.FEATURE_UPDATE: "New feature announcements and updates",
        NotificationType.USAGE_REPORT: "Usage and analytics reports",
        NotificationType.API_KEY_EXPIRY: "API key expiration warnings",
        NotificationType.ORGANIZATION_UPDATE: "Organization changes and updates",
        NotificationType.USER_ACTION_REQUIRED: "Notifications requiring user action",
    }
    return descriptions.get(notification_type, "System notification")
