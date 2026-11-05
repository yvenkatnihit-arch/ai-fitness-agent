import pytest
from pydantic import ValidationError

from app.core.config import Settings

REQUIRED = {
    "GEMINI_API_KEY": "test-gemini-key",
    "GEMINI_SMALL_MODEL": "test-small-model",
    "GEMINI_MID_MODEL": "test-mid-model",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "test-publishable",
    "SUPABASE_SECRET_KEY": "test-secret",
    "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
}


@pytest.fixture
def env(monkeypatch):
    """Start every test from a clean environment with only the required values set."""
    for name in list(REQUIRED) + ["CORS_ORIGINS", "APP_ENV", "LANGSMITH_TRACING"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in REQUIRED.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def load() -> Settings:
    # _env_file=None: ignore any real backend/.env so tests never depend on it.
    return Settings(_env_file=None)


def test_loads_when_required_values_present(env):
    settings = load()

    assert settings.gemini_small_model == "test-small-model"
    assert settings.app_env == "development"
    assert settings.cors_origins == ["http://localhost:5173"]


def test_missing_required_value_fails_clearly(env):
    env.delenv("GEMINI_API_KEY")

    with pytest.raises(ValidationError) as error:
        load()

    assert "gemini_api_key" in str(error.value)


def test_secrets_are_hidden_when_printed(env):
    settings = load()

    assert "test-gemini-key" not in repr(settings)
    assert settings.gemini_api_key.get_secret_value() == "test-gemini-key"


def test_cors_origins_splits_comma_list(env):
    env.setenv("CORS_ORIGINS", "http://localhost:5173, https://app.example.com")

    assert load().cors_origins == ["http://localhost:5173", "https://app.example.com"]
