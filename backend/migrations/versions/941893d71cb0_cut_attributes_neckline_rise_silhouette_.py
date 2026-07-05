"""cut_attributes: neckline, rise, silhouette, sleeve_length

Revision ID: 941893d71cb0
Revises: e1f2g3h4i5j6
Create Date: 2026-07-04 16:16:49.293764

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "941893d71cb0"
down_revision: str | None = "e1f2g3h4i5j6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clothing_items", sa.Column("neckline", sa.String(length=30), nullable=True))
    op.add_column("clothing_items", sa.Column("rise", sa.String(length=30), nullable=True))
    op.add_column("clothing_items", sa.Column("silhouette", sa.String(length=30), nullable=True))
    op.add_column("clothing_items", sa.Column("sleeve_length", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("clothing_items", "sleeve_length")
    op.drop_column("clothing_items", "silhouette")
    op.drop_column("clothing_items", "rise")
    op.drop_column("clothing_items", "neckline")
