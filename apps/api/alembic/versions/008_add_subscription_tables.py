"""Add subscription management tables

Revision ID: 008
Revises: 007
Create Date: 2025-10-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    """Create subscription management tables."""

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('plan_id', sa.String(length=100), nullable=False),
        sa.Column('current_period_start', sa.DateTime(), nullable=False),
        sa.Column('current_period_end', sa.DateTime(), nullable=False),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.UniqueConstraint('stripe_subscription_id'),
        sa.CheckConstraint(
            "status IN ('active', 'past_due', 'unpaid', 'canceled', 'trialing', 'incomplete')",
            name='valid_subscription_status'
        ),
        sa.CheckConstraint(
            "plan_id IN ('free', 'premium')",
            name='valid_plan_id'
        )
    )
    op.create_index(op.f('ix_subscriptions_id'), 'subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_subscriptions_stripe_subscription_id'), 'subscriptions', ['stripe_subscription_id'], unique=True)
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=True)

    # Create payment_methods table
    op.create_table(
        'payment_methods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('stripe_payment_method_id', sa.String(length=255), nullable=False),
        sa.Column('card_brand', sa.String(length=50), nullable=False),
        sa.Column('last4', sa.String(length=4), nullable=False),
        sa.Column('exp_month', sa.Integer(), nullable=False),
        sa.Column('exp_year', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_payment_method_id')
    )
    op.create_index(op.f('ix_payment_methods_id'), 'payment_methods', ['id'], unique=False)
    op.create_index(op.f('ix_payment_methods_user_id'), 'payment_methods', ['user_id'], unique=False)

    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('stripe_invoice_id', sa.String(length=255), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=False),
        sa.Column('amount_paid', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('billing_reason', sa.String(length=100), nullable=False),
        sa.Column('invoice_pdf', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_invoice_id')
    )
    op.create_index(op.f('ix_invoices_id'), 'invoices', ['id'], unique=False)
    op.create_index(op.f('ix_invoices_stripe_invoice_id'), 'invoices', ['stripe_invoice_id'], unique=True)
    op.create_index(op.f('ix_invoices_user_id'), 'invoices', ['user_id'], unique=False)

    # Create subscription_events table for audit trail
    op.create_table(
        'subscription_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('stripe_event_id', sa.String(length=255), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_event_id')
    )
    op.create_index(op.f('ix_subscription_events_id'), 'subscription_events', ['id'], unique=False)
    op.create_index('idx_subscription_events_subscription_id', 'subscription_events', ['subscription_id'], unique=False)
    op.create_index('idx_subscription_events_event_type', 'subscription_events', ['event_type'], unique=False)
    op.create_index('idx_subscription_events_created_at', 'subscription_events', ['created_at'], unique=False)

    # Create payment_audit_logs table for PCI compliance
    op.create_table(
        'payment_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('payment_method_last4', sa.String(length=4), nullable=True),
        sa.Column('card_brand', sa.String(length=50), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('failure_reason', sa.String(length=255), nullable=True),
        sa.Column('stripe_event_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payment_audit_logs_id'), 'payment_audit_logs', ['id'], unique=False)
    op.create_index('idx_payment_audit_user_id', 'payment_audit_logs', ['user_id'], unique=False)
    op.create_index('idx_payment_audit_created_at', 'payment_audit_logs', ['created_at'], unique=False)
    op.create_index('idx_payment_audit_action', 'payment_audit_logs', ['action'], unique=False)


def downgrade():
    """Drop subscription management tables."""

    # Drop tables in reverse order due to foreign key constraints
    op.drop_index('idx_payment_audit_action', table_name='payment_audit_logs')
    op.drop_index('idx_payment_audit_created_at', table_name='payment_audit_logs')
    op.drop_index('idx_payment_audit_user_id', table_name='payment_audit_logs')
    op.drop_index(op.f('ix_payment_audit_logs_id'), table_name='payment_audit_logs')
    op.drop_table('payment_audit_logs')

    op.drop_index('idx_subscription_events_created_at', table_name='subscription_events')
    op.drop_index('idx_subscription_events_event_type', table_name='subscription_events')
    op.drop_index('idx_subscription_events_subscription_id', table_name='subscription_events')
    op.drop_index(op.f('ix_subscription_events_id'), table_name='subscription_events')
    op.drop_table('subscription_events')

    op.drop_index(op.f('ix_invoices_user_id'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_stripe_invoice_id'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_id'), table_name='invoices')
    op.drop_table('invoices')

    op.drop_index(op.f('ix_payment_methods_user_id'), table_name='payment_methods')
    op.drop_index(op.f('ix_payment_methods_id'), table_name='payment_methods')
    op.drop_table('payment_methods')

    op.drop_index(op.f('ix_subscriptions_user_id'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_stripe_subscription_id'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_id'), table_name='subscriptions')
    op.drop_table('subscriptions')