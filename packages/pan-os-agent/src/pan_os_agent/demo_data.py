"""Demo mode: a canned firewall so the gauntlet runs with no live PA-440.

`DemoMcpClient` is a drop-in for `McpClient` (same async-context + `call_tool`
surface) that returns a small but realistic inventory and rulebase. It is *not*
a test fixture — it ships in the product so a Sales Engineer can run the full
gauntlet on a laptop with no firewall in the room.

The data is chosen so the checks visibly do something on the demo intents:
  - Zones trust/untrust/dmz exist; trust has User-ID on, dmz does not.
  - Some address objects/groups/services exist and some the demo intents will
    reference do NOT (e.g. no `database-server` object) — so the prerequisite
    stage produces real satisfied/unsatisfied findings.
  - The rulebase has a broad "allow-all-outbound" alert rule near the bottom and
    a couple of specific rules, so redundancy and shadowing have something real
    to catch (e.g. a web-browsing trust->untrust request is already covered).
"""

from typing import Any

from pan_os_rag.chunk import Chunk

# --- Inventory (shapes match the pan-os-mcp list tools: {"result": [ {...} ]}) ---

_ZONES = [
    {"name": "trust", "mode": "layer3", "interfaces": ["ethernet1/2"],
     "enable_user_identification": True, "enable_device_identification": False},
    {"name": "untrust", "mode": "layer3", "interfaces": ["ethernet1/1"],
     "enable_user_identification": False, "enable_device_identification": False},
    {"name": "dmz", "mode": "layer3", "interfaces": ["ethernet1/3"],
     "enable_user_identification": False, "enable_device_identification": False},
]

_ADDRESS_OBJECTS = [
    {"name": "web-server-1", "value": "10.1.20.10", "type": "ip-netmask",
     "description": "public web server", "tags": ["dmz"]},
    {"name": "internal-dns", "value": "10.1.1.53", "type": "ip-netmask",
     "description": "", "tags": []},
]

_ADDRESS_GROUPS = [
    {"name": "dmz-servers", "static_members": ["web-server-1"],
     "dynamic_filter": "", "description": "all DMZ hosts", "tags": ["dmz"]},
]

_SERVICES = [
    {"name": "service-https", "protocol": "tcp", "destination_port": "443",
     "source_port": "", "description": "", "tags": []},
    {"name": "service-mysql", "protocol": "tcp", "destination_port": "3306",
     "source_port": "", "description": "MySQL", "tags": []},
]

# --- Security rulebase, in evaluation order (top-down, first match wins) ---

_SECURITY_RULES = [
    {"name": "block-known-bad", "from_zones": ["any"], "to_zones": ["any"],
     "sources": ["any"], "destinations": ["any"], "source_users": ["any"],
     "applications": ["any"], "services": ["any"], "action": "deny",
     "disabled": False, "tags": ["threat"]},
    {"name": "dmz-inbound-web", "from_zones": ["untrust"], "to_zones": ["dmz"],
     "sources": ["any"], "destinations": ["web-server-1"], "source_users": ["any"],
     "applications": ["web-browsing", "ssl"], "services": ["application-default"],
     "action": "allow", "disabled": False, "tags": []},
    {"name": "allow-all-outbound", "from_zones": ["trust"], "to_zones": ["untrust"],
     "sources": ["any"], "destinations": ["any"], "source_users": ["any"],
     "applications": ["any"], "services": ["application-default"],
     "action": "allow", "disabled": False, "tags": ["broad"]},
]

_TOOL_RESULTS: dict[str, Any] = {
    "list_zones": {"result": _ZONES},
    "list_address_objects": {"result": _ADDRESS_OBJECTS},
    "list_address_groups": {"result": _ADDRESS_GROUPS},
    "list_services": {"result": _SERVICES},
    "list_security_rules": {"result": _SECURITY_RULES},
    "get_system_info": {
        "hostname": "demo-pa-440", "model": "PA-440", "serial": "0123456789",
        "sw_version": "11.1.4-h7", "uptime": "12 days, 3:14:07",
        "multi_vsys": False, "operational_mode": "normal",
    },
}


# --- Canned RAG retriever, so demo mode needs no Voyage key or built corpus ---

_DEMO_CHUNKS = [
    Chunk(
        text=(
            "To match traffic by username or user group in a Security policy rule, "
            "User-ID must be enabled on the source zone. Without User-ID, the "
            "source-user field cannot be evaluated and the rule matches all users."
        ),
        source_url="https://docs.paloaltonetworks.com/pan-os/security-policy/user-id",
        page_title="User-ID and Security Policy",
        heading_path=["Policy", "User-ID"],
        position=0,
    ),
    Chunk(
        text=(
            "A Security policy rule references address objects, address groups, and "
            "service objects by name. Any object named in a rule must already exist "
            "in the configuration; PAN-OS does not create objects implicitly."
        ),
        source_url="https://docs.paloaltonetworks.com/pan-os/objects/address-objects",
        page_title="Address and Service Objects",
        heading_path=["Objects", "Address Objects"],
        position=0,
    ),
    Chunk(
        text=(
            "Security rules are evaluated top-down, first match wins. A broad rule "
            "placed above a more specific one will shadow it: the specific rule is "
            "never evaluated because the broad rule already matched the traffic."
        ),
        source_url="https://docs.paloaltonetworks.com/pan-os/security-policy/rule-order",
        page_title="Security Policy Rule Order",
        heading_path=["Policy", "Rule Evaluation"],
        position=0,
    ),
    Chunk(
        text=(
            "application-default restricts an application to its standard ports. Use "
            "it instead of naming a service object when the intent is to allow an "
            "App-ID on the ports Palo Alto Networks defines for it."
        ),
        source_url="https://docs.paloaltonetworks.com/pan-os/app-id/application-default",
        page_title="Application Default Services",
        heading_path=["App-ID", "application-default"],
        position=0,
    ),
    Chunk(
        text=(
            "Custom TCP/UDP applications and non-standard ports require a service "
            "object specifying the protocol and destination port. Create the service "
            "object before referencing it in a rule."
        ),
        source_url="https://docs.paloaltonetworks.com/pan-os/objects/service-objects",
        page_title="Service Objects",
        heading_path=["Objects", "Service Objects"],
        position=0,
    ),
]


def demo_retriever(query: str, k: int = 5) -> list[Chunk]:
    """Canned retriever matching pan_os_rag.retrieve's (query, k) -> [Chunk].

    Returns a fixed, plausible set of PAN-OS doc chunks so the prerequisite stage
    is grounded in demo mode without a Voyage key or a built vector store.
    """
    return _DEMO_CHUNKS[:k]


class DemoMcpClient:
    """Drop-in replacement for McpClient backed by canned data (no firewall)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []

    async def __aenter__(self) -> "DemoMcpClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def call_tool(self, name: str, arguments: dict | None = None) -> Any:
        self.calls.append((name, arguments))
        if name not in _TOOL_RESULTS:
            raise KeyError(f"demo firewall has no canned result for tool {name!r}")
        return _TOOL_RESULTS[name]
