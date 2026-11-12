"""Store shopping intent and snapshot-scoped AI comparisons.

Revision ID: f38b09c51a24
Revises: e71c20a4b938
"""

from alembic import op
import sqlalchemy as sa


revision = "f38b09c51a24"
down_revision = "e71c20a4b938"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shopping_sessions", sa.Column("intent", sa.JSON(), nullable=True))
    op.add_column(
        "shopping_sessions", sa.Column("ai_comparison", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shopping_sessions", "ai_comparison")
    op.drop_column("shopping_sessions", "intent")
