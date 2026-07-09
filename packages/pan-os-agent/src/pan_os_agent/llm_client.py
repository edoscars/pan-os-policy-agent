"""The one place LLM (and MCP) clients are constructed.

Nothing else in the agent builds an Anthropic client directly — every entrypoint
(CLI, Streamlit UI) goes through `build_llm_client` so the routing decision lives
in exactly one place. Three modes, selected by `PORTKEY_MODE`:

  off          direct Anthropic — the default, no gateway, no scanning.
  self_hosted  route through a local OSS Portkey gateway (Docker, Apache 2.0),
               default http://localhost:8787/v1.
  cloud        route through Portkey Cloud (https://api.portkey.ai).

Both Portkey modes keep using the Anthropic SDK (so stages still get
`messages.parse` structured outputs) — we only repoint `base_url` and add the
`x-portkey-*` headers, per Portkey's Anthropic-SDK integration guide.

Prisma AIRS is *not* an SDK dependency here. It runs as an input/output guardrail
inside the Portkey Config named by `PORTKEY_CONFIG`; a denial comes back as HTTP
446, which `llm.complete_structured` turns into a security halt. So AIRS is only
active on a Portkey path (`self_hosted`/`cloud`) whose Config carries the
guardrail — in `off` mode there is no scanning, by design.

Settings come from the environment (`.env`) by default, but every field can be
overridden live — the Streamlit UI builds an `LLMSettings(**overrides)` from
in-session key entry so a Sales Engineer never edits a file mid-demo.
"""

from enum import Enum
from functools import lru_cache

from anthropic import AsyncAnthropic
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from pan_os_agent.mcp_client import McpClient


class PortkeyMode(str, Enum):
    OFF = "off"
    SELF_HOSTED = "self_hosted"
    CLOUD = "cloud"


class LLMSettings(BaseSettings):
    """Everything needed to construct the LLM client, from env or explicit kwargs.

    All secrets are SecretStr and unwrapped only at the SDK call site below. All
    Portkey fields are optional so the default (`off`) product needs nothing but
    an Anthropic key.
    """

    # Direct Anthropic (used in `off` mode, and as the provider key forwarded by a
    # self-hosted gateway that has no vault of its own).
    anthropic_api_key: SecretStr | None = None
    # Anthropic model id used when talking to Anthropic directly or via a
    # self-hosted gateway that forwards the raw provider model id.
    model: str = "claude-opus-4-8"

    portkey_mode: PortkeyMode = PortkeyMode.OFF
    portkey_api_key: SecretStr | None = None
    # Portkey Config ID (pc-***) whose input/output guardrails run Prisma AIRS.
    portkey_config: str = ""
    # Portkey Cloud references models by catalog slug: @<provider>/<model>.
    portkey_model: str = "@anthropic/claude-opus-4-8"
    # Optional Portkey Cloud virtual key (vault-backed provider credential).
    portkey_virtual_key: SecretStr | None = None
    # Base URL of a self-hosted OSS Portkey gateway.
    portkey_self_hosted_url: str = "http://localhost:8787/v1"
    # Optional: route MCP tool calls through the Portkey MCP gateway when set.
    portkey_mcp_url: str = ""

    model_config = SettingsConfigDict(env_file_encoding="utf-8", frozen=True)

    @property
    def call_model(self) -> str:
        """The model id to send on each call, per mode.

        Portkey Cloud wants the catalog slug (@anthropic/...); direct Anthropic and
        a self-hosted gateway forwarding the raw provider id want the plain model.
        """
        return self.portkey_model if self.portkey_mode is PortkeyMode.CLOUD else self.model


@lru_cache(maxsize=1)
def get_llm_settings() -> LLMSettings:
    return LLMSettings()


def _portkey_headers(settings: LLMSettings, *, provider: bool) -> dict[str, str]:
    """Common x-portkey-* headers. `provider` adds the raw-provider hint used when
    Portkey has no vault-backed credential of its own (self-hosted / no virtual key)."""
    headers: dict[str, str] = {}
    if settings.portkey_api_key is not None:
        headers["x-portkey-api-key"] = settings.portkey_api_key.get_secret_value()
    if settings.portkey_config:
        headers["x-portkey-config"] = settings.portkey_config
    if settings.portkey_virtual_key is not None:
        headers["x-portkey-virtual-key"] = settings.portkey_virtual_key.get_secret_value()
    if provider:
        headers["x-portkey-provider"] = "anthropic"
    return headers


def build_llm_client(settings: LLMSettings | None = None) -> AsyncAnthropic:
    """Construct the AsyncAnthropic client for the configured mode.

    `off` returns a direct client; `self_hosted`/`cloud` return a client pointed at
    the Portkey gateway with the x-portkey-* headers that attach the AIRS-carrying
    Config. The returned client is still a normal AsyncAnthropic, so every stage's
    `messages.parse` call is unchanged.
    """
    settings = settings or get_llm_settings()

    if settings.portkey_mode is PortkeyMode.OFF:
        return AsyncAnthropic(api_key=_anthropic_key(settings))

    if settings.portkey_mode is PortkeyMode.SELF_HOSTED:
        # No Portkey vault locally: forward the real Anthropic key as the provider
        # credential and tell the gateway which provider it is.
        return AsyncAnthropic(
            api_key=_anthropic_key(settings),
            base_url=settings.portkey_self_hosted_url,
            default_headers=_portkey_headers(settings, provider=True),
        )

    # CLOUD: Portkey injects the provider key from its vault (via virtual key /
    # Config), so the client's own api_key is unused unless we're forwarding one.
    return AsyncAnthropic(
        api_key=_anthropic_key(settings, allow_placeholder=True),
        base_url="https://api.portkey.ai",
        default_headers=_portkey_headers(settings, provider=settings.portkey_virtual_key is None),
    )


def _anthropic_key(settings: LLMSettings, *, allow_placeholder: bool = False) -> str:
    if settings.anthropic_api_key is not None:
        return settings.anthropic_api_key.get_secret_value()
    if allow_placeholder:
        # Portkey Cloud with a virtual key injects the provider key itself.
        return "unused-portkey-injects-the-provider-key"
    raise ValueError(
        "ANTHROPIC_API_KEY is required for this mode (direct Anthropic or a "
        "self-hosted gateway that forwards the provider key)."
    )


def build_mcp_client(settings: LLMSettings | None = None) -> McpClient:
    """MCP client for the configured mode.

    If a Portkey MCP gateway URL is set, route firewall tool calls through it
    (logged/governed by Portkey); otherwise spawn the local stdio server.
    """
    settings = settings or get_llm_settings()
    if settings.portkey_mcp_url and settings.portkey_api_key is not None:
        return McpClient(
            url=settings.portkey_mcp_url,
            headers={"x-portkey-api-key": settings.portkey_api_key.get_secret_value()},
        )
    return McpClient()
