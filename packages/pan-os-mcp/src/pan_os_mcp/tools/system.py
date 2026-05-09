"""System-info tools."""

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from pan_os_mcp.panos import get_firewall

class SystemInfo(BaseModel):
    """Subset of `show system info` output exposed to the agent."""
    hostname: str
    model: str
    serial: str
    sw_version: str 
    uptime: str
    multi_vsys : str
    operational_mode : str

def get_system_info() -> SystemInfo:
    """Return identifying information about the firewall.

    Includes hostname, model, serial number, software version, and
    uptime. Use this to verify which device is being inspected and
    which PAN-OS version is running.
    """
    fw = get_firewall()
    element = fw.client.op("show system info", xml=False)

    system = element.find("./result/system")
    if system is None:
        raise RuntimeError("Unexpected response shape from 'show system info': can't find ./result/system")
    
    raw_data = {
        "hostname" : system.findtext("hostname"),
        "model" : system.findtext("model"),
        "serial" : system.findtext("serial"),
        "sw_version" : system.findtext("sw-version"),
        "uptime" : system.findtext("uptime"),
        "operational_mode" : system.findtext("operational-mode"),
        "multi_vsys" : system.findtext("multi-vsys")
    }

    return SystemInfo(**raw_data)

def register(mcp: FastMCP) -> None:
    mcp.tool()(get_system_info)
