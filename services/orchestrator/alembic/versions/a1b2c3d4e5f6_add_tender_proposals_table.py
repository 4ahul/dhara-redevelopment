"""add_tender_proposals_table

Revision ID: a1b2c3d4e5f6
Revises: 1225b36ec86b
Create Date: 2026-05-04 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '1225b36ec86b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tender_proposals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tender_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bidder_name', sa.String(length=255), nullable=False),
        sa.Column('bidder_email', sa.String(length=255), nullable=False),
        sa.Column('bidder_company', sa.String(length=255), nullable=True),
        sa.Column('bidder_phone', sa.String(length=50), nullable=True),
        sa.Column('proposal_amount', sa.Float(), nullable=True),
        sa.Column('proposal_details', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='submitted'),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tender_id'], ['society_tenders.id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    op.drop_table('tender_proposals')