"""add my_team fields to fantrax_leagues

Revision ID: c67ca5c732c0
Revises: 0c9d5a8edc04
Create Date: 2025-10-16 22:38:16.101181

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c67ca5c732c0'
down_revision = '0c9d5a8edc04'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add my_team_id and my_team_name columns to fantrax_leagues
    op.add_column('fantrax_leagues', sa.Column('my_team_id', sa.String(length=100), nullable=True))
    op.add_column('fantrax_leagues', sa.Column('my_team_name', sa.String(length=200), nullable=True))


def downgrade() -> None:
    # Remove my_team_id and my_team_name columns from fantrax_leagues
    op.drop_column('fantrax_leagues', 'my_team_name')
    op.drop_column('fantrax_leagues', 'my_team_id')
