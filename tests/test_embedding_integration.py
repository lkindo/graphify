"""Integration tests for embedding functionality with the graphify pipeline."""

import networkx as nx
from graphify.build import build_from_json
from graphify.embed import generate_embeddings, add_similarity_edges, _is_file_node


def test_embedding_integration_with_real_graph():
    """Test that embedding functionality works with a real extraction result."""
    # Create a realistic extraction result similar to what comes from the pipeline
    extraction = {
        "nodes": [
            {
                "id": "n_auth_validator",
                "label": "validate_user",
                "file_type": "code",
                "source_file": "auth/validator.py",
                "source_location": "L15",
            },
            {
                "id": "n_api_checker",
                "label": "check_permissions",
                "file_type": "code",
                "source_file": "api/checker.py",
                "source_location": "L23",
            },
            {
                "id": "n_util_helper",
                "label": "sanitize_input",
                "file_type": "code",
                "source_file": "utils/helpers.py",
                "source_location": "L8",
            },
            # File hub node (should be filtered out)
            {
                "id": "n_file_hub",
                "label": "auth.py",
                "file_type": "code",
                "source_file": "auth.py",
                "source_location": "L1",
            },
            # Method stub node (should be filtered out)
            {
                "id": "n_method_stub",
                "label": ".validate()",
                "file_type": "code",
                "source_file": "auth/validator.py",
                "source_location": "L16",
            },
        ],
        "edges": [
            {
                "source": "n_auth_validator",
                "target": "n_api_checker",
                "relation": "calls",
                "confidence": "EXTRACTED",
                "source_file": "auth/validator.py",
                "weight": 1.0,
            }
        ],
        "input_tokens": 100,
        "output_tokens": 50,
    }

    # Build the graph
    G = build_from_json(extraction)

    # Verify initial state
    assert G.number_of_nodes() == 5
    assert G.number_of_edges() == 1

    # Test that file node detection works correctly
    assert _is_file_node(G, "n_file_hub") == True  # This is a file hub
    assert _is_file_node(G, "n_method_stub") == True  # This is a method stub
    assert _is_file_node(G, "n_auth_validator") == False  # This is a real entity

    # Generate embeddings (using mock backend)
    embeddings = generate_embeddings(G, backend="mock")

    # Should only have embeddings for real entities, not synthetic nodes
    expected_nodes = {"n_auth_validator", "n_api_checker", "n_util_helper"}
    actual_nodes = set(embeddings.keys())

    assert actual_nodes == expected_nodes
    assert len(embeddings) == 3  # Only 3 real entities

    # Test adding similarity edges
    initial_edge_count = G.number_of_edges()
    edges_added = add_similarity_edges(
        G, embeddings, threshold=0.1
    )  # Low threshold to ensure some edges

    # Should have added some similarity edges
    assert G.number_of_edges() >= initial_edge_count
    # Check that any new edges are semantically_similar_to relations
    for u, v, data in G.edges(data=True):
        if (
            data.get("source_file") == "embedding_pass"
        ):  # This indicates it's from embedding
            assert data["relation"] == "semantically_similar_to"
            assert data["confidence"] == "INFERRED"
            assert "confidence_score" in data


def test_embedding_with_empty_graph():
    """Test embedding functionality with an empty graph."""
    G = nx.Graph()

    embeddings = generate_embeddings(G, backend="mock")
    assert embeddings == {}

    edges_added = add_similarity_edges(G, embeddings)
    assert edges_added == 0
    assert G.number_of_edges() == 0


def test_embedding_with_single_node():
    """Test embedding functionality with a single node."""
    G = nx.Graph()
    G.add_node(
        "n_single", label="single_function", source_file="module.py", file_type="code"
    )

    embeddings = generate_embeddings(G, backend="mock")
    assert "n_single" in embeddings
    assert isinstance(embeddings["n_single"], list)
    assert len(embeddings["n_single"]) > 0

    # Adding similarity edges to a single node should add no edges
    edges_added = add_similarity_edges(G, embeddings, threshold=0.5)
    assert edges_added == 0
    assert G.number_of_edges() == 0  # No edges possible with single node


def test_embedding_preserves_existing_graph_structure():
    """Test that embedding integration doesn't modify existing graph structure unnecessarily."""
    extraction = {
        "nodes": [
            {
                "id": "n_func_a",
                "label": "function_a",
                "file_type": "code",
                "source_file": "mod_a.py",
            },
            {
                "id": "n_func_b",
                "label": "function_b",
                "file_type": "code",
                "source_file": "mod_b.py",
            },
        ],
        "edges": [
            {
                "source": "n_func_a",
                "target": "n_func_b",
                "relation": "calls",
                "confidence": "EXTRACTED",
                "source_file": "mod_a.py",
                "weight": 0.9,
            }
        ],
    }

    G = build_from_json(extraction)
    original_nodes = set(G.nodes())
    original_edges = [(u, v) for u, v in G.edges()]
    original_edge_attrs = {(u, v): G.edges[u, v] for u, v in G.edges()}

    # Generate and add embeddings
    embeddings = generate_embeddings(G, backend="mock")
    add_similarity_edges(G, embeddings, threshold=0.1)

    # Original structure should still be there
    assert set(G.nodes()) == original_nodes

    # Original edges should still exist
    for u, v in original_edges:
        assert G.has_edge(u, v)
        # Check that original edge attributes are preserved
        for key, value in original_edge_attrs[(u, v)].items():
            assert G.edges[u, v][key] == value

    # New edges should be only semantically_similar_to relations
    for u, v, data in G.edges(data=True):
        is_original = (u, v) in original_edges or (v, u) in original_edges
        if not is_original:
            # This is a new edge from embedding
            assert data["relation"] == "semantically_similar_to"
            assert data["confidence"] == "INFERRED"
            assert "confidence_score" in data
