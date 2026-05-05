"""remove_num_flats_and_registration_number_from_society

Revision ID: 1225b36ec86b
Revises: fd819f308a81
Create Date: 2026-05-04 15:49:33.639441

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1225b36ec86b'
down_revision: Union[str, None] = 'fd819f308a81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('societies', 'num_flats')
    op.drop_column('societies', 'registration_number')


def downgrade() -> None:
    op.add_column('societies', sa.Column('num_flats', sa.Integer(), nullable=True))
    op.add_column('societies', sa.Column('registration_number', sa.String(length=255), nullable=True))
