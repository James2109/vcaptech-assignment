"""Unit tests for the SSE event generator.

The agent is mocked so no OpenAI call happens. Asserts the wire-level
event ordering and payload shape promised by the SSE contract.
"""

import json
from collections.abc import AsyncIterator
from uuid import uuid4

from app.services.chat_stream import chat_event_stream
from app.sse.events import EVENT_DELTA, EVENT_DONE, EVENT_FAILED


class _FakeAgent:
    def __init__(self, deltas: list[str]):
        self._deltas = deltas

    async def stream_reply(self, history: list[dict[str, str]]) -> AsyncIterator[str]:
        for delta in self._deltas:
            yield delta


class _ExplodingAgent:
    async def stream_reply(self, history: list[dict[str, str]]) -> AsyncIterator[str]:
        yield "partial"
        raise RuntimeError("boom")


async def test_emits_deltas_then_done_in_order() -> None:
    persisted: list[str] = []

    async def persist(content: str) -> None:
        persisted.append(content)

    session_id = uuid4()
    events = [
        e
        async for e in chat_event_stream(
            agent=_FakeAgent(["Hel", "lo ", "world"]),
            history=[],
            session_id=session_id,
            persist_assistant=persist,
        )
    ]

    assert [e["event"] for e in events] == [
        EVENT_DELTA,
        EVENT_DELTA,
        EVENT_DELTA,
        EVENT_DONE,
    ]
    assert [json.loads(e["data"])["text"] for e in events[:3]] == ["Hel", "lo ", "world"]
    assert json.loads(events[-1]["data"])["session_id"] == str(session_id)
    assert persisted == ["Hello world"]


async def test_emits_failed_event_on_agent_error() -> None:
    persisted: list[str] = []

    async def persist(content: str) -> None:
        persisted.append(content)

    events = [
        e
        async for e in chat_event_stream(
            agent=_ExplodingAgent(),
            history=[],
            session_id=uuid4(),
            persist_assistant=persist,
        )
    ]

    assert [e["event"] for e in events] == [EVENT_DELTA, EVENT_FAILED]
    payload = json.loads(events[-1]["data"])
    assert "boom" in payload["error"]
    assert persisted == [], "must not persist assistant message when stream fails"


async def test_persist_failure_surfaces_as_workflow_failed() -> None:
    async def persist(content: str) -> None:
        raise RuntimeError("db down")

    events = [
        e
        async for e in chat_event_stream(
            agent=_FakeAgent(["ok"]),
            history=[],
            session_id=uuid4(),
            persist_assistant=persist,
        )
    ]

    assert [e["event"] for e in events] == [EVENT_DELTA, EVENT_FAILED]
