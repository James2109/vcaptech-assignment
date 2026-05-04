"""SSE event names and payload helpers.

Co-located so the wire contract is easy to audit in one place.
"""

import json
import time
from typing import Any

from sse_starlette import ServerSentEvent

EVENT_DELTA = "agent.message.delta"
EVENT_DONE = "agent.message.done"
EVENT_FAILED = "agent.workflow.failed"
EVENT_HEARTBEAT = "heartbeat"


def sse(event: str, payload: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False)}


def delta_event(text: str) -> dict[str, str]:
    return sse(EVENT_DELTA, {"text": text})


def done_event(session_id: str) -> dict[str, str]:
    return sse(EVENT_DONE, {"session_id": session_id})


def failed_event(error: str) -> dict[str, str]:
    return sse(EVENT_FAILED, {"error": error})


def heartbeat_factory() -> ServerSentEvent:
    return ServerSentEvent(
        event=EVENT_HEARTBEAT,
        data=json.dumps({"ts": int(time.time())}),
    )
