"""Tests for idempotent install behaviour (issue #401).

Covers:
- Already-integrated repo detection via git ls-files
- core.hooksPath is respected (Husky compatibility)
- core.bare=true guard
- --force flag bypasses integration check
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from graphify.__main__ import _is_already_integrated, _INTEGRATION_MARKERS
from graphify.hooks import (
    install as hook_install,
    uninstall as hook_uninstall,
    status as hook_status,
    _resolve_hooks_dir,
    _HOOK_MARKER,
    _CHECKOUT_MARKER,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"],
                    cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                    cwd=str(tmp_path), check=True, capture_output=True)
    return tmp_path


def _commit(repo: Path, msg: str = "init") -> None:
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", msg],
        cwd=str(repo), check=True, capture_output=True,
    )


# ── _is_already_integrated ───────────────────────────────────────────────────

class TestAlreadyIntegrated:
    def test_empty_repo_returns_empty(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        _commit(repo)
        assert _is_already_integrated(repo) == []

    def test_tracked_settings_json_detected(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        settings = repo / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{}")
        _commit(repo, "add settings")
        tracked = _is_already_integrated(repo)
        assert ".claude/settings.json" in tracked

    def test_tracked_codex_hooks_detected(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        hooks_json = repo / ".codex" / "hooks.json"
        hooks_json.parent.mkdir(parents=True)
        hooks_json.write_text("{}")
        _commit(repo, "add codex hooks")
        tracked = _is_already_integrated(repo)
        assert ".codex/hooks.json" in tracked

    def test_untracked_files_not_detected(self, tmp_path):
        """Untracked integration files should NOT trigger the guard."""
        repo = _make_git_repo(tmp_path)
        _commit(repo)
        # Create file but don't commit
        settings = repo / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{}")
        assert _is_already_integrated(repo) == []

    def test_non_git_dir_returns_empty(self, tmp_path):
        assert _is_already_integrated(tmp_path) == []

    def test_multiple_tracked_markers(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        for relpath in [".claude/settings.json", ".codex/hooks.json"]:
            p = repo / relpath
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}")
        _commit(repo, "add both")
        tracked = _is_already_integrated(repo)
        assert len(tracked) >= 2


# ── install --force ──────────────────────────────────────────────────────────

class TestInstallForce:
    def test_install_skips_in_integrated_repo(self, tmp_path, capsys):
        """install() prints guidance and returns without writing files."""
        repo = _make_git_repo(tmp_path)
        settings = repo / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{}")
        _commit(repo, "track settings")

        from graphify.__main__ import install
        with patch("graphify.__main__.Path.home", return_value=tmp_path):
            # Run install from inside the repo
            old_cwd = os.getcwd()
            try:
                os.chdir(repo)
                install(platform="claude")
            finally:
                os.chdir(old_cwd)

        out = capsys.readouterr().out
        assert "already tracks graphify integration files" in out
        # Skill file should NOT have been written
        assert not (tmp_path / ".claude" / "skills" / "graphify" / "SKILL.md").exists()

    def test_install_force_overrides_guard(self, tmp_path, capsys):
        """install(force=True) proceeds despite tracked integration files."""
        repo = _make_git_repo(tmp_path)
        settings = repo / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{}")
        _commit(repo, "track settings")

        from graphify.__main__ import install
        with patch("graphify.__main__.Path.home", return_value=tmp_path):
            old_cwd = os.getcwd()
            try:
                os.chdir(repo)
                install(platform="claude", force=True)
            finally:
                os.chdir(old_cwd)

        out = capsys.readouterr().out
        assert "skill installed" in out


# ── core.hooksPath ───────────────────────────────────────────────────────────

class TestHooksPath:
    def test_resolve_default_when_no_config(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        hooks_dir = _resolve_hooks_dir(repo)
        assert hooks_dir == repo / ".git" / "hooks"

    def test_resolve_respects_core_hookspath(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        custom_hooks = repo / ".husky" / "_"
        custom_hooks.mkdir(parents=True)
        subprocess.run(
            ["git", "config", "core.hooksPath", str(custom_hooks)],
            cwd=str(repo), check=True, capture_output=True,
        )
        hooks_dir = _resolve_hooks_dir(repo)
        assert hooks_dir == custom_hooks.resolve()

    def test_resolve_relative_hookspath(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        custom_hooks = repo / ".husky"
        custom_hooks.mkdir(parents=True)
        subprocess.run(
            ["git", "config", "core.hooksPath", ".husky"],
            cwd=str(repo), check=True, capture_output=True,
        )
        hooks_dir = _resolve_hooks_dir(repo)
        assert hooks_dir == custom_hooks.resolve()

    def test_resolve_falls_back_when_dir_missing(self, tmp_path):
        """If core.hooksPath points to a non-existent dir, fall back to .git/hooks."""
        repo = _make_git_repo(tmp_path)
        subprocess.run(
            ["git", "config", "core.hooksPath", "/nonexistent/path"],
            cwd=str(repo), check=True, capture_output=True,
        )
        hooks_dir = _resolve_hooks_dir(repo)
        assert hooks_dir == repo / ".git" / "hooks"

    def test_hook_install_uses_hookspath(self, tmp_path):
        """hook install writes to core.hooksPath directory, not .git/hooks."""
        repo = _make_git_repo(tmp_path)
        custom_hooks = repo / ".husky"
        custom_hooks.mkdir(parents=True)
        subprocess.run(
            ["git", "config", "core.hooksPath", ".husky"],
            cwd=str(repo), check=True, capture_output=True,
        )

        hook_install(repo)

        # Hooks should be in .husky/, NOT in .git/hooks/
        assert (custom_hooks / "post-commit").exists()
        assert (custom_hooks / "post-checkout").exists()
        assert not (repo / ".git" / "hooks" / "post-commit").exists()
        assert not (repo / ".git" / "hooks" / "post-checkout").exists()

    def test_hook_uninstall_uses_hookspath(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        custom_hooks = repo / ".husky"
        custom_hooks.mkdir(parents=True)
        subprocess.run(
            ["git", "config", "core.hooksPath", ".husky"],
            cwd=str(repo), check=True, capture_output=True,
        )
        hook_install(repo)
        hook_uninstall(repo)
        assert not (custom_hooks / "post-commit").exists()

    def test_hook_status_uses_hookspath(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        custom_hooks = repo / ".husky"
        custom_hooks.mkdir(parents=True)
        subprocess.run(
            ["git", "config", "core.hooksPath", ".husky"],
            cwd=str(repo), check=True, capture_output=True,
        )
        hook_install(repo)
        result = hook_status(repo)
        assert "installed" in result


# ── core.bare guard ──────────────────────────────────────────────────────────

class TestCoreBareGuard:
    def test_hook_install_refuses_core_bare(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        subprocess.run(
            ["git", "config", "core.bare", "true"],
            cwd=str(repo), check=True, capture_output=True,
        )
        result = hook_install(repo)
        assert "core.bare=true" in result
        # No hooks should have been written
        assert not (repo / ".git" / "hooks" / "post-commit").exists()

    def test_hook_install_ok_when_core_bare_false(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        subprocess.run(
            ["git", "config", "core.bare", "false"],
            cwd=str(repo), check=True, capture_output=True,
        )
        result = hook_install(repo)
        assert "installed" in result
        assert "core.bare" not in result

    def test_hook_install_ok_when_core_bare_unset(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        result = hook_install(repo)
        assert "installed" in result
