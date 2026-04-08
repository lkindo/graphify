"""Intelligent URL crawling: decide when a URL warrants fetching related pages,
discover those pages, and crawl them into the corpus.

Design:
  should_crawl(url, html) -> (bool, reason)   — reasoning engine
  discover_links(html, base_url) -> [url]      — same-domain content links
  crawl(start_url, target_dir, ...) -> [Path]  — BFS crawl, calls ingest internally
"""
from __future__ import annotations
import re
import time
import urllib.parse
from pathlib import Path

from graphify.security import safe_fetch_text, validate_url


# ── Signal tables ─────────────────────────────────────────────────────────────

# URL patterns that strongly suggest the entire site section is worth crawling.
# Each entry: (regex, human-readable label)
_CRAWL_SIGNALS: list[tuple[str, str]] = [
    # Documentation platforms
    (r"readthedocs\.(io|org)",          "Read the Docs site"),
    (r"gitbook\.io",                    "GitBook documentation"),
    (r"\.github\.io",                   "GitHub Pages site"),
    # Documentation subdomains
    (r"(?:^|\.)docs?\.",                "docs subdomain"),
    (r"(?:^|\.)wiki\.",                 "wiki subdomain"),
    (r"(?:^|\.)help\.",                 "help center"),
    (r"(?:^|\.)support\.",              "support site"),
    (r"(?:^|\.)learn\.",                "learning resource"),
    (r"(?:^|\.)developer[s]?\.",        "developer docs"),
    # Documentation paths
    (r"/docs?/",                        "documentation section"),
    (r"/documentation/",               "documentation section"),
    (r"/reference/",                    "API reference"),
    (r"/api[-_]reference/",             "API reference"),
    (r"/api[-_]docs?/",                 "API documentation"),
    (r"/guide[s]?/",                    "guide / tutorial"),
    (r"/tutorial[s]?/",                 "tutorial"),
    (r"/manual/",                       "manual"),
    (r"/handbook/",                     "handbook"),
    (r"/learn/",                        "learning resource"),
    (r"/getting[-_]?started",           "getting-started guide"),
    (r"/quickstart",                    "quickstart guide"),
    (r"/v\d+\.\d+/",                    "versioned documentation"),
    # Wiki platforms
    (r"/wiki/",                         "wiki section"),
    (r"/w/index\.php",                  "MediaWiki"),
    (r"confluence\.",                   "Confluence wiki"),
    (r"/confluence/",                   "Confluence wiki"),
    # Help / knowledge base
    (r"/kb/",                           "knowledge base"),
    (r"/knowledge[-_]?base/",           "knowledge base"),
    (r"/faq[s]?[/.]",                   "FAQ section"),
    (r"/help/",                         "help section"),
    # E-commerce
    (r"/product[s]?/",                  "product catalog"),
    (r"/shop/",                         "shop"),
    (r"/catalog[ue]?/",                 "catalog"),
    (r"/item[s]?/",                     "item listing"),
    (r"/categor(?:y|ies)/",             "category page"),
    (r"/collection[s]?/",               "collection"),
    (r"/store/",                        "store"),
    # Blogs / content hubs (path must end at the index, not a deep article)
    (r"/blog/?$",                       "blog index"),
    (r"/blog/(?:tag|category|author)/", "blog category"),
    (r"/post[s]?/?$",                   "posts index"),
    (r"/article[s]?/?$",               "articles index"),
    (r"/release[s]?[-_]notes?",         "release notes"),
    (r"/changelog",                     "changelog"),
    # Notion / other platforms
    (r"notion\.so",                     "Notion workspace"),
    (r"gitbook\.com",                   "GitBook"),
]

# Domains where crawling is never appropriate.
_NO_CRAWL_DOMAINS: frozenset[str] = frozenset({
    "twitter.com", "x.com",
    "facebook.com", "instagram.com", "linkedin.com",
    "reddit.com",
    "youtube.com", "youtu.be", "vimeo.com",
    "arxiv.org",   # individual papers
    "doi.org",
    "maps.google.com",
})

# Path/query patterns that indicate non-content pages — always skip.
_SKIP_PATH_RE = re.compile(
    r"(?:/login|/signin|/sign-in|/signup|/sign-up|/register|/logout|/log-out"
    r"|/checkout|/cart|/basket|/account|/profile|/settings|/preferences"
    r"|/cdn-cgi|/wp-admin|/wp-json|/wp-login"
    r"|\?(?:q|s|query|search)="
    r"|/sitemap|sitemap\.xml"
    r"|/tag[s]?/|/author[s]?/|/feed"
    r"|/\d{4}/\d{2}/\d{2}/)",   # date-based archive URLs
    re.IGNORECASE,
)

# File extensions that are NOT pages and should be skipped in link discovery
# (graphify handles them separately via detect).
_SKIP_EXT_RE = re.compile(
    r"\.(zip|rar|tar|gz|exe|dmg|pkg|deb|rpm|iso|bin|apk"
    r"|mp3|mp4|wav|avi|mov|mkv|webm"
    r"|png|jpe?g|gif|webp|svg|ico"
    r"|pdf|docx?|xlsx?|pptx?)$",
    re.IGNORECASE,
)


# ── Public API ────────────────────────────────────────────────────────────────

def should_crawl(url: str, html: str = "") -> tuple[bool, str]:
    """Decide whether this URL warrants crawling its linked sub-pages.

    Returns (should_crawl: bool, reason: str).

    Reasons are human-readable and explain the triggering signal so the caller
    can log them or show them to the user.
    """
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    full = (domain + parsed.path).lower()

    # Hard no-crawl domains
    for no_domain in _NO_CRAWL_DOMAINS:
        if no_domain in domain:
            return False, f"single-resource domain ({no_domain})"

    # URL pattern signals
    for pattern, label in _CRAWL_SIGNALS:
        if re.search(pattern, full, re.IGNORECASE):
            return True, label

    # HTML content signals (only when HTML is available)
    if html:
        signal = _html_signal(html, url)
        if signal:
            return True, signal

    return False, "single page — no crawl signals detected"


