"""Tests for issue #52 fixes: large-scale project robustness.

Sub-issue 1: tree-sitter version mismatch gives clear error message
Sub-issue 5: sample_for_viz reduces large graphs for HTML visualization
Sub-issue 8: extract() logs progress for large file batches
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import patch

import networkx as nx
import pytest

from graphify.export import (
    MAX_NODES_FOR_VIZ,
    sample_for_viz,
    to_html,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_large_graph(n_communities: int = 25, nodes_per: int = 60) -> tuple[
    nx.Graph, dict[int, list[str]], dict[int, str]
]:
    """Build a graph that exceeds MAX_NODES_FOR_VIZ when n_communities * nodes_per > 5000."""
    G = nx.Graph()
    communities: dict[int, list[str]] = {}
    labels: dict[int, str] = {}
    for cid in range(n_communities):
        members = []
        for j in range(nodes_per):
            node_id = f"c{cid}_n{j}"
            G.add_node(node_id, label=f"Node {cid}-{j}", file_type="code", source_file=f"f{cid}.py")
            members.append(node_id)
        # Connect nodes within community
        for j in range(nodes_per - 1):
            G.add_edge(members[j], members[j + 1], relation="calls", confidence="EXTRACTED")
        communities[cid] = members
        labels[cid] = f"Community {cid}"
    return G, communities, labels


def _make_small_graph() -> tuple[nx.Graph, dict[int, list[str]], dict[int, str]]:
    """Build a small graph well under the viz limit."""
    G = nx.Graph()
    G.add_node("a", label="Alpha", file_type="code", source_file="a.py")
    G.add_node("b", label="Beta", file_type="code", source_file="b.py")
    G.add_node("c", label="Gamma", file_type="code", source_file="c.py")
    G.add_edge("a", "b", relation="calls", confidence="EXTRACTED")
    G.add_edge("b", "c", relation="imports", confidence="EXTRACTED")
    communities = {0: ["a", "b"], 1: ["c"]}
    labels = {0: "Core", 1: "Docs"}
    return G, communities, labels


# ---------------------------------------------------------------------------
# Sub-issue 1: tree-sitter version mismatch error message
# ---------------------------------------------------------------------------

def test_tree_sitter_version_mismatch_error_message():
    """When Language() raises TypeError (version mismatch), the error should
    contain a helpful upgrade hint."""
    from graphify.extract import _extract_generic, LanguageConfig

    config = LanguageConfig(
        ts_module="tree_sitter_python",
        ts_language_fn="language",
    )

    # Simulate tree-sitter version mismatch: Language() raises TypeError
    # Language is imported inside _extract_generic via `from tree_sitter import Language`
    def raise_type_error(*args, **kwargs):
        raise TypeError("missing 1 required positional argument: 'name'")

    import types
    fake_ts = types.ModuleType("tree_sitter")
    fake_ts.Language = raise_type_error
    fake_ts.Parser = None

    with patch("graphify.extract.importlib.import_module") as mock_import:
        mock_mod = type("FakeMod", (), {"language": lambda: None})()
        mock_import.return_value = mock_mod

        with patch.dict(sys.modules, {"tree_sitter": fake_ts}):
            result = _extract_generic(Path("test.py"), config)

    assert "error" in result
    assert "tree-sitter version mismatch" in result["error"]
    assert "pip install --upgrade" in result["error"]


# ---------------------------------------------------------------------------
# Sub-issue 5: sample_for_viz
# ---------------------------------------------------------------------------

def test_sample_for_viz_reduces_node_count():
    """sample_for_viz should produce a subgraph under MAX_NODES_FOR_VIZ."""
    G, communities, labels = _make_large_graph(n_communities=30, nodes_per=200)
    assert G.number_of_nodes() > MAX_NODES_FOR_VIZ

    sampled_G, sampled_comm = sample_for_viz(G, communities)
    assert sampled_G.number_of_nodes() <= MAX_NODES_FOR_VIZ
    assert sampled_G.number_of_nodes() > 0


def test_sample_for_viz_keeps_top_communities():
    """Sampled result should contain the largest communities."""
    G, communities, labels = _make_large_graph(n_communities=30, nodes_per=200)

    sampled_G, sampled_comm = sample_for_viz(G, communities, max_communities=5)
    assert len(sampled_comm) == 5


def test_sample_for_viz_picks_highest_degree_nodes():
    """Within a community, the highest-degree nodes should be selected."""
    G = nx.Graph()
    members = []
    for i in range(100):
        nid = f"n{i}"
        G.add_node(nid, label=f"Node{i}", file_type="code", source_file="f.py")
        members.append(nid)
    # Make n0 a hub connected to all others
    for i in range(1, 100):
        G.add_edge("n0", f"n{i}", relation="calls", confidence="EXTRACTED")

    communities = {0: members}

    sampled_G, sampled_comm = sample_for_viz(G, communities, nodes_per_community=10)
    # n0 (degree 99) must be in the sample
    assert "n0" in sampled_comm[0]
    assert len(sampled_comm[0]) == 10


def test_to_html_sample_mode_no_error(tmp_path):
    """to_html with sample=True should succeed on large graphs instead of raising."""
    G, communities, labels = _make_large_graph(n_communities=30, nodes_per=200)
    assert G.number_of_nodes() > MAX_NODES_FOR_VIZ

    out = tmp_path / "graph.html"
    to_html(G, communities, str(out), community_labels=labels, sample=True)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "vis-network" in content or "vis.js" in content


def test_to_html_raises_without_sample():
    """to_html without sample=True should raise ValueError on large graphs."""
    G, communities, labels = _make_large_graph(n_communities=30, nodes_per=200)
    with pytest.raises(ValueError, match="too large"):
        to_html(G, communities, "out.html", community_labels=labels, sample=False)


def test_to_html_small_graph_no_sample_needed(tmp_path):
    """Small graphs should work without sample flag."""
    G, communities, labels = _make_small_graph()
    out = tmp_path / "graph.html"
    to_html(G, communities, str(out), community_labels=labels)
    assert out.exists()


# ---------------------------------------------------------------------------
# Sub-issue 8: extraction progress logging
# ---------------------------------------------------------------------------

def test_extract_logs_progress_for_large_batches(tmp_path, caplog):
    """extract() should log progress when processing >= 100 files."""
    from graphify.extract import extract

    # Create 150 tiny Python files
    files = []
    for i in range(150):
        f = tmp_path / f"mod_{i}.py"
        f.write_text(f"def func_{i}(): pass\n")
        files.append(f)

    with caplog.at_level(logging.INFO, logger="graphify.extract"):
        result = extract(files)

    assert "nodes" in result
    # Should have logged at least one progress message
    progress_msgs = [r for r in caplog.records if "Extraction progress" in r.message]
    assert len(progress_msgs) >= 1


def test_extract_no_progress_for_small_batches(tmp_path, caplog):
    """extract() should not log progress for small batches (< 100 files)."""
    from graphify.extract import extract

    files = []
    for i in range(5):
        f = tmp_path / f"mod_{i}.py"
        f.write_text(f"def func_{i}(): pass\n")
        files.append(f)

    with caplog.at_level(logging.INFO, logger="graphify.extract"):
        result = extract(files)

    assert "nodes" in result
    progress_msgs = [r for r in caplog.records if "Extraction progress" in r.message]
    assert len(progress_msgs) == 0
