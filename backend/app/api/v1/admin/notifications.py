"""
Admin Notifications Endpoints.

This module provides endpoints for super admins to manage and broadcast
system notifications.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_superuser, get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.system_notification import (
    SystemNotification,
    NotificationType,
    NotificationSeverity,
    NotificationSource,
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
    is_dismissed: bool = False
    user_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None
    role_requirement: Optional[str] = None
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    """Schema for creating/broadcasting a notification."""
    notification_type: str = Field(..., description="Type of notification")
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    severity: str = Field("info", description="Severity: info, success, warning, error, critical")

    # Targeting - at least one must be specified or broadcast to all
    user_id: Optional[UUID] = Field(None, description="Target specific user")
    organization_id: Optional[UUID] = Field(None, description="Target specific organization")
    role_requirement: Optional[str] = Field(None, description="Target users with role: member, admin, super_admin")
    broadcast_to_all: bool = Field(False, description="Send to all users (ignores other targeting)")

    # Optional settings
    action_url: Optional[str] = Field(None, description="URL for action button")
    action_text: Optional[str] = Field(None, description="Text for action button")
    expires_in_hours: Optional[int] = Field(24, ge=1, le=720, description="Hours until expiration (max 30 days)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional structured data")


class BulkNotificationCreate(BaseModel):
    """Schema for creating notifications for multiple users."""
    notification_type: str = Field(..., description="Type of notification")
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    severity: str = Field("info")
    user_ids: List[UUID] = Field(..., min_items=1, max_items=100, description="List of user IDs")
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    expires_in_hours: Optional[int] = Field(24, ge=1, le=720)
    metadata: Optional[Dict[str, Any]] = None


@router.get(
    "",
    summary="List all notifications",
    description="Get all system notifications with filtering options.",
)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    notification_type: Optional[str] = Query(None, description="Filter by type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    is_dismissed: Optional[bool] = Query(None, description="Filter by dismissed status"),
    user_id: Optional[UUID] = Query(None, description="Filter by target user"),
    organization_id: Optional[UUID] = Query(None, description="Filter by target organization"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List all system notifications with pagination and filtering."""
    query = select(SystemNotification)
    conditions = []

    if notification_type:
        try:
            type_enum = NotificationType(notification_type)
            conditions.append(SystemNotification.notification_type == type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid notification type: {notification_type}"
            )

    if severity:
        try:
            severity_enum = NotificationSeverity(severity)
            conditions.append(SystemNotification.severity == severity_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity: {severity}"
            )

    if is_read is not None:
        conditions.append(SystemNotification.is_read == is_read)

    if is_dismissed is not None:
        conditions.append(SystemNotification.is_dismissed == is_dismissed)

    if user_id:
        conditions.append(SystemNotification.user_id == user_id)

    if organization_id:
        conditions.append(SystemNotification.organization_id == organization_id)

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count(SystemNotification.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.order_by(SystemNotification.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    notifications = result.scalars().all()

    items = [
        NotificationResponse(
            id=n.id,
            notification_type=n.notification_type.value,
            title=n.title,
            message=n.message,
            severity=n.severity.value,
            is_read=n.is_read,
            is_dismissed=n.is_dismissed,
            user_id=n.user_id,
            organization_id=n.organization_id,
            role_requirement=n.role_requirement,
            action_url=n.action_url,
            action_text=n.action_text,
            expires_at=n.expires_at,
            created_at=n.created_at,
            metadata=n.notification_metadata,
        )
        for n in notifications
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create notification",
    description="Create and broadcast a new system notification.",
)
async def create_notification(
    notification_data: NotificationCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new notification (broadcast or targeted)."""
    notification_service = NotificationService(db)

    # Validate notification type
    try:
        notification_type = NotificationType(notification_data.notification_type)
    except ValueError:
        valid_types = [t.value for t in NotificationType]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid notification type. Valid types: {valid_types}"
        )

    # Validate severity
    try:
        severity = NotificationSeverity(notification_data.severity)
    except ValueError:
        valid_severities = [s.value for s in NotificationSeverity]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity. Valid severities: {valid_severities}"
        )

    # Validate organization exists if specified
    if notification_data.organization_id:
        org_result = await db.execute(
            select(Organization).where(Organization.id == notification_data.organization_id)
        )
        if not org_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

    # Validate user exists if specified
    if notification_data.user_id:
        user_result = await db.execute(
            select(User).where(User.id == notification_data.user_id)
        )
        if not user_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

    # Determine targeting
    if notification_data.broadcast_to_all:
        # Platform-wide notification (all targeting is null)
        user_id = None
        organization_id = None
        role_requirement = None
    else:
        user_id = notification_data.user_id
        organization_id = notification_data.organization_id
        role_requirement = notification_data.role_requirement

        # Validate at least one targeting is specified
        if not any([user_id, organization_id, role_requirement]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one targeting parameter must be specified, or set broadcast_to_all=true"
            )

    try:
        notification = await notification_service.create_notification(
            notification_type=notification_type,
            title=notification_data.title,
            message=notification_data.message,
            user_id=user_id,
            organization_id=organization_id,
            role_requirement=role_requirement,
            severity=severity,
            action_url=notification_data.action_url,
            action_text=notification_data.action_text,
            source_type=NotificationSource.MANUAL,
            expires_in_hours=notification_data.expires_in_hours,
            metadata=notification_data.metadata,
        )

        logger.info(
            f"Admin {current_user.email} created notification: {notification.id} "
            f"type={notification_type.value}, broadcast={notification_data.broadcast_to_all}"
        )

        return {
            "id": str(notification.id),
            "notification_type": notification.notification_type.value,
            "title": notification.title,
            "message": notification.message,
            "severity": notification.severity.value,
            "user_id": str(notification.user_id) if notification.user_id else None,
            "organization_id": str(notification.organization_id) if notification.organization_id else None,
            "role_requirement": notification.role_requirement,
            "action_url": notification.action_url,
            "action_text": notification.action_text,
            "expires_at": notification.expires_at.isoformat() if notification.expires_at else None,
            "created_at": notification.created_at.isoformat(),
            "broadcast": notification_data.broadcast_to_all,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Create bulk notifications",
    description="Create notifications for multiple specific users.",
)
async def create_bulk_notifications(
    notification_data: BulkNotificationCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create notifications for multiple users at once."""
    notification_service = NotificationService(db)

    # Validate notification type
    try:
        notification_type = NotificationType(notification_data.notification_type)
    except ValueError:
        valid_types = [t.value for t in NotificationType]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid notification type. Valid types: {valid_types}"
        )

    # Validate severity
    try:
        severity = NotificationSeverity(notification_data.severity)
    except ValueError:
        valid_severities = [s.value for s in NotificationSeverity]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity. Valid severities: {valid_severities}"
        )

    # Verify all users exist
    user_result = await db.execute(
        select(User.id).where(User.id.in_(notification_data.user_ids))
    )
    found_user_ids = set(row[0] for row in user_result.fetchall())
    missing_users = set(notification_data.user_ids) - found_user_ids

    if missing_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Users not found: {[str(u) for u in missing_users]}"
        )

    # Create notifications for each user
    created_notifications = []
    errors = []

    for user_id in notification_data.user_ids:
        try:
            notification = await notification_service.create_notification(
                notification_type=notification_type,
                title=notification_data.title,
                message=notification_data.message,
                user_id=user_id,
                severity=severity,
                action_url=notification_data.action_url,
                action_text=notification_data.action_text,
                source_type=NotificationSource.MANUAL,
                expires_in_hours=notification_data.expires_in_hours,
                metadata=notification_data.metadata,
            )
            created_notifications.append(str(notification.id))
        except Exception as e:
            errors.append({"user_id": str(user_id), "error": str(e)})

    logger.info(
        f"Admin {current_user.email} created bulk notifications: "
        f"created={len(created_notifications)}, errors={len(errors)}"
    )

    return {
        "created_count": len(created_notifications),
        "notification_ids": created_notifications,
        "errors": errors if errors else None,
    }


