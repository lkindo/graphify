# Source Management Workflow - Evaluation (2026-04-08)

**Corpus:** `worked/example/raw/` — 7 files (5 Python + 2 Markdown), ~2,159 words  
**Pipeline:** `/graphify source add` → `/graphify source list` → `/graphify source reload`  
**Graph output:** 73 nodes, 112 edges, 5 communities

---

## Workflow Assessment

### add / list / delete — Score: 9/10

**What works well:**
- `add` resolves relative paths to absolute before storing — no surprises if you run reload from a different working directory.
- inode stored alongside path — if you rename the directory within the same parent, `list` detects the new name and shows status `RENAMED` instead of `MISSING`.
- `list` shows status at a glance: `[OK]` / `[RENAMED]` / `[MISSING]`, with the date added.
- `delete` works by both path match and inode match — if you've already renamed the directory, delete still finds and removes the entry.
- `sources.json` lives in `graphify-out/` alongside `graph.json` and `GRAPH_REPORT.md`, so the whole graphify state for a project is in one directory.

**Limitations:**
- inode tracking only works within the same parent directory. Cross-filesystem moves (e.g., mounting a drive at a different path) require manually deleting the old entry and adding the new path.
- No bulk add (e.g., `source add ./repos/*`). Each path is added individually.

---

### reload — Score: 8/10

**What works well:**
- Incremental by default: only re-extracts files changed since the last run (manifest-based). On the 7-file corpus, a single-file edit → only that file gets re-extracted.
- Code-only detection: if all changed files are code files, semantic LLM extraction is skipped entirely. Reload is instant for code-only changes.
- Output isolation: each source's `graphify-out/` is independent. Reloading source A doesn't touch source B's graph.
- Sequential processing prevents temp file conflicts when multiple sources are registered.

**Limitations:**
- First reload on a source with no prior manifest treats all files as new — same cost as a full run. Expected behavior but worth knowing.
- No parallel reload across sources. With many large sources this can be slow. Acceptable for the common case (1-3 repos).
- If a source path is renamed between `add` and `reload`, the skill resolves via inode, but the output directory (`<old_path>/graphify-out/`) still refers to the old path. The manifest and cache stay valid; only the directory location differs. In practice: rename the directory, run reload, outputs go to `<new_path>/graphify-out/` fresh.

---

## Graph Quality (from reload on the example corpus)

The graph output is identical to running `/graphify ./worked/example/raw` directly — as expected.

- **73 nodes, 112 edges, 5 communities**
- `ValidationError` is the god node (11 edges) — correctly identifies it as the cross-cutting exception type
- Communities map cleanly to modules: Storage / API / Parser / Processor / Validator
- Docs (`notes.md`, `architecture.md`) not included in this reference run — would add semantic edges on a full `/graphify source reload` with LLM extraction enabled

---

## Recommended usage patterns

**Single repo, always up to date:**
```
/graphify source add ./             # register current project root
/graphify source reload             # after each significant change
```

**Multi-repo research:**
```
/graphify source add ./repo-a
/graphify source add ./repo-b
/graphify source add ./papers
/graphify source reload             # rebuilds all three incrementally
```

**After a rename:**
```
mv old-name new-name
/graphify source list               # shows [RENAMED] → /new-name
/graphify source reload             # works correctly via inode resolution
```

**Cleanup:**
```
/graphify source delete ./old-path
/graphify source list               # confirm removed
```
