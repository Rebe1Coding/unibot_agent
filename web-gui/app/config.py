from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    web_gui_host: str = "0.0.0.0"
    web_gui_port: int = 8002
    api_base_url: str = "http://university-agent:8000"
    api_key: str = ""
    log_level: str = "INFO"
    request_timeout: float = 120.0
    active_user_window_seconds: int = 300

    # Google OAuth 2.0
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8002/auth/google/callback"
    # Куда вернуть браузер после входа/выхода
    post_login_redirect: str = "/"

    # JWT-сессия в httpOnly-куке
    jwt_secret: str = ""
    jwt_ttl_seconds: int = 604800  # 7 дней
    cookie_secure: bool = False  # true за HTTPS в проде
    cookie_name: str = "unibot_session"

    # Пустой = вход открыт всем (dev). Иначе перечень эндпоинтов проверяется на куку.
    auth_disabled: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
