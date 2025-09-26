"""Add scouting_grades table

Revision ID: 004
Revises: 003
Create Date: 2025-09-25 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create scouting_grades table
    op.create_table('scouting_grades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prospect_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('overall', sa.Integer(), nullable=True),
        sa.Column('hit', sa.Integer(), nullable=True),
        sa.Column('power', sa.Integer(), nullable=True),
        sa.Column('run', sa.Integer(), nullable=True),
        sa.Column('field', sa.Integer(), nullable=True),
        sa.Column('throw', sa.Integer(), nullable=True),
        sa.Column('fastball', sa.Integer(), nullable=True),
        sa.Column('curveball', sa.Integer(), nullable=True),
        sa.Column('slider', sa.Integer(), nullable=True),
        sa.Column('changeup', sa.Integer(), nullable=True),
        sa.Column('control', sa.Integer(), nullable=True),
        sa.Column('future_value', sa.Integer(), nullable=True),
        sa.Column('risk', sa.String(length=20), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "source IN ('Fangraphs', 'MLB Pipeline', 'Baseball America', 'Baseball Prospectus')",
            name='valid_source'
        ),
        sa.CheckConstraint("overall >= 20 AND overall <= 80", name='valid_overall'),
        sa.CheckConstraint("hit >= 20 AND hit <= 80", name='valid_hit'),
        sa.CheckConstraint("power >= 20 AND power <= 80", name='valid_power'),
        sa.CheckConstraint("run >= 20 AND run <= 80", name='valid_run'),
        sa.CheckConstraint("field >= 20 AND field <= 80", name='valid_field'),
        sa.CheckConstraint("throw >= 20 AND throw <= 80", name='valid_throw'),
        sa.CheckConstraint("future_value >= 20 AND future_value <= 80", name='valid_future_value'),
        sa.CheckConstraint(
            "risk IN ('Safe', 'Moderate', 'High', 'Extreme')",
            name='valid_risk'
        ),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scouting_grades_id'), 'scouting_grades', ['id'], unique=False)
    op.create_index(op.f('ix_scouting_grades_source'), 'scouting_grades', ['source'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_scouting_grades_source'), table_name='scouting_grades')
    op.drop_index(op.f('ix_scouting_grades_id'), table_name='scouting_grades')
    op.drop_table('scouting_grades')