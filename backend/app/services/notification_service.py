"""
Notification Service Module.

This service manages system notifications for the frontend notification bell,
including creation, delivery, user preferences, and cleanup.

Example Usage:
    from app.services.notification_service import NotificationService

    service = NotificationService(db_session)
    await service.create_notification(
        notification_type=NotificationType.BUDGET_WARNING,
        title="Budget Alert",
        message="Platform provider approaching budget limit",
        severity=NotificationSeverity.WARNING,
        role_requirement="super_admin"
    )
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Union

from sqlalchemy import select, update, delete, and_, or_, func, desc
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_notification import (
    SystemNotification,
    NotificationPreference,
    NotificationType,
    NotificationSeverity,
    NotificationSource
)
from app.models.user import User
from app.models.organization import Organization
from app.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for managing system notifications and user preferences.

    This service handles:
    - Creating and sending notifications
    - Managing user preferences
    - Filtering notifications by targeting rules
    - Email digest functionality
    - Cleanup of expired notifications
    """

    def __init__(self, db_session: Session):
        """
        Initialize the notification service.

        Args:
            db_session: Database session (sync or async)
        """
        self.db = db_session

    @property
    def _is_async(self) -> bool:
        """Check if the database session is async."""
        return isinstance(self.db, AsyncSession)

    async def create_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        user_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        role_requirement: Optional[str] = None,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None,
        source_type: NotificationSource = NotificationSource.SYSTEM,
        source_id: Optional[uuid.UUID] = None,
        expires_in_hours: Optional[int] = 24,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SystemNotification:
        """
        Create a new system notification.

        Args:
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            user_id: Target specific user (optional)
            organization_id: Target specific organization (optional)
            role_requirement: Required role to see notification (optional)
            severity: Notification severity level
            action_url: URL for action button (optional)
            action_text: Text for action button (optional)
            source_type: System that generated the notification
            source_id: Related entity ID (optional)
            expires_in_hours: Hours until expiration (optional)
            metadata: Additional structured data (optional)

        Returns:
            SystemNotification: Created notification

        Raises:
            ValueError: If targeting parameters are invalid
        """
        # Validate targeting - at least one target must be specified
        if not any([user_id, organization_id, role_requirement]):
            raise ValueError("At least one targeting parameter must be specified")

        # Calculate expiration
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        notification = SystemNotification(
            user_id=user_id,
            organization_id=organization_id,
            role_requirement=role_requirement,
            notification_type=notification_type,
            title=title,
            message=message,
            severity=severity,
            action_url=action_url,
            action_text=action_text,
            source_type=source_type,
            source_id=source_id,
            expires_at=expires_at,
            notification_metadata=metadata or {}
        )

        self.db.add(notification)

        if self._is_async:
            await self.db.commit()
        else:
            self.db.commit()

        logger.info(
            f"Created notification {notification.id}: {notification_type.value} "
            f"for user={user_id}, org={organization_id}, role={role_requirement}"
        )

        return notification

    async def get_user_notifications(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
        include_dismissed: bool = False
    ) -> List[SystemNotification]:
        """
        Get notifications for a specific user.

        Args:
            user_id: User to get notifications for
            unread_only: Only return unread notifications
            limit: Maximum number of notifications to return
            offset: Number of notifications to skip
            include_dismissed: Include dismissed notifications

        Returns:
            List[SystemNotification]: User's notifications
        """
        # Get user and their organization memberships
        user_orgs = await self._get_user_organizations(user_id)
        user_roles = await self._get_user_roles(user_id)

        # Build query conditions
        conditions = []

        # Direct user targeting
        conditions.append(SystemNotification.user_id == user_id)

        # Organization targeting
        if user_orgs:
            conditions.append(
                and_(
                    SystemNotification.organization_id.in_(user_orgs),
                    SystemNotification.user_id.is_(None)
                )
            )

        # Role-based targeting
        if user_roles:
            conditions.append(
                and_(
                    SystemNotification.role_requirement.in_(user_roles),
                    SystemNotification.user_id.is_(None),
                    SystemNotification.organization_id.is_(None)
                )
            )

        # Platform-wide notifications (all nulls)
        conditions.append(
            and_(
                SystemNotification.user_id.is_(None),
                SystemNotification.organization_id.is_(None),
                SystemNotification.role_requirement.is_(None)
            )
        )

        # Main query
        query = (
            select(SystemNotification)
            .where(or_(*conditions))
            .order_by(desc(SystemNotification.created_at))
            .limit(limit)
            .offset(offset)
        )

        # Additional filters
        if unread_only:
            query = query.where(SystemNotification.is_read == False)

        if not include_dismissed:
            query = query.where(SystemNotification.is_dismissed == False)

        # Exclude expired notifications
        query = query.where(
            or_(
                SystemNotification.expires_at.is_(None),
                SystemNotification.expires_at > datetime.now(timezone.utc)
            )
        )

        if self._is_async:
            result = await self.db.execute(query)
        else:
            result = self.db.execute(query)

        notifications = result.scalars().all()

        # Filter by user preferences
        filtered_notifications = await self._filter_by_preferences(user_id, notifications)

        return filtered_notifications

    async def get_unread_count(self, user_id: uuid.UUID) -> int:
        """
        Get count of unread notifications for a user.

        Args:
            user_id: User to count notifications for

        Returns:
            int: Number of unread notifications
        """
        notifications = await self.get_user_notifications(
            user_id=user_id,
            unread_only=True,
            limit=1000,  # High limit for accurate count
            include_dismissed=False
        )
        return len(notifications)

    async def mark_notification_read(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        Mark a notification as read for a specific user.

        Args:
            notification_id: Notification to mark as read
            user_id: User marking the notification

        Returns:
            bool: True if notification was marked read, False if not found/accessible
        """
        # Verify user has access to this notification
        notifications = await self.get_user_notifications(user_id, limit=1000)
        notification_ids = [n.id for n in notifications]

        if notification_id not in notification_ids:
            return False

        # Update the notification
        if self._is_async:
            result = await self.db.execute(
                update(SystemNotification)
                .where(SystemNotification.id == notification_id)
                .values(is_read=True)
            )
            await self.db.commit()
        else:
            result = self.db.execute(
                update(SystemNotification)
                .where(SystemNotification.id == notification_id)
                .values(is_read=True)
            )
            self.db.commit()

        return result.rowcount > 0

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        """
        Mark all notifications as read for a user.

        Args:
            user_id: User to mark notifications for

        Returns:
            int: Number of notifications marked as read
        """
        # Get all accessible notification IDs for the user
        notifications = await self.get_user_notifications(
            user_id,
            unread_only=True,
            limit=1000,
            include_dismissed=False
        )
        notification_ids = [n.id for n in notifications]

        if not notification_ids:
            return 0

        # Update all accessible notifications
        if self._is_async:
            result = await self.db.execute(
                update(SystemNotification)
                .where(SystemNotification.id.in_(notification_ids))
                .values(is_read=True)
            )
            await self.db.commit()
        else:
            result = self.db.execute(
                update(SystemNotification)
                .where(SystemNotification.id.in_(notification_ids))
                .values(is_read=True)
            )
            self.db.commit()

        return result.rowcount

    async def dismiss_notification(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        Dismiss a notification for a specific user.

        Args:
            notification_id: Notification to dismiss
            user_id: User dismissing the notification

        Returns:
            bool: True if notification was dismissed, False if not found/accessible
        """
        # Verify user has access to this notification
        notifications = await self.get_user_notifications(user_id, limit=1000)
        notification_ids = [n.id for n in notifications]

        if notification_id not in notification_ids:
            return False

        # Update the notification
        if self._is_async:
            result = await self.db.execute(
                update(SystemNotification)
                .where(SystemNotification.id == notification_id)
                .values(is_dismissed=True, is_read=True)
            )
            await self.db.commit()
        else:
            result = self.db.execute(
                update(SystemNotification)
                .where(SystemNotification.id == notification_id)
                .values(is_dismissed=True, is_read=True)
            )
            self.db.commit()

        return result.rowcount > 0

    async def get_user_preferences(self, user_id: uuid.UUID) -> NotificationPreference:
        """
        Get notification preferences for a user, creating defaults if none exist.

        Args:
            user_id: User to get preferences for

        Returns:
            NotificationPreference: User's notification preferences
        """
        if self._is_async:
            result = await self.db.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            )
        else:
            result = self.db.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            )

        preferences = result.scalar_one_or_none()

        if not preferences:
            # Create default preferences
            preferences = NotificationPreference(
                user_id=user_id,
                enabled_types=[t.value for t in NotificationType],  # All types enabled by default
                email_enabled=True,
                email_digest_frequency="daily",
                show_success_notifications=True
            )
            self.db.add(preferences)

            if self._is_async:
                await self.db.commit()
            else:
                self.db.commit()

        return preferences

    async def update_user_preferences(
        self,
        user_id: uuid.UUID,
        enabled_types: Optional[List[str]] = None,
        email_enabled: Optional[bool] = None,
        email_digest_frequency: Optional[str] = None,
        show_success_notifications: Optional[bool] = None,
        auto_dismiss_after_seconds: Optional[int] = None
    ) -> NotificationPreference:
        """
        Update user notification preferences.

        Args:
            user_id: User to update preferences for
            enabled_types: List of enabled notification type strings
            email_enabled: Whether email notifications are enabled
            email_digest_frequency: Email digest frequency
            show_success_notifications: Whether to show success notifications
            auto_dismiss_after_seconds: Auto-dismiss timeout

        Returns:
            NotificationPreference: Updated preferences
        """
        preferences = await self.get_user_preferences(user_id)

        # Update provided values
        if enabled_types is not None:
            preferences.enabled_types = enabled_types
        if email_enabled is not None:
            preferences.email_enabled = email_enabled
        if email_digest_frequency is not None:
            preferences.email_digest_frequency = email_digest_frequency
        if show_success_notifications is not None:
            preferences.show_success_notifications = show_success_notifications
        if auto_dismiss_after_seconds is not None:
            preferences.auto_dismiss_after_seconds = auto_dismiss_after_seconds

        preferences.updated_at = datetime.now(timezone.utc)

        if self._is_async:
            await self.db.commit()
        else:
            self.db.commit()

        return preferences

    async def send_budget_warning_notification(
        self,
        provider_name: str,
        organization_id: Optional[uuid.UUID],
        usage_percentage: float,
        budget_amount: float,
        current_usage: float,
        period: str = "monthly"
    ) -> SystemNotification:
        """
        Send a budget warning notification.

        Args:
            provider_name: Name of the platform provider
            organization_id: Organization context (optional)
            usage_percentage: Current usage percentage
            budget_amount: Total budget amount
            current_usage: Current usage amount
            period: Budget period (monthly, daily, hourly)

        Returns:
            SystemNotification: Created notification
        """
        # Determine severity based on usage percentage
        if usage_percentage >= 100:
            severity = NotificationSeverity.CRITICAL
            title = "Budget Exhausted"
            notification_type = NotificationType.BUDGET_WARNING
        elif usage_percentage >= 90:
            severity = NotificationSeverity.ERROR
            title = "Critical Budget Alert"
            notification_type = NotificationType.BUDGET_WARNING
        else:
            severity = NotificationSeverity.WARNING
            title = "Budget Warning"
            notification_type = NotificationType.BUDGET_WARNING

        message = (
            f"Platform provider '{provider_name}' has used {usage_percentage:.1f}% "
            f"of its {period} budget (${current_usage:.2f} / ${budget_amount:.2f})"
        )

        # Determine targeting
        if organization_id:
            # Organization-specific alert - notify org admins
            role_requirement = None
            target_org_id = organization_id
        else:
            # Platform-wide alert - notify super admins
            role_requirement = "super_admin"
            target_org_id = None

        return await self.create_notification(
            notification_type=notification_type,
            title=title,
            message=message,
            organization_id=target_org_id,
            role_requirement=role_requirement,
            severity=severity,
            action_url="/admin/platform-providers",
            action_text="View Providers",
            source_type=NotificationSource.BUDGET_MONITOR,
            expires_in_hours=48,
            metadata={
                'provider_name': provider_name,
                'usage_percentage': usage_percentage,
                'budget_amount': budget_amount,
                'current_usage': current_usage,
                'period': period
            }
        )

    async def send_provider_failover_notification(
        self,
        failed_provider_name: str,
        new_provider_name: str,
        organization_id: Optional[uuid.UUID],
        failure_reason: str
    ) -> SystemNotification:
        """
        Send a provider failover notification.

        Args:
            failed_provider_name: Name of the failed provider
            new_provider_name: Name of the new provider
            organization_id: Organization context (optional)
            failure_reason: Reason for the failover

        Returns:
            SystemNotification: Created notification
        """
        message = (
            f"Platform provider '{failed_provider_name}' failed and has been "
            f"automatically switched to '{new_provider_name}'. "
            f"Reason: {failure_reason}"
        )

        return await self.create_notification(
            notification_type=NotificationType.PROVIDER_FAILOVER,
            title="Provider Failover",
            message=message,
            organization_id=organization_id,
            role_requirement="super_admin" if not organization_id else None,
            severity=NotificationSeverity.WARNING,
            action_url="/admin/platform-providers",
            action_text="View Providers",
            source_type=NotificationSource.FAILOVER_SYSTEM,
            expires_in_hours=24,
            metadata={
                'failed_provider': failed_provider_name,
                'new_provider': new_provider_name,
                'failure_reason': failure_reason
            }
        )

    async def cleanup_expired_notifications(self, days_old: int = 30) -> int:
        """
        Clean up old and expired notifications.

        Args:
            days_old: Delete notifications older than this many days

        Returns:
            int: Number of notifications deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

        # Delete notifications that are either expired or very old
        if self._is_async:
            result = await self.db.execute(
                delete(SystemNotification).where(
                    or_(
                        SystemNotification.expires_at < datetime.now(timezone.utc),
                        SystemNotification.created_at < cutoff_date
                    )
                )
            )
            await self.db.commit()
        else:
            result = self.db.execute(
                delete(SystemNotification).where(
                    or_(
                        SystemNotification.expires_at < datetime.now(timezone.utc),
                        SystemNotification.created_at < cutoff_date
                    )
                )
            )
            self.db.commit()

        deleted_count = result.rowcount
        logger.info(f"Cleaned up {deleted_count} expired/old notifications")
        return deleted_count

    # Private helper methods

    async def _get_user_organizations(self, user_id: uuid.UUID) -> List[uuid.UUID]:
        """Get list of organization IDs the user belongs to."""
        # This would need to be implemented based on your organization membership logic
        # For now, we'll use a simple approach
        if self._is_async:
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
        else:
            result = self.db.execute(
                select(User).where(User.id == user_id)
            )

        user = result.scalar_one_or_none()
        if user and user.default_organization_id:
            return [user.default_organization_id]
        return []

    async def _get_user_roles(self, user_id: uuid.UUID) -> List[str]:
        """Get list of roles the user has."""
        # This would need to be implemented based on your role system
        # For now, return basic roles
        if self._is_async:
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
        else:
            result = self.db.execute(
                select(User).where(User.id == user_id)
            )

        user = result.scalar_one_or_none()
        if user:
            roles = ["member"]
            if user.is_superuser:
                roles.append("super_admin")
            # Add organization-specific roles here based on your logic
            return roles
        return []

    async def _filter_by_preferences(
        self,
        user_id: uuid.UUID,
        notifications: List[SystemNotification]
    ) -> List[SystemNotification]:
        """Filter notifications based on user preferences."""
        try:
            preferences = await self.get_user_preferences(user_id)

            if not preferences.enabled_types:
                return notifications  # If no preferences, show all

            filtered = []
            for notification in notifications:
                # Check if notification type is enabled
                if notification.notification_type.value in preferences.enabled_types:
                    # Check success notification preference
                    if (notification.severity == NotificationSeverity.SUCCESS and
                        not preferences.show_success_notifications):
                        continue
                    filtered.append(notification)

            return filtered

        except Exception as e:
            logger.warning(f"Error filtering notifications by preferences: {e}")
            return notifications  # Return unfiltered if error occurs

    # Email and Webhook Delivery Methods

    async def send_email_notification(
        self,
        notification: SystemNotification,
        recipient_email: str
    ) -> Dict[str, Any]:
        """
        Send email notification to a recipient.

        Args:
            notification: The notification to send
            recipient_email: Email address to send to

        Returns:
            Dict with delivery status
        """
        try:
            import httpx
            from app.config import settings

            # Pydantic Settings attributes are lowercase. The previous
            # code referenced uppercase names (SMTP_HOST etc.) which
            # always returned None on the lowercase Settings object —
            # silently disabling every notification email regardless of
            # configuration.
            if not settings.smtp_enabled or not settings.smtp_host:
                logger.warning("Email not configured - smtp_enabled false or smtp_host empty")
                return {"status": "skipped", "reason": "Email not configured"}

            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            smtp_host = settings.smtp_host
            smtp_port = settings.smtp_port or 587
            smtp_user = settings.smtp_user
            smtp_password = settings.smtp_password
            from_email = settings.smtp_from_email or 'info@leafxtract.com'

            if not all([smtp_host, smtp_user, smtp_password]):
                return {"status": "skipped", "reason": "SMTP credentials not configured"}

            # Create email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{notification.severity.value.upper()}] {notification.title}"
            msg['From'] = from_email
            msg['To'] = recipient_email

            # Plain text version
            text_content = f"""
{notification.title}

