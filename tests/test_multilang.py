"""Tests for multi-language AST extraction: JS/TS, Go, Rust."""
from __future__ import annotations
import shutil
from pathlib import Path
import pytest
from graphify.extract import extract_js, extract_go, extract_rust, extract

FIXTURES = Path(__file__).parent / "fixtures"


# ── helpers ──────────────────────────────────────────────────────────────────

def _labels(result):
    return [n["label"] for n in result["nodes"]]

def _call_pairs(result):
    node_by_id = {n["id"]: n["label"] for n in result["nodes"]}
    return {
        (node_by_id.get(e["source"], e["source"]), node_by_id.get(e["target"], e["target"]))
        for e in result["edges"] if e["relation"] == "calls"
    }

def _confidences(result):
    return {e["confidence"] for e in result["edges"]}


# ── TypeScript ────────────────────────────────────────────────────────────────

def test_ts_finds_class():
    r = extract_js(FIXTURES / "sample.ts")
    assert "error" not in r
    assert "HttpClient" in _labels(r)

def test_ts_finds_methods():
    r = extract_js(FIXTURES / "sample.ts")
    labels = _labels(r)
    assert any("get" in l for l in labels)
    assert any("post" in l for l in labels)

def test_ts_finds_function():
    r = extract_js(FIXTURES / "sample.ts")
    assert any("buildHeaders" in l for l in _labels(r))

def test_ts_emits_calls():
    r = extract_js(FIXTURES / "sample.ts")
    calls = _call_pairs(r)
    # .post() calls .get()
    assert any("post" in src and "get" in tgt for src, tgt in calls)

def test_ts_calls_are_extracted():
    r = extract_js(FIXTURES / "sample.ts")
    for e in r["edges"]:
        if e["relation"] == "calls":
            assert e["confidence"] == "EXTRACTED"

def test_ts_no_dangling_edges():
    r = extract_js(FIXTURES / "sample.ts")
    node_ids = {n["id"] for n in r["nodes"]}
    for e in r["edges"]:
        if e["relation"] in ("contains", "method", "calls"):
            assert e["source"] in node_ids


# ── Go ────────────────────────────────────────────────────────────────────────

def test_go_finds_struct():
    r = extract_go(FIXTURES / "sample.go")
    assert "error" not in r
    assert "Server" in _labels(r)

def test_go_finds_methods():
    r = extract_go(FIXTURES / "sample.go")
    labels = _labels(r)
    assert any("Start" in l for l in labels)
    assert any("Stop" in l for l in labels)

def test_go_finds_constructor():
    r = extract_go(FIXTURES / "sample.go")
    assert any("NewServer" in l for l in _labels(r))

def test_go_emits_calls():
    r = extract_go(FIXTURES / "sample.go")
    # main() calls NewServer and Start
    assert len(_call_pairs(r)) > 0

def test_go_has_extracted_calls():
    r = extract_go(FIXTURES / "sample.go")
    assert "EXTRACTED" in _confidences(r)

def test_go_no_dangling_edges():
    r = extract_go(FIXTURES / "sample.go")
    node_ids = {n["id"] for n in r["nodes"]}
    for e in r["edges"]:
        if e["relation"] in ("contains", "method", "calls"):
            assert e["source"] in node_ids


# ── Rust ──────────────────────────────────────────────────────────────────────

def test_rust_finds_struct():
    r = extract_rust(FIXTURES / "sample.rs")
    assert "error" not in r
    assert "Graph" in _labels(r)

def test_rust_finds_impl_methods():
    r = extract_rust(FIXTURES / "sample.rs")
    labels = _labels(r)
    assert any("add_node" in l for l in labels)
    assert any("add_edge" in l for l in labels)

def test_rust_finds_function():
    r = extract_rust(FIXTURES / "sample.rs")
    assert any("build_graph" in l for l in _labels(r))

def test_rust_emits_calls():
    r = extract_rust(FIXTURES / "sample.rs")
    calls = _call_pairs(r)
    assert any("build_graph" in src for src, _ in calls)

def test_rust_calls_are_extracted():
    r = extract_rust(FIXTURES / "sample.rs")
    for e in r["edges"]:
        if e["relation"] == "calls":
            assert e["confidence"] == "EXTRACTED"

def test_rust_no_dangling_edges():
    r = extract_rust(FIXTURES / "sample.rs")
    node_ids = {n["id"] for n in r["nodes"]}
    for e in r["edges"]:
        if e["relation"] in ("contains", "method", "calls"):
            assert e["source"] in node_ids


# ── Rust cross-file `use crate::...` resolution ───────────────────────────────

