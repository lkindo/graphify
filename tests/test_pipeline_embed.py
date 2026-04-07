"""Tests for pipeline embedding integration."""

from pathlib import Path
import tempfile
import json

import pytest

from graphify.pipeline import run_embedding_pass, run_full_pipeline
from graphify.build import build_from_json
from graphify.cluster import cluster


def _make_test_extraction():
    """Create test extraction data for pipeline tests."""
    return {
        "nodes": [
            {
                "id": "n1_validate",
                "label": "validate_input",
                "file_type": "code",
                "source_file": "auth/validators.py",
                "source_location": "L5",
            },
            {
                "id": "n2_check",
                "label": "check_input",
                "file_type": "code",
                "source_file": "api/checks.py",
                "source_location": "L12",
            },
            {
                "id": "n3_sanitize",
                "label": "sanitize_data",
                "file_type": "code",
                "source_file": "utils/sanitize.py",
                "source_location": "L8",
            },
        ],
        "edges": [
            {
                "source": "n1_validate",
                "target": "n2_check",
                "relation": "calls",
                "confidence": "EXTRACTED",
                "source_file": "auth/validators.py",
                "weight": 1.0,
            }
        ],
        "input_tokens": 100,
        "output_tokens": 50,
    }


def _make_test_detection():
    """Create test detection data for pipeline tests."""
    return {
        "files": {
            "code": ["auth/validators.py", "api/checks.py", "utils/sanitize.py"],
            "document": [],
            "paper": [],
            "image": [],
        },
        "total_files": 3,
        "total_words": 500,
    }


def test_run_embedding_pass_disabled():
    """Test that embedding pass returns unchanged graph when disabled."""
    extraction = _make_test_extraction()
    G = build_from_json(extraction)
    communities = cluster(G)

    original_edges = G.number_of_edges()

    G_updated, communities_updated = run_embedding_pass(
        G,
        communities,
        embeddings_flag=False,
    )

    assert G_updated.number_of_edges() == original_edges
    assert communities_updated == communities


def test_run_embedding_pass_enabled():
    """Test that embedding pass adds similarity edges when enabled."""
    extraction = _make_test_extraction()
    G = build_from_json(extraction)
    communities = cluster(G)

    original_edges = G.number_of_edges()

    G_updated, communities_updated = run_embedding_pass(
        G,
        communities,
        embeddings_flag=True,
        embed_threshold=0.1,  # Low threshold to ensure edges are added
        embed_backend="mock",  # Use mock backend for tests
    )

    assert G_updated.number_of_edges() >= original_edges
    # Check that at least one edge is semantically_similar_to
    found_semantic = False
    for _, _, data in G_updated.edges(data=True):
        if data.get("relation") == "semantically_similar_to":
            found_semantic = True
            assert data.get("confidence") == "INFERRED"
            assert "confidence_score" in data
    assert found_semantic


def test_run_full_pipeline_without_embeddings(tmp_path):
    """Test full pipeline execution without embeddings."""
    extraction = _make_test_extraction()
    detection = _make_test_detection()

    result = run_full_pipeline(
        extraction,
        detection,
        root=tmp_path,
        embeddings_flag=False,
    )

    assert "graph" in result
    assert "communities" in result
    assert "report" in result
    assert "analysis" in result
    assert result["graph"].number_of_nodes() == 3
    assert result["graph"].number_of_edges() >= 1

    # Check output files were created
    out_dir = tmp_path / "graphify-out"
    assert out_dir.exists()
    assert (out_dir / "graph.json").exists()
    assert (out_dir / "GRAPH_REPORT.md").exists()
    assert (out_dir / "graph.html").exists()


def test_run_full_pipeline_with_embeddings(tmp_path):
    """Test full pipeline execution with embeddings enabled."""
    extraction = _make_test_extraction()
    detection = _make_test_detection()

    result = run_full_pipeline(
        extraction,
        detection,
        root=tmp_path,
        embeddings_flag=True,
        embed_threshold=0.1,  # Low threshold for test
        embed_backend="mock",  # Use mock backend for tests
    )

    assert "graph" in result
    assert result["graph"].number_of_nodes() == 3

    # Verify semantic edges were added
    semantic_edges = 0
    for _, _, data in result["graph"].edges(data=True):
        if data.get("relation") == "semantically_similar_to":
            semantic_edges += 1

    assert semantic_edges > 0


def test_pipeline_analysis_includes_embedding_edges(tmp_path):
    """Test that pipeline analysis properly handles embedding-generated edges."""
    extraction = _make_test_extraction()
    detection = _make_test_detection()

    result = run_full_pipeline(
        extraction,
        detection,
        root=tmp_path,
        embeddings_flag=True,
        embed_threshold=0.1,
        embed_backend="mock",
    )

    analysis = result["analysis"]

    assert "gods" in analysis
    assert "surprises" in analysis
    assert "questions" in analysis
    assert "graph_nodes" in analysis
    assert "graph_edges" in analysis

    assert analysis["graph_nodes"] == 3
    assert analysis["graph_edges"] >= 1


def test_embedding_cache_in_pipeline(tmp_path):
    """Test that embedding cache is used in pipeline runs."""
    extraction = _make_test_extraction()
    detection = _make_test_detection()

    # First run - should create cache
    result1 = run_full_pipeline(
        extraction,
        detection,
        root=tmp_path,
        embeddings_flag=True,
        embed_threshold=0.1,
        embed_backend="mock",
    )

    # Check cache directory exists
    cache_dir = tmp_path / "graphify-out" / "cache" / "embeddings"
    assert cache_dir.exists()
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) > 0

    # Second run with same data should use cache
    result2 = run_full_pipeline(
        extraction,
        detection,
        root=tmp_path,
        embeddings_flag=True,
        embed_threshold=0.1,
        embed_backend="mock",
    )

    # Results should be consistent
    assert result1["graph"].number_of_nodes() == result2["graph"].number_of_nodes()
    assert result1["graph"].number_of_edges() == result2["graph"].number_of_edges()
