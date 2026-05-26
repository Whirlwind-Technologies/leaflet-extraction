"""Add request context and success columns to webhook_deliveries

Adds four new columns to the webhook_deliveries table:

- request_url (VARCHAR 500): The URL the request was sent to.
- request_headers (JSONB): HTTP headers sent (secrets redacted).
- request_body (JSONB): The JSON body that was POSTed.
- success (BOOLEAN NOT NULL DEFAULT false): Quick flag for 2xx response.

These columns allow delivery logs to be fully self-contained for
debugging without needing to cross-reference the parent webhook.

Revision ID: a3d5f7e9b148
Revises: f8b3c4d5e617
Create Date: 2026-02-07 15:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a3d5f7e9b148"
down_revision: Union[str, None] = "f8b3c4d5e617"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add request context and success columns to webhook_deliveries."""
    op.add_column(
        "webhook_deliveries",
        sa.Column(
            "request_url",
            sa.String(length=500),
            nullable=True,
            comment="Target URL the request was sent to",
        ),
    )
    op.add_column(
        "webhook_deliveries",
        sa.Column(
            "request_headers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="HTTP headers sent with the request (secrets redacted)",
        ),
    )
    op.add_column(
        "webhook_deliveries",
        sa.Column(
            "request_body",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Serialized JSON body that was POSTed",
        ),
    )
    op.add_column(
        "webhook_deliveries",
        sa.Column(
            "success",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether delivery succeeded (2xx response)",
        ),
    )

    # Backfill existing rows: set success=true where status='success'.
    op.execute(
        "UPDATE webhook_deliveries SET success = true WHERE status = 'success'"
    )

    # Backfill request_url from the parent webhook's url.
    op.execute(
        """
        UPDATE webhook_deliveries wd
        SET request_url = w.url
        FROM webhooks w
        WHERE wd.webhook_id = w.id
          AND wd.request_url IS NULL
        """
    )


def downgrade() -> None:
    """Remove request context and success columns from webhook_deliveries."""
    op.drop_column("webhook_deliveries", "success")
    op.drop_column("webhook_deliveries", "request_body")
    op.drop_column("webhook_deliveries", "request_headers")
    op.drop_column("webhook_deliveries", "request_url")
