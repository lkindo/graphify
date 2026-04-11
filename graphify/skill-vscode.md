---
name: graphify
description: any input (code, docs, papers, images) → knowledge graph → clustered communities → HTML + JSON + audit report
trigger: /graphify
---

# /graphify (VS Code — GitHub Copilot Chat)

Turn any folder of files into a navigable knowledge graph with community detection, an honest audit trail, and three outputs: interactive HTML, GraphRAG-ready JSON, and a plain-language GRAPH_REPORT.md.

**Platform note:** This skill uses Python for all intermediate steps — no bash syntax. It works on Windows (PowerShell), macOS, and Linux without modification.

## Usage

```
/graphify                          # run on current directory
/graphify ./src                    # run on a specific subfolder
/graphify ./src --mode deep        # richer INFERRED edge extraction
/graphify ./src --update           # re-extract only changed files
/graphify ./src --no-viz           # skip HTML, just report + JSON

/graphify query "what is the auth flow?"
/graphify path "AuthModule" "Database"
/graphify explain "NutriApiRequest"
```

## What graphify is for

graphify is built around Andrej Karpathy's /raw folder workflow: drop anything into a folder — papers, tweets, screenshots, code, notes — and get a structured knowledge graph that shows you what you didn't know was connected.

Three things it does that Copilot alone cannot:
1. **Persistent graph** — relationships stored in `graphify-out/graph.json` survive across sessions.
2. **Honest audit trail** — every edge tagged EXTRACTED, INFERRED, or AMBIGUOUS. You know what was found vs invented.
3. **Cross-document surprise** — community detection finds connections between files you'd never think to ask about.

## What You Must Do When Invoked

If no path was given, use `.` (current directory). Do not ask the user for a path.

Follow these steps in order. Do not skip steps.

**All commands use `python` — they work on Windows PowerShell and Mac/Linux terminals without change.**

---

### Step 1 — Ensure graphify is installed

```python
python -c "
import sys, subprocess
from pathlib import Path
Path('graphify-out').mkdir(exist_ok=True)
Path('graphify-out/.graphify_python').write_text(sys.executable)
try:
    import graphify
    print('graphify ready:', sys.executable)
except ImportError:
    print('Installing graphify...')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'graphifyy', '-q'])
    print('graphify installed')
"
```

If the import succeeds, print nothing and proceed.

---

### Step 2 — Detect files

```python
python -c "
import json
from graphify.detect import detect
from pathlib import Path
result = detect(Path('INPUT_PATH'))
Path('graphify-out/.graphify_detect.json').write_text(json.dumps(result, indent=2))
files = result.get('files', {})
print('Corpus:')
for cat, lst in files.items():
    if lst:
        print(f'  {cat}: {len(lst)} files ({str(lst[0])[:60]}...)')
total_w = result.get('total_words', 0)
print(f'Total: {result.get(\"total_files\")} files ~{total_w:,} words')
"
```

Replace `INPUT_PATH` with the actual path the user gave (default `.`). Do NOT print the raw JSON — present the clean summary above.

Then act on it:
- If `total_files` is 0: stop with "No supported files found in [path]."
- If `total_files` > 200 or `total_words` > 2,000,000: show the top 5 subdirectories by file count and ask the user which subfolder to proceed with.
- Otherwise: proceed to Step 3.

---

### Step 3A — AST extraction (code files, deterministic)

**Run Step 3A and Step 3B at the same time.**

```python
python -c "
import json
from graphify.extract import collect_files, extract
from pathlib import Path
detect = json.loads(Path('graphify-out/.graphify_detect.json').read_text())
code_files = [
    p
    for f in detect.get('files', {}).get('code', [])
    for p in (collect_files(Path(f)) if Path(f).is_dir() else [Path(f)])
]
if code_files:
    result = extract(code_files)
    Path('graphify-out/.graphify_ast.json').write_text(json.dumps(result, indent=2))
    print(f'AST: {len(result[\"nodes\"])} nodes, {len(result[\"edges\"])} edges')
else:
    Path('graphify-out/.graphify_ast.json').write_text(
        json.dumps({'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0})
    )
    print('No code files — skipping AST')
"
```

---

### Step 3B — Semantic extraction (docs, papers, images)

**Fast path:** If detection found zero docs, papers, and images, skip to Step 3C:

