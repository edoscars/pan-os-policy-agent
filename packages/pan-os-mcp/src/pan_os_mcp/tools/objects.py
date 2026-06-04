from pydantic import BaseModel
from pan_os_mcp.panos import get_firewall
from mcp.server.fastmcp import FastMCP
from panos.objects import AddressObject as SdkAddressObject
from panos.objects import AddressGroup as SdkAddressGroup
from panos.objects import ServiceObject as SdkServiceObject

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

class AddressGroup(BaseModel):
    """An Address Group of the firewall.

    Either static (an explicit list of member address-object names) or
    dynamic (a tag-match filter expression), never both.
    """
    name: str
    static_members: list[str] = []
    dynamic_filter: str = ""
    description: str = ""
    tags: list[str] = []

def list_address_groups() -> list[AddressGroup]:
    """
    Return all Address Groups present in the firewall.

    Address groups bundle address objects under one name for reuse in
    security rules. A static group lists member object names; a dynamic
    group matches members by a tag filter. Use this tool when a policy
    references an address by a name that isn't a plain address object,
    to confirm the group exists and see what it resolves to.
    """

    fw = get_firewall()
    sdk_groups = SdkAddressGroup.refreshall(fw.client)

    return [
        AddressGroup(
            name=group.name,
            static_members=group.static_value or [],
            dynamic_filter=group.dynamic_value or "",
            description=group.description or "",
            tags=group.tag or []
        )
        for group in sdk_groups
    ]

class Service(BaseModel):
    """A Service object of the firewall.

    Defines a protocol (tcp/udp) and destination/source port(s) that
    security rules match on instead of the application-default ports.
    """
    name: str
    protocol: str               # tcp | udp
    destination_port: str = ""
    source_port: str = ""
    description: str = ""
    tags: list[str] = []

def list_services() -> list[Service]:
    """
    Return all custom Service objects present in the firewall.

    Services name a protocol and port (e.g. tcp/443) that a security
    rule can match on. Use this tool when a policy references a service
    by name, to verify it exists and inspect its protocol/port before
    proposing a rule that uses it. Note the built-in application-default
    and any/predefined services are not returned here.
    """

    fw = get_firewall()
    sdk_services = SdkServiceObject.refreshall(fw.client)

    return [
        Service(
            name=service.name,
            protocol=service.protocol,
            destination_port=service.destination_port or "",
            source_port=service.source_port or "",
            description=service.description or "",
            tags=service.tag or []
        )
        for service in sdk_services
    ]

def register(mcp: FastMCP) -> None:
    mcp.tool()(list_address_objects)
    mcp.tool()(list_address_groups)
    mcp.tool()(list_services)
