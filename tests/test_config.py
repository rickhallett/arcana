from arcana.config import Settings


def test_default_settings():
    settings = Settings(openai_api_key="test-openai", anthropic_api_key="test-anthropic")
    assert settings.nats_url == "nats://localhost:4222"
    assert settings.db_url == "sqlite+aiosqlite:///store/arcana.db"
    assert settings.chroma_host == "localhost"
    assert settings.chroma_port == 8000
    assert settings.trace_level == "full"
    assert settings.uploads_dir == "uploads"


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("ARCANA_NATS_URL", "nats://nats.arcana:4222")
    monkeypatch.setenv("ARCANA_DB_URL", "postgresql+asyncpg://user:pass@db:5432/arcana")
    monkeypatch.setenv("ARCANA_TRACE_LEVEL", "metadata")
    monkeypatch.setenv("ARCANA_OPENAI_API_KEY", "sk-prod")
    monkeypatch.setenv("ARCANA_ANTHROPIC_API_KEY", "sk-ant-prod")
    settings = Settings()
    assert settings.nats_url == "nats://nats.arcana:4222"
    assert settings.db_url == "postgresql+asyncpg://user:pass@db:5432/arcana"
    assert settings.trace_level == "metadata"
