"""Add portfolio_documents table

Revision ID: 20260506162239
Revises: fd819f308a81
Create Date: 2026-05-06 16:22:39.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

# revision identifiers, used by Alembic.
revision: str = "20260506162239"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = ["fd819f308a81"]


def upgrade() -> None:
    op.create_table(
        "portfolio_documents",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("public_id", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("format", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_portfolio_documents_user_id", "portfolio_documents", ["user_id"])


def downgrade() -> None:
    op.drop_table("portfolio_documents")
