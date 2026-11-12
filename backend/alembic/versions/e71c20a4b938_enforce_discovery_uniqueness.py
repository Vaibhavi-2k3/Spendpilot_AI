"""Enforce session-scoped uniqueness and track listing freshness.

Revision ID: e71c20a4b938
Revises: d412c3dc5594
"""

from alembic import op
import sqlalchemy as sa


revision = "e71c20a4b938"
down_revision = "d412c3dc5594"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_products_session_url", "products",
        ["shopping_session_id", "product_url"],
    )
    op.create_unique_constraint(
        "uq_recommendations_session_product", "recommendations",
        ["shopping_session_id", "product_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_recommendations_session_product", "recommendations", type_="unique",
    )
    op.drop_constraint("uq_products_session_url", "products", type_="unique")
    op.drop_column("products", "last_seen_at")
