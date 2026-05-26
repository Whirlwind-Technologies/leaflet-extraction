"""Reconcile platform provider monthly and daily cost counters

Follow-up to f1a2b3c4d530 which only reconciled total_spent but missed
current_month_spent and current_day_spent. The settings page reads
current_month_spent for the "This Month" cost display.

Revision ID: g2b3c4d5e641
Revises: f1a2b3c4d530
Create Date: 2026-03-30 13:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "g2b3c4d5e641"
down_revision: Union[str, None] = "f1a2b3c4d530"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Sync platform provider monthly/daily counters from leaflet data."""
    conn = op.get_bind()

    # Current month totals from leaflets
    month_result = conn.execute(sa.text("""
        SELECT
            COALESCE(SUM(processing_cost), 0) AS month_cost
        FROM leaflets
        WHERE processing_cost IS NOT NULL
          AND processing_cost > 0
          AND created_at >= DATE_TRUNC('month', NOW())
    """))
    month_row = month_result.fetchone()

    # Current day totals from leaflets
    day_result = conn.execute(sa.text("""
        SELECT
            COALESCE(SUM(processing_cost), 0) AS day_cost
        FROM leaflets
        WHERE processing_cost IS NOT NULL
          AND processing_cost > 0
          AND created_at >= DATE_TRUNC('day', NOW())
    """))
    day_row = day_result.fetchone()

    month_cost = month_row[0] if month_row else 0
    day_cost = day_row[0] if day_row else 0

    conn.execute(sa.text("""
        UPDATE platform_vlm_providers
        SET current_month_spent = :month_cost,
            current_day_spent = :day_cost
        WHERE is_active = true
    """), {
        "month_cost": month_cost,
        "day_cost": day_cost,
    })


def downgrade() -> None:
    """No downgrade — this is a one-time data reconciliation."""
    pass
