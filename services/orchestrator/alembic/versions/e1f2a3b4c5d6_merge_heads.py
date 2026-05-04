"""merge_heads

Merge three divergent heads into a single linear history.

Revision ID: e1f2a3b4c5d6
Revises: add_data_buffer_to_reports, 299bcff565b9, d4e5f6a7b8c9
Create Date: 2026-05-01 00:00:00.000000

"""
from collections.abc import Sequence

revision: str = "e1f2a3b4c5d6"
down_revision: tuple[str, ...] = (
    "add_data_buffer_to_reports",
    "299bcff565b9",
    "d4e5f6a7b8c9",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
