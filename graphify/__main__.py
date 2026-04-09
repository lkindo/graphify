"""graphify CLI - `graphify install` sets up the Claude Code skill."""
from __future__ import annotations
import json
import platform
import re
import shutil
import sys
from pathlib import Path

from graphify.integrations import (
    Integration,
    get_integration,
    project_command_keys,
    supported_platform_keys,
    supported_platforms_text,
)

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("graphifyy")
except Exception:
    __version__ = "unknown"


def _check_skill_version(skill_dst: Path) -> None:
    """Warn if the installed skill is from an older graphify version."""
    version_file = skill_dst.parent / ".graphify_version"
    if not version_file.exists():
        return
    installed = version_file.read_text(encoding="utf-8").strip()
    if installed != __version__:
        print(f"  warning: skill is from graphify {installed}, package is {__version__}. Run 'graphify install' to update.")

_SETTINGS_HOOK = {
    "matcher": "Glob|Grep",
    "hooks": [
        {
            "type": "command",
            "command": (
                "[ -f graphify-out/graph.json ] && "
                r"""echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"graphify: Knowledge graph exists. Read graphify-out/GRAPH_REPORT.md for god nodes and community structure before searching raw files."}}' """
                "|| true"
            ),
        }
    ],
}

_SKILL_REGISTRATION = (
    "\n# graphify\n"
    "- **graphify** (`~/.claude/skills/graphify/SKILL.md`) "
    "- any input to knowledge graph. Trigger: `/graphify`\n"
    "When the user types `/graphify`, invoke the Skill tool "
    "with `skill: \"graphify\"` before doing anything else.\n"
)


def _known_skill_destinations() -> tuple[Path, ...]:
    return tuple(Path.home() / integration.skill_dst for integration in map(get_integration, supported_platform_keys()) if integration)


def _project_command_usage(key: str) -> str:
    return f"Usage: graphify {key} [install|uninstall]"


def _default_install_platform() -> str:
    return "windows" if platform.system() == "Windows" else "claude"



def _project_help_line(integration: Integration, action: str) -> str:
    if integration.project_context_kind == "claude_md":
        if action == "install":
            details = f"write graphify section to CLAUDE.md + PreToolUse hook ({integration.display_name})"
        else:
            details = "remove graphify section from CLAUDE.md + PreToolUse hook"
    elif integration.project_context_kind == "agents_md":
        verb = "write" if action == "install" else "remove"
        details = f"{verb} graphify section {'to' if action == 'install' else 'from'} AGENTS.md ({integration.display_name})"
    else:
        details = f"{action} project integration"
    return f"  {integration.key} {action}".ljust(31) + details



def _register_home_claude_md() -> None:
    """Register graphify in ~/.claude/CLAUDE.md when needed."""
    claude_md = Path.home() / ".claude" / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        if "graphify" in content:
            print(f"  CLAUDE.md        ->  already registered (no change)")
        else:
            claude_md.write_text(content.rstrip() + _SKILL_REGISTRATION, encoding="utf-8")
            print(f"  CLAUDE.md        ->  skill registered in {claude_md}")
    else:
        claude_md.parent.mkdir(parents=True, exist_ok=True)
        claude_md.write_text(_SKILL_REGISTRATION.lstrip(), encoding="utf-8")
        print(f"  CLAUDE.md        ->  created at {claude_md}")


def install_home_skill(integration: Integration) -> None:
    skill_src = Path(__file__).parent / integration.skill_file
    if not skill_src.exists():
        print(f"error: {integration.skill_file} not found in package - reinstall graphify", file=sys.stderr)
        sys.exit(1)

    skill_dst = Path.home() / integration.skill_dst
    skill_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(skill_src, skill_dst)
    (skill_dst.parent / ".graphify_version").write_text(__version__, encoding="utf-8")
    print(f"  skill installed  ->  {skill_dst}")



def install_home_context(integration: Integration) -> None:
    if integration.home_context_kind == "claude_md":
        _register_home_claude_md()



def install(platform: str = "claude") -> None:
    integration = get_integration(platform)
    if integration is None:
        print(
            f"error: unknown platform '{platform}'. Choose from: {supported_platforms_text()}",
            file=sys.stderr,
        )
        sys.exit(1)

    install_home_skill(integration)
    install_home_context(integration)

    print()
    print("Done. Open your AI coding assistant and type:")
    print()
    print("  /graphify .")
    print()


_CLAUDE_MD_SECTION = """\
## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
"""

