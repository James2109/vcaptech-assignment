"""End-to-end persistence test.

Hits the real FastAPI app over an in-memory ASGI transport, with the
real Postgres test DB but a fake agent so no OpenAI call happens.
Verifies that user + assistant messages land in the DB after a stream.
"""

import json
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_agent_streamer
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.chat import ChatMessage, MessageRole

pytestmark = pytest.mark.integration


class _FakeAgent:
    def __init__(self, deltas: list[str]):
        self._deltas = deltas

    async def stream_reply(self, history: list[dict[str, str]]) -> AsyncIterator[str]:
        for delta in self._deltas:
            yield delta


@pytest_asyncio.fixture
async def reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(reset_db) -> AsyncIterator[AsyncClient]:
    fake = _FakeAgent(["Hello ", "there!"])
    app.dependency_overrides[get_agent_streamer] = lambda: fake

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    event = None
    for raw_line in body.splitlines():
        line = raw_line.rstrip("\r")
        if not line:
            event = None
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:") and event is not None:
            data = line[len("data:") :].strip()
            try:
                events.append((event, json.loads(data)))
            except json.JSONDecodeError:
                events.append((event, {"_raw": data}))
    return events


@pytest.mark.asyncio
async def test_chat_stream_persists_user_and_assistant_messages(client: AsyncClient) -> None:
    session_id = uuid4()
    user_id = "user-int-1"

    response = await client.post(
        "/api/v1/chat/stream",
        json={
            "session_id": str(session_id),
            "user_id": user_id,
            "message": "What is 2+2?",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(response.text)
    event_names = [e[0] for e in events]
    assert "agent.message.delta" in event_names
    assert event_names[-1] == "agent.message.done"
    assistant_text = "".join(
        payload["text"] for name, payload in events if name == "agent.message.delta"
    )
    assert assistant_text == "Hello there!"

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
            )
        ).scalars().all()

    assert [r.role for r in rows] == [MessageRole.user, MessageRole.assistant]
    assert rows[0].content == "What is 2+2?"
    assert rows[1].content == "Hello there!"


@pytest.mark.asyncio
async def test_history_endpoint_returns_persisted_messages(client: AsyncClient) -> None:
    session_id = uuid4()
    user_id = "user-int-2"

    await client.post(
        "/api/v1/chat/stream",
        json={
            "session_id": str(session_id),
            "user_id": user_id,
            "message": "Hi",
        },
    )

    history = await client.get(
        f"/api/v1/sessions/{session_id}/history",
        params={"user_id": user_id},
    )
    assert history.status_code == 200
    body = history.json()
    assert body["session_id"] == str(session_id)
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_other_user_cannot_read_session(client: AsyncClient) -> None:
    session_id = uuid4()

    await client.post(
        "/api/v1/chat/stream",
        json={
            "session_id": str(session_id),
            "user_id": "owner",
            "message": "secret",
        },
    )

    forbidden = await client.get(
        f"/api/v1/sessions/{session_id}/history",
        params={"user_id": "intruder"},
    )
    assert forbidden.status_code == 403
