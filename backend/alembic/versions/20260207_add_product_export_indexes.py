"""Add composite indexes on products table for export queries

Adds three composite indexes to accelerate filtered product exports
and the review queue endpoint:

1. (organization_id, review_status) -- export filtered by status
2. (organization_id, review_status, review_priority DESC, confidence ASC) -- review queue ordering
3. (organization_id, leaflet_id, review_status) -- per-leaflet export with status filter

Revision ID: e4a2b7c9d135
Revises: d7f3a9b2c614
Create Date: 2026-02-07 00:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4a2b7c9d135"
down_revision: Union[str, None] = "d7f3a9b2c614"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes for product export and review queue queries."""

    # 1. Composite index for org + status filtering (most common export filter).
    #    Covers: WHERE organization_id = X AND review_status IN (...)
    op.create_index(
        "ix_products_org_review_status",
        "products",
        ["organization_id", "review_status"],
    )

    # 2. Composite index for the review queue ordering.
    #    Covers: WHERE organization_id = X AND review_status IN ('pending', 'needs_correction')
    #            ORDER BY review_priority DESC, confidence ASC
    #    Uses postgresql_ops for descending/ascending sort directions so the
    #    planner can satisfy the ORDER BY directly from the index without a sort step.
    op.create_index(
        "ix_products_org_review_queue",
        "products",
        [
            sa.text("organization_id"),
            sa.text("review_status"),
            sa.text("review_priority DESC"),
            sa.text("confidence ASC"),
        ],
    )

    # 3. Composite index for per-leaflet export with optional status filter.
    #    Covers: WHERE organization_id = X AND leaflet_id = Y [AND review_status = ...]
    op.create_index(
        "ix_products_org_leaflet_status",
        "products",
        ["organization_id", "leaflet_id", "review_status"],
    )


def downgrade() -> None:
    """Remove composite export indexes from products table."""
    op.drop_index("ix_products_org_leaflet_status", table_name="products")
    op.drop_index("ix_products_org_review_queue", table_name="products")
    op.drop_index("ix_products_org_review_status", table_name="products")
