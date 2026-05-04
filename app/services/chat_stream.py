"""Pure async generator that turns an agent stream into SSE events.

Decoupled from FastAPI/DB so the unit test can drive it with mocks.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

from app.services.agent import AgentStreamer
from app.sse.events import delta_event, done_event, failed_event


async def chat_event_stream(
    *,
    agent: AgentStreamer,
    history: list[dict[str, str]],
    session_id: UUID,
    persist_assistant: Callable[[str], Awaitable[None]],
) -> AsyncIterator[dict[str, str]]:
    chunks: list[str] = []
    try:
        async for delta in agent.stream_reply(history):
            chunks.append(delta)
            yield delta_event(delta)
        await persist_assistant("".join(chunks))
        yield done_event(str(session_id))
    except Exception as exc:  # noqa: BLE001 - stream contract requires surfacing all errors
        yield failed_event(f"{type(exc).__name__}: {exc}")
