"""Diagnostic: measure overlap between vector-only and hybrid candidate sets.

Runs the first stage (candidate fetch) of both retrievers and compares
their top-CANDIDATES chunk_id sets — bypassing Voyage rerank entirely.

Tells you whether the two retrievers are actually fetching different
candidates, or whether the corpus is small enough that both pull the
same chunks before Voyage gets involved.

Usage:
    uv run --env-file .env python packages/pan-os-rag/scripts/diagnose_candidate_overlap.py
"""

import json
from pathlib import Path

from pan_os_rag.embed import embed_query
from pan_os_rag.retrieve import CANDIDATES
from pan_os_rag.store import get_table

EVAL_PATH = Path("packages/pan-os-rag/eval/questions.jsonl")


def main() -> None:
    with EVAL_PATH.open(encoding="utf-8") as f:
        questions = [json.loads(line) for line in f if line.strip()]

    table = get_table()

    print(f"Per-question candidate-set overlap (k={CANDIDATES}, corpus=257):\n")

    overlaps: list[int] = []
    for q in questions:
        query = q["question"]
        query_vec = embed_query(query)

        vec_rows = (
            table.search(query_vec, vector_column_name="vector")
            .limit(CANDIDATES)
            .to_arrow()
            .to_pylist()
        )
        hyb_rows = (
            table.search(
                query_type="hybrid",
                vector_column_name="vector",
                fts_columns="text",
            )
            .vector(query_vec)
            .text(query)
            .limit(CANDIDATES)
            .to_arrow()
            .to_pylist()
        )

        vec_ids = {r["chunk_id"] for r in vec_rows}
        hyb_ids = {r["chunk_id"] for r in hyb_rows}
        overlap = len(vec_ids & hyb_ids)
        overlaps.append(overlap)

        print(
            f"  {q['id']:4} overlap={overlap:3}/{CANDIDATES}  "
            f"only-vector={len(vec_ids - hyb_ids):3}  "
            f"only-hybrid={len(hyb_ids - vec_ids):3}"
        )

    n = len(overlaps)
    avg = sum(overlaps) / n
    print(f"\nAverage overlap: {avg:.1f}/{CANDIDATES} ({avg / CANDIDATES * 100:.0f}%)")
    print(f"Min overlap:     {min(overlaps):3}/{CANDIDATES}")
    print(f"Max overlap:     {max(overlaps):3}/{CANDIDATES}")


if __name__ == "__main__":
    main()
