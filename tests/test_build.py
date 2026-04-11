import json
from pathlib import Path
from graphify.build import build_from_json, build

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


def test_build_from_json_with_links_key():
    """NetworkX <= 3.1 used "links" as the edge key in node_link_data().
    build_from_json() must accept "links" as a fallback for "edges" so that
    data produced by older NetworkX versions (or any serialiser that uses
    "links") is handled correctly."""
    data = {
        "directed": False, "multigraph": False, "graph": {},
        "nodes": [{"id": "n1"}, {"id": "n2"}],
        "links": [{"source": "n1", "target": "n2"}],  # old NetworkX key
    }
    built = build_from_json(data)
    assert built.number_of_nodes() == 2
    assert built.number_of_edges() == 1     # was 0 before the fix


def test_build_from_json_with_edges_key():
    """NetworkX >= 3.2 uses "edges" as the default key — must still work."""
    import networkx as nx
    G = nx.Graph()
    G.add_node("n1", label="A")
    G.add_node("n2", label="B")
    G.add_edge("n1", "n2")
    nx_data = nx.node_link_data(G)
    built = build_from_json(nx_data)
    assert built.number_of_nodes() == 2
    assert built.number_of_edges() == 1
