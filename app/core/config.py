from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str = Field(
        default="postgresql+asyncpg://chat:chat@localhost:5432/chat",
    )

    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-5-nano")

    sse_heartbeat_seconds: int = 15

    agent_name: str = "ChatAssistant"
    agent_instructions: str = (
        "You are a friendly and concise chat assistant. "
        "Answer the user's questions accurately and clearly. "
        "Keep replies short unless the user explicitly asks for more detail."
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
