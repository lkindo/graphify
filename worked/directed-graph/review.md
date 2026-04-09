## Evidence: Why `--directed` matters

**Corpus**: A Python codebase with 1,150 nodes and 3,403 edges.

### Problem: Undirected graphs show wrong edge direction 60% of the time

We built the same corpus with undirected (current default) and directed graphs, then compared every edge. Results:

| Relation | Total edges | Wrong direction | Wrong % |
|----------|------------|----------------|---------|
| `calls` | 184 | 135 | **73%** |
| `inherits` | 66 | 56 | **85%** |
| `uses` | 2,088 | 1,340 | **64%** |
| `rationale_for` | 510 | 509 | **100%** |
| `imports_from` | 21 | 11 | **52%** |
| `method` | 310 | 0 | 0% |
| `contains` | 224 | 0 | 0% |
| **Total** | **3,403** | **2,051** | **60%** |

`nx.Graph` stores edges in arbitrary order. When vis.js renders arrows (hardcoded `arrows: { to: { enabled: true } }`), 60% point the wrong way. The structural relations (`method`, `contains`) happened to survive because NetworkX stored them in insertion order, but the semantically important ones — `calls`, `inherits`, `uses` — are essentially coin flips.

### Root cause

The original `build.py` uses `nx.Graph()` with `_src`/`_tgt` attributes as a workaround. This preserves direction metadata on the edge dict, but the graph structure itself is undirected. Any consumer reading `graph.json` (LLM agents, vis.js, NetworkX traversal) sees undirected edges and must guess direction.

### A/B test

We ran a controlled A/B test asking "How are the corpus connected?" — scored against a 21-item ground truth checklist across 4 dimensions (root cause accuracy, missed dependencies, story granularity, token cost).

- **Graph-based (undirected)**: 21.7/40 — got flow direction wrong, missed 8 of 21 dependencies
- **Raw corpus reading**: 30.3/40 — correct direction but expensive (120K+ tokens)
- **Projected directed graph**: ~26/40 — fixes the direction errors that cost ~6 points

### What the change does

- Adds `--directed` flag — opt-in, default remains undirected for backward compatibility
- Clustering converts to undirected internally for Louvain/Leiden (they require undirected input)
- HTML visualization conditionally renders arrows only when the graph is directed
- All 382 existing tests pass unchanged
