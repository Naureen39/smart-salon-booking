"""Conversation orchestrator (docs plan §9.1) — a slot-filling state machine
where the LLM is invoked only at genuine "edges": free-form input the
rule-based extractors can't resolve, generating a short booking-confirmation
message, and grounding an FAQ answer RAG couldn't confidently match. Intent
keywords, date/service parsing, availability lookup, and slot presentation
are all deterministic code — zero LLM tokens for the common case.

Known scope limits (disclosed, not accidental): once `intent` is set to
`book_appointment`, the machine assumes every subsequent message continues
that flow rather than detecting a mid-flow topic switch (e.g. an FAQ aside
during booking) — handling that robustly would need real context-stacking,
which is beyond this MVP. Only `book_appointment` and `faq` intents exist;
reschedule/cancel-by-chat aren't wired in here (those already have their own
REST endpoints from Phase 2).
"""

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.extractors import TIME_WINDOWS, extract_date, extract_specific_time, extract_time_window, match_service
from app.ai.llm_router import LLMRouter, get_default_router
from app.ai.rag import FaqMatch, answer_faq
from app.booking.availability import AvailableSlot, compute_available_slots
from app.booking.create import BookingConflictError, create_booking
from app.db.models.conversation_session import ConversationSession
from app.db.models.location import Location
from app.db.models.service import Service

REQUIRED_SLOTS = ("service", "date")

BOOKING_KEYWORDS = ("book", "appointment", "schedule", "reschedule")
FAQ_KEYWORDS = (
    "hour", "open", "close", "park", "cancel", "policy", "payment", "pay", "gift card", "walk-in", "walk in",
)

_ORDINAL_WORDS = {
    "first": 0, "1st": 0, "one": 0, "1": 0,
    "second": 1, "2nd": 1, "two": 1, "2": 1,
    "third": 2, "3rd": 2, "three": 2, "3": 2,
}

EXTRACTION_SYSTEM_PROMPT = (
    "You are a salon booking assistant's intent/slot extractor. Given the user's message and any "
    "already-known slots, respond with ONLY a JSON object of this exact shape: "
    '{"intent": "book_appointment" | "faq" | "unknown", '
    '"slot_updates": {"service": string|null, "date": "YYYY-MM-DD"|null, '
    '"time_window": "morning"|"afternoon"|"evening"|null}, "reply_text": string}. '
    "reply_text should be short and friendly — a clarifying question if information is missing."
)

CONFIRMATION_SYSTEM_PROMPT = (
    "You are a friendly salon booking assistant. Write one or two brief, warm sentences confirming a "
    "just-booked appointment. No placeholders, no brackets."
)
# "one or two brief sentences", not a numeric word count: a numeric
# constraint like "under 40 words" was observed, in manual end-to-end
# testing, to push the reasoning model into literally counting words in its
# hidden reasoning trace, sometimes consuming the entire token budget before
# any visible content and returning it blank. See GroqProvider's
# reasoning_effort setting for the other half of this fix.

FAQ_GROUNDING_SYSTEM_PROMPT = (
    "You are a salon's FAQ assistant. Answer the user's question using ONLY the context below, in one "
    "or two brief sentences. If the context doesn't contain the answer, say you'll check with staff "
    "and follow up."
)


@dataclass
class TurnResult:
    reply_text: str
    llm_calls: int
    state: dict
    appointment_id: str | None = None
    quick_replies: list[str] | None = None


def classify_intent_by_keywords(text: str) -> str | None:
    lowered = text.lower()
    if any(keyword in lowered for keyword in BOOKING_KEYWORDS):
        return "book_appointment"
    if any(keyword in lowered for keyword in FAQ_KEYWORDS) or lowered.strip().endswith("?"):
        return "faq"
    return None


