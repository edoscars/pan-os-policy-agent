"""Tests for pan_os_mcp.tools.policies."""

from types import SimpleNamespace

from panos.policies import SecurityRule as SdkSecurityRule
from pan_os_mcp.tools.policies import list_security_rules, SecurityRule


def test_list_security_rules_returns_ordered_typed_results(monkeypatch):
    """list_security_rules builds SecurityRule models, preserving rule order."""

    fake_rules = [
        SdkSecurityRule(
            name="allow-finance-salesforce",
            fromzone=["trust"], tozone=["untrust"],
            source=["any"], destination=["any"],
            source_user=["finance"], application=["salesforce"],
            service=["application-default"], action="allow",
        ),
        SdkSecurityRule(
            name="deny-all", fromzone=["any"], tozone=["any"],
            action="deny", disabled=True, tag=["cleanup"],
        ),
    ]

    # Security rules refresh against a Rulebase added to the firewall; the fake
    # client just needs a no-op add(), and refreshall is replaced with fakes.
    monkeypatch.setattr(
        "pan_os_mcp.tools.policies.get_firewall",
        lambda: SimpleNamespace(client=SimpleNamespace(add=lambda child: None)),
    )
    monkeypatch.setattr(
        "pan_os_mcp.tools.policies.SdkSecurityRule.refreshall",
        lambda rulebase: fake_rules,
    )

    result = list_security_rules()

    assert all(isinstance(r, SecurityRule) for r in result)
    # Order preserved — significant for first-match policy evaluation.
    assert [r.name for r in result] == ["allow-finance-salesforce", "deny-all"]

    rule = result[0]
    assert rule.from_zones == ["trust"]
    assert rule.to_zones == ["untrust"]
    assert rule.source_users == ["finance"]
    assert rule.applications == ["salesforce"]
    assert rule.services == ["application-default"]
    assert rule.action == "allow"
    assert rule.disabled is False

    assert result[1].action == "deny"
    assert result[1].disabled is True
    assert result[1].tags == ["cleanup"]
    # The SDK defaults an unspecified source to ["any"]; a single member is
    # normalized from the SDK's bare string back into a list.
    assert result[1].sources == ["any"]
