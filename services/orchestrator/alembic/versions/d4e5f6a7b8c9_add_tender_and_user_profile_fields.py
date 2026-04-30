"""add_tender_and_user_profile_fields

Add estimated_value to society_tenders.
Add PMC company profile fields to users table.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-29 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: str | None = 'c3d4e5f6a7b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # society_tenders: add estimated_value
    op.add_column('society_tenders', sa.Column('estimated_value', sa.String(50), nullable=True))

    # users: add PMC company profile fields
    op.add_column('users', sa.Column('registration_number', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('website', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('experience', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('projects_completed', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('specialization', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('portfolio_description', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('country', sa.String(100), nullable=True))


def downgrade() -> None:
    # users
    op.drop_column('users', 'country')
    op.drop_column('users', 'portfolio_description')
    op.drop_column('users', 'specialization')
    op.drop_column('users', 'projects_completed')
    op.drop_column('users', 'experience')
    op.drop_column('users', 'address')
    op.drop_column('users', 'website')
    op.drop_column('users', 'registration_number')

    # society_tenders
    op.drop_column('society_tenders', 'estimated_value')