{notification.message}

Severity: {notification.severity.value}
Type: {notification.notification_type.value}
"""
            if notification.action_url:
                text_content += f"\nAction: {notification.action_url}"

            # HTML version
            severity_color = {
                'info': '#3b82f6',
                'success': '#22c55e',
                'warning': '#f59e0b',
                'error': '#ef4444',
                'critical': '#dc2626',
            }.get(notification.severity.value, '#6b7280')

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {severity_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 20px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: {severity_color}; color: white; padding: 10px 20px;
                   text-decoration: none; border-radius: 4px; margin-top: 15px; }}
        .footer {{ margin-top: 20px; font-size: 12px; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">{notification.title}</h2>
        </div>
        <div class="content">
            <p>{notification.message}</p>
            <p><strong>Severity:</strong> {notification.severity.value.title()}</p>
            <p><strong>Type:</strong> {notification.notification_type.value.replace('_', ' ').title()}</p>
            {"<a href='" + notification.action_url + "' class='button'>" + (notification.action_text or 'View Details') + "</a>" if notification.action_url else ""}
        </div>
        <div class="footer">
            <p>This is an automated notification from Leaflet Extraction Platform.</p>
        </div>
    </div>
</body>
</html>
"""

            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            # Send email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(from_email, recipient_email, msg.as_string())

            logger.info(f"Email notification sent to {recipient_email} for notification {notification.id}")
            return {"status": "sent", "recipient": recipient_email}

        except Exception as e:
            logger.exception(f"Failed to send email notification: {e}")
            return {"status": "failed", "error": str(e)}

    async def send_webhook_notification(
        self,
        notification: SystemNotification,
        webhook_url: str,
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send notification to a webhook URL.

        Args:
            notification: The notification to send
            webhook_url: URL to send the webhook to
            secret: Optional secret for HMAC signature

        Returns:
            Dict with delivery status
        """
        try:
            import httpx
            import hashlib
            import hmac
            import json

            # Build payload
            payload = {
                "event": "notification",
                "notification": {
                    "id": str(notification.id),
                    "type": notification.notification_type.value,
                    "title": notification.title,
                    "message": notification.message,
                    "severity": notification.severity.value,
                    "action_url": notification.action_url,
                    "action_text": notification.action_text,
                    "metadata": notification.notification_metadata or {},
                    "created_at": notification.created_at.isoformat(),
                    "expires_at": notification.expires_at.isoformat() if notification.expires_at else None,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "LeafletExtraction-NotificationService/1.0",
            }

            # Add HMAC signature if secret is provided
            if secret:
                payload_bytes = json.dumps(payload, sort_keys=True).encode()
                signature = hmac.new(
                    secret.encode(),
                    payload_bytes,
                    hashlib.sha256
                ).hexdigest()
                headers["X-Webhook-Signature"] = f"sha256={signature}"

            # Send webhook
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                )

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Webhook notification sent to {webhook_url} for notification {notification.id}")
                return {
                    "status": "sent",
                    "url": webhook_url,
                    "status_code": response.status_code,
                }
            else:
                logger.warning(
                    f"Webhook notification failed: {webhook_url} returned {response.status_code}"
                )
                return {
                    "status": "failed",
                    "url": webhook_url,
                    "status_code": response.status_code,
                    "response": response.text[:500],
                }

        except httpx.TimeoutException:
            logger.warning(f"Webhook notification timed out: {webhook_url}")
            return {"status": "failed", "error": "timeout", "url": webhook_url}
        except Exception as e:
            logger.exception(f"Failed to send webhook notification: {e}")
            return {"status": "failed", "error": str(e), "url": webhook_url}

    async def send_notification_to_channels(
        self,
        notification: SystemNotification,
        email_recipients: Optional[List[str]] = None,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send notification through multiple channels.

        Args:
            notification: The notification to send
            email_recipients: List of email addresses
            webhook_url: Webhook URL
            webhook_secret: Webhook secret for signing

        Returns:
            Dict with results from each channel
        """
        results = {}

        # Send emails
        if email_recipients:
            email_results = []
            for email in email_recipients:
                result = await self.send_email_notification(notification, email)
                email_results.append(result)
            results["email"] = {
                "sent": len([r for r in email_results if r.get("status") == "sent"]),
                "failed": len([r for r in email_results if r.get("status") == "failed"]),
                "details": email_results,
            }

        # Send webhook
        if webhook_url:
            results["webhook"] = await self.send_webhook_notification(
                notification, webhook_url, webhook_secret
            )

        return results

    async def publish_notification_to_websocket(
        self,
        notification: SystemNotification
    ) -> bool:
        """
        Publish a notification to Redis for WebSocket delivery.

        Args:
            notification: The notification to publish

        Returns:
            bool: True if published successfully
        """
        try:
            import redis.asyncio as aioredis
            import json

            redis_client = aioredis.from_url(settings.redis_url)

            # Build the message
            message = json.dumps({
                "type": "notification",
                "notification": {
                    "id": str(notification.id),
                    "notification_type": notification.notification_type.value,
                    "title": notification.title,
                    "message": notification.message,
                    "severity": notification.severity.value,
                    "action_url": notification.action_url,
                    "action_text": notification.action_text,
                    "created_at": notification.created_at.isoformat(),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Determine which channels to publish to
            channels = []

            if notification.user_id:
                # User-specific notification
                channels.append(f"notifications:user:{notification.user_id}")
            elif notification.organization_id:
                # Organization notification - publish to org channel
                channels.append(f"notifications:org:{notification.organization_id}")
            elif notification.role_requirement:
                # Role-based notification - publish to role channel
                channels.append(f"notifications:role:{notification.role_requirement}")
            else:
                # Global notification
                channels.append("notifications:global")

            # Publish to all relevant channels
            for channel in channels:
                await redis_client.publish(channel, message)

            await redis_client.close()

            logger.debug(f"Published notification {notification.id} to channels: {channels}")
            return True

        except Exception as e:
            logger.exception(f"Failed to publish notification to WebSocket: {e}")
            return False

    async def create_and_publish_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        user_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        role_requirement: Optional[str] = None,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None,
        source_type: NotificationSource = NotificationSource.SYSTEM,
        source_id: Optional[uuid.UUID] = None,
        expires_in_hours: Optional[int] = 24,
        metadata: Optional[Dict[str, Any]] = None,
        email_recipients: Optional[List[str]] = None,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a notification and publish it through all channels.

        This is the main method for creating notifications with full delivery.
        It creates the notification in the database, publishes to WebSocket,
        and optionally sends email/webhook notifications.

        Returns:
            Dict with notification details and delivery results
        """
        # Create the notification
        notification = await self.create_notification(
            notification_type=notification_type,
            title=title,
            message=message,
            user_id=user_id,
            organization_id=organization_id,
            role_requirement=role_requirement,
            severity=severity,
            action_url=action_url,
            action_text=action_text,
            source_type=source_type,
            source_id=source_id,
            expires_in_hours=expires_in_hours,
            metadata=metadata,
        )

        # Publish to WebSocket
        websocket_published = await self.publish_notification_to_websocket(notification)

        # Send to external channels
        channel_results = await self.send_notification_to_channels(
            notification=notification,
            email_recipients=email_recipients,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )

        return {
            "notification_id": str(notification.id),
            "notification_type": notification.notification_type.value,
            "title": notification.title,
            "severity": notification.severity.value,
            "websocket_published": websocket_published,
            "channel_results": channel_results,
        }