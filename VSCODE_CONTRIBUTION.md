# VS Code GitHub Copilot Chat Support

**Status:** Ready for review  
**Target:** [safishamsi/graphify](https://github.com/safishamsi/graphify)  
**Fork:** [courasneto/graphify](https://github.com/courasneto/graphify)

---

## Summary

This contribution adds first-class support for **VS Code GitHub Copilot Chat** — which is distinct from GitHub Copilot CLI and was previously unsupported or incorrectly mapped to the same install path.

Three files changed, one file added.

---

## Problem

Running `graphify copilot install` installs a skill file for **GitHub Copilot CLI** (the terminal tool, `gh copilot suggest`). However, a large share of GitHub Copilot users work primarily through the **VS Code Copilot Chat panel** — a fundamentally different product with different capabilities and constraints:

| | GitHub Copilot CLI | VS Code Copilot Chat |
|---|---|---|
| Interface | Terminal | Editor chat panel |
| Terminal type | bash (Unix) | PowerShell (Windows) / bash (Mac/Linux) |
| Always-on config | — | `.github/copilot-instructions.md` |
| Skill trigger | `/graphify` | `/graphify` |
| Tool hooks | Not applicable | Not applicable (uses `copilot-instructions.md`) |

**Gaps before this PR:**

1. **No always-on mechanism for VS Code.** `copilot install` only copies SKILL.md to `~/.copilot/skills/`. VS Code reads `.github/copilot-instructions.md` automatically for every workspace session — equivalent to `CLAUDE.md` for Claude Code or `.cursor/rules/` for Cursor. This was missing.

2. **Skill uses bash-only syntax.** `skill-copilot.md` contains bash heredocs, variable assignments (`VAR=$(command)`), conditionals (`[ -f file ]`), and redirects that fail silently in Windows PowerShell — the default terminal for the majority of VS Code users on Windows.

3. **No `graphify vscode install` command.** Users working in VS Code had no dedicated setup path.

---

## Solution

### New command: `graphify vscode install`

Runs two actions:

1. **Copies `skill-vscode.md`** to `~/.copilot/skills/graphify/SKILL.md` — a VS Code-optimized skill with Python-only commands (no bash syntax).

2. **Writes `.github/copilot-instructions.md`** in the project root — VS Code reads this automatically, making the graph context always available without any hook mechanism.

```
$ graphify vscode install

  skill installed  ->  C:\Users\you\.copilot\skills\graphify\SKILL.md
  .github/copilot-instructions.md  ->  created

VS Code GitHub Copilot Chat is configured.

Next steps:
  1. Build the graph: type /graphify in Copilot Chat
  2. Copilot will read GRAPH_REPORT.md before answering architecture questions

Note: this configures VS Code Copilot Chat (chat panel in editor).
      For GitHub Copilot CLI (terminal), use: graphify copilot install
```

```
$ graphify vscode uninstall
```

Also included:

- `graphify install --platform vscode` — alias for the same skill install (without the always-on file)

### New skill: `skill-vscode.md`

A complete rewrite of the skill execution steps using **Python-only commands** that work identically on:

- Windows PowerShell (default in VS Code on Windows)
- macOS bash/zsh
- Linux bash

Key differences from `skill-copilot.md`:

| Pattern | `skill-copilot.md` (bash) | `skill-vscode.md` (Python) |
|---|---|---|
| mkdir | `mkdir -p graphify-out` | `Path('graphify-out').mkdir(exist_ok=True)` |
| Write to file | `python -c "..." > file.json` | `Path('file.json').write_text(json.dumps(...))` |
| Read from file | `$(cat graphify-out/.graphify_python)` | `Path('file').read_text()` in next Python call |
| Conditional check | `[ -f file ] && ... \|\| true` | `if Path('file').exists():` |
| Variable assign | `VAR=$(python -c "...")` | Python variable inside single -c block |

No bash pipes, no shell redirects, no `&&`/`||` operators.

### `__main__.py` changes

- Added `_VSCODE_INSTRUCTIONS_SECTION` and `_VSCODE_INSTRUCTIONS_MARKER` constants
- Added `vscode_install(project_dir)` and `vscode_uninstall(project_dir)` functions  
- Added `"vscode"` to `_PLATFORM_CONFIG` dict
- Added `vscode` CLI command handler (`graphify vscode install/uninstall`)
- Updated help text with new command entries

### `README.md` changes

- Added VS Code to the tagline and requirements list
- Added VS Code row to both platform install tables
- Added VS Code explanation in the "always-on" section
- Added `> Copilot CLI vs VS Code Copilot Chat` callout clarifying the distinction
- Added `graphify vscode install` to the usage reference block

---

## Files changed

```
graphify/skill-vscode.md    NEW   — cross-platform VS Code skill (Python-only commands)
graphify/__main__.py        MOD   — vscode_install/uninstall + config + CLI handler + help
README.md                   MOD   — VS Code platform entries + always-on explanation
```

---

## Testing

Tested manually on Windows 11 with VS Code 1.99 + GitHub Copilot Chat extension:

1. `graphify vscode install` → created `~/.copilot/skills/graphify/SKILL.md` and `.github/copilot-instructions.md` ✓
2. Typed `/graphify src` in Copilot Chat → skill loaded, Python commands executed in PowerShell ✓
3. Graph built: 853 nodes, 1841 edges, 28 communities from a 194-file TypeScript/React codebase ✓
4. `graphify vscode uninstall` → skill and instructions removed cleanly ✓
5. Existing `graphify copilot install` behavior unchanged ✓

---

## Backwards compatibility

- **No breaking changes.** All existing commands (`claude`, `codex`, `copilot`, `cursor`, `gemini`, etc.) are unchanged.
- `graphify copilot install` continues to work as before (Copilot CLI, bash-based skill).
- The new `vscode` command is purely additive.

---

## Motivation

I discovered this gap while trying to use graphify in VS Code on Windows. The `copilot install` command ran fine but Copilot Chat had no awareness of the graph between sessions (no always-on file), and the skill steps failed in PowerShell because of bash-specific syntax. This contribution fixes both issues with minimal, targeted changes.