@router.get(
    "/unread-count",
    summary="Get unread notification count",
    description="Get total count of unread notifications system-wide.",
)
async def get_unread_count(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get total unread notification count."""
    result = await db.execute(
        select(func.count(SystemNotification.id)).where(
            SystemNotification.is_read == False
        )
    )
    count = result.scalar() or 0
    return {"unread_count": count}


@router.get(
    "/stats",
    summary="Get notification statistics",
    description="Get statistics about notifications.",
)
async def get_notification_stats(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get notification statistics."""
    # Total count
    total_result = await db.execute(select(func.count(SystemNotification.id)))
    total = total_result.scalar() or 0

    # Unread count
    unread_result = await db.execute(
        select(func.count(SystemNotification.id)).where(SystemNotification.is_read == False)
    )
    unread = unread_result.scalar() or 0

    # Count by type
    type_result = await db.execute(
        select(
            SystemNotification.notification_type,
            func.count(SystemNotification.id)
        ).group_by(SystemNotification.notification_type)
    )
    by_type = {
        row[0].value: row[1]
        for row in type_result.fetchall()
    }

    # Count by severity
    severity_result = await db.execute(
        select(
            SystemNotification.severity,
            func.count(SystemNotification.id)
        ).group_by(SystemNotification.severity)
    )
    by_severity = {
        row[0].value: row[1]
        for row in severity_result.fetchall()
    }

    return {
        "total": total,
        "unread": unread,
        "read": total - unread,
        "by_type": by_type,
        "by_severity": by_severity,
    }


@router.get(
    "/{notification_id}",
    summary="Get notification details",
    description="Get details of a specific notification.",
)
async def get_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """Get a specific notification."""
    result = await db.execute(
        select(SystemNotification).where(SystemNotification.id == notification_id)
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    return NotificationResponse(
        id=notification.id,
        notification_type=notification.notification_type.value,
        title=notification.title,
        message=notification.message,
        severity=notification.severity.value,
        is_read=notification.is_read,
        is_dismissed=notification.is_dismissed,
        user_id=notification.user_id,
        organization_id=notification.organization_id,
        role_requirement=notification.role_requirement,
        action_url=notification.action_url,
        action_text=notification.action_text,
        expires_at=notification.expires_at,
        created_at=notification.created_at,
        metadata=notification.notification_metadata,
    )


@router.post(
    "/{notification_id}/read",
    summary="Mark notification as read",
    description="Mark a notification as read.",
)
async def mark_as_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a notification as read."""
    result = await db.execute(
        select(SystemNotification).where(SystemNotification.id == notification_id)
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
    "/mark-all-read",
    summary="Mark all notifications as read",
    description="Mark all notifications as read.",
)
async def mark_all_as_read(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark all notifications as read."""
    result = await db.execute(
        select(SystemNotification).where(SystemNotification.is_read == False)
    )
    notifications = result.scalars().all()

    for notification in notifications:
        notification.is_read = True

    await db.commit()

    return {"message": f"Marked {len(notifications)} notifications as read"}


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification",
    description="Delete a notification.",
)
async def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification."""
    result = await db.execute(
        select(SystemNotification).where(SystemNotification.id == notification_id)
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    delete_stmt = delete(SystemNotification).where(SystemNotification.id == notification_id)
    await db.execute(delete_stmt)
    await db.commit()

    logger.info(f"Admin {current_user.email} deleted notification: {notification_id}")


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete old notifications",
    description="Delete expired or old notifications.",
)
async def cleanup_notifications(
    days_old: int = Query(30, ge=1, le=365, description="Delete notifications older than this many days"),
    include_unread: bool = Query(False, description="Include unread notifications in cleanup"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Clean up old notifications."""
    notification_service = NotificationService(db)

    # Use service method for cleanup
    deleted_count = await notification_service.cleanup_expired_notifications(days_old=days_old)

    logger.info(
        f"Admin {current_user.email} cleaned up notifications: "
        f"deleted={deleted_count}, days_old={days_old}"
    )

    return {"deleted_count": deleted_count}
