"""
Platform VLM Provider Model Module.

This module defines models for platform-level VLM providers managed by super admins.
These providers serve as fallback when organizations don't have their own keys configured,
and support priority-based failover with smart failure detection.

Example Usage:
    from app.models.platform_vlm_provider import PlatformVLMProvider, PlatformVLMProviderType

    provider = PlatformVLMProvider(
        name="Primary Anthropic Claude",
        provider_type=PlatformVLMProviderType.ANTHROPIC,
        api_key="sk-ant-...",
        priority=1,
        monthly_budget=5000.0
    )
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Union

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    CheckConstraint,
    Index,
    case,
    update,
)
from sqlalchemy import func as sa_func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import object_session, relationship
from cryptography.fernet import Fernet

from app.models.base import Base
from app.config import settings


class PlatformVLMProviderType(str, enum.Enum):
    """
    Supported platform VLM provider types.

    Attributes:
        ANTHROPIC: Anthropic Claude API
        OPENAI: OpenAI GPT-4 Vision API
        GOOGLE: Google Gemini API
        AZURE_OPENAI: Azure OpenAI Service
        AWS_BEDROCK: AWS Bedrock
        CUSTOM: Custom VLM Provider
    """
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    CUSTOM = "custom"


class PlatformVLMProvider(Base):
    """
    Platform-level VLM Provider configuration managed by super admins.

    These providers serve as system-wide fallback when organizations don't have
    their own VLM providers configured. Supports priority-based failover with
    smart failure detection and budget management.

    Attributes:
        id: Unique identifier (UUID)
        name: User-friendly name for this configuration
        provider_type: Type of VLM provider
        api_key_encrypted: Encrypted API key
        api_endpoint: Custom API endpoint (for Azure, custom providers)
        model_name: Model to use (e.g., claude-sonnet-4.5-20250929)
        max_tokens: Maximum output tokens
        temperature: Sampling temperature
        config: Additional provider-specific configuration

        priority: Priority order (1=highest, 999=lowest)
        is_active: Whether this provider is active
        is_default: Whether this is the default platform provider

        monthly_budget: Monthly budget limit for this provider
        daily_budget: Daily budget limit
        max_requests_per_hour: Rate limiting

        total_spent: Total amount spent (all-time)
        current_month_spent: Amount spent in current month
        current_day_spent: Amount spent in current day
        current_hour_requests: Requests made in current hour

        created_by_user_id: Super admin who created this provider
        created_at: Creation timestamp
        updated_at: Last update timestamp
        last_used_at: Last time this provider was used
    """

    __tablename__ = "platform_vlm_providers"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Unique platform provider identifier"
    )

    # Basic Configuration
    name = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="User-friendly name for this platform provider"
    )

    provider_type = Column(
        Enum(PlatformVLMProviderType, values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
        comment="Type of VLM provider"
    )

    api_key_encrypted = Column(
        Text,
        nullable=False,
        comment="Encrypted API key using Fernet"
    )

    api_endpoint = Column(
        String(500),
        nullable=True,
        comment="Custom API endpoint URL (for Azure, custom providers)"
    )

    model_name = Column(
        String(100),
        nullable=False,
        default="claude-sonnet-4.5-20250929",
        comment="Model name to use"
    )

    # Model Parameters
    max_tokens = Column(
        Integer,
        nullable=False,
        default=16384,
        comment="Maximum output tokens"
    )

    temperature = Column(
        Float,
        nullable=False,
        default=0.1,
        comment="Sampling temperature"
    )

    config = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional provider-specific configuration"
    )

    # Priority and Status
    priority = Column(
        Integer,
        nullable=False,
        default=100,
        comment="Priority order (1=highest, 999=lowest)"
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this provider is active"
    )

    is_default = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the default platform provider"
    )

    # Budget and Rate Limiting (Numeric for fixed-point decimal precision)
    monthly_budget = Column(
        Numeric(10, 4),
        nullable=True,
        comment="Monthly budget limit in USD"
    )

    daily_budget = Column(
        Numeric(10, 4),
        nullable=True,
        comment="Daily budget limit in USD"
    )

    max_requests_per_hour = Column(
        Integer,
        nullable=False,
        default=1000,
        comment="Maximum requests per hour"
    )

    # Usage Tracking (Platform-wide, Numeric for fixed-point decimal precision)
    total_spent = Column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("0"),
        comment="Total amount spent (all-time) in USD"
    )

    current_month_spent = Column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("0"),
        comment="Amount spent in current month"
    )

    current_day_spent = Column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("0"),
        comment="Amount spent in current day"
    )

    current_hour_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of requests made in current hour"
    )

    # Request Tracking
    total_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total API requests made"
    )

    total_input_tokens = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total input tokens used"
    )

    total_output_tokens = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total output tokens used"
    )

    # Metadata
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Super admin who created this provider"
    )

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

    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time this provider was used"
    )

    # Relationships
    created_by = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        doc="Super admin who created this provider"
    )

    # Indexes and Constraints
    __table_args__ = (
        CheckConstraint("priority >= 1 AND priority <= 999", name="check_priority_range"),
        CheckConstraint("monthly_budget IS NULL OR monthly_budget > 0", name="check_monthly_budget_positive"),
        CheckConstraint("daily_budget IS NULL OR daily_budget > 0", name="check_daily_budget_positive"),
        CheckConstraint("max_requests_per_hour > 0", name="check_max_requests_positive"),
        CheckConstraint("total_spent >= 0", name="check_total_spent_non_negative"),
        CheckConstraint("current_month_spent >= 0", name="check_current_month_spent_non_negative"),
        CheckConstraint("current_day_spent >= 0", name="check_current_day_spent_non_negative"),
        Index("idx_platform_provider_priority_active", "priority", "is_active", "is_default"),
        Index("idx_platform_provider_type_active", "provider_type", "is_active"),
        Index("idx_platform_provider_created_at", "created_at"),
    )

    # Encryption key (derived from settings)
    _fernet = None

    @classmethod
    def _get_fernet(cls):
        """Get Fernet encryption instance."""
        if cls._fernet is None:
            # Use SECRET_KEY to derive encryption key
            import hashlib
            import base64
            key = hashlib.sha256(settings.secret_key.encode()).digest()
            cls._fernet = Fernet(base64.urlsafe_b64encode(key))
        return cls._fernet

    def set_api_key(self, api_key: str):
        """Encrypt and set API key."""
        fernet = self._get_fernet()
        self.api_key_encrypted = fernet.encrypt(api_key.encode()).decode()

    def get_api_key(self) -> str:
        """Decrypt and get API key."""
        fernet = self._get_fernet()
        return fernet.decrypt(self.api_key_encrypted.encode()).decode()

    def get_masked_api_key(self) -> str:
        """Get masked API key for display."""
        api_key = self.get_api_key()
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:4]}...{api_key[-4:]}"

    def _check_and_reset_stale_periods(self) -> dict:
        """
        Check if spending counters are stale and determine which need resetting.

        Compares the current UTC time against last_used_at to determine if the
        month, day, or hour has changed. Returns a dict of column reset values
        to apply via SQL UPDATE, ensuring atomic operation when combined with
        the increment in record_usage().

        This method is intentionally idempotent: calling it multiple times within
        the same period has no effect after the first reset.

        Returns:
            Dictionary of column values to reset (empty if no resets needed).
        """
        resets: dict = {}
        now = datetime.now(timezone.utc)

        if self.last_used_at is None:
            # Provider has never been used; counters should already be zero.
            return resets

        last = self.last_used_at
        # Ensure last_used_at is timezone-aware for comparison
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        # Monthly reset: different calendar month or year
        if (now.year, now.month) != (last.year, last.month):
            resets["current_month_spent"] = Decimal("0")

        # Daily reset: different calendar day
        if now.date() != last.date():
            resets["current_day_spent"] = Decimal("0")

        # Hourly reset: different hour (or different day)
        if (now.date() != last.date()) or (now.hour != last.hour):
            resets["current_hour_requests"] = 0

        return resets

    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        cost: Union[float, Decimal],
    ):
        """Record API usage for this platform provider using atomic SQL increments.

        Uses SQL-level ``SET col = col + value`` expressions combined with
        ``CASE`` expressions for period counters to prevent both lost updates
        and TOCTOU races at period boundaries. The staleness check for month,
        day, and hour counters is performed entirely within the SQL UPDATE
        statement using ``date_trunc()``, so two concurrent workers will never
        both decide to reset a counter based on stale in-memory state.

        After the atomic UPDATE, refreshes the ORM instance so in-memory
        state reflects the committed database values.
        """
        session = object_session(self)
        if session is None:
            raise RuntimeError(
                "PlatformVLMProvider.record_usage() requires the instance "
                "to be attached to a SQLAlchemy session."
            )

        cost_decimal = Decimal(str(cost)) if not isinstance(cost, Decimal) else cost
        now = datetime.now(timezone.utc)

        # Build the atomic increment values for cumulative counters.
        values: dict = {
            "total_requests": PlatformVLMProvider.total_requests + 1,
            "total_input_tokens": PlatformVLMProvider.total_input_tokens + input_tokens,
            "total_output_tokens": PlatformVLMProvider.total_output_tokens + output_tokens,
            "total_spent": PlatformVLMProvider.total_spent + cost_decimal,
            "last_used_at": now,
        }

        # For period counters, use SQL CASE expressions so the staleness
        # decision is made atomically against the row's actual last_used_at,
        # not the potentially-stale in-memory copy.
        #
        # Pattern: if last_used_at is NULL or in a previous period, reset the
        # counter to the new increment value; otherwise, add to the existing
        # DB value (with coalesce for NULL safety).

        # Monthly counter: reset when last_used_at is in a previous calendar month.
        values["current_month_spent"] = case(
            (
                PlatformVLMProvider.last_used_at.is_(None),
                cost_decimal,
            ),
            (
                sa_func.date_trunc("month", PlatformVLMProvider.last_used_at)
                < sa_func.date_trunc("month", sa_func.now()),
                cost_decimal,
            ),
            else_=sa_func.coalesce(PlatformVLMProvider.current_month_spent, Decimal("0"))
            + cost_decimal,
        )

        # Daily counter: reset when last_used_at is in a previous calendar day.
        values["current_day_spent"] = case(
            (
                PlatformVLMProvider.last_used_at.is_(None),
                cost_decimal,
            ),
            (
                sa_func.date_trunc("day", PlatformVLMProvider.last_used_at)
                < sa_func.date_trunc("day", sa_func.now()),
                cost_decimal,
            ),
            else_=sa_func.coalesce(PlatformVLMProvider.current_day_spent, Decimal("0"))
            + cost_decimal,
        )

        # Hourly request counter: reset when last_used_at is in a previous hour.
        values["current_hour_requests"] = case(
            (
                PlatformVLMProvider.last_used_at.is_(None),
                1,
            ),
            (
                sa_func.date_trunc("hour", PlatformVLMProvider.last_used_at)
                < sa_func.date_trunc("hour", sa_func.now()),
                1,
            ),
            else_=sa_func.coalesce(PlatformVLMProvider.current_hour_requests, 0) + 1,
        )

        stmt = (
            update(PlatformVLMProvider)
            .where(PlatformVLMProvider.id == self.id)
            .values(**values)
        )
        session.execute(stmt)
        session.flush()

        # Refresh the ORM instance so in-memory attributes reflect the DB state
        session.refresh(self)

    def check_monthly_budget(self) -> bool:
        """Check if within monthly budget.

        Uses stale period detection to treat counters as zero when the
        calendar month has changed, avoiding false budget exhaustion.
        """
        stale = self._check_and_reset_stale_periods()
        if self.monthly_budget is None:
            return True
        effective_spent = stale.get("current_month_spent", self.current_month_spent)
        return effective_spent < self.monthly_budget

    def check_daily_budget(self) -> bool:
        """Check if within daily budget.

        Uses stale period detection to treat counters as zero when the
        calendar day has changed, avoiding false budget exhaustion.
        """
        stale = self._check_and_reset_stale_periods()
        if self.daily_budget is None:
            return True
        effective_spent = stale.get("current_day_spent", self.current_day_spent)
        return effective_spent < self.daily_budget

    def check_hourly_rate_limit(self) -> bool:
        """Check if within hourly rate limit.

        Uses stale period detection to treat counters as zero when the
        hour has changed, avoiding false rate limit hits.
        """
        stale = self._check_and_reset_stale_periods()
        effective_requests = stale.get("current_hour_requests", self.current_hour_requests)
        return effective_requests < self.max_requests_per_hour

    def check_budget(self) -> bool:
        """Check if provider is within all budget limits.

        Detects stale period counters to avoid incorrectly blocking a
        provider due to spending from a previous month/day/hour.
        """
        return (
            self.check_monthly_budget()
            and self.check_daily_budget()
            and self.check_hourly_rate_limit()
        )

    def get_budget_status(self) -> dict:
        """Get detailed budget status information.

        Uses stale period detection so the returned values reflect the
        current period, not a previous one.
        """
        stale = self._check_and_reset_stale_periods()

        effective_month_spent = stale.get("current_month_spent", self.current_month_spent)
        effective_day_spent = stale.get("current_day_spent", self.current_day_spent)
        effective_hour_requests = stale.get("current_hour_requests", self.current_hour_requests)

        monthly_percentage = None
        daily_percentage = None
        hourly_percentage = None

        if self.monthly_budget:
            monthly_percentage = (effective_month_spent / self.monthly_budget) * 100

        if self.daily_budget:
            daily_percentage = (effective_day_spent / self.daily_budget) * 100

        hourly_percentage = (effective_hour_requests / self.max_requests_per_hour) * 100

        return {
            "monthly_budget": self.monthly_budget,
            "monthly_spent": effective_month_spent,
            "monthly_percentage": monthly_percentage,
            "daily_budget": self.daily_budget,
            "daily_spent": effective_day_spent,
            "daily_percentage": daily_percentage,
            "hourly_limit": self.max_requests_per_hour,
            "hourly_requests": effective_hour_requests,
            "hourly_percentage": hourly_percentage,
            "within_budget": self.check_budget()
        }

    def reset_monthly_spent(self):
        """Reset monthly spending (call at month start)."""
        self.current_month_spent = Decimal("0")

    def reset_daily_spent(self):
        """Reset daily spending (call at day start)."""
        self.current_day_spent = Decimal("0")

    def reset_hourly_requests(self):
        """Reset hourly request count (call at hour start)."""
        self.current_hour_requests = 0

    @property
    def provider_display_name(self) -> str:
        """Get display name for provider type."""
        names = {
            PlatformVLMProviderType.ANTHROPIC: "Anthropic Claude",
            PlatformVLMProviderType.OPENAI: "OpenAI GPT-4",
            PlatformVLMProviderType.GOOGLE: "Google Gemini",
            PlatformVLMProviderType.AZURE_OPENAI: "Azure OpenAI",
            PlatformVLMProviderType.AWS_BEDROCK: "AWS Bedrock",
            PlatformVLMProviderType.CUSTOM: "Custom Provider",
        }
        return names.get(self.provider_type, "Unknown")

    def __repr__(self) -> str:
        """String representation of PlatformVLMProvider."""
        return (
            f"<PlatformVLMProvider(id={self.id}, name='{self.name}', "
            f"provider_type={self.provider_type.value}, priority={self.priority}, "
            f"is_active={self.is_active}, is_default={self.is_default})>"
        )


# Default model configurations for platform providers (Updated March 2026)
PLATFORM_DEFAULT_MODELS = {
    PlatformVLMProviderType.ANTHROPIC: {
        # Latest Claude Sonnet 4.5
        "model_name": "claude-sonnet-4-5-20250929",
        "max_tokens": 16384,
        "temperature": 0.1,
        "input_cost_per_1m": 3.0,
        "output_cost_per_1m": 15.0,
        "max_requests_per_hour": 1000,
    },
    PlatformVLMProviderType.OPENAI: {
        # GPT-4.1 — latest stable model with vision
        "model_name": "gpt-4.1",
        "max_tokens": 8192,
        "temperature": 0.1,
        "input_cost_per_1m": 2.0,
        "output_cost_per_1m": 8.0,
        "max_requests_per_hour": 500,
    },
    PlatformVLMProviderType.GOOGLE: {
        # Gemini 2.5 Pro — stable GA released June 2025
        "model_name": "gemini-2.5-pro",
        "max_tokens": 1_000_000,
        "temperature": 0.1,
        "input_cost_per_1m": 1.25,
        "output_cost_per_1m": 5.0,
        "max_requests_per_hour": 1000,
    },
    PlatformVLMProviderType.AZURE_OPENAI: {
        # Mirror OpenAI GPT-4.1 default for Azure deployments
        "model_name": "gpt-4.1",
        "max_tokens": 8192,
        "temperature": 0.1,
        "input_cost_per_1m": 2.0,
        "output_cost_per_1m": 8.0,
        "max_requests_per_hour": 500,
    },
    PlatformVLMProviderType.AWS_BEDROCK: {
        # Claude Sonnet 4.5 via Bedrock — best cost/performance ratio
        "model_name": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "max_tokens": 16384,
        "temperature": 0.1,
        "input_cost_per_1m": 3.0,
        "output_cost_per_1m": 15.0,
        "max_requests_per_hour": 500,
    },
    PlatformVLMProviderType.CUSTOM: {
        # Custom provider with default settings
        "model_name": "custom-model-name",
        "max_tokens": 8192,
        "temperature": 0.1,
        "input_cost_per_1m": 5.0,
        "output_cost_per_1m": 15.0,
        "max_requests_per_hour": 1000,
    },
}