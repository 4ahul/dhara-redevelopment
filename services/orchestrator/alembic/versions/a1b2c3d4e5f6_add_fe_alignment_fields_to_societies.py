"""add_fe_alignment_fields_to_societies

Add registration_number, year_built, is_manual_process columns.
Convert status from varchar to society_status enum.

Revision ID: a1b2c3d4e5f6
Revises: 916c6509c5bd
Create Date: 2026-04-29 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '299bcff565b9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All valid society statuses for the new enum
SOCIETY_STATUSES = (
    'new', 'invitation_sent', 'report_pending', 'tender_pending',
    'tender_published', 'tender_review_pending', 'builder_finalized',
    'manual_process',
)


def upgrade() -> None:
    # 1. Add new columns
    op.add_column('societies', sa.Column('registration_number', sa.String(100), nullable=True))
    op.add_column('societies', sa.Column('year_built', sa.Integer(), nullable=True))
    op.add_column('societies', sa.Column('is_manual_process', sa.Boolean(), server_default='false', nullable=False))

    # 2. Create the enum type
    society_status_enum = sa.Enum(*SOCIETY_STATUSES, name='society_status')
    society_status_enum.create(op.get_bind(), checkfirst=True)

    # 3. Map any existing 'active' values to 'new' before altering column type
    op.execute("UPDATE societies SET status = 'new' WHERE status = 'active'")
    # Map any other unexpected values to 'new' as a safety net
    valid_csv = ', '.join(f"'{s}'" for s in SOCIETY_STATUSES)
    op.execute(f"UPDATE societies SET status = 'new' WHERE status NOT IN ({valid_csv})")

    # 4. Alter column type from varchar to the new enum
    op.execute(
        "ALTER TABLE societies "
        "ALTER COLUMN status TYPE society_status USING status::society_status"
    )
    op.execute("ALTER TABLE societies ALTER COLUMN status SET DEFAULT 'new'")


def downgrade() -> None:
    # Revert status column back to varchar
    op.execute(
        "ALTER TABLE societies "
        "ALTER COLUMN status TYPE VARCHAR(50) USING status::text"
    )
    op.execute("ALTER TABLE societies ALTER COLUMN status SET DEFAULT 'active'")

    # Drop new columns
    op.drop_column('societies', 'is_manual_process')
    op.drop_column('societies', 'year_built')
    op.drop_column('societies', 'registration_number')

    # Drop the enum type
    sa.Enum(name='society_status').drop(op.get_bind(), checkfirst=True)
