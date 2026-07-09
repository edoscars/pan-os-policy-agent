# Architecture & design rationale

This document explains *why* the project is shaped the way it is. For *what* it
does and how to run it, see the [README](../README.md).

## System shape

```
                    ┌─────────────────────────── pan-os-agent ───────────────────────────┐
                    │                                                                     │
   intent text ───▶ │  run_agent(_streamed) loop                                          │
                    │    for stage in STAGES:  state = await stage(state, ctx)            │
                    │                          if state.halted: break                     │
                    │                                                                     │
                    │   AgentContext (DI) ── mcp ──▶ McpClient ──(stdio)───────────────┐  │
                    │                    │            (or DemoMcpClient in demo mode)   │  │
                    │                    ├─ retriever ──▶ pan-os-rag.retrieve           │  │
                    │                    │            (or demo_retriever in demo mode)  │  │
                    │                    └─ anthropic ──▶ build_llm_client(PORTKEY_MODE)─┼──┼─▶ Anthropic
                    └────────────────────────────────────────────────────────────────┼──┘   (direct, or via
                                                                                       │      Portkey + AIRS)
                                          ┌────────────────────────────────────────────▼─┐
                                          │ pan-os-mcp server (FastMCP over stdio)         │
                                          │   tools/*.py  ──▶  pan-os-python  ──▶ PA-440   │
                                          └────────────────────────────────────────────────┘
```

`llm_client.py` is the single seam for both the LLM client (direct vs. Portkey,
by `PORTKEY_MODE`) and the MCP client (stdio vs. Portkey MCP gateway). Demo mode
swaps in `DemoMcpClient` + `demo_retriever` — canned firewall inventory and doc
chunks — so the gauntlet runs with no PA-440 and no Voyage key.

One `PolicyDraftState` is threaded through four async stages. Each stage reads
the state and the injected `AgentContext`, does its work, and returns a *new*
state (append-only). The loop stops at the first stage that halts.

## Key decisions

### MCP client, not direct import

The agent imports `pan-os-mcp` as a workspace dependency but does **not** call
its tool functions directly. Instead it spawns the server as a subprocess and
talks to it over the MCP protocol (stdio). This is the production-realistic
shape — the same client could point at any MCP server — and it forces a clean
boundary: the agent only sees typed tool results, never the firewall SDK. The
cost (one subprocess, async lifecycle) is paid once and amortized across all of
a run's tool calls by keeping a single `ClientSession` open.

### Hand-rolled state machine, not LangGraph/LangChain

The orchestrator is ~25 lines: a `for` loop over a list of stage functions with
an early-exit flag. This is deliberate. The four stages are a linear pipeline
with one branch (halt), which a framework would hide behind abstractions worth
more than they cost here. Hand-rolling keeps the portfolio narrative honest
("I built the control flow") and keeps the seams visible and testable. v2 would
reconsider only if genuine cycles, fan-out, or durable state emerge.

### Dependency injection via AgentContext

Stages take `(state, ctx)`. `AgentContext` is a plain dataclass bundling the
three collaborators a stage might need — the MCP client, the RAG retriever, the
Anthropic client. This is the testability seam: a stage test injects fakes for
all three and asserts both the returned state and *what the stage sent to
Claude*. Contrast with `pan-os-mcp`, which monkeypatches a module-level
`get_firewall()` global — injection is cleaner when one call graph needs several
fakes at once, which every stage does.

### One client factory; Portkey and AIRS optional by default

Nothing in the agent constructs an LLM client inline. `llm_client.py` is the sole
place an `AsyncAnthropic` (and the `McpClient`) is built, and `PORTKEY_MODE`
picks the routing: `off` (direct Anthropic — the default), `self_hosted` (a local
OSS Portkey gateway), or `cloud` (Portkey Cloud). All three keep using the
Anthropic SDK — the Portkey modes only repoint `base_url` and add `x-portkey-*`
headers — so every stage's `complete_structured` call is identical regardless of
mode. Centralizing this means the security posture is one config value, not a
second code path duplicated across entrypoints (an earlier design had separate
"secured"/"unsecured" apps and CLIs; they were collapsed into this).

