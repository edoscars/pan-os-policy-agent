"""Portkey AI gateway: route the Anthropic client through Portkey.

Portkey needs no SDK of its own — per its Anthropic-SDK integration guide you
point the official client at the Portkey base URL and authenticate with the
x-portkey-api-key header. Portkey injects the real Anthropic key from its vault
(so the client's own api_key is unused) and references the model by catalog slug
(@anthropic/<model>, set on AgentContext.model). This gives the secured product
LLM observability, guardrails, and caching with zero change to the stages.
"""

from anthropic import AsyncAnthropic

from pan_os_agent.security.config import SecuredSettings


def build_portkey_anthropic(settings: SecuredSettings) -> AsyncAnthropic:
    return AsyncAnthropic(
        api_key="unused-portkey-injects-the-provider-key",
        base_url=settings.portkey_base_url,
        default_headers={"x-portkey-api-key": settings.portkey_api_key.get_secret_value()},
    )
