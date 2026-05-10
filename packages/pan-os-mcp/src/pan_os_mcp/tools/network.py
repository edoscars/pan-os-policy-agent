from pydantic import BaseModel
from pan_os_mcp.panos import get_firewall
from panos.network import Zone as SdkZone
from mcp.server.fastmcp import FastMCP

class Zone(BaseModel):
    """A security zone on the firewall."""
    name: str
    mode: str                                # tap | layer3 | layer2 | virtual-wire | external
    interfaces: list[str] = []               # interface names attached to this zone
    enable_user_identification: bool = False
    enable_device_identification: bool = False


def list_zones() -> list[Zone]:
    """
    Return all security zones configured on the firewall. 
    Each zone include its mode (L2/L3/TAP/vWire), its attached interfaces,
    whether User-ID or Device-ID is enabled.
    """

    fw = get_firewall()
    sdk_zones = SdkZone.refreshall(fw.client)

    return [
        Zone(
            name=z.name,
            mode=z.mode,
            interfaces=z.interface or [],
            enable_device_identification=bool(z.enable_device_identification),
            enable_user_identification=bool(z.enable_user_identification)
        )
        for z in sdk_zones
    ]

def register(mcp: FastMCP) -> None:
    mcp.tool()(list_zones)
