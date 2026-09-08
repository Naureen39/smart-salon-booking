import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConversationSession(Base):
    """Chat/voice session state. Keeps a slot-filling snapshot, not full transcripts,
    to minimize LLM token usage (see plan doc §9.1)."""

    __tablename__ = "conversation_sessions"
    __table_args__ = (CheckConstraint("channel IN ('chat','voice')", name="ck_conversation_sessions_channel"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    channel: Mapped[str | None] = mapped_column(String)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    """Slot-filling state machine snapshot."""
    summary: Mapped[str | None] = mapped_column(String)
    """Rolling LLM-free summary, not full transcript."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
