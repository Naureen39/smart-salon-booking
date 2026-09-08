"""add daily_booking_stats rollup table for the admin dashboard (docs plan §12)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-08

"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE daily_booking_stats (
            date DATE PRIMARY KEY,
            total_bookings INT NOT NULL DEFAULT 0,
            completed_count INT NOT NULL DEFAULT 0,
            cancelled_count INT NOT NULL DEFAULT 0,
            no_show_count INT NOT NULL DEFAULT 0,
            revenue_cents BIGINT NOT NULL DEFAULT 0,
            web_count INT NOT NULL DEFAULT 0,
            chat_count INT NOT NULL DEFAULT 0,
            voice_count INT NOT NULL DEFAULT 0,
            admin_count INT NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS daily_booking_stats;")
