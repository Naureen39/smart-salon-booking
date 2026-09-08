import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import process_turn
from app.api.deps import get_current_user
from app.db.models.conversation_session import ConversationSession
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.conversation import (
    ConversationSessionRead,
    ConversationTurnResponse,
    SendMessageRequest,
    StartSessionRequest,
)

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.post("/start", response_model=ConversationSessionRead, status_code=status.HTTP_201_CREATED)
async def start_session(
    payload: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationSession:
    session = ConversationSession(client_id=current_user.id, channel=payload.channel, state={})
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.post("/{session_id}/message", response_model=ConversationTurnResponse)
async def send_message(
    session_id: uuid.UUID,
    payload: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationTurnResponse:
    session = await db.get(ConversationSession, session_id)
    if session is None or session.client_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation session not found")

    result = await process_turn(db, session=session, message=payload.message, client_id=current_user.id)
    return ConversationTurnResponse(
        reply_text=result.reply_text,
        quick_replies=result.quick_replies,
        appointment_id=result.appointment_id,
        state=result.state,
    )
