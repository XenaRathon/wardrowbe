"""calendar_sharing: is_private, worn_by_user_id, outfit.worn_at, wear_nudge

Revision ID: aa19f37becf4
Revises: e1f2g3h4i5j6
Create Date: 2026-07-04 12:57:28.358956

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'aa19f37becf4'
down_revision: str | None = 'e1f2g3h4i5j6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'clothing_items',
        sa.Column('is_private', sa.Boolean(), server_default='false', nullable=False),
    )
    op.add_column(
        'item_history',
        sa.Column('worn_by_user_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'item_history_worn_by_user_id_fkey', 'item_history', 'users', ['worn_by_user_id'], ['id']
    )
    op.add_column(
        'outfits',
        sa.Column('worn_at', sa.Date(), nullable=True),
    )
    op.create_index(op.f('ix_outfits_worn_at'), 'outfits', ['worn_at'], unique=False)
    op.add_column(
        'user_preferences',
        sa.Column('wear_nudge_enabled', sa.Boolean(), server_default='true', nullable=False),
    )
    op.add_column(
        'user_preferences',
        sa.Column('wear_nudge_time', sa.Time(), server_default='20:00', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('user_preferences', 'wear_nudge_time')
    op.drop_column('user_preferences', 'wear_nudge_enabled')
    op.drop_index(op.f('ix_outfits_worn_at'), table_name='outfits')
    op.drop_column('outfits', 'worn_at')
    op.drop_constraint('item_history_worn_by_user_id_fkey', 'item_history', type_='foreignkey')
    op.drop_column('item_history', 'worn_by_user_id')
    op.drop_column('clothing_items', 'is_private')