def _match_presented_slot(message: str, presented_slots: list[dict]) -> dict | None:
    lowered = message.lower().strip()
    for word, index in _ORDINAL_WORDS.items():
        if word == lowered or f" {word} " in f" {lowered} ":
            if index < len(presented_slots):
                return presented_slots[index]

    for slot in presented_slots:
        # Falls back to a bare-time label for slots persisted before "label"
        # existed (an in-flight conversation whose state was written by an
        # older deployment) rather than raising a KeyError.
        label = slot.get("label") or datetime.fromisoformat(slot["start"]).strftime("%I:%M %p")
        if label.lower().lstrip("0") in lowered:
            return slot
    return None


def _filter_by_time_window(slots: list[AvailableSlot], window: str | None) -> list[AvailableSlot]:
    bounds = TIME_WINDOWS.get(window or "")
    if bounds is None:
        return slots
    start_hour, end_hour = bounds
    return [slot for slot in slots if start_hour <= slot.start.hour < end_hour]


def _closest_to_requested_time(slots: list[AvailableSlot], requested: time | None) -> list[AvailableSlot]:
    """Sorts by proximity to an explicit requested clock time (e.g. "3pm"), so
    a specific request surfaces the nearest real openings first instead of
    always the day's earliest slots — `slots` is already in chronological
    order when no specific time was requested, so that ordering is preserved.
    """
    if requested is None:
        return slots
    requested_minutes = requested.hour * 60 + requested.minute
    return sorted(slots, key=lambda slot: abs((slot.start.hour * 60 + slot.start.minute) - requested_minutes))


def _templated_missing_slot_prompt(missing: list[str]) -> str:
    if "service" in missing and "date" in missing:
        return "What service would you like to book, and on what date?"
    if "service" in missing:
        return "What service would you like to book?"
    if "date" in missing:
        return "What date works for you?"
    return "Could you give me a bit more detail?"


async def _get_active_service_names(db: AsyncSession) -> list[str]:
    result = await db.scalars(select(Service.name).where(Service.is_active.is_(True)))
    return list(result)


