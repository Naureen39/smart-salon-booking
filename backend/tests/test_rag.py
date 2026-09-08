import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_passage
from app.ai.rag import FALLBACK_MESSAGE, answer_faq, search_faq
from app.db.models.faq_document import FaqDocument


@pytest.fixture
async def seeded_faq(db_session: AsyncSession) -> FaqDocument:
    embedding = embed_passage("What are your hours?")
    doc = FaqDocument(
        question="What are your hours?",
        answer="We're open Tuesday through Saturday, 9 AM to 6 PM.",
        embedding=embedding,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


async def test_search_faq_finds_close_match(db_session: AsyncSession, seeded_faq: FaqDocument) -> None:
    matches = await search_faq(db_session, "What time are you open?")
    assert matches
    assert matches[0].question == seeded_faq.question
    assert matches[0].similarity > 0.5


async def test_answer_faq_returns_stored_answer_with_no_llm_call_when_confident(
    db_session: AsyncSession, seeded_faq: FaqDocument
) -> None:
    llm_fallback_called = False

    async def _llm_fallback(query: str, matches: list) -> str:
        nonlocal llm_fallback_called
        llm_fallback_called = True
        return "should not be reached"

    result = await answer_faq(db_session, "What are your hours?", llm_fallback=_llm_fallback)

    assert result.llm_used is False
    assert result.text == seeded_faq.answer
    assert result.matched_question == seeded_faq.question
    assert llm_fallback_called is False


async def test_answer_faq_falls_back_when_no_confident_match(
    db_session: AsyncSession, seeded_faq: FaqDocument
) -> None:
    result = await answer_faq(db_session, "Do you offer skydiving lessons?")
    assert result.llm_used is False
    assert result.text == FALLBACK_MESSAGE


async def test_answer_faq_uses_llm_fallback_when_provided_and_match_is_weak(
    db_session: AsyncSession, seeded_faq: FaqDocument
) -> None:
    async def _llm_fallback(query: str, matches: list) -> str:
        return "LLM-grounded answer"

    result = await answer_faq(db_session, "Do you offer skydiving lessons?", llm_fallback=_llm_fallback)
    assert result.llm_used is True
    assert result.text == "LLM-grounded answer"


async def test_ask_faq_endpoint_returns_direct_answer(
    client: AsyncClient, seeded_faq: FaqDocument
) -> None:
    response = await client.post("/api/v1/faq/ask", json={"question": "What are your hours?"})
    assert response.status_code == 200
    body = response.json()
    assert body["llm_used"] is False
    assert body["answer"] == seeded_faq.answer
