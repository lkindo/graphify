"""Tests for community summary generation."""
import networkx as nx
import pytest
from graphify.summarize import (
    extractive_summary,
    summarize_community,
    summarize_all_communities,
)


def _make_graph() -> nx.Graph:
    G = nx.Graph()
    G.add_node("n1", label="Transformer", source_file="model.py")
    G.add_node("n2", label="MultiHeadAttention", source_file="model.py")
    G.add_node("n3", label="LayerNorm", source_file="model.py")
    G.add_node("n4", label="attention mechanism", source_file="paper.md")
    G.add_edge("n1", "n2", relation="contains")
    G.add_edge("n1", "n3", relation="contains")
    G.add_edge("n2", "n4", relation="implements")
    return G


def test_extractive_summary_contains_labels():
    G = _make_graph()
    summary = extractive_summary(G, ["n1", "n2", "n3"])
    assert "Transformer" in summary
    assert "MultiHeadAttention" in summary


def test_extractive_summary_contains_relations():
    G = _make_graph()
    summary = extractive_summary(G, ["n1", "n2", "n3"])
    assert "contains" in summary


def test_extractive_summary_contains_sources():
    G = _make_graph()
    summary = extractive_summary(G, ["n1", "n2", "n3"])
    assert "model.py" in summary


def test_extractive_summary_empty_community():
    G = _make_graph()
    summary = extractive_summary(G, [])
    assert summary == "Empty community."


def test_extractive_summary_single_node():
    G = _make_graph()
    summary = extractive_summary(G, ["n4"])
    assert "attention mechanism" in summary


def test_extractive_summary_respects_max_nodes():
    G = _make_graph()
    summary = extractive_summary(G, ["n1", "n2", "n3", "n4"], max_nodes=2)
    # Should mention "+N more"
    assert "+2 more" in summary


def test_summarize_community_default_backend():
    G = _make_graph()
    summary = summarize_community(G, ["n1", "n2"])
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_summarize_community_invalid_backend():
    G = _make_graph()
    with pytest.raises(ValueError, match="Unknown summary backend"):
        summarize_community(G, ["n1"], backend="nonexistent")


def test_summarize_all_communities():
    G = _make_graph()
    communities = {0: ["n1", "n2", "n3"], 1: ["n4"]}
    summaries = summarize_all_communities(G, communities)
    assert set(summaries.keys()) == {0, 1}
    assert all(isinstance(v, str) for v in summaries.values())
    assert "Transformer" in summaries[0]
    assert "attention mechanism" in summaries[1]
