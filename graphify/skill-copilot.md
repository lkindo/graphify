---
name: graphify
description: >
  Turn any folder of code, docs, papers, or images into a queryable knowledge graph.
  Use when the user types /graphify, asks to build a knowledge graph, understand a codebase,
  find connections between files, or wants to explore code architecture. Generates HTML,
  JSON, Obsidian vault, and a plain-language audit report.
allowed-tools: shell
---

# /graphify

Turn any folder of files into a navigable knowledge graph with community detection, an honest audit trail, and three primary outputs: interactive HTML, `graph.json`, and `GRAPH_REPORT.md`.

## GitHub Copilot CLI requirements

This is the macOS/Linux Copilot skill. Use POSIX shell commands here. On Windows, graphify installs a separate PowerShell-specific Copilot skill automatically.

If no path was given, use `.`. Only ask the user for a narrower path when the corpus is too large.

## What you must do when invoked

### Step 1 - Ensure `graphify` is importable

Use shell commands and prefer this order:

1. Try `python -c "import graphify"`.
2. If that fails, try `python3 -c "import graphify"`.
3. If graphify is still unavailable, install it with `python -m pip install graphifyy` or `python3 -m pip install graphifyy`.
4. Write the chosen interpreter path to `.graphify_python`.

Example shell flow:

```bash
GRAPHIFY_BIN=$(which graphify 2>/dev/null)
if [ -n "$GRAPHIFY_BIN" ]; then
    PYTHON=$(head -1 "$GRAPHIFY_BIN" | tr -d '#!')
elif python -c "import graphify" >/dev/null 2>&1; then
    PYTHON="python"
else
    PYTHON="python3"
fi
$PYTHON -c "import graphify" >/dev/null 2>&1 || $PYTHON -m pip install graphifyy
$PYTHON -c "import sys; open('.graphify_python', 'w').write(sys.executable)"
```

### Step 2 - Detect the corpus

Use the interpreter recorded in `.graphify_python`:

```bash
$(cat .graphify_python) -c "import json; from pathlib import Path; from graphify.detect import detect; result = detect(Path('INPUT_PATH')); Path('.graphify_detect.json').write_text(json.dumps(result), encoding='utf-8')"
```

Do not print the raw JSON. Summarize it like this:

```text
Corpus: X files · ~Y words
  code:   N files
  docs:   N files
  papers: N files
  images: N files
```

Then:

- If `total_files == 0`, stop with `No supported files found in [path].`
- If sensitive files were skipped, mention only the count.
- If `total_words > 2_000_000` or `total_files > 200`, summarize the busiest subdirectories and ask the user which subfolder to run on.
- Otherwise continue immediately.

### Step 3 - Structural extraction for code files

Run AST extraction first:

```bash
$(cat .graphify_python) -c "import json; from pathlib import Path; from graphify.extract import collect_files, extract; detect = json.loads(Path('.graphify_detect.json').read_text(encoding='utf-8')); code_files = []; [code_files.extend(collect_files(Path(f)) if Path(f).is_dir() else [Path(f)]) for f in detect.get('files', {}).get('code', [])]; result = extract(code_files) if code_files else {'nodes': [], 'edges': [], 'hyperedges': [], 'input_tokens': 0, 'output_tokens': 0}; Path('.graphify_ast.json').write_text(json.dumps(result, indent=2), encoding='utf-8'); print(f'AST: {len(result["nodes"])} nodes, {len(result["edges"])} edges')"
```

If there are no code files, write the empty JSON and continue.

### Step 4 - Semantic extraction for docs, papers, and images

GitHub Copilot CLI should read uncached files directly and extract concepts sequentially in chunks of roughly 20-25 files.

Before extracting, check cache:

```bash
$(cat .graphify_python) -c "import json; from pathlib import Path; from graphify.cache import check_semantic_cache; detect = json.loads(Path('.graphify_detect.json').read_text(encoding='utf-8')); all_files = [f for files in detect['files'].values() for f in files]; cached_nodes, cached_edges, cached_hyperedges, uncached = check_semantic_cache(all_files); import json as _json; open('.graphify_uncached.txt', 'w', encoding='utf-8').write('\n'.join(uncached)); Path('.graphify_cached.json').write_text(_json.dumps({'nodes': cached_nodes, 'edges': cached_edges, 'hyperedges': cached_hyperedges}), encoding='utf-8') if (cached_nodes or cached_edges or cached_hyperedges) else None; print(f'Cache: {len(all_files)-len(uncached)} files hit, {len(uncached)} files need extraction')"
```

Extraction rules:

- Explicit relationships are `EXTRACTED` with `confidence_score: 1.0`.
- Reasonable indirect links are `INFERRED` with `confidence_score` between `0.6` and `0.9`.
- Uncertain links are `AMBIGUOUS` with `confidence_score` between `0.1` and `0.3`.
- Code files should only add semantic edges AST did not already provide.
- Doc and paper files should extract named concepts, citations, rationale, and trade-offs.
- Image files should reason about the image content, not only OCR.
- In `--mode deep`, be more aggressive with `INFERRED` edges.

Write fresh semantic output to `.graphify_semantic_new.json`, then save cache and merge into `.graphify_semantic.json`.

### Step 5 - Build, analyze, cluster, and export

Using `.graphify_python`, call the Python modules under `graphify.build`, `graphify.cluster`, `graphify.analyze`, `graphify.report`, and `graphify.export`.

Produce at least:

- `graphify-out/graph.json`
- `graphify-out/GRAPH_REPORT.md`
- `graphify-out/graph.html` unless `--no-viz` was requested

If optional flags such as `--svg`, `--graphml`, `--neo4j`, `--wiki`, or `--obsidian` were requested, run the matching exporter too.

### Step 6 - Clean up temporary files

Use POSIX cleanup:

```bash
rm -f .graphify_cached.json .graphify_uncached.txt .graphify_semantic_new.json
```

### Step 7 - Report results

End with a concise summary that includes:

- corpus size
- nodes / edges / communities
- output paths
- whether cache was used

If any step fails, surface the exact failing step and command output instead of silently degrading.
