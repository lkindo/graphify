"""Tests for watch.py - file watcher helpers (no watchdog required)."""
import time
from pathlib import Path
import pytest

from graphify.watch import _notify_only, _rebuild_code, _WATCHED_EXTENSIONS


# --- _notify_only ---

def test_notify_only_creates_flag(tmp_path):
    _notify_only(tmp_path)
    flag = tmp_path / "graphify-out" / "needs_update"
    assert flag.exists()
    assert flag.read_text() == "1"

def test_notify_only_creates_flag_dir(tmp_path):
    # graphify-out dir does not exist yet
    assert not (tmp_path / "graphify-out").exists()
    _notify_only(tmp_path)
    assert (tmp_path / "graphify-out").is_dir()

def test_notify_only_idempotent(tmp_path):
    _notify_only(tmp_path)
    _notify_only(tmp_path)
    flag = tmp_path / "graphify-out" / "needs_update"
    assert flag.read_text() == "1"


def test_rebuild_code_writes_project_relative_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("def hello():\n    return 1\n", encoding="utf-8")

    assert _rebuild_code(Path("."))

    graph_json = (tmp_path / "graphify-out" / "graph.json").read_text(encoding="utf-8")
    report = (tmp_path / "graphify-out" / "GRAPH_REPORT.md").read_text(encoding="utf-8")
    html = (tmp_path / "graphify-out" / "graph.html").read_text(encoding="utf-8")
    cache_entries = list((tmp_path / "graphify-out" / "cache").glob("*.json"))

    assert '"source_file": "pkg/a.py"' in graph_json
    assert str(tmp_path) not in graph_json
    assert str(tmp_path) not in report
    assert tmp_path.name in report.splitlines()[0]
    assert str(tmp_path) not in html
    assert cache_entries
    for entry in cache_entries:
        assert str(tmp_path) not in entry.read_text(encoding="utf-8")


def test_rebuild_code_keeps_subdir_prefix_relative_to_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("def hello():\n    return 1\n", encoding="utf-8")

    assert _rebuild_code(Path("pkg"))

    graph_json = (tmp_path / "pkg" / "graphify-out" / "graph.json").read_text(encoding="utf-8")
    assert '"source_file": "pkg/a.py"' in graph_json


# --- _WATCHED_EXTENSIONS ---

def test_watched_extensions_includes_code():
    assert ".py" in _WATCHED_EXTENSIONS
    assert ".ts" in _WATCHED_EXTENSIONS
    assert ".go" in _WATCHED_EXTENSIONS
    assert ".rs" in _WATCHED_EXTENSIONS

def test_watched_extensions_includes_docs():
    assert ".md" in _WATCHED_EXTENSIONS
    assert ".txt" in _WATCHED_EXTENSIONS
    assert ".pdf" in _WATCHED_EXTENSIONS

def test_watched_extensions_includes_images():
    assert ".png" in _WATCHED_EXTENSIONS
    assert ".jpg" in _WATCHED_EXTENSIONS

def test_watched_extensions_excludes_noise():
    assert ".json" not in _WATCHED_EXTENSIONS
    assert ".pyc" not in _WATCHED_EXTENSIONS
    assert ".log" not in _WATCHED_EXTENSIONS


# --- watch() import error without watchdog ---

def test_watch_raises_without_watchdog(tmp_path, monkeypatch):
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "watchdog.observers" or name == "watchdog.events":
            raise ImportError("mocked missing watchdog")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from graphify.watch import watch
    with pytest.raises(ImportError, match="watchdog not installed"):
        watch(tmp_path)