```python
python -c "
import json
from pathlib import Path
Path('graphify-out/.graphify_semantic.json').write_text(
    json.dumps({'nodes':[],'edges':[],'hyperedges':[],'input_tokens':0,'output_tokens':0})
)
print('No doc/image files — skipping semantic extraction')
"
```

**Otherwise:** First check the SHA256 cache to avoid re-processing unchanged files:

```python
python -c "
import json
from graphify.cache import check_semantic_cache
from pathlib import Path
detect = json.loads(Path('graphify-out/.graphify_detect.json').read_text())
non_code = [f for cat, lst in detect['files'].items() for f in lst if cat != 'code']
cached_nodes, cached_edges, cached_hyperedges, uncached = check_semantic_cache(non_code)
if cached_nodes or cached_edges:
    Path('graphify-out/.graphify_cached.json').write_text(
        json.dumps({'nodes': cached_nodes, 'edges': cached_edges, 'hyperedges': cached_hyperedges})
    )
Path('graphify-out/.graphify_uncached.txt').write_text('\n'.join(uncached))
print(f'Cache: {len(non_code)-len(uncached)} hits, {len(uncached)} need extraction')
if uncached:
    for f in uncached:
        print(f'  {f}')
"
```

For each uncached file, **read the file** and extract a knowledge graph fragment. Combine all results into a single JSON object matching this schema and write it to `graphify-out/.graphify_semantic_new.json`:

```json
{
  "nodes": [{"id": "filestem_concept", "label": "Human Readable Name", "file_type": "document|paper|image", "source_file": "relative/path", "source_location": null, "source_url": null, "captured_at": null, "author": null, "contributor": null}],
  "edges": [{"source": "node_id", "target": "node_id", "relation": "references|cites|conceptually_related_to|rationale_for|semantically_similar_to", "confidence": "EXTRACTED|INFERRED|AMBIGUOUS", "confidence_score": 1.0, "source_file": "relative/path", "source_location": null, "weight": 1.0}],
  "hyperedges": [],
  "input_tokens": 0,
  "output_tokens": 0
}
```

Rules:
- EXTRACTED = relationship explicit in source (confidence_score: 1.0)
- INFERRED = reasonable inference (0.6–0.9, reason about each individually)
- AMBIGUOUS = uncertain (0.1–0.3)
- Never omit `confidence_score`, never use 0.5 as a default

Merge cache + new results:

```python
python -c "
import json
from graphify.cache import save_semantic_cache
from pathlib import Path
new = json.loads(Path('graphify-out/.graphify_semantic_new.json').read_text()) if Path('graphify-out/.graphify_semantic_new.json').exists() else {'nodes':[],'edges':[],'hyperedges':[]}
cached = json.loads(Path('graphify-out/.graphify_cached.json').read_text()) if Path('graphify-out/.graphify_cached.json').exists() else {'nodes':[],'edges':[],'hyperedges':[]}
seen = set()
all_nodes = []
for n in cached.get('nodes',[]) + new.get('nodes',[]):
    if n['id'] not in seen:
        seen.add(n['id'])
        all_nodes.append(n)
merged = {
    'nodes': all_nodes,
    'edges': cached.get('edges',[]) + new.get('edges',[]),
    'hyperedges': cached.get('hyperedges',[]) + new.get('hyperedges',[]),
    'input_tokens': new.get('input_tokens', 0),
    'output_tokens': new.get('output_tokens', 0),
}
Path('graphify-out/.graphify_semantic.json').write_text(json.dumps(merged, indent=2))
save_semantic_cache(new.get('nodes',[]), new.get('edges',[]), new.get('hyperedges',[]))
print(f'Semantic: {len(all_nodes)} nodes, {len(merged[\"edges\"])} edges')
"
```

---

### Step 3C — Merge AST + semantic

Wait for both Step 3A and Step 3B to complete, then:

```python
python -c "
import json
from pathlib import Path
ast = json.loads(Path('graphify-out/.graphify_ast.json').read_text())
sem = json.loads(Path('graphify-out/.graphify_semantic.json').read_text())
seen = {n['id'] for n in ast['nodes']}
nodes = list(ast['nodes'])
for n in sem['nodes']:
    if n['id'] not in seen:
        nodes.append(n)
        seen.add(n['id'])
extract = {
    'nodes': nodes,
    'edges': ast['edges'] + sem['edges'],
    'hyperedges': sem.get('hyperedges', []),
    'input_tokens': sem.get('input_tokens', 0),
    'output_tokens': sem.get('output_tokens', 0),
}
Path('graphify-out/.graphify_extract.json').write_text(json.dumps(extract, indent=2))
print(f'Merged: {len(nodes)} nodes, {len(extract[\"edges\"])} edges ({len(ast[\"nodes\"])} AST + {len(sem[\"nodes\"])} semantic)')
"
```

