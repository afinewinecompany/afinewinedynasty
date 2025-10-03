"""Add engagement and retention tables (Tasks 3-8)

Revision ID: 013
Revises: 012
Create Date: 2025-10-03 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Task 4: Achievements
    op.create_table('achievements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('criteria', sa.String(50), nullable=False),
        sa.Column('icon', sa.String(50), nullable=False),
        sa.Column('points', sa.Integer(), default=10, nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('user_achievements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('achievement_id', sa.Integer(), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['achievement_id'], ['achievements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'achievement_id', name='uq_user_achievement')
    )
    op.create_index('ix_user_achievements_user_id', 'user_achievements', ['user_id'])

    # Task 5: Referrals
    op.create_table('referral_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('uses_remaining', sa.Integer(), default=10, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_referral_codes_code', 'referral_codes', ['code'], unique=True)

    op.create_table('referrals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('referrer_id', sa.Integer(), nullable=False),
        sa.Column('referred_user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), default='pending', nullable=False),
        sa.Column('reward_granted', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['referrer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['referred_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_referrals_referrer_id', 'referrals', ['referrer_id'])

    # Task 6: Feedback
    op.create_table('feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('feature_request', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_feedback_user_id', 'feedback', ['user_id'])
    op.create_index('ix_feedback_submitted_at', 'feedback', ['submitted_at'])

    # Task 7: Analytics
    op.create_table('analytics_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('event_name', sa.String(100), nullable=False),
        sa.Column('event_data', postgresql.JSONB(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_events_user_id', 'analytics_events', ['user_id'])
    op.create_index('ix_analytics_events_timestamp', 'analytics_events', ['timestamp'])
    op.create_index('ix_analytics_events_event_name', 'analytics_events', ['event_name'])

    # Task 8: Engagement Metrics
    op.create_table('user_engagement_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('login_frequency', sa.Integer(), default=0, nullable=False),
        sa.Column('feature_usage_score', sa.Float(), default=0.0, nullable=False),
        sa.Column('churn_risk_score', sa.Float(), default=0.0, nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_engagement_metrics_user_id', 'user_engagement_metrics', ['user_id'], unique=True)


def downgrade() -> None:
    op.drop_table('user_engagement_metrics')
    op.drop_table('analytics_events')
    op.drop_table('feedback')
    op.drop_table('referrals')
    op.drop_table('referral_codes')
    op.drop_table('user_achievements')
    op.drop_table('achievements')
