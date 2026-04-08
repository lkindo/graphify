"""Shared extraction infrastructure: helpers, LanguageConfig, and ExtractionContext."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


def _make_id(*parts: str) -> str:
    """Build a stable node ID from one or more name parts."""
    combined = "_".join(p.strip("_.") for p in parts if p)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", combined)
    return cleaned.strip("_").lower()


def _read_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _resolve_name(node, source: bytes, config: LanguageConfig) -> str | None:
    """Get the name from a node using config.name_field, falling back to child types."""
    if config.resolve_function_name_fn is not None:
        return None  # caller handles this separately
    n = node.child_by_field_name(config.name_field)
    if n:
        return _read_text(n, source)
    for child in node.children:
        if child.type in config.name_fallback_child_types:
            return _read_text(child, source)
    return None


def _find_body(node, config: LanguageConfig):
    """Find the body node using config.body_field, falling back to child types."""
    b = node.child_by_field_name(config.body_field)
    if b:
        return b
    for child in node.children:
        if child.type in config.body_fallback_child_types:
            return child
    return None


@dataclass
class LanguageConfig:
    ts_module: str                                   # e.g. "tree_sitter_python"
    ts_language_fn: str = "language"                 # attr to call: e.g. tslang.language()

    class_types: frozenset = frozenset()
    function_types: frozenset = frozenset()
    import_types: frozenset = frozenset()
    call_types: frozenset = frozenset()

    # Name extraction
    name_field: str = "name"
    name_fallback_child_types: tuple = ()

    # Body detection
    body_field: str = "body"
    body_fallback_child_types: tuple = ()

    # Call name extraction
    call_function_field: str = "function"
    call_accessor_node_types: frozenset = frozenset()
    call_accessor_field: str = "attribute"

    # Stop recursion at these types in walk_calls
    function_boundary_types: frozenset = frozenset()

    # Import handler: called for import nodes instead of generic handling
    import_handler: Callable | None = None

    # Optional custom name resolver for functions (C, C++ declarator unwrapping)
    resolve_function_name_fn: Callable | None = None

    # Extra label formatting for functions: if True, functions get "name()" label
    function_label_parens: bool = True

    # Extra walk hook called after generic dispatch
    extra_walk_fn: Callable | None = None


class ExtractionContext:
    """Encapsulates the shared state and helpers used by all language extractors.

    Eliminates the duplicated add_node/add_edge/call-graph-pass/clean-edges
    pattern that was previously copy-pasted across 5 extractors.
    """

    def __init__(self, path: Path, source: bytes) -> None:
        self.path = path
        self.source = source
        self.stem = path.stem
        self.str_path = str(path)
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self.seen_ids: set[str] = set()
        self.function_bodies: list[tuple[str, Any]] = []

        self.file_nid = _make_id(self.stem)
        self.add_node(self.file_nid, path.name, 1)

    def add_node(self, nid: str, label: str, line: int) -> None:
        if nid not in self.seen_ids:
            self.seen_ids.add(nid)
            self.nodes.append({
                "id": nid,
                "label": label,
                "file_type": "code",
                "source_file": self.str_path,
                "source_location": f"L{line}",
            })

    def add_edge(self, src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", weight: float = 1.0) -> None:
        self.edges.append({
            "source": src,
            "target": tgt,
            "relation": relation,
            "confidence": confidence,
            "source_file": self.str_path,
            "source_location": f"L{line}",
            "weight": weight,
        })

    def run_call_graph_pass(self, walk_calls_fn: Callable) -> None:
        """Build label→nid map and run call-graph walker over all collected function bodies."""
        label_to_nid: dict[str, str] = {}
        for n in self.nodes:
            raw = n["label"]
            normalised = raw.strip("()").lstrip(".")
            label_to_nid[normalised.lower()] = n["id"]

        seen_call_pairs: set[tuple[str, str]] = set()

        for caller_nid, body_node in self.function_bodies:
            walk_calls_fn(body_node, caller_nid, label_to_nid, seen_call_pairs)

    def finalize(self) -> dict:
        """Clean edges (drop references to unknown nodes) and return the result dict."""
        valid_ids = self.seen_ids
        clean_edges = [
            edge for edge in self.edges
            if edge["source"] in valid_ids
            and (edge["target"] in valid_ids
                 or edge["relation"] in ("imports", "imports_from"))
        ]
        return {"nodes": self.nodes, "edges": clean_edges}


def init_parser(config: LanguageConfig):
    """Import tree-sitter module and create a parser. Returns (parser, language, source=None) or error dict."""
    import importlib
    try:
        mod = importlib.import_module(config.ts_module)
        from tree_sitter import Language, Parser
        lang_fn = getattr(mod, config.ts_language_fn, None)
        if lang_fn is None:
            lang_fn = getattr(mod, "language", None)
        if lang_fn is None:
            return None, None, f"No language function in {config.ts_module}"
        language = Language(lang_fn())
        parser = Parser(language)
        return parser, language, None
    except ImportError:
        return None, None, f"{config.ts_module} not installed"
    except Exception as e:
        return None, None, str(e)


def make_error_result(error: str) -> dict:
    return {"nodes": [], "edges": [], "error": error}
