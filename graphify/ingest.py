# fetch URLs (tweet/arxiv/pdf/web) and save as annotated markdown
# When nimble_python is installed, powered by Nimble (nimbleway.com) for
# real-time web intelligence with stealth unblocking and JS rendering.
# Uses built-in urllib as an alternative path.
from __future__ import annotations
import json
import re
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from graphify.security import safe_fetch, safe_fetch_text, validate_url

# ---------------------------------------------------------------------------
# Nimble availability
# ---------------------------------------------------------------------------

try:
    from nimble_python import Nimble

    _HAS_NIMBLE = True
except ImportError:
    _HAS_NIMBLE = False


_nimble_cached: "Nimble | None" = None


def _nimble_client() -> "Nimble":
    """Return a cached Nimble client. Requires NIMBLE_API_KEY env var."""
    global _nimble_cached
    if _nimble_cached is None:
        _nimble_cached = Nimble()
    return _nimble_cached


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yaml_str(s: str) -> str:
    """Escape a string for embedding in a YAML double-quoted scalar."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def _safe_filename(url: str, suffix: str) -> str:
    """Turn a URL into a safe filename."""
    parsed = urllib.parse.urlparse(url)
    name = parsed.netloc + parsed.path
    name = re.sub(r"[^\w\-]", "_", name).strip("_")
    name = re.sub(r"_+", "_", name)[:80]
    return name + suffix


def _detect_url_type(url: str) -> str:
    """Classify the URL for targeted extraction."""
    lower = url.lower()
    if "twitter.com" in lower or "x.com" in lower:
        return "tweet"
    if "arxiv.org" in lower:
        return "arxiv"
    if "github.com" in lower:
        return "github"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "youtube"
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    if path.endswith(".pdf"):
        return "pdf"
    if any(path.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return "image"
    return "webpage"


def _write_unique(target_dir: Path, filename: str, content: str) -> Path:
    """Write content to target_dir/filename, appending a counter if it exists."""
    out_path = target_dir / filename
    counter = 1
    while out_path.exists():
        stem = Path(filename).stem
        out_path = target_dir / f"{stem}_{counter}.md"
        counter += 1
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Nimble-powered extraction
# ---------------------------------------------------------------------------


def _nimble_extract_markdown(url: str) -> str:
    """Use Nimble Extract to fetch a URL and return markdown content."""
    client = _nimble_client()
    response = client.extract(url=url, render=True, formats=["markdown"])
    return response.data.markdown or ""


# ---------------------------------------------------------------------------
# Built-in urllib fetching
# ---------------------------------------------------------------------------


def _fetch_html(url: str) -> str:
    return safe_fetch_text(url)


def _html_to_markdown(html_str: str, url: str) -> str:
    """Convert HTML to clean markdown. Uses html2text if available, else basic strip."""
    try:
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        return h.handle(html_str)
    except ImportError:
        # Fallback: strip tags
        text = re.sub(r"<script[^>]*>.*?</script>", "", html_str, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:8000]


# ---------------------------------------------------------------------------
# Fetchers (Nimble when available, urllib as alternative)
# ---------------------------------------------------------------------------


def _fetch_tweet(url: str, author: str | None, contributor: str | None) -> tuple[str, str]:
    """Fetch a tweet URL. Returns (content, filename)."""
    if _HAS_NIMBLE:
        try:
            markdown = _nimble_extract_markdown(url)
            tweet_text = markdown.strip() or f"Tweet at {url} (could not fetch content)"
            tweet_author = "unknown"
            # Try to extract author from the markdown
            author_match = re.search(r"@(\w+)", markdown)
            if author_match:
                tweet_author = author_match.group(1)
        except Exception:
            tweet_text = f"Tweet at {url} (could not fetch content)"
            tweet_author = "unknown"
    else:
        # Alternative: oEmbed
        oembed_url = url.replace("x.com", "twitter.com")
        oembed_api = f"https://publish.twitter.com/oembed?url={urllib.parse.quote(oembed_url)}&omit_script=true"
        try:
            data = json.loads(safe_fetch_text(oembed_api))
            tweet_text = re.sub(r"<[^>]+>", "", data.get("html", "")).strip()
            tweet_author = data.get("author_name", "unknown")
        except Exception:
            tweet_text = f"Tweet at {url} (could not fetch content)"
            tweet_author = "unknown"

    now = datetime.now(timezone.utc).isoformat()
    content = f"""---
source_url: {url}
type: tweet
author: {tweet_author}
captured_at: {now}
contributor: {contributor or author or 'unknown'}
---

# Tweet by @{tweet_author}

{tweet_text}

