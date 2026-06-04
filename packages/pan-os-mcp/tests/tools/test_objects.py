"""Tests for pan_os_mcp.tools.objects."""

from panos.objects import AddressObject as SdkAddressObject
from panos.objects import AddressGroup as SdkAddressGroup
from panos.objects import ServiceObject as SdkServiceObject
from pan_os_mcp.tools.objects import (
    list_address_objects,
    list_address_groups,
    list_services,
    AddressObject,
    AddressGroup,
    Service,
)
from types import SimpleNamespace

def test_list_address_objects_returns_typed_results(monkeypatch):
    """list_address_objects builds AddressObjects models from SDK objects."""
    
    fake_address_objects = [

        SdkAddressObject(name="malicious_ip_197.158.8.97", value="197.158.8.97", type="ip-netmask", description="", tag=[]),
        SdkAddressObject(name="malicious-fqdn", value="www.malicious-domain.com", type="fqdn", description="found in the wild", tag=[]),
        SdkAddressObject(name="test", value="10.0.0.1-10.0.0.4", type="ip-range", description="", tag=['test', 'PrivateIpRange']),
    ]

    monkeypatch.setattr(
        "pan_os_mcp.tools.objects.get_firewall",
        lambda: SimpleNamespace(client=None),
    )
    monkeypatch.setattr(
        "pan_os_mcp.tools.objects.SdkAddressObject.refreshall",
        lambda fw: fake_address_objects,
    )
    
    result = list_address_objects()

    assert isinstance(result, list)
    assert len(result) == 3
    assert all(isinstance(r, AddressObject) for r in result)

    assert result[0].name == "malicious_ip_197.158.8.97"
    assert result[0].value == "197.158.8.97"
    assert result[0].type == "ip-netmask"
    assert result[0].description == ""
    assert result[0].tags == []

    assert result[1].name == "malicious-fqdn"
    assert result[1].value == "www.malicious-domain.com"
    assert result[1].type == "fqdn"
    assert result[1].description == "found in the wild"
    assert result[1].tags == []

    assert result[2].name == "test"
    assert result[2].value == "10.0.0.1-10.0.0.4"
    assert result[2].type == "ip-range"
    assert result[2].description == ""
    assert result[2].tags == ["test", "PrivateIpRange"]


def test_list_address_groups_returns_typed_results(monkeypatch):
    """list_address_groups builds AddressGroup models, handling static and dynamic."""

    fake_groups = [
        SdkAddressGroup(name="finance-hosts", static_value=["host-a", "host-b"]),
        SdkAddressGroup(name="quarantine", dynamic_value="'malware' and 'untrusted'"),
    ]

    monkeypatch.setattr(
        "pan_os_mcp.tools.objects.get_firewall",
        lambda: SimpleNamespace(client=None),
    )
    monkeypatch.setattr(
        "pan_os_mcp.tools.objects.SdkAddressGroup.refreshall",
        lambda fw: fake_groups,
    )

    result = list_address_groups()

    assert all(isinstance(r, AddressGroup) for r in result)

    assert result[0].name == "finance-hosts"
    assert result[0].static_members == ["host-a", "host-b"]
    assert result[0].dynamic_filter == ""

    assert result[1].name == "quarantine"
    assert result[1].static_members == []
    assert result[1].dynamic_filter == "'malware' and 'untrusted'"


def test_list_services_returns_typed_results(monkeypatch):
    """list_services builds Service models from SDK objects."""

    fake_services = [
        SdkServiceObject(name="tcp-8443", protocol="tcp", destination_port="8443"),
        SdkServiceObject(name="syslog-udp", protocol="udp", destination_port="514",
                         description="syslog", tag=["logging"]),
    ]

    monkeypatch.setattr(
        "pan_os_mcp.tools.objects.get_firewall",
        lambda: SimpleNamespace(client=None),
    )
    monkeypatch.setattr(
        "pan_os_mcp.tools.objects.SdkServiceObject.refreshall",
        lambda fw: fake_services,
    )

    result = list_services()

    assert all(isinstance(r, Service) for r in result)

    assert result[0].name == "tcp-8443"
    assert result[0].protocol == "tcp"
    assert result[0].destination_port == "8443"
    assert result[0].tags == []

    assert result[1].name == "syslog-udp"
    assert result[1].protocol == "udp"
    assert result[1].destination_port == "514"
    assert result[1].description == "syslog"
    assert result[1].tags == ["logging"]
