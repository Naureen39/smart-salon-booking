"""add llm_usage table for LLM router observability (docs plan §9.4)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-08

"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE llm_usage (
            id BIGSERIAL PRIMARY KEY,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            purpose TEXT NOT NULL,
            tokens_in INT NOT NULL DEFAULT 0,
            tokens_out INT NOT NULL DEFAULT 0,
            latency_ms INT NOT NULL DEFAULT 0,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            error TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS llm_usage;")
