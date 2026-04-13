"""Tests for Kiro platform support: config, skill, install/uninstall, CLI routing."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from graphify.__main__ import (
    _PLATFORM_CONFIG,
    _KIRO_HOOK_CONFIG,
    _KIRO_STEERING_MARKER,
    _KIRO_STEERING_SECTION,
    kiro_install,
    kiro_uninstall,
)


# ---------------------------------------------------------------------------
# Platform config
# ---------------------------------------------------------------------------

def test_platform_config_kiro_exists():
    assert "kiro" in _PLATFORM_CONFIG


def test_platform_config_kiro_values():
    cfg = _PLATFORM_CONFIG["kiro"]
    assert cfg["skill_file"] == "skill-kiro.md"
    assert cfg["skill_dst"] == Path(".kiro") / "skills" / "graphify" / "SKILL.md"
    assert cfg["claude_md"] is False


# ---------------------------------------------------------------------------
# Skill file existence
# ---------------------------------------------------------------------------

def test_skill_kiro_file_exists():
    import graphify
    skill = Path(graphify.__file__).parent / "skill-kiro.md"
    assert skill.exists(), "skill-kiro.md not found in package"


# ---------------------------------------------------------------------------
# Skill install via install()
# ---------------------------------------------------------------------------

def _install(tmp_path, platform):
    from graphify.__main__ import install
    with patch("graphify.__main__.Path.home", return_value=tmp_path):
        install(platform=platform)


def test_install_kiro_copies_skill(tmp_path):
    _install(tmp_path, "kiro")
    assert (tmp_path / ".kiro" / "skills" / "graphify" / "SKILL.md").exists()


def test_install_kiro_creates_version_file(tmp_path):
    _install(tmp_path, "kiro")
    assert (tmp_path / ".kiro" / "skills" / "graphify" / ".graphify_version").exists()


def test_install_kiro_does_not_write_claude_md(tmp_path):
    _install(tmp_path, "kiro")
    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()


# ---------------------------------------------------------------------------
# Always-on install
# ---------------------------------------------------------------------------

def test_kiro_install_creates_steering_file(tmp_path):
    kiro_install(tmp_path)
    steering = tmp_path / ".kiro" / "steering" / "graphify.md"
    assert steering.exists()
    content = steering.read_text(encoding="utf-8")
    assert _KIRO_STEERING_MARKER in content


def test_kiro_install_steering_contains_rules(tmp_path):
    kiro_install(tmp_path)
    content = (tmp_path / ".kiro" / "steering" / "graphify.md").read_text(encoding="utf-8")
    assert "GRAPH_REPORT.md" in content
    assert "wiki/index.md" in content
    assert "_rebuild_code" in content


def test_kiro_install_creates_hook_file(tmp_path):
    kiro_install(tmp_path)
    hook = tmp_path / ".kiro" / "hooks" / "graphify-pretool.json"
    assert hook.exists()
    data = json.loads(hook.read_text(encoding="utf-8"))
    assert data["name"] == "graphify-pretool"
    assert data["when"]["type"] == "preToolUse"
    assert "read" in data["when"]["toolTypes"]


def test_kiro_install_hook_has_valid_schema(tmp_path):
    kiro_install(tmp_path)
    hook = tmp_path / ".kiro" / "hooks" / "graphify-pretool.json"
    data = json.loads(hook.read_text(encoding="utf-8"))
    # Verify all required Kiro hook schema fields
    assert "name" in data
    assert "version" in data
    assert "when" in data
    assert "then" in data
    assert data["then"]["type"] == "runCommand"
    assert "command" in data["then"]


def test_kiro_install_creates_directories(tmp_path):
    """Directories are created automatically even if .kiro/ doesn't exist."""
    kiro_install(tmp_path)
    assert (tmp_path / ".kiro" / "steering").is_dir()
    assert (tmp_path / ".kiro" / "hooks").is_dir()


def test_kiro_install_idempotent_steering(tmp_path, capsys):
    kiro_install(tmp_path)
    capsys.readouterr()  # clear first call
    kiro_install(tmp_path)
    out = capsys.readouterr().out
    assert "already configured" in out
    # Content not duplicated
    content = (tmp_path / ".kiro" / "steering" / "graphify.md").read_text(encoding="utf-8")
    assert content.count(_KIRO_STEERING_MARKER) == 1


def test_kiro_install_idempotent_hook(tmp_path, capsys):
    kiro_install(tmp_path)
    capsys.readouterr()
    kiro_install(tmp_path)
    out = capsys.readouterr().out
    assert "already installed" in out


# ---------------------------------------------------------------------------
# Always-on uninstall
# ---------------------------------------------------------------------------

def test_kiro_uninstall_removes_steering(tmp_path):
    kiro_install(tmp_path)
    kiro_uninstall(tmp_path)
    assert not (tmp_path / ".kiro" / "steering" / "graphify.md").exists()


def test_kiro_uninstall_removes_hook(tmp_path):
    kiro_install(tmp_path)
    kiro_uninstall(tmp_path)
    assert not (tmp_path / ".kiro" / "hooks" / "graphify-pretool.json").exists()


def test_kiro_uninstall_no_op_steering(tmp_path, capsys):
    kiro_uninstall(tmp_path)
    out = capsys.readouterr().out
    assert "nothing to do" in out


def test_kiro_uninstall_no_op_hook(tmp_path, capsys):
    kiro_uninstall(tmp_path)
    out = capsys.readouterr().out
    assert "not installed" in out


# ---------------------------------------------------------------------------
# CLI routing
# ---------------------------------------------------------------------------

def test_cli_kiro_install_routes(tmp_path, monkeypatch):
    """graphify kiro install calls kiro_install()."""
    called = []
    monkeypatch.setattr("graphify.__main__.kiro_install", lambda: called.append("install"))
    monkeypatch.setattr("sys.argv", ["graphify", "kiro", "install"])
    from graphify.__main__ import main
    main()
    assert called == ["install"]


def test_cli_kiro_uninstall_routes(tmp_path, monkeypatch):
    """graphify kiro uninstall calls kiro_uninstall()."""
    called = []
    monkeypatch.setattr("graphify.__main__.kiro_uninstall", lambda: called.append("uninstall"))
    monkeypatch.setattr("sys.argv", ["graphify", "kiro", "uninstall"])
    from graphify.__main__ import main
    main()
    assert called == ["uninstall"]


def test_cli_kiro_no_subcmd_exits(monkeypatch):
    """graphify kiro without subcommand exits with error."""
    monkeypatch.setattr("sys.argv", ["graphify", "kiro"])
    from graphify.__main__ import main
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Skill file content
# ---------------------------------------------------------------------------

def test_skill_kiro_has_yaml_frontmatter():
    import graphify
    content = (Path(graphify.__file__).parent / "skill-kiro.md").read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "name: graphify" in content
    assert "description:" in content
    assert "trigger:" in content


def test_skill_kiro_has_all_steps():
    import graphify
    content = (Path(graphify.__file__).parent / "skill-kiro.md").read_text(encoding="utf-8")
    for step in range(1, 10):
        assert f"Step {step}" in content, f"Missing Step {step}"


def test_skill_kiro_sequential_extraction():
    """Kiro skill describes sequential extraction (like OpenClaw)."""
    import graphify
    content = (Path(graphify.__file__).parent / "skill-kiro.md").read_text(encoding="utf-8")
    assert "sequential" in content.lower()
    assert "Kiro" in content
