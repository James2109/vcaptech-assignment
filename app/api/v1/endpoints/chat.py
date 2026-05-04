from fastapi import APIRouter, HTTPException, status
from sse_starlette import EventSourceResponse

from app.api.deps import AgentDep, DbSession, SettingsDep
from app.db.session import SessionLocal
from app.models.chat import MessageRole
from app.schemas.chat import ChatStreamRequest
from app.services.chat_service import (
    SessionForbiddenError,
    append_message,
    get_or_create_session,
    list_messages,
    messages_to_agent_input,
)
from app.services.chat_stream import chat_event_stream
from app.sse.events import heartbeat_factory

router = APIRouter()


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatStreamRequest,
    db: DbSession,
    agent: AgentDep,
    settings: SettingsDep,
) -> EventSourceResponse:
    # Pre-stream DB work: ownership check, persist user message, snapshot history.
    # Doing it here (not inside the generator) lets us return an HTTP 403 before
    # the SSE response begins, instead of leaking the error onto the wire.
    try:
        session = await get_or_create_session(
            db, session_id=payload.session_id, user_id=payload.user_id
        )
        await append_message(
            db,
            session_id=session.id,
            role=MessageRole.user,
            content=payload.message,
        )
        history_rows = await list_messages(
            db, session_id=session.id, user_id=payload.user_id
        )
        history = messages_to_agent_input(history_rows)
        await db.commit()
    except SessionForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="session does not belong to user",
        ) from exc

    session_id = session.id

    async def persist_assistant(content: str) -> None:
        # Use a fresh session because the request-scoped one is closed by the
        # time the SSE generator finishes producing.
        async with SessionLocal() as write_db:
            await append_message(
                write_db,
                session_id=session_id,
                role=MessageRole.assistant,
                content=content,
            )
            await write_db.commit()

    return EventSourceResponse(
        chat_event_stream(
            agent=agent,
            history=history,
            session_id=session_id,
            persist_assistant=persist_assistant,
        ),
        ping=settings.sse_heartbeat_seconds,
        ping_message_factory=heartbeat_factory,
    )
