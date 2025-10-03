"""Add onboarding fields to users table

Revision ID: 011
Revises: 010
Create Date: 2025-10-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add onboarding tracking fields to users table

    Fields added:
    - onboarding_completed: Boolean flag indicating if user completed onboarding
    - onboarding_step: Integer tracking current step in onboarding flow (0-based)
    - onboarding_started_at: Timestamp when user first started onboarding
    - onboarding_completed_at: Timestamp when user completed onboarding
    """
    op.add_column('users', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('onboarding_step', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('onboarding_started_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('onboarding_completed_at', sa.DateTime(), nullable=True))

    # Create index for querying users by onboarding status
    op.create_index(op.f('ix_users_onboarding_completed'), 'users', ['onboarding_completed'], unique=False)


def downgrade() -> None:
    """
    Remove onboarding tracking fields from users table
    """
    op.drop_index(op.f('ix_users_onboarding_completed'), table_name='users')
    op.drop_column('users', 'onboarding_completed_at')
    op.drop_column('users', 'onboarding_started_at')
    op.drop_column('users', 'onboarding_step')
    op.drop_column('users', 'onboarding_completed')
