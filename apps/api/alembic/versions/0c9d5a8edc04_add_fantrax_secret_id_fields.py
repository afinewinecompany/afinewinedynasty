"""add fantrax secret id fields

Revision ID: 0c9d5a8edc04
Revises: 0b1f09f8d62d
Create Date: 2025-10-16 15:56:30.109647

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0c9d5a8edc04'
down_revision = '0b1f09f8d62d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add fantrax_secret_id column for official API authentication
    op.add_column('users', sa.Column('fantrax_secret_id', sa.Text(), nullable=True))

    # Add fantrax_connected boolean to track connection status
    op.add_column('users', sa.Column('fantrax_connected', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove the added columns
    op.drop_column('users', 'fantrax_connected')
    op.drop_column('users', 'fantrax_secret_id')