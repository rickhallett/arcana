from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "ARCANA_"}
    nats_url: str = "nats://localhost:4222"
    db_url: str = "sqlite+aiosqlite:///store/arcana.db"
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    uploads_dir: str = "uploads"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    langsmith_api_key: str = ""
    langsmith_project: str = "arcana"
    trace_level: Literal["full", "metadata"] = "full"
    worker_type: str = ""
    max_retries: int = 3
    retry_base_delay: float = 2.0
    retry_max_delay: float = 16.0
    nats_ack_timeout: int = 30
