"""Tests for Nimble integration in graphify.ingest."""
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from graphify.ingest import ingest, search_ingest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _FakeExtractData:
    def __init__(self, markdown: str):
        self.markdown = markdown

class _FakeExtractResponse:
    def __init__(self, markdown: str):
        self.data = _FakeExtractData(markdown)

class _FakeSearchResultItem:
    def __init__(self, title="", url="", description="", content=""):
        self.title = title
        self.url = url
        self.description = description
        self.content = content

class _FakeSearchResponse:
    def __init__(self, results):
        self.results = results


def _make_client(extract_md="# Page Title\n\nSome content.", search_results=None):
    client = MagicMock()
    client.extract.return_value = _FakeExtractResponse(extract_md)
    if search_results is not None:
        items = [_FakeSearchResultItem(**r) if isinstance(r, dict) else r for r in search_results]
        client.search.return_value = _FakeSearchResponse(items)
    return client


@pytest.fixture
def nimble(request):
    """Patch Nimble as available with a fake client. Use `indirect` to pass extract_md."""
    md = getattr(request, "param", "# Page Title\n\nSome content.")
    client = _make_client(extract_md=md)
    with patch("graphify.ingest._HAS_NIMBLE", True), \
         patch("graphify.ingest._nimble_client", return_value=client), \
         patch("graphify.ingest.validate_url", side_effect=lambda u: u):
        yield client


@pytest.fixture
def nimble_search(request):
    """Patch Nimble as available with search results."""
    results = getattr(request, "param", [])
    client = _make_client(search_results=results)
    with patch("graphify.ingest._HAS_NIMBLE", True), \
         patch("graphify.ingest._nimble_client", return_value=client):
        yield client


@pytest.fixture
def no_nimble():
    with patch("graphify.ingest._HAS_NIMBLE", False), \
         patch("graphify.ingest.validate_url", side_effect=lambda u: u):
        yield


# ---------------------------------------------------------------------------
# Nimble Extract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nimble", ["# Hello World\n\nContent from Nimble."], indirect=True)
def test_webpage_via_nimble(nimble, tmp_path):
    out = ingest("https://example.com", tmp_path)
    content = out.read_text()
    assert "Content from Nimble" in content
    assert "type: webpage" in content
    nimble.extract.assert_called_once_with(url="https://example.com", render=True, formats=["markdown"])


@pytest.mark.parametrize("nimble", ["# My Great Page\n\nBody."], indirect=True)
def test_title_from_markdown_heading(nimble, tmp_path):
    out = ingest("https://example.com/page", tmp_path)
    assert 'title: "My Great Page"' in out.read_text()


def test_nimble_error_uses_urllib(tmp_path):
    client = _make_client()
    client.extract.side_effect = Exception("connection timeout")
    html = "<html><head><title>Alternative</title></head><body>Hello</body></html>"
    with patch("graphify.ingest._HAS_NIMBLE", True), \
         patch("graphify.ingest._nimble_client", return_value=client), \
         patch("graphify.ingest.validate_url", side_effect=lambda u: u), \
         patch("graphify.ingest._fetch_html", return_value=html):
        out = ingest("https://example.com", tmp_path)
    assert "Alternative" in out.read_text()


@pytest.mark.parametrize("nimble", ["Tweet by @testuser\n\nHello world!"], indirect=True)
def test_tweet_via_nimble(nimble, tmp_path):
    out = ingest("https://x.com/testuser/status/123", tmp_path)
    content = out.read_text()
    assert "type: tweet" in content
    assert "testuser" in content


@pytest.mark.parametrize("nimble", ["# Attention Is All You Need\n\nAuthors: Vaswani et al.\n\nAbstract\nNew architecture."], indirect=True)
def test_arxiv_via_nimble(nimble, tmp_path):
    out = ingest("https://arxiv.org/abs/1706.03762", tmp_path)
    content = out.read_text()
    assert "type: paper" in content
    assert "1706.03762" in content
    assert "Attention Is All You Need" in content


