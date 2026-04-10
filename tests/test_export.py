import json
import tempfile
from pathlib import Path
from graphify.build import build_from_json
from graphify.cluster import cluster
from graphify.export import to_json, to_cypher, to_graphml, to_html, to_canvas
from graphify.report import generate as generate_report

FIXTURES = Path(__file__).parent / "fixtures"

def make_graph():
    return build_from_json(json.loads((FIXTURES / "extraction.json").read_text()))

def test_to_json_creates_file():
    G = make_graph()
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.json"
        to_json(G, communities, str(out))
        assert out.exists()

def test_to_json_valid_json():
    G = make_graph()
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.json"
        to_json(G, communities, str(out))
        data = json.loads(out.read_text())
        assert "nodes" in data
        assert "links" in data

def test_to_json_nodes_have_community():
    G = make_graph()
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.json"
        to_json(G, communities, str(out))
        data = json.loads(out.read_text())
        for node in data["nodes"]:
            assert "community" in node

def test_to_cypher_creates_file():
    G = make_graph()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cypher.txt"
        to_cypher(G, str(out))
        assert out.exists()

def test_to_cypher_contains_merge_statements():
    G = make_graph()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cypher.txt"
        to_cypher(G, str(out))
        content = out.read_text()
        assert "MERGE" in content

def test_to_graphml_creates_file():
    G = make_graph()
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.graphml"
        to_graphml(G, communities, str(out))
        assert out.exists()

def test_to_graphml_valid_xml():
    G = make_graph()
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.graphml"
        to_graphml(G, communities, str(out))
        content = out.read_text()
        assert "<graphml" in content
        assert "<node" in content

def test_to_graphml_has_community_attribute():
    G = make_graph()
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.graphml"
        to_graphml(G, communities, str(out))
        content = out.read_text()
        assert "community" in content

def test_to_html_creates_file():
    G = make_graph()
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.html"
        to_html(G, communities, str(out))
        assert out.exists()

def test_to_html_contains_visjs():
    G = make_graph()
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.html"
        to_html(G, communities, str(out))
        content = out.read_text()
        assert "vis-network" in content

def test_to_html_contains_search():
    G = make_graph()
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.html"
        to_html(G, communities, str(out))
        content = out.read_text()
        assert "search" in content.lower()

def test_to_html_contains_legend_with_labels():
    G = make_graph()
    communities = cluster(G)
    labels = {cid: f"Group {cid}" for cid in communities}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.html"
        to_html(G, communities, str(out), community_labels=labels)
        content = out.read_text()
        assert "Group 0" in content

def test_to_html_contains_nodes_and_edges():
    G = make_graph()
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.html"
        to_html(G, communities, str(out))
        content = out.read_text()
        assert "RAW_NODES" in content
        assert "RAW_EDGES" in content


# ── Edge-direction regression tests ──────────────────────────────────────────
#
# graphify stores its working graph as an undirected nx.Graph but stashes
# the extractor's original direction in the _src/_tgt edge attrs. Export
# and display code must route every edge through build.edge_direction()
# to avoid flipping roughly half the edges. These tests exercise the
# round trip: build a graph with many known-direction edges, export,
# and verify every edge comes out the right way round.

def _directed_extraction():
    """Build an extraction where every edge points alphabetically lower to
    higher. Any flip shows up immediately when we scan the exported file."""
    nodes = [
        {"id": f"n{i}", "label": f"Node{i}", "source_file": "t.py", "file_type": "code"}
        for i in range(10)
    ]
    edges = [
        {
            "source": f"n{i}",
            "target": f"n{i + 1}",
            "relation": "calls",
            "confidence": "EXTRACTED",
            "source_file": "t.py",
        }
        for i in range(9)
    ]
    # Add a couple of "backward" edges (higher → lower) to make sure the
    # helper doesn't just normalize everything into alphabetical order.
    edges.append({
        "source": "n9", "target": "n0",
        "relation": "references", "confidence": "EXTRACTED",
        "source_file": "t.py",
    })
    edges.append({
        "source": "n5", "target": "n2",
        "relation": "depends_on", "confidence": "AMBIGUOUS",
        "source_file": "t.py",
    })
    return {"nodes": nodes, "edges": edges}


def test_to_json_preserves_edge_direction():
    G = build_from_json(_directed_extraction())
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.json"
        to_json(G, communities, str(out))
        data = json.loads(out.read_text())

    expected = {(e["source"], e["target"]) for e in _directed_extraction()["edges"]}
    actual = {(link["source"], link["target"]) for link in data["links"]}
    assert expected == actual, f"direction flipped: missing {expected - actual}, extra {actual - expected}"


def test_to_json_strips_internal_direction_attrs():
    """_src / _tgt are an internal workaround — they must not leak to users."""
    G = build_from_json(_directed_extraction())
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.json"
        to_json(G, communities, str(out))
        data = json.loads(out.read_text())
    for link in data["links"]:
        assert "_src" not in link
        assert "_tgt" not in link


def test_to_cypher_preserves_edge_direction():
    G = build_from_json(_directed_extraction())
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cypher.txt"
        to_cypher(G, str(out))
        content = out.read_text()
    expected = {(e["source"], e["target"]) for e in _directed_extraction()["edges"]}
    # Cypher MATCH line: MATCH (a {id: 'SRC'}), (b {id: 'TGT'}) MERGE ...
    import re as _re
    pairs = set(_re.findall(r"MATCH \(a \{id: '([^']+)'\}\), \(b \{id: '([^']+)'\}\)", content))
    assert expected == pairs, f"direction flipped: missing {expected - pairs}, extra {pairs - expected}"


def test_to_html_preserves_edge_direction():
    G = build_from_json(_directed_extraction())
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.html"
        to_html(G, communities, str(out))
        content = out.read_text()
    # The vis.js edge list is embedded as JSON assigned to RAW_EDGES.
    import re as _re
    m = _re.search(r"RAW_EDGES\s*=\s*(\[.*?\]);", content, _re.DOTALL)
    assert m is not None, "RAW_EDGES not found in HTML output"
    vis_edges = json.loads(m.group(1))
    expected = {(e["source"], e["target"]) for e in _directed_extraction()["edges"]}
    actual = {(e["from"], e["to"]) for e in vis_edges}
    assert expected == actual, f"direction flipped: missing {expected - actual}, extra {actual - expected}"


def test_to_canvas_preserves_edge_direction():
    G = build_from_json(_directed_extraction())
    communities = cluster(G)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.canvas"
        to_canvas(G, communities, str(out))
        data = json.loads(out.read_text())
    expected = {(e["source"], e["target"]) for e in _directed_extraction()["edges"]}
    # Canvas edges use fromNode/toNode with "n_" prefix.
    actual = {
        (e["fromNode"][2:], e["toNode"][2:])
        for e in data["edges"]
    }
    assert expected == actual, f"direction flipped: missing {expected - actual}, extra {actual - expected}"


def test_report_ambiguous_edges_preserve_direction():
    G = build_from_json(_directed_extraction())
    communities = cluster(G)
    # The fixture has one AMBIGUOUS edge: n5 → n2.
    md = generate_report(
        G=G,
        communities=communities,
        cohesion_scores={},
        community_labels={},
        god_node_list=[],
        surprise_list=[],
        detection_result={"total_files": 1, "total_words": 100},
        token_cost={"input": 0, "output": 0},
        root="test",
    )
    # Report renders as `src_label` → `tgt_label`. Node5's label is "Node5".
    assert "`Node5` → `Node2`" in md
    assert "`Node2` → `Node5`" not in md
