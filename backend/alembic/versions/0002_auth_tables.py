"""Auth tables: users, sessions, login_failures (feature 002, data-model.md).

Revision ID: 0002_auth_tables
Revises: 0001_enable_vector
Create Date: 2026-11-05 09:18:45.035358

"""
# Alembic requires these lowercase names and numbered file names, and fills in `op` at run time.
# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa  # pylint: disable=unused-import
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0002_auth_tables"
down_revision: str | Sequence[str] | None = "0001_enable_vector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "login_failures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_login_failures_email_attempted_at",
        "login_failures",
        ["email", "attempted_at"],
        unique=False,
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_index("ix_login_failures_email_attempted_at", table_name="login_failures")
    op.drop_table("login_failures")
