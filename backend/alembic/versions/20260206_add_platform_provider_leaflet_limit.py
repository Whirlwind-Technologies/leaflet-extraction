"""Add platform provider leaflet limit to organizations

Track which leaflets used the platform shared AI provider and enforce
a per-organization quota (default: 10 free extractions).

Revision ID: c5d8e2f1a309
Revises: a1c4f7e8d902
Create Date: 2026-02-06 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5d8e2f1a309"
down_revision: Union[str, None] = "a1c4f7e8d902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add platform provider tracking columns and backfill historical data."""

    # 1. Add used_platform_provider to leaflets
    op.add_column(
        "leaflets",
        sa.Column(
            "used_platform_provider",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether extraction used the platform shared API key (not org's own provider)",
        ),
    )

    # 2. Add platform quota columns to organizations
    op.add_column(
        "organizations",
        sa.Column(
            "platform_leaflet_limit",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("10"),
            comment="Max leaflets this org can extract using the platform shared AI provider (0 = unlimited)",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "platform_leaflets_used",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Denormalized count of leaflets that used the platform provider",
        ),
    )

    # 3. Create composite index for efficient counting queries
    op.create_index(
        "ix_leaflets_org_platform_provider",
        "leaflets",
        ["organization_id", "used_platform_provider"],
    )

    # 4. Backfill: Mark historical leaflets that reached extraction as having used the platform provider.
    #    All leaflets that reached extraction used the platform provider because
    #    no organization-level providers existed before this feature.
    #    LeafletStatus values (stored as VARCHAR, native_enum=False):
    #    completed, reviewing, extracting, validating, failed
    op.execute(
        sa.text(
            """
            UPDATE leaflets
            SET used_platform_provider = true
            WHERE status IN ('completed', 'reviewing', 'extracting', 'validating', 'failed')
              AND used_platform_provider = false
            """
        )
    )

    # 5. Backfill: Update denormalized counters on organizations
    op.execute(
        sa.text(
            """
            UPDATE organizations o
            SET platform_leaflets_used = (
                SELECT COUNT(*)
                FROM leaflets l
                WHERE l.organization_id = o.id
                  AND l.used_platform_provider = true
            )
            """
        )
    )


def downgrade() -> None:
    """Remove platform provider tracking columns."""

    # Drop the composite index
    op.drop_index("ix_leaflets_org_platform_provider", table_name="leaflets")

    # Drop columns from organizations
    op.drop_column("organizations", "platform_leaflets_used")
    op.drop_column("organizations", "platform_leaflet_limit")

    # Drop column from leaflets
    op.drop_column("leaflets", "used_platform_provider")
