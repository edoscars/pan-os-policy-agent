"""Voyage AI embedding wrapping for chunks."""

import voyageai
from pan_os_rag import config
from pan_os_rag.chunk import Chunk

BATCH_SIZE = 128
MODEL = "voyage-3-large"

class EmbeddedChunk(Chunk):
    """A chunk that has been embedded. Adds the vector to the base Chunk."""
    vector: list[float]


def _get_client() -> voyageai.Client:
    """Construct a Voyage client from settings."""
    return voyageai.Client(api_key = config.get_settings().voyage_api_key.get_secret_value())


def embed_chunks(chunks: list[Chunk]) -> list[EmbeddedChunk]:
    """Embed a list of chunks as documents.
    Batches into requests of BATCH_SIZE. Returns embedded chunks
    in the same order as the input.
    """

    voyage_client = _get_client()
    
    embedded_chunks: list[EmbeddedChunk] = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c.text for c in batch]
        
        result = voyage_client.embed(
            texts,
            model=MODEL,
            input_type="document",
        )
        vectors = result.embeddings
        
        for chunk, vector in zip(batch, vectors):
            embedded_chunks.append(EmbeddedChunk(
                **chunk.model_dump(),
                vector=vector,
            ))

    return embedded_chunks


def embed_query(query: str) -> list[float]:
    """Embed a single query string.
    Uses input_type='query' for optimal retrieval against document embeddings.
    """
    voyage_client = _get_client()
    return voyage_client.embed(texts=[query], model=MODEL, input_type="query").embeddings[0]


if __name__ == "__main__":
    # Embed one chunk to verify the pipeline works
       
    fake_chunk = Chunk(
        text="The firewall enforces security policy rules in order.",
        source_url="https://example.com",
        page_title="Test",
        heading_path=["Test"],
        position=0,
    )
       
    embedded = embed_chunks([fake_chunk])

    # Embed a query to verify the query-side path works
    query = "How do I configure a security rule to allow traffic from a specific zone?"
    query_vector = embed_query(query)
    print(f"\nQuery vector dimension: {len(query_vector)}")
    print(f"First 5 values: {query_vector[:5]}")

    
    print(f"Got {len(embedded)} embeddings")
    print(f"Vector dimension: {len(embedded[0].vector)}")
    print(f"First 5 values: {embedded[0].vector[:5]}")