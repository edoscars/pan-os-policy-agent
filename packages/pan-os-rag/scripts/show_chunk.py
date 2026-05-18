"""Print a chunk by its chunk_id.

Usage:
    uv run python packages/pan-os-rag/scripts/show_chunk.py <chunk_id>

Example:
    uv run python packages/pan-os-rag/scripts/show_chunk.py \\
        content/techdocs/en_US/ngfw/administration/user-id/enable-user-id:4
"""

import sys
from pan_os_rag.store import get_table


target = sys.argv[1]
rows = get_table().to_arrow().to_pylist()
match = next((r for r in rows if r["chunk_id"] == target), None)
if not match:
    print(f"Not found: {target}")
    sys.exit(1)
print(f"=== {match['chunk_id']} ===")
print(f"Page:    {match['page_title']}")
print(f"Heading: {match['heading_path']}")
print(f"URL:     {match['source_url']}\n")
print(match["text"])