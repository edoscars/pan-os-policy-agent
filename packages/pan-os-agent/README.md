# pan-os-agent

The agent: a hand-rolled async state machine that runs a natural-language policy
intent through a four-stage gauntlet and proposes a PAN-OS Security rule. It
never commits (v1). See the [root README](../../README.md) for the full picture
and [docs/architecture.md](../../docs/architecture.md) for design rationale.

## Layout

- **`orchestrator.py`** — the loop. `run_agent_streamed` yields state after each
  stage (for the live UI); `run_agent` drains it.
- **`stages/`** — the four stages (`intent`, `prerequisite`, `redundancy`,
  `proposal`), each an async `(state, ctx) -> state` function with Pydantic I/O.
- **`state.py`** / **`models.py`** — the frozen, append-only `PolicyDraftState`
  and the stage output models.
- **`context.py`** — `AgentContext`, the DI seam bundling the MCP client, RAG
  retriever, and Anthropic client.
- **`llm_client.py`** — the single place LLM/MCP clients are built;
  `PORTKEY_MODE` selects direct Anthropic (default) / Portkey self-hosted / cloud.
- **`llm.py`** — `complete_structured`, the schema-validated Claude call; maps a
  Portkey guardrail denial (HTTP 446) to a security halt.
- **`demo_data.py`** — `DemoMcpClient` + `demo_retriever`, the canned firewall
  and docs that power Demo mode.
- **`app.py`** / **`ui.py`** — the Streamlit demo app and its renderers.
- **`driver.py`** / **`scripts/`** — the single-shot CLI and eval runners.

## Run

```bash
# UI (Demo mode needs only an Anthropic key)
uv run --group demo streamlit run packages/pan-os-agent/app.py

# CLI (live mode)
uv run --env-file .env python packages/pan-os-agent/scripts/run_agent.py "<intent>"
```

## Tests

`uv run pytest` — offline and deterministic. The firewall, retriever, and
Anthropic client are all faked (see `tests/conftest.py`). `eval/` holds the
end-task grounding cases scored by `scripts/run_grounding_eval.py`.
