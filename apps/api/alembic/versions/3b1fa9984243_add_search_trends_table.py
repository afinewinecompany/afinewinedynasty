"""add_search_trends_table

Revision ID: 3b1fa9984243
Revises: a9a3952fbabf
Create Date: 2025-10-13 20:27:45.067954

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = '3b1fa9984243'
down_revision = 'a9a3952fbabf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create search_trends table
    op.create_table(
        'search_trends',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_hype_id', sa.Integer(), nullable=True),
        sa.Column('search_interest', sa.Float(), nullable=False),
        sa.Column('search_interest_avg_7d', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('search_interest_avg_30d', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('search_growth_rate', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('region', sa.String(), nullable=True, server_default='US'),
        sa.Column('regional_interest', JSON, nullable=True),
        sa.Column('related_queries', JSON, nullable=True),
        sa.Column('rising_queries', JSON, nullable=True),
        sa.Column('collected_at', sa.DateTime(), nullable=True),
        sa.Column('data_period_start', sa.DateTime(), nullable=True),
        sa.Column('data_period_end', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['player_hype_id'], ['player_hype.id'], ),
    )
    op.create_index(op.f('ix_search_trends_id'), 'search_trends', ['id'], unique=False)


def downgrade() -> None:
    # Drop search_trends table
    op.drop_index(op.f('ix_search_trends_id'), table_name='search_trends')
    op.drop_table('search_trends')