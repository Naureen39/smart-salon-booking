from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag import answer_faq
from app.db.session import get_db
from app.schemas.faq import FaqAnswerResponse, FaqQuestionRequest

router = APIRouter(prefix="/faq", tags=["faq"])


@router.post("/ask", response_model=FaqAnswerResponse)
async def ask_faq(payload: FaqQuestionRequest, db: AsyncSession = Depends(get_db)) -> FaqAnswerResponse:
    result = await answer_faq(db, payload.question)
    return FaqAnswerResponse(
        answer=result.text,
        llm_used=result.llm_used,
        matched_question=result.matched_question,
        similarity=result.similarity,
    )
