"""Backfill existing users as approved

Ensure all currently active users remain active and verified after the
introduction of the registration approval gate.  New personal registrations
now start with is_active=False, so existing users must be explicitly
marked as is_active=True and is_verified=True to prevent lockout.

This is a data-only migration -- no schema changes are required because
the is_active and is_verified columns already exist on the users table.

Revision ID: c8e4f2a1b753
Revises: b7c9d2e4f316
Create Date: 2026-02-23 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8e4f2a1b753"
down_revision: Union[str, None] = "b7c9d2e4f316"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill existing active-but-unverified users as verified.

    Only touches users that are active but not yet verified, ensuring:
    - Users who were already verified are not modified.
    - Users who were deactivated for cause remain untouched.
    - Running this migration again is a no-op (idempotent).
    """
    op.execute(
        "UPDATE users SET is_verified = TRUE "
        "WHERE is_active = TRUE AND is_verified = FALSE"
    )


def downgrade() -> None:
    """No-op: we never want to deactivate users on downgrade."""
    pass