def discover_links(html: str, base_url: str) -> list[str]:
    """Extract same-domain content links from an HTML page, ranked by priority.

    Filters out navigation boilerplate, admin paths, file downloads, and
    external links. Returns deduplicated absolute URLs, highest-priority first.
    """
    parsed = urllib.parse.urlparse(base_url)
    base_domain = parsed.netloc
    base_root = f"{parsed.scheme}://{base_domain}"
    start_prefix = parsed.path.rsplit("/", 1)[0]  # e.g. /docs/v2 -> /docs

    # Extract raw hrefs
    raw = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)

    seen: set[str] = set()
    scored: list[tuple[int, str]] = []

    for href in raw:
        href = href.strip().split("#")[0].rstrip("?").rstrip("/")
        if not href:
            continue
        if href.startswith(("javascript:", "mailto:", "tel:", "data:")):
            continue

        # Absolutise
        if href.startswith("//"):
            href = parsed.scheme + ":" + href
        elif href.startswith("/"):
            href = base_root + href
        elif not href.startswith("http"):
            href = urllib.parse.urljoin(base_url, href)

        # Validate & normalise
        try:
            p = urllib.parse.urlparse(href)
        except Exception:
            continue
        if p.netloc != base_domain:
            continue
        if not p.scheme.startswith("http"):
            continue
        if _SKIP_PATH_RE.search(p.path + ("?" + p.query if p.query else "")):
            continue
        if _SKIP_EXT_RE.search(p.path):
            continue

        href = f"{p.scheme}://{p.netloc}{p.path}"
        if p.query:
            href += "?" + p.query

        if href in seen or href == base_url:
            continue
        seen.add(href)

        # Score: same prefix > same depth > shorter path
        score = 0
        if p.path.startswith(start_prefix):
            score += 10
        depth = len([s for s in p.path.split("/") if s])
        score -= depth          # prefer shallower pages
        scored.append((score, href))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in scored]


def crawl(
    start_url: str,
    target_dir: Path,
    *,
    max_pages: int = 50,
    max_depth: int = 3,
    delay: float = 0.5,
    author: str | None = None,
    contributor: str | None = None,
) -> list[Path]:
    """BFS crawl from start_url, ingesting every discovered content page.

    Calls graphify.ingest.ingest() for each page with _skip_crawl=True to
    prevent recursive crawl triggering.

    Returns list of saved file paths (does NOT include the start URL — the
    caller is responsible for having ingested that first).
    """
    from collections import deque
    # Lazy import to avoid circular dependency
    from graphify.ingest import ingest as _ingest

    queue: deque[tuple[str, int]] = deque()
    visited: set[str] = {start_url}
    saved: list[Path] = []

    # Seed the queue from the start page's links
    try:
        html = safe_fetch_text(start_url)
        for link in discover_links(html, start_url):
            if link not in visited:
                visited.add(link)
                queue.append((link, 1))
    except Exception as exc:
        print(f"[crawl] Could not seed from {start_url}: {exc}")
        return saved

    print(f"[crawl] Queued {len(queue)} links — will fetch up to {max_pages}")

    while queue and len(saved) < max_pages:
        url, depth = queue.popleft()

        try:
            validate_url(url)
        except ValueError:
            continue

        try:
            out = _ingest(url, target_dir, author=author, contributor=contributor,
                         _skip_crawl=True)
            saved.append(out)
            print(f"[crawl] [{len(saved)}/{max_pages}] depth={depth} {url}")
        except Exception as exc:
            print(f"[crawl] skip {url}: {exc}")
            continue

        if delay > 0:
            time.sleep(delay)

        if depth >= max_depth:
            continue

        # Discover links from this page for the next BFS level
        try:
            page_html = safe_fetch_text(url)
        except Exception:
            continue

        for link in discover_links(page_html, start_url):
            if link not in visited:
                visited.add(link)
                queue.append((link, depth + 1))

    print(f"[crawl] Done — {len(saved)} pages saved to {target_dir}")
    return saved


# ── Helpers ───────────────────────────────────────────────────────────────────

def _html_signal(html: str, base_url: str) -> str | None:
    """Return a crawl reason if the page HTML shows crawl-worthy structure."""
    parsed = urllib.parse.urlparse(base_url)
    base_domain = re.escape(parsed.netloc)

    # Count unique same-domain links — a hub page has many
    same_domain = set(re.findall(
        rf'href=["\'](?:https?://{base_domain})?(/[^"\'#?][^"\']*)["\']',
        html, re.IGNORECASE,
    ))
    if len(same_domain) >= 12:
        return "hub page with many internal links"

    # Structural signals
    checks = [
        (r'class=["\'][^"\']*(?:sidebar|toc|table-of-contents|nav-menu)[^"\']*["\']',
         "sidebar / table-of-contents navigation"),
        (r'(?:next|previous)\s+(?:page|article|chapter|section)',
         "paginated / multi-page content"),
        (r'class=["\'][^"\']*breadcrumb[^"\']*["\']',
         "breadcrumb hierarchy"),
        (r'<nav\b[^>]*>',
         "structured navigation element"),
        (r'(?:showing|results?)\s+\d+[-–]\d+\s+of\s+\d+',
         "paginated listing"),
    ]
    for pattern, label in checks:
        if re.search(pattern, html, re.IGNORECASE):
            return label

    return None
