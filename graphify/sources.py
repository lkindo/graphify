"""Source registry for graphify source add|delete|list|reload."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_SOURCES_FILE = Path("graphify-out/sources.json")


def _load_raw(sources_file: Path) -> dict:
    if sources_file.exists():
        try:
            return json.loads(sources_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"sources": []}


def load_sources(sources_file: Path = _SOURCES_FILE) -> list[dict]:
    """Return the list of registered source entries."""
    return _load_raw(sources_file)["sources"]


def save_sources(sources: list[dict], sources_file: Path = _SOURCES_FILE) -> None:
    """Write the sources list back to disk."""
    sources_file.parent.mkdir(parents=True, exist_ok=True)
    sources_file.write_text(json.dumps({"sources": sources}, indent=2), encoding="utf-8")


def add_source(path: str, sources_file: Path = _SOURCES_FILE) -> dict:
    """Register a source path.

    Resolves to an absolute path, stores the inode for rename tracking.
    Raises ValueError if the path does not exist or is already registered.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise ValueError(f"Path does not exist: {p}")
    inode = p.stat().st_ino
    sources = load_sources(sources_file)
    for s in sources:
        if s["path"] == str(p) or s.get("inode") == inode:
            raise ValueError(f"Source already registered: {s['path']}")
    entry = {
        "path": str(p),
        "inode": inode,
        "added": datetime.now(timezone.utc).isoformat(),
    }
    sources.append(entry)
    save_sources(sources, sources_file)
    return entry


def delete_source(path: str, sources_file: Path = _SOURCES_FILE) -> bool:
    """Remove a source by path or inode match.

    Returns True if a source was found and removed, False if not found.
    """
    p = Path(path).resolve()
    sources = load_sources(sources_file)
    target_inode = p.stat().st_ino if p.exists() else None
    new = [
        s for s in sources
        if s["path"] != str(p) and s.get("inode") != target_inode
    ]
    if len(new) == len(sources):
        return False
    save_sources(new, sources_file)
    return True


def resolve_source_path(entry: dict) -> Path | None:
    """Resolve a source entry to its current filesystem path.

    Handles renames: if the stored path no longer exists, searches the parent
    directory by inode to find the new name.
    Returns None if the source cannot be located.
    """
    p = Path(entry["path"])
    stored_inode = entry.get("inode")
    if p.exists():
        # Path still present — trust it regardless of inode (cross-fs moves)
        if not stored_inode or p.stat().st_ino == stored_inode:
            return p
        return p
    # Path gone — search parent by inode
    if stored_inode and p.parent.exists():
        for child in p.parent.iterdir():
            try:
                if child.stat().st_ino == stored_inode:
                    return child
            except OSError:
                pass
    return None


def list_sources(sources_file: Path = _SOURCES_FILE) -> list[dict]:
    """Return all sources with a status field: ok | renamed | missing."""
    result = []
    for s in load_sources(sources_file):
        entry = dict(s)
        current = resolve_source_path(s)
        if current is None:
            entry["status"] = "missing"
        elif str(current) != s["path"]:
            entry["status"] = "renamed"
            entry["current_path"] = str(current)
        else:
            entry["status"] = "ok"
        result.append(entry)
    return result
