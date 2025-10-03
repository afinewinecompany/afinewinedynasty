"""Update Fantrax to cookie-based authentication

Revision ID: 010
Revises: 009
Create Date: 2025-10-03 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade to cookie-based Fantrax authentication

    Changes:
    - Remove fantrax_user_id and fantrax_refresh_token columns
    - Add fantrax_cookies column for storing encrypted cookie data
    """
    # Drop old OAuth columns
    op.drop_column('users', 'fantrax_user_id')
    op.drop_column('users', 'fantrax_refresh_token')

    # Add new cookie column
    op.add_column('users', sa.Column('fantrax_cookies', sa.Text(), nullable=True))


def downgrade() -> None:
    """
    Downgrade from cookie-based to OAuth authentication
    """
    # Remove cookie column
    op.drop_column('users', 'fantrax_cookies')

    # Restore old OAuth columns
    op.add_column('users', sa.Column('fantrax_user_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('fantrax_refresh_token', sa.String(512), nullable=True))

    # Restore unique constraint on fantrax_user_id
    op.create_unique_constraint('uq_users_fantrax_user_id', 'users', ['fantrax_user_id'])
