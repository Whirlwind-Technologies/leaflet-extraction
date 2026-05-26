"""
VLM Provider Model Module.

This module defines models for configuring different VLM providers
(Anthropic Claude, OpenAI GPT-4V, Google Gemini, etc.).

Example Usage:
    from app.models.vlm_provider import VLMProvider, VLMProviderType
    
    provider = VLMProvider(
        user_id=user.id,
        provider_type=VLMProviderType.ANTHROPIC,
        api_key="sk-ant-...",
        model_name="claude-sonnet-4-20250514"
    )
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Union
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    case,
    update,
)
from sqlalchemy import func as sa_func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import object_session, relationship
from cryptography.fernet import Fernet

from app.models.base import BaseModel, TimestampMixin
from app.config import settings


class VLMProviderType(str, Enum):
    """
    Supported VLM provider types.
    
    Attributes:
        ANTHROPIC: Anthropic Claude API
        OPENAI: OpenAI GPT-4 Vision API
        GOOGLE: Google Gemini API
        AZURE_OPENAI: Azure OpenAI Service
        AWS_BEDROCK: AWS Bedrock
        CUSTOM: Custom/self-hosted models
    """
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    CUSTOM = "custom"


class VLMProvider(BaseModel, TimestampMixin):
    """
    VLM Provider configuration for users.
    
    Stores API keys and configuration for different VLM providers.
    API keys are encrypted at rest.
    
    Attributes:
        id: Unique identifier (UUID)
        user_id: Owner user ID
        provider_type: Type of VLM provider
        name: User-friendly name for this configuration
        api_key_encrypted: Encrypted API key
        api_endpoint: Custom API endpoint (for Azure, custom providers)
        model_name: Model to use (e.g., claude-sonnet-4-20250514)
        max_tokens: Maximum output tokens
        temperature: Sampling temperature
        is_default: Whether this is the default provider for the user
        is_active: Whether this provider is active
        monthly_budget: Monthly budget limit (optional)
        total_spent: Total amount spent
        last_used_at: Last time this provider was used
    """
    
    __tablename__ = "vlm_providers"
    
    # Owner (nullable for organization-scoped providers)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Owner user ID (deprecated - use organization_id)"
    )

    # Organization ownership
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this provider belongs to"
    )

    # Provider configuration
    provider_type = Column(
        SQLEnum(
            VLMProviderType,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
            create_constraint=False,
        ),
        nullable=False,
        default=VLMProviderType.ANTHROPIC,
        comment="Type of VLM provider"
    )
    
    name = Column(
        String(100),
        nullable=False,
        comment="User-friendly name for this configuration"
    )
    
    api_key_encrypted = Column(
        Text,
        nullable=False,
        comment="Encrypted API key"
    )
    
    api_endpoint = Column(
        String(500),
        nullable=True,
        comment="Custom API endpoint URL"
    )
    
    model_name = Column(
        String(100),
        nullable=False,
        default="claude-sonnet-4-5-20250929",
        comment="Model name to use"
    )
    
    # Model parameters
    max_tokens = Column(
        Integer,
        nullable=False,
        default=8192,
        comment="Maximum output tokens"
    )
    
    temperature = Column(
        Float,
        nullable=False,
        default=0.1,
        comment="Sampling temperature"
    )
    
    # Additional config (for provider-specific settings)
    config = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional provider-specific configuration"
    )
    
    # Status flags
    is_default = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the default provider"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this provider is active"
    )
    
    # Cost tracking (Numeric for fixed-point decimal precision)
    monthly_budget = Column(
        Numeric(10, 4),
        nullable=True,
        comment="Monthly budget limit in USD"
    )

    total_spent = Column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("0"),
        comment="Total amount spent in USD"
    )

    current_month_spent = Column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("0"),
        comment="Amount spent in current month"
    )
    
    # Usage tracking
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
    
    last_used_at = Column(
        DateTime,
        nullable=True,
        comment="Last time this provider was used"
    )
    
    # Relationships
    user = relationship("User", back_populates="vlm_providers")
    
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
    
    def _check_and_reset_stale_month(self) -> bool:
        """
        Check if the monthly spending counter is stale and needs resetting.

        Compares the current UTC month/year against last_used_at. Returns
        True if the calendar month has changed, indicating that the monthly
        counter should be reset before incrementing.

        This method is idempotent: calling it multiple times within the
        same month returns False after the first reset has been applied.

        Returns:
            True if the monthly counter is stale and needs resetting.
        """
        if self.last_used_at is None:
            # Provider has never been used; counter should already be zero.
            return False

        now = datetime.now(timezone.utc)
        last = self.last_used_at
        # Handle naive timestamps stored by legacy datetime.utcnow() calls
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        return (now.year, now.month) != (last.year, last.month)

    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        cost: Union[float, Decimal],
    ):
        """Record API usage using atomic SQL increments.

        Uses SQL-level ``SET col = col + value`` expressions combined with a
        ``CASE`` expression for the monthly counter to prevent both lost
        updates and TOCTOU races at month boundaries. The staleness check is
        performed entirely within the SQL UPDATE using ``date_trunc()``, so
        two concurrent workers will never both decide to reset the counter
        based on stale in-memory state.

        After the atomic UPDATE, refreshes the ORM instance so in-memory
        state reflects the committed database values.
        """
        session = object_session(self)
        if session is None:
            raise RuntimeError(
                "VLMProvider.record_usage() requires the instance "
                "to be attached to a SQLAlchemy session."
            )

        cost_decimal = Decimal(str(cost)) if not isinstance(cost, Decimal) else cost
        now = datetime.now(timezone.utc)

        # Build the atomic increment values for cumulative counters.
        values: dict = {
            "total_requests": VLMProvider.total_requests + 1,
            "total_input_tokens": VLMProvider.total_input_tokens + input_tokens,
            "total_output_tokens": VLMProvider.total_output_tokens + output_tokens,
            "total_spent": VLMProvider.total_spent + cost_decimal,
            "last_used_at": now,
        }

        # Monthly counter: use SQL CASE so the staleness decision is made
        # atomically against the row's actual last_used_at, not the
        # potentially-stale in-memory copy.
        values["current_month_spent"] = case(
            (
                VLMProvider.last_used_at.is_(None),
                cost_decimal,
            ),
            (
                sa_func.date_trunc("month", VLMProvider.last_used_at)
                < sa_func.date_trunc("month", sa_func.now()),
                cost_decimal,
            ),
            else_=sa_func.coalesce(VLMProvider.current_month_spent, Decimal("0"))
            + cost_decimal,
        )

        stmt = (
            update(VLMProvider)
            .where(VLMProvider.id == self.id)
            .values(**values)
        )
        session.execute(stmt)
        session.flush()

        # Refresh the ORM instance so in-memory attributes reflect the DB state
        session.refresh(self)

    def check_budget(self) -> bool:
        """Check if within monthly budget.

        Uses stale month detection to treat the counter as zero when the
        calendar month has changed, preventing stale spending from a
        previous month from blocking usage.
        """
        month_is_stale = self._check_and_reset_stale_month()
        if self.monthly_budget is None:
            return True
        effective_spent = Decimal("0") if month_is_stale else self.current_month_spent
        return effective_spent < self.monthly_budget
    
    def reset_monthly_spent(self):
        """Reset monthly spending (call at month start)."""
        self.current_month_spent = Decimal("0")
    
    @property
    def provider_display_name(self) -> str:
        """Get display name for provider type."""
        names = {
            VLMProviderType.ANTHROPIC: "Anthropic Claude",
            VLMProviderType.OPENAI: "OpenAI GPT-4",
            VLMProviderType.GOOGLE: "Google Gemini",
            VLMProviderType.AZURE_OPENAI: "Azure OpenAI",
            VLMProviderType.AWS_BEDROCK: "AWS Bedrock",
            VLMProviderType.CUSTOM: "Custom Provider",
        }
        return names.get(self.provider_type, "Unknown")


# Default model configurations for each provider (Updated March 2026)
DEFAULT_MODELS = {
    VLMProviderType.ANTHROPIC: {
        "model_name": "claude-sonnet-4-5-20250929",
        "max_tokens": 16384,
        "temperature": 0.1,
        "input_cost_per_1m": 3.0,
        "output_cost_per_1m": 15.0,
    },
    VLMProviderType.OPENAI: {
        "model_name": "gpt-4.1",
        "max_tokens": 8192,
        "temperature": 0.1,
        "input_cost_per_1m": 2.0,
        "output_cost_per_1m": 8.0,
    },
    VLMProviderType.GOOGLE: {
        "model_name": "gemini-2.5-pro",
        "max_tokens": 8192,
        "temperature": 0.1,
        "input_cost_per_1m": 1.25,
        "output_cost_per_1m": 5.0,
    },
    VLMProviderType.AZURE_OPENAI: {
        "model_name": "gpt-4.1",
        "max_tokens": 8192,
        "temperature": 0.1,
        "input_cost_per_1m": 2.0,
        "output_cost_per_1m": 8.0,
    },
    VLMProviderType.AWS_BEDROCK: {
        "model_name": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "max_tokens": 16384,
        "temperature": 0.1,
        "input_cost_per_1m": 3.0,
        "output_cost_per_1m": 15.0,
    },
}