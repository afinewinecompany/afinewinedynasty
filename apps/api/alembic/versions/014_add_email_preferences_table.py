"""Add email_preferences table for email digest settings

Revision ID: 014
Revises: 013
Create Date: 2025-10-03 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Email preferences table for digest settings
    op.create_table('email_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('digest_enabled', sa.Boolean(), default=True, nullable=False),
        sa.Column('frequency', sa.String(20), default='weekly', nullable=False),
        sa.Column('last_sent', sa.DateTime(), nullable=True),
        sa.Column('preferences', postgresql.JSONB(), default={}, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_email_preferences_user_id', 'email_preferences', ['user_id'], unique=True)
    op.create_index('ix_email_preferences_last_sent', 'email_preferences', ['last_sent'])


def downgrade() -> None:
    op.drop_table('email_preferences')
