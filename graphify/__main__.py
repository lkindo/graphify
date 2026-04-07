"""graphify CLI - `graphify install` sets up the Claude Code skill."""
from __future__ import annotations
import argparse
import json
import platform
import re
import shutil
import sys
from pathlib import Path
from graphify import __version__


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
                "echo 'graphify: Knowledge graph exists. Read graphify-out/GRAPH_REPORT.md "
                "for god nodes and community structure before searching raw files.' || true"
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


_PLATFORM_CONFIG: dict[str, dict] = {
    "claude": {
        "skill_file": "skill.md",
        "skill_dst": Path(".claude") / "skills" / "graphify" / "SKILL.md",
        "claude_md": True,
    },
    "codex": {
        "skill_file": "skill-codex.md",
        "skill_dst": Path(".agents") / "skills" / "graphify" / "SKILL.md",
        "claude_md": False,
    },
    "opencode": {
        "skill_file": "skill-opencode.md",
        "skill_dst": Path(".config") / "opencode" / "skills" / "graphify" / "SKILL.md",
        "claude_md": False,
    },
    "claw": {
        "skill_file": "skill-claw.md",
        "skill_dst": Path(".claw") / "skills" / "graphify" / "SKILL.md",
        "claude_md": False,
    },
    "droid": {
        "skill_file": "skill-droid.md",
        "skill_dst": Path(".factory") / "skills" / "graphify" / "SKILL.md",
        "claude_md": False,
    },
    "windows": {
        "skill_file": "skill-windows.md",
        "skill_dst": Path(".claude") / "skills" / "graphify" / "SKILL.md",
        "claude_md": True,
    },
}


def install(platform: str = "claude") -> None:
    if platform not in _PLATFORM_CONFIG:
        print(
            f"error: unknown platform '{platform}'. Choose from: {', '.join(_PLATFORM_CONFIG)}",
            file=sys.stderr,
        )
        sys.exit(1)

    cfg = _PLATFORM_CONFIG[platform]
    skill_src = Path(__file__).parent / cfg["skill_file"]
    if not skill_src.exists():
        print(f"error: {cfg['skill_file']} not found in package - reinstall graphify", file=sys.stderr)
        sys.exit(1)

    skill_dst = Path.home() / cfg["skill_dst"]
    skill_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(skill_src, skill_dst)
    (skill_dst.parent / ".graphify_version").write_text(__version__, encoding="utf-8")
    print(f"  skill installed  ->  {skill_dst}")

    if cfg["claude_md"]:
        # Register in ~/.claude/CLAUDE.md (Claude Code only)
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
    print()
    print(f"{platform.capitalize()} will now check the knowledge graph before answering")
    print("codebase questions and rebuild it after code changes.")
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


def _default_platform() -> str:
    return "windows" if platform.system() == "Windows" else "claude"


