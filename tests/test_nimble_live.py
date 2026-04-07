"""Live integration tests for Nimble — requires NIMBLE_API_KEY env var.

Run with:
    uv run --with nimble_python --with pytest pytest tests/test_nimble_live.py -v -s

Skipped automatically in CI or when no API key is set.
"""
from __future__ import annotations
import os
from pathlib import Path

import pytest

try:
    import nimble_python  # noqa: F401
    _HAS_NIMBLE = True
except ImportError:
    _HAS_NIMBLE = False

pytestmark = pytest.mark.skipif(
    not _HAS_NIMBLE or not os.environ.get("NIMBLE_API_KEY"),
    reason="nimble_python not installed or NIMBLE_API_KEY not set",
)


@pytest.fixture
def nimble_client():
    from nimble_python import Nimble
    return Nimble()


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

class TestLiveExtract:

    def test_extract_markdown(self, nimble_client):
        response = nimble_client.extract(url="https://example.com", render=True, formats=["markdown"])
        md = response.data.markdown
        assert md is not None
        assert len(md) > 20
        # Nimble returns body text as markdown; example.com mentions "domain" and "examples"
        assert "domain" in md.lower()
        print(f"\n--- Extract markdown ({len(md)} chars) ---")
        print(md[:500])

    def test_extract_html(self, nimble_client):
        response = nimble_client.extract(url="https://example.com")
        html = response.data.html
        assert html is not None
        assert "<html" in html.lower()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestLiveSearch:

    def test_search_general_deep(self, nimble_client):
        response = nimble_client.search(
            query="what is a knowledge graph",
            max_results=3,
            focus="general",
            search_depth="deep",
        )
        assert response.results is not None
        assert len(response.results) > 0

        first = response.results[0]
        assert first.title
        assert first.url
        # deep mode should populate content
        assert first.content and len(first.content) > 100

        print(f"\n--- Search: {len(response.results)} results ---")
        for r in response.results:
            print(f"  {r.title[:60]}  ({r.url[:50]})")
            print(f"    content: {len(r.content or '')} chars, description: {len(r.description or '')} chars")

    def test_search_lite(self, nimble_client):
        """Lite mode returns metadata only — content should be empty/minimal."""
        response = nimble_client.search(
            query="python programming",
            max_results=3,
            focus="general",
            search_depth="lite",
        )
        assert len(response.results) > 0
        first = response.results[0]
        assert first.title
        assert first.url
        assert first.description


# ---------------------------------------------------------------------------
# End-to-end: ingest + search_ingest
# ---------------------------------------------------------------------------

class TestLiveIngest:

    def test_ingest_webpage(self, tmp_path):
        from graphify.ingest import ingest
        out = ingest("https://example.com", tmp_path)
        assert out.exists()
        content = out.read_text()
        assert "domain" in content.lower()
        assert "type: webpage" in content
        print(f"\n--- Ingest webpage: {out.name} ({len(content)} chars) ---")

    def test_search_ingest(self, tmp_path):
        from graphify.ingest import search_ingest
        paths = search_ingest("knowledge graph AI", tmp_path, max_results=3)
        assert len(paths) > 0
        for p in paths:
            assert p.exists()
            content = p.read_text()
            assert "type: search_result" in content
            assert "source_url:" in content
            print(f"\n--- Search result: {p.name} ({len(content)} chars) ---")
            # Print first few lines
            for line in content.splitlines()[:8]:
                print(f"  {line}")
