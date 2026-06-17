from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    embedding_model: str = "deepvk/USER-bge-m3"
    bm25_model: str = "Qdrant/bm25"
    chunk_size: int = 512
    chunk_overlap: int = 64
    batch_size: int = 64
    admin_username: str = "admin"
    admin_password: str

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