Both the gateway and AIRS are **optional by default** on purpose. The core value
— the four-stage gauntlet — must run for someone with only an Anthropic key and
no Portkey account, or the demo has a hard dependency an SE can't satisfy in the
room. So `off` is the default and needs nothing extra. Prisma AIRS is layered on
top as a Portkey Config guardrail (see below), not baked into the agent, so
enabling governance is a deployment choice rather than a code change — which is
exactly the story an SE is selling.

### Prisma AIRS as a gateway guardrail, not an SDK gate

AIRS runs as an input/output guardrail *inside the Portkey Config* named by
`PORTKEY_CONFIG`, configured entirely in the Portkey GUI. When it denies a call,
Portkey returns HTTP 446; `complete_structured` turns that into a
`GuardrailBlocked`, and the orchestrator turns *that* into a clean security halt.
The agent carries no `pan-aisecurity` dependency and no AIRS key. This was a
deliberate choice over an in-process SDK gate: it keeps scanning at the gateway
(the same place a real deployment would enforce it, in front of *all* traffic,
not just this app), and it means the "secured" behavior is the same code with a
different Config — nothing to re-test in the agent. The trade-off, accepted for
v1: AIRS is only active on a Portkey path (`self_hosted` / `cloud`); the default
Direct-Anthropic path has no gateway and therefore no scanning, and the UI says
so rather than implying protection that isn't there.

### Structured outputs, not hand-parsed JSON

Every stage calls Claude through one helper, `complete_structured`, which wraps
the SDK's `messages.parse(output_format=<PydanticModel>)`. The SDK constrains
the response to the schema and returns a validated instance — so stages never
hand-parse JSON or guard against malformed output, and refusals surface as a
`None` return. The stage's static instructions are sent as a cache-controlled
system block (stable across fixtures → cheaper after the first call); the
per-intent data goes in the user turn, after the cache breakpoint.

### Append-only, JSON-serializable state

`PolicyDraftState` is a frozen Pydantic model. Stages mutate it only through
`advance(...)` / `halt(...)`, which return copies with a trace breadcrumb
appended. The whole object serializes to JSON, so a run *is* its own trace —
`model_dump_json()` yields a complete, replayable record of every stage's input
and output. The prerequisite stage additionally records the `chunk_id`s of the
docs that grounded it, so grounding is auditable, not asserted.

## Testing strategy

Three fakes, one per collaborator, all matching the real surface shape:

| Real thing | Fake | Mechanism |
|---|---|---|
| `Firewall` SDK (in `pan-os-mcp`) | `FakeFirewallClient` | XML fixture replay / `refreshall` monkeypatch |
| `McpClient` | `FakeMcpClient` | canned `{tool: result}` map |
| `AsyncAnthropic` | `FakeAnthropic` | canned `parse` results + recorded call kwargs |

Pure logic (result parsing, state transitions, the eval scorer, the driver
renderer) is unit-tested directly. LLM-driven stages are tested against fakes
for determinism *and* validated live against a PA-440 for real-world behavior.

## Evaluation: end-task, not proxy

Retrieval quality (recall@5) is a proxy — it measures whether the right chunks
were fetched, not whether the agent reached the right answer. The grounding eval
closes that gap: it runs the full gauntlet over labeled intents and scores the
product the agent emits — outcome (proposal vs halt-at-stage), proposed-rule
fields, and flagged prerequisites/shadowing. Cases are labeled with *robust*
expectations (incoherent intents, exact-match redundancy, denies reliably
shadowed by a broad allow, references to objects that don't exist) so LLM
non-determinism doesn't make the score flaky.

## v1 / v2 split

v1 is read-only with a fake approval gate: it proposes and explains but never
writes to the firewall. Every MCP tool is read-only by construction. v2 (post
this build) would add commit capability — and that write path is exactly where
Prisma AIRS belongs, guarding the agent's proposed change before it reaches the
device.
