"""Add watchlists table for prospect tracking

Revision ID: 012
Revises: 011
Create Date: 2025-10-03 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create watchlists table for tracking user's watched prospects

    Fields:
    - id: Primary key
    - user_id: Foreign key to users table
    - prospect_id: Foreign key to prospects table
    - notes: Optional user notes about the prospect
    - added_at: Timestamp when prospect was added to watchlist
    - last_checked_at: Timestamp of last change check
    - notify_on_changes: Boolean flag for change notifications
    """
    op.create_table('watchlists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('prospect_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('notify_on_changes', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'prospect_id', name='uq_user_prospect_watchlist')
    )

    # Create indexes for efficient queries
    op.create_index(op.f('ix_watchlists_user_id'), 'watchlists', ['user_id'], unique=False)
    op.create_index(op.f('ix_watchlists_prospect_id'), 'watchlists', ['prospect_id'], unique=False)
    op.create_index(op.f('ix_watchlists_added_at'), 'watchlists', ['added_at'], unique=False)


def downgrade() -> None:
    """
    Drop watchlists table
    """
    op.drop_index(op.f('ix_watchlists_added_at'), table_name='watchlists')
    op.drop_index(op.f('ix_watchlists_prospect_id'), table_name='watchlists')
    op.drop_index(op.f('ix_watchlists_user_id'), table_name='watchlists')
    op.drop_table('watchlists')