_CLAUDE_MD_MARKER = "## graphify"

# AGENTS.md section for Codex, OpenCode, and OpenClaw.
# All three platforms read AGENTS.md in the project root for persistent instructions.
_AGENTS_MD_SECTION = """\
## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
"""

_AGENTS_MD_MARKER = "## graphify"

_CODEX_HOOK = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            "[ -f graphify-out/graph.json ] && "
                            r"""echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"graphify: Knowledge graph exists. Read graphify-out/GRAPH_REPORT.md for god nodes and community structure before searching raw files."}}' """
                            "|| true"
                        ),
                    }
                ],
            }
        ]
    }
}


def _install_codex_hook(project_dir: Path) -> None:
    """Add graphify PreToolUse hook to .codex/hooks.json."""
    hooks_path = project_dir / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)

    if hooks_path.exists():
        try:
            existing = json.loads(hooks_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    pre_tool = existing.setdefault("hooks", {}).setdefault("PreToolUse", [])
    if any("graphify" in str(h) for h in pre_tool):
        print(f"  .codex/hooks.json  ->  hook already registered (no change)")
        return

    pre_tool.extend(_CODEX_HOOK["hooks"]["PreToolUse"])
    hooks_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"  .codex/hooks.json  ->  PreToolUse hook registered")


def _uninstall_codex_hook(project_dir: Path) -> None:
    """Remove graphify PreToolUse hook from .codex/hooks.json."""
    hooks_path = project_dir / ".codex" / "hooks.json"
    if not hooks_path.exists():
        return
    try:
        existing = json.loads(hooks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    pre_tool = existing.get("hooks", {}).get("PreToolUse", [])
    filtered = [h for h in pre_tool if "graphify" not in str(h)]
    existing["hooks"]["PreToolUse"] = filtered
    hooks_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"  .codex/hooks.json  ->  PreToolUse hook removed")


def _agents_install(project_dir: Path, platform: str) -> None:
    """Write the graphify section to the local AGENTS.md (Codex/OpenCode/OpenClaw)."""
    target = (project_dir or Path(".")) / "AGENTS.md"

    if target.exists():
        content = target.read_text(encoding="utf-8")
        if _AGENTS_MD_MARKER in content:
            print(f"graphify already configured in AGENTS.md")
            return
        new_content = content.rstrip() + "\n\n" + _AGENTS_MD_SECTION
    else:
        new_content = _AGENTS_MD_SECTION

    target.write_text(new_content, encoding="utf-8")
    print(f"graphify section written to {target.resolve()}")

    if platform == "codex":
        _install_codex_hook(project_dir or Path("."))

    print()
    print(f"{platform.capitalize()} will now check the knowledge graph before answering")
    print("codebase questions and rebuild it after code changes.")
    if platform != "codex":
        print()
        print("Note: unlike Claude Code, there is no PreToolUse hook equivalent for")
        print(f"{platform.capitalize()} — the AGENTS.md rules are the always-on mechanism.")


def _agents_uninstall(project_dir: Path) -> None:
    """Remove the graphify section from the local AGENTS.md."""
    target = (project_dir or Path(".")) / "AGENTS.md"

    if not target.exists():
        print("No AGENTS.md found in current directory - nothing to do")
        return

    content = target.read_text(encoding="utf-8")
    if _AGENTS_MD_MARKER not in content:
        print("graphify section not found in AGENTS.md - nothing to do")
        return

    cleaned = re.sub(
        r"\n*## graphify\n.*?(?=\n## |\Z)",
        "",
        content,
        flags=re.DOTALL,
    ).rstrip()
    if cleaned:
        target.write_text(cleaned + "\n", encoding="utf-8")
        print(f"graphify section removed from {target.resolve()}")
    else:
        target.unlink()
        print(f"AGENTS.md was empty after removal - deleted {target.resolve()}")


def claude_install(project_dir: Path | None = None) -> None:
    """Write the graphify section to the local CLAUDE.md."""
    target = (project_dir or Path(".")) / "CLAUDE.md"

    if target.exists():
        content = target.read_text(encoding="utf-8")
        if _CLAUDE_MD_MARKER in content:
            print("graphify already configured in CLAUDE.md")
            return
        new_content = content.rstrip() + "\n\n" + _CLAUDE_MD_SECTION
    else:
        new_content = _CLAUDE_MD_SECTION

    target.write_text(new_content, encoding="utf-8")
    print(f"graphify section written to {target.resolve()}")

    # Also write Claude Code PreToolUse hook to .claude/settings.json
    _install_claude_hook(project_dir or Path("."))

    print()
    print("Claude Code will now check the knowledge graph before answering")
    print("codebase questions and rebuild it after code changes.")


