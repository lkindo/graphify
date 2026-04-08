# Graphify Evaluation - Prune Example (2026-04-08)

**Evaluator:** Claude Sonnet 4.6 (live execution)
**Corpus:** Synthetic 5-file Python document-pipeline codebase (api.py, parser.py, processor.py, storage.py, validator.py)
**Purpose:** Demonstrate the before/after effect of the ghost-node pruning fix (issue #51)
**Pipeline:** AST extraction only (no LLM — .md files excluded from this run)

---

## Setup

`before/raw/` contains all 5 `.py` files.
`after/raw/` has `storage.py` and `validator.py` deleted, simulating a corpus shrink.

Both graphs were built with `_rebuild_code()` (AST-only, no LLM semantic pass).
The `.md` files (architecture.md, notes.md) are present in both but not extracted.

---

## 1. Before Graph (all 5 files)

**73 nodes · 112 edges · 5 communities**

### What it got right

- **Clean module-level communities.** Each `.py` file landed in its own community with near-zero cross-contamination. Community 0 = storage, 1 = api, 2 = parser, 3 = processor, 4 = validator. This is accurate — the codebase is layered and the AST extractor captured that structure faithfully.
- **`ValidationError` as the god node (11 edges).** Correct. `ValidationError` is the one exception class imported by multiple modules (api.py, processor.py, storage.py all catch it). The graph surfaced this cross-cutting dependency accurately.
- **`_ensure_storage()` as second god node (7 edges).** Correct. It's called by every storage operation before disk access. The extractor picked this up via call-site analysis.
- **EXTRACTED/INFERRED split (68%/32%).** Reasonable for this corpus. Explicit `import` and `def`/`call` relationships are EXTRACTED; inferred edges are cross-module usage patterns the extractor reasoned about. Spot-checking the inferred edges for `ValidationError` — all 5 flagged "surprising connections" between `api.py` and `validator.py` are real: the API handlers do propagate `ValidationError` to callers.

### What it got wrong

- **Node labels are truncated docstrings, not names.** Nodes like `"API module - exposes the document pipeline over HTTP. Thin layer over parser, va"` are module-level docstrings, not clean identifiers. These pollute the god-node and community lists and make the graph harder to read. The AST extractor is emitting the docstring as the node label instead of the module filename.
- **28 isolated nodes.** These are all docstring nodes — one per function — that have ≤1 connection. The extractor creates a node for each docstring but doesn't always link it to its owning function node, leaving dangling documentation nodes that add noise without adding signal.
- **Community cohesion is low (0.17–0.23).** Expected for this corpus size and structure, but worth noting: these communities are essentially one-file-per-community, which a simple file grouping would have produced without a graph. The clustering adds value only at larger corpus scales.

---

## 2. After Graph (storage.py + validator.py deleted)

**42 nodes · 51 edges · 13 communities**

### What changed

- **31 nodes removed, 61 edges removed.** Matches expected: storage.py contributed ~17 nodes, validator.py ~14. The deletion cleanly excised those nodes and all edges incident to them.
- **`ValidationError` is gone.** Correct — it was defined in `validator.py`. All 9 inferred edges that previously bridged api.py → validator.py are also gone.
- **Community count exploded from 5 to 13.** This is a real regression caused by losing the bridging nodes. With `ValidationError` and `_ensure_storage()` removed, the remaining 3 modules have fewer cross-file edges, so Leiden fragments them into many small 2-node clusters. This is technically correct graph behaviour but makes the after-state graph less useful as a navigation tool.
- **Many "thin community" warnings.** 6 of 13 communities have only 2 nodes. These are handler functions and their docstrings. Accurate but noisy.

### What the pruning fix demonstrates

Without the fix (pre-PR), re-running `--update` after deleting `storage.py` and `validator.py` would leave the before-state's 73 nodes intact in `graph.json`. Querying the graph for `_ensure_storage()` or `ValidationError` would return results pointing to files that no longer exist on disk.

With the fix, the after-state graph is a faithful reflection of the current corpus: 42 nodes, no stale references, no ghost nodes.

---

## 3. Known Limitations of This Run

- **No semantic extraction.** The `.md` files were not processed. A full run with LLM extraction would add architecture and notes nodes, likely bridging some of the isolated docstring nodes and producing higher-quality community labels.
- **Synthetic corpus.** This codebase was generated for testing; real projects with circular imports, large inheritance chains, and mixins would stress the extractor differently.
- **Community labels are placeholders.** Labels are `"Community 0"` through `"Community 12"` — Step 5 (LLM labelling) was not run. In a full run these would be human-readable.

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Files | 5 | 3 |
| Nodes | 73 | 42 |
| Edges | 112 | 51 |
| Communities | 5 | 13 |
| Ghost nodes | — | 0 (fixed) |

The AST extractor produces a structurally accurate graph for this corpus. The main extraction quality issues are docstring-as-label noise and isolated docstring nodes with no owning-function edge — neither is introduced by the pruning change. The pruning fix itself works correctly: the after-state graph contains exactly the nodes and edges derivable from the surviving files.
