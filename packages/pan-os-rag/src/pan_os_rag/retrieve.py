"""Two-stage retrieval: vector search + Voyage rerank."""

import voyageai

from pan_os_rag import config
from pan_os_rag.chunk import Chunk
from pan_os_rag.embed import embed_query
from pan_os_rag.store import get_table

CANDIDATES = 50
RERANK_MODEL = "rerank-2.5"


def _get_voyage_client() -> voyageai.Client:
    """Construct a Voyage client for reranking.

    Mirrors embed.py's _get_client — both call out to the same SDK,
    same secret-handling boundary. Duplicated because importing
    embed._get_client would leak an internal across modules.
    """
    return voyageai.Client(api_key=config.get_settings().voyage_api_key.get_secret_value())


def retrieve(query: str, k: int = 5) -> list[Chunk]:
    """Return the top-k most relevant chunks for a query.

    Two-stage: vector search top-CANDIDATES from LanceDB, then Voyage
    rerank to top-k.
    """
    query_vec = embed_query(query)

    table = get_table()
    results = table.search(query_vec).limit(CANDIDATES).to_arrow().to_pylist()

    candidate_texts = [r["text"] for r in results]

    client = _get_voyage_client()
    rerank_result = client.rerank(
        query=query,
        documents=candidate_texts,
        model=RERANK_MODEL,
        top_k=k,
    )

    top_chunks: list[Chunk] = []
    for r in rerank_result.results:
        row = results[r.index]
        top_chunks.append(Chunk(
            text=row["text"],
            source_url=row["source_url"],
            page_title=row["page_title"],
            heading_path=row["heading_path"],
            position=row["position"],
        ))
    return top_chunks


def _rows_to_chunks(rows: list[dict]) -> list[Chunk]:
    return [
        Chunk(
            text=r["text"],
            source_url=r["source_url"],
            page_title=r["page_title"],
            heading_path=r["heading_path"],
            position=r["position"],
        )
        for r in rows
    ]


def retrieve_vector_raw(query: str, k: int = 5) -> list[Chunk]:
    """Vector search only, no rerank — top-k by cosine distance directly.

    Baseline for measuring whether Voyage rerank adds value over vanilla ANN.
    """
    query_vec = embed_query(query)
    rows = (
        get_table()
        .search(query_vec, vector_column_name="vector")
        .limit(k)
        .to_arrow()
        .to_pylist()
    )
    return _rows_to_chunks(rows)


def retrieve_hybrid_raw(query: str, k: int = 5) -> list[Chunk]:
    """Hybrid BM25+vector with LanceDB's RRF fusion, no Voyage rerank.

    Tests whether BM25-enhanced fusion alone is competitive with the
    rerank-based path — a common production tradeoff (faster, cheaper,
    no external rerank dependency).
    """
    query_vec = embed_query(query)
    rows = (
        get_table()
        .search(
            query_type="hybrid",
            vector_column_name="vector",
            fts_columns="text",
        )
        .vector(query_vec)
        .text(query)
        .limit(k)
        .to_arrow()
        .to_pylist()
    )
    return _rows_to_chunks(rows)


def retrieve_hybrid(query: str, k: int = 5) -> list[Chunk]:
    """Hybrid BM25+vector + Voyage rerank. Three-stage retriever.

    Compared to retrieve(): adds BM25 keyword matching to the candidate
    set, with the hypothesis that canonical-procedure chunks (whose
    headings contain the literal phrasing of common queries) surface
    better with literal matching than with embeddings alone.
    """
    query_vec = embed_query(query)

    table = get_table()
    results = (
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

    candidate_texts = [r["text"] for r in results]

    client = _get_voyage_client()
    rerank_result = client.rerank(
        query=query,
        documents=candidate_texts,
        model=RERANK_MODEL,
        top_k=k,
    )

    top_chunks: list[Chunk] = []
    for r in rerank_result.results:
        row = results[r.index]
        top_chunks.append(Chunk(
            text=row["text"],
            source_url=row["source_url"],
            page_title=row["page_title"],
            heading_path=row["heading_path"],
            position=row["position"],
        ))
    return top_chunks