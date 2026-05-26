"""
VLM Model Registry Module.

This module defines the VLMModel model for storing available VLM models
that can be dynamically updated without code changes.

Example Usage:
    from app.models.vlm_model import VLMModel, VLMProviderType

    model = VLMModel(
        provider_type="anthropic",
        model_id="claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        max_tokens=8192,
        input_cost_per_1m=3.0,
        output_cost_per_1m=15.0,
    )
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import BaseModel, TimestampMixin


class VLMModel(BaseModel, TimestampMixin):
    """
    Registry of available VLM models.

    This table stores all available models for each provider type,
    allowing dynamic updates without code changes.

    Attributes:
        id: Unique identifier (UUID)
        provider_type: Type of VLM provider (anthropic, openai, google, etc.)
        model_id: Model identifier used in API calls (e.g., claude-sonnet-4-20250514)
        display_name: Human-readable name (e.g., "Claude Sonnet 4")
        description: Optional description of the model
        max_tokens: Maximum output tokens supported
        context_window: Maximum context window size
        temperature_default: Default temperature setting
        input_cost_per_1m: Cost per 1M input tokens in USD
        output_cost_per_1m: Cost per 1M output tokens in USD
        supports_vision: Whether the model supports image input
        supports_tools: Whether the model supports tool/function calling
        is_default: Whether this is the default model for the provider
        is_active: Whether this model is available for use
        is_deprecated: Whether this model is deprecated
        deprecation_date: When the model will be/was deprecated
        replacement_model_id: Model ID to migrate to when deprecated
        release_date: When the model was released
        capabilities: JSON field for additional capabilities
        sort_order: Order for display in UI (lower = higher priority)
    """

    __tablename__ = "vlm_models"

    # Provider type (matches VLMProviderType enum values)
    provider_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="VLM provider type (anthropic, openai, google, azure_openai, aws_bedrock)"
    )

    # Model identification
    model_id = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Model identifier used in API calls"
    )

    display_name = Column(
        String(100),
        nullable=False,
        comment="Human-readable display name"
    )

    description = Column(
        Text,
        nullable=True,
        comment="Optional description of the model"
    )

    # Model parameters
    max_tokens = Column(
        Integer,
        nullable=False,
        default=8192,
        comment="Maximum output tokens"
    )

    context_window = Column(
        Integer,
        nullable=True,
        comment="Maximum context window size"
    )

    temperature_default = Column(
        Float,
        nullable=False,
        default=0.1,
        comment="Default temperature setting"
    )

    # Cost per 1M tokens in USD
    input_cost_per_1m = Column(
        Float,
        nullable=False,
        default=3.0,
        comment="Cost per 1M input tokens in USD"
    )

    output_cost_per_1m = Column(
        Float,
        nullable=False,
        default=15.0,
        comment="Cost per 1M output tokens in USD"
    )

    # Capabilities
    supports_vision = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the model supports image input"
    )

    supports_tools = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the model supports tool/function calling"
    )

    # Status flags
    is_default = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the default model for the provider"
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this model is available for use"
    )

    is_deprecated = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this model is deprecated"
    )

    deprecation_date = Column(
        DateTime,
        nullable=True,
        comment="When the model will be/was deprecated"
    )

    replacement_model_id = Column(
        String(100),
        nullable=True,
        comment="Model ID to migrate to when deprecated"
    )

    release_date = Column(
        DateTime,
        nullable=True,
        comment="When the model was released"
    )

    # Additional capabilities as JSON
    capabilities = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional model capabilities"
    )

    # Display ordering
    sort_order = Column(
        Integer,
        nullable=False,
        default=100,
        comment="Order for display in UI (lower = higher priority)"
    )

    # Unique constraint on provider_type + model_id
    __table_args__ = (
        UniqueConstraint('provider_type', 'model_id', name='uq_vlm_model_provider_model'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "provider_type": self.provider_type,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "description": self.description,
            "max_tokens": self.max_tokens,
            "context_window": self.context_window,
            "temperature_default": self.temperature_default,
            "input_cost_per_1m": self.input_cost_per_1m,
            "output_cost_per_1m": self.output_cost_per_1m,
            "supports_vision": self.supports_vision,
            "supports_tools": self.supports_tools,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "is_deprecated": self.is_deprecated,
            "deprecation_date": self.deprecation_date.isoformat() if self.deprecation_date else None,
            "replacement_model_id": self.replacement_model_id,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "capabilities": self.capabilities or {},
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_default_model(cls, db_session, provider_type: str) -> Optional["VLMModel"]:
        """Get the default model for a provider type."""
        from sqlalchemy import select

        result = db_session.execute(
            select(cls).where(
                cls.provider_type == provider_type,
                cls.is_default == True,
                cls.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    def get_active_models(cls, db_session, provider_type: Optional[str] = None) -> List["VLMModel"]:
        """Get all active models, optionally filtered by provider type."""
        from sqlalchemy import select

        query = select(cls).where(cls.is_active == True).order_by(cls.sort_order, cls.display_name)

        if provider_type:
            query = query.where(cls.provider_type == provider_type)

        result = db_session.execute(query)
        return list(result.scalars().all())


# Default models to seed the database (Updated March 2026)
# These will be inserted on first run if the table is empty
DEFAULT_VLM_MODELS = [
    # ── Anthropic models ──────────────────────────────────────────────
    {
        "provider_type": "anthropic",
        "model_id": "claude-sonnet-4-5-20250929",
        "display_name": "Claude Sonnet 4.5",
        "description": "Latest Claude Sonnet model with excellent vision and reasoning capabilities",
        "max_tokens": 16384,
        "context_window": 200000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 3.0,
        "output_cost_per_1m": 15.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": True,
        "is_active": True,
        "sort_order": 10,
    },
    {
        "provider_type": "anthropic",
        "model_id": "claude-sonnet-4-20250514",
        "display_name": "Claude Sonnet 4",
        "description": "Claude Sonnet 4 with strong vision and structured extraction",
        "max_tokens": 8192,
        "context_window": 200000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 3.0,
        "output_cost_per_1m": 15.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 15,
    },
    {
        "provider_type": "anthropic",
        "model_id": "claude-opus-4-5-20251124",
        "display_name": "Claude Opus 4.5",
        "description": "Most powerful Claude model for complex extraction tasks",
        "max_tokens": 16384,
        "context_window": 200000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 15.0,
        "output_cost_per_1m": 75.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 20,
    },
    # ── OpenAI models (GPT-4.1 line + reasoning models) ──────────────
    {
        "provider_type": "openai",
        "model_id": "gpt-4.1",
        "display_name": "GPT-4.1",
        "description": "Latest GPT-4.1 model with improved vision and instruction following",
        "max_tokens": 8192,
        "context_window": 128000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 2.0,
        "output_cost_per_1m": 8.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": True,
        "is_active": True,
        "sort_order": 5,
    },
    {
        "provider_type": "openai",
        "model_id": "gpt-4.1-mini",
        "display_name": "GPT-4.1 Mini",
        "description": "Cost-effective GPT-4.1 variant for simpler extraction tasks",
        "max_tokens": 8192,
        "context_window": 128000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 0.4,
        "output_cost_per_1m": 1.6,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 15,
    },
    {
        "provider_type": "openai",
        "model_id": "gpt-4.1-nano",
        "display_name": "GPT-4.1 Nano",
        "description": "Ultra-low-cost GPT-4.1 variant for high-volume simple tasks",
        "max_tokens": 8192,
        "context_window": 128000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 0.1,
        "output_cost_per_1m": 0.4,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 18,
    },
    {
        "provider_type": "openai",
        "model_id": "o3",
        "display_name": "o3 (Reasoning)",
        "description": "OpenAI reasoning model with deep analytical capabilities",
        "max_tokens": 8192,
        "context_window": 200000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 10.0,
        "output_cost_per_1m": 40.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 20,
    },
    {
        "provider_type": "openai",
        "model_id": "o4-mini",
        "display_name": "o4-mini (Reasoning)",
        "description": "Cost-effective OpenAI reasoning model",
        "max_tokens": 8192,
        "context_window": 200000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 1.1,
        "output_cost_per_1m": 4.4,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 22,
    },
    {
        "provider_type": "openai",
        "model_id": "gpt-4o-2025-03-26",
        "display_name": "GPT-4o (March 2025)",
        "description": "GPT-4o model with enhanced vision capabilities",
        "max_tokens": 8192,
        "context_window": 128000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 2.5,
        "output_cost_per_1m": 10.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 30,
    },
    {
        "provider_type": "openai",
        "model_id": "gpt-4o-mini",
        "display_name": "GPT-4o Mini",
        "description": "Cost-effective GPT-4o model for simpler extraction tasks",
        "max_tokens": 4096,
        "context_window": 128000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 0.15,
        "output_cost_per_1m": 0.6,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 35,
    },
    {
        "provider_type": "openai",
        "model_id": "gpt-4-turbo",
        "display_name": "GPT-4 Turbo (Deprecated)",
        "description": "Legacy GPT-4 Turbo model -- use GPT-4.1 instead",
        "max_tokens": 4096,
        "context_window": 128000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 10.0,
        "output_cost_per_1m": 30.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "is_deprecated": True,
        "replacement_model_id": "gpt-4.1",
        "sort_order": 90,
    },
    # ── Google models (Gemini 2.5 Pro GA June 2025) ──────────────────
    {
        "provider_type": "google",
        "model_id": "gemini-2.5-pro",
        "display_name": "Gemini 2.5 Pro",
        "description": "Latest stable Gemini model with very large context window (GA June 2025)",
        "max_tokens": 1000000,
        "context_window": 1000000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 1.25,
        "output_cost_per_1m": 5.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": True,
        "is_active": True,
        "sort_order": 10,
    },
    {
        "provider_type": "google",
        "model_id": "gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "description": "Fast and cost-effective Gemini model",
        "max_tokens": 8192,
        "context_window": 1000000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 0.075,
        "output_cost_per_1m": 0.3,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 20,
    },
    # ── Azure OpenAI models (Mirror OpenAI GPT-4.1) ─────────────────
    {
        "provider_type": "azure_openai",
        "model_id": "gpt-4.1",
        "display_name": "GPT-4.1 (Azure)",
        "description": "GPT-4.1 deployed on Azure OpenAI Service",
        "max_tokens": 8192,
        "context_window": 128000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 2.0,
        "output_cost_per_1m": 8.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": True,
        "is_active": True,
        "sort_order": 10,
    },
    {
        "provider_type": "azure_openai",
        "model_id": "gpt-4o-2025-03-26",
        "display_name": "GPT-4o (Azure, March 2025)",
        "description": "GPT-4o latest deployed on Azure OpenAI Service",
        "max_tokens": 8192,
        "context_window": 128000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 2.5,
        "output_cost_per_1m": 10.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 20,
    },
    # ── AWS Bedrock models (Opus 4.5 November 2025) ──────────────────
    {
        "provider_type": "aws_bedrock",
        "model_id": "anthropic.claude-opus-4-5-20251124-v1:0",
        "display_name": "Claude Opus 4.5 (Bedrock)",
        "description": "Most powerful Claude model via AWS Bedrock (Nov 2025)",
        "max_tokens": 16384,
        "context_window": 200000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 15.0,
        "output_cost_per_1m": 75.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": False,
        "is_active": True,
        "sort_order": 20,
    },
    {
        "provider_type": "aws_bedrock",
        "model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "display_name": "Claude Sonnet 4.5 (Bedrock)",
        "description": "Claude Sonnet 4.5 via AWS Bedrock",
        "max_tokens": 16384,
        "context_window": 200000,
        "temperature_default": 0.1,
        "input_cost_per_1m": 3.0,
        "output_cost_per_1m": 15.0,
        "supports_vision": True,
        "supports_tools": True,
        "is_default": True,
        "is_active": True,
        "sort_order": 10,
    },
]
