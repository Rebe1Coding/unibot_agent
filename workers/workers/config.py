from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "university-files"
    minio_public_endpoint: str = ""
    minio_public_secure: bool = False

    # RouterAI (транскрибация аудио + LLM-структурирование)
    routerai_api_key: str = ""
    routerai_base_url: str = "https://routerai.ru/api/v1"
    routerai_model: str = "openai/gpt-4o-mini"
    transcribe_model: str = "mistralai/voxtral-small-24b-2507"


settings = Settings()
