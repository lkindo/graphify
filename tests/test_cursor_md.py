"""Tests for graphify cursor install / uninstall commands."""

from pathlib import Path
import pytest
from graphify.__main__ import cursor_install, cursor_uninstall, _CURSOR_RULE_MARKER


# ---------------------------------------------------------------------------
# rule file install
# ---------------------------------------------------------------------------


def test_cursor_install_creates_rule_file(tmp_path):
    """Creates .cursor/rules/graphify.mdc when none exists."""
    cursor_install(tmp_path)
    rule_file = tmp_path / ".cursor" / "rules" / "graphify.mdc"
    assert rule_file.exists()
    assert _CURSOR_RULE_MARKER in rule_file.read_text()


def test_cursor_rule_has_always_apply(tmp_path):
    """Rule file has alwaysApply: true frontmatter."""
    cursor_install(tmp_path)
    content = (tmp_path / ".cursor" / "rules" / "graphify.mdc").read_text()
    assert "alwaysApply: true" in content


def test_cursor_rule_contains_expected_rules(tmp_path):
    """Written rule includes the three rules."""
    cursor_install(tmp_path)
    content = (tmp_path / ".cursor" / "rules" / "graphify.mdc").read_text()
    assert "GRAPH_REPORT.md" in content
    assert "wiki/index.md" in content
    assert "_rebuild_code" in content


def test_cursor_install_is_idempotent(tmp_path, capsys):
    """Running install twice does not duplicate the rule file."""
    cursor_install(tmp_path)
    cursor_install(tmp_path)
    content = (tmp_path / ".cursor" / "rules" / "graphify.mdc").read_text()
    assert content.count(_CURSOR_RULE_MARKER) == 1
    captured = capsys.readouterr()
    assert "already configured" in captured.out


# ---------------------------------------------------------------------------
# rule file uninstall
# ---------------------------------------------------------------------------


def test_cursor_uninstall_removes_rule_file(tmp_path):
    """Removes .cursor/rules/graphify.mdc after install."""
    cursor_install(tmp_path)
    cursor_uninstall(tmp_path)
    rule_file = tmp_path / ".cursor" / "rules" / "graphify.mdc"
    assert not rule_file.exists()


def test_cursor_uninstall_no_op_when_not_installed(tmp_path, capsys):
    """Uninstall when rule file absent exits cleanly."""
    cursor_uninstall(tmp_path)
    out = capsys.readouterr().out
    assert "nothing to do" in out or "not found" in out or "No .cursor" in out


# ---------------------------------------------------------------------------
# hooks.json + graphify-check.sh
# ---------------------------------------------------------------------------


def test_cursor_install_creates_hooks_json(tmp_path):
    """cursor_install writes .cursor/hooks.json with sessionStart entry."""
    import json

    cursor_install(tmp_path)
    hooks_path = tmp_path / ".cursor" / "hooks.json"
    assert hooks_path.exists()
    hooks = json.loads(hooks_path.read_text())
    session_hooks = hooks.get("hooks", {}).get("sessionStart", [])
    assert any("graphify-check.sh" in h.get("command", "") for h in session_hooks)


def test_cursor_install_hooks_json_idempotent(tmp_path):
    """Running install twice does not duplicate the sessionStart hook entry."""
    import json

    cursor_install(tmp_path)
    cursor_install(tmp_path)
    hooks_path = tmp_path / ".cursor" / "hooks.json"
    hooks = json.loads(hooks_path.read_text())
    session_hooks = hooks.get("hooks", {}).get("sessionStart", [])
    graphify_hooks = [
        h for h in session_hooks if "graphify-check.sh" in h.get("command", "")
    ]
    assert len(graphify_hooks) == 1


def test_cursor_install_creates_hook_script(tmp_path):
    """cursor_install writes the graphify-check.sh script."""
    cursor_install(tmp_path)
    script = tmp_path / ".cursor" / "hooks" / "graphify-check.sh"
    assert script.exists()
    assert "graphify-out/graph.json" in script.read_text()


def test_cursor_hook_script_is_executable(tmp_path):
    """graphify-check.sh is written with executable permissions."""
    import stat

    cursor_install(tmp_path)
    script = tmp_path / ".cursor" / "hooks" / "graphify-check.sh"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "Script should be user-executable"


def test_cursor_uninstall_removes_hook_entry(tmp_path):
    """cursor_uninstall removes the sessionStart hook entry from hooks.json."""
    import json

    cursor_install(tmp_path)
    cursor_uninstall(tmp_path)
    hooks_path = tmp_path / ".cursor" / "hooks.json"
    if hooks_path.exists():
        hooks = json.loads(hooks_path.read_text())
        session_hooks = hooks.get("hooks", {}).get("sessionStart", [])
        assert not any(
            "graphify-check.sh" in h.get("command", "") for h in session_hooks
        )


def test_cursor_uninstall_preserves_other_hooks(tmp_path):
    """cursor_uninstall keeps non-graphify hooks in hooks.json."""
    import json

    hooks_path = tmp_path / ".cursor" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {
        "version": 1,
        "hooks": {
            "sessionStart": [{"command": ".cursor/hooks/other.sh"}],
            "afterFileEdit": [{"command": ".cursor/hooks/format.sh"}],
        },
    }
    hooks_path.write_text(json.dumps(existing), encoding="utf-8")
    cursor_install(tmp_path)
    cursor_uninstall(tmp_path)
    hooks = json.loads(hooks_path.read_text())
    # Other hooks preserved
    assert any(
        h.get("command") == ".cursor/hooks/other.sh"
        for h in hooks.get("hooks", {}).get("sessionStart", [])
    )
    assert hooks.get("hooks", {}).get("afterFileEdit")


def test_cursor_uninstall_removes_hook_script(tmp_path):
    """cursor_uninstall deletes graphify-check.sh."""
    cursor_install(tmp_path)
    cursor_uninstall(tmp_path)
    script = tmp_path / ".cursor" / "hooks" / "graphify-check.sh"
    assert not script.exists()


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def test_cursor_cli_install(tmp_path, monkeypatch):
    """graphify cursor install creates the rule file."""
    import sys
    from graphify.__main__ import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["graphify", "cursor", "install"])
    main()
    assert (tmp_path / ".cursor" / "rules" / "graphify.mdc").exists()


def test_cursor_cli_uninstall(tmp_path, monkeypatch):
    """graphify cursor uninstall removes the rule file."""
    import sys
    from graphify.__main__ import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["graphify", "cursor", "install"])
    main()
    monkeypatch.setattr(sys, "argv", ["graphify", "cursor", "uninstall"])
    main()
    assert not (tmp_path / ".cursor" / "rules" / "graphify.mdc").exists()
