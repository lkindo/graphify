from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

HomeContextKind = Literal["none", "claude_md"]
ProjectContextKind = Literal["none", "claude_md", "agents_md"]
ProjectHookKind = Literal["none", "claude_pretooluse", "codex_pretooluse"]


@dataclass(frozen=True)
class Integration:
    key: str
    display_name: str
    skill_file: str
    skill_dst: Path
    home_context_kind: HomeContextKind = "none"
    project_context_kind: ProjectContextKind = "none"
    project_hook_kind: ProjectHookKind = "none"
    project_command: bool = True
    variant_of: str | None = None


INTEGRATIONS: dict[str, Integration] = {
    "claude": Integration(
        key="claude",
        display_name="Claude Code",
        skill_file="skill.md",
        skill_dst=Path(".claude") / "skills" / "graphify" / "SKILL.md",
        home_context_kind="claude_md",
        project_context_kind="claude_md",
        project_hook_kind="claude_pretooluse",
    ),
    "codex": Integration(
        key="codex",
        display_name="Codex",
        skill_file="skill-codex.md",
        skill_dst=Path(".agents") / "skills" / "graphify" / "SKILL.md",
        project_context_kind="agents_md",
        project_hook_kind="codex_pretooluse",
    ),
    "opencode": Integration(
        key="opencode",
        display_name="OpenCode",
        skill_file="skill-opencode.md",
        skill_dst=Path(".config") / "opencode" / "skills" / "graphify" / "SKILL.md",
        project_context_kind="agents_md",
    ),
    "claw": Integration(
        key="claw",
        display_name="OpenClaw",
        skill_file="skill-claw.md",
        skill_dst=Path(".claw") / "skills" / "graphify" / "SKILL.md",
        project_context_kind="agents_md",
    ),
    "droid": Integration(
        key="droid",
        display_name="Factory Droid",
        skill_file="skill-droid.md",
        skill_dst=Path(".factory") / "skills" / "graphify" / "SKILL.md",
        project_context_kind="agents_md",
    ),
    "trae": Integration(
        key="trae",
        display_name="Trae",
        skill_file="skill-trae.md",
        skill_dst=Path(".trae") / "skills" / "graphify" / "SKILL.md",
        project_context_kind="agents_md",
    ),
    "trae-cn": Integration(
        key="trae-cn",
        display_name="Trae CN",
        skill_file="skill-trae.md",
        skill_dst=Path(".trae-cn") / "skills" / "graphify" / "SKILL.md",
        project_context_kind="agents_md",
    ),
    "windows": Integration(
        key="windows",
        display_name="Claude Code (Windows)",
        skill_file="skill-windows.md",
        skill_dst=Path(".claude") / "skills" / "graphify" / "SKILL.md",
        home_context_kind="claude_md",
        project_context_kind="claude_md",
        project_hook_kind="claude_pretooluse",
        project_command=False,
        variant_of="claude",
    ),
}


def get_integration(key: str) -> Integration | None:
    return INTEGRATIONS.get(key)


def supported_platform_keys() -> tuple[str, ...]:
    return tuple(INTEGRATIONS)


def project_command_keys() -> tuple[str, ...]:
    return tuple(key for key, integration in INTEGRATIONS.items() if integration.project_command)


def supported_platforms_text() -> str:
    return ", ".join(supported_platform_keys())
