import uuid
from datetime import date, timedelta

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
from app.db.models.location import Location
from app.db.models.service import Service
from app.db.models.staff_profile import StaffProfile
from app.db.models.user import User


class _FakeProvider:
    def __init__(self, name: str, responses: list) -> None:
        self.name = name
        self.model = "fake"
        self._responses = list(responses)
        self.call_count = 0
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str, *, max_tokens: int, json_mode: bool) -> LLMResponse:
        self.call_count += 1
        self.calls.append((system, user))
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _confirmation_router() -> LLMRouter:
    groq = _FakeProvider("groq", [LLMResponse(text="You're all set, see you then!", tokens_in=50, tokens_out=10)])
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


async def test_specific_time_request_prioritizes_closest_slots_over_earliest(
    db_session: AsyncSession,
    client_user: User,
    service: Service,
    staff: StaffProfile,
    target_date: date,
) -> None:
    """A request naming an exact clock time (e.g. "4pm") should surface slots
    near that time first, not just the day's earliest openings, regression
    test for a gap found in manual end-to-end testing: extract_time_window
    only recognizes "morning"/"afternoon"/"evening", so a literal time like
    "4pm" was previously silently ignored and every request got 9 AM options.
    """
    session = ConversationSession(client_id=client_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    message = f"I'd like to book a {service.name} on {target_date.isoformat()} at 4pm"
    router = _confirmation_router()

    result = await process_turn(db_session, session=session, message=message, client_id=client_user.id, router=router)

    assert result.llm_calls == 0
    presented_starts = [slot["start"] for slot in result.state["presented_slots"]]
    assert any("T16:" in start or "T15:" in start for start in presented_starts), presented_starts
    assert not all("T09:" in start for start in presented_starts)


async def test_multi_location_booking_names_location_and_persists_it(
    db_session: AsyncSession,
    client_user: User,
    service: Service,
    staff: StaffProfile,
    target_date: date,
) -> None:
    """Regression test for a disclosed gap now fixed: the conversational flow
    used to ignore location entirely, it never told the client which
    location a slot was at, and every chat-booked appointment was persisted
    with location_id=None regardless of the staff member's actual location.
    With a second location/staff sharing the same early availability, the
    reply should name locations to disambiguate, and the booked appointment
    should carry the chosen staff member's real location_id.
    """
    second_location = Location(name="Second Branch", timezone="UTC")
    db_session.add(second_location)
    await db_session.commit()
    await db_session.refresh(second_location)

    weekday_keys = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    second_staff = StaffProfile(
        location_id=second_location.id,
        title="Second Stylist",
        working_hours={weekday_keys[target_date.weekday()]: ["09:00-17:00"]},
    )
    db_session.add(second_staff)
    await db_session.commit()
    await db_session.refresh(second_staff)

    session = ConversationSession(client_id=client_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    message = f"I'd like to book a {service.name} on {target_date.isoformat()} at 9am"
    router = _confirmation_router()

    first = await process_turn(db_session, session=session, message=message, client_id=client_user.id, router=router)

    assert first.llm_calls == 0
    presented = first.state["presented_slots"]
    location_ids_offered = {slot["location_id"] for slot in presented}
    assert len(location_ids_offered) > 1, presented
    assert "Second Branch" in first.reply_text or any("Second Branch" in reply for reply in first.quick_replies or [])

    second = await process_turn(db_session, session=session, message="1", client_id=client_user.id, router=router)
    assert second.appointment_id is not None
    appointment = await db_session.get(Appointment, uuid.UUID(second.appointment_id))
    assert appointment is not None
    assert appointment.location_id in (staff.location_id, second_location.id)


async def test_confirmation_message_uses_the_booked_slots_own_offset(
    db_session: AsyncSession,
    client_user: User,
    service: Service,
    target_date: date,
) -> None:
    """Regression test for a real bug found in manual end-to-end testing: the
    confirmation message was built from `appointment.scheduled_start` after
    SQLAlchemy refreshed it from Postgres, and a `timestamptz` column always
    reads back UTC-normalized regardless of the location's real timezone. A
    client who booked 12:00 PM Pacific was told their appointment was
    confirmed for "7 PM" (19:00, the UTC hour, formatted as if already
    local). The fix uses the originally-presented, still-correctly-offset
    slot instead.
    """
    ny_location = Location(name="NYC Branch", timezone="America/New_York")
    db_session.add(ny_location)
    await db_session.commit()
    await db_session.refresh(ny_location)

    weekday_keys = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    ny_staff = StaffProfile(
        location_id=ny_location.id,
        title="NYC Stylist",
        working_hours={weekday_keys[target_date.weekday()]: ["09:00-17:00"]},
    )
    db_session.add(ny_staff)
    await db_session.commit()
    await db_session.refresh(ny_staff)

    session = ConversationSession(client_id=client_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    router = _confirmation_router()
    message = f"I'd like to book a {service.name} on {target_date.isoformat()} at 12pm"
    await process_turn(db_session, session=session, message=message, client_id=client_user.id, router=router)
    await process_turn(db_session, session=session, message="1", client_id=client_user.id, router=router)

    fake_groq = router.primary
    confirmation_calls = [user for _, user in fake_groq.calls if "Date/time" in user]
    assert len(confirmation_calls) == 1
    # 12 PM America/New_York must stay "12:00 PM" in the prompt sent to the
    # LLM, never "05:00 PM"/"04:00 PM" (its UTC-shifted equivalent).
    assert "12:00 PM" in confirmation_calls[0]


async def test_confirmation_message_never_contains_an_em_dash(
    db_session: AsyncSession, client_user: User, service: Service, staff: StaffProfile, target_date: date
) -> None:
    """Regression test for a real bug found in manual end-to-end testing: the
    LLM generated a genuine confirmation message containing a real em dash
    ("...12:30 PM—looking forward to seeing you then!"), despite the system
    prompt asking it not to. A style instruction in a prompt is advice, not a
    guarantee, this project bans the character outright, so the orchestrator
    sanitizes every LLM-generated reply rather than trusting the model to
    comply on its own.
    """
    session = ConversationSession(client_id=client_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    router = LLMRouter(
        primary=_FakeProvider(
            "groq",
            [LLMResponse(text="You're all set—see you then!", tokens_in=50, tokens_out=10)],
        ),
        fallback=_FakeProvider("gemini", []),
    )
    message = f"I'd like to book a {service.name} on {target_date.isoformat()} in the morning"
    first = await process_turn(db_session, session=session, message=message, client_id=client_user.id, router=router)
    second = await process_turn(db_session, session=session, message="1", client_id=client_user.id, router=router)

    assert "—" not in first.reply_text
    assert "—" not in second.reply_text
    assert "You're all set, see you then!" == second.reply_text


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


async def test_unknown_intent_does_not_permanently_stick_the_session(
    db_session: AsyncSession, client_user: User, service: Service, staff: StaffProfile, target_date: date
) -> None:
    """Regression test for a real bug found in manual end-to-end testing: a
    bare greeting on turn one legitimately classifies as intent "unknown"
    (EXTRACTION_SYSTEM_PROMPT explicitly allows this) and that gets
    persisted to session.state. The bug: re-classification was gated on
    `intent is None`, treating a persisted "unknown" as a *final* answer, so
    a later, completely unambiguous "book a haircut" in the very same
    session hit the generic fallback forever instead of ever starting the
    booking flow.
    """
    session = ConversationSession(client_id=client_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    greeting_router = LLMRouter(
        primary=_FakeProvider(
            "groq",
            [
                LLMResponse(
                    text='{"intent": "unknown", "slot_updates": {}, '
                    '"reply_text": "Hello! How can I help you today?"}',
                    tokens_in=50,
                    tokens_out=15,
                )
            ],
        ),
        fallback=_FakeProvider("gemini", []),
    )
    first = await process_turn(
        db_session, session=session, message="hi", client_id=client_user.id, router=greeting_router
    )
    assert first.state["intent"] == "unknown"

    message = f"I need to book a {service.name} on {target_date.isoformat()}"
    second = await process_turn(
        db_session, session=session, message=message, client_id=client_user.id, router=_confirmation_router()
    )

    assert second.reply_text != "I'm not sure how to help with that yet. Could you tell me more?"
    assert second.state["intent"] == "book_appointment"


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
    # FAQ is a stateless aside, session resets so the next message starts fresh.
    assert result.state["intent"] is None


async def test_mid_booking_faq_aside_answers_from_the_real_faq_and_preserves_booking(
    db_session: AsyncSession, client_user: User, service: Service
) -> None:
    """Regression test for a real bug found in manual end-to-end testing: a
    message mid-booking that names no service/date/time ("actually, what are
    your hours?") falls to the extraction LLM for lack of anything rule-based
    to go on, and that call's own free-form reply_text was used verbatim as
    the answer. The extraction LLM has no grounding in the real FAQ
    knowledge base, and in a real conversation it confidently stated hours
    that didn't match the actual seeded answer, a hallucination handed
    straight to the user. Since EXTRACTION_SYSTEM_PROMPT lets this call
    classify intent as "faq" too, routing to the same RAG-grounded answering
    path the top-level "faq" intent uses (instead of trusting this call's own
    guess) fixes it, and booking progress must survive the aside so the flow
    can resume afterward.
    """
    doc = FaqDocument(
        question="What are your hours?",
        answer="We're open Tuesday to Saturday, 9 to 6.",
        embedding=embed_passage("What are your hours?"),
    )
    db_session.add(doc)

    session = ConversationSession(
        client_id=client_user.id,
        channel="chat",
        state={"intent": "book_appointment", "slots": {"service": service.name}, "turn_count": 1},
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    router = LLMRouter(
        primary=_FakeProvider(
            "groq",
            [
                LLMResponse(
                    text='{"intent": "faq", "slot_updates": {}, '
                    '"reply_text": "We are open every day 24 hours!"}',
                    tokens_in=50,
                    tokens_out=15,
                )
            ],
        ),
        fallback=_FakeProvider("gemini", []),
    )

    result = await process_turn(
        db_session, session=session, message="actually, what are your hours?", client_id=client_user.id, router=router
    )

    assert result.reply_text == doc.answer
    assert result.state["intent"] == "book_appointment"
    assert result.state["slots"] == {"service": service.name}


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


async def test_no_availability_clears_date_so_a_new_date_can_be_given(
    db_session: AsyncSession,
    client_user: User,
    service: Service,
    staff: StaffProfile,
    target_date: date,
) -> None:
    """Regression test for a real bug found in manual end-to-end testing: the
    `staff` fixture only has working hours on `target_date`'s weekday, so
    asking for the very next day has zero availability. The old code left the
    unavailable date sitting in `slots` after replying "would another day
    work?", so a reply that didn't itself parse as a date (a plain "yes")
    fell through to the exact same availability lookup for the exact same
    day, repeating the identical "nothing available" message forever instead
    of ever accepting a new date.
    """
    session = ConversationSession(client_id=client_user.id, channel="chat", state={})
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    unavailable_date = target_date + timedelta(days=1)

    # "yes" alone names no service/date/time-window, so it isn't resolvable by
    # the rule-based extractors and needs the one genuine LLM fallback call
    # (matching the pattern in test_ambiguous_input_triggers_exactly_one_llm_call).
    router = LLMRouter(
        primary=_FakeProvider(
            "groq",
            [
                LLMResponse(
                    text='{"intent": "book_appointment", "slot_updates": {}, '
                    '"reply_text": "Sure, what date would work instead?"}',
                    tokens_in=50,
                    tokens_out=15,
                )
            ],
        ),
        fallback=_FakeProvider("gemini", []),
    )

    first = await process_turn(
        db_session,
        session=session,
        message=f"I'd like to book a {service.name} on {unavailable_date.isoformat()}",
        client_id=client_user.id,
        router=router,
    )
    assert "nothing available" in first.reply_text.lower()
    assert "date" not in first.state["slots"]

    second = await process_turn(db_session, session=session, message="yes", client_id=client_user.id, router=router)
    assert "nothing available" not in second.reply_text.lower()
    assert "date" in second.reply_text.lower()

    third = await process_turn(
        db_session,
        session=session,
        message=target_date.isoformat(),
        client_id=client_user.id,
        router=_confirmation_router(),
    )
    assert third.quick_replies


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
