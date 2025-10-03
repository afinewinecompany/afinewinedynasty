"""Add recommendation preferences tables

Revision ID: 010_add_recommendation_preferences
Revises: 009_add_fantrax_tables
Create Date: 2025-10-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010_add_recommendation_preferences'
down_revision = '009_add_fantrax_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema"""

    # Create user_recommendation_preferences table
    op.create_table(
        'user_recommendation_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),

        # Risk tolerance settings
        sa.Column('risk_tolerance', sa.String(length=20), nullable=False, server_default='balanced'),

        # Timeline preferences
        sa.Column('prefer_win_now', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('prefer_rebuild', sa.Boolean(), nullable=False, server_default='false'),

        # Position priorities (JSON array)
        sa.Column('position_priorities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Trade preferences
        sa.Column('prefer_buy_low', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('prefer_sell_high', sa.Boolean(), nullable=False, server_default='true'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), onupdate=sa.text('now()')),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint("risk_tolerance IN ('conservative', 'balanced', 'aggressive')", name='valid_risk_tolerance')
    )

    # Create indexes for user_recommendation_preferences
    op.create_index('ix_user_recommendation_preferences_user_id', 'user_recommendation_preferences', ['user_id'], unique=True)

    # Create recommendation_history table
    op.create_table(
        'recommendation_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=True),  # Nullable for system-wide recommendations
        sa.Column('prospect_id', sa.Integer(), nullable=False),

        # Recommendation details
        sa.Column('recommendation_type', sa.String(length=20), nullable=False),
        sa.Column('fit_score', sa.Float(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),

        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['league_id'], ['fantrax_leagues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ondelete='CASCADE'),
        sa.CheckConstraint("recommendation_type IN ('fit', 'trade', 'draft', 'stash')", name='valid_recommendation_type')
    )

    # Create indexes for recommendation_history
    op.create_index('ix_recommendation_history_user_id', 'recommendation_history', ['user_id'])
    op.create_index('ix_recommendation_history_league_id', 'recommendation_history', ['league_id'])
    op.create_index('ix_recommendation_history_prospect_id', 'recommendation_history', ['prospect_id'])
    op.create_index('ix_recommendation_history_created_at', 'recommendation_history', ['created_at'])

    # Create recommendation_feedback table
    op.create_table(
        'recommendation_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recommendation_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),

        # Feedback details
        sa.Column('feedback_type', sa.String(length=20), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),

        # Timestamp
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['recommendation_id'], ['recommendation_history.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint("feedback_type IN ('helpful', 'not_helpful', 'inaccurate')", name='valid_feedback_type')
    )

    # Create indexes for recommendation_feedback
    op.create_index('ix_recommendation_feedback_recommendation_id', 'recommendation_feedback', ['recommendation_id'])
    op.create_index('ix_recommendation_feedback_user_id', 'recommendation_feedback', ['user_id'])


def downgrade() -> None:
    """Downgrade database schema"""

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_index('ix_recommendation_feedback_user_id', table_name='recommendation_feedback')
    op.drop_index('ix_recommendation_feedback_recommendation_id', table_name='recommendation_feedback')
    op.drop_table('recommendation_feedback')

    op.drop_index('ix_recommendation_history_created_at', table_name='recommendation_history')
    op.drop_index('ix_recommendation_history_prospect_id', table_name='recommendation_history')
    op.drop_index('ix_recommendation_history_league_id', table_name='recommendation_history')
    op.drop_index('ix_recommendation_history_user_id', table_name='recommendation_history')
    op.drop_table('recommendation_history')

    op.drop_index('ix_user_recommendation_preferences_user_id', table_name='user_recommendation_preferences')
    op.drop_table('user_recommendation_preferences')
