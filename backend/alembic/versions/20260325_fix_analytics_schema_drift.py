"""Fix analytics tables schema drift

Add missing columns to cost_tracking and feedback_logs tables so the ORM
model matches the actual database schema.  Without these columns, SQLAlchemy
cascade-deletes on User fail with "column does not exist".

Revision ID: e2a4b6c8d913
Revises: d9f5a3b7c821
Create Date: 2026-03-25 13:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "e2a4b6c8d913"
down_revision: Union[str, None] = "d9f5a3b7c821"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to cost_tracking and feedback_logs."""
    # cost_tracking: add updated_at (TimestampMixin expects it)
    op.add_column(
        "cost_tracking",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
            comment="Last updated timestamp",
        ),
    )

    # feedback_logs: add metadata_ and updated_at
    op.add_column(
        "feedback_logs",
        sa.Column(
            "metadata_",
            JSONB,
            nullable=True,
            comment="Additional metadata",
        ),
    )
    op.add_column(
        "feedback_logs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
            comment="Last updated timestamp",
        ),
    )


def downgrade() -> None:
    """Remove added columns."""
    op.drop_column("feedback_logs", "updated_at")
    op.drop_column("feedback_logs", "metadata_")
    op.drop_column("cost_tracking", "updated_at")
