FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv

# ffmpeg — нормализация любого входного аудио в формат, понятный модели распознавания
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY shared/ /shared/
COPY workers/pyproject.toml workers/uv.lock* ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

COPY workers/ .

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["uv", "run", "celery", "-A", "workers.celery_app:app", "worker", \
     "--loglevel=info", "--concurrency=2", "--queues=default"]
