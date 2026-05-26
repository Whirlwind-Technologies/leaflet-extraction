"""Add notification_metadata to system_notifications
Revision ID: c4ddf64a11f8
Revises: c8e4f2a1b753
Create Date: 2026-03-11 23:38:13.657088+00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c4ddf64a11f8'
down_revision: Union[str, None] = 'c8e4f2a1b753'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Guard: 001_complete_initial already creates this column on fresh DBs
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'system_notifications' AND column_name = 'notification_metadata'"
    ))
    if not result.fetchone():
        op.add_column('system_notifications',
            sa.Column('notification_metadata', postgresql.JSONB(), nullable=False, server_default='{}')
        )

def downgrade() -> None:
    op.drop_column('system_notifications', 'notification_metadata')
