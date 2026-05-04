"""Test bootstrap.

Env vars must be set BEFORE importing anything from `app`, because the
DB engine and settings cache freeze at first import. Anything else here
goes through normal fixtures.
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://chat:chat@localhost:5432/chat",
    ),
)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-used")
