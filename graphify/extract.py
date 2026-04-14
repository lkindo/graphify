"""Deterministic structural extraction from source code using tree-sitter. Outputs nodes+edges dicts."""
from __future__ import annotations
import importlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any
from .cache import load_cached, save_cached


def _make_id(*parts: str) -> str:
    """Build a stable node ID from one or more name parts."""
    combined = "_".join(p.strip("_.") for p in parts if p)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", combined)
    return cleaned.strip("_").lower()


# ── LanguageConfig dataclass ─────────────────────────────────────────────────

@dataclass
class LanguageConfig:
    ts_module: str                                   # e.g. "tree_sitter_python"
    ts_language_fn: str = "language"                 # attr to call: e.g. tslang.language()

    class_types: frozenset = frozenset()
    function_types: frozenset = frozenset()
    import_types: frozenset = frozenset()
    call_types: frozenset = frozenset()
    static_prop_types: frozenset = frozenset()
    helper_fn_names: frozenset = frozenset()
    container_bind_methods: frozenset = frozenset()
    event_listener_properties: frozenset = frozenset()

    # Name extraction
    name_field: str = "name"
    name_fallback_child_types: tuple = ()

    # Body detection
    body_field: str = "body"
    body_fallback_child_types: tuple = ()   # e.g. ("declaration_list", "compound_statement")

    # Call name extraction
    call_function_field: str = "function"           # field on call node for callee
    call_accessor_node_types: frozenset = frozenset()  # member/attribute nodes
    call_accessor_field: str = "attribute"          # field on accessor for method name

    # Stop recursion at these types in walk_calls
    function_boundary_types: frozenset = frozenset()

    # Import handler: called for import nodes instead of generic handling
    import_handler: Callable | None = None

    # Optional custom name resolver for functions (C, C++ declarator unwrapping)
    resolve_function_name_fn: Callable | None = None

    # Extra label formatting for functions: if True, functions get "name()" label
    function_label_parens: bool = True

    # Extra walk hook called after generic dispatch (for JS arrow functions, C# namespaces, etc.)
    extra_walk_fn: Callable | None = None


# ── Generic helpers ───────────────────────────────────────────────────────────

def _read_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _resolve_name(node, source: bytes, config: LanguageConfig) -> str | None:
    """Get the name from a node using config.name_field, falling back to child types."""
    if config.resolve_function_name_fn is not None:
        # For C/C++ where the name is inside a declarator
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


# ── Import handlers ───────────────────────────────────────────────────────────

def _import_python(node, source: bytes, file_nid: str, stem: str, edges: list, str_path: str) -> None:
    t = node.type
    if t == "import_statement":
        for child in node.children:
            if child.type in ("dotted_name", "aliased_import"):
                raw = _read_text(child, source)
                module_name = raw.split(" as ")[0].strip().lstrip(".")
                tgt_nid = _make_id(module_name)
                edges.append({
                    "source": file_nid,
                    "target": tgt_nid,
                    "relation": "imports",
                    "confidence": "EXTRACTED",
                    "source_file": str_path,
                    "source_location": f"L{node.start_point[0] + 1}",
                    "weight": 1.0,
                })
    elif t == "import_from_statement":
        module_node = node.child_by_field_name("module_name")
        if module_node:
            raw = _read_text(module_node, source)
            if raw.startswith("."):
                # Relative import - resolve to full path so IDs match file node IDs
                dots = len(raw) - len(raw.lstrip("."))
                module_name = raw.lstrip(".")
                base = Path(str_path).parent
                for _ in range(dots - 1):
                    base = base.parent
                rel = (module_name.replace(".", "/") + ".py") if module_name else "__init__.py"
                tgt_nid = _make_id(str(base / rel))
            else:
                tgt_nid = _make_id(raw)
            edges.append({
                "source": file_nid,
                "target": tgt_nid,
                "relation": "imports_from",
                "confidence": "EXTRACTED",
                "source_file": str_path,
                "source_location": f"L{node.start_point[0] + 1}",
                "weight": 1.0,
            })


def _import_js(node, source: bytes, file_nid: str, stem: str, edges: list, str_path: str) -> None:
    for child in node.children:
        if child.type == "string":
            raw = _read_text(child, source).strip("'\"` ")
            if not raw:
                break
            if raw.startswith("."):
                # Relative import - resolve to full path so IDs match file node IDs
                resolved = Path(str_path).parent / raw
                # TypeScript ESM: imports written as .js but actual file is .ts/.tsx
                if resolved.suffix == ".js":
                    resolved = resolved.with_suffix(".ts")
                elif resolved.suffix == ".jsx":
                    resolved = resolved.with_suffix(".tsx")
                tgt_nid = _make_id(str(resolved))
            else:
                # Bare/scoped import (node_modules) - use last segment; dropped as external
                module_name = raw.split("/")[-1]
                if not module_name:
                    break
                tgt_nid = _make_id(module_name)
            edges.append({
                "source": file_nid,
                "target": tgt_nid,
                "relation": "imports_from",
                "confidence": "EXTRACTED",
                "source_file": str_path,
                "source_location": f"L{node.start_point[0] + 1}",
                "weight": 1.0,
            })
            break


def _import_java(node, source: bytes, file_nid: str, stem: str, edges: list, str_path: str) -> None:
    def _walk_scoped(n) -> str:
        parts: list[str] = []
        cur = n
        while cur:
            if cur.type == "scoped_identifier":
                name_node = cur.child_by_field_name("name")
                if name_node:
                    parts.append(_read_text(name_node, source))
                cur = cur.child_by_field_name("scope")
            elif cur.type == "identifier":
                parts.append(_read_text(cur, source))
                break
            else:
                break
        parts.reverse()
        return ".".join(parts)

    for child in node.children:
        if child.type in ("scoped_identifier", "identifier"):
            path_str = _walk_scoped(child)
            module_name = path_str.split(".")[-1].strip("*").strip(".") or (
                path_str.split(".")[-2] if len(path_str.split(".")) > 1 else path_str
            )
            if module_name:
                tgt_nid = _make_id(module_name)
                edges.append({
                    "source": file_nid,
                    "target": tgt_nid,
                    "relation": "imports",
                    "confidence": "EXTRACTED",
                    "source_file": str_path,
                    "source_location": f"L{node.start_point[0] + 1}",
                    "weight": 1.0,
                })
            break


def _import_c(node, source: bytes, file_nid: str, stem: str, edges: list, str_path: str) -> None:
    for child in node.children:
        if child.type in ("string_literal", "system_lib_string", "string"):
            raw = _read_text(child, source).strip('"<> ')
            module_name = raw.split("/")[-1].split(".")[0]
            if module_name:
                tgt_nid = _make_id(module_name)
                edges.append({
                    "source": file_nid,
                    "target": tgt_nid,
                    "relation": "imports",
                    "confidence": "EXTRACTED",
                    "source_file": str_path,
                    "source_location": f"L{node.start_point[0] + 1}",
                    "weight": 1.0,
                })
            break


def _import_csharp(node, source: bytes, file_nid: str, stem: str, edges: list, str_path: str) -> None:
    for child in node.children:
        if child.type in ("qualified_name", "identifier", "name_equals"):
            raw = _read_text(child, source)
            module_name = raw.split(".")[-1].strip()
            if module_name:
                tgt_nid = _make_id(module_name)
                edges.append({
                    "source": file_nid,
                    "target": tgt_nid,
                    "relation": "imports",
                    "confidence": "EXTRACTED",
                    "source_file": str_path,
                    "source_location": f"L{node.start_point[0] + 1}",
                    "weight": 1.0,
                })
            break


def _import_kotlin(node, source: bytes, file_nid: str, stem: str, edges: list, str_path: str) -> None:
    path_node = node.child_by_field_name("path")
    if path_node:
        raw = _read_text(path_node, source)
        module_name = raw.split(".")[-1].strip()
        if module_name:
            tgt_nid = _make_id(module_name)
            edges.append({
                "source": file_nid,
                "target": tgt_nid,
                "relation": "imports",
                "confidence": "EXTRACTED",
                "source_file": str_path,
                "source_location": f"L{node.start_point[0] + 1}",
                "weight": 1.0,
            })
        return
    # Fallback: find identifier child
    for child in node.children:
        if child.type == "identifier":
            raw = _read_text(child, source)
            tgt_nid = _make_id(raw)
            edges.append({
                "source": file_nid,
                "target": tgt_nid,
                "relation": "imports",
                "confidence": "EXTRACTED",
                "source_file": str_path,
                "source_location": f"L{node.start_point[0] + 1}",
                "weight": 1.0,
            })
            break


def _import_scala(node, source: bytes, file_nid: str, stem: str, edges: list, str_path: str) -> None:
    for child in node.children:
        if child.type in ("stable_id", "identifier"):
            raw = _read_text(child, source)
            module_name = raw.split(".")[-1].strip("{} ")
            if module_name and module_name != "_":
                tgt_nid = _make_id(module_name)
                edges.append({
                    "source": file_nid,
                    "target": tgt_nid,
                    "relation": "imports",
                    "confidence": "EXTRACTED",
                    "source_file": str_path,
                    "source_location": f"L{node.start_point[0] + 1}",
                    "weight": 1.0,
                })
            break


def _import_php(node, source: bytes, file_nid: str, stem: str, edges: list, str_path: str) -> None:
    for child in node.children:
        if child.type in ("qualified_name", "name", "identifier"):
            raw = _read_text(child, source)
            module_name = raw.split("\\")[-1].strip()
            if module_name:
                tgt_nid = _make_id(module_name)
                edges.append({
                    "source": file_nid,
                    "target": tgt_nid,
                    "relation": "imports",
                    "confidence": "EXTRACTED",
                    "source_file": str_path,
                    "source_location": f"L{node.start_point[0] + 1}",
                    "weight": 1.0,
                })
            break


# ── C/C++ function name helpers ───────────────────────────────────────────────

def _get_c_func_name(node, source: bytes) -> str | None:
    """Recursively unwrap declarator to find the innermost identifier (C)."""
    if node.type == "identifier":
        return _read_text(node, source)
    decl = node.child_by_field_name("declarator")
    if decl:
        return _get_c_func_name(decl, source)
    for child in node.children:
        if child.type == "identifier":
            return _read_text(child, source)
    return None


def _get_cpp_func_name(node, source: bytes) -> str | None:
    """Recursively unwrap declarator to find the innermost identifier (C++)."""
    if node.type == "identifier":
        return _read_text(node, source)
    if node.type == "qualified_identifier":
        name_node = node.child_by_field_name("name")
        if name_node:
            return _read_text(name_node, source)
    decl = node.child_by_field_name("declarator")
    if decl:
        return _get_cpp_func_name(decl, source)
    for child in node.children:
        if child.type == "identifier":
            return _read_text(child, source)
    return None


# ── JS/TS extra walk for arrow functions ──────────────────────────────────────

def _js_extra_walk(node, source: bytes, file_nid: str, stem: str, str_path: str,
                   nodes: list, edges: list, seen_ids: set, function_bodies: list,
                   parent_class_nid: str | None, add_node_fn, add_edge_fn) -> bool:
    """Handle lexical_declaration (arrow functions) for JS/TS. Returns True if handled."""
    if node.type == "lexical_declaration":
        for child in node.children:
            if child.type == "variable_declarator":
                value = child.child_by_field_name("value")
                if value and value.type == "arrow_function":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        func_name = _read_text(name_node, source)
                        line = child.start_point[0] + 1
                        func_nid = _make_id(stem, func_name)
                        add_node_fn(func_nid, f"{func_name}()", line)
                        add_edge_fn(file_nid, func_nid, "contains", line)
                        body = value.child_by_field_name("body")
                        if body:
                            function_bodies.append((func_nid, body))
        return True
    return False


# ── C# extra walk for namespace declarations ──────────────────────────────────

def _csharp_extra_walk(node, source: bytes, file_nid: str, stem: str, str_path: str,
                       nodes: list, edges: list, seen_ids: set, function_bodies: list,
                       parent_class_nid: str | None, add_node_fn, add_edge_fn,
                       walk_fn) -> bool:
    """Handle namespace_declaration for C#. Returns True if handled."""
    if node.type == "namespace_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            ns_name = _read_text(name_node, source)
            ns_nid = _make_id(stem, ns_name)
            line = node.start_point[0] + 1
            add_node_fn(ns_nid, ns_name, line)
            add_edge_fn(file_nid, ns_nid, "contains", line)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                walk_fn(child, parent_class_nid)
        return True
    return False


# ── Swift extra walk for enum cases ──────────────────────────────────────────

def _swift_extra_walk(node, source: bytes, file_nid: str, stem: str, str_path: str,
                      nodes: list, edges: list, seen_ids: set, function_bodies: list,
                      parent_class_nid: str | None, add_node_fn, add_edge_fn) -> bool:
    """Handle enum_entry for Swift. Returns True if handled."""
    if node.type == "enum_entry" and parent_class_nid:
        for child in node.children:
            if child.type == "simple_identifier":
                case_name = _read_text(child, source)
                case_nid = _make_id(parent_class_nid, case_name)
                line = node.start_point[0] + 1
                add_node_fn(case_nid, case_name, line)
                add_edge_fn(parent_class_nid, case_nid, "case_of", line)
        return True
    return False


# ── Language configs ──────────────────────────────────────────────────────────

_PYTHON_CONFIG = LanguageConfig(
    ts_module="tree_sitter_python",
    class_types=frozenset({"class_definition"}),
    function_types=frozenset({"function_definition"}),
    import_types=frozenset({"import_statement", "import_from_statement"}),
    call_types=frozenset({"call"}),
    call_function_field="function",
    call_accessor_node_types=frozenset({"attribute"}),
    call_accessor_field="attribute",
    function_boundary_types=frozenset({"function_definition"}),
    import_handler=_import_python,
)

_JS_CONFIG = LanguageConfig(
    ts_module="tree_sitter_javascript",
    class_types=frozenset({"class_declaration"}),
    function_types=frozenset({"function_declaration", "method_definition"}),
    import_types=frozenset({"import_statement"}),
    call_types=frozenset({"call_expression"}),
    call_function_field="function",
    call_accessor_node_types=frozenset({"member_expression"}),
    call_accessor_field="property",
    function_boundary_types=frozenset({"function_declaration", "arrow_function", "method_definition"}),
    import_handler=_import_js,
)

_TS_CONFIG = LanguageConfig(
    ts_module="tree_sitter_typescript",
    ts_language_fn="language_typescript",
    class_types=frozenset({"class_declaration"}),
    function_types=frozenset({"function_declaration", "method_definition"}),
    import_types=frozenset({"import_statement"}),
    call_types=frozenset({"call_expression"}),
    call_function_field="function",
    call_accessor_node_types=frozenset({"member_expression"}),
    call_accessor_field="property",
    function_boundary_types=frozenset({"function_declaration", "arrow_function", "method_definition"}),
    import_handler=_import_js,
)

_JAVA_CONFIG = LanguageConfig(
    ts_module="tree_sitter_java",
    class_types=frozenset({"class_declaration", "interface_declaration"}),
    function_types=frozenset({"method_declaration", "constructor_declaration"}),
    import_types=frozenset({"import_declaration"}),
    call_types=frozenset({"method_invocation"}),
    call_function_field="name",
    call_accessor_node_types=frozenset(),
    function_boundary_types=frozenset({"method_declaration", "constructor_declaration"}),
    import_handler=_import_java,
)

_C_CONFIG = LanguageConfig(
    ts_module="tree_sitter_c",
    class_types=frozenset(),
    function_types=frozenset({"function_definition"}),
    import_types=frozenset({"preproc_include"}),
    call_types=frozenset({"call_expression"}),
    call_function_field="function",
    call_accessor_node_types=frozenset({"field_expression"}),
    call_accessor_field="field",
    function_boundary_types=frozenset({"function_definition"}),
    import_handler=_import_c,
    resolve_function_name_fn=_get_c_func_name,
)

_CPP_CONFIG = LanguageConfig(
    ts_module="tree_sitter_cpp",
    class_types=frozenset({"class_specifier"}),
    function_types=frozenset({"function_definition"}),
    import_types=frozenset({"preproc_include"}),
    call_types=frozenset({"call_expression"}),
    call_function_field="function",
    call_accessor_node_types=frozenset({"field_expression", "qualified_identifier"}),
    call_accessor_field="field",
    function_boundary_types=frozenset({"function_definition"}),
    import_handler=_import_c,
    resolve_function_name_fn=_get_cpp_func_name,
)

