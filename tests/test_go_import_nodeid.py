"""Test that Go stdlib imports don't collide with same-named local files.

Regression test for: stdlib package name (e.g. "context") creates a node id
that collides with a local file of the same name (e.g. accounting/context.go),
producing spurious edges. See PR for upstream bug report.
"""

from pathlib import Path
import pytest

pytest.importorskip("tree_sitter_go")

from graphify.extract import extract_go


def _fixture(tmp_path: Path, rel: str, source: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source, encoding="utf-8")
    return p


def test_go_stdlib_import_does_not_collide_with_local_file(tmp_path):
    """Imports of Go stdlib packages (e.g. "context") must not share a
    node id with local files of the same basename (e.g. context.go).
    """
    # Create a local file that has the same basename as a stdlib package.
    local_ctx = _fixture(
        tmp_path,
        "internal/accounting/context.go",
        "package accounting\n\ntype Context struct{}\n",
    )
    # Create another file that only imports stdlib "context".
    caller = _fixture(
        tmp_path,
        "internal/sms/mock.go",
        'package sms\n\nimport "context"\n\nfunc F(ctx context.Context) {}\n',
    )

    # Extract both.
    ctx_result = extract_go(local_ctx)
    caller_result = extract_go(caller)

    ctx_file_id = next(
        n["id"] for n in ctx_result["nodes"] if n["label"] == "context.go"
    )

    # Find the import edge from caller → stdlib "context".
    import_edges = [
        e for e in caller_result["edges"] if e.get("relation") == "imports_from"
    ]
    assert import_edges, "expected at least one imports_from edge"
    stdlib_targets = {e["target"] for e in import_edges}

    # Assert the stdlib import target is NOT the same id as the local file.
    assert ctx_file_id not in stdlib_targets, (
        f"Go stdlib import 'context' produced target id {stdlib_targets!r} "
        f"which collides with local file id {ctx_file_id!r}. "
        f"This causes spurious cross-package 'imports_from' edges."
    )


def test_go_local_import_full_path_in_id(tmp_path):
    """Local Go imports should use the full import path in node id to
    avoid collisions between packages with the same final segment.

    E.g. `presto/internal/accounting` and `otherapp/internal/accounting`
    should produce different target node ids.
    """
    caller = _fixture(
        tmp_path,
        "main.go",
        'package main\n\nimport (\n\t"presto/internal/accounting"\n\t"otherapp/internal/accounting"\n)\n\nfunc main() {}\n',
    )
    result = extract_go(caller)
    import_edges = [e for e in result["edges"] if e.get("relation") == "imports_from"]
    targets = [e["target"] for e in import_edges]
    # Two distinct imports → two distinct target ids.
    assert len(set(targets)) == 2, (
        f"Expected 2 distinct import target ids for two different packages "
        f"ending in 'accounting', got {targets!r}"
    )
