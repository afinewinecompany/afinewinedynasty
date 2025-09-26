"""Add performance indexes for query optimization

Revision ID: 006
Revises: 005
Create Date: 2025-09-25 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Performance indexes on prospects table
    op.create_index('ix_prospects_organization', 'prospects', ['organization'])
    op.create_index('ix_prospects_position', 'prospects', ['position'])
    op.create_index('ix_prospects_eta_year', 'prospects', ['eta_year'])
    op.create_index('ix_prospects_org_position', 'prospects', ['organization', 'position'])

    # Composite indexes on prospect_stats table
    op.create_index('ix_prospect_stats_prospect_season', 'prospect_stats', ['prospect_id', 'season'])
    op.create_index('ix_prospect_stats_season', 'prospect_stats', ['season'])
    op.create_index('ix_prospect_stats_prospect_date', 'prospect_stats', ['prospect_id', 'date_recorded'])

    # Performance indexes on scouting_grades table
    op.create_index('ix_scouting_grades_source_updated', 'scouting_grades', ['source', 'updated_at'])
    op.create_index('ix_scouting_grades_prospect_id', 'scouting_grades', ['prospect_id'])
    op.create_index('ix_scouting_grades_prospect_source', 'scouting_grades', ['prospect_id', 'source'])

    # Additional indexes on users table for subscription queries
    op.create_index('ix_users_subscription_tier', 'users', ['subscription_tier'])


def downgrade() -> None:
    # Remove user indexes
    op.drop_index('ix_users_subscription_tier')

    # Remove scouting_grades indexes
    op.drop_index('ix_scouting_grades_prospect_source')
    op.drop_index('ix_scouting_grades_prospect_id')
    op.drop_index('ix_scouting_grades_source_updated')

    # Remove prospect_stats indexes
    op.drop_index('ix_prospect_stats_prospect_date')
    op.drop_index('ix_prospect_stats_season')
    op.drop_index('ix_prospect_stats_prospect_season')

    # Remove prospects indexes
    op.drop_index('ix_prospects_org_position')
    op.drop_index('ix_prospects_eta_year')
    op.drop_index('ix_prospects_position')
    op.drop_index('ix_prospects_organization')