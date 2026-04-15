"""Tests for watch.py - file watcher helpers (no watchdog required)."""
from pathlib import Path
import pytest

from graphify.watch import _notify_only, _WATCHED_EXTENSIONS, _observer_mode


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


def test_observer_mode_defaults_to_auto(monkeypatch):
    monkeypatch.delenv("GRAPHIFY_WATCH_OBSERVER", raising=False)
    assert _observer_mode() == "auto"


def test_observer_mode_invalid_falls_back_to_auto(monkeypatch):
    monkeypatch.setenv("GRAPHIFY_WATCH_OBSERVER", "banana")
    assert _observer_mode() == "auto"


def test_observer_mode_accepts_native(monkeypatch):
    monkeypatch.setenv("GRAPHIFY_WATCH_OBSERVER", "native")
    assert _observer_mode() == "native"


def test_observer_mode_accepts_polling(monkeypatch):
    monkeypatch.setenv("GRAPHIFY_WATCH_OBSERVER", "polling")
    assert _observer_mode() == "polling"
