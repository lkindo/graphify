"""Tests for graphify CLI commands: dry-run and diff."""
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch


FIXTURES = Path(__file__).parent / "fixtures"


# ── dry-run ───────────────────────────────────────────────────────────────────

def _run_main(argv):
    """Run graphify.__main__.main() with the given argv, return (stdout, exit_code)."""
    import io
    from graphify.__main__ import main
    buf = io.StringIO()
    exit_code = 0
    with patch("sys.argv", argv), patch("sys.stdout", buf):
        try:
            main()
        except SystemExit as e:
            exit_code = e.code or 0
    return buf.getvalue(), exit_code


def test_dry_run_prints_summary(tmp_path):
    """dry-run on a directory with code files prints a file-count summary."""
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "utils.py").write_text("def f(): pass\n")
    out, code = _run_main(["graphify", "dry-run", str(tmp_path)])
    assert code == 0
    assert "Corpus scan" in out
    assert "Code files" in out
    assert "Total" in out


def test_dry_run_no_files_written(tmp_path):
    """dry-run must not create graphify-out/ or any files."""
    (tmp_path / "readme.md").write_text("# hello\n")
    _run_main(["graphify", "dry-run", str(tmp_path)])
    assert not (tmp_path / "graphify-out").exists()


def test_dry_run_default_path(tmp_path, monkeypatch):
    """dry-run with no path argument defaults to current directory."""
    (tmp_path / "main.py").write_text("print('hi')\n")
    monkeypatch.chdir(tmp_path)
    out, code = _run_main(["graphify", "dry-run"])
    assert code == 0
    assert "Corpus scan" in out


def test_dry_run_missing_path(tmp_path):
    """dry-run with a non-existent path exits with error."""
    out_stderr = []
    with patch("sys.argv", ["graphify", "dry-run", str(tmp_path / "nonexistent")]), \
         patch("sys.stderr") as mock_err:
        mock_err.write = lambda s: out_stderr.append(s)
        with pytest.raises(SystemExit) as exc:
            from graphify.__main__ import main
            main()
    assert exc.value.code != 0


def test_dry_run_no_graphify_out_written(tmp_path):
    """dry-run message says no files were written."""
    (tmp_path / "a.py").write_text("a = 1\n")
    out, _ = _run_main(["graphify", "dry-run", str(tmp_path)])
    assert "No files were written" in out


# ── diff ──────────────────────────────────────────────────────────────────────

try:
    import networkx  # noqa: F401
    _HAS_NETWORKX = True
except ImportError:
    _HAS_NETWORKX = False

requires_networkx = pytest.mark.skipif(not _HAS_NETWORKX, reason="networkx not installed")


def _make_graph_json(tmp_path, name, nodes, edges):
    data = {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": [{"id": n, "label": n} for n in nodes],
        "links": [
            {"source": s, "target": t, "relation": r, "confidence": "EXTRACTED", "weight": 1.0}
            for s, t, r in edges
        ],
    }
    p = tmp_path / name
    p.write_text(json.dumps(data))
    return p


@requires_networkx
def test_diff_no_changes(tmp_path):
    """diff of identical graphs reports 'no changes'."""
    nodes = ["alpha", "beta"]
    edges = [("alpha", "beta", "calls")]
    old = _make_graph_json(tmp_path, "old.json", nodes, edges)
    new = _make_graph_json(tmp_path, "new.json", nodes, edges)
    out, code = _run_main(["graphify", "diff", str(old), str(new)])
    assert code == 0
    assert "no changes" in out


@requires_networkx
def test_diff_new_node(tmp_path):
    """diff detects a newly added node."""
    old = _make_graph_json(tmp_path, "old.json", ["alpha"], [])
    new = _make_graph_json(tmp_path, "new.json", ["alpha", "gamma"], [])
    out, code = _run_main(["graphify", "diff", str(old), str(new)])
    assert code == 0
    assert "gamma" in out
    assert "New nodes" in out


@requires_networkx
def test_diff_removed_node(tmp_path):
    """diff detects a removed node."""
    old = _make_graph_json(tmp_path, "old.json", ["alpha", "beta"], [])
    new = _make_graph_json(tmp_path, "new.json", ["alpha"], [])
    out, code = _run_main(["graphify", "diff", str(old), str(new)])
    assert code == 0
    assert "beta" in out
    assert "Removed nodes" in out


@requires_networkx
def test_diff_new_edge(tmp_path):
    """diff detects a new edge."""
    old = _make_graph_json(tmp_path, "old.json", ["a", "b"], [])
    new = _make_graph_json(tmp_path, "new.json", ["a", "b"], [("a", "b", "imports")])
    out, code = _run_main(["graphify", "diff", str(old), str(new)])
    assert code == 0
    assert "New edges" in out
    assert "imports" in out


def test_diff_missing_file(tmp_path):
    """diff exits with error when a file does not exist."""
    old = _make_graph_json(tmp_path, "old.json", ["a"], [])
    with pytest.raises(SystemExit) as exc:
        with patch("sys.argv", ["graphify", "diff", str(old), str(tmp_path / "missing.json")]):
            from graphify.__main__ import main
            main()
    assert exc.value.code != 0


def test_diff_missing_args(tmp_path):
    """diff with fewer than 2 positional args exits with error."""
    with pytest.raises(SystemExit) as exc:
        with patch("sys.argv", ["graphify", "diff", str(tmp_path / "only_one.json")]):
            from graphify.__main__ import main
            main()
    assert exc.value.code != 0
