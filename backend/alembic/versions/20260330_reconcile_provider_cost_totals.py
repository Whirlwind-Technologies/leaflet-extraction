"""Reconcile platform provider cost totals from leaflet data

One-time data migration to fix historical cost drift caused by a race
condition in record_usage() (concurrent Celery workers using ORM-level
mutations lost updates).  The source of truth is SUM(leaflets.processing_cost).

Revision ID: f1a2b3c4d530
Revises: e2a4b6c8d913
Create Date: 2026-03-30 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d530"
down_revision: Union[str, None] = "e2a4b6c8d913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Sync platform provider totals from leaflet processing_cost data."""
    conn = op.get_bind()

    # Get all-time reconciled totals from leaflets (source of truth)
    result = conn.execute(sa.text("""
        SELECT
            COALESCE(SUM(processing_cost), 0) AS total_cost,
            COALESCE(SUM(
                CAST(processing_metadata->>'input_tokens' AS INTEGER)
            ), 0) AS total_input,
            COALESCE(SUM(
                CAST(processing_metadata->>'output_tokens' AS INTEGER)
            ), 0) AS total_output
        FROM leaflets
        WHERE processing_cost IS NOT NULL
          AND processing_cost > 0
    """))
    row = result.fetchone()

    # Get current month totals
    month_result = conn.execute(sa.text("""
        SELECT
            COALESCE(SUM(processing_cost), 0) AS month_cost,
            COALESCE(SUM(
                CAST(processing_metadata->>'input_tokens' AS INTEGER)
            ), 0) AS month_input,
            COALESCE(SUM(
                CAST(processing_metadata->>'output_tokens' AS INTEGER)
            ), 0) AS month_output
        FROM leaflets
        WHERE processing_cost IS NOT NULL
          AND processing_cost > 0
          AND created_at >= DATE_TRUNC('month', NOW())
    """))
    month_row = month_result.fetchone()

    # Get current day totals
    day_result = conn.execute(sa.text("""
        SELECT COALESCE(SUM(processing_cost), 0) AS day_cost
        FROM leaflets
        WHERE processing_cost IS NOT NULL
          AND processing_cost > 0
          AND created_at >= DATE_TRUNC('day', NOW())
    """))
    day_row = day_result.fetchone()

    if row and row[0] > 0:
        conn.execute(sa.text("""
            UPDATE platform_vlm_providers
            SET total_spent = :total_cost,
                total_input_tokens = :total_input,
                total_output_tokens = :total_output,
                current_month_spent = :month_cost,
                current_day_spent = :day_cost
            WHERE is_active = true
        """), {
            "total_cost": row[0],
            "total_input": row[1],
            "total_output": row[2],
            "month_cost": month_row[0] if month_row else 0,
            "day_cost": day_row[0] if day_row else 0,
        })


def downgrade() -> None:
    """No downgrade — this is a one-time data reconciliation."""
    pass
