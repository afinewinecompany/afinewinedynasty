"""Add prospects table

Revision ID: 002
Revises: 001
Create Date: 2025-09-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create prospects table
    op.create_table('prospects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mlb_id', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('position', sa.String(length=10), nullable=False),
        sa.Column('organization', sa.String(length=50), nullable=True),
        sa.Column('level', sa.String(length=20), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('eta_year', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "position IN ('C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'SP', 'RP')",
            name='valid_position'
        ),
        sa.CheckConstraint("age > 0 AND age < 50", name='valid_age'),
        sa.CheckConstraint("eta_year >= 2024 AND eta_year <= 2035", name='valid_eta_year'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mlb_id')
    )
    op.create_index(op.f('ix_prospects_id'), 'prospects', ['id'], unique=False)
    op.create_index(op.f('ix_prospects_mlb_id'), 'prospects', ['mlb_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_prospects_mlb_id'), table_name='prospects')
    op.drop_index(op.f('ix_prospects_id'), table_name='prospects')
    op.drop_table('prospects')