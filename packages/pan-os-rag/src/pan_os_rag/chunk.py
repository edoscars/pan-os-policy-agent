"""Chunk markdown files into ~500-token pieces with metadata."""

import re
from pathlib import Path
from pydantic import BaseModel
from urllib.parse import urlparse

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

def parse_blocks(markdown_text: str) -> list[tuple[str, int, str]]:
    """Split markdown into (kind, level, text) blocks.
    
    kind is 'heading' or 'prose'.
    level is 1-6 for headings, 0 for prose.
    
    Prose blocks are separated by blank lines. Adjacent non-heading,
    non-blank lines are joined into one prose block.
    """
    blocks: list[tuple[str, int, str]] = []
    prose: list[str] = []

    def flush_prose() -> None:
        if prose:
            blocks.append(("prose", 0, "\n".join(prose)))
            prose.clear()

    for line in markdown_text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            flush_prose()
            blocks.append(("heading", len(m.group(1)), m.group(2)))
        elif line.strip():
            prose.append(line)
        else:
            flush_prose()
    flush_prose()
    return blocks

def _approx_tokens(text: str) -> int:
    return len(text) // 4

TARGET_TOKENS = 500
OVERLAP_TOKENS = 50
MAX_TOKENS = 800
MIN_TOKENS = 30   # below this, the chunk is probably noise

class Chunk(BaseModel):
    """One chunk of source content, ready for embedding."""
    
    text: str
    source_url: str
    page_title: str
    heading_path: list[str]
    position: int
    
    @property
    def chunk_id(self) -> str:
        """Stable identifier for this chunk.
        
        Used as the primary key in the vector store and as a reference
        in the eval set ("the answer to question X lives in chunk Y").
        """
        path = urlparse(self.source_url).path.strip("/")
        return f"{path}:{self.position}"

def _split_oversized(chunk: Chunk) -> list[Chunk]:
    """Force-split a chunk over MAX_TOKENS at sentence boundaries."""
    if _approx_tokens(chunk.text) <= MAX_TOKENS:
        return [chunk]

    sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
    sub_chunks: list[Chunk] = []
    buf: list[str] = []
    buf_tokens = 0

    def emit() -> None:
        nonlocal buf, buf_tokens
        if not buf:
            return
        sub_chunks.append(Chunk(
            text=" ".join(buf),
            source_url=chunk.source_url,
            page_title=chunk.page_title,
            heading_path=chunk.heading_path,
            position=chunk.position + len(sub_chunks),
        ))
        buf = []
        buf_tokens = 0

    for sentence in sentences:
        t = _approx_tokens(sentence)
        if buf and buf_tokens + t > TARGET_TOKENS:
            emit()
        buf.append(sentence)
        buf_tokens += t
    emit()
    return sub_chunks


def chunk_file(md_path: Path, source_url: str) -> list[Chunk]:
    """Split a markdown file into chunks with structural metadata.
    
    Boundary strategy: structure-aware (respect paragraphs and
    headings), target ~500 tokens per chunk with 10% overlap.
    """
    blocks = parse_blocks(md_path.read_text(encoding="utf-8"))
    page_title = next((t for k, _, t in blocks if k == "heading"), md_path.stem)

    chunks: list[Chunk] = []
    heading_path: list[str] = []
    levels: list[int] = []
    buf: list[str] = []

    def flush(carry: bool) -> None:
        body = "\n\n".join(buf).strip()
        if not body:
            buf.clear()
            return
        chunks.append(Chunk(
            text=body,
            source_url=source_url,
            page_title=page_title,
            heading_path=list(heading_path),
            position=len(chunks),
        ))
        overlap: list[str] = []
        if carry:
            tokens = 0
            for p in reversed(buf):
                if overlap and tokens + _approx_tokens(p) > OVERLAP_TOKENS:
                    break
                overlap.insert(0, p)
                tokens += _approx_tokens(p)
        buf.clear()
        buf.extend(overlap)

    for kind, level, text in blocks:
        if kind == "heading":
            flush(carry=False)
            while levels and levels[-1] >= level:
                levels.pop()
                heading_path.pop()
            levels.append(level)
            heading_path.append(text)
        else:
            buf.append(text)
            if sum(_approx_tokens(p) for p in buf) >= TARGET_TOKENS:
                flush(carry=True)
    flush(carry=False)

    # Renumber sequentially after split, since _split_oversized produces
    # position values that may collide with subsequent original chunks.
    final: list[Chunk] = []
    for chunk in chunks:
        final.extend(_split_oversized(chunk))
    final = [c for c in final if _approx_tokens(c.text) >= MIN_TOKENS]
    for i, chunk in enumerate(final):
        chunk.position = i
    return final


if __name__ == "__main__":
    from collections import Counter
    
    CORPUS = Path("corpus")
    BASE_URL = "https://docs.paloaltonetworks.com"
    
    all_chunks: list[Chunk] = []
    
    for md_path in CORPUS.rglob("*.md"):
        # Reconstruct the URL from the cached file path
        relative = md_path.relative_to(CORPUS).with_suffix("")
        source_url = f"{BASE_URL}/{relative.as_posix()}"
        
        chunks = chunk_file(md_path, source_url=source_url)
        all_chunks.extend(chunks)
    
    print(f"Total chunks: {len(all_chunks)}")
    
    # Distribution of chunk sizes
    sizes = [_approx_tokens(c.text) for c in all_chunks]
    print(f"Size — min: {min(sizes)}, max: {max(sizes)}, "
          f"avg: {sum(sizes) // len(sizes)}, median: {sorted(sizes)[len(sizes)//2]}")
    
    # Distribution of chunks per file
    files = Counter(c.source_url for c in all_chunks)
    print(f"Pages: {len(files)}, chunks per page — min: {min(files.values())}, "
          f"max: {max(files.values())}, avg: {sum(files.values()) // len(files)}")
    
    # Show 3 examples — one short, one medium, one long
    sorted_by_size = sorted(all_chunks, key=lambda c: _approx_tokens(c.text))
    examples = [sorted_by_size[0], sorted_by_size[len(sorted_by_size)//2], sorted_by_size[-1]]
    for chunk in examples:
        print(f"\n--- {chunk.chunk_id} ({_approx_tokens(chunk.text)} tokens) ---")
        print(f"  heading_path: {chunk.heading_path}")
        print(f"  text preview: {chunk.text[:200]}")