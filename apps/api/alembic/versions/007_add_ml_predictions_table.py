"""Add ML predictions table for future features

Revision ID: 007
Revises: 006
Create Date: 2025-09-25 13:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ml_predictions table
    op.create_table('ml_predictions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prospect_id', sa.Integer(), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('prediction_type', sa.String(length=50), nullable=False),
        sa.Column('prediction_value', sa.Float(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("confidence_score >= 0.0 AND confidence_score <= 1.0", name='valid_confidence_score'),
        sa.CheckConstraint(
            "prediction_type IN ('career_war', 'debut_probability', 'success_rating')",
            name='valid_prediction_type'
        ),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ml_predictions_id'), 'ml_predictions', ['id'], unique=False)
    op.create_index(op.f('ix_ml_predictions_prospect_id'), 'ml_predictions', ['prospect_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ml_predictions_prospect_id'), table_name='ml_predictions')
    op.drop_index(op.f('ix_ml_predictions_id'), table_name='ml_predictions')
    op.drop_table('ml_predictions')