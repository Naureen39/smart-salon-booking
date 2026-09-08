"""Retrieval-augmented FAQ answering (docs plan §9.2). Most FAQ questions never
need an LLM call at all: embed the incoming question, run a pgvector cosine
similarity search against pre-embedded canonical FAQ questions, and return the
stored answer directly when the top match is confident enough.

Below that confidence threshold, the plan calls for grounding a generated
answer in the retrieved snippets via the LLM router — which doesn't exist yet
(that's Phase 6/7). So this module accepts an optional `llm_fallback`
callable the orchestrator can supply later; without one, it returns a plain
"I'll check with staff" response, which keeps this fully functional and
testable on its own today.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_query
from app.core.config import get_settings
from app.db.models.faq_document import FaqDocument

settings = get_settings()

TOP_K = 3
FALLBACK_MESSAGE = "I'm not fully certain about that — let me check with our staff and get back to you."


@dataclass(frozen=True)
class FaqMatch:
    question: str
    answer: str
    similarity: float


@dataclass(frozen=True)
class FaqAnswer:
    text: str
    llm_used: bool
    matched_question: str | None
    similarity: float | None


async def search_faq(db: AsyncSession, query: str, *, top_k: int = TOP_K) -> list[FaqMatch]:
    """Returns up to top_k FAQ documents ranked by cosine similarity to `query`,
    highest similarity first."""
    query_embedding = embed_query(query)
    distance = FaqDocument.embedding.cosine_distance(query_embedding)

    result = await db.execute(select(FaqDocument, distance.label("distance")).order_by(distance).limit(top_k))
    return [
        FaqMatch(question=doc.question, answer=doc.answer, similarity=1 - dist)
        for doc, dist in result.all()
    ]


async def answer_faq(
    db: AsyncSession,
    query: str,
    *,
    llm_fallback: Callable[[str, list[FaqMatch]], Awaitable[str]] | None = None,
) -> FaqAnswer:
    matches = await search_faq(db, query)
    top_similarity = matches[0].similarity if matches else None

    if matches and matches[0].similarity >= settings.rag_similarity_threshold:
        top = matches[0]
        return FaqAnswer(text=top.answer, llm_used=False, matched_question=top.question, similarity=top.similarity)

    if llm_fallback is not None:
        text = await llm_fallback(query, matches)
        return FaqAnswer(text=text, llm_used=True, matched_question=None, similarity=top_similarity)

    return FaqAnswer(text=FALLBACK_MESSAGE, llm_used=False, matched_question=None, similarity=top_similarity)
