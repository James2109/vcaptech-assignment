"""Thin wrapper around the OpenAI Agents SDK.

Kept narrow on purpose so the streaming endpoint depends on a stable
`stream_reply` async iterator instead of the SDK's surface area, which
makes the unit test trivial to mock.
"""

import os
from collections.abc import AsyncIterator
from typing import Protocol

from agents import Agent, Runner
from openai.types.responses import ResponseTextDeltaEvent

from app.core.config import Settings


class AgentStreamer(Protocol):
    async def stream_reply(
        self,
        history: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        ...


class OpenAIAgentStreamer:
    def __init__(self, settings: Settings):
        # The SDK's OpenAI client reads OPENAI_API_KEY from env; export it here
        # so settings remain the single source of truth even if .env loaded it
        # under a different name.
        if settings.openai_api_key:
            os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)

        self._agent = Agent(
            name=settings.agent_name,
            instructions=settings.agent_instructions,
            model=settings.openai_model,
        )

    async def stream_reply(
        self,
        history: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        result = Runner.run_streamed(starting_agent=self._agent, input=history)
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(
                event.data, ResponseTextDeltaEvent
            ):
                delta = event.data.delta
                if delta:
                    yield delta
