"""Tests for graphify install and assistant integration support."""

from pathlib import Path
from unittest.mock import patch

import json
import pytest


def _install(tmp_path, platform):
    from graphify.__main__ import install

    with patch("graphify.__main__.Path.home", return_value=tmp_path):
        install(platform=platform)


def _agents_install(tmp_path, platform):
    from graphify.__main__ import _agents_install as _install_fn

    _install_fn(tmp_path, platform)


def _agents_uninstall(tmp_path):
    from graphify.__main__ import _agents_uninstall as _uninstall_fn

    _uninstall_fn(tmp_path, platform="codex")


def test_install_default_claude(tmp_path):
    _install(tmp_path, "claude")
    assert (tmp_path / ".claude" / "skills" / "graphify" / "SKILL.md").exists()


def test_install_codex(tmp_path):
    _install(tmp_path, "codex")
    assert (tmp_path / ".agents" / "skills" / "graphify" / "SKILL.md").exists()


@pytest.mark.parametrize(
    "platform",
    [
        "opencode",
        "claw",
        "droid",
        "trae",
        "trae-cn",
        "windows",
        "aider",
        "copilot",
        "cursor",
        "gemini",
        "hermes",
        "kiro",
        "antigravity",
    ],
)
def test_install_rejects_unsupported_platforms(tmp_path, platform):
    with pytest.raises(SystemExit):
        _install(tmp_path, platform)


def test_install_unknown_platform_exits(tmp_path):
    with pytest.raises(SystemExit):
        _install(tmp_path, "unknown")


def test_codex_skill_contains_spawn_agent():
    import graphify

    skill = (Path(graphify.__file__).parent / "skill-codex.md").read_text()
    assert "spawn_agent" in skill


def test_all_skill_files_exist_in_package():
    import graphify

    pkg = Path(graphify.__file__).parent
    for name in ("skill.md", "skill-codex.md"):
        assert (pkg / name).exists(), f"Missing: {name}"


def test_claude_install_registers_claude_md(tmp_path):
    _install(tmp_path, "claude")
    assert (tmp_path / ".claude" / "CLAUDE.md").exists()


def test_codex_install_does_not_write_claude_md(tmp_path):
    _install(tmp_path, "codex")
    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()


def test_codex_agents_install_writes_agents_md(tmp_path):
    _agents_install(tmp_path, "codex")
    agents_md = tmp_path / "AGENTS.md"
    assert agents_md.exists()
    assert "graphify" in agents_md.read_text()
    assert "GRAPH_REPORT.md" in agents_md.read_text()


def test_codex_agents_install_registers_codex_hook(tmp_path):
    _agents_install(tmp_path, "codex")
    hooks = json.loads((tmp_path / ".codex" / "hooks.json").read_text())
    assert any("graphify" in str(entry) for entry in hooks["hooks"]["PreToolUse"])


def test_agents_install_idempotent(tmp_path):
    _agents_install(tmp_path, "codex")
    _agents_install(tmp_path, "codex")
    content = (tmp_path / "AGENTS.md").read_text()
    assert content.count("## graphify") == 1


def test_agents_install_appends_to_existing(tmp_path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# Existing rules\n\nDo not break things.\n")
    _agents_install(tmp_path, "codex")
    content = agents_md.read_text()
    assert "Do not break things." in content
    assert "## graphify" in content


def test_agents_uninstall_removes_section(tmp_path):
    _agents_install(tmp_path, "codex")
    _agents_uninstall(tmp_path)
    agents_md = tmp_path / "AGENTS.md"
    assert not agents_md.exists()


def test_agents_uninstall_preserves_other_content(tmp_path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# Existing rules\n\nDo not break things.\n")
    _agents_install(tmp_path, "codex")
    _agents_uninstall(tmp_path)
    assert agents_md.exists()
    content = agents_md.read_text()
    assert "Do not break things." in content
    assert "## graphify" not in content


def test_agents_uninstall_removes_codex_hook(tmp_path):
    _agents_install(tmp_path, "codex")
    _agents_uninstall(tmp_path)
    hooks_path = tmp_path / ".codex" / "hooks.json"
    if hooks_path.exists():
        hooks = json.loads(hooks_path.read_text())
        assert not any("graphify" in str(entry) for entry in hooks.get("hooks", {}).get("PreToolUse", []))


def test_agents_uninstall_no_op_when_not_installed(tmp_path, capsys):
    _agents_uninstall(tmp_path)
    out = capsys.readouterr().out
    assert "nothing to do" in out
