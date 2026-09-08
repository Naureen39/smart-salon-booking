"""add exclusion constraint preventing overlapping bookings per staff member

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    op.execute("""
        ALTER TABLE appointments
        ADD CONSTRAINT appointments_no_overlap
        EXCLUDE USING gist (
            staff_id WITH =,
            tstzrange(scheduled_start, scheduled_end) WITH &&
        )
        WHERE (status IN ('booked', 'confirmed'));
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_no_overlap;")