def _install_claude_hook(project_dir: Path) -> None:
    """Add graphify PreToolUse hook to .claude/settings.json."""
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    pre_tool = hooks.setdefault("PreToolUse", [])

    # Check if already installed
    if any(h.get("matcher") == "Glob|Grep" and "graphify" in str(h) for h in pre_tool):
        print(f"  .claude/settings.json  ->  hook already registered (no change)")
        return

    pre_tool.append(_SETTINGS_HOOK)
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print(f"  .claude/settings.json  ->  PreToolUse hook registered")


def _uninstall_claude_hook(project_dir: Path) -> None:
    """Remove graphify PreToolUse hook from .claude/settings.json."""
    settings_path = project_dir / ".claude" / "settings.json"
    if not settings_path.exists():
        return
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    pre_tool = settings.get("hooks", {}).get("PreToolUse", [])
    filtered = [h for h in pre_tool if not (h.get("matcher") == "Glob|Grep" and "graphify" in str(h))]
    if len(filtered) == len(pre_tool):
        return
    settings["hooks"]["PreToolUse"] = filtered
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print(f"  .claude/settings.json  ->  PreToolUse hook removed")


def claude_uninstall(project_dir: Path | None = None) -> None:
    """Remove the graphify section from the local CLAUDE.md."""
    target = (project_dir or Path(".")) / "CLAUDE.md"

    if not target.exists():
        print("No CLAUDE.md found in current directory - nothing to do")
        return

    content = target.read_text(encoding="utf-8")
    if _CLAUDE_MD_MARKER not in content:
        print("graphify section not found in CLAUDE.md - nothing to do")
        return

    # Remove the ## graphify section: from the marker to the next ## heading or EOF
    cleaned = re.sub(
        r"\n*## graphify\n.*?(?=\n## |\Z)",
        "",
        content,
        flags=re.DOTALL,
    ).rstrip()
    if cleaned:
        target.write_text(cleaned + "\n", encoding="utf-8")
        print(f"graphify section removed from {target.resolve()}")
    else:
        target.unlink()
        print(f"CLAUDE.md was empty after removal - deleted {target.resolve()}")

    _uninstall_claude_hook(project_dir or Path("."))



def install_project_integration(platform: str, project_dir: Path | None = None) -> None:
    integration = get_integration(platform)
    if integration is None:
        print(f"error: unknown platform '{platform}'. Choose from: {supported_platforms_text()}", file=sys.stderr)
        sys.exit(1)

    if integration.project_context_kind == "claude_md":
        claude_install(project_dir)
    elif integration.project_context_kind == "agents_md":
        _agents_install(project_dir or Path("."), platform)
    else:
        print(f"error: platform '{platform}' does not support project install", file=sys.stderr)
        sys.exit(1)