Source: {url}
"""
    filename = _safe_filename(url, ".md")
    return content, filename


def _fetch_webpage_urllib(url: str) -> tuple[str, str]:
    """Fetch webpage via urllib and return (title, markdown)."""
    html_str = _fetch_html(url)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_str, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else url
    markdown = _html_to_markdown(html_str, url)
    return title, markdown


def _fetch_webpage(url: str, author: str | None, contributor: str | None) -> tuple[str, str]:
    """Fetch a generic webpage and convert to markdown."""
    if _HAS_NIMBLE:
        try:
            markdown = _nimble_extract_markdown(url)
            title_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else url
        except Exception:
            title, markdown = _fetch_webpage_urllib(url)
    else:
        title, markdown = _fetch_webpage_urllib(url)

    now = datetime.now(timezone.utc).isoformat()
    content = f"""---
source_url: {url}
type: webpage
title: "{_yaml_str(title)}"
captured_at: {now}
contributor: {contributor or author or 'unknown'}
---

# {title}

Source: {url}

---

{markdown[:12000]}
"""
    filename = _safe_filename(url, ".md")
    return content, filename


def _fetch_arxiv(url: str, author: str | None, contributor: str | None) -> tuple[str, str]:
    """Fetch arXiv abstract page."""
    arxiv_id = re.search(r"(\d{4}\.\d{4,5})", url)
    if not arxiv_id:
        return _fetch_webpage(url, author, contributor)

    if _HAS_NIMBLE:
        try:
            abs_url = f"https://arxiv.org/abs/{arxiv_id.group(1)}"
            markdown = _nimble_extract_markdown(abs_url)
            # Try to extract structured info from markdown
            title_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else arxiv_id.group(1)
            # Look for abstract section
            abstract_match = re.search(r"(?:Abstract|abstract)[:\s]*\n(.*?)(?:\n#|\n\n\n|\Z)", markdown, re.DOTALL)
            abstract = abstract_match.group(1).strip() if abstract_match else ""
            paper_authors = ""
            authors_match = re.search(r"(?:Authors?|By)[:\s]*(.+?)(?:\n#|\n\n)", markdown, re.DOTALL)
            if authors_match:
                paper_authors = authors_match.group(1).strip()
        except Exception:
            title, abstract, paper_authors = arxiv_id.group(1), "", ""
    else:
        api_url = f"https://export.arxiv.org/abs/{arxiv_id.group(1)}"
        try:
            html_str = _fetch_html(api_url)
            abstract_match = re.search(r'class="abstract[^"]*"[^>]*>(.*?)</blockquote>', html_str, re.DOTALL | re.IGNORECASE)
            abstract = re.sub(r"<[^>]+>", "", abstract_match.group(1)).strip() if abstract_match else ""
            title_match = re.search(r'class="title[^"]*"[^>]*>(.*?)</h1>', html_str, re.DOTALL | re.IGNORECASE)
            title = re.sub(r"<[^>]+>", " ", title_match.group(1)).strip() if title_match else arxiv_id.group(1)
            authors_match = re.search(r'class="authors"[^>]*>(.*?)</div>', html_str, re.DOTALL | re.IGNORECASE)
            paper_authors = re.sub(r"<[^>]+>", "", authors_match.group(1)).strip() if authors_match else ""
        except Exception:
            title, abstract, paper_authors = arxiv_id.group(1), "", ""

    now = datetime.now(timezone.utc).isoformat()
    content = f"""---
source_url: {url}
arxiv_id: {arxiv_id.group(1)}
type: paper
title: "{title}"
paper_authors: "{paper_authors}"
captured_at: {now}
contributor: {contributor or author or 'unknown'}
---

# {title}

**Authors:** {paper_authors}
**arXiv:** {arxiv_id.group(1)}

## Abstract

{abstract}

Source: {url}
"""
    filename = f"arxiv_{arxiv_id.group(1).replace('.', '_')}.md"
    return content, filename


def _download_binary(url: str, suffix: str, target_dir: Path) -> Path:
    """Download a binary file (PDF, image) directly."""
    filename = _safe_filename(url, suffix)
    out_path = target_dir / filename
    out_path.write_bytes(safe_fetch(url))
    return out_path


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def ingest(url: str, target_dir: Path, author: str | None = None, contributor: str | None = None) -> Path:
    """
    Fetch a URL and save it into target_dir as a graphify-ready file.

    When nimble_python is installed, uses Nimble Extract for JS rendering,
    anti-bot handling, and clean markdown. Uses urllib as an alternative otherwise.

    Returns the path of the saved file.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        validate_url(url)
    except ValueError as exc:
        raise ValueError(f"ingest: {exc}") from exc

    url_type = _detect_url_type(url)

    try:
        if url_type == "pdf":
            out = _download_binary(url, ".pdf", target_dir)
            print(f"Downloaded PDF: {out.name}")
            return out

        if url_type == "image":
            suffix = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
            out = _download_binary(url, suffix, target_dir)
            print(f"Downloaded image: {out.name}")
            return out

        if url_type == "tweet":
            content, filename = _fetch_tweet(url, author, contributor)
        elif url_type == "arxiv":
            content, filename = _fetch_arxiv(url, author, contributor)
        else:
            content, filename = _fetch_webpage(url, author, contributor)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"ingest: failed to fetch {url!r}: {exc}") from exc

    backend = "nimble" if _HAS_NIMBLE else "urllib"
    out_path = _write_unique(target_dir, filename, content)
    print(f"Saved {url_type}: {out_path.name} (via {backend})")
    return out_path


