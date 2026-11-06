"""Taxpayer profiles: one per user, tax year and ATL status (feature 002, data-model.md).

Revision ID: 0003_taxpayer_profiles
Revises: 0002_auth_tables
Create Date: 2026-11-05 09:54:08.836651

"""
# Alembic requires these lowercase names and numbered file names, and fills in `op` at run time.
# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa  # pylint: disable=unused-import
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0003_taxpayer_profiles"
down_revision: str | Sequence[str] | None = "0002_auth_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "taxpayer_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tax_year", sa.String(), nullable=False),
        sa.Column("on_atl", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("taxpayer_profiles")
