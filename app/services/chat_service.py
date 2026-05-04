"""Chat persistence + history rules.

Centralises the session ownership check so endpoints never query messages
without the (session_id, user_id) pair.
"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession, MessageRole


class SessionForbiddenError(Exception):
    """Raised when a user tries to access a session that belongs to someone else."""


class SessionNotFoundError(Exception):
    """Raised when a session does not exist."""


async def get_or_create_session(
    db: AsyncSession,
    *,
    session_id: UUID,
    user_id: str,
) -> ChatSession:
    session = await db.get(ChatSession, session_id)
    if session is None:
        session = ChatSession(id=session_id, user_id=user_id)
        db.add(session)
        await db.flush()
        return session
    if session.user_id != user_id:
        raise SessionForbiddenError(str(session_id))
    return session


async def append_message(
    db: AsyncSession,
    *,
    session_id: UUID,
    role: MessageRole,
    content: str,
) -> ChatMessage:
    message = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(message)
    await db.flush()
    return message


async def list_messages(
    db: AsyncSession,
    *,
    session_id: UUID,
    user_id: str,
) -> list[ChatMessage]:
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise SessionNotFoundError(str(session_id))
    if session.user_id != user_id:
        raise SessionForbiddenError(str(session_id))

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_session(
    db: AsyncSession,
    *,
    session_id: UUID,
    user_id: str,
) -> None:
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise SessionNotFoundError(str(session_id))
    if session.user_id != user_id:
        raise SessionForbiddenError(str(session_id))
    await db.execute(delete(ChatSession).where(ChatSession.id == session_id))


def messages_to_agent_input(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": m.role.value, "content": m.content} for m in messages]
