"""add_is_admin_to_users

Revision ID: 0b1f09f8d62d
Revises: 3b1fa9984243
Create Date: 2025-10-14 12:50:04.742187

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0b1f09f8d62d'
down_revision = '3b1fa9984243'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_admin column to users table
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove is_admin column from users table
    op.drop_column('users', 'is_admin')