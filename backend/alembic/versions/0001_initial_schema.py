"""initial schema — users, locations, staff_profiles, services, appointments,
conversation_sessions, faq_documents (pgvector), audit_log

Mirrors the schema defined in docs plan §6 verbatim so the two stay in sync.

Revision ID: 0001
Revises:
Create Date: 2026-09-08

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            hashed_password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('client','staff','admin')) DEFAULT 'client',
            is_active BOOLEAN DEFAULT TRUE,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE locations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            address TEXT,
            timezone TEXT NOT NULL DEFAULT 'UTC'
        );
    """)

    op.execute("""
        CREATE TABLE staff_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id),
            location_id UUID REFERENCES locations(id),
            title TEXT,
            bio TEXT,
            working_hours JSONB
        );
    """)

    op.execute("""
        CREATE TABLE services (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            duration_minutes INT NOT NULL,
            price_cents INT NOT NULL,
            image_url TEXT,
            is_active BOOLEAN DEFAULT TRUE
        );
    """)

    op.execute("""
        CREATE TABLE appointments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id UUID REFERENCES users(id),
            staff_id UUID REFERENCES staff_profiles(id),
            service_id UUID REFERENCES services(id),
            location_id UUID REFERENCES locations(id),
            scheduled_start TIMESTAMPTZ NOT NULL,
            scheduled_end TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL CHECK (status IN
                ('booked','confirmed','completed','cancelled','no_show')) DEFAULT 'booked',
            booking_channel TEXT CHECK (booking_channel IN ('web','chat','voice','admin')),
            is_first_visit BOOLEAN DEFAULT FALSE,
            lead_time_hours NUMERIC,
            no_show_risk_score NUMERIC,
            reminder_sent_at TIMESTAMPTZ[],
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE conversation_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id UUID REFERENCES users(id),
            channel TEXT CHECK (channel IN ('chat','voice')),
            state JSONB NOT NULL DEFAULT '{}',
            summary TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE faq_documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            embedding VECTOR(384),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX faq_embedding_idx ON faq_documents USING hnsw (embedding vector_cosine_ops);")

    op.execute("""
        CREATE TABLE audit_log (
            id BIGSERIAL PRIMARY KEY,
            user_id UUID,
            action TEXT NOT NULL,
            entity TEXT,
            entity_id UUID,
            ip_address INET,
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_log;")
    op.execute("DROP TABLE IF EXISTS faq_documents;")
    op.execute("DROP TABLE IF EXISTS conversation_sessions;")
    op.execute("DROP TABLE IF EXISTS appointments;")
    op.execute("DROP TABLE IF EXISTS services;")
    op.execute("DROP TABLE IF EXISTS staff_profiles;")
    op.execute("DROP TABLE IF EXISTS locations;")
    op.execute("DROP TABLE IF EXISTS users;")
