"""merge heads

Revision ID: e15fd0428f23
Revises: 001_complete_initial, 20260119_add_external_id
Create Date: 2026-01-28 23:58:54.640036+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e15fd0428f23'
down_revision: Union[str, None] = ('001_complete_initial', '20260119_add_external_id')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Downgrade database schema."""
    pass