_RUBY_CONFIG = LanguageConfig(
    ts_module="tree_sitter_ruby",
    class_types=frozenset({"class"}),
    function_types=frozenset({"method", "singleton_method"}),
    import_types=frozenset(),
    call_types=frozenset({"call"}),
    call_function_field="method",
    call_accessor_node_types=frozenset(),
    name_fallback_child_types=("constant", "scope_resolution", "identifier"),
    body_fallback_child_types=("body_statement",),
    function_boundary_types=frozenset({"method", "singleton_method"}),
)

_CSHARP_CONFIG = LanguageConfig(
    ts_module="tree_sitter_c_sharp",
    class_types=frozenset({"class_declaration", "interface_declaration"}),
    function_types=frozenset({"method_declaration"}),
    import_types=frozenset({"using_directive"}),
    call_types=frozenset({"invocation_expression"}),
    call_function_field="function",
    call_accessor_node_types=frozenset({"member_access_expression"}),
    call_accessor_field="name",
    body_fallback_child_types=("declaration_list",),
    function_boundary_types=frozenset({"method_declaration"}),
    import_handler=_import_csharp,
)

_KOTLIN_CONFIG = LanguageConfig(
    ts_module="tree_sitter_kotlin",
    class_types=frozenset({"class_declaration", "object_declaration"}),
    function_types=frozenset({"function_declaration"}),
    import_types=frozenset({"import_header"}),
    call_types=frozenset({"call_expression"}),
    call_function_field="",
    call_accessor_node_types=frozenset({"navigation_expression"}),
    call_accessor_field="",
    name_fallback_child_types=("simple_identifier",),
    body_fallback_child_types=("function_body", "class_body"),
    function_boundary_types=frozenset({"function_declaration"}),
    import_handler=_import_kotlin,
)

_SCALA_CONFIG = LanguageConfig(
    ts_module="tree_sitter_scala",
    class_types=frozenset({"class_definition", "object_definition"}),
    function_types=frozenset({"function_definition"}),
    import_types=frozenset({"import_declaration"}),
    call_types=frozenset({"call_expression"}),
    call_function_field="",
    call_accessor_node_types=frozenset({"field_expression"}),
    call_accessor_field="field",
    name_fallback_child_types=("identifier",),
    body_fallback_child_types=("template_body",),
    function_boundary_types=frozenset({"function_definition"}),
    import_handler=_import_scala,
)

_PHP_CONFIG = LanguageConfig(
    ts_module="tree_sitter_php",
    ts_language_fn="language_php",
    class_types=frozenset({"class_declaration"}),
    function_types=frozenset({"function_definition", "method_declaration"}),
    import_types=frozenset({"namespace_use_clause"}),
    call_types=frozenset({"function_call_expression", "member_call_expression"}),
    static_prop_types=frozenset({"scoped_property_access_expression"}),
    helper_fn_names=frozenset({"config"}),
    container_bind_methods=frozenset({"bind", "singleton", "scoped", "instance"}),
    event_listener_properties=frozenset({"listen", "subscribe"}),
    call_function_field="function",
    call_accessor_node_types=frozenset({"member_call_expression"}),
    call_accessor_field="name",
    name_fallback_child_types=("name",),
    body_fallback_child_types=("declaration_list", "compound_statement"),
    function_boundary_types=frozenset({"function_definition", "method_declaration"}),
    import_handler=_import_php,
)


def _import_lua(node, source: bytes, file_nid: str, stem: str, edges: list, str_path: str) -> None:
    """Extract require('module') from Lua variable_declaration nodes."""
    text = _read_text(node, source)
    import re
    m = re.search(r"""require\s*[\('"]\s*['"]?([^'")\s]+)""", text)
    if m:
        module_name = m.group(1).split(".")[-1]
        if module_name:
            edges.append({
                "source": file_nid,
                "target": module_name,
                "relation": "imports",
                "confidence": "EXTRACTED",
                "confidence_score": 1.0,
                "source_file": str_path,
                "source_location": str(node.start_point[0] + 1),
                "weight": 1.0,
            })


_LUA_CONFIG = LanguageConfig(
    ts_module="tree_sitter_lua",
    ts_language_fn="language",
    class_types=frozenset(),
    function_types=frozenset({"function_declaration"}),
    import_types=frozenset({"variable_declaration"}),
    call_types=frozenset({"function_call"}),
    call_function_field="name",
    call_accessor_node_types=frozenset({"method_index_expression"}),
    call_accessor_field="name",
    name_fallback_child_types=("identifier", "method_index_expression"),
    body_fallback_child_types=("block",),
    function_boundary_types=frozenset({"function_declaration"}),
    import_handler=_import_lua,
)


def _import_swift(node, source: bytes, file_nid: str, stem: str, edges: list, str_path: str) -> None:
    for child in node.children:
        if child.type == "identifier":
            raw = _read_text(child, source)
            tgt_nid = _make_id(raw)
            edges.append({
                "source": file_nid,
                "target": tgt_nid,
                "relation": "imports",
                "confidence": "EXTRACTED",
                "source_file": str_path,
                "source_location": f"L{node.start_point[0] + 1}",
                "weight": 1.0,
            })
            break


_SWIFT_CONFIG = LanguageConfig(
    ts_module="tree_sitter_swift",
    class_types=frozenset({"class_declaration", "protocol_declaration"}),
    function_types=frozenset({"function_declaration", "init_declaration", "deinit_declaration", "subscript_declaration"}),
    import_types=frozenset({"import_declaration"}),
    call_types=frozenset({"call_expression"}),
    call_function_field="",
    call_accessor_node_types=frozenset({"navigation_expression"}),
    call_accessor_field="",
    name_fallback_child_types=("simple_identifier", "type_identifier", "user_type"),
    body_fallback_child_types=("class_body", "protocol_body", "function_body", "enum_class_body"),
    function_boundary_types=frozenset({"function_declaration", "init_declaration", "deinit_declaration", "subscript_declaration"}),
    import_handler=_import_swift,
)


# ── Generic extractor ─────────────────────────────────────────────────────────

