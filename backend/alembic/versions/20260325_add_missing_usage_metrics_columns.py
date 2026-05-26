"""Add missing columns to usage_metrics table

The UsageMetrics ORM model defines exports_csv, exports_json, exports_excel,
webhooks_sent, and webhooks_failed columns that were never added to the
database via a migration.  This causes a 500 error when SQLAlchemy tries to
SELECT these non-existent columns (e.g. during cascade-delete of a user).

Revision ID: d9f5a3b7c821
Revises: d9f4a3b7c826
Create Date: 2026-03-25 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d9f5a3b7c821"
down_revision: Union[str, None] = "d9f4a3b7c826"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add exports and webhook tracking columns to usage_metrics."""
    op.add_column(
        "usage_metrics",
        sa.Column(
            "exports_csv",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="CSV exports",
        ),
    )
    op.add_column(
        "usage_metrics",
        sa.Column(
            "exports_json",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="JSON exports",
        ),
    )
    op.add_column(
        "usage_metrics",
        sa.Column(
            "exports_excel",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Excel exports",
        ),
    )
    op.add_column(
        "usage_metrics",
        sa.Column(
            "webhooks_sent",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Webhooks sent",
        ),
    )
    op.add_column(
        "usage_metrics",
        sa.Column(
            "webhooks_failed",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Webhooks failed",
        ),
    )


def downgrade() -> None:
    """Remove exports and webhook tracking columns from usage_metrics."""
    op.drop_column("usage_metrics", "webhooks_failed")
    op.drop_column("usage_metrics", "webhooks_sent")
    op.drop_column("usage_metrics", "exports_excel")
    op.drop_column("usage_metrics", "exports_json")
    op.drop_column("usage_metrics", "exports_csv")
