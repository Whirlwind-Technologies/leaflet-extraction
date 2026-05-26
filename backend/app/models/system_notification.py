"""
System Notification Model Module.

This module defines models for system-wide notifications displayed in the frontend
notification bell. Supports targeting by user, organization, or role requirements.

Example Usage:
    from app.models.system_notification import SystemNotification, NotificationType, NotificationSeverity

    notification = SystemNotification(
        notification_type=NotificationType.BUDGET_WARNING,
        title="Budget Alert",
        message="Platform provider budget at 90%",
        severity=NotificationSeverity.WARNING,
        organization_id=org_id
    )
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    ForeignKey,
    Index,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class NotificationType(str, enum.Enum):
    """
    System notification types.

    Attributes:
        BUDGET_WARNING: Budget threshold exceeded
        PROVIDER_FAILOVER: VLM provider failover occurred
        SYSTEM_ALERT: General system alert
        MAINTENANCE: Scheduled maintenance notification
        SECURITY_ALERT: Security-related alerts
        FEATURE_UPDATE: New feature announcements
        USAGE_REPORT: Usage reports and summaries
        API_KEY_EXPIRY: API key expiration warnings
        ORGANIZATION_UPDATE: Organization-related updates
        USER_ACTION_REQUIRED: Action required from user
    """
    BUDGET_WARNING = "budget_warning"
    PROVIDER_FAILOVER = "provider_failover"
    SYSTEM_ALERT = "system_alert"
    MAINTENANCE = "maintenance"
    SECURITY_ALERT = "security_alert"
    FEATURE_UPDATE = "feature_update"
    USAGE_REPORT = "usage_report"
    API_KEY_EXPIRY = "api_key_expiry"
    ORGANIZATION_UPDATE = "organization_update"
    USER_ACTION_REQUIRED = "user_action_required"


class NotificationSeverity(str, enum.Enum):
    """
    Notification severity levels.

    Attributes:
        INFO: Informational notification (blue)
        SUCCESS: Success notification (green)
        WARNING: Warning notification (yellow)
        ERROR: Error notification (red)
        CRITICAL: Critical alert (red with emphasis)
    """
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationSource(str, enum.Enum):
    """
    Notification source systems.

    Attributes:
        BUDGET_MONITOR: Budget monitoring system
        FAILOVER_SYSTEM: Provider failover system
        MANUAL: Manually created by admin
        SYSTEM: System-generated
        WEBHOOK: External webhook
        SCHEDULED: Scheduled task
    """
    BUDGET_MONITOR = "budget_monitor"
    FAILOVER_SYSTEM = "failover_system"
    MANUAL = "manual"
    SYSTEM = "system"
    WEBHOOK = "webhook"
    SCHEDULED = "scheduled"


class SystemNotification(Base):
    """
    System notification model for frontend notification bell.

    Supports flexible targeting by user, organization, or role requirement.
    Notifications can include action buttons and expire automatically.

    Attributes:
        id: Unique identifier (UUID)

        # Targeting
        user_id: Specific user (null = not user-specific)
        organization_id: Specific organization (null = platform-wide)
        role_requirement: Required role to see notification (admin, super_admin, member)

        # Content
        notification_type: Type of notification
        title: Notification title (shown in bell dropdown)
        message: Detailed message content
        severity: Visual severity level

        # Action
        action_url: URL to navigate when clicked
        action_text: Button text for action

        # Status
        is_read: Whether notification has been read
        is_dismissed: Whether notification has been dismissed
        expires_at: Automatic expiration timestamp

        # Metadata
        source_type: System that generated this notification
        source_id: Related entity ID (provider_id, alert_id, etc.)
        metadata: Additional structured data

        created_at: Creation timestamp
    """

    __tablename__ = "system_notifications"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Unique notification identifier"
    )

    # Targeting - at least one must be specified
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Specific user (null = not user-specific)"
    )

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Specific organization (null = platform-wide)"
    )

    role_requirement = Column(
        String(20),
        nullable=True,
        index=True,
        comment="Required role to see notification (admin, super_admin, member)"
    )

    # Notification Content
    notification_type = Column(
        Enum(
            NotificationType,
            values_callable=lambda x: [e.value for e in x],
            create_type=False
        ),
        nullable=False,
        index=True,
        comment="Type of notification"
    )

    title = Column(
        String(200),
        nullable=False,
        comment="Notification title (shown in bell dropdown)"
    )

    message = Column(
        Text,
        nullable=False,
        comment="Detailed message content"
    )

    severity = Column(
        Enum(
            NotificationSeverity,
            values_callable=lambda x: [e.value for e in x],
            create_type=False
        ),
        nullable=False,
        default=NotificationSeverity.INFO,
        comment="Visual severity level"
    )

    # Action Configuration
    action_url = Column(
        String(500),
        nullable=True,
        comment="URL to navigate when clicked"
    )

    action_text = Column(
        String(50),
        nullable=True,
        comment="Button text for action"
    )

    # Status Tracking
    is_read = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether notification has been read"
    )

    is_dismissed = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether notification has been dismissed"
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Automatic expiration timestamp"
    )

    # Source and Metadata
    source_type = Column(
        Enum(
            NotificationSource,
            values_callable=lambda x: [e.value for e in x],
            create_type=False
        ),
        nullable=False,
        default=NotificationSource.SYSTEM,
        comment="System that generated this notification"
    )

    source_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Related entity ID (provider_id, alert_id, etc.)"
    )

    notification_metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional structured data"
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        index=True,
        comment="Creation timestamp"
    )

    # Relationships
    user = relationship(
        "User",
        foreign_keys=[user_id],
        doc="Target user for this notification"
    )

    organization = relationship(
        "Organization",
        foreign_keys=[organization_id],
        doc="Target organization for this notification"
    )

    # Indexes
    __table_args__ = (
        Index("idx_notification_user_read_created", "user_id", "is_read", "created_at"),
        Index("idx_notification_org_read_created", "organization_id", "is_read", "created_at"),
        Index("idx_notification_role_read_created", "role_requirement", "is_read", "created_at"),
        Index("idx_notification_type_created", "notification_type", "created_at"),
        Index("idx_notification_severity_created", "severity", "created_at"),
        Index("idx_notification_expires", "expires_at"),
        Index("idx_notification_source", "source_type", "source_id"),
    )

    @property
    def is_expired(self) -> bool:
        """Check if notification has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_visible(self) -> bool:
        """Check if notification should be visible."""
        return not self.is_dismissed and not self.is_expired

    @property
    def severity_color(self) -> str:
        """Get color code for severity level."""
        colors = {
            NotificationSeverity.INFO: "blue",
            NotificationSeverity.SUCCESS: "green",
            NotificationSeverity.WARNING: "yellow",
            NotificationSeverity.ERROR: "red",
            NotificationSeverity.CRITICAL: "red",
        }
        return colors.get(self.severity, "gray")

    @property
    def severity_icon(self) -> str:
        """Get icon name for severity level."""
        icons = {
            NotificationSeverity.INFO: "info-circle",
            NotificationSeverity.SUCCESS: "check-circle",
            NotificationSeverity.WARNING: "exclamation-triangle",
            NotificationSeverity.ERROR: "x-circle",
            NotificationSeverity.CRITICAL: "exclamation-circle",
        }
        return icons.get(self.severity, "bell")

    def mark_read(self):
        """Mark notification as read."""
        self.is_read = True

    def mark_dismissed(self):
        """Mark notification as dismissed."""
        self.is_dismissed = True

    def to_dict(self, include_metadata: bool = False) -> dict:
        """Convert notification to dictionary for API responses."""
        result = {
            "id": str(self.id),
            "notification_type": self.notification_type.value,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "severity_color": self.severity_color,
            "severity_icon": self.severity_icon,
            "action_url": self.action_url,
            "action_text": self.action_text,
            "is_read": self.is_read,
            "is_dismissed": self.is_dismissed,
            "is_expired": self.is_expired,
            "is_visible": self.is_visible,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

        if include_metadata:
            result["metadata"] = self.notification_metadata
            result["source_type"] = self.source_type.value
            result["source_id"] = str(self.source_id) if self.source_id else None
            result["user_id"] = str(self.user_id) if self.user_id else None
            result["organization_id"] = str(self.organization_id) if self.organization_id else None
            result["role_requirement"] = self.role_requirement

        return result

    def __repr__(self) -> str:
        """String representation of SystemNotification."""
        target = "all"
        if self.user_id:
            target = f"user:{self.user_id}"
        elif self.organization_id:
            target = f"org:{self.organization_id}"
        elif self.role_requirement:
            target = f"role:{self.role_requirement}"

        return (
            f"<SystemNotification(id={self.id}, type={self.notification_type.value}, "
            f"target={target}, severity={self.severity.value}, "
            f"read={self.is_read}, dismissed={self.is_dismissed})>"
        )


class NotificationPreference(Base):
    """
    User notification preferences for controlling delivery.

    Allows users to control which types of notifications they receive
    and how they want to receive them.
    """

    __tablename__ = "notification_preferences"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique preference identifier"
    )

    # Target User
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="User these preferences belong to"
    )

    # Enabled Notification Types
    enabled_types = Column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="List of enabled notification types"
    )

    # Email Settings
    email_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether to send email notifications"
    )

    email_digest_frequency = Column(
        String(20),
        nullable=False,
        default="daily",
        comment="Email digest frequency (immediate, daily, weekly, never)"
    )

    # In-App Settings
    show_success_notifications = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Show success/info notifications in app"
    )

    auto_dismiss_after_seconds = Column(
        Integer,
        nullable=True,
        comment="Auto-dismiss notifications after N seconds (null = manual)"
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        comment="Creation timestamp"
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Last update timestamp"
    )

    # Relationships
    user = relationship(
        "User",
        back_populates="notification_preferences",
        doc="User these preferences belong to"
    )

    def is_type_enabled(self, notification_type: NotificationType) -> bool:
        """Check if a notification type is enabled for this user."""
        if self.enabled_types is None:
            return True  # Default to all enabled
        return notification_type.value in self.enabled_types

    def __repr__(self) -> str:
        """String representation of NotificationPreference."""
        return (
            f"<NotificationPreference(user_id={self.user_id}, "
            f"email_enabled={self.email_enabled}, "
            f"types_count={len(self.enabled_types or [])})>"
        )