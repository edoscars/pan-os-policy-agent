# Architecture & design rationale

This document explains *why* the project is shaped the way it is. For *what* it
does and how to run it, see the [README](../README.md).

## System shape

```
                    ┌─────────────────────────── pan-os-agent ───────────────────────────┐
                    │                                                                     │
   intent text ───▶ │  run_agent loop                                                     │
                    │    for stage in STAGES:  state = await stage(state, ctx)            │
                    │                          if state.halted: break                     │
                    │                                                                     │
                    │   AgentContext (DI) ── mcp ──▶ McpClient ──(stdio subprocess)──┐    │
                    │                    ├─ retriever ──▶ pan-os-rag.retrieve         │    │
                    │                    └─ anthropic ──▶ AsyncAnthropic              │    │
                    └───────────────────────────────────────────────────────────────┼────┘
                                                                                     │
                                          ┌──────────────────────────────────────────▼─┐
                                          │ pan-os-mcp server (FastMCP over stdio)       │
                                          │   tools/*.py  ──▶  pan-os-python  ──▶ PA-440 │
                                          └──────────────────────────────────────────────┘
```

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
