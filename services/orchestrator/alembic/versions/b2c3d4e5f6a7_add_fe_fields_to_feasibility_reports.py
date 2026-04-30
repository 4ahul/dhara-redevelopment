"""add_fe_fields_to_feasibility_reports

Add summary columns (feasibility, fsi, estimated_value, etc.) to feasibility_reports.
Add new values to report_status enum (draft, in_progress, final).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-29 13:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add summary columns to feasibility_reports
    op.add_column('feasibility_reports', sa.Column('feasibility', sa.String(20), nullable=True, server_default='pending'))
    op.add_column('feasibility_reports', sa.Column('fsi', sa.Float(), nullable=True))
    op.add_column('feasibility_reports', sa.Column('estimated_value', sa.String(50), nullable=True))
    op.add_column('feasibility_reports', sa.Column('plot_area', sa.Float(), nullable=True))
    op.add_column('feasibility_reports', sa.Column('existing_units', sa.Integer(), nullable=True))
    op.add_column('feasibility_reports', sa.Column('proposed_units', sa.Integer(), nullable=True))
    op.add_column('feasibility_reports', sa.Column('structural_grade', sa.String(10), nullable=True))
    op.add_column('feasibility_reports', sa.Column('completion_days', sa.Integer(), nullable=True))

    # 2. Add new enum values to report_status
    # PostgreSQL enums require ALTER TYPE ... ADD VALUE
    op.execute("ALTER TYPE report_status ADD VALUE IF NOT EXISTS 'draft'")
    op.execute("ALTER TYPE report_status ADD VALUE IF NOT EXISTS 'in_progress'")
    op.execute("ALTER TYPE report_status ADD VALUE IF NOT EXISTS 'final'")


def downgrade() -> None:
    # Drop summary columns
    op.drop_column('feasibility_reports', 'completion_days')
    op.drop_column('feasibility_reports', 'structural_grade')
    op.drop_column('feasibility_reports', 'proposed_units')
    op.drop_column('feasibility_reports', 'existing_units')
    op.drop_column('feasibility_reports', 'plot_area')
    op.drop_column('feasibility_reports', 'estimated_value')
    op.drop_column('feasibility_reports', 'fsi')
    op.drop_column('feasibility_reports', 'feasibility')
    # Note: PostgreSQL doesn't support removing enum values easily.
    # The added enum values (draft, in_progress, final) will remain.
