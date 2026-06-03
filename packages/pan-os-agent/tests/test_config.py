"""Tests for pan_os_agent.config."""

from pan_os_agent.config import Settings


def test_settings_reads_anthropic_key(monkeypatch):
    """Settings reads the Anthropic key from the environment as a SecretStr.

    Constructs Settings() directly rather than get_settings() so the
    lru_cache can't leak a cached instance across tests.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")

    settings = Settings()

    assert settings.anthropic_api_key.get_secret_value() == "sk-test-123"
    # SecretStr never leaks the value in its repr.
    assert "sk-test-123" not in repr(settings)
