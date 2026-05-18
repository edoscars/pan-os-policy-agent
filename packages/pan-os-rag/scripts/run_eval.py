"""Measure retrieval recall@k against a hand-labeled eval set.

Usage:
    uv run --env-file .env python packages/pan-os-rag/scripts/run_eval.py
"""

import json
from pathlib import Path
from collections import defaultdict

from pan_os_rag.retrieve import (
    retrieve,
    retrieve_hybrid,
    retrieve_hybrid_raw,
    retrieve_vector_raw,
)

QUESTIONS_FILE = Path("packages/pan-os-rag/eval/questions.jsonl")
K = 5


def load_questions(path: Path) -> list[dict]:
    """Read the eval set, one question per line."""
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def recall_at_k(expected: set[str], retrieved: list[str], k: int) -> float:
    """Fraction of expected chunk_ids present in the top-k retrieved.

    1 expected, found at rank 1 → 1.0
    3 expected, 2 in top-5 → 0.667
    1 expected, not in top-5 → 0.0
    """
    if not expected:
        raise ValueError("Empty expected set — labeling bug, not a 0.0 result.")
    hits = len(expected & set(retrieved[:k]))
    return hits / len(expected)

RETRIEVERS = {
    "vector": retrieve,
    "hybrid": retrieve_hybrid,
    "vector_raw": retrieve_vector_raw,
    "hybrid_raw": retrieve_hybrid_raw,
}


def evaluate(name: str, retriever, questions: list[dict]) -> dict[str, list[float]]:
    """Run one retriever against the eval set, print per-question and per-shape
    results, and return the per-shape scores for cross-retriever comparison.
    """
    print(f"\n{'=' * 70}\n{name.upper()} retriever\n{'=' * 70}\n")

    overall: list[float] = []
    by_shape: dict[str, list[float]] = defaultdict(list)
    misses: list[dict] = []

    for q in questions:
        results = retriever(q["question"], k=K)
        retrieved_ids = [c.chunk_id for c in results]
        expected = set(q["expected_chunk_ids"])
        score = recall_at_k(expected, retrieved_ids, K)

        overall.append(score)
        by_shape[q["shape"]].append(score)
        if score < 1.0:
            misses.append({"q": q, "retrieved": retrieved_ids, "score": score})

        marker = "✓" if score == 1.0 else "✗"
        print(f"  {marker} [{score:.2f}] {q['id']:4} {q['shape']:13} {q['question'][:60]}")

    print(f"\nOverall recall@{K}: {sum(overall) / len(overall):.3f}")
    print("\nBy shape:")
    for shape, scores in sorted(by_shape.items()):
        print(f"  {shape:13} {sum(scores) / len(scores):.3f}  (n={len(scores)})")

    if misses:
        print(f"\n{len(misses)} questions below 1.0:\n")
        for m in misses:
            missing = set(m["q"]["expected_chunk_ids"]) - set(m["retrieved"])
            print(f"  {m['q']['id']} [{m['score']:.2f}]: {m['q']['question']}")
            print(f"    Missing: {sorted(missing)}")
            print(f"    Got:     {m['retrieved']}\n")

    return dict(by_shape)


def print_comparison(results_by_retriever: dict[str, dict[str, list[float]]]) -> None:
    """Print a side-by-side per-shape comparison table across retrievers."""
    names = list(results_by_retriever.keys())
    shapes = sorted({s for r in results_by_retriever.values() for s in r})

    print(f"\n{'=' * 70}\nCOMPARISON\n{'=' * 70}\n")
    header = f"  {'shape':14}" + "".join(f"{n:>10}" for n in names)
    if len(names) == 2:
        header += f"{'delta':>10}"
    print(header)

    for shape in shapes:
        row = f"  {shape:14}"
        avgs = []
        for n in names:
            scores = results_by_retriever[n].get(shape, [])
            avg = sum(scores) / len(scores) if scores else 0.0
            avgs.append(avg)
            row += f"{avg:>10.3f}"
        if len(avgs) == 2:
            delta = avgs[1] - avgs[0]
            sign = "+" if delta >= 0 else ""
            row += f"{sign + format(delta, '.3f'):>10}"
        print(row)

    print()
    overall_row = f"  {'overall':14}"
    overall_avgs = []
    for n in names:
        all_scores = [s for shape_scores in results_by_retriever[n].values() for s in shape_scores]
        avg = sum(all_scores) / len(all_scores) if all_scores else 0.0
        overall_avgs.append(avg)
        overall_row += f"{avg:>10.3f}"
    if len(overall_avgs) == 2:
        delta = overall_avgs[1] - overall_avgs[0]
        sign = "+" if delta >= 0 else ""
        overall_row += f"{sign + format(delta, '.3f'):>10}"
    print(overall_row)


def main() -> None:
    questions = load_questions(QUESTIONS_FILE)
    print(f"Loaded {len(questions)} questions.")

    results_by_retriever: dict[str, dict[str, list[float]]] = {}
    for name, retriever in RETRIEVERS.items():
        results_by_retriever[name] = evaluate(name, retriever, questions)

    print_comparison(results_by_retriever)


if __name__ == "__main__":
    main()