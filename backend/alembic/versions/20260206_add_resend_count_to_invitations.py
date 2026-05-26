"""Add resend_count to organization_invitations

Tracks how many times an invitation email has been resent so the
resend endpoint can enforce the MAX_INVITATION_RESENDS limit.

Revision ID: d7f3a9b2c614
Revises: c5d8e2f1a309
Create Date: 2026-02-06 18:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7f3a9b2c614"
down_revision: Union[str, None] = "c5d8e2f1a309"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add resend_count column to organization_invitations table."""
    op.add_column(
        "organization_invitations",
        sa.Column(
            "resend_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Number of times the invitation email has been resent",
        ),
    )


def downgrade() -> None:
    """Remove resend_count column from organization_invitations table."""
    op.drop_column("organization_invitations", "resend_count")
