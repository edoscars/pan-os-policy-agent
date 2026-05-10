"""Tests for pan_os_mcp.tools.objects."""

from panos.objects import AddressObject as SdkAddressObject
from pan_os_mcp.tools.objects import list_address_objects, AddressObject
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
