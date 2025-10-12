"""Change social_mentions to composite unique constraint

Revision ID: 33237cb5bb9b
Revises: 60f06475fb40
Create Date: 2025-10-10 21:14:46.874353

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '33237cb5bb9b'
down_revision = '60f06475fb40'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing unique constraint on post_id column
    op.drop_constraint('social_mentions_post_id_key', 'social_mentions', type_='unique')

    # Add composite unique constraint on (post_id, player_hype_id)
    op.create_unique_constraint(
        'uq_social_mention_player',
        'social_mentions',
        ['post_id', 'player_hype_id']
    )


def downgrade() -> None:
    # Remove composite unique constraint
    op.drop_constraint('uq_social_mention_player', 'social_mentions', type_='unique')

    # Restore unique constraint on post_id column
    op.create_unique_constraint('social_mentions_post_id_key', 'social_mentions', ['post_id'])