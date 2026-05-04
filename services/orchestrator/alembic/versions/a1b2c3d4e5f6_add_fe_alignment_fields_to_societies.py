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
down_revision: str | None = '916c6509c5bd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All valid society statuses — UPPERCASE to match Python SocietyStatus enum and existing DB enum
SOCIETY_STATUSES = (
    'NEW', 'ACTIVE', 'ONBOARDED', 'INVITATION_SENT', 'REPORT_PENDING',
    'TENDER_PENDING', 'TENDER_PUBLISHED', 'TENDER_REVIEW_PENDING',
    'BUILDER_FINALIZED', 'MANUAL_PROCESS',
)


def upgrade() -> None:
    # 1. Add new columns (IF NOT EXISTS for idempotency)
    op.execute("ALTER TABLE societies ADD COLUMN IF NOT EXISTS registration_number VARCHAR(100)")
    op.execute("ALTER TABLE societies ADD COLUMN IF NOT EXISTS year_built INTEGER")
    op.execute("ALTER TABLE societies ADD COLUMN IF NOT EXISTS is_manual_process BOOLEAN NOT NULL DEFAULT false")

    # 2. Create enum if it doesn't exist; if it does, add any missing values
    society_status_enum = sa.Enum(*SOCIETY_STATUSES, name='society_status')
    society_status_enum.create(op.get_bind(), checkfirst=True)
    for val in SOCIETY_STATUSES:
        op.execute(f"ALTER TYPE society_status ADD VALUE IF NOT EXISTS '{val}'")

    # 3. Normalize existing varchar data to UPPERCASE before casting
    op.execute("UPDATE societies SET status = UPPER(status)")
    # Fall back unmapped rows to 'NEW'
    valid_csv = ', '.join(f"'{s}'" for s in SOCIETY_STATUSES)
    op.execute(f"UPDATE societies SET status = 'NEW' WHERE status NOT IN ({valid_csv})")

    # 4. Alter column type from varchar to enum
    op.execute(
        "ALTER TABLE societies "
        "ALTER COLUMN status TYPE society_status USING status::society_status"
    )
    op.execute("ALTER TABLE societies ALTER COLUMN status SET DEFAULT 'NEW'")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE societies "
        "ALTER COLUMN status TYPE VARCHAR(50) USING status::text"
    )
    op.execute("ALTER TABLE societies ALTER COLUMN status SET DEFAULT 'NEW'")
    op.drop_column('societies', 'is_manual_process')
    op.drop_column('societies', 'year_built')
    op.drop_column('societies', 'registration_number')
    sa.Enum(name='society_status').drop(op.get_bind(), checkfirst=True)
