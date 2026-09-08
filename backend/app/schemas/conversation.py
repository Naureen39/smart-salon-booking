import uuid

from pydantic import BaseModel, ConfigDict


class StartSessionRequest(BaseModel):
    channel: str = "chat"


class ConversationSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel: str | None
    state: dict


class SendMessageRequest(BaseModel):
    message: str


class ConversationTurnResponse(BaseModel):
    reply_text: str
    quick_replies: list[str] | None = None
    appointment_id: str | None = None
    state: dict
