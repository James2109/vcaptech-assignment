from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.agent import AgentStreamer


def get_agent_streamer(request: Request) -> AgentStreamer:
    return request.app.state.agent_streamer


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
AgentDep = Annotated[AgentStreamer, Depends(get_agent_streamer)]
