"""Add export_jobs table for async product exports

Creates the export_jobs table used to track asynchronous product export
jobs dispatched to Celery.  Includes indexes on organization_id and
status for efficient polling queries.

Revision ID: f8b3c4d5e617
Revises: e4a2b7c9d135
Create Date: 2026-02-07 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f8b3c4d5e617"
down_revision: Union[str, None] = "e4a2b7c9d135"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the export_jobs table."""
    op.create_table(
        "export_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("request_params", postgresql.JSONB, nullable=True),
        sa.Column("product_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Composite index for listing a user's/org's active jobs
    op.create_index(
        "ix_export_jobs_org_status",
        "export_jobs",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    """Drop the export_jobs table."""
    op.drop_index("ix_export_jobs_org_status", table_name="export_jobs")
    op.drop_table("export_jobs")
