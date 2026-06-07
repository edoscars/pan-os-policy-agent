"""Portkey AI gateway: route the Anthropic client through Portkey.

Portkey needs no SDK of its own — per its Anthropic-SDK integration guide you
point the official client at the Portkey base URL and authenticate with the
x-portkey-api-key header. Portkey injects the real Anthropic key from its vault
(so the client's own api_key is unused) and references the model by catalog slug
(@anthropic/<model>, set on AgentContext.model).

The x-portkey-config header selects a Portkey Config whose input/output
guardrails run Prisma AIRS — so AIRS scans every call's prompt before the model
runs, and the response after. AIRS is configured entirely in the Portkey GUI;
this code only names the Config. A guardrail denial comes back as HTTP 446,
which the LLM helper turns into a security halt.
"""

from anthropic import AsyncAnthropic

from pan_os_agent.security.config import SecuredSettings


def build_portkey_anthropic(settings: SecuredSettings) -> AsyncAnthropic:
    return AsyncAnthropic(
        api_key="unused-portkey-injects-the-provider-key",
        base_url=settings.portkey_base_url,
        default_headers={
            "x-portkey-api-key": settings.portkey_api_key.get_secret_value(),
            "x-portkey-config": settings.portkey_config,
        },
    )
