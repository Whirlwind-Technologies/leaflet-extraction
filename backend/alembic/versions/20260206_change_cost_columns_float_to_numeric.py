"""Change cost columns from Float to Numeric for precision

Revision ID: a1c4f7e8d902
Revises: b3b7bc3abea0
Create Date: 2026-02-06 00:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1c4f7e8d902'
down_revision: Union[str, None] = 'b3b7bc3abea0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change all cost/budget columns from Float to Numeric(10,4) for precision."""
    # VLM Providers (organization-level)
    op.alter_column(
        'vlm_providers', 'monthly_budget',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=True,
    )
    op.alter_column(
        'vlm_providers', 'total_spent',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )
    op.alter_column(
        'vlm_providers', 'current_month_spent',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )

    # Platform VLM Providers (admin-level)
    op.alter_column(
        'platform_vlm_providers', 'monthly_budget',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=True,
    )
    op.alter_column(
        'platform_vlm_providers', 'daily_budget',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=True,
    )
    op.alter_column(
        'platform_vlm_providers', 'total_spent',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )
    op.alter_column(
        'platform_vlm_providers', 'current_month_spent',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )
    op.alter_column(
        'platform_vlm_providers', 'current_day_spent',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )

    # Leaflets
    op.alter_column(
        'leaflets', 'processing_cost',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )

    # Cost Tracking
    op.alter_column(
        'cost_tracking', 'input_cost',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )
    op.alter_column(
        'cost_tracking', 'output_cost',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )
    op.alter_column(
        'cost_tracking', 'total_cost',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )
    op.alter_column(
        'cost_tracking', 'input_price_per_1m',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=True,
    )
    op.alter_column(
        'cost_tracking', 'output_price_per_1m',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=True,
    )

    # Usage Metrics
    op.alter_column(
        'usage_metrics', 'api_cost',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )

    # Processing Stats
    op.alter_column(
        'processing_stats', 'total_cost',
        type_=sa.Numeric(10, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert cost columns from Numeric(10,4) back to Float."""
    # Processing Stats
    op.alter_column(
        'processing_stats', 'total_cost',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )

    # Usage Metrics
    op.alter_column(
        'usage_metrics', 'api_cost',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )

    # Cost Tracking
    op.alter_column(
        'cost_tracking', 'output_price_per_1m',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=True,
    )
    op.alter_column(
        'cost_tracking', 'input_price_per_1m',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=True,
    )
    op.alter_column(
        'cost_tracking', 'total_cost',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )
    op.alter_column(
        'cost_tracking', 'output_cost',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )
    op.alter_column(
        'cost_tracking', 'input_cost',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )

    # Leaflets
    op.alter_column(
        'leaflets', 'processing_cost',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )

    # Platform VLM Providers
    op.alter_column(
        'platform_vlm_providers', 'current_day_spent',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )
    op.alter_column(
        'platform_vlm_providers', 'current_month_spent',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )
    op.alter_column(
        'platform_vlm_providers', 'total_spent',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )
    op.alter_column(
        'platform_vlm_providers', 'daily_budget',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=True,
    )
    op.alter_column(
        'platform_vlm_providers', 'monthly_budget',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=True,
    )

    # VLM Providers
    op.alter_column(
        'vlm_providers', 'current_month_spent',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )
    op.alter_column(
        'vlm_providers', 'total_spent',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
    )
    op.alter_column(
        'vlm_providers', 'monthly_budget',
        type_=sa.Float(),
        existing_type=sa.Numeric(10, 4),
        existing_nullable=True,
    )
