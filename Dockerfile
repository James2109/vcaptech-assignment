# syntax=docker/dockerfile:1.7

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# `uv` ships as a static binary — no apt-get, no compiler needed. All our
# Python deps have wheels for linux/amd64/cpython3.11, so there's nothing
# to build from source either.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

# Install runtime deps in their own layer so changes to app code don't
# invalidate the dep cache. The cache mount keeps uv's package cache
# warm across rebuilds.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
