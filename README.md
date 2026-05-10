# pan-os-policy-agent

A guided security policy authoring agent for PAN-OS firewalls.
Translates natural-language policy intents ("finance group needs
access to Salesforce") into proposed Security rules, after
validating intent, prerequisite firewall features, and rulebase
redundancy.

## Architecture

Three components:

- **`pan-os-mcp`** — MCP server exposing read-only tools over the
  PAN-OS firewall (system info, zones, address objects, security
  rules, etc.). Each tool is a narrow, semantically meaningful
  operation; tests use captured fixtures so they run offline.
- **`panos-rag`** _(in progress)_ — Retrieval over PAN-OS
  TechDocs (admin guide, API references, best-practice docs),
  pinned to PAN-OS 11.2. Voyage embeddings + LanceDB, with a
  reranker pass. Hand-built eval set measures retrieval quality
  before agent work begins.
- **`policy-agent`** _(planned)_ — Four-stage state machine:
  intent validation, prerequisite check, redundancy check,
  proposal + shadowing analysis. Each stage produces structured
  output; runs are JSON-traceable end-to-end.

A grounding-quality eval harness measures whether the agent's
claims are supported by retrieved evidence and live firewall state.

## Deferred MCP tools

The following tools are planned but not yet implemented:

- list_address_groups
- list_services
- list_applications
- list_security_rules
- get_rule_by_name
- dry_run_rule_match
- get_user_id_status
- get_device_id_status
- get_decryption_status

Each follows the pattern established in tools 1-3:
schema, function, register, test.
