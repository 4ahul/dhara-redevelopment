"""Add data_buffer to feasibility_reports

Revision ID: add_data_buffer_to_reports
Revises: add_fp_tps_cts
Create Date: 2024-05-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_data_buffer_to_reports'
down_revision = 'add_fp_tps_cts'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('feasibility_reports', sa.Column('data_buffer', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('feasibility_reports', 'data_buffer')
