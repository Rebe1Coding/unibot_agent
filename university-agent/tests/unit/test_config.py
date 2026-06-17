"""Unit tests: application configuration (config.py)."""

from __future__ import annotations


class TestSettings:
    """Validate that Settings loads correctly from environment and defaults."""

    def test_default_values(self, monkeypatch):
        """Default values should match expected production defaults."""
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("MEMORY_TTL", raising=False)
        monkeypatch.delenv("TOKEN_BUDGET_RATIO", raising=False)
        monkeypatch.delenv("MAX_AGENT_ITERATIONS", raising=False)
        monkeypatch.delenv("VECTOR_DIM", raising=False)
        monkeypatch.delenv("MINIO_SECURE", raising=False)
        monkeypatch.delenv("AUTH_DISABLED", raising=False)

        from app.config import Settings

        s = Settings(_env_file="")
        # Настройки RouterAI берутся из config.yaml, а не из pydantic defaults
        assert s.memory_ttl == 14400
        assert s.token_budget_ratio == 0.75
        assert s.mcp_servers == {}
        assert s.max_agent_iterations == 5
        assert s.vector_dim == 1024
        assert s.minio_secure is False
        assert s.auth_disabled is False

    def test_env_override(self, monkeypatch):
        """Environment variables should override defaults."""
        monkeypatch.setenv("TOKEN_BUDGET_RATIO", "0.5")
        monkeypatch.setenv("MAX_AGENT_ITERATIONS", "7")

        from app.config import Settings

        s = Settings(_env_file="")
        assert s.token_budget_ratio == 0.5
        assert s.max_agent_iterations == 7

    def test_empty_env_file_fallback(self, monkeypatch):
        """When no .env file is present, defaults are used without error."""
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        from app.config import Settings

        s = Settings(_env_file="")
        assert s.redis_url == "redis://redis:6379/0"
        assert s.database_url == "postgresql+asyncpg://user:pass@postgres:5432/university"

    def test_module_level_singleton_exists(self):
        """The module-level `settings` singleton must be importable and loaded from YAML."""
        from app.config import settings

        assert settings is not None
        assert settings.routerai_model  # должна быть непустая строка (из config.yaml)
        assert settings.routerai_base_url.startswith("https://")


class TestSettingsEdgeCases:
    """Negative / edge case validation for config."""

    def test_internal_api_key_empty_by_default(self, monkeypatch):
        """Internal API key should default to empty string."""
        monkeypatch.delenv("INTERNAL_API_KEY", raising=False)

        from app.config import Settings

        s = Settings(_env_file="")
        assert s.internal_api_key == ""

    def test_celery_urls_are_different(self):
        """Celery broker and result backend use different Redis DBs."""
        from app.config import Settings

        s = Settings(_env_file="")
        assert "/1" in s.celery_broker_url
        assert "/2" in s.celery_result_backend
        assert s.celery_broker_url != s.celery_result_backend
