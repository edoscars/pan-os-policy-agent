"""Fetch and extract PAN-OS TechDocs pages."""

from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify
from collections import deque
import time

def url_to_cache_path(url: str, cache_dir: Path) -> Path:
    """Turn a TechDocs URL into a cache file path under cache_dir.
    
    Mirrors URL structure: 
        https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-admin/policy/security-policy
    →   cache_dir / pan-os/11-1/pan-os-admin/policy/security-policy.html
    """
    parsed_url = urlparse(url).path.lstrip("/")
    if not parsed_url.endswith(".html"):
        parsed_url += ".html"
    return cache_dir / parsed_url
    

def fetch(url: str, cache_dir: Path) -> Path:
    """Fetch URL if not cached, save raw HTML to disk, return the file path."""
    path = url_to_cache_path(url, cache_dir)
    if path.exists():
        return path
    project_root = Path(__file__).parents[4]
    final_file_path = project_root / path
    final_file_path.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client(follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        final_file_path.write_text(response.text, encoding="utf-8")

    return final_file_path



def extract_markdown(html_path: Path) -> Path:
    """Convert cached HTML to markdown, save next to it, return the .md path."""
    html_content = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "html.parser")
    article = soup.select_one("div.topic")
    if not article:
        raise ValueError(f"Could not find 'div.topic' in {html_path}")
    
    md_content = markdownify(str(article), heading_style="ATX")

    md_path = html_path.with_suffix(".md")
    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def discover_subpages(html_path: Path) -> list[str]:
    """Find subpage URLs in a TechDocs page's table-of-contents.
    
    TechDocs pages list child pages as <ul data-outputclass="nav">.
    Returns absolute URLs with fragments stripped.
    """
    html_content = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "html.parser")
    subpages = soup.select('ul[data-outputclass="nav"] a.xref')
    subpages_urls = []

    for subpage in subpages:
        href = subpage.get('href')
        if not href:
            continue 
        subpage_url = urljoin("https://docs.paloaltonetworks.com/", urldefrag(href)[0])
        parsed = urlparse(subpage_url)
        if not parsed.path.strip("/"):
            continue

        subpages_urls.append(subpage_url)

    return subpages_urls

def crawl(seed_urls: list[str], corpus_dir: Path) -> list[Path]:
    """Fetch seed URLs plus their discoverable subpages, recursively."""
    
    seen: set[str] = set()
    queue: deque[str] = deque(seed_urls)
    cached_paths: list[Path] = []
    skipped : list[tuple[str,int]] = []
    
    while queue:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)

        print(f"Fetching {url}...")

        try:
            
            url_fetched = fetch(url, corpus_dir)
            
            print(f"  → {url_fetched}") 
            extract_markdown(url_fetched)

            subpages = discover_subpages(url_fetched)

            for subpage in subpages:
                queue.append(subpage)
        
            cached_paths.append(url_fetched)
        
        except httpx.HTTPStatusError as e:
            skipped.append((url, e.response.status_code))
            print(f" SKIP: {e.response.status_code} for {url}")
            continue

        time.sleep(0.5)

    print(f"\nCrawled {len(cached_paths)} pages, skipped {len(skipped)}")
    if skipped:
        for url, status in skipped:
            print(f"  {status} {url}")
    
    return cached_paths

if __name__ == "__main__":
    cache = Path("corpus")
    seeds = [
        # PAN-OS 11.1 Admin Guide — Policy chapter (Security Policy, sub-pages)
        "https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-admin/policy",
        
        # PAN-OS 11.1 Admin Guide — Policy Objects (Address, Service, Application, etc.)
        "https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-admin/policy/policy-objects",
        
        # User-ID Guide (on the newer /ngfw/administration/ path)
        "https://docs.paloaltonetworks.com/ngfw/administration/user-id",
    ]
    
    paths = crawl(seeds, cache)
    print(f"\nCrawled {len(paths)} pages total.")