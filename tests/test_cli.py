"""CLI behaviour tests for shell-friendly command aliases."""

from pathlib import Path
import sys


def test_normalize_command_token_accepts_shell_aliases():
    from graphify.__main__ import _normalize_command_token

    assert _normalize_command_token("update") == "update"
    assert _normalize_command_token("--update") == "update"
    assert _normalize_command_token("--cluster-only") == "cluster-only"
    assert _normalize_command_token("--unknown") == "--unknown"


def test_main_update_accepts_shell_alias(monkeypatch, tmp_path):
    from graphify.__main__ import main
    import graphify.watch

    called = {}

    def fake_rebuild(path: Path) -> bool:
        called["path"] = path
        return True

    monkeypatch.setattr(graphify.watch, "_rebuild_code", fake_rebuild)
    monkeypatch.setattr(sys, "argv", ["graphify", "--update", str(tmp_path)])

    main()

    assert called["path"] == tmp_path
