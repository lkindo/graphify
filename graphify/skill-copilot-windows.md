---
name: graphify
description: >
  Turn any folder of code, docs, papers, or images into a queryable knowledge graph.
  Use when the user types /graphify, asks to build a knowledge graph, understand a codebase,
  find connections between files, or wants to explore code architecture. Generates HTML,
  JSON, Obsidian vault, and a plain-language audit report.
allowed-tools:
  - powershell
  - view
  - glob
  - rg
  - ask_user
---

# /graphify

Turn any folder of files into a navigable knowledge graph with community detection, an honest audit trail, and three primary outputs: interactive HTML, `graph.json`, and `GRAPH_REPORT.md`.

## Usage

```
/graphify
/graphify <path>
/graphify <path> --mode deep
/graphify <path> --update
/graphify <path> --cluster-only
/graphify <path> --no-viz
/graphify <path> --svg
/graphify <path> --graphml
/graphify <path> --neo4j
/graphify <path> --neo4j-push bolt://localhost:7687
/graphify <path> --mcp
/graphify <path> --watch
/graphify add <url>
/graphify query "<question>"
/graphify path "Node A" "Node B"
/graphify explain "Node"
```

## GitHub Copilot CLI requirements

This platform uses PowerShell-oriented commands and Copilot CLI tools. Do not emit bash-specific commands such as `which`, `rm -f`, `$(cat file)`, or `python3`-only instructions without a Windows fallback.

If no path was given, use `.`. Only ask the user for a narrower path when the corpus is too large.

## What you must do when invoked

### Step 1 - Ensure `graphify` is importable

Use the `powershell` tool and prefer this order:

1. Try `python -c "import graphify"`.
2. If that fails and `py` exists, try `py -3 -c "import graphify"`.
3. If graphify is still unavailable, install it with `python -m pip install graphifyy`.
4. Write the chosen interpreter path to `.graphify_python`.

Example PowerShell:

```powershell
$chosen = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
  try { python -c "import graphify"; if ($LASTEXITCODE -eq 0) { $chosen = "python" } } catch {}
}
if (-not $chosen -and (Get-Command py -ErrorAction SilentlyContinue)) {
  try { py -3 -c "import graphify"; if ($LASTEXITCODE -eq 0) { $chosen = "py -3" } } catch {}
}
if (-not $chosen) {
  $chosen = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py -3" }
  & $chosen -m pip install graphifyy
}
$exe = (& $chosen -c "import sys; print(sys.executable)").Trim()
Set-Content -Path .graphify_python -Value $exe -NoNewline
```

### Step 2 - Detect the corpus

Use the interpreter recorded in `.graphify_python`:

```powershell
$py = Get-Content .graphify_python -Raw
& $py -c "import json; from pathlib import Path; from graphify.detect import detect; result = detect(Path('INPUT_PATH')); Path('.graphify_detect.json').write_text(json.dumps(result), encoding='utf-8')"
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

```powershell
$py = Get-Content .graphify_python -Raw
& $py -c "import json; from pathlib import Path; from graphify.extract import collect_files, extract; detect = json.loads(Path('.graphify_detect.json').read_text(encoding='utf-8')); code_files = []; [code_files.extend(collect_files(Path(f)) if Path(f).is_dir() else [Path(f)]) for f in detect.get('files', {}).get('code', [])]; result = extract(code_files) if code_files else {'nodes': [], 'edges': [], 'hyperedges': [], 'input_tokens': 0, 'output_tokens': 0}; Path('.graphify_ast.json').write_text(json.dumps(result, indent=2), encoding='utf-8'); print(f'AST: {len(result["nodes"])} nodes, {len(result["edges"])} edges')"
```

If there are no code files, write the empty JSON and continue.

### Step 4 - Semantic extraction for docs, papers, and images

GitHub Copilot CLI should read uncached files directly and extract concepts sequentially in chunks of roughly 20-25 files.

Before extracting, check cache:

```powershell
$py = Get-Content .graphify_python -Raw
& $py -c "import json; from pathlib import Path; from graphify.cache import check_semantic_cache; detect = json.loads(Path('.graphify_detect.json').read_text(encoding='utf-8')); all_files = [f for files in detect['files'].values() for f in files]; cached_nodes, cached_edges, cached_hyperedges, uncached = check_semantic_cache(all_files); import json as _json; Path('.graphify_uncached.txt').write_text('\n'.join(uncached), encoding='utf-8'); Path('.graphify_cached.json').write_text(_json.dumps({'nodes': cached_nodes, 'edges': cached_edges, 'hyperedges': cached_hyperedges}), encoding='utf-8') if (cached_nodes or cached_edges or cached_hyperedges) else None; print(f'Cache: {len(all_files)-len(uncached)} files hit, {len(uncached)} files need extraction')"
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

Use PowerShell cleanup, not `rm -f`:

```powershell
Remove-Item .graphify_cached.json, .graphify_uncached.txt, .graphify_semantic_new.json -ErrorAction SilentlyContinue
```

### Step 7 - Report results

End with a concise summary that includes:

- corpus size
- nodes / edges / communities
- output paths
- whether cache was used

If any step fails, surface the exact failing step and command output instead of silently degrading.
