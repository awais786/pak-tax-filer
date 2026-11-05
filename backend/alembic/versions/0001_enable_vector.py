"""Enable the pgvector extension (feature 001, research R3).

Revision ID: 0001_enable_vector
Revises:
Create Date: 2026-11-05
"""

# Alembic requires these lowercase names and numbered file names, and fills in `op` at run time.
# pylint: disable=invalid-name,no-member

from alembic import op

revision: str = "0001_enable_vector"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Make the vector type available (used by feature 006's passages)."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Remove the extension again."""
    op.execute("DROP EXTENSION IF EXISTS vector")