def test_pdf_binary_download(nimble, tmp_path):
    with patch("graphify.ingest.safe_fetch", return_value=b"%PDF-1.4 fake"):
        out = ingest("https://example.com/paper.pdf", tmp_path)
    assert out.suffix == ".pdf"
    assert out.read_bytes() == b"%PDF-1.4 fake"


# ---------------------------------------------------------------------------
# urllib alternative
# ---------------------------------------------------------------------------

def test_webpage_via_urllib(no_nimble, tmp_path):
    html = "<html><head><title>Old School</title></head><body>Content</body></html>"
    with patch("graphify.ingest._fetch_html", return_value=html):
        out = ingest("https://example.com", tmp_path)
    assert "Old School" in out.read_text()


def test_tweet_via_oembed(no_nimble, tmp_path):
    resp = json.dumps({"html": "<p>Hello tweet</p>", "author_name": "testuser"})
    with patch("graphify.ingest.safe_fetch_text", return_value=resp):
        out = ingest("https://x.com/testuser/status/1", tmp_path)
    content = out.read_text()
    assert "testuser" in content
    assert "Hello tweet" in content


# ---------------------------------------------------------------------------
# Nimble Search
# ---------------------------------------------------------------------------

_TWO_RESULTS = [
    {"title": "Result 1", "url": "https://a.com/1", "description": "First", "content": "Full content 1"},
    {"title": "Result 2", "url": "https://b.com/2", "description": "Second", "content": "Full content 2"},
]

@pytest.mark.parametrize("nimble_search", [_TWO_RESULTS], indirect=True)
def test_search_saves_results(nimble_search, tmp_path):
    paths = search_ingest("test query", tmp_path)
    assert len(paths) == 2
    for p in paths:
        content = p.read_text()
        assert "type: search_result" in content
        assert 'query: "test query"' in content


@pytest.mark.parametrize("nimble_search", [[]], indirect=True)
def test_search_params(nimble_search, tmp_path):
    search_ingest("AI transformers", tmp_path, max_results=5)
    nimble_search.search.assert_called_once_with(
        query="AI transformers", max_results=5, focus="general", search_depth="deep",
    )


@pytest.mark.parametrize("nimble_search", [[
    {"title": "No URL", "description": "Missing"},
    {"title": "Has URL", "url": "https://c.com/page", "description": "Good"},
]], indirect=True)
def test_search_skips_results_without_url(nimble_search, tmp_path):
    assert len(search_ingest("query", tmp_path)) == 1


def test_search_raises_without_nimble(no_nimble, tmp_path):
    with pytest.raises(ImportError, match="nimble_python"):
        search_ingest("query", tmp_path)


@pytest.mark.parametrize("nimble_search,field,expected", [
    ([{"title": "Deep", "url": "https://d.com/d", "content": "Full deep content"}], "content", "Full deep content"),
    ([{"title": "Lite", "url": "https://e.com/e", "description": "Just a description"}], "description", "Just a description"),
], indirect=["nimble_search"])
def test_search_content_vs_description(nimble_search, field, expected, tmp_path):
    paths = search_ingest("query", tmp_path)
    assert expected in paths[0].read_text()


@pytest.mark.parametrize("nimble_search", [[
    {"title": "A", "url": "https://same.com/a", "description": "A"},
    {"title": "A", "url": "https://same.com/a", "description": "A dup"},
]], indirect=True)
def test_search_no_filename_collision(nimble_search, tmp_path):
    paths = search_ingest("query", tmp_path)
    assert len(paths) == 2
    assert paths[0] != paths[1]


@pytest.mark.parametrize("nimble_search", [[
    {"title": "T", "url": "https://f.com/f", "description": "t"},
]], indirect=True)
def test_search_contributor(nimble_search, tmp_path):
    paths = search_ingest("query", tmp_path, author="Alice", contributor="Bob")
    assert "contributor: Bob" in paths[0].read_text()
