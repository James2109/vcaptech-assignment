# Chat API — AI Core Service

Small async FastAPI service that runs an OpenAI-Agents-SDK agent, streams its
reply over SSE, and persists every turn to PostgreSQL.

## Stack

| | |
|---|---|
| Language | Python 3.11+ |
| Framework | FastAPI + `sse-starlette` |
| Agent | `openai-agents` SDK in streaming mode |
| DB | PostgreSQL via async SQLAlchemy 2.0 (`asyncpg`) |
| Migrations | Alembic |
| Tests | `pytest` + `pytest-asyncio` + `httpx` (ASGI transport) |
| Runtime | `docker compose up` brings up the API + Postgres |

## Layout

```
app/
├── main.py                 # FastAPI app + lifespan
├── core/config.py          # pydantic-settings
├── api/
│   ├── deps.py             # DB / Settings / Agent deps
│   └── v1/
│       ├── router.py
│       └── endpoints/
│           ├── chat.py     # POST /chat/stream  (SSE)
│           ├── sessions.py # GET history, DELETE session
│           └── health.py
├── db/                     # Engine, base, session
├── models/chat.py          # ChatSession + ChatMessage + role enum
├── schemas/chat.py         # Pydantic request/response shapes
├── services/
│   ├── agent.py            # OpenAI Agents SDK wrapper (streaming)
│   ├── chat_service.py     # Persistence + ownership rules
│   └── chat_stream.py      # Pure SSE-event generator (testable)
└── sse/events.py           # Wire-format helpers + heartbeat factory

alembic/                    # `alembic upgrade head` builds the schema
tests/
├── unit/                   # SSE event ordering, mocked agent
└── integration/            # Real DB, mocked agent, full request lifecycle
```

## Run with Docker (recommended)

```bash
cp .env.example .env
# put your real OPENAI_API_KEY in .env

docker compose up --build
# API is on http://localhost:8000  ·  Postgres on localhost:5432
```

The `api` service runs `alembic upgrade head` before starting Uvicorn, so the
schema is ready on first boot.

Try it:

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "user_id":    "user-123",
    "message":    "What is the capital of France?"
  }'
```

You'll see `agent.message.delta` events streaming in, then a final
`agent.message.done` event, with `heartbeat` every 15s while the stream stays
open.

## Run locally (no Docker)

```bash
uv sync --dev
docker run -d --name pg -p 5432:5432 \
  -e POSTGRES_USER=chat -e POSTGRES_PASSWORD=chat -e POSTGRES_DB=chat \
  postgres:16-alpine

export DATABASE_URL=postgresql+asyncpg://chat:chat@localhost:5432/chat
export OPENAI_API_KEY=sk-...

uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## API contract

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/chat/stream` | Body `{session_id, user_id, message}` → `text/event-stream` |
| `GET`  | `/api/v1/sessions/{id}/history?user_id=...` | Full ordered message list |
| `DELETE` | `/api/v1/sessions/{id}?user_id=...` | Cascade-deletes messages |
| `GET` | `/api/v1/health` | `{"status":"ok"}` |

SSE events:

| Event | Payload |
|---|---|
| `agent.message.delta` | `{"text": "..."}` per model chunk |
| `agent.message.done`  | `{"session_id": "..."}` once the run finishes |
| `agent.workflow.failed` | `{"error": "..."}` on any unhandled exception |
| `heartbeat` | `{"ts": <epoch>}` every `SSE_HEARTBEAT_SECONDS` (default 15) |

Sessions are scoped by `(session_id, user_id)`. Reading or deleting someone
else's session returns `403`.

## Tests

```bash
# Unit tests only — no DB required, no API key required
uv run pytest -m "not integration"

# Full suite — needs a running Postgres at DATABASE_URL (or TEST_DATABASE_URL)
docker compose up -d postgres
uv run pytest
```

- **Unit** — drives the SSE generator with a fake agent and asserts event
  order (`delta*, done`) plus the failure path (`delta, workflow.failed`).
- **Integration** — boots the FastAPI app over an in-process ASGI transport,
  overrides only the agent dep, and asserts that both the user message and the
  assembled assistant reply land in `chat_messages` after the stream finishes.

## Design notes

**Pre-stream DB writes happen in the request handler, not the SSE generator.**
The handler runs ownership/persistence work synchronously so an unauthorised
caller gets a real `403` *before* the SSE stream opens — instead of the error
having to be smuggled into the response body. The generator only owns the
agent run and the post-stream assistant write.

**Persistence and streaming are decoupled.** `chat_event_stream` is a pure
async generator that takes an `AgentStreamer` protocol and a
`persist_assistant` callback. That keeps the SSE wire contract testable
without spinning up a DB or hitting OpenAI, which is what the unit test
exploits.

**Heartbeats use `sse-starlette`'s `ping_message_factory`.** The library
already runs a periodic ping; pointing it at our own factory turns those into
the `heartbeat` event type the contract requires, with no extra timer task.

**Trade-offs left on the table.**
- No retry/back-off around the OpenAI call — surfacing the error as
  `agent.workflow.failed` is enough for this scope.
- History is reloaded as a flat list each turn; for long sessions you'd want a
  cap or summarisation step.
- The integration test recreates tables per-test for isolation. Fine at this
  scale; for a real suite I'd switch to nested-transaction rollback.
