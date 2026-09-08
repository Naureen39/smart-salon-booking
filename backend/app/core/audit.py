import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog


async def record_audit_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: uuid.UUID | None,
    metadata: dict | None = None,
) -> None:
    """Adds an audit_log row to the current session — the caller commits alongside
    whatever mutation this event describes, so the two are never out of sync."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            audit_metadata=metadata,
        )
    )