async def _location_names_by_id(db: AsyncSession, location_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not location_ids:
        return {}
    locations = await db.scalars(select(Location).where(Location.id.in_(location_ids)))
    return {location.id: location.name for location in locations}


async def _find_service_by_name(db: AsyncSession, name: str) -> Service | None:
    result = await db.scalars(select(Service).where(Service.name == name, Service.is_active.is_(True)))
    return result.first()


async def _llm_classify_and_extract(
    router: LLMRouter, db: AsyncSession, message: str, *, existing_slots: dict | None = None
) -> tuple[str, dict, str]:
    user_message = f"Known slots: {json.dumps(existing_slots or {})}\nUser message: {message}"
    raw = await router.complete(
        db,
        system=EXTRACTION_SYSTEM_PROMPT,
        user=user_message,
        purpose="intent_slot_extraction",
        max_tokens=200,
        json_mode=True,
    )
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        parsed = {}

    intent = parsed.get("intent") or "book_appointment"
    slot_updates = {key: value for key, value in (parsed.get("slot_updates") or {}).items() if value}
    reply_text = parsed.get("reply_text") or "Could you tell me more about what you'd like to book?"
    return intent, slot_updates, reply_text


async def _generate_confirmation_message(
    router: LLMRouter, db: AsyncSession, service_name: str, start: datetime
) -> str:
    user_message = f"Service: {service_name}\nDate/time: {start.strftime('%A, %B %d at %I:%M %p')}"
    return await router.complete(
        db, system=CONFIRMATION_SYSTEM_PROMPT, user=user_message, purpose="booking_confirmation", max_tokens=100
    )


def _make_faq_llm_fallback(router: LLMRouter, db: AsyncSession):
    async def _fallback(query: str, matches: list[FaqMatch]) -> str:
        context = "\n".join(f"Q: {match.question}\nA: {match.answer}" for match in matches)
        user_message = f"Context:\n{context}\n\nQuestion: {query}"
        return await router.complete(
            db, system=FAQ_GROUNDING_SYSTEM_PROMPT, user=user_message, purpose="faq_grounded_answer", max_tokens=200
        )

    return _fallback


async def _persist_state(db: AsyncSession, session: ConversationSession, state: dict) -> None:
    session.state = state
    await db.commit()


def _fresh_state(turn_count: int) -> dict:
    return {"intent": None, "slots": {}, "turn_count": turn_count}


async def process_turn(
    db: AsyncSession,
    *,
    session: ConversationSession,
    message: str,
    client_id: uuid.UUID,
    router: LLMRouter | None = None,
) -> TurnResult:
    router = router or get_default_router()
    state = dict(session.state or {})
    slots = dict(state.get("slots") or {})
    intent = state.get("intent")
    llm_calls = 0

    if intent is None:
        intent = classify_intent_by_keywords(message)
        if intent is None:
            llm_calls += 1
            intent, slot_updates, reply_text = await _llm_classify_and_extract(router, db, message)
            slots.update(slot_updates)
            state = {"intent": intent, "slots": slots, "turn_count": state.get("turn_count", 0) + 1}
            await _persist_state(db, session, state)
            return TurnResult(reply_text=reply_text, llm_calls=llm_calls, state=state)
        state["intent"] = intent

    if intent == "faq":
        answer = await answer_faq(db, message, llm_fallback=_make_faq_llm_fallback(router, db))
        if answer.llm_used:
            llm_calls += 1
        state = _fresh_state(state.get("turn_count", 0) + 1)
        await _persist_state(db, session, state)
        return TurnResult(reply_text=answer.text, llm_calls=llm_calls, state=state)

    if intent == "book_appointment":
        return await _process_booking_turn(db, session, state, slots, message, client_id, router, llm_calls)

    state["turn_count"] = state.get("turn_count", 0) + 1
    await _persist_state(db, session, state)
    return TurnResult(
        reply_text="I'm not sure how to help with that yet — could you tell me more?",
        llm_calls=llm_calls,
        state=state,
    )


async def _process_booking_turn(
    db: AsyncSession,
    session: ConversationSession,
    state: dict,
    slots: dict,
    message: str,
    client_id: uuid.UUID,
    router: LLMRouter,
    llm_calls: int,
) -> TurnResult:
    presented_slots = state.get("presented_slots") or []

    if presented_slots:
        chosen = _match_presented_slot(message, presented_slots)
        if chosen is not None:
            chosen_start = datetime.fromisoformat(chosen["start"])
            try:
                appointment = await create_booking(
                    db,
                    client_id=client_id,
                    service_id=uuid.UUID(chosen["service_id"]),
                    staff_id=uuid.UUID(chosen["staff_id"]),
                    scheduled_start=chosen_start,
                    booking_channel="chat",
                )
            except BookingConflictError:
                state["presented_slots"] = None
                state["turn_count"] = state.get("turn_count", 0) + 1
                await _persist_state(db, session, state)
                return TurnResult(
                    reply_text="Sorry, that slot was just taken. Could you pick another one, or a different date?",
                    llm_calls=llm_calls,
                    state=state,
                )

            llm_calls += 1
            service = await db.get(Service, appointment.service_id)
            # chosen_start, not appointment.scheduled_start: SQLAlchemy
            # refreshes the appointment from Postgres after insert, and a
            # `timestamptz` column always reads back UTC-normalized
            # regardless of the location's real timezone (found in manual
            # end-to-end testing: a 12:00 PM Pacific booking was confirmed
            # back to the client as "7 PM", its UTC hour, formatted as if it
            # were already local). chosen_start is the same instant, still
            # carrying the offset it was actually presented and booked in.
            confirmation = await _generate_confirmation_message(
                router, db, service.name if service else "your service", chosen_start
            )
            state = _fresh_state(state.get("turn_count", 0) + 1)
            await _persist_state(db, session, state)
            return TurnResult(
                reply_text=confirmation, llm_calls=llm_calls, state=state, appointment_id=str(appointment.id)
            )

    service_names = await _get_active_service_names(db)
    matched_service = match_service(message, service_names)
    if matched_service:
        slots["service"] = matched_service
    parsed_date = extract_date(message)
    if parsed_date:
        slots["date"] = parsed_date.isoformat()
    time_window = extract_time_window(message)
    if time_window:
        slots["time_window"] = time_window
    specific_time = extract_specific_time(message)
    if specific_time:
        slots["specific_time"] = specific_time.isoformat()

    missing = [slot_name for slot_name in REQUIRED_SLOTS if not slots.get(slot_name)]

    if missing:
        if not matched_service and not parsed_date and not time_window:
            llm_calls += 1
            _, slot_updates, reply_text = await _llm_classify_and_extract(router, db, message, existing_slots=slots)
            slots.update(slot_updates)
            missing = [slot_name for slot_name in REQUIRED_SLOTS if not slots.get(slot_name)]
            state["slots"] = slots
            state["turn_count"] = state.get("turn_count", 0) + 1
            if missing:
                await _persist_state(db, session, state)
                return TurnResult(reply_text=reply_text, llm_calls=llm_calls, state=state)
        else:
            state["slots"] = slots
            state["turn_count"] = state.get("turn_count", 0) + 1
            await _persist_state(db, session, state)
            return TurnResult(reply_text=_templated_missing_slot_prompt(missing), llm_calls=llm_calls, state=state)

    service = await _find_service_by_name(db, slots["service"])
    if service is None:
        state["slots"] = {key: value for key, value in slots.items() if key != "service"}
        state["turn_count"] = state.get("turn_count", 0) + 1
        await _persist_state(db, session, state)
        return TurnResult(
            reply_text=f"Sorry, I couldn't find a service called '{slots['service']}'. What would you like to book?",
            llm_calls=llm_calls,
            state=state,
        )

    target_date = date.fromisoformat(slots["date"])
    available = await compute_available_slots(db, target_date=target_date, duration_minutes=service.duration_minutes)
    available = _filter_by_time_window(available, slots.get("time_window"))

    state["slots"] = slots
    state["turn_count"] = state.get("turn_count", 0) + 1

    if not available:
        await _persist_state(db, session, state)
        return TurnResult(
            reply_text=f"Sorry, there's nothing available for {service.name} on {target_date.isoformat()}. "
            "Would another day work?",
            llm_calls=llm_calls,
            state=state,
        )

    requested_time = time.fromisoformat(slots["specific_time"]) if slots.get("specific_time") else None
    top_options = _closest_to_requested_time(available, requested_time)[:3]

    # Only worth naming the location per-option when the presented slots
    # actually span more than one — the common single-location case (and any
    # multi-location business whose top matches happen to share one) stays as
    # plain times, so this never adds noise for the setup most deployments
    # actually have. Naming it also disambiguates two slots that land on the
    # same clock time at different locations, which quick-reply matching
    # would otherwise have no way to tell apart.
    distinct_locations = {option.location_id for option in top_options if option.location_id}
    location_names = await _location_names_by_id(db, distinct_locations) if len(distinct_locations) > 1 else {}

    def _option_label(option: AvailableSlot) -> str:
        time_label = option.start.strftime("%I:%M %p")
        if option.location_id and option.location_id in location_names:
            return f"{time_label} at {location_names[option.location_id]}"
        return time_label

    labels = [_option_label(option) for option in top_options]
    presented = [
        {
            "staff_id": str(option.staff_id),
            "service_id": str(service.id),
            "location_id": str(option.location_id) if option.location_id else None,
            "start": option.start.isoformat(),
            "end": option.end.isoformat(),
            "label": label,
        }
        for option, label in zip(top_options, labels, strict=True)
    ]
    state["presented_slots"] = presented
    await _persist_state(db, session, state)

    options_text = "\n".join(f"{i + 1}. {label}" for i, label in enumerate(labels))
    reply_text = (
        f"Here are some open times for {service.name} on {target_date.strftime('%A, %B %d')}:\n"
        f"{options_text}\nWhich works best?"
    )
    return TurnResult(reply_text=reply_text, llm_calls=llm_calls, state=state, quick_replies=labels)
