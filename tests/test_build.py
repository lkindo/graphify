import json
from pathlib import Path
from graphify.build import build_from_json, build, prune_deleted_nodes

FIXTURES = Path(__file__).parent / "fixtures"

def load_extraction():
    return json.loads((FIXTURES / "extraction.json").read_text())

def test_build_from_json_node_count():
    G = build_from_json(load_extraction())
    assert G.number_of_nodes() == 4

def test_build_from_json_edge_count():
    G = build_from_json(load_extraction())
    assert G.number_of_edges() == 4

def test_nodes_have_label():
    G = build_from_json(load_extraction())
    assert G.nodes["n_transformer"]["label"] == "Transformer"

def test_edges_have_confidence():
    G = build_from_json(load_extraction())
    data = G.edges["n_attention", "n_concept_attn"]
    assert data["confidence"] == "INFERRED"

def test_ambiguous_edge_preserved():
    G = build_from_json(load_extraction())
    data = G.edges["n_layernorm", "n_concept_attn"]
    assert data["confidence"] == "AMBIGUOUS"

def test_build_merges_multiple_extractions():
    ext1 = {"nodes": [{"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"}],
            "edges": [], "input_tokens": 0, "output_tokens": 0}
    ext2 = {"nodes": [{"id": "n2", "label": "B", "file_type": "document", "source_file": "b.md"}],
            "edges": [{"source": "n1", "target": "n2", "relation": "references",
                       "confidence": "INFERRED", "source_file": "b.md", "weight": 1.0}],
            "input_tokens": 0, "output_tokens": 0}
    G = build([ext1, ext2])
    assert G.number_of_nodes() == 2
    assert G.number_of_edges() == 1


def test_prune_deleted_nodes_removes_matching():
    ext = {"nodes": [
        {"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"},
        {"id": "n2", "label": "B", "file_type": "code", "source_file": "b.py"},
    ], "edges": [], "input_tokens": 0, "output_tokens": 0}
    G = build_from_json(ext)
    count = prune_deleted_nodes(G, ["a.py"])
    assert count == 1
    assert "n1" not in G.nodes
    assert "n2" in G.nodes


def test_prune_deleted_nodes_removes_connected_edges():
    ext = {"nodes": [
        {"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"},
        {"id": "n2", "label": "B", "file_type": "code", "source_file": "b.py"},
    ], "edges": [
        {"source": "n1", "target": "n2", "relation": "calls",
         "confidence": "EXTRACTED", "source_file": "a.py", "weight": 1.0},
    ], "input_tokens": 0, "output_tokens": 0}
    G = build_from_json(ext)
    prune_deleted_nodes(G, ["a.py"])
    assert G.number_of_edges() == 0


def test_prune_deleted_nodes_returns_count():
    ext = {"nodes": [
        {"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"},
        {"id": "n2", "label": "B", "file_type": "code", "source_file": "a.py"},
    ], "edges": [], "input_tokens": 0, "output_tokens": 0}
    G = build_from_json(ext)
    assert prune_deleted_nodes(G, ["a.py"]) == 2


def test_prune_deleted_nodes_empty_list_is_noop():
    ext = {"nodes": [
        {"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"},
    ], "edges": [], "input_tokens": 0, "output_tokens": 0}
    G = build_from_json(ext)
    count = prune_deleted_nodes(G, [])
    assert count == 0
    assert G.number_of_nodes() == 1
