# pan-os-mcp

A [FastMCP](https://github.com/jlowin/fastmcp) server exposing **read-only**
PAN-OS firewall operations as MCP tools, backed by
[pan-os-python](https://github.com/PaloAltoNetworks/pan-os-python). It is the
firewall boundary for [`pan-os-agent`](../pan-os-agent): the agent talks to it as
an MCP client and only ever sees typed results, never the SDK.

## Tools

| Tool | Returns |
|---|---|
| `get_system_info` | hostname, model, serial, sw version, uptime, mode |
| `list_zones` | zones with mode, interfaces, User-ID / Device-ID flags |
| `list_address_objects` | address objects (name, value, type, tags) |
| `list_address_groups` | address groups (static members / dynamic filter) |
| `list_services` | service objects (protocol, ports) |
| `list_security_rules` | Security rulebase in evaluation order |

Every tool is a read: `refreshall` / `op("show …")`. There is no create, set, or
commit path — the agent's "never writes to the firewall" guarantee is enforced
here by construction.

## Run

```bash
# stdio (how the agent spawns it) — reads PANOS_* from the environment
uv run --env-file .env pan-os-mcp

# or over streamable-HTTP (e.g. behind the Portkey MCP gateway)
PAN_OS_MCP_TRANSPORT=streamable-http uv run --env-file .env pan-os-mcp
```

Config (`PANOS_HOST`, `PANOS_API_KEY` as `SecretStr`, `PANOS_VSYS`) comes from
the environment via pydantic-settings. Tests run offline against captured XML
fixtures and `refreshall` monkeypatching (`uv run pytest`).
