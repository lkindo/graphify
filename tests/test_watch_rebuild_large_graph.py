"""Regression test: _rebuild_code should not fail when the graph is too
large for HTML visualization. Core products (graph.json, GRAPH_REPORT.md)
must still be written.

Before the fix:
- `to_html` raised ValueError for graphs > MAX_NODES_FOR_VIZ (5000).
- _rebuild_code wrapped everything in one try/except and returned False.
- graph.json was also not written (it happened before to_html but the
  outer exception handler still prevented completion reporting).

After the fix:
- to_html is wrapped in its own try/except.
- graph.json + GRAPH_REPORT.md are always written regardless of size.
- graph.html is silently skipped with a warning when too big.
"""

from pathlib import Path
from unittest.mock import patch

import networkx as nx
import pytest

from graphify.watch import _rebuild_code


def test_rebuild_succeeds_when_html_viz_fails(tmp_path, monkeypatch):
    """Core artifacts must be produced even when to_html raises."""

    # Create a minimal code file so collect_files has something to extract.
    src = tmp_path / "sample.py"
    src.write_text("def f(): return 1\n")

    # Patch graphify.export.to_html at the source module (lazy-imported by watch).
    import graphify.export as export_mod

    def fake_to_html(*args, **kwargs):
        raise ValueError("Graph has 99999 nodes - too large for HTML viz. Use --no-viz or reduce input size.")

    monkeypatch.setattr(export_mod, "to_html", fake_to_html)

    ok = _rebuild_code(tmp_path)
    assert ok is True, "_rebuild_code should succeed even when to_html fails"

    out = tmp_path / "graphify-out"
    assert (out / "graph.json").exists(), "graph.json must always be written"
    assert (out / "GRAPH_REPORT.md").exists(), "GRAPH_REPORT.md must always be written"
    # graph.html should NOT exist when to_html failed.
    assert not (out / "graph.html").exists(), "graph.html should be skipped when to_html raises"


def test_rebuild_still_writes_graph_html_when_viz_succeeds(tmp_path):
    """Normal-sized graphs should still produce graph.html."""
    src = tmp_path / "sample.py"
    src.write_text("def f(): return 1\n")

    ok = _rebuild_code(tmp_path)
    assert ok is True

    out = tmp_path / "graphify-out"
    # All three core products present for a small graph.
    assert (out / "graph.json").exists()
    assert (out / "GRAPH_REPORT.md").exists()
    assert (out / "graph.html").exists(), "graph.html should be written for small graphs"
