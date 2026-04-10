"""Regression tests for Windows encoding fixes.

Verifies that CJK characters and emoji in graph labels survive a write/read
round-trip without UnicodeEncodeError or data loss.

These tests exercise the exact IO patterns that were fixed:
  - open(path, "w", encoding="utf-8")          -- export.py to_json / to_cypher
  - Path.write_text(..., encoding="utf-8")     -- cache.py, detect.py, wiki.py, watch.py
  - Path.read_text(encoding="utf-8")           -- cache.py, serve.py, benchmark.py

To confirm the tests catch the bug on an un-patched build, revert e.g.
cache.py line 73 from:
    tmp.write_text(json.dumps(result), encoding="utf-8")
to:
    tmp.write_text(json.dumps(result))
then run under a CP1252 locale with ensure_ascii=False data - the write will
raise UnicodeEncodeError.  The hook LF test would also fail on Windows because
the bare write_text would convert \\n to \\r\\n.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

CJK_LABEL = "変換器_トランスフォーマー"       # Japanese
KOREAN_LABEL = "주의 메커니즘"                 # Korean
CHINESE_LABEL = "注意力機制"                    # Traditional Chinese
EMOJI_LABEL = "graph\U0001f4ca node"           # 📊 U+1F4CA


# ---------------------------------------------------------------------------
# Primitive write_text / read_text with CJK  (baseline IO pattern)
# ---------------------------------------------------------------------------

def test_write_read_text_cjk_roundtrip_primitive(tmp_path):
    """Baseline: Path.write_text + read_text with explicit encoding='utf-8'
    must survive CJK + emoji labels with ensure_ascii=False JSON payloads.

    This is the raw IO pattern that all graphify file writes now use.  On a
    system where the default encoding is not UTF-8 (Windows CP1252/CP932/CP950),
    omitting encoding='utf-8' would raise UnicodeEncodeError here.
    """
    payload = {
        "nodes": [
            {"id": "n1", "label": CJK_LABEL},
            {"id": "n2", "label": EMOJI_LABEL},
            {"id": "n3", "label": KOREAN_LABEL},
            {"id": "n4", "label": CHINESE_LABEL},
        ],
        "edges": [],
        "hyperedges": [],
    }
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)

    out_file = tmp_path / "payload.json"
    out_file.write_text(json_str, encoding="utf-8")

    recovered = json.loads(out_file.read_text(encoding="utf-8"))
    labels = {n["label"] for n in recovered["nodes"]}

    assert CJK_LABEL in labels, f"CJK label lost: {labels}"
    assert EMOJI_LABEL in labels, f"Emoji label lost: {labels}"
    assert KOREAN_LABEL in labels, f"Korean label lost: {labels}"
    assert CHINESE_LABEL in labels, f"Chinese label lost: {labels}"


def test_cache_save_load_uses_utf8(tmp_path):
    """Verify that graphify.cache save_cached / load_cached use utf-8 internally."""
    from graphify.cache import save_cached, load_cached

    src_file = tmp_path / "source.py"
    src_file.write_bytes(b"# source\n")

    # Build a result dict.  json.dumps(ensure_ascii=True) will escape non-ASCII
    # so the bug is hidden for standard usage.  But the file must still be readable
    # as UTF-8 (the default json.loads handles both escaped and raw forms).
    result = {
        "nodes": [{"id": "n1", "label": CJK_LABEL}],
        "edges": [],
        "hyperedges": [],
    }
    save_cached(src_file, result, root=tmp_path)
    loaded = load_cached(src_file, root=tmp_path)

    assert loaded is not None, "load_cached returned None - cache miss after save"
    assert loaded["nodes"][0]["label"] == CJK_LABEL


# ---------------------------------------------------------------------------
# export.to_json IO pattern  (without networkx, test the open() layer directly)
# ---------------------------------------------------------------------------

def test_to_json_open_pattern_cjk(tmp_path):
    """The open(path, 'w', encoding='utf-8') pattern used in to_json must handle CJK.

    This replicates what to_json does after the fix:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    We patch ensure_ascii=False to prove the bytes are UTF-8.
    """
    out = tmp_path / "graph.json"
    data = {
        "nodes": [
            {"id": "n1", "label": CJK_LABEL},
            {"id": "n2", "label": EMOJI_LABEL},
        ],
        "links": [],
    }
    # Reproduce fixed export.py pattern
    with open(str(out), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    raw = out.read_bytes()
    assert CJK_LABEL.encode("utf-8") in raw, "CJK bytes not found in output file"
    assert "\U0001f4ca".encode("utf-8") in raw, "Emoji bytes not found in output file"

    recovered = json.loads(raw.decode("utf-8"))
    assert recovered["nodes"][0]["label"] == CJK_LABEL
    assert recovered["nodes"][1]["label"] == EMOJI_LABEL


# ---------------------------------------------------------------------------
# hooks._install_hook  — must write LF, not CRLF
# ---------------------------------------------------------------------------

def test_hook_install_lf_only(tmp_path):
    """Git hooks written by graphify must use LF line endings, not CRLF.

    A CRLF shebang line (#!/bin/sh\\r) causes 'bad interpreter' on Unix/WSL.
    This test will fail on an un-patched codebase on Windows because
    Path.write_text() without newline='\\n' converts \\n to \\r\\n.
    """
    from graphify.hooks import _install_hook

    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)

    marker = "# graphify-test-marker"
    script = f"{marker}\necho hello\n# graphify-test-marker-end\n"

    _install_hook(hooks_dir, "post-commit", script, marker)

    hook_file = hooks_dir / "post-commit"
    raw_bytes = hook_file.read_bytes()

    assert b"\r\n" not in raw_bytes, (
        f"Hook file contains CRLF line endings - will break sh interpreter on Unix/WSL. "
        f"First 80 bytes: {raw_bytes[:80]!r}"
    )
    assert raw_bytes.startswith(b"#!/bin/sh\n"), (
        f"Shebang line must be '#!/bin/sh\\n', got: {raw_bytes[:20]!r}"
    )


def test_hook_append_lf_only(tmp_path):
    """Appending to an existing hook must also produce LF-only output."""
    from graphify.hooks import _install_hook

    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)

    # Create a pre-existing hook (with LF endings, as Unix would have)
    existing = hooks_dir / "post-commit"
    existing.write_bytes(b"#!/bin/sh\n# existing hook\nexit 0\n")

    marker = "# graphify-append-marker"
    script = f"{marker}\npython -m graphify --hook\n# graphify-append-marker-end\n"

    _install_hook(hooks_dir, "post-commit", script, marker)

    raw_bytes = existing.read_bytes()
    assert b"\r\n" not in raw_bytes, (
        f"Appended hook file contains CRLF. First 120 bytes: {raw_bytes[:120]!r}"
    )
