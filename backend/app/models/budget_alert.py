"""
Budget Alert Model Module.

This module defines models for configurable budget alerts and warnings
for platform VLM providers and organizations.

Example Usage:
    from app.models.budget_alert import BudgetAlert, AlertType, AlertPeriod

    alert = BudgetAlert(
        platform_provider_id=provider_id,
        alert_type=AlertType.WARNING,
        threshold_percentage=80,
        period=AlertPeriod.MONTHLY,
        notify_super_admins=True
    )
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base


class AlertType(str, enum.Enum):
    """
    Budget alert severity types.

    Attributes:
        WARNING: Early warning alert (typically 80%)
        CRITICAL: Critical threshold alert (typically 90-95%)
        EXHAUSTED: Budget completely exhausted (100%)
        RATE_LIMIT: Rate limit threshold reached
    """
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"
    RATE_LIMIT = "rate_limit"


class AlertPeriod(str, enum.Enum):
    """
    Budget monitoring periods.

    Attributes:
        DAILY: Daily budget monitoring
        MONTHLY: Monthly budget monitoring
        HOURLY: Hourly rate limit monitoring
    """
    DAILY = "daily"
    MONTHLY = "monthly"
    HOURLY = "hourly"


class BudgetAlert(Base):
    """
    Configurable budget alerts for platform providers and organizations.

    This model defines alert rules that trigger notifications when budget
    thresholds are exceeded or rate limits are approached.

    Attributes:
        id: Unique identifier (UUID)

        # Alert Scope
        platform_provider_id: Platform provider to monitor (required)
        organization_id: Specific organization to monitor (optional)

        # Alert Configuration
        alert_type: Type/severity of alert
        threshold_percentage: Percentage threshold (0-100)
        period: Monitoring period (daily, monthly, hourly)

        # Status
        is_active: Whether this alert is active
        last_triggered_at: Last time this alert was triggered
        trigger_count: Number of times this alert has been triggered

        # Notification Settings
        notify_super_admins: Send notifications to super admins
        notify_org_admins: Send notifications to organization admins
        email_recipients: Additional email addresses to notify
        webhook_url: Webhook URL for external notifications
        slack_webhook_url: Slack webhook for team notifications

        # Cooldown and Rate Limiting
        cooldown_minutes: Minimum minutes between notifications
        max_triggers_per_day: Maximum triggers per day before disabling

        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "budget_alerts"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique alert identifier"
    )

    # Alert Scope
    platform_provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("platform_vlm_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Platform provider to monitor"
    )

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Specific organization to monitor (null = all organizations)"
    )

    # Alert Configuration
    alert_type = Column(
        Enum(AlertType, values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
        comment="Type/severity of alert"
    )

    threshold_percentage = Column(
        Integer,
        nullable=False,
        comment="Percentage threshold (0-100)"
    )

    period = Column(
        Enum(AlertPeriod, values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
        comment="Monitoring period (daily, monthly, hourly)"
    )

    # Status Tracking
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this alert is active"
    )

    last_triggered_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time this alert was triggered"
    )

    trigger_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times this alert has been triggered"
    )

    # Notification Settings
    notify_super_admins = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Send notifications to super admins"
    )

    notify_org_admins = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Send notifications to organization admins"
    )

    email_recipients = Column(
        ARRAY(String),
        nullable=True,
        comment="Additional email addresses to notify"
    )

    webhook_url = Column(
        String(500),
        nullable=True,
        comment="Webhook URL for external notifications"
    )

    slack_webhook_url = Column(
        String(500),
        nullable=True,
        comment="Slack webhook for team notifications"
    )

    # Rate Limiting and Cooldown
    cooldown_minutes = Column(
        Integer,
        nullable=False,
        default=60,
        comment="Minimum minutes between notifications"
    )

    max_triggers_per_day = Column(
        Integer,
        nullable=False,
        default=10,
        comment="Maximum triggers per day before auto-disabling"
    )

    # Custom Alert Settings
    custom_message = Column(
        Text,
        nullable=True,
        comment="Custom alert message template"
    )

    alert_metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional alert configuration"
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
    platform_provider = relationship(
        "PlatformVLMProvider",
        doc="Platform provider being monitored"
    )

    organization = relationship(
        "Organization",
        doc="Organization being monitored (if specific)"
    )

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("threshold_percentage >= 0 AND threshold_percentage <= 100", name="check_threshold_range"),
        CheckConstraint("cooldown_minutes >= 0", name="check_cooldown_non_negative"),
        CheckConstraint("max_triggers_per_day > 0", name="check_max_triggers_positive"),
        CheckConstraint("trigger_count >= 0", name="check_trigger_count_non_negative"),

        Index("idx_budget_alert_provider_active", "platform_provider_id", "is_active"),
        Index("idx_budget_alert_org_active", "organization_id", "is_active"),
        Index("idx_budget_alert_type_period", "alert_type", "period"),
        Index("idx_budget_alert_threshold", "threshold_percentage"),
        Index("idx_budget_alert_last_triggered", "last_triggered_at"),
    )

    def can_trigger(self) -> bool:
        """
        Check if this alert can be triggered based on cooldown and rate limits.

        Returns:
            bool: True if alert can be triggered, False otherwise
        """
        if not self.is_active:
            return False

        # Check cooldown period
        if self.last_triggered_at:
            minutes_since_last = (
                datetime.now(timezone.utc) - self.last_triggered_at
            ).total_seconds() / 60
            if minutes_since_last < self.cooldown_minutes:
                return False

        # Check daily trigger limit
        if self.last_triggered_at:
            same_day = self.last_triggered_at.date() == datetime.now(timezone.utc).date()
            if same_day and self.trigger_count >= self.max_triggers_per_day:
                return False

        return True

    def trigger_alert(self):
        """
        Record that this alert was triggered.

        Updates trigger count and timestamp. Auto-disables if daily limit exceeded.
        """
        now = datetime.now(timezone.utc)

        # Reset trigger count if it's a new day
        if self.last_triggered_at and self.last_triggered_at.date() != now.date():
            self.trigger_count = 0

        self.trigger_count += 1
        self.last_triggered_at = now

        # Auto-disable if daily limit exceeded
        if self.trigger_count >= self.max_triggers_per_day:
            self.is_active = False

    def get_alert_message(self, current_usage: float, budget_limit: float) -> str:
        """
        Generate alert message based on usage and configuration.

        Args:
            current_usage: Current usage amount
            budget_limit: Budget limit amount

        Returns:
            str: Formatted alert message
        """
        if self.custom_message:
            return self.custom_message.format(
                usage=current_usage,
                limit=budget_limit,
                percentage=self.threshold_percentage,
                provider=self.platform_provider.name if self.platform_provider else "Unknown",
                organization=self.organization.name if self.organization else "All Organizations"
            )

        # Default message templates
        percentage = (current_usage / budget_limit * 100) if budget_limit > 0 else 0
        provider_name = self.platform_provider.name if self.platform_provider else "Unknown"

        if self.alert_type == AlertType.WARNING:
            return (
                f"Budget warning: {provider_name} has reached {percentage:.1f}% "
                f"of its {self.period.value} budget (${current_usage:.2f} / ${budget_limit:.2f})"
            )
        elif self.alert_type == AlertType.CRITICAL:
            return (
                f"Critical budget alert: {provider_name} has reached {percentage:.1f}% "
                f"of its {self.period.value} budget (${current_usage:.2f} / ${budget_limit:.2f})"
            )
        elif self.alert_type == AlertType.EXHAUSTED:
            return (
                f"Budget exhausted: {provider_name} has exceeded its "
                f"{self.period.value} budget (${current_usage:.2f} / ${budget_limit:.2f})"
            )
        elif self.alert_type == AlertType.RATE_LIMIT:
            return (
                f"Rate limit warning: {provider_name} has reached {percentage:.1f}% "
                f"of its hourly rate limit ({int(current_usage)} / {int(budget_limit)} requests)"
            )

        return f"Budget alert: {provider_name} threshold reached"

    def to_dict(self) -> dict:
        """Convert alert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "platform_provider_id": str(self.platform_provider_id),
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "alert_type": self.alert_type.value,
            "threshold_percentage": self.threshold_percentage,
            "period": self.period.value,
            "is_active": self.is_active,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "trigger_count": self.trigger_count,
            "notify_super_admins": self.notify_super_admins,
            "notify_org_admins": self.notify_org_admins,
            "email_recipients": self.email_recipients or [],
            "webhook_url": self.webhook_url,
            "slack_webhook_url": self.slack_webhook_url,
            "cooldown_minutes": self.cooldown_minutes,
            "max_triggers_per_day": self.max_triggers_per_day,
            "custom_message": self.custom_message,
            "alert_metadata": self.alert_metadata,
            "can_trigger": self.can_trigger(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    def __repr__(self) -> str:
        """String representation of BudgetAlert."""
        scope = "global"
        if self.organization_id:
            scope = f"org:{self.organization_id}"

        return (
            f"<BudgetAlert(id={self.id}, provider={self.platform_provider_id}, "
            f"type={self.alert_type.value}, threshold={self.threshold_percentage}%, "
            f"period={self.period.value}, scope={scope}, active={self.is_active})>"
        )


class AlertHistory(Base):
    """
    Historical record of triggered budget alerts.

    This model keeps a permanent record of all alert triggers for
    auditing and analysis purposes.
    """

    __tablename__ = "alert_history"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique alert history record identifier"
    )

    # Alert Reference
    budget_alert_id = Column(
        UUID(as_uuid=True),
        ForeignKey("budget_alerts.id", ondelete="SET NULL"),
        nullable=True,  # Can be null if alert is deleted
        index=True,
        comment="Budget alert that was triggered"
    )

    # Alert Context (preserved even if alert is deleted)
    platform_provider_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Platform provider that triggered the alert"
    )

    organization_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Organization context (if applicable)"
    )

    alert_type = Column(
        Enum(AlertType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        comment="Type of alert that was triggered"
    )

    threshold_percentage = Column(
        Integer,
        nullable=False,
        comment="Threshold percentage that was exceeded"
    )

    period = Column(
        Enum(AlertPeriod, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        comment="Budget period being monitored"
    )

    # Usage Data at Time of Alert
    current_usage = Column(
        Numeric(10, 4),
        nullable=False,
        comment="Usage amount when alert triggered"
    )

    budget_limit = Column(
        Numeric(10, 4),
        nullable=False,
        comment="Budget limit at time of alert"
    )

    usage_percentage = Column(
        Float,
        nullable=False,
        comment="Calculated usage percentage"
    )

    # Alert Message
    alert_message = Column(
        Text,
        nullable=False,
        comment="Generated alert message"
    )

    # Notification Results
    notifications_sent = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Record of notifications sent {type: success/failure}"
    )

    # Metadata
    triggered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        index=True,
        comment="When the alert was triggered"
    )

    # Relationships
    budget_alert = relationship(
        "BudgetAlert",
        doc="Budget alert configuration that was triggered"
    )

    # Indexes
    __table_args__ = (
        Index("idx_alert_history_provider_triggered", "platform_provider_id", "triggered_at"),
        Index("idx_alert_history_org_triggered", "organization_id", "triggered_at"),
        Index("idx_alert_history_type_triggered", "alert_type", "triggered_at"),
        Index("idx_alert_history_triggered", "triggered_at"),
    )

    def __repr__(self) -> str:
        """String representation of AlertHistory."""
        return (
            f"<AlertHistory(id={self.id}, provider={self.platform_provider_id}, "
            f"type={self.alert_type.value}, usage={self.usage_percentage:.1f}%, "
            f"triggered_at={self.triggered_at})>"
        )