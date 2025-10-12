"""Add HYPE feature tables

Revision ID: add_hype_tables
Revises:
Create Date: 2025-01-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_hype_tables'
down_revision = '6f9aa7d4751c'
branch_labels = None
depends_on = None


def upgrade():
    # Create player_hype table
    op.create_table('player_hype',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('player_name', sa.String(), nullable=False),
        sa.Column('player_type', sa.String(), nullable=False),
        sa.Column('hype_score', sa.Float(), nullable=True),
        sa.Column('hype_trend', sa.Float(), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('virality_score', sa.Float(), nullable=True),
        sa.Column('total_mentions_24h', sa.Integer(), nullable=True),
        sa.Column('total_mentions_7d', sa.Integer(), nullable=True),
        sa.Column('total_mentions_30d', sa.Integer(), nullable=True),
        sa.Column('total_likes', sa.Integer(), nullable=True),
        sa.Column('total_shares', sa.Integer(), nullable=True),
        sa.Column('total_comments', sa.Integer(), nullable=True),
        sa.Column('engagement_rate', sa.Float(), nullable=True),
        sa.Column('last_calculated', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_player_hype_player_id'), 'player_hype', ['player_id'], unique=False)

    # Create social_mentions table
    op.create_table('social_mentions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_hype_id', sa.Integer(), nullable=True),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('post_id', sa.String(), nullable=False),
        sa.Column('author_handle', sa.String(), nullable=True),
        sa.Column('author_followers', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('media_urls', sa.JSON(), nullable=True),
        sa.Column('hashtags', sa.JSON(), nullable=True),
        sa.Column('likes', sa.Integer(), nullable=True),
        sa.Column('shares', sa.Integer(), nullable=True),
        sa.Column('comments', sa.Integer(), nullable=True),
        sa.Column('views', sa.Integer(), nullable=True),
        sa.Column('sentiment', sa.String(), nullable=True),
        sa.Column('sentiment_confidence', sa.Float(), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('posted_at', sa.DateTime(), nullable=True),
        sa.Column('collected_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['player_hype_id'], ['player_hype.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id')
    )

    # Create media_articles table
    op.create_table('media_articles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_hype_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('author', sa.String(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('sentiment', sa.String(), nullable=True),
        sa.Column('sentiment_confidence', sa.Float(), nullable=True),
        sa.Column('prominence_score', sa.Float(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('collected_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['player_hype_id'], ['player_hype.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url')
    )

    # Create hype_history table
    op.create_table('hype_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_hype_id', sa.Integer(), nullable=True),
        sa.Column('hype_score', sa.Float(), nullable=False),
        sa.Column('sentiment_score', sa.Float(), nullable=False),
        sa.Column('virality_score', sa.Float(), nullable=False),
        sa.Column('total_mentions', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('granularity', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['player_hype_id'], ['player_hype.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create hype_alerts table
    op.create_table('hype_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('alert_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('hype_score_before', sa.Float(), nullable=True),
        sa.Column('hype_score_after', sa.Float(), nullable=True),
        sa.Column('change_percentage', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('acknowledged', sa.Boolean(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hype_alerts_player_id'), 'hype_alerts', ['player_id'], unique=False)

    # Create trending_topics table
    op.create_table('trending_topics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('topic', sa.String(), nullable=False),
        sa.Column('topic_type', sa.String(), nullable=True),
        sa.Column('mention_count', sa.Integer(), nullable=True),
        sa.Column('engagement_total', sa.Integer(), nullable=True),
        sa.Column('sentiment_average', sa.Float(), nullable=True),
        sa.Column('started_trending', sa.DateTime(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trending_topics_player_id'), 'trending_topics', ['player_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_trending_topics_player_id'), table_name='trending_topics')
    op.drop_table('trending_topics')
    op.drop_index(op.f('ix_hype_alerts_player_id'), table_name='hype_alerts')
    op.drop_table('hype_alerts')
    op.drop_table('hype_history')
    op.drop_table('media_articles')
    op.drop_table('social_mentions')
    op.drop_index(op.f('ix_player_hype_player_id'), table_name='player_hype')
    op.drop_table('player_hype')