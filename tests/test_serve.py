"""Tests for serve.py - MCP graph query helpers (no mcp package required)."""
import json
import pytest
import networkx as nx
from networkx.readwrite import json_graph

from graphify.serve import (
    _communities_from_graph,
    _find_node,
    _score_nodes,
    _strip_diacritics,
    _bfs,
    _dfs,
    _subgraph_to_text,
    _load_graph,
)


def _make_graph() -> nx.Graph:
    G = nx.Graph()
    G.add_node("n1", label="extract", source_file="extract.py", source_location="L10", community=0)
    G.add_node("n2", label="cluster", source_file="cluster.py", source_location="L5", community=0)
    G.add_node("n3", label="build", source_file="build.py", source_location="L1", community=1)
    G.add_node("n4", label="report", source_file="report.py", source_location="L1", community=1)
    G.add_node("n5", label="isolated", source_file="other.py", source_location="L1", community=2)
    G.add_edge("n1", "n2", relation="calls", confidence="INFERRED")
    G.add_edge("n2", "n3", relation="imports", confidence="EXTRACTED")
    G.add_edge("n3", "n4", relation="uses", confidence="EXTRACTED")
    return G


# --- _communities_from_graph ---

def test_communities_from_graph_basic():
    G = _make_graph()
    communities = _communities_from_graph(G)
    assert 0 in communities
    assert 1 in communities
    assert "n1" in communities[0]
    assert "n2" in communities[0]
    assert "n3" in communities[1]

def test_communities_from_graph_no_community_attr():
    G = nx.Graph()
    G.add_node("a", label="foo")  # no community attr
    communities = _communities_from_graph(G)
    assert communities == {}

def test_communities_from_graph_isolated():
    G = _make_graph()
    communities = _communities_from_graph(G)
    assert 2 in communities
    assert "n5" in communities[2]


# --- _score_nodes ---

def test_score_nodes_exact_label_match():
    G = _make_graph()
    scored = _score_nodes(G, ["extract"])
    nids = [nid for _, nid in scored]
    assert "n1" in nids
    assert scored[0][1] == "n1"  # highest score first

def test_score_nodes_no_match():
    G = _make_graph()
    scored = _score_nodes(G, ["xyzzy"])
    assert scored == []

def test_score_nodes_source_file_partial():
    G = _make_graph()
    # "cluster.py" contains "cluster" - should score 0.5 for source match
    scored = _score_nodes(G, ["cluster"])
    nids = [nid for _, nid in scored]
    assert "n2" in nids


# --- _bfs ---

def test_bfs_depth_1():
    G = _make_graph()
    visited, edges = _bfs(G, ["n1"], depth=1)
    assert "n1" in visited
    assert "n2" in visited  # direct neighbor
    assert "n3" not in visited  # 2 hops away

def test_bfs_depth_2():
    G = _make_graph()
    visited, edges = _bfs(G, ["n1"], depth=2)
    assert "n3" in visited  # n1 -> n2 -> n3

def test_bfs_disconnected():
    G = _make_graph()
    visited, edges = _bfs(G, ["n5"], depth=3)
    assert visited == {"n5"}  # isolated node

def test_bfs_returns_edges():
    G = _make_graph()
    visited, edges = _bfs(G, ["n1"], depth=1)
    assert len(edges) >= 1
    assert any(u == "n1" or v == "n1" for u, v in edges)


# --- _dfs ---

def test_dfs_depth_1():
    G = _make_graph()
    visited, edges = _dfs(G, ["n1"], depth=1)
    assert "n1" in visited
    assert "n2" in visited
    assert "n3" not in visited

def test_dfs_full_chain():
    G = _make_graph()
    visited, edges = _dfs(G, ["n1"], depth=5)
    assert {"n1", "n2", "n3", "n4"}.issubset(visited)


# --- _subgraph_to_text ---

def test_subgraph_to_text_contains_labels():
    G = _make_graph()
    text = _subgraph_to_text(G, {"n1", "n2"}, [("n1", "n2")])
    assert "extract" in text
    assert "cluster" in text

def test_subgraph_to_text_truncates():
    G = _make_graph()
    # Very small budget forces truncation
    text = _subgraph_to_text(G, {"n1", "n2", "n3", "n4"}, [("n1", "n2")], token_budget=1)
    assert "truncated" in text

def test_subgraph_to_text_edge_included():
    G = _make_graph()
    text = _subgraph_to_text(G, {"n1", "n2"}, [("n1", "n2")])
    assert "EDGE" in text
    assert "calls" in text


