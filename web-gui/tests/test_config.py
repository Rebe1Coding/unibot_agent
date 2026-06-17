import importlib

import pytest


def _reload_settings():
    from app import config as cfg
    importlib.reload(cfg)
    return cfg.settings


def test_defaults(monkeypatch):
    for key in [
        "WEB_GUI_HOST", "WEB_GUI_PORT", "API_BASE_URL", "API_KEY", "LOG_LEVEL",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = _reload_settings()
    assert s.web_gui_host == "0.0.0.0"
    assert s.web_gui_port == 8002
    assert s.api_base_url == "http://university-agent:8000"
    assert s.api_key == ""
    assert s.log_level == "INFO"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("WEB_GUI_HOST", "127.0.0.1")
    monkeypatch.setenv("WEB_GUI_PORT", "9999")
    monkeypatch.setenv("API_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("API_KEY", "secret-123")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = _reload_settings()
    assert s.web_gui_host == "127.0.0.1"
    assert s.web_gui_port == 9999
    assert s.api_base_url == "http://localhost:8000"
    assert s.api_key == "secret-123"
    assert s.log_level == "DEBUG"


def test_port_must_be_int(monkeypatch):
    monkeypatch.setenv("WEB_GUI_PORT", "not-a-number")
    with pytest.raises(Exception):
        _reload_settings()
