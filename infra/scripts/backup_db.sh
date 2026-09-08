#!/usr/bin/env bash
# Nightly pg_dump backup (docs plan §8 checklist item: "Backups: nightly
# pg_dump ... or provider-managed backups on Supabase free tier").
#
# If deploying to Supabase, its own managed backups (free tier includes daily
# backups with a short retention window) may make this redundant — this
# script is for self-hosted Postgres deployments (Render/Fly.io/a VPS) where
# no managed backup exists.
#
# Usage (e.g. as a daily cron job):
#   DATABASE_URL=postgresql://user:pass@host:5432/glowdesk ./backup_db.sh /var/backups/glowdesk
#
# Requires the DATABASE_URL used here to be a plain postgresql:// URL (pg_dump
# doesn't understand the +asyncpg driver suffix the app's own DATABASE_URL uses).

set -euo pipefail

BACKUP_DIR="${1:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is required (a plain postgresql:// URL, not +asyncpg)" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
OUT_FILE="$BACKUP_DIR/glowdesk-$TIMESTAMP.sql.gz"

pg_dump "$DATABASE_URL" | gzip > "$OUT_FILE"
echo "Wrote $OUT_FILE"

# Prune backups older than RETENTION_DAYS.
find "$BACKUP_DIR" -name 'glowdesk-*.sql.gz' -mtime "+$RETENTION_DAYS" -delete
