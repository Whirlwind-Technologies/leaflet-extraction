"""Webhook security hardening: encrypted secrets, soft delete, response body constraint

Three schema changes for the webhook security review:

1. Widen webhooks.secret from VARCHAR(64) to VARCHAR(500) to accommodate
   Fernet-encrypted values (base64 encoded ciphertext is ~200 chars).
2. Add webhooks.deleted_at (nullable TIMESTAMP) for soft-delete support,
   with an index for efficient filtering.
3. Change webhook_deliveries.response_body from unlimited TEXT to
   VARCHAR(10240), matching the application-level MAX_RESPONSE_BODY_LENGTH
   constant.  Existing rows longer than 10 KB are truncated.

Revision ID: b7c9d2e4f316
Revises: a3d5f7e9b148
Create Date: 2026-02-07 18:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c9d2e4f316"
down_revision: Union[str, None] = "a3d5f7e9b148"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply webhook security hardening schema changes."""

    # 1. Widen webhooks.secret to hold Fernet-encrypted values.
    op.alter_column(
        "webhooks",
        "secret",
        existing_type=sa.String(64),
        type_=sa.String(500),
        existing_nullable=False,
        comment="Fernet-encrypted secret for HMAC signing",
    )

    # 2. Add soft-delete column to webhooks.
    op.add_column(
        "webhooks",
        sa.Column(
            "deleted_at",
            sa.DateTime(),
            nullable=True,
            comment="Soft-delete timestamp (NULL = active, set = deleted)",
        ),
    )
    op.create_index(
        "ix_webhooks_deleted_at",
        "webhooks",
        ["deleted_at"],
    )

    # 3. Truncate any existing response bodies longer than 10 KB
    #    before altering the column type.
    op.execute(
        "UPDATE webhook_deliveries "
        "SET response_body = LEFT(response_body, 10240) "
        "WHERE length(response_body) > 10240"
    )

    op.alter_column(
        "webhook_deliveries",
        "response_body",
        existing_type=sa.Text(),
        type_=sa.String(10240),
        existing_nullable=True,
        comment="Response body (truncated to 10 KB max)",
    )


def downgrade() -> None:
    """Revert webhook security hardening schema changes."""

    # 3. Revert response_body back to TEXT.
    op.alter_column(
        "webhook_deliveries",
        "response_body",
        existing_type=sa.String(10240),
        type_=sa.Text(),
        existing_nullable=True,
    )

    # 2. Remove soft-delete column.
    op.drop_index("ix_webhooks_deleted_at", table_name="webhooks")
    op.drop_column("webhooks", "deleted_at")

    # 1. Revert secret column back to VARCHAR(64).
    #    NOTE: This will fail if any encrypted secrets exceed 64 chars.
    #    Only safe to run before data migration.
    op.alter_column(
        "webhooks",
        "secret",
        existing_type=sa.String(500),
        type_=sa.String(64),
        existing_nullable=False,
    )
