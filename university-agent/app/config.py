from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings


def _load_yaml_config() -> dict[str, Any]:
    """Загрузить config.yaml из корня приложения."""
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def _yaml_routerai() -> dict[str, Any]:
    """Извлечь секцию routerai из config.yaml."""
    yc = _load_yaml_config()
    return yc.get("routerai", {})


_YAML = _load_yaml_config()
_YAML_ROUTERAI = _yaml_routerai()


class Settings(BaseSettings):
    # LLM (RouterAI) — API-ключ из .env, остальное из config.yaml
    routerai_api_key: str = ""
    routerai_base_url: str = ""
    routerai_model: str = ""
    routerai_temperature: float = 0.1
    routerai_max_tokens: int = 4096

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://user:pass@postgres:5432/university"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "university-files"
    # Public hostname used to sign download URLs that leave the docker network
    # (Telegram clients, browsers). Must match the host the client actually hits,
    # otherwise the SigV4 signature check on MinIO will fail. Empty = same as minio_endpoint.
    minio_public_endpoint: str = ""
    minio_public_secure: bool = False

    # Embeddings
    embedding_model: str = "deepvk/USER-bge-m3"
    bm25_model: str = "Qdrant/bm25"
    vector_dim: int = 1024

    # Memory
    memory_ttl: int = 14400  # 4 hours in seconds
    archive_session_ttl: int = 3600  # TTL для старой сессии после new_chat — 1 час

    # Token budget
    token_budget_ratio: float = 0.75  # share of the model context window for prompt
    context_window: int = 0  # 0 = auto-detect from model name
    token_reserve: int = 6000  # tokens reserved for system prompt + agent scratchpad

    # Agent (одна итерация уходит на обязательное размышление через think)
    max_agent_iterations: int = 5

    # MCP servers (JSON map: name -> {transport, url|command, ...})
    mcp_servers: dict = {}

    # Web search
    serpapi_api_key: str = ""
    tavily_api_key: str = ""

    # Auth
    internal_api_key: str = ""
    auth_disabled: bool = False

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # extra="ignore": the repo uses one shared .env; each service reads only its own vars.
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Инициализация: YAML даёт defaults, .env переопределяет (только API-ключ)
_settings = Settings(
    routerai_base_url=_YAML_ROUTERAI.get("base_url", "https://routerai.ru/api/v1"),
    routerai_model=_YAML_ROUTERAI.get("model", "openai/gpt-4o"),
    routerai_temperature=float(_YAML_ROUTERAI.get("temperature", 0.1)),
    routerai_max_tokens=int(_YAML_ROUTERAI.get("max_tokens", 4096)),
)

# Публичный доступ к context_windows из YAML
CONTEXT_WINDOWS: dict[str, int] = {
    str(k): int(v) for k, v in _YAML.get("context_windows", {}).items()
}

settings = _settings
