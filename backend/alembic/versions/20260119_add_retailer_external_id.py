"""Add external_id column to retailers table

Revision ID: 20260119_add_external_id
Revises: None (standalone migration for existing deployments)
Create Date: 2026-01-19

This migration adds the external_id column to retailers table
for deployments that have the old migration chain without this column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260119_add_external_id'
down_revision: Union[str, None] = '001_complete_initial'   # Set to None to avoid chain conflicts
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add external_id column to retailers table if it doesn't exist."""
    # Use raw SQL to check if column exists and add if not
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'retailers' AND column_name = 'external_id'
            ) THEN
                ALTER TABLE retailers ADD COLUMN external_id VARCHAR(255);
                CREATE INDEX IF NOT EXISTS ix_retailers_external_id ON retailers (external_id);
                COMMENT ON COLUMN retailers.external_id IS 'Optional external identifier for integration with other systems';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Remove external_id column from retailers table."""
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'retailers' AND column_name = 'external_id'
            ) THEN
                DROP INDEX IF EXISTS ix_retailers_external_id;
                ALTER TABLE retailers DROP COLUMN external_id;
            END IF;
        END $$;
    """)
