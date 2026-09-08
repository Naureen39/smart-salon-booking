from pydantic import BaseModel


class FaqQuestionRequest(BaseModel):
    question: str


class FaqAnswerResponse(BaseModel):
    answer: str
    llm_used: bool
    matched_question: str | None
    similarity: float | None
