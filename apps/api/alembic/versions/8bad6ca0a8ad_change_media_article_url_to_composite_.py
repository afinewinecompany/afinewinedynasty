"""change_media_article_url_to_composite_unique

Revision ID: 8bad6ca0a8ad
Revises: add_hype_tables
Create Date: 2025-10-10 19:36:32.116765

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8bad6ca0a8ad'
down_revision = 'add_hype_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing unique constraint on url column
    op.drop_constraint('media_articles_url_key', 'media_articles', type_='unique')

    # Add composite unique constraint on (url, player_hype_id)
    op.create_unique_constraint(
        'uq_media_article_player',
        'media_articles',
        ['url', 'player_hype_id']
    )


def downgrade() -> None:
    # Remove composite unique constraint
    op.drop_constraint('uq_media_article_player', 'media_articles', type_='unique')

    # Restore unique constraint on url column
    op.create_unique_constraint('media_articles_url_key', 'media_articles', ['url'])