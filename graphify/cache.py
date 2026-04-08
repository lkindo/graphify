# per-file extraction cache - skip unchanged files on re-run
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def file_hash(path: Path) -> str:
    """SHA256 of file contents + resolved path. Prevents cache collisions on identical content."""
    p = Path(path)
    h = hashlib.sha256()
    h.update(p.read_bytes())
    h.update(b"\x00")
    h.update(str(p.resolve()).encode())
    return h.hexdigest()


def cache_dir(root: Path = Path("."), output_dir: Path | None = None) -> Path:
    """Returns the cache directory. Creates it if needed.

    If output_dir is given, uses output_dir/cache/.
    Otherwise falls back to root/graphify-out/cache/.
    """
    if output_dir is not None:
        d = Path(output_dir) / "cache"
    else:
        d = Path(root) / "graphify-out" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_cached(path: Path, root: Path = Path("."), output_dir: Path | None = None) -> dict | None:
    """Return cached extraction for this file if hash matches, else None.

    Cache key: SHA256 of file contents.
    Cache value: stored as {cache_dir}/{hash}.json where cache_dir depends on output_dir.
    If output_dir is given, cache is in output_dir/cache/. Otherwise in root/graphify-out/cache/.
    Returns None if no cache entry or file has changed.
    """
    try:
        h = file_hash(path)
    except OSError:
        return None
    entry = cache_dir(root, output_dir) / f"{h}.json"
    if not entry.exists():
        return None
    try:
        return json.loads(entry.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_cached(path: Path, result: dict, root: Path = Path("."), output_dir: Path | None = None) -> None:
    """Save extraction result for this file.

    Stores as {cache_dir}/{hash}.json where hash = SHA256 of current file contents.
    Cache location depends on output_dir: if given, uses output_dir/cache/; otherwise uses root/graphify-out/cache/.
    result should be a dict with 'nodes' and 'edges' lists.
    """
    h = file_hash(path)
    entry = cache_dir(root, output_dir) / f"{h}.json"
    tmp = entry.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(result))
        os.replace(tmp, entry)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def cached_files(root: Path = Path("."), output_dir: Path | None = None) -> set[str]:
    """Return set of file paths that have a valid cache entry (hash still matches)."""
    d = cache_dir(root, output_dir)
    return {p.stem for p in d.glob("*.json")}


def clear_cache(root: Path = Path("."), output_dir: Path | None = None) -> None:
    """Delete all cache files.

    Clears the cache directory (output_dir/cache/ if output_dir is given, otherwise root/graphify-out/cache/).
    """
    d = cache_dir(root, output_dir)
    for f in d.glob("*.json"):
        f.unlink()


def check_semantic_cache(
    files: list[str],
    root: Path = Path("."),
    output_dir: Path | None = None,
) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    """Check semantic extraction cache for a list of absolute file paths.

    Returns (cached_nodes, cached_edges, cached_hyperedges, uncached_files).
    Uncached files need Claude extraction; cached files are merged directly.
    """
    cached_nodes: list[dict] = []
    cached_edges: list[dict] = []
    cached_hyperedges: list[dict] = []
    uncached: list[str] = []

    for fpath in files:
        result = load_cached(Path(fpath), root, output_dir)
        if result is not None:
            cached_nodes.extend(result.get("nodes", []))
            cached_edges.extend(result.get("edges", []))
            cached_hyperedges.extend(result.get("hyperedges", []))
        else:
            uncached.append(fpath)

    return cached_nodes, cached_edges, cached_hyperedges, uncached


def save_semantic_cache(
    nodes: list[dict],
    edges: list[dict],
    hyperedges: list[dict] | None = None,
    root: Path = Path("."),
    output_dir: Path | None = None,
) -> int:
    """Save semantic extraction results to cache, keyed by source_file.

    Groups nodes and edges by source_file, then saves one cache entry per file.
    Returns the number of files cached.
    """
    from collections import defaultdict

    by_file: dict[str, dict] = defaultdict(lambda: {"nodes": [], "edges": [], "hyperedges": []})
    for n in nodes:
        src = n.get("source_file", "")
        if src:
            by_file[src]["nodes"].append(n)
    for e in edges:
        src = e.get("source_file", "")
        if src:
            by_file[src]["edges"].append(e)
    for h in (hyperedges or []):
        src = h.get("source_file", "")
        if src:
            by_file[src]["hyperedges"].append(h)

    saved = 0
    for fpath, result in by_file.items():
        p = Path(fpath)
        if not p.is_absolute():
            p = Path(root) / p
        if p.exists():
            save_cached(p, result, root, output_dir)
            saved += 1
    return saved