def _extract_generic(path: Path, config: LanguageConfig, source_override: bytes | None = None) -> dict:
    """Generic AST extractor driven by LanguageConfig.

    Args:
        path: Real file path (used for metadata, node IDs, source_file fields).
        config: LanguageConfig driving the traversal.
        source_override: If provided, parse these bytes instead of reading path.
            Used by extract_ets() to inject pre-processed (struct→class) source
            while keeping metadata tied to the original .ets file.
    """
    try:
        mod = importlib.import_module(config.ts_module)
        from tree_sitter import Language, Parser
        lang_fn = getattr(mod, config.ts_language_fn, None)
        if lang_fn is None:
            # Fallback for PHP: try "language_php" then "language"
            lang_fn = getattr(mod, "language", None)
        if lang_fn is None:
            return {"nodes": [], "edges": [], "error": f"No language function in {config.ts_module}"}
        language = Language(lang_fn())
    except ImportError:
        return {"nodes": [], "edges": [], "error": f"{config.ts_module} not installed"}
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    try:
        parser = Parser(language)
        source = source_override if source_override is not None else path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    stem = path.stem
    str_path = str(path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()
    function_bodies: list[tuple[str, object]] = []
    pending_listen_edges: list[tuple[str, str, int]] = []

    def add_node(nid: str, label: str, line: int) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            nodes.append({
                "id": nid,
                "label": label,
                "file_type": "code",
                "source_file": str_path,
                "source_location": f"L{line}",
            })

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", weight: float = 1.0) -> None:
        edges.append({
            "source": src,
            "target": tgt,
            "relation": relation,
            "confidence": confidence,
            "source_file": str_path,
            "source_location": f"L{line}",
            "weight": weight,
        })

    file_nid = _make_id(str(path))
    add_node(file_nid, path.name, 1)

    def walk(node, parent_class_nid: str | None = None) -> None:
        t = node.type

        # Import types
        if t in config.import_types:
            if config.import_handler:
                config.import_handler(node, source, file_nid, stem, edges, str_path)
            return

        # Class types
        if t in config.class_types:
            # Resolve class name
            name_node = node.child_by_field_name(config.name_field)
            if name_node is None:
                for child in node.children:
                    if child.type in config.name_fallback_child_types:
                        name_node = child
                        break
            if not name_node:
                return
            class_name = _read_text(name_node, source)
            class_nid = _make_id(stem, class_name)
            line = node.start_point[0] + 1
            add_node(class_nid, class_name, line)
            add_edge(file_nid, class_nid, "contains", line)

            # Python-specific: inheritance
            if config.ts_module == "tree_sitter_python":
                args = node.child_by_field_name("superclasses")
                if args:
                    for arg in args.children:
                        if arg.type == "identifier":
                            base = _read_text(arg, source)
                            base_nid = _make_id(stem, base)
                            if base_nid not in seen_ids:
                                base_nid = _make_id(base)
                                if base_nid not in seen_ids:
                                    nodes.append({
                                        "id": base_nid,
                                        "label": base,
                                        "file_type": "code",
                                        "source_file": "",
                                        "source_location": "",
                                    })
                                    seen_ids.add(base_nid)
                            add_edge(class_nid, base_nid, "inherits", line)

            # Swift-specific: conformance / inheritance
            if config.ts_module == "tree_sitter_swift":
                for child in node.children:
                    if child.type == "inheritance_specifier":
                        for sub in child.children:
                            if sub.type in ("user_type", "type_identifier"):
                                base = _read_text(sub, source)
                                base_nid = _make_id(stem, base)
                                if base_nid not in seen_ids:
                                    base_nid = _make_id(base)
                                    if base_nid not in seen_ids:
                                        nodes.append({
                                            "id": base_nid,
                                            "label": base,
                                            "file_type": "code",
                                            "source_file": "",
                                            "source_location": "",
                                        })
                                        seen_ids.add(base_nid)
                                add_edge(class_nid, base_nid, "inherits", line)

            # C#-specific: inheritance / interface implementation via base_list
            if config.ts_module == "tree_sitter_c_sharp":
                for child in node.children:
                    if child.type == "base_list":
                        for sub in child.children:
                            if sub.type in ("identifier", "generic_name"):
                                if sub.type == "generic_name":
                                    name_child = sub.child_by_field_name("name")
                                    base = _read_text(name_child, source) if name_child else _read_text(sub.children[0], source)
                                else:
                                    base = _read_text(sub, source)
                                base_nid = _make_id(stem, base)
                                if base_nid not in seen_ids:
                                    base_nid = _make_id(base)
                                    if base_nid not in seen_ids:
                                        nodes.append({
                                            "id": base_nid,
                                            "label": base,
                                            "file_type": "code",
                                            "source_file": "",
                                            "source_location": "",
                                        })
                                        seen_ids.add(base_nid)
                                add_edge(class_nid, base_nid, "inherits", line)

            # Find body and recurse
            body = _find_body(node, config)
            if body:
                for child in body.children:
                    walk(child, parent_class_nid=class_nid)
            return

        # Event listener property arrays: $listen = [Event::class => [Listener::class]]
        if (t == "property_declaration"
                and parent_class_nid
                and config.event_listener_properties):
            for element in node.children:
                if element.type != "property_element":
                    continue
                prop_name: str | None = None
                array_node = None
                for c in element.children:
                    if c.type == "variable_name":
                        for sc in c.children:
                            if sc.type == "name":
                                prop_name = _read_text(sc, source)
                                break
                    elif c.type == "array_creation_expression":
                        array_node = c
                if (prop_name is None
                        or prop_name not in config.event_listener_properties
                        or array_node is None):
                    continue
                for entry in array_node.children:
                    if entry.type != "array_element_initializer":
                        continue
                    event_cls: str | None = None
                    listener_arr = None
                    for sub in entry.children:
                        if sub.type == "class_constant_access_expression" and event_cls is None:
                            for sc in sub.children:
                                if sc.is_named and sc.type in ("name", "qualified_name"):
                                    event_cls = _read_text(sc, source)
                                    break
                        elif sub.type == "array_creation_expression":
                            listener_arr = sub
                    if not event_cls or listener_arr is None:
                        continue
                    for listener_entry in listener_arr.children:
                        if listener_entry.type != "array_element_initializer":
                            continue
                        for item in listener_entry.children:
                            if item.type != "class_constant_access_expression":
                                continue
                            for sc in item.children:
                                if sc.is_named and sc.type in ("name", "qualified_name"):
                                    listener_cls = _read_text(sc, source)
                                    line_no = item.start_point[0] + 1
                                    pending_listen_edges.append((event_cls, listener_cls, line_no))
                                    break
                            break
            return

        # Function types
        if t in config.function_types:
            # Swift deinit/subscript have no name field — resolve before generic fallback
            if t == "deinit_declaration":
                func_name: str | None = "deinit"
            elif t == "subscript_declaration":
                func_name = "subscript"
            elif config.resolve_function_name_fn is not None:
                # C/C++ style: use declarator
                declarator = node.child_by_field_name("declarator")
                func_name = None
                if declarator:
                    func_name = config.resolve_function_name_fn(declarator, source)
            else:
                name_node = node.child_by_field_name(config.name_field)
                if name_node is None:
                    for child in node.children:
                        if child.type in config.name_fallback_child_types:
                            name_node = child
                            break
                func_name = _read_text(name_node, source) if name_node else None

            if not func_name:
                return

            line = node.start_point[0] + 1
            if parent_class_nid:
                func_nid = _make_id(parent_class_nid, func_name)
                add_node(func_nid, f".{func_name}()", line)
                add_edge(parent_class_nid, func_nid, "method", line)
            else:
                func_nid = _make_id(stem, func_name)
                add_node(func_nid, f"{func_name}()", line)
                add_edge(file_nid, func_nid, "contains", line)

            body = _find_body(node, config)
            if body:
                function_bodies.append((func_nid, body))
            return

        # JS/TS arrow functions and C# namespaces — language-specific extra handling
        if config.ts_module in ("tree_sitter_javascript", "tree_sitter_typescript"):
            if _js_extra_walk(node, source, file_nid, stem, str_path,
                              nodes, edges, seen_ids, function_bodies,
                              parent_class_nid, add_node, add_edge):
                return

        if config.ts_module == "tree_sitter_c_sharp":
            if _csharp_extra_walk(node, source, file_nid, stem, str_path,
                                   nodes, edges, seen_ids, function_bodies,
                                   parent_class_nid, add_node, add_edge, walk):
                return

        if config.ts_module == "tree_sitter_swift":
            if _swift_extra_walk(node, source, file_nid, stem, str_path,
                                  nodes, edges, seen_ids, function_bodies,
                                  parent_class_nid, add_node, add_edge):
                return

        # Default: recurse
        for child in node.children:
            walk(child, parent_class_nid=None)

    walk(root)

    # ── Call-graph pass ───────────────────────────────────────────────────────
    label_to_nid: dict[str, str] = {}
    for n in nodes:
        raw = n["label"]
        normalised = raw.strip("()").lstrip(".")
        label_to_nid[normalised.lower()] = n["id"]

    seen_call_pairs: set[tuple[str, str]] = set()
    seen_static_ref_pairs: set[tuple[str, str, str]] = set()
    seen_helper_ref_pairs: set[tuple[str, str, str]] = set()
    seen_bind_pairs: set[tuple[str, str, str]] = set()

    def _php_class_const_scope(n) -> str | None:
        scope = n.child_by_field_name("scope")
        if scope is None:
            for c in n.children:
                if c.is_named and c.type in ("name", "qualified_name", "identifier"):
                    scope = c
                    break
        if scope is None:
            return None
        return _read_text(scope, source)

    def walk_calls(node, caller_nid: str) -> None:
        if node.type in config.function_boundary_types:
            return

        if node.type in config.call_types:
            callee_name: str | None = None

            # Special handling per language
            if config.ts_module == "tree_sitter_swift":
                # Swift: first child may be simple_identifier or navigation_expression
                first = node.children[0] if node.children else None
                if first:
                    if first.type == "simple_identifier":
                        callee_name = _read_text(first, source)
                    elif first.type == "navigation_expression":
                        for child in first.children:
                            if child.type == "navigation_suffix":
                                for sc in child.children:
                                    if sc.type == "simple_identifier":
                                        callee_name = _read_text(sc, source)
            elif config.ts_module == "tree_sitter_kotlin":
                # Kotlin: first child may be simple_identifier or navigation_expression
                first = node.children[0] if node.children else None
                if first:
                    if first.type == "simple_identifier":
                        callee_name = _read_text(first, source)
                    elif first.type == "navigation_expression":
                        for child in reversed(first.children):
                            if child.type == "simple_identifier":
                                callee_name = _read_text(child, source)
                                break
            elif config.ts_module == "tree_sitter_scala":
                # Scala: first child
                first = node.children[0] if node.children else None
                if first:
                    if first.type == "identifier":
                        callee_name = _read_text(first, source)
                    elif first.type == "field_expression":
                        field = first.child_by_field_name("field")
                        if field:
                            callee_name = _read_text(field, source)
                        else:
                            for child in reversed(first.children):
                                if child.type == "identifier":
                                    callee_name = _read_text(child, source)
                                    break
            elif config.ts_module == "tree_sitter_c_sharp" and node.type == "invocation_expression":
                # C#: try name field, then first named child
                name_node = node.child_by_field_name("name")
                if name_node:
                    callee_name = _read_text(name_node, source)
                else:
                    for child in node.children:
                        if child.is_named:
                            raw = _read_text(child, source)
                            if "." in raw:
                                callee_name = raw.split(".")[-1]
                            else:
                                callee_name = raw
                            break
            elif config.ts_module == "tree_sitter_php":
                # PHP: distinguish function_call_expression vs member_call_expression
                if node.type == "function_call_expression":
                    func_node = node.child_by_field_name("function")
                    if func_node:
                        callee_name = _read_text(func_node, source)
                else:
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        callee_name = _read_text(name_node, source)
            elif config.ts_module == "tree_sitter_cpp":
                # C++: function field, then field_expression/qualified_identifier
                func_node = node.child_by_field_name(config.call_function_field) if config.call_function_field else None
                if func_node:
                    if func_node.type == "identifier":
                        callee_name = _read_text(func_node, source)
                    elif func_node.type in ("field_expression", "qualified_identifier"):
                        name = func_node.child_by_field_name("field") or func_node.child_by_field_name("name")
                        if name:
                            callee_name = _read_text(name, source)
            else:
                # Generic: get callee from call_function_field
                func_node = node.child_by_field_name(config.call_function_field) if config.call_function_field else None
                if func_node:
                    if func_node.type == "identifier":
                        callee_name = _read_text(func_node, source)
                    elif func_node.type in config.call_accessor_node_types:
                        if config.call_accessor_field:
                            attr = func_node.child_by_field_name(config.call_accessor_field)
                            if attr:
                                callee_name = _read_text(attr, source)
                    else:
                        # Try reading the node directly (e.g. Java name field is the callee)
                        callee_name = _read_text(func_node, source)

            if callee_name:
                tgt_nid = label_to_nid.get(callee_name.lower())
                if tgt_nid and tgt_nid != caller_nid:
                    pair = (caller_nid, tgt_nid)
                    if pair not in seen_call_pairs:
                        seen_call_pairs.add(pair)
                        line = node.start_point[0] + 1
                        edges.append({
                            "source": caller_nid,
                            "target": tgt_nid,
                            "relation": "calls",
                            "confidence": "EXTRACTED",
                            "source_file": str_path,
                            "source_location": f"L{line}",
                            "weight": 1.0,
                        })

            # Helper function calls: config('foo.bar') → uses_config edge to "foo"
            if (callee_name and callee_name in config.helper_fn_names):
                args_node = node.child_by_field_name("arguments")
                first_key: str | None = None
                if args_node:
                    for arg in args_node.children:
                        if arg.type != "argument":
                            continue
                        for inner in arg.children:
                            if inner.type == "string":
                                for sc in inner.children:
                                    if sc.type == "string_content":
                                        first_key = _read_text(sc, source)
                                        break
                                break
                        if first_key:
                            break
                if first_key:
                    segment = first_key.split(".")[0]
                    tgt_nid = (label_to_nid.get(segment.lower())
                               or label_to_nid.get(f"{segment}.php".lower()))
                    if tgt_nid and tgt_nid != caller_nid:
                        relation = f"uses_{callee_name}"
                        pair3 = (caller_nid, tgt_nid, relation)
                        if pair3 not in seen_helper_ref_pairs:
                            seen_helper_ref_pairs.add(pair3)
                            line = node.start_point[0] + 1
                            edges.append({
                                "source": caller_nid,
                                "target": tgt_nid,
                                "relation": relation,
                                "confidence": "EXTRACTED",
                                "confidence_score": 1.0,
                                "source_file": str_path,
                                "source_location": f"L{line}",
                                "weight": 1.0,
                            })

            # Service container bindings: $this->app->bind(Foo::class, Bar::class)
            if (node.type == "member_call_expression"
                    and callee_name
                    and callee_name in config.container_bind_methods):
                args_node = node.child_by_field_name("arguments")
                class_args: list[str] = []
                if args_node:
                    for arg in args_node.children:
                        if arg.type != "argument":
                            continue
                        for inner in arg.children:
                            if inner.type == "class_constant_access_expression":
                                cls = _php_class_const_scope(inner)
                                if cls:
                                    class_args.append(cls)
                                break
                        if len(class_args) >= 2:
                            break
                if len(class_args) == 2:
                    contract_name, impl_name = class_args
                    contract_nid = label_to_nid.get(contract_name.lower())
                    impl_nid = label_to_nid.get(impl_name.lower())
                    if contract_nid and impl_nid and contract_nid != impl_nid:
                        pair3 = (contract_nid, impl_nid, "bound_to")
                        if pair3 not in seen_bind_pairs:
                            seen_bind_pairs.add(pair3)
                            line = node.start_point[0] + 1
                            edges.append({
                                "source": contract_nid,
                                "target": impl_nid,
                                "relation": "bound_to",
                                "confidence": "EXTRACTED",
                                "confidence_score": 1.0,
                                "source_file": str_path,
                                "source_location": f"L{line}",
                                "weight": 1.0,
                            })

        # Static property access: Foo::$bar → uses_static_prop edge
        if node.type in config.static_prop_types:
            scope_node = node.child_by_field_name("scope")
            if scope_node is None:
                for child in node.children:
                    if child.is_named and child.type in ("name", "qualified_name", "identifier"):
                        scope_node = child
                        break
            if scope_node is not None:
                class_name = _read_text(scope_node, source)
                tgt_nid = label_to_nid.get(class_name.lower())
                if tgt_nid and tgt_nid != caller_nid:
                    pair3 = (caller_nid, tgt_nid, "uses_static_prop")
                    if pair3 not in seen_static_ref_pairs:
                        seen_static_ref_pairs.add(pair3)
                        line = node.start_point[0] + 1
                        edges.append({
                            "source": caller_nid,
                            "target": tgt_nid,
                            "relation": "uses_static_prop",
                            "confidence": "EXTRACTED",
                            "confidence_score": 1.0,
                            "source_file": str_path,
                            "source_location": f"L{line}",
                            "weight": 1.0,
                        })

        for child in node.children:
            walk_calls(child, caller_nid)

    for caller_nid, body_node in function_bodies:
        walk_calls(body_node, caller_nid)

    # ── Event listener pass ───────────────────────────────────────────────────
    seen_listen_pairs: set[tuple[str, str]] = set()
    for event_name, listener_name, line in pending_listen_edges:
        event_nid = label_to_nid.get(event_name.lower())
        listener_nid = label_to_nid.get(listener_name.lower())
        if not event_nid or not listener_nid or event_nid == listener_nid:
            continue
        pair2 = (event_nid, listener_nid)
        if pair2 in seen_listen_pairs:
            continue
        seen_listen_pairs.add(pair2)
        edges.append({
            "source": event_nid,
            "target": listener_nid,
            "relation": "listened_by",
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": str_path,
            "source_location": f"L{line}",
            "weight": 1.0,
        })

    # ── Clean edges ───────────────────────────────────────────────────────────
    valid_ids = seen_ids
    clean_edges = []
    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        if src in valid_ids and (tgt in valid_ids or edge["relation"] in ("imports", "imports_from")):
            clean_edges.append(edge)

    return {"nodes": nodes, "edges": clean_edges}


# ── Python rationale extraction ───────────────────────────────────────────────

_RATIONALE_PREFIXES = ("# NOTE:", "# IMPORTANT:", "# HACK:", "# WHY:", "# RATIONALE:", "# TODO:", "# FIXME:")


def _extract_python_rationale(path: Path, result: dict) -> None:
    """Post-pass: extract docstrings and rationale comments from Python source.
    Mutates result in-place by appending to result['nodes'] and result['edges'].
    """
    try:
        import tree_sitter_python as tspython
        from tree_sitter import Language, Parser
        language = Language(tspython.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception:
        return

    stem = path.stem
    str_path = str(path)
    nodes = result["nodes"]
    edges = result["edges"]
    seen_ids = {n["id"] for n in nodes}
    file_nid = _make_id(str(path))

    def _get_docstring(body_node) -> tuple[str, int] | None:
        if not body_node:
            return None
        for child in body_node.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type in ("string", "concatenated_string"):
                        text = source[sub.start_byte:sub.end_byte].decode("utf-8", errors="replace")
                        text = text.strip("\"'").strip('"""').strip("'''").strip()
                        if len(text) > 20:
                            return text, child.start_point[0] + 1
            break
        return None

    def _add_rationale(text: str, line: int, parent_nid: str) -> None:
        label = text[:80].replace("\r\n", " ").replace("\r", " ").replace("\n", " ").strip()
        rid = _make_id(stem, "rationale", str(line))
        if rid not in seen_ids:
            seen_ids.add(rid)
            nodes.append({
                "id": rid,
                "label": label,
                "file_type": "rationale",
                "source_file": str_path,
                "source_location": f"L{line}",
            })
        edges.append({
            "source": rid,
            "target": parent_nid,
            "relation": "rationale_for",
            "confidence": "EXTRACTED",
            "source_file": str_path,
            "source_location": f"L{line}",
            "weight": 1.0,
        })

    # Module-level docstring
    ds = _get_docstring(root)
    if ds:
        _add_rationale(ds[0], ds[1], file_nid)

    # Class and function docstrings
    def walk_docstrings(node, parent_nid: str) -> None:
        t = node.type
        if t == "class_definition":
            name_node = node.child_by_field_name("name")
            body = node.child_by_field_name("body")
            if name_node and body:
                class_name = source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
                nid = _make_id(stem, class_name)
                ds = _get_docstring(body)
                if ds:
                    _add_rationale(ds[0], ds[1], nid)
                for child in body.children:
                    walk_docstrings(child, nid)
            return
        if t == "function_definition":
            name_node = node.child_by_field_name("name")
            body = node.child_by_field_name("body")
            if name_node and body:
                func_name = source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
                nid = _make_id(parent_nid, func_name) if parent_nid != file_nid else _make_id(stem, func_name)
                ds = _get_docstring(body)
                if ds:
                    _add_rationale(ds[0], ds[1], nid)
            return
        for child in node.children:
            walk_docstrings(child, parent_nid)

    walk_docstrings(root, file_nid)

    # Rationale comments (# NOTE:, # IMPORTANT:, etc.)
    source_text = source.decode("utf-8", errors="replace")
    for lineno, line_text in enumerate(source_text.splitlines(), start=1):
        stripped = line_text.strip()
        if any(stripped.startswith(p) for p in _RATIONALE_PREFIXES):
            _add_rationale(stripped, lineno, file_nid)


# ── Public API ────────────────────────────────────────────────────────────────

def extract_python(path: Path) -> dict:
    """Extract classes, functions, and imports from a .py file via tree-sitter AST."""
    result = _extract_generic(path, _PYTHON_CONFIG)
    if "error" not in result:
        _extract_python_rationale(path, result)
    return result


def extract_js(path: Path) -> dict:
    """Extract classes, functions, arrow functions, and imports from a .js/.ts/.tsx file."""
    config = _TS_CONFIG if path.suffix in (".ts", ".tsx") else _JS_CONFIG
    return _extract_generic(path, config)


# ── ArkTS (.ets) support ─────────────────────────────────────────────────────
#
# ArkTS is HarmonyOS's UI language — a strict superset of TypeScript with two
# non-TS syntactic additions:
#   1. The `struct` keyword for UI components: `@Component struct Foo { ... }`
#   2. A rich decorator system with V1/V2 families covering state management,
#      composition, observation, persistence, and styling.
#
# Decorators are already valid TypeScript syntax (experimentalDecorators), so
# tree-sitter-typescript handles them fine. Only `struct` needs preprocessing:
# we substitute `struct` → `class ` (both 6 chars — keeps byte offsets stable,
# so line numbers in AST match the original .ets file).
#
# After AST extraction we post-process the original source text to emit:
#   • arkts_component nodes (@Component/@ComponentV2 struct) — distinct from
#     plain classes so the graph can reason about UI components specifically
#   • arkts_decorator nodes for component-level decorators (@Entry, @Preview, …)
#   • arkts_state nodes for every reactive field (@State/@Prop/@Link/@Local/…)
#   • arkts_lifecycle nodes for lifecycle methods (aboutToAppear/onPageShow/…)
#   • arkts_resource nodes for `$r("app.xxx.yyy")` references
#   • arkts_provide_key nodes connecting @Provide("k") ↔ @Consume("k") across
#     components (cross-component state flow)
#
# And edges:
#   • decorates:         decorator  → struct
#   • contains_state:    struct     → reactive field
#   • has_lifecycle:     struct     → lifecycle method
#   • watches:           @Watch     → target method (same struct)
#   • monitors:          @Monitor   → target expression literal
#   • observes:          @ObservedV2 class → @Trace field
#   • uses_component:    parent struct → child UI component (from build() body)
#   • references_resource: struct   → resource
#   • provides / consumes: struct   → arkts_provide_key node
#   • storage_binds:     @StorageLink/@StorageProp → AppStorage key
#   • local_storage_binds: @LocalStorageLink/@LocalStorageProp → LocalStorage key
#
# These give the knowledge graph real HarmonyOS semantics instead of plain TS.

_ARKTS_COMPONENT_DECORATORS = frozenset({
    "Component", "ComponentV2", "Entry", "Preview", "CustomDialog",
    "Reusable", "ReusableV2",
})

_ARKTS_STATE_DECORATORS = frozenset({
    # V1 reactive decorators
    "State", "Prop", "Link", "Provide", "Consume", "Observed", "ObjectLink",
    "StorageLink", "StorageProp", "LocalStorageLink", "LocalStorageProp",
    "Watch", "BuilderParam", "Require",
    # V2 reactive decorators
    "ObservedV2", "Local", "Param", "Event", "Once", "Trace", "Monitor", "Computed",
    "Provider", "Consumer",
})

_ARKTS_BUILDER_DECORATORS = frozenset({
    "Builder", "Styles", "Extend", "AnimatableExtend", "Concurrent",
})

# Subset of state decorators whose string argument names a provide/consume key.
# Includes both V1 (Provide/Consume) and V2 (Provider/Consumer).
_ARKTS_PROVIDE_DECORATORS = frozenset({"Provide", "Provider"})
_ARKTS_CONSUME_DECORATORS = frozenset({"Consume", "Consumer"})

# Subset that binds to AppStorage or LocalStorage by a string key
_ARKTS_STORAGE_DECORATORS = frozenset({"StorageLink", "StorageProp"})
_ARKTS_LOCAL_STORAGE_DECORATORS = frozenset({"LocalStorageLink", "LocalStorageProp"})

# Lifecycle methods in ArkTS Components (V1 and V2)
_ARKTS_LIFECYCLE_METHODS = frozenset({
    "aboutToAppear", "aboutToDisappear",
    "aboutToReuse", "aboutToRecycle", "aboutToReappear",
    "onPageShow", "onPageHide", "onBackPress",
    "onDidBuild", "pageTransition",
    # Ability lifecycle (UIAbility / EntryAbility)
    "onCreate", "onDestroy",
    "onWindowStageCreate", "onWindowStageDestroy",
    "onWindowFocusChanged", "onForeground", "onBackground",
})

# Match a decorator line: @Name, @Name(...), or @Name({ ...  (multi-line start)
# We capture the name; balancing parens/braces is handled in _enrich_arkts.
_ETS_DECORATOR_RE = re.compile(r"^\s*@(\w+)\b")
# Match a struct/class head that is the declaration being decorated
_ETS_STRUCT_HEAD_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:struct|class)\s+(\w+)")
# Match a decorated field: `@State foo: Type = ...` or `@Local foo =`.
# Also matches decorated getters: `@Computed get total(): T { ... }`.
_ETS_DECORATED_FIELD_RE = re.compile(
    r"^\s*@(\w+)\s*(?:\([^)]*\))?\s+"
    r"(?:private\s+|public\s+|protected\s+|readonly\s+|static\s+)*"
    r"(?:get\s+|set\s+)?"
    r"(\w+)\s*[:=?(]"  # allow `(` so decorated getters like @Computed get total() match
)

# Capitalized-identifier + "(" — used to find UI component usages inside build() bodies.
# This matches both built-in containers (Column, Row, NavDestination, ForEach, Text, Button,
# Image, List, Scroll, Stack, Flex, Grid, …) and user-defined components.
_ETS_UI_COMPONENT_CALL_RE = re.compile(r"\b([A-Z]\w+)\s*\(")
# Resource references: $r("app.string.xxx") / $r("app.color.xxx") / $r("app.media.xxx") etc.
_ETS_RESOURCE_REF_RE = re.compile(r"""\$r\s*\(\s*["']((?:app|sys)\.[\w.]+)["']\s*\)""")
# Raw file references: $rawfile("path")
_ETS_RAWFILE_REF_RE = re.compile(r"""\$rawfile\s*\(\s*["']([^"']+)["']\s*\)""")
# @Watch('methodName') / @Watch("methodName") — the string arg names a method in the same struct
_ETS_WATCH_ARG_RE = re.compile(r"""@Watch\s*\(\s*["'](\w+)["']\s*\)""")
# @Monitor('field' | 'field1','field2' | 'nested.path') — V2 multi-target observation
_ETS_MONITOR_ARG_RE = re.compile(r"""@Monitor\s*\(\s*((?:["'][^"']+["']\s*,?\s*)+)\)""")
# @Provide('key') / @Consume('key') / @Provider('key') / @Consumer('key')
_ETS_PROVIDE_CONSUME_ARG_RE = re.compile(
    r"""@(Provide|Consume|Provider|Consumer)\s*\(\s*["'](\w+)["']\s*\)"""
)
# @StorageLink('key') / @StorageProp('key') / @LocalStorageLink('key') / @LocalStorageProp('key')
_ETS_STORAGE_ARG_RE = re.compile(
    r"""@(Storage(?:Link|Prop)|LocalStorage(?:Link|Prop))\s*\(\s*["'](\w+)["']\s*\)"""
)
# @ObservedV2 class head on preceding line → @Trace fields inside — handled structurally
_ETS_CLASS_HEAD_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+(\w+)")
# Method definition inside a struct body: "methodName(" possibly with modifiers
_ETS_METHOD_DEF_RE = re.compile(
    r"^\s*(?:private\s+|public\s+|protected\s+|static\s+|async\s+|override\s+)*"
    r"(\w+)\s*\([^)]*\)\s*(?::\s*[\w<>|\[\]\s]+)?\s*\{?$"
)

# Names that look like UI components but are actually not (chained style methods, operators).
# Chained property calls like .fontSize(12) start with '.', so our `\b[A-Z]` regex already
# filters those. What remains are statements or type annotations. We skip a small blocklist
# of things that frequently appear capitalized-paren but aren't UI components.
_ETS_NOT_UI_COMPONENTS = frozenset({
    # Math / util constructors that show up in UI but aren't components
    "Date", "Array", "Map", "Set", "Promise", "JSON", "Math", "Number", "String",
    "Object", "Boolean", "RegExp", "Symbol", "Error", "URL", "URLSearchParams",
    "Uint8Array", "Int8Array", "Float32Array", "Float64Array",
    # Common DSL "marker" calls that take props/style but aren't composition targets
    # (kept minimal — we err on the side of recognizing too many rather than too few)
})


def _find_struct_ranges(lines: list[str]) -> list[dict]:
    """Find (struct_or_class, start_line, end_line, open_brace_line) for each
    top-level struct/class in the source.

    Uses naive brace counting; good enough for ArkTS where strings rarely span
    multiple lines and template literals are uncommon. Returns lines 1-indexed.
    """
    ranges: list[dict] = []
    stack: list[dict] = []  # Currently-open structs; we only keep 1 at a time (ArkTS disallows nested structs)
    depth = 0
    # crude string tracking to avoid counting braces inside strings
    for idx, line in enumerate(lines):
        lineno = idx + 1
        # Strip inline // comments (not inside strings — still crude)
        code = re.sub(r"//.*$", "", line)

        # Detect new struct/class head on this line, only when not already inside one
        m = _ETS_STRUCT_HEAD_RE.match(code)
        if m and (not stack):
            stack.append({
                "name": m.group(1),
                "kind": "struct" if re.match(r"^\s*(?:export\s+)?(?:default\s+)?struct", code) else "class",
                "head_line": lineno,
                "depth_at_entry": depth,
            })

        # Count braces on this line, honoring strings (simple rule: ignore chars in "..."/'...')
        in_single = False
        in_double = False
        in_template = False
        escape = False
        for ch in code:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if in_single:
                if ch == "'":
                    in_single = False
                continue
            if in_double:
                if ch == '"':
                    in_double = False
                continue
            if in_template:
                if ch == "`":
                    in_template = False
                continue
            if ch == "'":
                in_single = True; continue
            if ch == '"':
                in_double = True; continue
            if ch == "`":
                in_template = True; continue
            if ch == "{":
                depth += 1
                # First { after entering struct is the body-open brace
                if stack and stack[-1].get("open_line") is None and depth == stack[-1]["depth_at_entry"] + 1:
                    stack[-1]["open_line"] = lineno
            elif ch == "}":
                depth -= 1
                # Closing the struct body
                if stack and depth == stack[-1]["depth_at_entry"]:
                    entry = stack.pop()
                    ranges.append({
                        "name": entry["name"],
                        "kind": entry["kind"],
                        "head_line": entry["head_line"],
                        "open_line": entry.get("open_line", entry["head_line"]),
                        "close_line": lineno,
                    })
    return ranges


def _containing_struct(struct_ranges: list[dict], lineno: int) -> dict | None:
    """Return the innermost struct range whose body contains the given line."""
    for r in struct_ranges:
        if r["open_line"] <= lineno <= r["close_line"]:
            return r
    return None


def _enrich_arkts(source_text: str, path: Path, result: dict) -> None:
    """Post-process extraction result with ArkTS-specific semantic nodes/edges.

    Mutates ``result`` in place. Done in multiple passes over the original
    source text so that the AST-derived node IDs remain authoritative.
    """
    str_path = str(path)
    file_nid = _make_id(str(path))
    stem = path.stem
    nodes = result["nodes"]
    edges = result["edges"]
    seen = {n["id"] for n in nodes}
    # Index AST-derived class/struct nodes so enrichment can upgrade their node_type
    ast_struct_ids: set[str] = set()
    for n in nodes:
        # Class nodes have IDs like "stem_classname" from _extract_generic
        if "." not in (n.get("label") or "") and not n.get("node_type"):
            ast_struct_ids.add(n["id"])
    node_by_id = {n["id"]: n for n in nodes}

    def add_node(nid: str, label: str, line: int, node_type: str) -> None:
        if nid in seen:
            # Upgrade node_type if already present without type
            existing = node_by_id.get(nid)
            if existing and not existing.get("node_type"):
                existing["node_type"] = node_type
            return
        seen.add(nid)
        n = {
            "id": nid,
            "label": label,
            "file_type": "code",
            "node_type": node_type,
            "source_file": str_path,
            "source_location": f"L{line}",
        }
        nodes.append(n)
        node_by_id[nid] = n

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED") -> None:
        edges.append({
            "source": src,
            "target": tgt,
            "relation": relation,
            "confidence": confidence,
            "source_file": str_path,
            "source_location": f"L{line}",
            "weight": 1.0,
        })

    lines = source_text.splitlines()
    struct_ranges = _find_struct_ranges(lines)

    # ── Pass 1: walk lines, detect decorators + fields + methods ──────────────
    pending: list[tuple[str, int]] = []  # queued decorators waiting for their target
    paren_depth = 0                       # for multi-line decorator args

    # Track @Trace fields per class so we can link to an enclosing @ObservedV2 class
    observed_v2_class: str | None = None        # most recent @ObservedV2 class name
    observed_v2_line: int = 0                   # line of its declaration
    # Collect per-struct @Watch bindings: list of (struct_name, deco_line, target_method_name)
    pending_watches: list[tuple[str, int, str]] = []

    for idx, raw_line in enumerate(lines):
        lineno = idx + 1
        stripped = raw_line.rstrip()
        stripped_lead = stripped.lstrip()

        # Inside multi-line decorator args: update depth, don't parse
        if paren_depth > 0:
            paren_depth += raw_line.count("(") - raw_line.count(")")
            if paren_depth < 0:
                paren_depth = 0
            continue

        # Skip blanks and comments
        if not stripped_lead or stripped_lead.startswith("//") or stripped_lead.startswith("*") or stripped_lead.startswith("/*"):
            continue

        # Case 1: decorated-field on one line → "@State foo: T = ..."
        m_field = _ETS_DECORATED_FIELD_RE.match(stripped)
        if m_field:
            deco_name, field_name = m_field.group(1), m_field.group(2)
            containing = _containing_struct(struct_ranges, lineno)
            _emit_field_decorator(
                add_node, add_edge, stripped, file_nid, stem, path,
                deco_name, field_name, lineno, containing, observed_v2_class, observed_v2_line,
            )
            # @Watch('method') on a decorated field → queue the watch binding
            if deco_name == "Watch" and containing:
                for wm in _ETS_WATCH_ARG_RE.finditer(stripped):
                    pending_watches.append((containing["name"], lineno, wm.group(1)))
            continue

        # Case 2: standalone decorator line
        m_deco = _ETS_DECORATOR_RE.match(stripped)
        if m_deco:
            deco_name = m_deco.group(1)
            rest = stripped[m_deco.end():]
            paren_depth = rest.count("(") - rest.count(")")
            if paren_depth < 0:
                paren_depth = 0
            pending.append((deco_name, lineno))
            # Capture Watch/Monitor/Provide/Consume/Storage args for later binding
            if "(" in stripped:
                full_line = raw_line  # use original line for arg regex
                for m in _ETS_WATCH_ARG_RE.finditer(full_line):
                    pending_watches.append(("__pending__", lineno, m.group(1)))
            continue

        # Case 3: class/struct head — consume pending decorators
        m_cls = _ETS_CLASS_HEAD_RE.match(stripped)
        m_struct = _ETS_STRUCT_HEAD_RE.match(stripped)
        if (m_struct or m_cls) and pending:
            name = (m_struct or m_cls).group(1)
            target_nid = _make_id(stem, name)
            is_component = False
            for deco_name, deco_line in pending:
                if deco_name in _ARKTS_COMPONENT_DECORATORS:
                    is_component = True
                    deco_nid = _make_id(str_path, name, f"@{deco_name}")
                    add_node(deco_nid, f"@{deco_name}", deco_line, "arkts_decorator")
                    add_edge(deco_nid, target_nid, "decorates", deco_line)
                elif deco_name == "ObservedV2":
                    observed_v2_class = name
                    observed_v2_line = lineno
                    # Mark the class as observed
                    if target_nid in node_by_id:
                        node_by_id[target_nid]["node_type"] = "arkts_observed_v2"
                elif deco_name == "Observed":
                    if target_nid in node_by_id:
                        node_by_id[target_nid]["node_type"] = "arkts_observed"
            # Upgrade struct type → arkts_component
            if is_component and target_nid in node_by_id:
                node_by_id[target_nid]["node_type"] = "arkts_component"
            # Link pending Watch bindings to this struct's future methods
            for i, (tag, l, method_name) in enumerate(pending_watches):
                if tag == "__pending__":
                    pending_watches[i] = (name, l, method_name)
            pending.clear()
            continue

        # Case 4: field after pending decorator on previous line
        if pending:
            field_match = re.match(
                r"^\s*(?:private\s+|public\s+|protected\s+|readonly\s+)*(\w+)\s*[:=?]",
                stripped,
            )
            if field_match:
                field_name = field_match.group(1)
                containing = _containing_struct(struct_ranges, lineno)
                for deco_name, deco_line in pending:
                    _emit_field_decorator(
                        add_node, add_edge, stripped, file_nid, stem, path,
                        deco_name, field_name, deco_line, containing,
                        observed_v2_class, observed_v2_line,
                    )
                pending.clear()
                continue

        # Case 5: method definition — check if it's a lifecycle method
        m_method = _ETS_METHOD_DEF_RE.match(stripped)
        if m_method:
            method_name = m_method.group(1)
            if method_name in _ARKTS_LIFECYCLE_METHODS:
                containing = _containing_struct(struct_ranges, lineno)
                if containing:
                    struct_nid = _make_id(stem, containing["name"])
                    method_nid = _make_id(stem, containing["name"], method_name)
                    # Reuse AST-created method node if present; else create
                    if method_nid in node_by_id:
                        node_by_id[method_nid]["node_type"] = "arkts_lifecycle"
                    else:
                        add_node(method_nid, f".{method_name}()", lineno, "arkts_lifecycle")
                    add_edge(struct_nid, method_nid, "has_lifecycle", lineno)
            # Resolve pending @Watch bindings for methods in the current struct
            containing = _containing_struct(struct_ranges, lineno)
            if containing:
                for i, (bound_struct, deco_line, target_method) in enumerate(pending_watches):
                    if bound_struct == containing["name"] and target_method == method_name:
                        watch_nid = _make_id(stem, containing["name"], f"@Watch:{target_method}")
                        method_nid = _make_id(stem, containing["name"], method_name)
                        add_node(watch_nid, f"@Watch('{target_method}')", deco_line, "arkts_watch")
                        add_edge(watch_nid, method_nid, "watches", deco_line)
                        pending_watches[i] = ("", -1, "")

        # Any non-matching line clears pending
        pending.clear()

    # ── Pass 2: UI composition from build() bodies ────────────────────────────
    _enrich_ui_composition(lines, struct_ranges, stem, str_path, add_node, add_edge)

    # ── Pass 3: resource references anywhere in the file ──────────────────────
    _enrich_resources(source_text, struct_ranges, stem, str_path, add_node, add_edge)

    # ── Pass 4: Provide/Consume cross-component keys ─────────────────────────
    _enrich_provide_consume(source_text, struct_ranges, stem, str_path, add_node, add_edge)

    # ── Pass 5: Storage bindings ─────────────────────────────────────────────
    _enrich_storage_bindings(source_text, struct_ranges, stem, str_path, add_node, add_edge)

    # ── Pass 6: Monitor targets ──────────────────────────────────────────────
    _enrich_monitors(source_text, struct_ranges, stem, str_path, add_node, add_edge)


def _emit_field_decorator(add_node, add_edge, stripped, file_nid, stem, path,
                           deco_name, field_name, lineno, containing,
                           observed_v2_class, observed_v2_line):
    """Emit a reactive-state node + edges for a single @Decorator field."""
    if deco_name not in _ARKTS_STATE_DECORATORS:
        return
    str_path = str(path)
    state_nid = _make_id(str_path, f"@{deco_name}", field_name)
    add_node(state_nid, f"@{deco_name} {field_name}", lineno, "arkts_state")
    # Link to containing struct if we can find it; else to file
    if containing:
        struct_nid = _make_id(stem, containing["name"])
        add_edge(struct_nid, state_nid, "contains_state", lineno)
    else:
        add_edge(file_nid, state_nid, "contains_state", lineno)
    # @Trace field inside @ObservedV2 class → observes edge from class
    if deco_name == "Trace" and containing and containing.get("kind") == "class":
        class_nid = _make_id(stem, containing["name"])
        add_edge(class_nid, state_nid, "observes", lineno)


def _enrich_ui_composition(lines, struct_ranges, stem, str_path, add_node, add_edge) -> None:
    """For each struct, find build() body and emit uses_component edges."""
    for sr in struct_ranges:
        # Scan struct body for a `build(` method followed by `{`
        body_text = "\n".join(lines[sr["open_line"]: sr["close_line"]])
        build_match = re.search(r"\bbuild\s*\(\s*\)\s*\{", body_text)
        if not build_match:
            continue
        # Find build() body by brace counting, starting from the line containing the match
        # Compute starting line in original file
        prefix = body_text[: build_match.start()]
        build_open_offset = build_match.end()  # position right after the '{'
        build_start_lineno_in_body = prefix.count("\n")
        build_start_line = sr["open_line"] + build_start_lineno_in_body + 1  # 1-indexed

        depth = 1  # we already entered `{`
        body_lines: list[tuple[int, str]] = []
        # Scan from build_open_offset in body_text until matching close
        i = build_open_offset
        current_line = build_start_line
        line_buffer = ""
        end_line = sr["close_line"]
        while i < len(body_text) and depth > 0:
            ch = body_text[i]
            if ch == "\n":
                body_lines.append((current_line, line_buffer))
                current_line += 1
                line_buffer = ""
            else:
                line_buffer += ch
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_line = current_line
                    break
            i += 1

        # Collect UI component calls
        seen_in_build: set[str] = set()
        parent_nid = _make_id(stem, sr["name"])
        for lno, bl in body_lines:
            # Strip inline // comments
            code_only = re.sub(r"//.*$", "", bl)
            # Strip chained property calls: anything starting with "." is a style call
            # But our regex uses \b which won't match after "."
            for m in _ETS_UI_COMPONENT_CALL_RE.finditer(code_only):
                comp_name = m.group(1)
                if comp_name in _ETS_NOT_UI_COMPONENTS:
                    continue
                # Dedup per-struct to avoid noise from every ForEach iteration
                if comp_name in seen_in_build:
                    continue
                seen_in_build.add(comp_name)
                comp_nid = _make_id(stem, sr["name"], "uses", comp_name)
                add_node(comp_nid, comp_name, lno, "arkts_ui_component_usage")
                add_edge(parent_nid, comp_nid, "uses_component", lno)


def _enrich_resources(source_text, struct_ranges, stem, str_path, add_node, add_edge) -> None:
    """Find $r('app.xxx.yyy') / $rawfile('...') refs, create arkts_resource nodes."""
    emitted_edges: set[tuple[str, str, int]] = set()
    for m in _ETS_RESOURCE_REF_RE.finditer(source_text):
        resource_key = m.group(1)       # e.g. "app.color.color_16DB99"
        lineno = source_text.count("\n", 0, m.start()) + 1
        resource_nid = _make_id("resource", resource_key)
        add_node(resource_nid, f"$r({resource_key})", lineno, "arkts_resource")
        containing = _containing_struct(struct_ranges, lineno)
        if containing:
            struct_nid = _make_id(stem, containing["name"])
            key = (struct_nid, resource_nid, 0)  # dedup per struct, any line
            if key in emitted_edges:
                continue
            emitted_edges.add(key)
            add_edge(struct_nid, resource_nid, "references_resource", lineno)
    for m in _ETS_RAWFILE_REF_RE.finditer(source_text):
        resource_key = m.group(1)
        lineno = source_text.count("\n", 0, m.start()) + 1
        resource_nid = _make_id("rawfile", resource_key)
        add_node(resource_nid, f"$rawfile({resource_key})", lineno, "arkts_resource")
        containing = _containing_struct(struct_ranges, lineno)
        if containing:
            struct_nid = _make_id(stem, containing["name"])
            key = (struct_nid, resource_nid, 0)
            if key in emitted_edges:
                continue
            emitted_edges.add(key)
            add_edge(struct_nid, resource_nid, "references_resource", lineno)


def _enrich_provide_consume(source_text, struct_ranges, stem, str_path, add_node, add_edge) -> None:
    """Emit synthetic key nodes for @Provide/@Consume/@Provider/@Consumer cross-component flow."""
    for m in _ETS_PROVIDE_CONSUME_ARG_RE.finditer(source_text):
        deco_name, key = m.group(1), m.group(2)
        start = m.start()
        lineno = source_text.count("\n", 0, start) + 1
        containing = _containing_struct(struct_ranges, lineno)
        if not containing:
            continue
        struct_nid = _make_id(stem, containing["name"])
        key_nid = _make_id("provide_key", key)
        add_node(key_nid, f"Provide<{key}>", lineno, "arkts_provide_key")
        if deco_name in _ARKTS_PROVIDE_DECORATORS:
            add_edge(struct_nid, key_nid, "provides", lineno)
        else:
            add_edge(struct_nid, key_nid, "consumes", lineno)


def _enrich_storage_bindings(source_text, struct_ranges, stem, str_path, add_node, add_edge) -> None:
    """Emit synthetic storage key nodes for @StorageLink / @LocalStorageLink bindings."""
    for m in _ETS_STORAGE_ARG_RE.finditer(source_text):
        deco_name, key = m.group(1), m.group(2)
        start = m.start()
        lineno = source_text.count("\n", 0, start) + 1
        containing = _containing_struct(struct_ranges, lineno)
        if not containing:
            continue
        struct_nid = _make_id(stem, containing["name"])
        if deco_name.startswith("LocalStorage"):
            key_nid = _make_id("local_storage_key", key)
            add_node(key_nid, f"LocalStorage<{key}>", lineno, "arkts_local_storage_key")
            add_edge(struct_nid, key_nid, "local_storage_binds", lineno)
        else:
            key_nid = _make_id("app_storage_key", key)
            add_node(key_nid, f"AppStorage<{key}>", lineno, "arkts_app_storage_key")
            add_edge(struct_nid, key_nid, "storage_binds", lineno)


def _enrich_monitors(source_text, struct_ranges, stem, str_path, add_node, add_edge) -> None:
    """@Monitor('path1', 'path2', ...) — attach monitor targets as monitors edges."""
    for m in _ETS_MONITOR_ARG_RE.finditer(source_text):
        args_blob = m.group(1)
        # Extract individual string literals
        targets = re.findall(r"""["']([^"']+)["']""", args_blob)
        start = m.start()
        lineno = source_text.count("\n", 0, start) + 1
        containing = _containing_struct(struct_ranges, lineno)
        if not containing:
            continue
        struct_nid = _make_id(stem, containing["name"])
        for target_expr in targets:
            monitor_nid = _make_id(stem, containing["name"], "monitor", target_expr)
            add_node(monitor_nid, f"@Monitor('{target_expr}')", lineno, "arkts_monitor_target")
            add_edge(struct_nid, monitor_nid, "monitors", lineno)


# Preprocess "struct X" → "class  X" preserving byte offsets (both 6 chars + space).
# This lets tree-sitter-typescript parse ArkTS component declarations as classes
# without breaking line/column info in the AST.
_ETS_STRUCT_PATTERN = re.compile(rb"\bstruct\b")


def extract_ets(path: Path) -> dict:
    """Extract from an ArkTS (.ets) file.

    ArkTS = TypeScript + `struct` keyword + HarmonyOS-specific decorators.
    We preprocess struct → class (same byte length, line numbers preserved)
    then run the standard TypeScript extractor, then enrich the result with
    ArkTS decorator semantics.
    """
    try:
        raw = path.read_bytes()
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    # struct (6 bytes) → class  (6 bytes: c-l-a-s-s-space), preserves offsets
    preprocessed = _ETS_STRUCT_PATTERN.sub(b"class ", raw)
    result = _extract_generic(path, _TS_CONFIG, source_override=preprocessed)
    if "error" in result and not result.get("nodes"):
        return result

    try:
        source_text = raw.decode("utf-8", errors="replace")
        _enrich_arkts(source_text, path, result)
    except Exception:
        # Enrichment failure shouldn't kill the base extraction
        pass

    return result


def extract_java(path: Path) -> dict:
    """Extract classes, interfaces, methods, constructors, and imports from a .java file."""
    return _extract_generic(path, _JAVA_CONFIG)


def extract_c(path: Path) -> dict:
    """Extract functions and includes from a .c/.h file."""
    return _extract_generic(path, _C_CONFIG)


def extract_cpp(path: Path) -> dict:
    """Extract functions, classes, and includes from a .cpp/.cc/.cxx/.hpp file."""
    return _extract_generic(path, _CPP_CONFIG)


def extract_ruby(path: Path) -> dict:
    """Extract classes, methods, singleton methods, and calls from a .rb file."""
    return _extract_generic(path, _RUBY_CONFIG)


def extract_csharp(path: Path) -> dict:
    """Extract classes, interfaces, methods, namespaces, and usings from a .cs file."""
    return _extract_generic(path, _CSHARP_CONFIG)


def extract_kotlin(path: Path) -> dict:
    """Extract classes, objects, functions, and imports from a .kt/.kts file."""
    return _extract_generic(path, _KOTLIN_CONFIG)


def extract_scala(path: Path) -> dict:
    """Extract classes, objects, functions, and imports from a .scala file."""
    return _extract_generic(path, _SCALA_CONFIG)


def extract_php(path: Path) -> dict:
    """Extract classes, functions, methods, namespace uses, and calls from a .php file."""
    return _extract_generic(path, _PHP_CONFIG)


def extract_blade(path: Path) -> dict:
    """Extract @include, <livewire:> components, and wire:click bindings from Blade templates."""
    import re
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"error": f"cannot read {path}"}

    file_nid = _make_id(str(path))
    nodes = [{"id": file_nid, "label": path.name, "file_type": "code",
              "source_file": str(path), "source_location": None}]
    edges = []

    # @include('path.to.partial') or @include("path.to.partial")
    for m in re.finditer(r"@include\(['\"]([^'\"]+)['\"]", src):
        tgt = m.group(1).replace(".", "/")
        tgt_nid = _make_id(tgt)
        if tgt_nid not in {n["id"] for n in nodes}:
            nodes.append({"id": tgt_nid, "label": m.group(1), "file_type": "code",
                          "source_file": str(path), "source_location": None})
        edges.append({"source": file_nid, "target": tgt_nid, "relation": "includes",
                      "confidence": "EXTRACTED", "confidence_score": 1.0,
                      "source_file": str(path), "source_location": None, "weight": 1.0})

    # <livewire:component.name /> or <livewire:component.name>
    for m in re.finditer(r"<livewire:([\w.\-]+)", src):
        tgt_nid = _make_id(m.group(1))
        if tgt_nid not in {n["id"] for n in nodes}:
            nodes.append({"id": tgt_nid, "label": m.group(1), "file_type": "code",
                          "source_file": str(path), "source_location": None})
        edges.append({"source": file_nid, "target": tgt_nid, "relation": "uses_component",
                      "confidence": "EXTRACTED", "confidence_score": 1.0,
                      "source_file": str(path), "source_location": None, "weight": 1.0})

    # wire:click="methodName"
    for m in re.finditer(r'wire:click=["\']([^"\']+)["\']', src):
        tgt_nid = _make_id(m.group(1))
        if tgt_nid not in {n["id"] for n in nodes}:
            nodes.append({"id": tgt_nid, "label": m.group(1), "file_type": "code",
                          "source_file": str(path), "source_location": None})
        edges.append({"source": file_nid, "target": tgt_nid, "relation": "binds_method",
                      "confidence": "EXTRACTED", "confidence_score": 1.0,
                      "source_file": str(path), "source_location": None, "weight": 1.0})

    return {"nodes": nodes, "edges": edges}


