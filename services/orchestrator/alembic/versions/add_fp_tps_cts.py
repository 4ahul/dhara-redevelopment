"""Add fp_no, tps_name, cts_validated to societies

Revision ID: add_fp_tps_cts
Revises: add_audit_logs
Create Date: 2026-04-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_fp_tps_cts"
down_revision: str | None = "58575a921803"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add new columns to societies table
    op.add_column("societies", sa.Column("fp_no", sa.String(100), nullable=True))
    op.add_column("societies", sa.Column("tps_name", sa.String(255), nullable=True))
    op.add_column("societies", sa.Column("cts_validated", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("societies", "cts_validated")
    op.drop_column("societies", "tps_name")
    op.drop_column("societies", "fp_no")