---

### Step 4 — Build graph, cluster, analyze, generate initial report

```python
python -c "
import json
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from graphify.export import to_json
from pathlib import Path
extract = json.loads(Path('graphify-out/.graphify_extract.json').read_text())
detection = json.loads(Path('graphify-out/.graphify_detect.json').read_text())
G = build_from_json(extract)
if G.number_of_nodes() == 0:
    print('ERROR: Graph is empty — extraction produced no nodes.')
    raise SystemExit(1)
communities = cluster(G)
cohesion = score_all(G, communities)
tokens = {'input': extract.get('input_tokens',0), 'output': extract.get('output_tokens',0)}
gods = god_nodes(G)
surprises = surprising_connections(G, communities)
labels = {cid: 'Community ' + str(cid) for cid in communities}
questions = suggest_questions(G, communities, labels)
report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, 'INPUT_PATH', suggested_questions=questions)
Path('graphify-out/GRAPH_REPORT.md').write_text(report)
to_json(G, communities, 'graphify-out/graph.json')
analysis = {
    'communities': {str(k): v for k, v in communities.items()},
    'cohesion': {str(k): v for k, v in cohesion.items()},
    'gods': gods, 'surprises': surprises, 'questions': questions,
}
Path('graphify-out/.graphify_analysis.json').write_text(json.dumps(analysis, indent=2))
print(f'Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities')
"
```

Replace `INPUT_PATH` with the actual path. If the command prints `ERROR: Graph is empty`, stop and tell the user.

---

### Step 5 — Label communities

Read `graphify-out/.graphify_analysis.json`. For each community key, look at its node labels and write a 2–5 word plain-language name (e.g. "Authentication Flow", "Payment Module").

Then regenerate the report and HTML:

```python
python -c "
import json
from graphify.build import build_from_json
from graphify.cluster import score_all
from graphify.analyze import suggest_questions
from graphify.report import generate
from graphify.export import to_html
from pathlib import Path
extract = json.loads(Path('graphify-out/.graphify_extract.json').read_text())
detection = json.loads(Path('graphify-out/.graphify_detect.json').read_text())
analysis = json.loads(Path('graphify-out/.graphify_analysis.json').read_text())
G = build_from_json(extract)
communities = {int(k): v for k, v in analysis['communities'].items()}
cohesion = {int(k): v for k, v in analysis['cohesion'].items()}
tokens = {'input': extract.get('input_tokens',0), 'output': extract.get('output_tokens',0)}
labels = LABELS_DICT
questions = suggest_questions(G, communities, labels)
from graphify.report import generate
from graphify.analyze import god_nodes, surprising_connections
report = generate(G, communities, cohesion, labels, analysis['gods'], analysis['surprises'], detection, tokens, 'INPUT_PATH', suggested_questions=questions)
Path('graphify-out/GRAPH_REPORT.md').write_text(report)
Path('graphify-out/.graphify_labels.json').write_text(json.dumps({str(k): v for k, v in labels.items()}))
to_html(G, communities, 'graphify-out/graph.html', community_labels=labels)
print('Done: GRAPH_REPORT.md + graph.html generated')
"
```

Replace `LABELS_DICT` with the actual dict you built (e.g. `{0: "Auth Flow", 1: "API Layer"}`).
Replace `INPUT_PATH` with the actual path.

Skip HTML if `--no-viz` was given.

---

### Final output

Print a concise summary:

```
Graph ready — graphify-out/
  GRAPH_REPORT.md   → god nodes, communities, surprising connections
  graph.html        → open in browser for interactive visualization
  graph.json        → queryable by agents

Top god nodes (most connected — core abstractions):
  1. <node> — N edges
  2. <node> — N edges
  3. <node> — N edges

Suggested questions:
  - <question from report>
  - <question from report>
```

---

## Notes for VS Code

- All Python commands above work in **PowerShell** (Windows), **bash** (macOS/Linux), and the **VS Code integrated terminal**.
- `graphify-out/` is written relative to wherever the terminal's working directory is. Make sure the terminal is at your project root before running `/graphify`.
- To rebuild after code changes: `python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`
- To query the graph from chat: `/graphify query "describe the auth flow"` or use `graphify query "..."` in the terminal.
