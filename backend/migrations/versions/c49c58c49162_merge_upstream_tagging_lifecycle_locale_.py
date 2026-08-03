"""merge upstream tagging-lifecycle + locale heads

Revision ID: c49c58c49162
Revises: d4e5f6a7b8c9, e53191fcdd54
Create Date: 2026-08-03 18:36:58.168846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c49c58c49162'
down_revision: Union[str, None] = ('d4e5f6a7b8c9', 'e53191fcdd54')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
