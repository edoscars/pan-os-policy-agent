"""Tests for pan_os_mcp.tools.network."""

from panos.network import Zone as SdkZone
from pan_os_mcp.tools.network import list_zones, Zone
from types import SimpleNamespace



def test_list_zones_returns_typed_results(monkeypatch):
    """list_zones builds Zone models from SDK objects."""
    
    fake_sdk_zones = [
        # TODO: construct 2-3 SdkZone instances mimicking your real PA-440 zones.
        # Cover variation: at least one with multiple interfaces, one with
        # User-ID enabled, one in tap mode.

        SdkZone(name="internet", mode="layer3", interface=["ethernet1/2"], enable_user_identification=True),
        SdkZone(name="sensor_OT", mode="tap", interface=["ethernet1/3"], enable_device_identification=True),
        SdkZone(name="test123", mode="layer2")
    ]
    

    monkeypatch.setattr(
        "pan_os_mcp.tools.network.get_firewall",
        lambda: SimpleNamespace(client=None),
    )
    monkeypatch.setattr(
        "pan_os_mcp.tools.network.SdkZone.refreshall",
        lambda fw: fake_sdk_zones,
    )
    
    result = list_zones()

    assert len(result) == 3

    assert result[0].name == "internet"
    assert result[0].mode == "layer3"
    assert result[0].interfaces == ["ethernet1/2"]
    assert result[0].enable_user_identification is True
    assert result[0].enable_device_identification is False

    assert result[1].name == "sensor_OT"
    assert result[1].mode == "tap"
    assert result[1].interfaces == ["ethernet1/3"]
    assert result[1].enable_user_identification is False
    assert result[1].enable_device_identification is True

    assert result[2].name == "test123"
    assert result[2].mode == "layer2"
    assert result[2].enable_user_identification is False
    assert result[2].enable_device_identification is False
