# pan-os-rag

Retrieval over PAN-OS 11.1 TechDocs (Policy, Policy Objects, User-ID), used by
[`pan-os-agent`](../pan-os-agent)'s prerequisite stage to ground its findings in
documentation. Scrape → chunk → embed → store → retrieve, with a rerank pass.

## Pipeline

- **`scrape.py`** — crawl and cache TechDocs pages as markdown.
- **`chunk.py`** — structure-aware ~500-token chunks (50-token overlap), each
  with a stable `chunk_id`.
- **`embed.py`** — Voyage `voyage-3-large` embeddings (1024-dim).
- **`store.py`** — LanceDB store at `corpus/lancedb` with vector + BM25 indexes.
- **`retrieve.py`** — vector top-50 → Voyage `rerank-2.5` → top-k (the path the
  agent uses). Hybrid / raw variants exist for the eval harness.

## Build the store

The corpus is gitignored (regenerable). Build once before live-mode use:

```bash
uv run --env-file .env python packages/pan-os-rag/scripts/build_embeddings.py
uv run --env-file .env python packages/pan-os-rag/scripts/build_store.py
```

Needs `VOYAGE_API_KEY`. (The agent's Demo mode uses a canned retriever instead,
so no store or key is required there.)

## Evaluation

`eval/questions.jsonl` — 30 hand-labeled questions across five shapes (factual,
workflow, prerequisite, edge-case, cross-cutting). `scripts/run_eval.py` scores
recall@5; `scripts/diagnose_candidate_overlap.py` compares vector-only vs. hybrid
candidate sets.
