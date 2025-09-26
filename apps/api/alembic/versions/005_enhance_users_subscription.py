"""Enhance users table with subscription management fields

Revision ID: 005
Revises: 004
Create Date: 2025-09-25 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add subscription management fields to users table
    op.add_column('users', sa.Column('subscription_tier', sa.String(length=20), nullable=False, server_default='free'))
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('fantrax_user_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('fantrax_refresh_token', sa.String(length=512), nullable=True))

    # Change preferences column to JSONB
    op.alter_column('users', 'preferences', type_=postgresql.JSONB(), existing_type=sa.Text(), postgresql_using='preferences::jsonb', server_default='{}')

    # Add constraints
    op.create_check_constraint('valid_subscription_tier', 'users', "subscription_tier IN ('free', 'premium')")
    op.create_unique_constraint('uq_users_stripe_customer_id', 'users', ['stripe_customer_id'])
    op.create_unique_constraint('uq_users_fantrax_user_id', 'users', ['fantrax_user_id'])


def downgrade() -> None:
    # Remove constraints
    op.drop_constraint('uq_users_fantrax_user_id', 'users', type_='unique')
    op.drop_constraint('uq_users_stripe_customer_id', 'users', type_='unique')
    op.drop_constraint('valid_subscription_tier', 'users', type_='check')

    # Change preferences back to TEXT
    op.alter_column('users', 'preferences', type_=sa.Text(), existing_type=postgresql.JSONB(), postgresql_using='preferences::text', server_default='{}')

    # Remove added columns
    op.drop_column('users', 'fantrax_refresh_token')
    op.drop_column('users', 'fantrax_user_id')
    op.drop_column('users', 'stripe_customer_id')
    op.drop_column('users', 'subscription_tier')