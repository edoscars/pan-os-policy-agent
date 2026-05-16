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