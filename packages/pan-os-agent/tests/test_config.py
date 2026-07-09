"""Tests for pan_os_agent.llm_client settings and client construction."""

import pytest

from pan_os_agent.llm_client import LLMSettings, PortkeyMode, build_llm_client

# The Anthropic SDK reads ANTHROPIC_* env vars (base URL, custom headers) at
# client construction. A dev shell may have those set (e.g. its own gateway
# routing), which would leak into the client and mask what our code builds.
# Clear them so these tests assert our construction logic in isolation.
_SDK_ENV_VARS = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_API_KEY",
    "PORTKEY_API_KEY",
    "PORTKEY_CONFIG",
)


@pytest.fixture(autouse=True)
def _isolate_sdk_env(monkeypatch):
    for var in _SDK_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_settings_reads_anthropic_key_as_secret(monkeypatch):
    """Settings reads the Anthropic key from the environment as a SecretStr.

    Constructs LLMSettings() directly rather than get_llm_settings() so the
    lru_cache can't leak a cached instance across tests.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")

    settings = LLMSettings()

    assert settings.anthropic_api_key.get_secret_value() == "sk-test-123"
    # SecretStr never leaks the value in its repr.
    assert "sk-test-123" not in repr(settings)


def test_defaults_to_off_mode(monkeypatch):
    monkeypatch.delenv("PORTKEY_MODE", raising=False)
    assert LLMSettings().portkey_mode is PortkeyMode.OFF


def test_call_model_switches_to_slug_only_for_cloud():
    direct = LLMSettings(portkey_mode="off", model="claude-opus-4-8")
    cloud = LLMSettings(
        portkey_mode="cloud", portkey_model="@anthropic/claude-opus-4-8"
    )
    assert direct.call_model == "claude-opus-4-8"
    assert cloud.call_model == "@anthropic/claude-opus-4-8"


def test_off_mode_requires_anthropic_key():
    settings = LLMSettings(portkey_mode="off", anthropic_api_key=None)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_llm_client(settings)


def test_off_mode_builds_direct_client():
    settings = LLMSettings(portkey_mode="off", anthropic_api_key="sk-test")
    client = build_llm_client(settings)
    # A direct client attaches no Portkey routing/guardrail headers.
    assert not any(h.startswith("x-portkey-") for h in client.default_headers)


def test_cloud_mode_points_at_portkey_with_config_header():
    settings = LLMSettings(
        portkey_mode="cloud",
        portkey_api_key="pk-test",
        portkey_config="pc-123",
    )
    client = build_llm_client(settings)
    assert "api.portkey.ai" in str(client.base_url)
    headers = client.default_headers
    assert headers["x-portkey-api-key"] == "pk-test"
    assert headers["x-portkey-config"] == "pc-123"


def test_self_hosted_mode_uses_local_gateway_and_provider_header():
    settings = LLMSettings(
        portkey_mode="self_hosted",
        anthropic_api_key="sk-test",
        portkey_self_hosted_url="http://localhost:8787/v1",
    )
    client = build_llm_client(settings)
    assert "localhost:8787" in str(client.base_url)
    assert client.default_headers["x-portkey-provider"] == "anthropic"
