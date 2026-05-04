from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.schemas.chat import ChatMessageOut, SessionHistoryOut
from app.services.chat_service import (
    SessionForbiddenError,
    SessionNotFoundError,
    delete_session,
    list_messages,
)

router = APIRouter()


@router.get("/sessions/{session_id}/history", response_model=SessionHistoryOut)
async def get_session_history(
    session_id: UUID,
    db: DbSession,
    user_id: str = Query(..., min_length=1, max_length=255),
) -> SessionHistoryOut:
    try:
        messages = await list_messages(db, session_id=session_id, user_id=user_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        ) from exc
    except SessionForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from exc

    return SessionHistoryOut(
        session_id=session_id,
        messages=[ChatMessageOut.model_validate(m) for m in messages],
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_session(
    session_id: UUID,
    db: DbSession,
    user_id: str = Query(..., min_length=1, max_length=255),
) -> None:
    try:
        await delete_session(db, session_id=session_id, user_id=user_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        ) from exc
    except SessionForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from exc
    await db.commit()
