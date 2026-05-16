"""Build the LanceDB table from embeddings.jsonl.

Usage:
    uv run python packages/pan-os-rag/scripts/build_store.py
"""

from pathlib import Path
from pan_os_rag.store import build_table, build_index

JSONL_PATH = Path("corpus/embeddings.jsonl")


def main() -> None:
    build_table(JSONL_PATH)
    build_index()
    print("Done.")


if __name__ == "__main__":
    main()