"""LanceDB storage for embedded chunks.

Loads embeddings.jsonl into a LanceDB table with vector indexing.
The table is the canonical source for retrieve.py.

Build the table:
    uv run python packages/pan-os-rag/scripts/build_store.py

(The build is in a script, not in this module — keep library code free
of side effects.)
"""

from pathlib import Path
import json

import lancedb
from lancedb.pydantic import LanceModel, Vector

DB_PATH = Path("corpus/lancedb")
TABLE_NAME = "chunks"
VECTOR_DIM = 1024   # voyage-3-large


class ChunkRecord(LanceModel):
    """One row in the chunks table. Parallel to EmbeddedChunk, but a
    distinct type because LanceDB needs the vector dimension declared.
    """
    chunk_id: str
    text: str
    source_url: str
    page_title: str
    heading_path: list[str]
    position: int
    vector: Vector(VECTOR_DIM)


def get_db():
    """Open (or create) the LanceDB database at DB_PATH.

    LanceDB is embedded — connect() points at a directory, not a server.
    """
    return lancedb.connect(DB_PATH)


def build_table(jsonl_path: Path) -> None:
    """Create the chunks table from a JSONL of embedded chunks.

    Idempotent at the table level: drops and re-creates the table if it
    exists. Idempotency at the chunk level lives in build_embeddings.py.
    """
    db = get_db()

    with open(jsonl_path, "r", encoding="utf-8") as f:
        records = [ChunkRecord(**json.loads(line)) for line in f]

    if TABLE_NAME in db.table_names():
        db.drop_table(TABLE_NAME)

    db.create_table(TABLE_NAME, data=records, schema=ChunkRecord)
    print(f"Wrote {len(records)} rows.")


def get_table():
    """Open the chunks table for querying. Used by retrieve.py."""
    return get_db().open_table(TABLE_NAME)


def build_index() -> None:
    """Create a vector index on the chunks table.

    For 257 rows this is overkill — brute-force scan is fast enough.
    Doing it anyway as muscle memory for production-scale corpora.
    """
    table = get_table()
    table.create_index(metric="cosine", vector_column_name="vector")

def build_fts_index() -> None:
    """Create a BM25 full-text-search index on the text column.

    Used by retrieve.py for hybrid retrieval (BM25 + vector).
    Indexing happens asynchronously after this call returns —
    queries against the FTS index work immediately but may be
    slower until indexing completes.
    """
    table = get_table()
    table.create_fts_index(
        "text",
        use_tantivy=False,
        replace=True,
        language="English",
    )