def test_rust_use_crate_resolves_braced_imports():
    """`use crate::types::{StrategyMode, StrategyRuntime}` should produce
    one INFERRED `uses` edge per imported ident, targeting the real type
    nodes in types.rs — NOT a single dangling edge to a nonexistent "types" node."""
    files = [
        FIXTURES / "rust_crate" / "lib.rs",
        FIXTURES / "rust_crate" / "types.rs",
        FIXTURES / "rust_crate" / "manager.rs",
        FIXTURES / "rust_crate" / "helper.rs",
    ]
    r = extract(files)
    uses = [e for e in r["edges"] if e["relation"] == "uses"]
    # manager.rs imports both StrategyMode and StrategyRuntime
    use_targets = {
        (e["source_file"], n.get("label"))
        for e in uses
        for n in r["nodes"] if n["id"] == e["target"]
    }
    assert any(
        "manager.rs" in sf and lbl == "StrategyRuntime"
        for sf, lbl in use_targets
    ), f"manager.rs should have uses edge to StrategyRuntime, got: {use_targets}"
    assert any(
        "manager.rs" in sf and lbl == "StrategyMode"
        for sf, lbl in use_targets
    ), f"manager.rs should have uses edge to StrategyMode, got: {use_targets}"


def test_rust_use_crate_resolves_single_ident_import():
    """`use crate::types::StrategyMode;` (no braces) should produce a uses edge."""
    files = [
        FIXTURES / "rust_crate" / "types.rs",
        FIXTURES / "rust_crate" / "helper.rs",
    ]
    r = extract(files)
    uses = [e for e in r["edges"] if e["relation"] == "uses"]
    targets_from_helper = [
        n.get("label")
        for e in uses if "helper.rs" in e["source_file"]
        for n in r["nodes"] if n["id"] == e["target"]
    ]
    assert "StrategyMode" in targets_from_helper


def test_rust_pub_use_reexports_in_lib_rs():
    """`pub use manager::{Foo, Bar};` in lib.rs should produce `reexports` edges
    (not `uses`) so they're distinguishable from ordinary imports in queries."""
    files = [
        FIXTURES / "rust_crate" / "lib.rs",
        FIXTURES / "rust_crate" / "types.rs",
        FIXTURES / "rust_crate" / "manager.rs",
    ]
    r = extract(files)
    reexports = [e for e in r["edges"] if e["relation"] == "reexports"]
    reexport_labels = {
        n.get("label")
        for e in reexports if "lib.rs" in e["source_file"]
        for n in r["nodes"] if n["id"] == e["target"]
    }
    # lib.rs has: pub use manager::{GraduationError, StrategyLifecycleManager};
    #             pub use types::{StrategyMode, StrategyRuntime};
    assert "StrategyLifecycleManager" in reexport_labels
    assert "GraduationError" in reexport_labels
    assert "StrategyMode" in reexport_labels
    assert "StrategyRuntime" in reexport_labels


def test_rust_cross_file_edges_are_inferred():
    """Cross-file `use` edges should be INFERRED, not EXTRACTED — tree-sitter
    alone cannot fully verify type identity the way rust-analyzer would."""
    files = [
        FIXTURES / "rust_crate" / "lib.rs",
        FIXTURES / "rust_crate" / "types.rs",
        FIXTURES / "rust_crate" / "manager.rs",
        FIXTURES / "rust_crate" / "helper.rs",
    ]
    r = extract(files)
    for e in r["edges"]:
        if e["relation"] in ("uses", "reexports"):
            assert e["confidence"] == "INFERRED", (
                f"cross-file edge must be INFERRED, got {e['confidence']} for {e}"
            )


def test_rust_use_crate_never_produces_dangling_imports_from():
    """The old code emitted `imports_from` edges to non-existent stem-only
    node IDs for every `use` declaration, which then got garbage-collected
    by the dangling-edge filter. Verify we no longer produce those at all."""
    files = [
        FIXTURES / "rust_crate" / "lib.rs",
        FIXTURES / "rust_crate" / "types.rs",
        FIXTURES / "rust_crate" / "manager.rs",
    ]
    r = extract(files)
    # imports_from is reserved for Python / import_statement parsing in other
    # languages — it should not appear in a pure-Rust extraction result.
    assert not any(e["relation"] == "imports_from" for e in r["edges"])


# ── extract() dispatch ────────────────────────────────────────────────────────

def test_extract_dispatches_all_languages():
    files = [
        FIXTURES / "sample.py",
        FIXTURES / "sample.ts",
        FIXTURES / "sample.go",
        FIXTURES / "sample.rs",
    ]
    r = extract(files)
    source_files = {n["source_file"] for n in r["nodes"] if n["source_file"]}
    # All four files should contribute nodes
    assert any("sample.py" in f for f in source_files)
    assert any("sample.ts" in f for f in source_files)
    assert any("sample.go" in f for f in source_files)
    assert any("sample.rs" in f for f in source_files)


# ── Cache ─────────────────────────────────────────────────────────────────────

def test_cache_hit_returns_same_result(tmp_path):
    src = FIXTURES / "sample.py"
    dst = tmp_path / "sample.py"
    dst.write_bytes(src.read_bytes())

    r1 = extract([dst])
    r2 = extract([dst])
    assert len(r1["nodes"]) == len(r2["nodes"])
    assert len(r1["edges"]) == len(r2["edges"])

def test_cache_miss_after_file_change(tmp_path):
    dst = tmp_path / "a.py"
    dst.write_text("def foo(): pass\n")
    r1 = extract([dst])

    dst.write_text("def foo(): pass\ndef bar(): pass\n")
    r2 = extract([dst])
    # bar() should appear in the second result
    labels2 = [n["label"] for n in r2["nodes"]]
    assert any("bar" in l for l in labels2)
