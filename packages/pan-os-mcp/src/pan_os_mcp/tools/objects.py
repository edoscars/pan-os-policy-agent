from pydantic import BaseModel
from pan_os_mcp.panos import get_firewall
from mcp.server.fastmcp import FastMCP
from panos.objects import AddressObject as SdkAddressObject

class AddressObject(BaseModel):
    """An Address Object of the firewall.
   
    """
    name: str
    value: str                                
    type: str               # ip-netmask (default), ip-range, ip-wildcard, fqdn
    description: str = ""
    tags: list[str] = []

def list_address_objects() -> list[AddressObject]:
    """
    Return all Address Objects present in the firewall

    Address objects are reusable IP/FQDN definitions referenced by
    name in security rules, NAT rules, and address groups. Each one
    has a type (ip-netmask, ip-range, ip-wildcard, or fqdn) and a
    value matching that type. Use this tool when policy proposals
    reference an address by name, to verify the object exists and
    inspect its definition. 
    
    """

    fw = get_firewall()
    sdk_addresses = SdkAddressObject.refreshall(fw.client)

    return [
        AddressObject(
            name=address.name,
            value=address.value,
            type=address.type,
            description=address.description or "",
            tags=address.tag or []
        )
        for address in sdk_addresses
    ]

def register(mcp: FastMCP) -> None:
    mcp.tool()(list_address_objects)
