import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_passage
from app.ai.llm_router import LLMRouter
from app.ai.orchestrator import process_turn
from app.ai.providers.base import LLMResponse
from app.core.security import create_access_token, hash_password
from app.db.models.appointment import Appointment
from app.db.models.conversation_session import ConversationSession
from app.db.models.faq_document import FaqDocument
from app.db.models.service import Service
from app.db.models.staff_profile import StaffProfile
from app.db.models.user import User


class _FakeProvider:
    def __init__(self, name: str, responses: list) -> None:
        self.name = name
        self.model = "fake"
        self._responses = list(responses)
        self.call_count = 0

    async def complete(self, system: str, user: str, *, max_tokens: int, json_mode: bool) -> LLMResponse:
        self.call_count += 1
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _confirmation_router() -> LLMRouter:
    groq = _FakeProvider("groq", [LLMResponse(text="You're all set — see you then!", tokens_in=50, tokens_out=10)])
    gemini = _FakeProvider("gemini", [])
    return LLMRouter(primary=groq, fallback=gemini)


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


async def test_full_booking_flow_creates_appointment_with_zero_extraction_llm_calls(
    db_session: AsyncSession,
    client_user: User,
    service: Service,
    staff: StaffProfile,
    target_date: date,
) -> None:
    session = ConversationSession(client_id=client_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    message = f"I'd like to book a {service.name} on {target_date.isoformat()} in the morning"
    router = _confirmation_router()

    first = await process_turn(db_session, session=session, message=message, client_id=client_user.id, router=router)

    assert first.llm_calls == 0
    assert first.quick_replies
    assert first.appointment_id is None

    second = await process_turn(db_session, session=session, message="1", client_id=client_user.id, router=router)

    assert second.llm_calls == 1  # confirmation message generation only
    assert second.appointment_id is not None

    appointment = await db_session.get(Appointment, uuid.UUID(second.appointment_id))
    assert appointment is not None
    assert appointment.status == "booked"
    assert appointment.client_id == client_user.id
    assert appointment.booking_channel == "chat"


async def test_ambiguous_input_triggers_exactly_one_llm_call(
    db_session: AsyncSession, client_user: User
) -> None:
    session = ConversationSession(client_id=client_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    groq = _FakeProvider(
        "groq",
        [
            LLMResponse(
                text='{"intent": "book_appointment", "slot_updates": {}, '
                '"reply_text": "Sure! What service and date would you like?"}',
                tokens_in=100,
                tokens_out=30,
            )
        ],
    )
    gemini = _FakeProvider("gemini", [])
    router = LLMRouter(primary=groq, fallback=gemini)

    result = await process_turn(
        db_session,
        session=session,
        message="hey can you help me out with something",
        client_id=client_user.id,
        router=router,
    )

    assert result.llm_calls == 1
    assert groq.call_count == 1
    assert result.state["intent"] == "book_appointment"


async def test_faq_question_answered_without_llm_when_confident(
    db_session: AsyncSession, client_user: User
) -> None:
    doc = FaqDocument(
        question="What are your hours?",
        answer="We're open Tuesday to Saturday, 9 to 6.",
        embedding=embed_passage("What are your hours?"),
    )
    db_session.add(doc)
    await db_session.commit()

    session = ConversationSession(client_id=client_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    groq = _FakeProvider("groq", [])
    gemini = _FakeProvider("gemini", [])
    router = LLMRouter(primary=groq, fallback=gemini)

    result = await process_turn(
        db_session, session=session, message="What are your hours?", client_id=client_user.id, router=router
    )

    assert result.llm_calls == 0
    assert result.reply_text == doc.answer
    # FAQ is a stateless aside — session resets so the next message starts fresh.
    assert result.state["intent"] is None


async def test_missing_slot_prompts_without_llm(
    db_session: AsyncSession, client_user: User, service: Service, staff: StaffProfile
) -> None:
    session = ConversationSession(client_id=client_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    result = await process_turn(
        db_session,
        session=session,
        message=f"I want to book a {service.name}",
        client_id=client_user.id,
        router=LLMRouter(primary=_FakeProvider("groq", []), fallback=_FakeProvider("gemini", [])),
    )

    assert result.llm_calls == 0
    assert "date" in result.reply_text.lower()


async def test_conversation_endpoints_end_to_end(
    client: AsyncClient, client_user: User, service: Service, staff: StaffProfile, target_date: date
) -> None:
    start_response = await client.post(
        "/api/v1/conversation/start", json={"channel": "chat"}, headers=_auth_header(client_user)
    )
    assert start_response.status_code == 201
    session_id = start_response.json()["id"]

    message_response = await client.post(
        f"/api/v1/conversation/{session_id}/message",
        json={"message": f"I want to book a {service.name}"},
        headers=_auth_header(client_user),
    )
    assert message_response.status_code == 200
    assert "date" in message_response.json()["reply_text"].lower()


async def test_message_to_other_users_session_is_rejected(
    client: AsyncClient, client_user: User, db_session: AsyncSession
) -> None:
    other_user = User(
        email="otherconvouser@example.com",
        hashed_password=hash_password("password123"),
        full_name="Other Convo User",
        role="client",
        is_active=True,
        is_verified=True,
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    session = ConversationSession(client_id=other_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    response = await client.post(
        f"/api/v1/conversation/{session.id}/message",
        json={"message": "hello"},
        headers=_auth_header(client_user),
    )
    assert response.status_code == 404
