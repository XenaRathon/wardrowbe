"""merge b1 calendar-sharing + styler heads

Revision ID: e53191fcdd54
Revises: 0ea7c1b9b76e, aa19f37becf4
Create Date: 2026-07-04 22:54:30.846939

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e53191fcdd54'
down_revision: Union[str, None] = ('0ea7c1b9b76e', 'aa19f37becf4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
