from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat import MessageRole


class ChatStreamRequest(BaseModel):
    session_id: UUID
    user_id: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: MessageRole
    content: str
    created_at: datetime


class SessionHistoryOut(BaseModel):
    session_id: UUID
    messages: list[ChatMessageOut]
