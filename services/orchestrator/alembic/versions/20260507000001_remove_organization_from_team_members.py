"""Remove organization from team_members

Revision ID: 20260507000001
Revises: 20260506162239
Create Date: 2026-05-07 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260507000001"
down_revision: Union[str, None] = "20260506162239"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = ["fd819f308a81"]


def upgrade() -> None:
    op.drop_column("team_members", "organization")


def downgrade() -> None:
    op.add_column(
        "team_members", sa.Column("organization", sa.String(255), nullable=False)
    )