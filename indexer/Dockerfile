# syntax=docker/dockerfile:1.7

# ---- Builder ----
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- Runtime ----
FROM python:3.11-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser indexer /app/indexer

RUN install -d -o appuser -g appuser /app/.cache/huggingface

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface

USER appuser
EXPOSE 8001

CMD ["uvicorn", "indexer.main:app", "--host", "0.0.0.0", "--port", "8001"]
