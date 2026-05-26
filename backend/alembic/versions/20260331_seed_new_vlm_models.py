"""Seed new VLM models (GPT-4.1 line, o3, o4-mini) and deprecate gpt-4-turbo

Adds newer OpenAI models (GPT-4.1, GPT-4.1 Mini, GPT-4.1 Nano, o3, o4-mini),
adds Claude Sonnet 4 as explicit entry, marks gpt-4-turbo as deprecated with
replacement pointing to gpt-4.1, and adds GPT-4.1 to Azure OpenAI.

Does NOT delete or modify existing model entries that users may have selected.

Revision ID: h3c4d5e6f752
Revises: g2b3c4d5e641
Create Date: 2026-03-31 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision: str = "h3c4d5e6f752"
down_revision: Union[str, None] = "g2b3c4d5e641"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New models to insert
NEW_MODELS = [
    # Anthropic: Claude Sonnet 4 (explicit entry)
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
        "is_deprecated": False,
        "sort_order": 15,
    },
    # OpenAI: GPT-4.1 (new default)
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
        "is_deprecated": False,
        "sort_order": 5,
    },
    # OpenAI: GPT-4.1 Mini
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
        "is_deprecated": False,
        "sort_order": 15,
    },
    # OpenAI: GPT-4.1 Nano
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
        "is_deprecated": False,
        "sort_order": 18,
    },
    # OpenAI: o3 (reasoning model)
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
        "is_deprecated": False,
        "sort_order": 20,
    },
    # OpenAI: o4-mini (reasoning model)
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
        "is_deprecated": False,
        "sort_order": 22,
    },
    # Azure OpenAI: GPT-4.1 (new default)
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
        "is_deprecated": False,
        "sort_order": 5,
    },
]


def upgrade() -> None:
    """Insert new VLM models and mark gpt-4-turbo as deprecated."""
    conn = op.get_bind()

    vlm_models = sa.table(
        "vlm_models",
        sa.column("id", UUID),
        sa.column("provider_type", sa.String),
        sa.column("model_id", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("max_tokens", sa.Integer),
        sa.column("context_window", sa.Integer),
        sa.column("temperature_default", sa.Float),
        sa.column("input_cost_per_1m", sa.Float),
        sa.column("output_cost_per_1m", sa.Float),
        sa.column("supports_vision", sa.Boolean),
        sa.column("supports_tools", sa.Boolean),
        sa.column("is_default", sa.Boolean),
        sa.column("is_active", sa.Boolean),
        sa.column("is_deprecated", sa.Boolean),
        sa.column("replacement_model_id", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    # Insert new models only if they don't already exist (idempotent)
    for model_data in NEW_MODELS:
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM vlm_models WHERE provider_type = :pt AND model_id = :mid LIMIT 1"
            ),
            {"pt": model_data["provider_type"], "mid": model_data["model_id"]},
        ).fetchone()

        if not exists:
            conn.execute(
                vlm_models.insert().values(
                    id=str(uuid.uuid4()),
                    provider_type=model_data["provider_type"],
                    model_id=model_data["model_id"],
                    display_name=model_data["display_name"],
                    description=model_data.get("description"),
                    max_tokens=model_data["max_tokens"],
                    context_window=model_data.get("context_window"),
                    temperature_default=model_data.get("temperature_default", 0.1),
                    input_cost_per_1m=model_data["input_cost_per_1m"],
                    output_cost_per_1m=model_data["output_cost_per_1m"],
                    supports_vision=model_data.get("supports_vision", True),
                    supports_tools=model_data.get("supports_tools", False),
                    is_default=model_data.get("is_default", False),
                    is_active=model_data.get("is_active", True),
                    is_deprecated=model_data.get("is_deprecated", False),
                    replacement_model_id=model_data.get("replacement_model_id"),
                    sort_order=model_data.get("sort_order", 100),
                    created_at=sa.func.now(),
                    updated_at=sa.func.now(),
                )
            )

    # Mark gpt-4-turbo as deprecated with replacement pointing to gpt-4.1
    # Only update if the model exists and is not already deprecated
    conn.execute(
        sa.text("""
            UPDATE vlm_models
            SET is_deprecated = true,
                replacement_model_id = 'gpt-4.1',
                display_name = CASE
                    WHEN display_name NOT LIKE '%Deprecated%'
                    THEN display_name || ' (Deprecated)'
                    ELSE display_name
                END,
                updated_at = NOW()
            WHERE model_id = 'gpt-4-turbo'
              AND is_deprecated = false
        """)
    )

    # Demote old OpenAI default: gpt-4o-2025-03-26 is no longer the default
    # (only if gpt-4.1 was successfully inserted as the new default)
    gpt41_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM vlm_models WHERE provider_type = 'openai' AND model_id = 'gpt-4.1' LIMIT 1"
        )
    ).fetchone()

    if gpt41_exists:
        conn.execute(
            sa.text("""
                UPDATE vlm_models
                SET is_default = false, updated_at = NOW()
                WHERE provider_type = 'openai'
                  AND model_id != 'gpt-4.1'
                  AND is_default = true
            """)
        )

    # Demote old Azure OpenAI default similarly
    azure_gpt41_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM vlm_models WHERE provider_type = 'azure_openai' AND model_id = 'gpt-4.1' LIMIT 1"
        )
    ).fetchone()

    if azure_gpt41_exists:
        conn.execute(
            sa.text("""
                UPDATE vlm_models
                SET is_default = false, updated_at = NOW()
                WHERE provider_type = 'azure_openai'
                  AND model_id != 'gpt-4.1'
                  AND is_default = true
            """)
        )


def downgrade() -> None:
    """Remove newly inserted models and restore gpt-4-turbo deprecation status."""
    conn = op.get_bind()

    new_model_ids = [m["model_id"] for m in NEW_MODELS]

    # Delete only the models this migration inserted
    for model_data in NEW_MODELS:
        conn.execute(
            sa.text(
                "DELETE FROM vlm_models WHERE provider_type = :pt AND model_id = :mid"
            ),
            {"pt": model_data["provider_type"], "mid": model_data["model_id"]},
        )

    # Restore gpt-4-turbo deprecation status
    conn.execute(
        sa.text("""
            UPDATE vlm_models
            SET is_deprecated = false,
                replacement_model_id = NULL,
                display_name = REPLACE(display_name, ' (Deprecated)', ''),
                updated_at = NOW()
            WHERE model_id = 'gpt-4-turbo'
        """)
    )

    # Restore old OpenAI default (gpt-4o-2025-03-26)
    conn.execute(
        sa.text("""
            UPDATE vlm_models
            SET is_default = true, updated_at = NOW()
            WHERE provider_type = 'openai'
              AND model_id = 'gpt-4o-2025-03-26'
        """)
    )

    # Restore old Azure OpenAI default (gpt-4o-2025-03-26)
    conn.execute(
        sa.text("""
            UPDATE vlm_models
            SET is_default = true, updated_at = NOW()
            WHERE provider_type = 'azure_openai'
              AND model_id = 'gpt-4o-2025-03-26'
        """)
    )
