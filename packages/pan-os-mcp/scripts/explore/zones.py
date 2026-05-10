"""
    Script for exploring SDK

    This is used for panos.network.Zone

"""

from panos.network import Zone
from pan_os_mcp.panos import get_firewall

if __name__ == "__main__":
    import xml.etree.ElementTree as ET

    fw = get_firewall()
    zones = Zone.refreshall(fw.client)

    for zone in zones:
        print(zone.name)
        print(zone.enable_device_identification) # either True or None
        print(zone.interface)

    xpath = "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/zone"
    fw.client.xapi.get(xpath=xpath)
    
    # The result is in fw.client.xapi.xml_result() — the raw XML string
    print(fw.client.xapi.xml_result())
