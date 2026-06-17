from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    log_viewer_host: str = "0.0.0.0"
    log_viewer_port: int = 3002
    log_viewer_log_level: str = "INFO"
    log_viewer_default_tail: int = 200
    log_viewer_max_buffer: int = 5000
    log_viewer_heartbeat_sec: int = 15
    log_viewer_project_name: str = "unibot"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
