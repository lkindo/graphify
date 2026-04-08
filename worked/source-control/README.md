# Source Management Workflow

Demonstrates `/graphify source add|list|reload|delete` — register directories as persistent sources and rebuild their graphs with a single command. No need to remember paths or re-run manually after each commit.

## What this demos

The source management system stores a registry of paths in `graphify-out/sources.json`. Once registered, `/graphify source reload` runs an incremental rebuild on every source, re-extracting only files that changed since the last run.

This worked example uses `worked/example/raw/` as the corpus — a 7-file document+code pipeline with clear call relationships.

## Input corpus

```
worked/example/raw/
├── parser.py        — reads files, detects format, kicks off the pipeline
├── validator.py     — schema checks, calls processor for text normalization
├── processor.py     — keyword extraction, cross-reference detection
├── storage.py       — persists everything, maintains the index
├── api.py           — HTTP handlers that orchestrate the above four modules
├── architecture.md  — design decisions and module responsibilities
└── notes.md         — open questions and tradeoffs
```

## How to reproduce

```bash
pip install graphifyy
graphify install   # Claude Code
```

Open Claude Code from the repo root and run:

```
# Step 1 — register the source
/graphify source add ./worked/example/raw

# Step 2 — confirm it was registered
/graphify source list

# Step 3 — run the full incremental pipeline on all registered sources
/graphify source reload
```

Output lands in `worked/example/raw/graphify-out/` — the same `graph.json`, `GRAPH_REPORT.md`, and `graph.html` you'd get from running `/graphify ./worked/example/raw` directly.

## What to expect

```
Sources to reload: 1
  /path/to/worked/example/raw

Reloading /path/to/worked/example/raw ...
  7 new/changed file(s) to re-extract.
  AST: 47 nodes, 52 edges
  Semantic extraction: ~2 files → 1 agent, estimated ~45s
  Merged: 56 nodes, 61 edges
  Graph: 56 nodes, 61 edges, 2 communities

Reload complete.
  /path/to/worked/example/raw  →  56 nodes, 61 edges
```

After running, ask questions from your AI coding assistant:

- "what calls storage directly?"
- "what does the architecture doc say about validator design?"
- "which module has the most connections?"

## After a simulated commit

To test the incremental update path, modify one file and reload:

```bash
# simulate a file change
echo "# updated" >> worked/example/raw/parser.py

# reload — only parser.py gets re-extracted
/graphify source reload
```

The manifest in `worked/example/raw/graphify-out/manifest.json` tracks file mtimes. Only modified files are re-extracted, so reload is fast on large corpora.

## Removing a source

```
/graphify source delete ./worked/example/raw
/graphify source list   # should show empty registry
```

## Reference output

`GRAPH_REPORT.md` and `sources.json` in this directory are reference snapshots from a real run. Your output will differ slightly (node IDs, community labels) but the structure should match.

The `sources.json` path will be machine-specific — it stores the absolute path resolved on the machine where the source was added.
