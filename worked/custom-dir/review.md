# Review: custom-dir

**Corpus:** `worked/example/raw` — 5 Python modules + 2 markdown docs, ~2,159 words  
**Command:** `/graphify worked/example/raw --output-dir worked/custom-dir`  
**Result:** 73 nodes · 112 edges · 5 communities

---

## What the graph got right

**Module boundaries mapped cleanly.** The 5 communities correspond almost exactly to the 5 Python modules (storage, api, parser, processor, validator). The AST extraction correctly identified each module's public interface and the cohesion scores (0.17–0.23) accurately reflect that these are loosely coupled modules.

**`ValidationError` as the real hub.** The graph correctly identified `ValidationError` as the top god node with 11 edges. This is accurate — it's raised by validator, caught by processor and api, and flows through the whole pipeline. The graph found this without being told; the architecture doc doesn't call it out explicitly.

**Pipeline flow visible.** The edges from `parse_file()` → `validate_document()` → `enrich_document()` → storage functions trace the actual document lifecycle described in `architecture.md`. The EXTRACTED edges here are correct.

---

## What the graph got wrong

**Surprising connections aren't surprising — they're noise.** All 5 listed "surprising connections" are the same thing: api handlers → `ValidationError` (INFERRED). These aren't cross-community surprises; they're just the API catching errors from deeper layers. The graph flagged 5 variations of the same inferred edge as separate discoveries.

**28 isolated nodes is a real gap.** Most module-level docstrings became orphaned nodes because AST extraction didn't link them to the functions they describe. These aren't missing edges in the codebase — they're a limitation of how graphify handles module docstrings vs function nodes. The "Knowledge Gaps" warning is technically correct but misleading.

**Community labels are placeholder numbers.** Running without semantic extraction means communities are named "Community 0" through "Community 4". A follow-up `/graphify --cluster-only` with LLM labeling would fix this.

---

## Note on --output-dir

This corpus was run specifically to verify the `--output-dir` flag added in PR #61. The flag routes all outputs to a user-specified directory (`worked/custom-dir/`) instead of the hardcoded `graphify-out/`. Confirmed: `graphify-out/` was never created.
