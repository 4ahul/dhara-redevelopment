"""add_registration_number_to_societies

Revision ID: a1b2c3d4e5f6
Revises: 916c6509c5bd
Create Date: 2026-04-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "916c6509c5bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("societies", sa.Column("registration_number", sa.String(255), nullable=True))
    # Widen status column to hold longer values like "Tender Review Pending"
    op.alter_column("societies", "status", type_=sa.String(100))


def downgrade() -> None:
    op.drop_column("societies", "registration_number")
    op.alter_column("societies", "status", type_=sa.String(50))
