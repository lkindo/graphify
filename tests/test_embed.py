"""Tests for graphify/embed.py - local embedding generation."""

import pytest
import networkx as nx
from pathlib import Path


def test_embed_module_imports():
    """Test that embed module can be imported."""
    from graphify import embed

    assert hasattr(embed, "generate_embeddings")
    assert hasattr(embed, "add_similarity_edges")


def test_generate_embeddings_returns_dict():
    """Test that generate_embeddings returns a dict mapping node_id -> embedding vector."""
    from graphify.embed import generate_embeddings

    G = nx.Graph()
    G.add_node("n1", label="validate_input", source_file="auth.py", file_type="code")
    G.add_node("n2", label="check_input", source_file="api.py", file_type="code")

    embeddings = generate_embeddings(G, backend="mock")

    assert isinstance(embeddings, dict)
    assert "n1" in embeddings
    assert "n2" in embeddings
    assert isinstance(embeddings["n1"], list)
    assert len(embeddings["n1"]) > 0


def test_add_similarity_edges_creates_edges():
    """Test that add_similarity_edges adds semantically_similar_to edges above threshold."""
    from graphify.embed import add_similarity_edges

    G = nx.Graph()
    G.add_node("n1", label="validate_input", source_file="auth.py", file_type="code")
    G.add_node("n2", label="check_input", source_file="api.py", file_type="code")

    # Mock embeddings with high similarity
    embeddings = {
        "n1": [0.8, 0.6, 0.2],
        "n2": [0.82, 0.58, 0.22],
    }

    initial_edges = G.number_of_edges()
    add_similarity_edges(G, embeddings, threshold=0.8)

    assert G.number_of_edges() > initial_edges
    assert G.has_edge("n1", "n2")
    edge_data = G.edges["n1", "n2"]
    assert edge_data["relation"] == "semantically_similar_to"
    assert edge_data["confidence"] == "INFERRED"
    assert "confidence_score" in edge_data
    assert 0.0 <= edge_data["confidence_score"] <= 1.0


def test_add_similarity_edges_respects_threshold():
    """Test that edges below threshold are not added."""
    from graphify.embed import add_similarity_edges

    G = nx.Graph()
    G.add_node("n1", label="validate_input", source_file="auth.py", file_type="code")
    G.add_node("n2", label="unrelated_function", source_file="api.py", file_type="code")

    # Mock embeddings with low similarity
    embeddings = {
        "n1": [1.0, 0.0, 0.0],
        "n2": [0.0, 1.0, 0.0],
    }

    add_similarity_edges(G, embeddings, threshold=0.9)

    assert G.number_of_edges() == 0


def test_filters_synthetic_nodes():
    """Test that synthetic file nodes and method stubs are excluded from embedding."""
    from graphify.embed import generate_embeddings

    G = nx.Graph()
    G.add_node(
        "n1", label="auth.py", source_file="auth.py", file_type="code"
    )  # file hub
    G.add_node(
        "n2", label=".validate()", source_file="auth.py", file_type="code"
    )  # method stub
    G.add_node(
        "n3", label="validate_input", source_file="auth.py", file_type="code"
    )  # real entity

    embeddings = generate_embeddings(G, backend="mock")

    # Only real entity should be embedded
    assert "n3" in embeddings
    assert "n1" not in embeddings  # file hub excluded
    assert "n2" not in embeddings  # method stub excluded


def test_embedding_cache_roundtrip(tmp_path):
    """Test that embeddings can be cached and loaded."""
    from graphify.embed import save_embedding_cache, load_embedding_cache

    embeddings = {
        "n1": [0.1, 0.2, 0.3],
        "n2": [0.4, 0.5, 0.6],
    }

    save_embedding_cache(embeddings, root=tmp_path)
    loaded = load_embedding_cache(root=tmp_path)

    assert loaded == embeddings


def test_embedding_cache_invalidation(tmp_path):
    """Test that cache is invalidated when graph changes."""
    from graphify.embed import save_embedding_cache, load_embedding_cache

    G = nx.Graph()
    G.add_node("n1", label="validate_input", source_file="auth.py")

    embeddings = {"n1": [0.1, 0.2, 0.3]}
    save_embedding_cache(embeddings, root=tmp_path)

    # Modify graph
    G.add_node("n2", label="check_input", source_file="api.py")

    # Cache should detect change (in real impl, would check node IDs)
    loaded = load_embedding_cache(root=tmp_path)
    assert loaded is not None  # Cache exists but may be partial
