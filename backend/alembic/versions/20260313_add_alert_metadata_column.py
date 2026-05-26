"""Add alert_metadata column to budget_alerts table

The budget_alerts model defines an alert_metadata JSONB column, but it was
never added to the database via a migration.  This causes a 500 error on
GET /api/v1/admin/budget-alerts because SQLAlchemy tries to SELECT the
non-existent column.

Revision ID: d9f4a3b7c826
Revises: c4ddf64a11f8
Create Date: 2026-03-13 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "d9f4a3b7c826"
down_revision: Union[str, None] = "c4ddf64a11f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard: 001_complete_initial already creates this column on fresh DBs
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'budget_alerts' AND column_name = 'alert_metadata'"
    ))
    if not result.fetchone():
        op.add_column(
            "budget_alerts",
            sa.Column(
                "alert_metadata",
                JSONB,
                nullable=False,
                server_default="{}",
                comment="Additional alert configuration",
            ),
        )


def downgrade() -> None:
    op.drop_column("budget_alerts", "alert_metadata")