# --- _load_graph ---

def test_load_graph_roundtrip(tmp_path):
    G = _make_graph()
    data = json_graph.node_link_data(G, edges="links")
    p = tmp_path / "graph.json"
    p.write_text(json.dumps(data))
    G2 = _load_graph(str(p))
    assert G2.number_of_nodes() == G.number_of_nodes()
    assert G2.number_of_edges() == G.number_of_edges()

def test_load_graph_missing_file(tmp_path):
    graphify_dir = tmp_path / "graphify-out"
    graphify_dir.mkdir()
    with pytest.raises(SystemExit):
        _load_graph(str(graphify_dir / "nonexistent.json"))


# --- diacritic-insensitive scoring via norm_label ---

def _make_diacritic_graph(with_norm: bool = True) -> nx.Graph:
    """Graph with diacritic labels.  with_norm=True simulates a rebuilt graph."""
    G = nx.Graph()
    attrs = {"source_location": None, "community": 5}
    G.add_node("d1", label="Přehled základních cvičení",
               source_file="docs/zakladni-cviceni.md", **attrs)
    G.add_node("d2", label="Tréninkový plán",
               source_file="docs/treninkovy-plan.md", **attrs)
    G.add_node("d3", label="Préparation du résumé",
               source_file="notes/preparation-resume.md",
               community=1, source_location=None)
    if with_norm:
        for nid, d in G.nodes(data=True):
            d["norm_label"] = _strip_diacritics(d["label"]).lower()
    G.add_edge("d1", "d2", relation="related", confidence="INFERRED")
    return G


# --- _strip_diacritics (fallback helper) ---

def test_strip_diacritics_polish():
    assert _strip_diacritics("ćwiczenia") == "cwiczenia"
    assert _strip_diacritics("ćwiczenia z lukami") == "cwiczenia z lukami"

def test_strip_diacritics_french():
    assert _strip_diacritics("résumé") == "resume"

def test_strip_diacritics_ascii_passthrough():
    assert _strip_diacritics("hello world") == "hello world"
    assert _strip_diacritics("") == ""


# --- _score_nodes with norm_label ---

def test_score_nodes_ascii_matches_diacritic_label():
    """ASCII query 'prehled cviceni' matches norm_label from 'Přehled základních cvičení'."""
    G = _make_diacritic_graph()
    scored = _score_nodes(G, ["prehled", "cviceni"])
    nids = [nid for _, nid in scored]
    assert "d1" in nids
    assert scored[0][1] == "d1"

def test_score_nodes_diacritic_query_still_works():
    G = _make_diacritic_graph()
    scored = _score_nodes(G, ["přehled"])
    assert any(nid == "d1" for _, nid in scored)

def test_score_nodes_french_diacritics():
    G = _make_diacritic_graph()
    scored = _score_nodes(G, ["resume"])
    assert any(nid == "d3" for _, nid in scored)

def test_score_nodes_fallback_without_norm_label():
    """Old graphs without norm_label still get diacritic matching via fallback."""
    G = _make_diacritic_graph(with_norm=False)
    scored = _score_nodes(G, ["prehled"])
    assert any(nid == "d1" for _, nid in scored)


# --- _find_node with norm_label ---

def test_find_node_ascii_query():
    G = _make_diacritic_graph()
    assert "d1" in _find_node(G, "prehled")

def test_find_node_diacritic_query():
    G = _make_diacritic_graph()
    assert "d1" in _find_node(G, "přehled")

def test_find_node_fallback_without_norm_label():
    G = _make_diacritic_graph(with_norm=False)
    assert "d1" in _find_node(G, "prehled")


# --- _subgraph_to_text relevance ordering ---

def test_subgraph_to_text_relevance_ordering():
    G = _make_diacritic_graph()
    scores = {"d1": 2.0, "d2": 0.5}
    text = _subgraph_to_text(G, {"d1", "d2"}, [], node_scores=scores)
    lines = text.strip().split("\n")
    d1_pos = next(i for i, l in enumerate(lines) if "Přehled" in l)
    d2_pos = next(i for i, l in enumerate(lines) if "Tréninkový" in l)
    assert d1_pos < d2_pos

def test_subgraph_to_text_no_scores_falls_back_to_degree():
    G = _make_diacritic_graph()
    text = _subgraph_to_text(G, {"d1", "d2"}, [])
    assert "NODE" in text
