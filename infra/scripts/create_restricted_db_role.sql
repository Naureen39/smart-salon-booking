-- Least-privilege application DB role (docs plan §8 checklist item:
-- "the app's DB user should not be a Postgres superuser").
--
-- The local docker-compose stack's POSTGRES_USER ("glowdesk") owns its
-- database and is convenient for local dev, but a production deployment
-- should run the app against a role scoped to exactly what it needs:
-- CRUD on application tables, nothing at the cluster/role-management level.
--
-- Usage (run once against the production database, as an admin/superuser):
--   psql "$ADMIN_DATABASE_URL" -f create_restricted_db_role.sql
-- Then point the app's DATABASE_URL at glowdesk_app instead of the owner role.

CREATE ROLE glowdesk_app WITH LOGIN PASSWORD 'CHANGE_ME';

GRANT CONNECT ON DATABASE glowdesk TO glowdesk_app;
GRANT USAGE ON SCHEMA public TO glowdesk_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO glowdesk_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO glowdesk_app;

-- Keeps the grants applying to tables/sequences created by future migrations
-- (run as the same role/owner that runs `alembic upgrade`).
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO glowdesk_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO glowdesk_app;

-- Explicitly NOT granted: CREATEDB, CREATEROLE, SUPERUSER, or DDL rights.
-- Run `alembic upgrade head` as the schema-owning role, not glowdesk_app.
