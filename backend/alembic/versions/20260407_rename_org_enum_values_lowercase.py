"""Rename organizationrole and invitationstatus enum values to lowercase

Revision ID: i4d5e6f7a863
Revises: h3c4d5e6f752
Create Date: 2026-04-07

The Postgres enum types `organizationrole` and `invitationstatus` were
originally created with UPPERCASE labels (OWNER, ADMIN, MEMBER, VIEWER /
PENDING, ACCEPTED, EXPIRED, REVOKED). The Python enums use lowercase
values, and the SQLAlchemy models now use `values_callable` to bind the
lowercase forms. Without this migration, every INSERT into
organization_invitations / organization_users fails with
`invalid input value for enum ... "member"` causing HTTP 500 on the
invite-team-member endpoint.

Postgres 10+ `ALTER TYPE ... RENAME VALUE` preserves existing rows.
"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "i4d5e6f7a863"
down_revision = "h3c4d5e6f752"
branch_labels = None
depends_on = None


ROLE_VALUES = [
    ("OWNER", "owner"),
    ("ADMIN", "admin"),
    ("MEMBER", "member"),
    ("VIEWER", "viewer"),
]

STATUS_VALUES = [
    ("PENDING", "pending"),
    ("ACCEPTED", "accepted"),
    ("EXPIRED", "expired"),
    ("REVOKED", "revoked"),
]


def _enum_labels(enum_name: str) -> set:
    bind = op.get_bind()
    result = bind.execute(
        text(
            "SELECT e.enumlabel FROM pg_type t "
            "JOIN pg_enum e ON t.oid = e.enumtypid "
            "WHERE t.typname = :name"
        ),
        {"name": enum_name},
    )
    return {row[0] for row in result}


def upgrade() -> None:
    # organizationrole
    existing = _enum_labels("organizationrole")
    for old, new in ROLE_VALUES:
        if old in existing and new not in existing:
            op.execute(f"ALTER TYPE organizationrole RENAME VALUE '{old}' TO '{new}'")

    # invitationstatus
    existing = _enum_labels("invitationstatus")
    for old, new in STATUS_VALUES:
        if old in existing and new not in existing:
            op.execute(f"ALTER TYPE invitationstatus RENAME VALUE '{old}' TO '{new}'")


def downgrade() -> None:
    existing = _enum_labels("organizationrole")
    for old, new in ROLE_VALUES:
        if new in existing and old not in existing:
            op.execute(f"ALTER TYPE organizationrole RENAME VALUE '{new}' TO '{old}'")

    existing = _enum_labels("invitationstatus")
    for old, new in STATUS_VALUES:
        if new in existing and old not in existing:
            op.execute(f"ALTER TYPE invitationstatus RENAME VALUE '{new}' TO '{old}'")