def uninstall_project_integration(platform: str, project_dir: Path | None = None) -> None:
    integration = get_integration(platform)
    if integration is None:
        print(f"error: unknown platform '{platform}'. Choose from: {supported_platforms_text()}", file=sys.stderr)
        sys.exit(1)

    if integration.project_context_kind == "claude_md":
        claude_uninstall(project_dir)
    elif integration.project_context_kind == "agents_md":
        _agents_uninstall(project_dir or Path("."))
        if integration.project_hook_kind == "codex_pretooluse":
            _uninstall_codex_hook(project_dir or Path("."))
    else:
        print(f"error: platform '{platform}' does not support project uninstall", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    # Check all known skill install locations for a stale version stamp
    for skill_dst in _known_skill_destinations():
        _check_skill_version(skill_dst)

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: graphify <command>")
        print()
        print("Commands:")
        print(f"  install [--platform P]  copy skill to platform config dir ({supported_platforms_text()})")
        print("  query \"<question>\"       BFS traversal of graph.json for a question")
        print("    --dfs                   use depth-first instead of breadth-first")
        print("    --budget N              cap output at N tokens (default 2000)")
        print("    --graph <path>          path to graph.json (default graphify-out/graph.json)")
        print("  benchmark [graph.json]  measure token reduction vs naive full-corpus approach")
        print("  hook install            install post-commit/post-checkout git hooks (all platforms)")
        print("  hook uninstall          remove git hooks")
        print("  hook status             check if git hooks are installed")
        for key in project_command_keys():
            integration = get_integration(key)
            if integration is None:
                continue
            print(_project_help_line(integration, "install"))
            print(_project_help_line(integration, "uninstall"))
        print()
        return

    cmd = sys.argv[1]
    if cmd == "install":
        chosen_platform = _default_install_platform()
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i].startswith("--platform="):
                chosen_platform = args[i].split("=", 1)[1]
                i += 1
            elif args[i] == "--platform" and i + 1 < len(args):
                chosen_platform = args[i + 1]
                i += 2
            else:
                i += 1
        install(platform=chosen_platform)
    elif cmd in project_command_keys():
        subcmd = sys.argv[2] if len(sys.argv) > 2 else ""
        if subcmd == "install":
            install_project_integration(cmd)
        elif subcmd == "uninstall":
            uninstall_project_integration(cmd)
        else:
            print(_project_command_usage(cmd), file=sys.stderr)
            sys.exit(1)
    elif cmd == "hook":
        from graphify.hooks import install as hook_install, uninstall as hook_uninstall, status as hook_status
        subcmd = sys.argv[2] if len(sys.argv) > 2 else ""
        if subcmd == "install":
            print(hook_install(Path(".")))
        elif subcmd == "uninstall":
            print(hook_uninstall(Path(".")))
        elif subcmd == "status":
            print(hook_status(Path(".")))
        else:
            print("Usage: graphify hook [install|uninstall|status]", file=sys.stderr)
            sys.exit(1)
    elif cmd == "query":
        if len(sys.argv) < 3:
            print("Usage: graphify query \"<question>\" [--dfs] [--budget N] [--graph path]", file=sys.stderr)
            sys.exit(1)
        from graphify.serve import _score_nodes, _bfs, _dfs, _subgraph_to_text
        from networkx.readwrite import json_graph
        question = sys.argv[2]
        use_dfs = "--dfs" in sys.argv
        budget = 2000
        graph_path = "graphify-out/graph.json"
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == "--budget" and i + 1 < len(args):
                try:
                    budget = int(args[i + 1])
                except ValueError:
                    print(f"error: --budget must be an integer", file=sys.stderr)
                    sys.exit(1)
                i += 2
            elif args[i].startswith("--budget="):
                try:
                    budget = int(args[i].split("=", 1)[1])
                except ValueError:
                    print(f"error: --budget must be an integer", file=sys.stderr)
                    sys.exit(1)
                i += 1
            elif args[i] == "--graph" and i + 1 < len(args):
                graph_path = args[i + 1]; i += 2
            else:
                i += 1
        # Load graph directly — validate_graph_path restricts to graphify-out/
        # so for custom --graph paths we resolve and load directly after existence check
        gp = Path(graph_path).resolve()
        if not gp.exists():
            print(f"error: graph file not found: {gp}", file=sys.stderr)
            sys.exit(1)
        if not gp.suffix == ".json":
            print(f"error: graph file must be a .json file", file=sys.stderr)
            sys.exit(1)
        try:
            import json as _json
            _raw = _json.loads(gp.read_text(encoding="utf-8"))
            try:
                G = json_graph.node_link_graph(_raw, edges="links")
            except TypeError:
                G = json_graph.node_link_graph(_raw)
        except Exception as exc:
            print(f"error: could not load graph: {exc}", file=sys.stderr)
            sys.exit(1)
        terms = [t.lower() for t in question.split() if len(t) > 2]
        scored = _score_nodes(G, terms)
        if not scored:
            print("No matching nodes found.")
            sys.exit(0)
        start = [nid for _, nid in scored[:5]]
        nodes, edges = (_dfs if use_dfs else _bfs)(G, start, depth=2)
        print(_subgraph_to_text(G, nodes, edges, token_budget=budget))
    elif cmd == "benchmark":
        from graphify.benchmark import run_benchmark, print_benchmark
        graph_path = sys.argv[2] if len(sys.argv) > 2 else "graphify-out/graph.json"
        # Try to load corpus_words from detect output
        corpus_words = None
        detect_path = Path(".graphify_detect.json")
        if detect_path.exists():
            try:
                detect_data = json.loads(detect_path.read_text(encoding="utf-8"))
                corpus_words = detect_data.get("total_words")
            except Exception:
                pass
        result = run_benchmark(graph_path, corpus_words=corpus_words)
        print_benchmark(result)
    else:
        print(f"error: unknown command '{cmd}'", file=sys.stderr)
        print("Run 'graphify --help' for usage.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
