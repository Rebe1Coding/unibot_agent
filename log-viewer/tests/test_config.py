import pytest


def _reload_settings():
    from app.config import Settings
    return Settings()


def test_defaults(monkeypatch):
    for key in [
        "LOG_VIEWER_HOST", "LOG_VIEWER_PORT", "LOG_VIEWER_LOG_LEVEL",
        "LOG_VIEWER_DEFAULT_TAIL", "LOG_VIEWER_MAX_BUFFER",
        "LOG_VIEWER_HEARTBEAT_SEC", "LOG_VIEWER_PROJECT_NAME",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = _reload_settings()
    assert s.log_viewer_host == "0.0.0.0"
    assert s.log_viewer_port == 3002
    assert s.log_viewer_log_level == "INFO"
    assert s.log_viewer_default_tail == 200
    assert s.log_viewer_max_buffer == 5000
    assert s.log_viewer_heartbeat_sec == 15
    assert s.log_viewer_project_name == "unibot"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LOG_VIEWER_PORT", "4000")
    monkeypatch.setenv("LOG_VIEWER_DEFAULT_TAIL", "50")
    monkeypatch.setenv("LOG_VIEWER_PROJECT_NAME", "custom")
    s = _reload_settings()
    assert s.log_viewer_port == 4000
    assert s.log_viewer_default_tail == 50
    assert s.log_viewer_project_name == "custom"


def test_port_must_be_int(monkeypatch):
    monkeypatch.setenv("LOG_VIEWER_PORT", "not-a-number")
    with pytest.raises(Exception):
        _reload_settings()