def search_ingest(
    query: str,
    target_dir: Path,
    max_results: int = 10,
    author: str | None = None,
    contributor: str | None = None,
) -> list[Path]:
    """
    Search the web for *query* using Nimble Search (general focus, deep mode),
    then ingest each result into target_dir as graphify-ready markdown.

    Requires nimble_python to be installed. Raises ImportError otherwise.

    Returns list of saved file paths.
    """
    if not _HAS_NIMBLE:
        raise ImportError(
            "search_ingest requires nimble_python. "
            "Install it with: pip install graphifyy[nimble]"
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    client = _nimble_client()

    response = client.search(
        query=query,
        max_results=max_results,
        focus="general",
        search_depth="deep",
    )

    saved: list[Path] = []
    results = response.results or []

    now = datetime.now(timezone.utc).isoformat()
    for item in results:
        title = getattr(item, "title", "")
        url = getattr(item, "url", "")
        description = getattr(item, "description", "")
        content_text = getattr(item, "content", "")

        if not url:
            continue

        content = f"""---
source_url: {url}
type: search_result
query: "{_yaml_str(query)}"
title: "{_yaml_str(title)}"
captured_at: {now}
contributor: {contributor or author or 'unknown'}
---

# {title}

Source: {url}
Search query: {query}

---

{content_text or description}
"""
        filename = _safe_filename(url, ".md")
        out_path = _write_unique(target_dir, filename, content)
        saved.append(out_path)

    print(f"Search '{query}': saved {len(saved)} results (via nimble)")
    return saved


# ---------------------------------------------------------------------------
# Q&A memory (unchanged)
# ---------------------------------------------------------------------------


def save_query_result(
    question: str,
    answer: str,
    memory_dir: Path,
    query_type: str = "query",
    source_nodes: list[str] | None = None,
) -> Path:
    """Save a Q&A result as markdown so it gets extracted into the graph on next --update.

    Files are stored in memory_dir (typically graphify-out/memory/) with YAML frontmatter
    that graphify's extractor reads as node metadata. This closes the feedback loop:
    the system grows smarter from both what you add AND what you ask.
    """
    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    slug = re.sub(r"[^\w]", "_", question.lower())[:50].strip("_")
    filename = f"query_{now.strftime('%Y%m%d_%H%M%S')}_{slug}.md"

    frontmatter_lines = [
        "---",
        f'type: "{query_type}"',
        f'date: "{now.isoformat()}"',
        f'question: "{_yaml_str(question)}"',
        'contributor: "graphify"',
    ]
    if source_nodes:
        nodes_str = ", ".join(f'"{n}"' for n in source_nodes[:10])
        frontmatter_lines.append(f"source_nodes: [{nodes_str}]")
    frontmatter_lines.append("---")

    body_lines = [
        "",
        f"# Q: {question}",
        "",
        "## Answer",
        "",
        answer,
    ]
    if source_nodes:
        body_lines += ["", "## Source Nodes", ""]
        body_lines += [f"- {n}" for n in source_nodes]

    content = "\n".join(frontmatter_lines + body_lines)
    out_path = memory_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch a URL into a graphify /raw folder")
    parser.add_argument("url", help="URL to fetch (or use --search for topic search)")
    parser.add_argument("target_dir", nargs="?", default="./raw", help="Target directory (default: ./raw)")
    parser.add_argument("--author", help="Your name (stored as node metadata)")
    parser.add_argument("--contributor", help="Contributor name for team graphs")
    parser.add_argument("--search", action="store_true", help="Treat 'url' as a search query (requires nimble)")
    parser.add_argument("--max-results", type=int, default=10, help="Max search results (default: 10)")
    args = parser.parse_args()

    if args.search:
        results = search_ingest(
            args.url, Path(args.target_dir),
            max_results=args.max_results,
            author=args.author, contributor=args.contributor,
        )
        print(f"Ready for graphify: {len(results)} files in {args.target_dir}")
    else:
        out = ingest(args.url, Path(args.target_dir), author=args.author, contributor=args.contributor)
        print(f"Ready for graphify: {out}")
