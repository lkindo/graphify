import json
from pathlib import Path

from networkx.readwrite import json_graph

from graphify.build import build, build_from_json, prune_nodes_for_deleted_files
from graphify.detect import detect_incremental

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


# --- prune / --update (deleted source files) ---


def test_detect_incremental_lists_deleted_files(tmp_path):
    """Manifest entries for removed files appear in deleted_files."""
    gone = tmp_path / "gone.py"
    stay = tmp_path / "stay.py"
    gone.write_text("def gone(): pass\n", encoding="utf-8")
    stay.write_text("def stay(): pass\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({str(gone): 1.0, str(stay): 2.0}),
        encoding="utf-8",
    )

    gone.unlink()

    result = detect_incremental(tmp_path, manifest_path=str(manifest_path))
    assert str(gone) in result["deleted_files"]
    assert str(stay) not in result["deleted_files"]


def test_detect_incremental_no_deletions_empty_deleted_files(tmp_path):
    """When manifest matches current files, deleted_files is empty."""
    f = tmp_path / "keep.py"
    f.write_text("def x(): pass\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({str(f): 100.0}), encoding="utf-8")

    result = detect_incremental(tmp_path, manifest_path=str(manifest_path))
    assert result["deleted_files"] == []


def test_prune_after_incremental_matches_detect_paths(tmp_path):
    """deleted_files from detect_incremental removes matching source_file nodes."""
    gone = tmp_path / "gone.py"
    stay = tmp_path / "stay.py"
    gone.write_text("def gone(): pass\n", encoding="utf-8")
    stay.write_text("def stay(): pass\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({str(gone): 1.0, str(stay): 2.0}),
        encoding="utf-8",
    )
    gone.unlink()

    inc = detect_incremental(tmp_path, manifest_path=str(manifest_path))
    deleted = inc["deleted_files"]
    assert deleted

    ext = {
        "nodes": [
            {"id": "n_gone", "label": "gone_fn", "source_file": str(gone)},
            {"id": "n_stay", "label": "stay_fn", "source_file": str(stay)},
        ],
        "edges": [
            {
                "source": "n_gone",
                "target": "n_stay",
                "relation": "calls",
                "confidence": "EXTRACTED",
                "source_file": str(gone),
            }
        ],
        "hyperedges": [],
    }
    G = build_from_json(ext)
    assert prune_nodes_for_deleted_files(G, deleted) == 1
    assert set(G.nodes()) == {"n_stay"}
    assert G.number_of_edges() == 0


def test_prune_then_merge_update_like_skill(tmp_path):
    """Load graph JSON → prune → merge empty extraction (skill order)."""
    gone = tmp_path / "gone.py"
    stay = tmp_path / "stay.py"
    gone.write_text("x=1\n", encoding="utf-8")
    stay.write_text("y=2\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({str(gone): 1.0, str(stay): 2.0}),
        encoding="utf-8",
    )
    gone.unlink()

    inc = detect_incremental(tmp_path, manifest_path=str(manifest_path))

    existing_data = {
        "nodes": [
            {"id": "a", "label": "A", "source_file": str(gone)},
            {"id": "b", "label": "B", "source_file": str(stay)},
        ],
        "links": [],
        "hyperedges": [],
    }
    G_existing = json_graph.node_link_graph(existing_data, edges="links")
    if "hyperedges" in existing_data:
        G_existing.graph["hyperedges"] = list(existing_data["hyperedges"])

    prune_nodes_for_deleted_files(G_existing, inc["deleted_files"])
    G_new = build_from_json({"nodes": [], "edges": [], "hyperedges": []})
    G_existing.update(G_new)

    assert set(G_existing.nodes()) == {"b"}
    assert G_existing.number_of_edges() == 0


def test_prune_removes_nodes_and_incident_edges():
    ext = {
        "nodes": [
            {"id": "x1", "label": "X", "source_file": "gone.py"},
            {"id": "x2", "label": "Y", "source_file": "stay.py"},
        ],
        "edges": [
            {
                "source": "x1",
                "target": "x2",
                "relation": "calls",
                "confidence": "EXTRACTED",
                "source_file": "gone.py",
            },
        ],
        "hyperedges": [],
    }
    G = build_from_json(ext)
    assert prune_nodes_for_deleted_files(G, ["gone.py"]) == 1
    assert "x1" not in G and "x2" in G and G.number_of_edges() == 0


def test_prune_path_normalization():
    p = Path("sub") / "foo.py"
    G = build_from_json(
        {"nodes": [{"id": "a", "label": "A", "source_file": str(p)}], "edges": []}
    )
    assert prune_nodes_for_deleted_files(G, ["sub/foo.py"]) == 1
    assert G.number_of_nodes() == 0


def test_prune_keeps_nodes_without_source_file():
    G = build_from_json(
        {
            "nodes": [
                {"id": "ext", "label": "stdlib", "source_file": ""},
                {"id": "x", "label": "X", "source_file": "gone.py"},
            ],
            "edges": [],
        }
    )
    prune_nodes_for_deleted_files(G, ["gone.py"])
    assert "ext" in G and "x" not in G


def test_prune_hyperedges_when_file_deleted():
    G = build_from_json(
        {
            "nodes": [
                {"id": "A", "label": "A", "source_file": "auth.py"},
                {"id": "B", "label": "B", "source_file": "auth.py"},
                {"id": "C", "label": "C", "source_file": "other.py"},
            ],
            "edges": [],
            "hyperedges": [
                {
                    "id": "h1",
                    "label": "auth",
                    "nodes": ["A", "B", "C"],
                    "source_file": "auth.py",
                }
            ],
        }
    )
    prune_nodes_for_deleted_files(G, ["auth.py"])
    assert G.graph.get("hyperedges") == []
    assert set(G.nodes()) == {"C"}


def test_prune_noop_when_no_deleted_list():
    G = build_from_json(
        {"nodes": [{"id": "a", "label": "A", "source_file": "f.py"}], "edges": []}
    )
    assert prune_nodes_for_deleted_files(G, []) == 0
    assert "a" in G


def test_prune_drops_hyperedge_when_fewer_than_two_nodes_remain():
    G = build_from_json(
        {
            "nodes": [
                {"id": "A", "label": "A", "source_file": "keep.py"},
                {"id": "B", "label": "B", "source_file": "gone.py"},
            ],
            "edges": [],
            "hyperedges": [
                {
                    "id": "h1",
                    "label": "pair",
                    "nodes": ["A", "B"],
                    "source_file": "keep.py",
                }
            ],
        }
    )
    prune_nodes_for_deleted_files(G, ["gone.py"])
    assert G.graph.get("hyperedges") == []


def test_prune_second_call_removes_nothing():
    G = build_from_json(
        {"nodes": [{"id": "a", "label": "A", "source_file": "f.py"}], "edges": []}
    )
    assert prune_nodes_for_deleted_files(G, ["f.py"]) == 1
    assert G.number_of_nodes() == 0
    assert prune_nodes_for_deleted_files(G, ["f.py"]) == 0


def test_prune_deleted_path_not_in_graph_is_safe():
    """Extra paths in deleted_files that do not match any node are ignored."""
    G = build_from_json(
        {"nodes": [{"id": "a", "label": "A", "source_file": "only.py"}], "edges": []}
    )
    assert prune_nodes_for_deleted_files(G, ["missing.py", "only.py"]) == 1
    assert G.number_of_nodes() == 0


def test_prune_multiple_deleted_files_one_call():
    G = build_from_json(
        {
            "nodes": [
                {"id": "a", "label": "A", "source_file": "a.py"},
                {"id": "b", "label": "B", "source_file": "b.py"},
            ],
            "edges": [],
        }
    )
    assert prune_nodes_for_deleted_files(G, ["a.py", "b.py"]) == 2
    assert G.number_of_nodes() == 0