def extract_dart(path: Path) -> dict:
    """Extract classes, mixins, functions, imports, and calls from a .dart file using regex."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"error": f"cannot read {path}"}

    file_nid = _make_id(str(path))
    nodes = [{"id": file_nid, "label": path.name, "file_type": "code",
              "source_file": str(path), "source_location": None}]
    edges = []
    defined: set[str] = set()

    # Classes and mixins
    for m in re.finditer(r"^\s*(?:abstract\s+)?(?:class|mixin)\s+(\w+)", src, re.MULTILINE):
        nid = _make_id(str(path), m.group(1))
        if nid not in defined:
            nodes.append({"id": nid, "label": m.group(1), "file_type": "code",
                          "source_file": str(path), "source_location": None})
            edges.append({"source": file_nid, "target": nid, "relation": "defines",
                          "confidence": "EXTRACTED", "confidence_score": 1.0,
                          "source_file": str(path), "source_location": None, "weight": 1.0})
            defined.add(nid)

    # Top-level and member functions/methods
    for m in re.finditer(r"^\s*(?:static\s+|async\s+)?(?:\w+\s+)+(\w+)\s*\(", src, re.MULTILINE):
        name = m.group(1)
        if name in {"if", "for", "while", "switch", "catch", "return"}:
            continue
        nid = _make_id(str(path), name)
        if nid not in defined:
            nodes.append({"id": nid, "label": name, "file_type": "code",
                          "source_file": str(path), "source_location": None})
            edges.append({"source": file_nid, "target": nid, "relation": "defines",
                          "confidence": "EXTRACTED", "confidence_score": 1.0,
                          "source_file": str(path), "source_location": None, "weight": 1.0})
            defined.add(nid)

    # import 'package:...' or import '...'
    for m in re.finditer(r"""^import\s+['"]([^'"]+)['"]""", src, re.MULTILINE):
        pkg = m.group(1)
        tgt_nid = _make_id(pkg)
        if tgt_nid not in defined:
            nodes.append({"id": tgt_nid, "label": pkg, "file_type": "code",
                          "source_file": str(path), "source_location": None})
            defined.add(tgt_nid)
        edges.append({"source": file_nid, "target": tgt_nid, "relation": "imports",
                      "confidence": "EXTRACTED", "confidence_score": 1.0,
                      "source_file": str(path), "source_location": None, "weight": 1.0})

    return {"nodes": nodes, "edges": edges}


def extract_verilog(path: Path) -> dict:
    """Extract modules, functions, tasks, package imports, and instantiations from .v/.sv files."""
    try:
        import tree_sitter_verilog as tsverilog
        from tree_sitter import Language, Parser
    except ImportError:
        return {"nodes": [], "edges": [], "error": "tree_sitter_verilog not installed"}

    try:
        language = Language(tsverilog.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    stem = path.stem
    str_path = str(path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()

    def add_node(nid: str, label: str, line: int) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            nodes.append({"id": nid, "label": label, "file_type": "code",
                          "source_file": str_path, "source_location": f"L{line}",
                          "confidence_score": 1.0})

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", score: float = 1.0) -> None:
        edges.append({"source": src, "target": tgt, "relation": relation,
                      "confidence": confidence, "confidence_score": score,
                      "source_file": str_path, "source_location": f"L{line}", "weight": 1.0})

    file_nid = _make_id(str(path))
    add_node(file_nid, path.name, 1)

    def walk(node, module_nid: str | None = None) -> None:
        t = node.type

        if t == "module_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                mod_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                nid = _make_id(stem, mod_name)
                add_node(nid, mod_name, line)
                add_edge(file_nid, nid, "defines", line)
                for child in node.children:
                    walk(child, nid)
                return

        elif t in ("function_declaration", "function_prototype"):
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                parent = module_nid or file_nid
                nid = _make_id(parent, func_name)
                add_node(nid, f"{func_name}()", line)
                add_edge(parent, nid, "contains", line)

        elif t == "task_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                task_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                parent = module_nid or file_nid
                nid = _make_id(parent, task_name)
                add_node(nid, task_name, line)
                add_edge(parent, nid, "contains", line)

        elif t == "package_import_declaration":
            for child in node.children:
                if child.type == "package_import_item":
                    pkg_text = _read_text(child, source)
                    pkg_name = pkg_text.split("::")[0].strip()
                    if pkg_name:
                        line = node.start_point[0] + 1
                        tgt_nid = _make_id(pkg_name)
                        add_node(tgt_nid, pkg_name, line)
                        src = module_nid or file_nid
                        add_edge(src, tgt_nid, "imports_from", line)

        elif t == "module_instantiation":
            # module_type instantiates another module
            type_node = node.child_by_field_name("module_type")
            if type_node and module_nid:
                inst_type = _read_text(type_node, source).strip()
                if inst_type:
                    line = node.start_point[0] + 1
                    tgt_nid = _make_id(inst_type)
                    add_node(tgt_nid, inst_type, line)
                    add_edge(module_nid, tgt_nid, "instantiates", line)

        for child in node.children:
            walk(child, module_nid)

    walk(root)
    return {"nodes": nodes, "edges": edges}


def extract_lua(path: Path) -> dict:
    """Extract functions, methods, require() imports, and calls from a .lua file."""
    return _extract_generic(path, _LUA_CONFIG)


def extract_swift(path: Path) -> dict:
    """Extract classes, structs, protocols, functions, imports, and calls from a .swift file."""
    return _extract_generic(path, _SWIFT_CONFIG)


# ── Julia extractor (custom walk) ────────────────────────────────────────────

def extract_julia(path: Path) -> dict:
    """Extract modules, structs, functions, imports, and calls from a .jl file."""
    try:
        import tree_sitter_julia as tsjulia
        from tree_sitter import Language, Parser
    except ImportError:
        return {"nodes": [], "edges": [], "error": "tree-sitter-julia not installed"}

    try:
        language = Language(tsjulia.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    stem = path.stem
    str_path = str(path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()
    function_bodies: list[tuple[str, object]] = []

    def add_node(nid: str, label: str, line: int) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            nodes.append({
                "id": nid,
                "label": label,
                "file_type": "code",
                "source_file": str_path,
                "source_location": f"L{line}",
            })

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", weight: float = 1.0) -> None:
        edges.append({
            "source": src,
            "target": tgt,
            "relation": relation,
            "confidence": confidence,
            "source_file": str_path,
            "source_location": f"L{line}",
            "weight": weight,
        })

    file_nid = _make_id(str(path))
    add_node(file_nid, path.name, 1)

    def _func_name_from_signature(sig_node) -> str | None:
        """Extract function name from a Julia signature node (call_expression > identifier)."""
        for child in sig_node.children:
            if child.type == "call_expression":
                callee = child.children[0] if child.children else None
                if callee and callee.type == "identifier":
                    return _read_text(callee, source)
        return None

    def walk_calls(body_node, func_nid: str) -> None:
        if body_node is None:
            return
        t = body_node.type
        if t in ("function_definition", "short_function_definition"):
            return
        if t == "call_expression" and body_node.children:
            callee = body_node.children[0]
            # Direct call: foo(...)
            if callee.type == "identifier":
                callee_name = _read_text(callee, source)
                target_nid = _make_id(stem, callee_name)
                add_edge(func_nid, target_nid, "calls", body_node.start_point[0] + 1,
                         confidence="EXTRACTED")
            # Method call: obj.method(...)
            elif callee.type == "field_expression" and len(callee.children) >= 3:
                method_node = callee.children[-1]
                method_name = _read_text(method_node, source)
                target_nid = _make_id(stem, method_name)
                add_edge(func_nid, target_nid, "calls", body_node.start_point[0] + 1,
                         confidence="EXTRACTED")
        for child in body_node.children:
            walk_calls(child, func_nid)

    def walk(node, scope_nid: str) -> None:
        t = node.type

        # Module
        if t == "module_definition":
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            if name_node:
                mod_name = _read_text(name_node, source)
                mod_nid = _make_id(stem, mod_name)
                line = node.start_point[0] + 1
                add_node(mod_nid, mod_name, line)
                add_edge(file_nid, mod_nid, "defines", line)
                for child in node.children:
                    walk(child, mod_nid)
            return

        # Struct (struct / mutable struct — both map to struct_definition in tree-sitter-julia)
        if t == "struct_definition":
            # type_head may contain: identifier (simple) or binary_expression (Foo <: Bar)
            type_head = next((c for c in node.children if c.type == "type_head"), None)
            if type_head:
                bin_expr = next((c for c in type_head.children if c.type == "binary_expression"), None)
                if bin_expr:
                    # First identifier is the struct name, last is the supertype
                    identifiers = [c for c in bin_expr.children if c.type == "identifier"]
                    if identifiers:
                        struct_name = _read_text(identifiers[0], source)
                        struct_nid = _make_id(stem, struct_name)
                        line = node.start_point[0] + 1
                        add_node(struct_nid, struct_name, line)
                        add_edge(scope_nid, struct_nid, "defines", line)
                        if len(identifiers) >= 2:
                            super_name = _read_text(identifiers[-1], source)
                            add_edge(struct_nid, _make_id(stem, super_name), "inherits",
                                     line, confidence="EXTRACTED")
                else:
                    name_node = next((c for c in type_head.children if c.type == "identifier"), None)
                    if name_node:
                        struct_name = _read_text(name_node, source)
                        struct_nid = _make_id(stem, struct_name)
                        line = node.start_point[0] + 1
                        add_node(struct_nid, struct_name, line)
                        add_edge(scope_nid, struct_nid, "defines", line)
            return

        # Abstract type
        if t == "abstract_definition":
            # type_head > identifier
            type_head = next((c for c in node.children if c.type == "type_head"), None)
            if type_head:
                name_node = next((c for c in type_head.children if c.type == "identifier"), None)
                if name_node:
                    abs_name = _read_text(name_node, source)
                    abs_nid = _make_id(stem, abs_name)
                    line = node.start_point[0] + 1
                    add_node(abs_nid, abs_name, line)
                    add_edge(scope_nid, abs_nid, "defines", line)
            return

        # Function: function foo(...) ... end
        if t == "function_definition":
            sig_node = next((c for c in node.children if c.type == "signature"), None)
            if sig_node:
                func_name = _func_name_from_signature(sig_node)
                if func_name:
                    func_nid = _make_id(stem, func_name)
                    line = node.start_point[0] + 1
                    add_node(func_nid, f"{func_name}()", line)
                    add_edge(scope_nid, func_nid, "defines", line)
                    function_bodies.append((func_nid, node))
            return

        # Short function: foo(x) = expr
        if t == "assignment":
            lhs = node.children[0] if node.children else None
            if lhs and lhs.type == "call_expression" and lhs.children:
                callee = lhs.children[0]
                if callee.type == "identifier":
                    func_name = _read_text(callee, source)
                    func_nid = _make_id(stem, func_name)
                    line = node.start_point[0] + 1
                    add_node(func_nid, f"{func_name}()", line)
                    add_edge(scope_nid, func_nid, "defines", line)
                    # Only walk the RHS (index 2 after lhs and operator) to avoid self-loops
                    rhs = node.children[-1] if len(node.children) >= 3 else None
                    if rhs:
                        function_bodies.append((func_nid, rhs))
            return

        # Using / Import
        if t in ("using_statement", "import_statement"):
            line = node.start_point[0] + 1
            for child in node.children:
                if child.type == "identifier":
                    mod_name = _read_text(child, source)
                    imp_nid = _make_id(mod_name)
                    add_node(imp_nid, mod_name, line)
                    add_edge(scope_nid, imp_nid, "imports", line)
                elif child.type == "selected_import":
                    identifiers = [c for c in child.children if c.type == "identifier"]
                    if identifiers:
                        pkg_name = _read_text(identifiers[0], source)
                        pkg_nid = _make_id(pkg_name)
                        add_node(pkg_nid, pkg_name, line)
                        add_edge(scope_nid, pkg_nid, "imports", line)
            return

        for child in node.children:
            walk(child, scope_nid)

    walk(root, file_nid)

    for func_nid, body_node in function_bodies:
        # For function_definition nodes, walk children directly to avoid
        # the boundary check returning early on the top-level node itself.
        # Skip the "signature" child — it contains the function's own call_expression
        # which would create a self-loop.
        if body_node.type == "function_definition":
            for child in body_node.children:
                if child.type != "signature":
                    walk_calls(child, func_nid)
        else:
            walk_calls(body_node, func_nid)

    return {"nodes": nodes, "edges": edges}


# ── Go extractor (custom walk) ────────────────────────────────────────────────

def extract_go(path: Path) -> dict:
    """Extract functions, methods, type declarations, and imports from a .go file."""
    try:
        import tree_sitter_go as tsgo
        from tree_sitter import Language, Parser
    except ImportError:
        return {"nodes": [], "edges": [], "error": "tree-sitter-go not installed"}

    try:
        language = Language(tsgo.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    stem = path.stem
    # Use directory name as package scope so methods on the same type across
    # multiple files in a package share one canonical type node.
    pkg_scope = path.parent.name or stem
    str_path = str(path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()
    function_bodies: list[tuple[str, object]] = []

    def add_node(nid: str, label: str, line: int) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            nodes.append({
                "id": nid,
                "label": label,
                "file_type": "code",
                "source_file": str_path,
                "source_location": f"L{line}",
            })

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", weight: float = 1.0) -> None:
        edges.append({
            "source": src,
            "target": tgt,
            "relation": relation,
            "confidence": confidence,
            "source_file": str_path,
            "source_location": f"L{line}",
            "weight": weight,
        })

    file_nid = _make_id(str(path))
    add_node(file_nid, path.name, 1)

    def walk(node) -> None:
        t = node.type

        if t == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                func_nid = _make_id(stem, func_name)
                add_node(func_nid, f"{func_name}()", line)
                add_edge(file_nid, func_nid, "contains", line)
                body = node.child_by_field_name("body")
                if body:
                    function_bodies.append((func_nid, body))
            return

        if t == "method_declaration":
            receiver = node.child_by_field_name("receiver")
            receiver_type: str | None = None
            if receiver:
                for param in receiver.children:
                    if param.type == "parameter_declaration":
                        type_node = param.child_by_field_name("type")
                        if type_node:
                            raw = _read_text(type_node, source).lstrip("*").strip()
                            receiver_type = raw
                        break
            name_node = node.child_by_field_name("name")
            if name_node:
                method_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                if receiver_type:
                    parent_nid = _make_id(pkg_scope, receiver_type)
                    add_node(parent_nid, receiver_type, line)
                    method_nid = _make_id(parent_nid, method_name)
                    add_node(method_nid, f".{method_name}()", line)
                    add_edge(parent_nid, method_nid, "method", line)
                else:
                    method_nid = _make_id(stem, method_name)
                    add_node(method_nid, f"{method_name}()", line)
                    add_edge(file_nid, method_nid, "contains", line)
                body = node.child_by_field_name("body")
                if body:
                    function_bodies.append((method_nid, body))
            return

        if t == "type_declaration":
            for child in node.children:
                if child.type == "type_spec":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        type_name = _read_text(name_node, source)
                        line = child.start_point[0] + 1
                        type_nid = _make_id(pkg_scope, type_name)
                        add_node(type_nid, type_name, line)
                        add_edge(file_nid, type_nid, "contains", line)
            return

        if t == "import_declaration":
            for child in node.children:
                if child.type == "import_spec_list":
                    for spec in child.children:
                        if spec.type == "import_spec":
                            path_node = spec.child_by_field_name("path")
                            if path_node:
                                raw = _read_text(path_node, source).strip('"')
                                module_name = raw.split("/")[-1]
                                tgt_nid = _make_id(module_name)
                                add_edge(file_nid, tgt_nid, "imports_from", spec.start_point[0] + 1)
                elif child.type == "import_spec":
                    path_node = child.child_by_field_name("path")
                    if path_node:
                        raw = _read_text(path_node, source).strip('"')
                        module_name = raw.split("/")[-1]
                        tgt_nid = _make_id(module_name)
                        add_edge(file_nid, tgt_nid, "imports_from", child.start_point[0] + 1)
            return

        for child in node.children:
            walk(child)

    walk(root)

    label_to_nid: dict[str, str] = {}
    for n in nodes:
        raw = n["label"]
        normalised = raw.strip("()").lstrip(".")
        label_to_nid[normalised.lower()] = n["id"]

    seen_call_pairs: set[tuple[str, str]] = set()

    def walk_calls(node, caller_nid: str) -> None:
        if node.type in ("function_declaration", "method_declaration"):
            return
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            callee_name: str | None = None
            if func_node:
                if func_node.type == "identifier":
                    callee_name = _read_text(func_node, source)
                elif func_node.type == "selector_expression":
                    field = func_node.child_by_field_name("field")
                    if field:
                        callee_name = _read_text(field, source)
            if callee_name:
                tgt_nid = label_to_nid.get(callee_name.lower())
                if tgt_nid and tgt_nid != caller_nid:
                    pair = (caller_nid, tgt_nid)
                    if pair not in seen_call_pairs:
                        seen_call_pairs.add(pair)
                        line = node.start_point[0] + 1
                        edges.append({
                            "source": caller_nid,
                            "target": tgt_nid,
                            "relation": "calls",
                            "confidence": "EXTRACTED",
                            "source_file": str_path,
                            "source_location": f"L{line}",
                            "weight": 1.0,
                        })
        for child in node.children:
            walk_calls(child, caller_nid)

    for caller_nid, body_node in function_bodies:
        walk_calls(body_node, caller_nid)

    valid_ids = seen_ids
    clean_edges = []
    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        if src in valid_ids and (tgt in valid_ids or edge["relation"] in ("imports", "imports_from")):
            clean_edges.append(edge)

    return {"nodes": nodes, "edges": clean_edges}


# ── Rust extractor (custom walk) ──────────────────────────────────────────────

def extract_rust(path: Path) -> dict:
    """Extract functions, structs, enums, traits, impl methods, and use declarations from a .rs file."""
    try:
        import tree_sitter_rust as tsrust
        from tree_sitter import Language, Parser
    except ImportError:
        return {"nodes": [], "edges": [], "error": "tree-sitter-rust not installed"}

    try:
        language = Language(tsrust.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    stem = path.stem
    str_path = str(path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()
    function_bodies: list[tuple[str, object]] = []

    def add_node(nid: str, label: str, line: int) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            nodes.append({
                "id": nid,
                "label": label,
                "file_type": "code",
                "source_file": str_path,
                "source_location": f"L{line}",
            })

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", weight: float = 1.0) -> None:
        edges.append({
            "source": src,
            "target": tgt,
            "relation": relation,
            "confidence": confidence,
            "source_file": str_path,
            "source_location": f"L{line}",
            "weight": weight,
        })

    file_nid = _make_id(str(path))
    add_node(file_nid, path.name, 1)

    def walk(node, parent_impl_nid: str | None = None) -> None:
        t = node.type

        if t == "function_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                if parent_impl_nid:
                    func_nid = _make_id(parent_impl_nid, func_name)
                    add_node(func_nid, f".{func_name}()", line)
                    add_edge(parent_impl_nid, func_nid, "method", line)
                else:
                    func_nid = _make_id(stem, func_name)
                    add_node(func_nid, f"{func_name}()", line)
                    add_edge(file_nid, func_nid, "contains", line)
                body = node.child_by_field_name("body")
                if body:
                    function_bodies.append((func_nid, body))
            return

        if t in ("struct_item", "enum_item", "trait_item"):
            name_node = node.child_by_field_name("name")
            if name_node:
                item_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                item_nid = _make_id(stem, item_name)
                add_node(item_nid, item_name, line)
                add_edge(file_nid, item_nid, "contains", line)
            return

        if t == "impl_item":
            type_node = node.child_by_field_name("type")
            impl_nid: str | None = None
            if type_node:
                type_name = _read_text(type_node, source).strip()
                impl_nid = _make_id(stem, type_name)
                add_node(impl_nid, type_name, node.start_point[0] + 1)
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    walk(child, parent_impl_nid=impl_nid)
            return

        if t == "use_declaration":
            arg = node.child_by_field_name("argument")
            if arg:
                raw = _read_text(arg, source)
                clean = raw.split("{")[0].rstrip(":").rstrip("*").rstrip(":")
                module_name = clean.split("::")[-1].strip()
                if module_name:
                    tgt_nid = _make_id(module_name)
                    add_edge(file_nid, tgt_nid, "imports_from", node.start_point[0] + 1)
            return

        for child in node.children:
            walk(child, parent_impl_nid=None)

    walk(root)

    label_to_nid: dict[str, str] = {}
    for n in nodes:
        raw = n["label"]
        normalised = raw.strip("()").lstrip(".")
        label_to_nid[normalised.lower()] = n["id"]

    seen_call_pairs: set[tuple[str, str]] = set()

    def walk_calls(node, caller_nid: str) -> None:
        if node.type == "function_item":
            return
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            callee_name: str | None = None
            if func_node:
                if func_node.type == "identifier":
                    callee_name = _read_text(func_node, source)
                elif func_node.type == "field_expression":
                    field = func_node.child_by_field_name("field")
                    if field:
                        callee_name = _read_text(field, source)
                elif func_node.type == "scoped_identifier":
                    name = func_node.child_by_field_name("name")
                    if name:
                        callee_name = _read_text(name, source)
            if callee_name:
                tgt_nid = label_to_nid.get(callee_name.lower())
                if tgt_nid and tgt_nid != caller_nid:
                    pair = (caller_nid, tgt_nid)
                    if pair not in seen_call_pairs:
                        seen_call_pairs.add(pair)
                        line = node.start_point[0] + 1
                        edges.append({
                            "source": caller_nid,
                            "target": tgt_nid,
                            "relation": "calls",
                            "confidence": "EXTRACTED",
                            "source_file": str_path,
                            "source_location": f"L{line}",
                            "weight": 1.0,
                        })
        for child in node.children:
            walk_calls(child, caller_nid)

    for caller_nid, body_node in function_bodies:
        walk_calls(body_node, caller_nid)

    valid_ids = seen_ids
    clean_edges = []
    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        if src in valid_ids and (tgt in valid_ids or edge["relation"] in ("imports", "imports_from")):
            clean_edges.append(edge)

    return {"nodes": nodes, "edges": clean_edges}


# ── Zig ───────────────────────────────────────────────────────────────────────

def extract_zig(path: Path) -> dict:
    """Extract functions, structs, enums, unions, and imports from a .zig file."""
    try:
        import tree_sitter_zig as tszig
        from tree_sitter import Language, Parser
    except ImportError:
        return {"nodes": [], "edges": [], "error": "tree_sitter_zig not installed"}

    try:
        language = Language(tszig.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    stem = path.stem
    str_path = str(path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()
    function_bodies: list[tuple[str, Any]] = []

    def add_node(nid: str, label: str, line: int) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            nodes.append({"id": nid, "label": label, "file_type": "code",
                          "source_file": str_path, "source_location": f"L{line}"})

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", weight: float = 1.0) -> None:
        edges.append({"source": src, "target": tgt, "relation": relation,
                      "confidence": confidence, "source_file": str_path,
                      "source_location": f"L{line}", "weight": weight})

    file_nid = _make_id(str(path))
    add_node(file_nid, path.name, 1)

    def _extract_import(node) -> None:
        for child in node.children:
            if child.type == "builtin_function":
                bi = None
                args = None
                for c in child.children:
                    if c.type == "builtin_identifier":
                        bi = _read_text(c, source)
                    elif c.type == "arguments":
                        args = c
                if bi in ("@import", "@cImport") and args:
                    for arg in args.children:
                        if arg.type in ("string_literal", "string"):
                            raw = _read_text(arg, source).strip('"')
                            module_name = raw.split("/")[-1].split(".")[0]
                            if module_name:
                                tgt_nid = _make_id(module_name)
                                add_edge(file_nid, tgt_nid, "imports_from",
                                         node.start_point[0] + 1)
                            return
            elif child.type == "field_expression":
                _extract_import(child)
                return

    def walk(node, parent_struct_nid: str | None = None) -> None:
        t = node.type

        if t == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                if parent_struct_nid:
                    func_nid = _make_id(parent_struct_nid, func_name)
                    add_node(func_nid, f".{func_name}()", line)
                    add_edge(parent_struct_nid, func_nid, "method", line)
                else:
                    func_nid = _make_id(stem, func_name)
                    add_node(func_nid, f"{func_name}()", line)
                    add_edge(file_nid, func_nid, "contains", line)
                body = node.child_by_field_name("body")
                if body:
                    function_bodies.append((func_nid, body))
            return

        if t == "variable_declaration":
            name_node = None
            value_node = None
            for child in node.children:
                if child.type == "identifier":
                    name_node = child
                elif child.type in ("struct_declaration", "enum_declaration",
                                    "union_declaration", "builtin_function",
                                    "field_expression"):
                    value_node = child

            if value_node and value_node.type == "struct_declaration":
                if name_node:
                    struct_name = _read_text(name_node, source)
                    line = node.start_point[0] + 1
                    struct_nid = _make_id(stem, struct_name)
                    add_node(struct_nid, struct_name, line)
                    add_edge(file_nid, struct_nid, "contains", line)
                    for child in value_node.children:
                        walk(child, parent_struct_nid=struct_nid)
                return

            if value_node and value_node.type in ("enum_declaration", "union_declaration"):
                if name_node:
                    type_name = _read_text(name_node, source)
                    line = node.start_point[0] + 1
                    type_nid = _make_id(stem, type_name)
                    add_node(type_nid, type_name, line)
                    add_edge(file_nid, type_nid, "contains", line)
                return

            if value_node and value_node.type in ("builtin_function", "field_expression"):
                _extract_import(node)
            return

        for child in node.children:
            walk(child, parent_struct_nid)

    walk(root)

    seen_call_pairs: set[tuple[str, str]] = set()

    def walk_calls(node, caller_nid: str) -> None:
        if node.type == "function_declaration":
            return
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn:
                callee = _read_text(fn, source).split(".")[-1]
                tgt_nid = next((n["id"] for n in nodes if n["label"] in
                                (f"{callee}()", f".{callee}()")), None)
                if tgt_nid and tgt_nid != caller_nid:
                    pair = (caller_nid, tgt_nid)
                    if pair not in seen_call_pairs:
                        seen_call_pairs.add(pair)
                        add_edge(caller_nid, tgt_nid, "calls",
                                 node.start_point[0] + 1,
                                 confidence="EXTRACTED", weight=1.0)
        for child in node.children:
            walk_calls(child, caller_nid)

    for caller_nid, body_node in function_bodies:
        walk_calls(body_node, caller_nid)

    clean_edges = [e for e in edges if e["source"] in seen_ids and
                   (e["target"] in seen_ids or e["relation"] == "imports_from")]
    return {"nodes": nodes, "edges": clean_edges}


# ── PowerShell ────────────────────────────────────────────────────────────────

def extract_powershell(path: Path) -> dict:
    """Extract functions, classes, methods, and using statements from a .ps1 file."""
    try:
        import tree_sitter_powershell as tsps
        from tree_sitter import Language, Parser
    except ImportError:
        return {"nodes": [], "edges": [], "error": "tree_sitter_powershell not installed"}

    try:
        language = Language(tsps.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    stem = path.stem
    str_path = str(path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()
    function_bodies: list[tuple[str, Any]] = []

    def add_node(nid: str, label: str, line: int) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            nodes.append({"id": nid, "label": label, "file_type": "code",
                          "source_file": str_path, "source_location": f"L{line}"})

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", weight: float = 1.0) -> None:
        edges.append({"source": src, "target": tgt, "relation": relation,
                      "confidence": confidence, "source_file": str_path,
                      "source_location": f"L{line}", "weight": weight})

    file_nid = _make_id(str(path))
    add_node(file_nid, path.name, 1)

    _PS_SKIP = frozenset({
        "using", "return", "if", "else", "elseif", "foreach", "for",
        "while", "do", "switch", "try", "catch", "finally", "throw",
        "break", "continue", "exit", "param", "begin", "process", "end",
    })

    def _find_script_block_body(node):
        for child in node.children:
            if child.type == "script_block":
                for sc in child.children:
                    if sc.type == "script_block_body":
                        return sc
                return child
        return None

    def walk(node, parent_class_nid: str | None = None) -> None:
        t = node.type

        if t == "function_statement":
            name_node = next((c for c in node.children if c.type == "function_name"), None)
            if name_node:
                func_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                func_nid = _make_id(stem, func_name)
                add_node(func_nid, f"{func_name}()", line)
                add_edge(file_nid, func_nid, "contains", line)
                body = _find_script_block_body(node)
                if body:
                    function_bodies.append((func_nid, body))
            return

        if t == "class_statement":
            name_node = next((c for c in node.children if c.type == "simple_name"), None)
            if name_node:
                class_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                class_nid = _make_id(stem, class_name)
                add_node(class_nid, class_name, line)
                add_edge(file_nid, class_nid, "contains", line)
                for child in node.children:
                    walk(child, parent_class_nid=class_nid)
            return

        if t == "class_method_definition":
            name_node = next((c for c in node.children if c.type == "simple_name"), None)
            if name_node:
                method_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                if parent_class_nid:
                    method_nid = _make_id(parent_class_nid, method_name)
                    add_node(method_nid, f".{method_name}()", line)
                    add_edge(parent_class_nid, method_nid, "method", line)
                else:
                    method_nid = _make_id(stem, method_name)
                    add_node(method_nid, f"{method_name}()", line)
                    add_edge(file_nid, method_nid, "contains", line)
                body = _find_script_block_body(node)
                if body:
                    function_bodies.append((method_nid, body))
            return

        if t == "command":
            cmd_name_node = next((c for c in node.children if c.type == "command_name"), None)
            if cmd_name_node:
                cmd_text = _read_text(cmd_name_node, source).lower()
                if cmd_text == "using":
                    tokens = []
                    for child in node.children:
                        if child.type == "command_elements":
                            for el in child.children:
                                if el.type == "generic_token":
                                    tokens.append(_read_text(el, source))
                    module_tokens = [t for t in tokens
                                     if t.lower() not in ("namespace", "module", "assembly")]
                    if module_tokens:
                        module_name = module_tokens[-1].split(".")[-1]
                        add_edge(file_nid, _make_id(module_name), "imports_from",
                                 node.start_point[0] + 1)
            return

        for child in node.children:
            walk(child, parent_class_nid)

    walk(root)

    label_to_nid = {n["label"].strip("()").lstrip(".").lower(): n["id"] for n in nodes}
    seen_call_pairs: set[tuple[str, str]] = set()

    def walk_calls(node, caller_nid: str) -> None:
        if node.type in ("function_statement", "class_statement"):
            return
        if node.type == "command":
            cmd_name_node = next((c for c in node.children if c.type == "command_name"), None)
            if cmd_name_node:
                cmd_text = _read_text(cmd_name_node, source)
                if cmd_text.lower() not in _PS_SKIP:
                    tgt_nid = label_to_nid.get(cmd_text.lower())
                    if tgt_nid and tgt_nid != caller_nid:
                        pair = (caller_nid, tgt_nid)
                        if pair not in seen_call_pairs:
                            seen_call_pairs.add(pair)
                            add_edge(caller_nid, tgt_nid, "calls",
                                     node.start_point[0] + 1,
                                     confidence="EXTRACTED", weight=1.0)
        for child in node.children:
            walk_calls(child, caller_nid)

    for caller_nid, body_node in function_bodies:
        walk_calls(body_node, caller_nid)

    clean_edges = [e for e in edges if e["source"] in seen_ids and
                   (e["target"] in seen_ids or e["relation"] == "imports_from")]
    return {"nodes": nodes, "edges": clean_edges}


# ── Cross-file import resolution ──────────────────────────────────────────────

def _resolve_cross_file_imports(
    per_file: list[dict],
    paths: list[Path],
) -> list[dict]:
    """
    Two-pass import resolution: turn file-level imports into class-level edges.

    Pass 1 - build a global map: class/function name → node_id, per stem.
    Pass 2 - for each `from .module import Name`, look up Name in the global
              map and add a direct INFERRED edge from each class in the
              importing file to the imported entity.

    This turns:
        auth.py --imports_from--> models.py          (obvious, filtered out)
    Into:
        DigestAuth --uses--> Response  [INFERRED]    (cross-file, interesting!)
        BasicAuth  --uses--> Request   [INFERRED]
    """
    try:
        import tree_sitter_python as tspython
        from tree_sitter import Language, Parser
    except ImportError:
        return []

    language = Language(tspython.language())
    parser = Parser(language)

    # Pass 1: name → node_id across all files
    # Map: stem → {ClassName: node_id}
    stem_to_entities: dict[str, dict[str, str]] = {}
    for file_result in per_file:
        for node in file_result.get("nodes", []):
            src = node.get("source_file", "")
            if not src:
                continue
            stem = Path(src).stem
            label = node.get("label", "")
            nid = node.get("id", "")
            # Only index real classes/functions (not file nodes, not method stubs)
            if label and not label.endswith((")", ".py")) and "_" not in label[:1]:
                stem_to_entities.setdefault(stem, {})[label] = nid

    # Pass 2: for each file, find `from .X import A, B, C` and resolve
    new_edges: list[dict] = []
    stem_to_path: dict[str, Path] = {p.stem: p for p in paths}

    for file_result, path in zip(per_file, paths):
        stem = path.stem
        str_path = str(path)

        # Find all classes defined in this file (the importers)
        local_classes = [
            n["id"] for n in file_result.get("nodes", [])
            if n.get("source_file") == str_path
            and not n["label"].endswith((")", ".py"))
            and n["id"] != _make_id(stem)  # exclude file-level node
        ]
        if not local_classes:
            continue

        # Parse imports from this file
        try:
            source = path.read_bytes()
            tree = parser.parse(source)
        except Exception:
            continue

        def walk_imports(node) -> None:
            if node.type == "import_from_statement":
                # Find the module name - handles both absolute and relative imports.
                # Relative: `from .models import X` → relative_import → dotted_name
                # Absolute: `from models import X`  → module_name field
                target_stem: str | None = None
                for child in node.children:
                    if child.type == "relative_import":
                        # Dig into relative_import → dotted_name → identifier
                        for sub in child.children:
                            if sub.type == "dotted_name":
                                raw = source[sub.start_byte:sub.end_byte].decode("utf-8", errors="replace")
                                target_stem = raw.split(".")[-1]
                                break
                        break
                    if child.type == "dotted_name" and target_stem is None:
                        raw = source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                        target_stem = raw.split(".")[-1]

                if not target_stem or target_stem not in stem_to_entities:
                    return

                # Collect imported names: dotted_name children of import_from_statement
                # that come AFTER the 'import' keyword token.
                imported_names: list[str] = []
                past_import_kw = False
                for child in node.children:
                    if child.type == "import":
                        past_import_kw = True
                        continue
                    if not past_import_kw:
                        continue
                    if child.type == "dotted_name":
                        imported_names.append(
                            source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                        )
                    elif child.type == "aliased_import":
                        # `import X as Y` - take the original name
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            imported_names.append(
                                source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
                            )

                line = node.start_point[0] + 1
                for name in imported_names:
                    tgt_nid = stem_to_entities[target_stem].get(name)
                    if tgt_nid:
                        for src_class_nid in local_classes:
                            new_edges.append({
                                "source": src_class_nid,
                                "target": tgt_nid,
                                "relation": "uses",
                                "confidence": "INFERRED",
                                "source_file": str_path,
                                "source_location": f"L{line}",
                                "weight": 0.8,
                            })
            for child in node.children:
                walk_imports(child)

        walk_imports(tree.root_node)

    return new_edges


def extract_objc(path: Path) -> dict:
    """Extract interfaces, implementations, protocols, methods, and imports from .m/.mm/.h files."""
    try:
        import tree_sitter_objc as tsobjc
        from tree_sitter import Language, Parser
    except ImportError:
        return {"nodes": [], "edges": [], "error": "tree_sitter_objc not installed"}

    try:
        language = Language(tsobjc.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    stem = path.stem
    str_path = str(path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()
    method_bodies: list[tuple[str, Any]] = []

    def add_node(nid: str, label: str, line: int) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            nodes.append({"id": nid, "label": label, "file_type": "code",
                          "source_file": str_path, "source_location": f"L{line}"})

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", weight: float = 1.0) -> None:
        edges.append({"source": src, "target": tgt, "relation": relation,
                      "confidence": confidence, "source_file": str_path,
                      "source_location": f"L{line}", "weight": weight})

    file_nid = _make_id(str(path))
    add_node(file_nid, path.name, 1)

    def _read(node) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _get_name(node, field: str) -> str | None:
        n = node.child_by_field_name(field)
        return _read(n) if n else None

    def walk(node, parent_nid: str | None = None) -> None:
        t = node.type
        line = node.start_point[0] + 1

        if t == "preproc_include":
            # #import <Foundation/Foundation.h> or #import "MyClass.h"
            for child in node.children:
                if child.type == "system_lib_string":
                    raw = _read(child).strip("<>")
                    module = raw.split("/")[-1].replace(".h", "")
                    if module:
                        tgt_nid = _make_id(module)
                        add_edge(file_nid, tgt_nid, "imports", line)
                elif child.type == "string_literal":
                    # recurse into string_literal to find string_content
                    for sub in child.children:
                        if sub.type == "string_content":
                            raw = _read(sub)
                            module = raw.split("/")[-1].replace(".h", "")
                            if module:
                                tgt_nid = _make_id(module)
                                add_edge(file_nid, tgt_nid, "imports", line)
            return

        if t == "class_interface":
            # @interface ClassName : SuperClass <Protocols>
            # children: @interface, identifier(name), ':', identifier(super), parameterized_arguments, ...
            identifiers = [c for c in node.children if c.type == "identifier"]
            if not identifiers:
                for child in node.children:
                    walk(child, parent_nid)
                return
            name = _read(identifiers[0])
            cls_nid = _make_id(stem, name)
            add_node(cls_nid, name, line)
            add_edge(file_nid, cls_nid, "contains", line)
            # superclass is second identifier after ':'
            colon_seen = False
            for child in node.children:
                if child.type == ":":
                    colon_seen = True
                elif colon_seen and child.type == "identifier":
                    super_nid = _make_id(_read(child))
                    add_edge(cls_nid, super_nid, "inherits", line)
                    colon_seen = False
                elif child.type == "parameterized_arguments":
                    # protocols adopted
                    for sub in child.children:
                        if sub.type == "type_name":
                            for s in sub.children:
                                if s.type == "type_identifier":
                                    proto_nid = _make_id(_read(s))
                                    add_edge(cls_nid, proto_nid, "imports", line)
                elif child.type == "method_declaration":
                    walk(child, cls_nid)
            return

        if t == "class_implementation":
            # @implementation ClassName
            name = None
            for child in node.children:
                if child.type == "identifier":
                    name = _read(child)
                    break
            if not name:
                for child in node.children:
                    walk(child, parent_nid)
                return
            impl_nid = _make_id(stem, name)
            if impl_nid not in seen_ids:
                add_node(impl_nid, name, line)
                add_edge(file_nid, impl_nid, "contains", line)
            for child in node.children:
                if child.type == "implementation_definition":
                    for sub in child.children:
                        walk(sub, impl_nid)
            return

        if t == "protocol_declaration":
            name = None
            for child in node.children:
                if child.type == "identifier":
                    name = _read(child)
                    break
            if name:
                proto_nid = _make_id(stem, name)
                add_node(proto_nid, f"<{name}>", line)
                add_edge(file_nid, proto_nid, "contains", line)
                for child in node.children:
                    walk(child, proto_nid)
            return

        if t in ("method_declaration", "method_definition"):
            container = parent_nid or file_nid
            # method name is the first identifier child (simple selector)
            # for compound selectors: identifier + method_parameter pairs
            parts = []
            for child in node.children:
                if child.type == "identifier":
                    parts.append(_read(child))
                elif child.type == "method_parameter":
                    for sub in child.children:
                        if sub.type == "identifier":
                            # selector keyword before ':'
                            pass
            method_name = "".join(parts) if parts else None
            if method_name:
                method_nid = _make_id(container, method_name)
                add_node(method_nid, f"-{method_name}", line)
                add_edge(container, method_nid, "method", line)
                if t == "method_definition":
                    method_bodies.append((method_nid, node))
            return

        for child in node.children:
            walk(child, parent_nid)

    walk(root)

    # Second pass: resolve calls inside method bodies
    all_method_nids = {n["id"] for n in nodes if n["id"] != file_nid}
    seen_calls: set[tuple[str, str]] = set()
    for caller_nid, body_node in method_bodies:
        def walk_calls(n) -> None:
            if n.type == "message_expression":
                # [receiver selector]
                for child in n.children:
                    if child.type in ("selector", "keyword_argument_list"):
                        sel = []
                        if child.type == "selector":
                            sel.append(_read(child))
                        else:
                            for sub in child.children:
                                if sub.type == "keyword_argument":
                                    for s in sub.children:
                                        if s.type == "selector":
                                            sel.append(_read(s))
                        method_name = "".join(sel)
                        for candidate in all_method_nids:
                            if candidate.endswith(_make_id("", method_name).lstrip("_")):
                                pair = (caller_nid, candidate)
                                if pair not in seen_calls and caller_nid != candidate:
                                    seen_calls.add(pair)
                                    add_edge(caller_nid, candidate, "calls", body_node.start_point[0] + 1,
                                             confidence="EXTRACTED", weight=1.0)
            for child in n.children:
                walk_calls(child)
        walk_calls(body_node)

    return {"nodes": nodes, "edges": edges, "input_tokens": 0, "output_tokens": 0}


def extract_elixir(path: Path) -> dict:
    """Extract modules, functions, imports, and calls from a .ex/.exs file."""
    try:
        import tree_sitter_elixir as tselixir
        from tree_sitter import Language, Parser
    except ImportError:
        return {"nodes": [], "edges": [], "error": "tree_sitter_elixir not installed"}

    try:
        language = Language(tselixir.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

    stem = path.stem
    str_path = str(path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()
    function_bodies: list[tuple[str, Any]] = []

    def add_node(nid: str, label: str, line: int) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            nodes.append({"id": nid, "label": label, "file_type": "code",
                          "source_file": str_path, "source_location": f"L{line}"})

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", weight: float = 1.0) -> None:
        edges.append({"source": src, "target": tgt, "relation": relation,
                      "confidence": confidence, "source_file": str_path,
                      "source_location": f"L{line}", "weight": weight})

    file_nid = _make_id(str(path))
    add_node(file_nid, path.name, 1)

    _IMPORT_KEYWORDS = frozenset({"alias", "import", "require", "use"})

    def _get_alias_text(node) -> str | None:
        for child in node.children:
            if child.type == "alias":
                return source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
        return None

    def walk(node, parent_module_nid: str | None = None) -> None:
        if node.type != "call":
            for child in node.children:
                walk(child, parent_module_nid)
            return

        identifier_node = None
        arguments_node = None
        do_block_node = None
        for child in node.children:
            if child.type == "identifier":
                identifier_node = child
            elif child.type == "arguments":
                arguments_node = child
            elif child.type == "do_block":
                do_block_node = child

        if identifier_node is None:
            for child in node.children:
                walk(child, parent_module_nid)
            return

        keyword = source[identifier_node.start_byte:identifier_node.end_byte].decode("utf-8", errors="replace")
        line = node.start_point[0] + 1

        if keyword == "defmodule":
            module_name = _get_alias_text(arguments_node) if arguments_node else None
            if not module_name:
                return
            module_nid = _make_id(stem, module_name)
            add_node(module_nid, module_name, line)
            add_edge(file_nid, module_nid, "contains", line)
            if do_block_node:
                for child in do_block_node.children:
                    walk(child, parent_module_nid=module_nid)
            return

        if keyword in ("def", "defp"):
            func_name = None
            if arguments_node:
                for child in arguments_node.children:
                    if child.type == "call":
                        for sub in child.children:
                            if sub.type == "identifier":
                                func_name = source[sub.start_byte:sub.end_byte].decode("utf-8", errors="replace")
                                break
                    elif child.type == "identifier":
                        func_name = source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                        break
            if not func_name:
                return
            container = parent_module_nid or file_nid
            func_nid = _make_id(container, func_name)
            add_node(func_nid, f"{func_name}()", line)
            if parent_module_nid:
                add_edge(parent_module_nid, func_nid, "method", line)
            else:
                add_edge(file_nid, func_nid, "contains", line)
            if do_block_node:
                function_bodies.append((func_nid, do_block_node))
            return

        if keyword in _IMPORT_KEYWORDS and arguments_node:
            module_name = _get_alias_text(arguments_node)
            if module_name:
                tgt_nid = _make_id(module_name)
                add_edge(file_nid, tgt_nid, "imports", line)
            return

        for child in node.children:
            walk(child, parent_module_nid)

    walk(root)

    label_to_nid: dict[str, str] = {}
    for n in nodes:
        normalised = n["label"].strip("()").lstrip(".")
        label_to_nid[normalised.lower()] = n["id"]

    seen_call_pairs: set[tuple[str, str]] = set()
    _SKIP_KEYWORDS = frozenset({
        "def", "defp", "defmodule", "defmacro", "defmacrop",
        "defstruct", "defprotocol", "defimpl", "defguard",
        "alias", "import", "require", "use",
        "if", "unless", "case", "cond", "with", "for",
    })

    def walk_calls(node, caller_nid: str) -> None:
        if node.type != "call":
            for child in node.children:
                walk_calls(child, caller_nid)
            return
        for child in node.children:
            if child.type == "identifier":
                kw = source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                if kw in _SKIP_KEYWORDS:
                    for c in node.children:
                        walk_calls(c, caller_nid)
                    return
                break
        callee_name: str | None = None
        for child in node.children:
            if child.type == "dot":
                dot_text = source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                parts = dot_text.rstrip(".").split(".")
                if parts:
                    callee_name = parts[-1]
                break
            if child.type == "identifier":
                callee_name = source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                break
        if callee_name:
            tgt_nid = label_to_nid.get(callee_name.lower())
            if tgt_nid and tgt_nid != caller_nid:
                pair = (caller_nid, tgt_nid)
                if pair not in seen_call_pairs:
                    seen_call_pairs.add(pair)
                    add_edge(caller_nid, tgt_nid, "calls",
                             node.start_point[0] + 1, confidence="EXTRACTED", weight=1.0)
        for child in node.children:
            walk_calls(child, caller_nid)

    for caller_nid, body in function_bodies:
        walk_calls(body, caller_nid)

    clean_edges = [e for e in edges if e["source"] in seen_ids and
                   (e["target"] in seen_ids or e["relation"] == "imports")]
    return {"nodes": nodes, "edges": clean_edges, "input_tokens": 0, "output_tokens": 0}


# ── Main extract and collect_files ────────────────────────────────────────────


def _check_tree_sitter_version() -> None:
    """Raise a clear error if tree-sitter is too old for the new Language API."""
    try:
        from tree_sitter import LANGUAGE_VERSION
    except ImportError:
        raise ImportError(
            "tree-sitter is not installed. Run: pip install 'tree-sitter>=0.23.0'"
        )
    # Language API v2 starts at LANGUAGE_VERSION 14
    if LANGUAGE_VERSION < 14:
        import tree_sitter as _ts
        raise RuntimeError(
            f"tree-sitter {getattr(_ts, '__version__', 'unknown')} is too old. "
            f"graphify requires tree-sitter >= 0.23.0 (Language API v2). "
            f"Run: pip install --upgrade tree-sitter"
        )


def extract(paths: list[Path]) -> dict:
    """Extract AST nodes and edges from a list of code files.

    Two-pass process:
    1. Per-file structural extraction (classes, functions, imports)
    2. Cross-file import resolution: turns file-level imports into
       class-level INFERRED edges (DigestAuth --uses--> Response)
    """
    _check_tree_sitter_version()
    per_file: list[dict] = []

    # Infer a common root for cache keys
    try:
        if not paths:
            root = Path(".")
        elif len(paths) == 1:
            root = paths[0].parent
        else:
            common_len = sum(
                1 for i in range(min(len(p.parts) for p in paths))
                if len({p.parts[i] for p in paths}) == 1
            )
            root = Path(*paths[0].parts[:common_len]) if common_len else Path(".")
    except Exception:
        root = Path(".")

    _DISPATCH: dict[str, Any] = {
        ".py": extract_python,
        ".js": extract_js,
        ".jsx": extract_js,
        ".ts": extract_js,
        ".tsx": extract_js,
        ".ets": extract_ets,
        ".go": extract_go,
        ".rs": extract_rust,
        ".java": extract_java,
        ".c": extract_c,
        ".h": extract_c,
        ".cpp": extract_cpp,
        ".cc": extract_cpp,
        ".cxx": extract_cpp,
        ".hpp": extract_cpp,
        ".rb": extract_ruby,
        ".cs": extract_csharp,
        ".kt": extract_kotlin,
        ".kts": extract_kotlin,
        ".scala": extract_scala,
        ".php": extract_php,
        ".swift": extract_swift,
        ".lua": extract_lua,
        ".toc": extract_lua,
        ".zig": extract_zig,
        ".ps1": extract_powershell,
        ".ex": extract_elixir,
        ".exs": extract_elixir,
        ".m": extract_objc,
        ".mm": extract_objc,
        ".jl": extract_julia,
        ".vue": extract_js,
        ".svelte": extract_js,
        ".dart": extract_dart,
        ".v": extract_verilog,
        ".sv": extract_verilog,
    }

    total = len(paths)
    _PROGRESS_INTERVAL = 100
    for i, path in enumerate(paths):
        if total >= _PROGRESS_INTERVAL and i % _PROGRESS_INTERVAL == 0 and i > 0:
            print(f"  AST extraction: {i}/{total} files ({i * 100 // total}%)", flush=True)
        # .blade.php must be checked before suffix lookup since Path.suffix returns .php
        if path.name.endswith(".blade.php"):
            extractor = extract_blade
        else:
            extractor = _DISPATCH.get(path.suffix)
        if extractor is None:
            continue
        cached = load_cached(path, root)
        if cached is not None:
            per_file.append(cached)
            continue
        result = extractor(path)
        if "error" not in result:
            save_cached(path, result, root)
        per_file.append(result)
    if total >= _PROGRESS_INTERVAL:
        print(f"  AST extraction: {total}/{total} files (100%)", flush=True)

    all_nodes: list[dict] = []
    all_edges: list[dict] = []
    for result in per_file:
        all_nodes.extend(result.get("nodes", []))
        all_edges.extend(result.get("edges", []))

    # Add cross-file class-level edges (Python only - uses Python parser internally)
    py_paths = [p for p in paths if p.suffix == ".py"]
    if py_paths:
        py_results = [r for r, p in zip(per_file, paths) if p.suffix == ".py"]
        try:
            cross_file_edges = _resolve_cross_file_imports(py_results, py_paths)
            all_edges.extend(cross_file_edges)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Cross-file import resolution failed, skipping: %s", exc)

    return {
        "nodes": all_nodes,
        "edges": all_edges,
        "input_tokens": 0,
        "output_tokens": 0,
    }


def collect_files(target: Path, *, follow_symlinks: bool = False, root: Path | None = None) -> list[Path]:
    if target.is_file():
        return [target]
    _EXTENSIONS = {
        ".py", ".js", ".ts", ".tsx", ".go", ".rs",
        ".java", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp",
        ".rb", ".cs", ".kt", ".kts", ".scala", ".php", ".swift",
        ".lua", ".toc", ".zig", ".ps1",
        ".m", ".mm",
    }
    from graphify.detect import _load_graphifyignore, _is_ignored
    ignore_root = root if root is not None else target
    patterns = _load_graphifyignore(ignore_root)

    def _ignored(p: Path) -> bool:
        return bool(patterns and _is_ignored(p, ignore_root, patterns))

    if not follow_symlinks:
        results: list[Path] = []
        for ext in sorted(_EXTENSIONS):
            results.extend(
                p for p in target.rglob(f"*{ext}")
                if not any(part.startswith(".") for part in p.parts)
                and not _ignored(p)
            )
        return sorted(results)
    # Walk with symlink following + cycle detection
    results = []
    for dirpath, dirnames, filenames in os.walk(target, followlinks=True):
        if os.path.islink(dirpath):
            real = os.path.realpath(dirpath)
            parent_real = os.path.realpath(os.path.dirname(dirpath))
            if parent_real == real or parent_real.startswith(real + os.sep):
                dirnames.clear()
                continue
        dp = Path(dirpath)
        if any(part.startswith(".") for part in dp.parts):
            dirnames.clear()
            continue
        for fname in filenames:
            p = dp / fname
            if p.suffix in _EXTENSIONS and not fname.startswith(".") and not _ignored(p):
                results.append(p)
    return sorted(results)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m graphify.extract <file_or_dir> ...", file=sys.stderr)
        sys.exit(1)

    paths: list[Path] = []
    for arg in sys.argv[1:]:
        paths.extend(collect_files(Path(arg)))

    result = extract(paths)
    print(json.dumps(result, indent=2))
