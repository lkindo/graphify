# Objective-C Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add first-pass Objective-C support so graphify can discover and structurally extract `.m` and `.h` files in mixed iOS repositories.

**Architecture:** Extend the existing AST extraction pipeline instead of creating a separate parser path. Add Objective-C file discovery, introduce a `tree-sitter`-backed extractor in `graphify/extract.py`, and cover the change with fixtures and regression tests.

**Tech Stack:** Python, tree-sitter, pytest, setuptools

---

### Task 1: Add Objective-C file discovery

**Files:**
- Modify: `graphify/detect.py`
- Modify: `graphify/extract.py`
- Test: `tests/test_extract.py`

**Step 1: Write the failing test**

Add tests that assert:
- `.m` is treated as code by `classify_file()`
- `collect_files()` includes `.m`
- existing `.h` handling remains unchanged

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_extract.py -v`
Expected: FAIL because `.m` is not yet collected or classified.

**Step 3: Write minimal implementation**

Update:
- `CODE_EXTENSIONS` in `graphify/detect.py`
- `_EXTENSIONS` in `collect_files()` inside `graphify/extract.py`

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_extract.py -v`
Expected: PASS for the new discovery assertions.

**Step 5: Commit**

```bash
git add graphify/detect.py graphify/extract.py tests/test_extract.py
git commit -m "feat: detect objective-c source files"
```

### Task 2: Add Objective-C parser dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Write the failing check**

Document the expected Objective-C `tree-sitter` package choice and verify import shape manually during implementation.

**Step 2: Run dependency validation**

Run: `python -c "import importlib; import sys; print(sys.version)"`
Expected: confirm the local Python version and environment before adding the dependency.

**Step 3: Write minimal implementation**

Add the chosen Objective-C `tree-sitter` package to `dependencies` in `pyproject.toml`.

**Step 4: Run dependency install/validation**

Run: `pip install -e .`
Expected: install succeeds and the Objective-C grammar package is importable.

**Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: add objective-c tree-sitter dependency"
```

### Task 3: Implement Objective-C extractor skeleton

**Files:**
- Modify: `graphify/extract.py`
- Test: `tests/test_languages.py`
- Create: `tests/fixtures/sample.h`
- Create: `tests/fixtures/sample.m`

**Step 1: Write the failing test**

Add tests that assert the new extractor:
- does not return `"error"` for the sample files
- finds at least one class node
- finds at least one protocol node
- finds methods
- emits import relations
- routes `.m` through Objective-C extraction

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_languages.py -v`
Expected: FAIL because `extract_objc()` and Objective-C dispatch do not exist yet.

**Step 3: Write minimal implementation**

In `graphify/extract.py`:
- add `_OBJC_CONFIG`
- add any Objective-C-specific import handler needed
- add `extract_objc(path: Path) -> dict`
- add `.m` routing in `_DISPATCH`

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_languages.py -v`
Expected: PASS for the Objective-C extractor tests.

**Step 5: Commit**

```bash
git add graphify/extract.py tests/test_languages.py tests/fixtures/sample.h tests/fixtures/sample.m
git commit -m "feat: add objective-c structural extraction"
```

### Task 4: Add safe header routing for `.h`

**Files:**
- Modify: `graphify/extract.py`
- Test: `tests/test_extract.py`
- Test: `tests/test_languages.py`

**Step 1: Write the failing test**

Add tests that assert:
- an Objective-C header fixture is routed to the Objective-C extractor
- a plain C header fixture is still routed to the current C extractor

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_extract.py tests/test_languages.py -v`
Expected: FAIL because header routing is still global and `.h` is not yet distinguished by content.

**Step 3: Write minimal implementation**

Extend `graphify/extract.py` to:
- add a small content-aware Objective-C header detector
- route `.h` files to Objective-C only when they look like Objective-C headers
- preserve the existing C/C++ path for non-Objective-C headers

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_extract.py tests/test_languages.py -v`
Expected: PASS for header routing assertions.

**Step 5: Commit**

```bash
git add graphify/extract.py tests/test_extract.py tests/test_languages.py
git commit -m "feat: route objective-c headers safely"
```

### Task 5: Map inheritance and protocol relationships safely

**Files:**
- Modify: `graphify/extract.py`
- Test: `tests/test_languages.py`

**Step 1: Write the failing test**

Add tests that assert:
- a class inherits from its superclass
- a protocol inheritance or adoption signal is preserved in the graph using an existing relation type

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_languages.py -v`
Expected: FAIL because superclass or protocol relationships are incomplete.

**Step 3: Write minimal implementation**

Extend the Objective-C AST walk to:
- read superclass names
- read adopted protocol names where practical
- emit only existing relation types unless there is a clear need to expand the schema

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_languages.py -v`
Expected: PASS for inheritance and protocol assertions.

**Step 5: Commit**

```bash
git add graphify/extract.py tests/test_languages.py
git commit -m "feat: add objective-c inheritance relations"
```

### Task 6: Verify multi-language dispatch and regression safety

**Files:**
- Modify: `tests/test_extract.py`
- Modify: `tests/test_multilang.py`

**Step 1: Write the failing test**

Add coverage that:
- `extract()` dispatches `.m`
- Objective-C headers and C headers follow their expected extractor paths
- Objective-C support does not break existing Python/TS/Go/Rust dispatch assumptions

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_extract.py tests/test_multilang.py -v`
Expected: FAIL until dispatch coverage includes Objective-C routing logic.

**Step 3: Write minimal implementation**

Adjust any shared extraction code only if required to keep merged results stable.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_extract.py tests/test_multilang.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_extract.py tests/test_multilang.py
git commit -m "test: cover objective-c dispatch integration"
```

### Task 7: Run focused verification and update docs

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Add changelog entry**

Add a concise release note describing first-pass Objective-C support and its first-version limits.

**Step 2: Run focused verification**

Run: `pytest tests/test_extract.py tests/test_languages.py tests/test_multilang.py -v`
Expected: PASS.

**Step 3: Run broad verification**

Run: `pytest -q`
Expected: PASS, or any unrelated failures are identified explicitly.

**Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: note objective-c support"
```

## Notes For Implementation

- Treat `.mm` support as explicitly out of scope for this plan
- Prefer selector-style method labels over truncated names
- Avoid adding brand-new graph relation types in the first pass unless a concrete downstream need appears
- Keep Objective-C support structural and deterministic; do not introduce LLM-based fallback parsing