def _build_graph(path: Path, out_dir: Path, no_viz: bool = False) -> None:
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.detect import detect, save_manifest
    from graphify.export import to_html, to_json
    from graphify.extract import extract
    from graphify.report import generate

    detection = detect(path)
    code_files = [Path(p) for p in detection["files"].get("code", [])]
    if not code_files:
        print(f"error: no supported code files found in {path}", file=sys.stderr)
        sys.exit(1)

    extraction = extract(code_files)
    G = build_from_json(extraction)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    labels = {cid: f"Community {cid}" for cid in communities}
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    questions = suggest_questions(G, communities, labels)
    token_cost = {
        "input": extraction.get("input_tokens", 0),
        "output": extraction.get("output_tokens", 0),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    to_json(G, communities, str(out_dir / "graph.json"))
    if not no_viz:
        to_html(G, communities, str(out_dir / "graph.html"), community_labels=labels)

    report = generate(
        G,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        token_cost,
        str(path),
        suggested_questions=questions,
    )
    (out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    save_manifest(detection["files"], manifest_path=str(out_dir / "manifest.json"))

    print(f"Graph built for {path.resolve()}")
    print(f"- Nodes: {G.number_of_nodes()} · Edges: {G.number_of_edges()} · Communities: {len(communities)}")
    print(f"- Wrote {out_dir / 'graph.json'}")
    print(f"- Wrote {out_dir / 'GRAPH_REPORT.md'}")
    if no_viz:
        print("- Skipped HTML visualization (--no-viz)")
    else:
        print(f"- Wrote {out_dir / 'graph.html'}")


def _query_graph(question: str, use_dfs: bool, budget: int, graph_path: str) -> None:
    from graphify.serve import _bfs, _dfs, _load_graph, _score_nodes, _subgraph_to_text

    G = _load_graph(graph_path)
    terms = [term.lower() for term in question.split() if len(term) > 2]
    scored = _score_nodes(G, terms)
    if not scored:
        print("No matching nodes found.")
        return
    start = [node_id for _, node_id in scored[:5]]
    nodes, edges = (_dfs if use_dfs else _bfs)(G, start, depth=2)
    print(_subgraph_to_text(G, nodes, edges, token_budget=budget))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="graphify", description="Graphify command line interface")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    install_parser = subparsers.add_parser("install", help="install graphify skill files")
    install_parser.add_argument("--platform", choices=sorted(_PLATFORM_CONFIG.keys()), default=_default_platform())

    build_parser = subparsers.add_parser("build", help="build graph outputs directly from CLI (AST-only)")
    build_parser.add_argument("path", nargs="?", default=".", help="path to analyze")
    build_parser.add_argument("--out", default="graphify-out", help="output directory")
    build_parser.add_argument("--no-viz", action="store_true", help="skip HTML visualization")

    query_parser = subparsers.add_parser("query", help="query graph.json from the terminal")
    query_parser.add_argument("question", help="natural-language query")
    query_parser.add_argument("--dfs", action="store_true", help="use depth-first traversal")
    query_parser.add_argument("--budget", type=int, default=2000, help="token budget for response text")
    query_parser.add_argument("--graph", default="graphify-out/graph.json", help="path to graph.json")

    benchmark_parser = subparsers.add_parser("benchmark", help="measure token reduction vs naive full-corpus approach")
    benchmark_parser.add_argument("graph_path", nargs="?", default="graphify-out/graph.json")

    hook_parser = subparsers.add_parser("hook", help="manage git hooks")
    hook_parser.add_argument("action", choices=["install", "uninstall", "status"])

    claude_parser = subparsers.add_parser("claude", help="manage CLAUDE.md integration")
    claude_parser.add_argument("action", choices=["install", "uninstall"])

    for platform_name in ("codex", "opencode", "claw", "droid"):
        platform_parser = subparsers.add_parser(platform_name, help=f"manage {platform_name} AGENTS.md integration")
        platform_parser.add_argument("action", choices=["install", "uninstall"])

    return parser


def main(argv: list[str] | None = None) -> None:
    # Check all known skill install locations for stale version stamps.
    for cfg in _PLATFORM_CONFIG.values():
        _check_skill_version(Path.home() / cfg["skill_dst"])

    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return

    if args.command == "install":
        install(platform=args.platform)
    elif args.command == "build":
        _build_graph(Path(args.path), Path(args.out), no_viz=args.no_viz)
    elif args.command == "query":
        _query_graph(args.question, use_dfs=args.dfs, budget=args.budget, graph_path=args.graph)
    elif args.command == "claude":
        if args.action == "install":
            claude_install()
        else:
            claude_uninstall()
    elif args.command in ("codex", "opencode", "claw", "droid"):
        if args.action == "install":
            _agents_install(Path("."), args.command)
        else:
            _agents_uninstall(Path("."))
    elif args.command == "hook":
        from graphify.hooks import install as hook_install, uninstall as hook_uninstall, status as hook_status
        if args.action == "install":
            print(hook_install(Path(".")))
        elif args.action == "uninstall":
            print(hook_uninstall(Path(".")))
        else:
            print(hook_status(Path(".")))
    elif args.command == "benchmark":
        from graphify.benchmark import run_benchmark, print_benchmark

        corpus_words = None
        detect_path = Path(".graphify_detect.json")
        if detect_path.exists():
            try:
                detect_data = json.loads(detect_path.read_text(encoding="utf-8"))
                corpus_words = detect_data.get("total_words")
            except Exception:
                pass
        result = run_benchmark(args.graph_path, corpus_words=corpus_words)
        print_benchmark(result)


if __name__ == "__main__":
    main()
