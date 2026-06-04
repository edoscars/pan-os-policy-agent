"""Security-policy tools."""

from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP
from panos.policies import Rulebase, SecurityRule as SdkSecurityRule

from pan_os_mcp.panos import get_firewall


class SecurityRule(BaseModel):
    """A Security policy rule, in evaluation order.

    PAN-OS evaluates rules top-down, first match wins, so position in the
    returned list is significant. List fields default to ["any"] on the
    firewall when unset; this surfaces them as-is for match reasoning.
    """
    name: str
    from_zones: list[str] = []
    to_zones: list[str] = []
    sources: list[str] = []
    destinations: list[str] = []
    source_users: list[str] = []
    applications: list[str] = []
    services: list[str] = []
    action: str = ""
    description: str = ""
    disabled: bool = False
    tags: list[str] = []


def _as_list(value) -> list[str]:
    """Normalize a pan-os-python member field to a list.

    pan-os-python collapses single-member fields to a bare string (so a rule
    with one service yields 'application-default', not ['application-default']).
    Coerce str -> [str], None -> [], list -> list.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def list_security_rules() -> list[SecurityRule]:
    """
    Return all Security policy rules in evaluation (top-down) order.

    Security rules are matched first-to-last, first match wins, so the order
    of this list is significant for redundancy and shadowing analysis. Each
    rule reports its zones, source/destination, user, application, service,
    and action. Use this tool to check whether an existing rule already
    covers a proposed intent, or whether a broader earlier rule would shadow
    a proposed rule.
    """
    fw = get_firewall()
    rulebase = Rulebase()
    fw.client.add(rulebase)
    sdk_rules = SdkSecurityRule.refreshall(rulebase)

    return [
        SecurityRule(
            name=rule.name,
            from_zones=_as_list(rule.fromzone),
            to_zones=_as_list(rule.tozone),
            sources=_as_list(rule.source),
            destinations=_as_list(rule.destination),
            source_users=_as_list(rule.source_user),
            applications=_as_list(rule.application),
            services=_as_list(rule.service),
            action=rule.action or "",
            description=rule.description or "",
            disabled=bool(rule.disabled),
            tags=_as_list(rule.tag),
        )
        for rule in sdk_rules
    ]


def register(mcp: FastMCP) -> None:
    mcp.tool()(list_security_rules)
