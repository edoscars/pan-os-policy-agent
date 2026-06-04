# pan-os-policy-agent

A guided security-policy authoring agent for Palo Alto Networks PAN-OS
firewalls. It turns a natural-language policy intent — *"finance group
needs access to Salesforce"* — into a proposed Security rule, after running
it through a four-stage validation gauntlet against the **live firewall** and
**PAN-OS documentation**.

v1 has a deliberate fake approval gate: the agent proposes and explains, but
**never commits**. (v2, planned, adds commit capability protected by Prisma
AIRS.)

```
intent text ──▶ [1] intent validation ──▶ [2] prerequisite check ──▶
                [3] redundancy check  ──▶ [4] proposal + shadowing ──▶ proposed rule
                         (halts early if the intent is incoherent or already satisfied)
```

## The four-stage gauntlet

1. **Intent validation** — parse the request into structured PAN-OS terms
   (zones, source/destination, user, application, service, action) and judge
   coherence. Halts if it isn't an access-control request.
2. **Prerequisite check** — gather firewall inventory over MCP (zones, address
   objects/groups, services) and retrieve relevant docs via RAG, then flag
   missing objects and missing configuration prerequisites (e.g. User-ID for
   group-based rules), each grounded in retrieved documentation.
3. **Redundancy check** — read the rulebase in evaluation order and judge
   whether an existing rule already satisfies the intent. Halts if so.
4. **Proposal + shadowing** — generate the proposed rule (filling
   `any`/`application-default` defaults) and check whether an earlier broader
   rule would shadow it. Output is formatted for the fake approval gate.

Every run produces an append-only, JSON-serializable trace of all four stages.

## Packages

A `uv` workspace with three library packages (`pan-os-*` PyPI names,
`pan_os_*` import names):

- **`pan-os-mcp`** — a FastMCP server exposing read-only tools over the
  firewall (`get_system_info`, `list_zones`, `list_address_objects`,
  `list_address_groups`, `list_services`, `list_security_rules`). Each tool is
  a narrow typed operation; tests run offline via captured XML fixtures or
  `refreshall` monkeypatching.
- **`pan-os-rag`** — retrieval over PAN-OS 11.1 TechDocs (Policy + Policy
  Objects + User-ID). Voyage embeddings + LanceDB with a rerank pass; a
  hand-labeled eval set measures retrieval quality (recall@5).
- **`pan-os-agent`** — the agent. A real MCP **client** (spawns the server
  over stdio), a hand-rolled async state machine, the four stages, and a
  single-shot CLI driver.

## Running it

All scripts run from the repo root with credentials injected at runtime:

```bash
# one intent
uv run --env-file .env python packages/pan-os-agent/scripts/run_agent.py \
    "finance group needs access to Salesforce"

# a fixtures file, dumping JSON traces to ./traces
uv run --env-file .env python packages/pan-os-agent/scripts/run_agent.py \
    --fixtures packages/pan-os-agent/fixtures/intents.txt --out traces

# end-task grounding eval (agent outcomes vs labeled expectations)
uv run --env-file .env python packages/pan-os-agent/scripts/run_grounding_eval.py
```

`.env` holds `PANOS_HOST`, `PANOS_API_KEY`, `VOYAGE_API_KEY`, and
`ANTHROPIC_API_KEY` (see `.env.example`).

## Testing

```bash
uv run pytest
```

Tests are offline and deterministic: the firewall, RAG retriever, and Anthropic
client are all faked (fixture replay / monkeypatch / injected fakes). The
LLM-driven stages are additionally validated live against a PA-440.

## Evaluation

Two layers:

- **Retrieval** (`pan-os-rag/eval`) — recall@5 over 30 hand-labeled questions.
- **End-task grounding** (`pan-os-agent/eval`) — runs the full gauntlet over
  labeled intents and scores the *product*: outcome (proposal vs halt),
  proposed-rule fields, and flagged prerequisites/shadowing. This is an
  end-task eval, not a retrieval proxy (8/8 labeled cases passing).

See [docs/architecture.md](docs/architecture.md) for design rationale (why MCP,
why RAG, why a hand-rolled state machine, the v1/v2 split).
