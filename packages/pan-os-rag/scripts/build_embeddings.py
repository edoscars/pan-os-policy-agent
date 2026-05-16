"""Build embeddings for the entire corpus.

Walks corpus/**/*.md, chunks each document, embeds new chunks via Voyage AI,
and appends results to corpus/embeddings.jsonl.

Idempotent: chunks whose chunk_id already appears in the output file are
skipped. Re-running after a partial failure resumes from where it left off.

Streaming writes: each successful batch is flushed to disk immediately, so
a crash mid-run does not lose prior progress.

Usage:
    uv run --env-file .env python packages/pan-os-rag/scripts/build_embeddings.py
"""

import json
from pathlib import Path

from pan_os_rag.chunk import Chunk, chunk_file
from pan_os_rag.embed import BATCH_SIZE, EmbeddedChunk, embed_chunks


CORPUS_DIR = Path("corpus")
OUTPUT_FILE = CORPUS_DIR / "embeddings.jsonl"
BASE_URL = "https://docs.paloaltonetworks.com"


def chunk_corpus(corpus_dir: Path) -> list[Chunk]:
    """Walk corpus_dir for *.md files and chunk each one with reconstructed URLs."""
    all_chunks: list[Chunk] = []
    for md_path in corpus_dir.rglob("*.md"):
        relative = md_path.relative_to(corpus_dir).with_suffix("")
        source_url = f"{BASE_URL}/{relative.as_posix()}"
        all_chunks.extend(chunk_file(md_path, source_url=source_url))
    return all_chunks


def load_existing_chunk_ids(path: Path) -> set[str]:
    """Read the output file and return chunk_ids already embedded.

    Returns an empty set if the file does not exist (first run).
    """
    if not path.exists():
        return set()
    ids: set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            ids.add(json.loads(line)["chunk_id"])
    return ids


def write_batch(path: Path, embedded_chunks: list[EmbeddedChunk]) -> None:
    """Append a batch of embedded chunks to the JSONL output file."""
    with open(path, "a", encoding="utf-8") as f:
        for chunk in embedded_chunks:
            record = chunk.model_dump()
            record["chunk_id"] = chunk.chunk_id
            f.write(json.dumps(record) + "\n")


def main() -> None:
    """Build embeddings for the corpus, resuming from any prior partial run."""
    existing_ids = load_existing_chunk_ids(OUTPUT_FILE)
    if existing_ids:
        print(f"Resuming: {len(existing_ids)} chunks already embedded")
    else:
        print("Starting fresh.")

    all_chunks = chunk_corpus(CORPUS_DIR)
    print(f"Found {len(all_chunks)} chunks across the corpus.")

    todo = [c for c in all_chunks if c.chunk_id not in existing_ids]
    print(f"{len(todo)} chunks need embedding.")

    if not todo:
        print("Nothing to do.")
        return

    done = 0
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i : i + BATCH_SIZE]
        embedded = embed_chunks(batch)
        write_batch(OUTPUT_FILE, embedded)
        done += len(embedded)
        print(f"Embedded {done}/{len(todo)}")

    print(f"Done. Embedded {done} new chunks.")


if __name__ == "__main__":
    main()