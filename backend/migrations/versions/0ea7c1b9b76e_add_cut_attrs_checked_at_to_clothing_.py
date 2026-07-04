"""add cut_attrs_checked_at to clothing_items

Revision ID: 0ea7c1b9b76e
Revises: 941893d71cb0
Create Date: 2026-07-04 17:03:41.086800

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0ea7c1b9b76e"
down_revision: str | None = "941893d71cb0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clothing_items",
        sa.Column("cut_attrs_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clothing_items", "cut_attrs_checked_at")
