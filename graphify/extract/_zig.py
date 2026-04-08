"""Zig language extractor (custom walk — not driven by LanguageConfig)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ._base import ExtractionContext, _make_id, _read_text, make_error_result


def extract_zig(path: Path) -> dict:
    """Extract functions, structs, enums, unions, and imports from a .zig file."""
    try:
        import tree_sitter_zig as tszig
        from tree_sitter import Language, Parser
    except ImportError:
        return make_error_result("tree_sitter_zig not installed")

    try:
        language = Language(tszig.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return make_error_result(str(e))

    ctx = ExtractionContext(path, source)

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
                                ctx.add_edge(ctx.file_nid, tgt_nid, "imports_from",
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
                    ctx.add_node(func_nid, f".{func_name}()", line)
                    ctx.add_edge(parent_struct_nid, func_nid, "method", line)
                else:
                    func_nid = _make_id(ctx.stem, func_name)
                    ctx.add_node(func_nid, f"{func_name}()", line)
                    ctx.add_edge(ctx.file_nid, func_nid, "contains", line)
                body = node.child_by_field_name("body")
                if body:
                    ctx.function_bodies.append((func_nid, body))
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
                    struct_nid = _make_id(ctx.stem, struct_name)
                    ctx.add_node(struct_nid, struct_name, line)
                    ctx.add_edge(ctx.file_nid, struct_nid, "contains", line)
                    for child in value_node.children:
                        walk(child, parent_struct_nid=struct_nid)
                return

            if value_node and value_node.type in ("enum_declaration", "union_declaration"):
                if name_node:
                    type_name = _read_text(name_node, source)
                    line = node.start_point[0] + 1
                    type_nid = _make_id(ctx.stem, type_name)
                    ctx.add_node(type_nid, type_name, line)
                    ctx.add_edge(ctx.file_nid, type_nid, "contains", line)
                return

            if value_node and value_node.type in ("builtin_function", "field_expression"):
                _extract_import(node)
            return

        for child in node.children:
            walk(child, parent_struct_nid)

    walk(root)

    def walk_calls(node, caller_nid: str, label_to_nid: dict, seen_call_pairs: set) -> None:
        if node.type == "function_declaration":
            return
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn:
                callee = _read_text(fn, source).split(".")[-1]
                tgt_nid = next((n["id"] for n in ctx.nodes if n["label"] in
                                (f"{callee}()", f".{callee}()")), None)
                if tgt_nid and tgt_nid != caller_nid:
                    pair = (caller_nid, tgt_nid)
                    if pair not in seen_call_pairs:
                        seen_call_pairs.add(pair)
                        ctx.add_edge(caller_nid, tgt_nid, "calls",
                                     node.start_point[0] + 1,
                                     confidence="INFERRED", weight=0.8)
        for child in node.children:
            walk_calls(child, caller_nid, label_to_nid, seen_call_pairs)

    ctx.run_call_graph_pass(walk_calls)
    return ctx.finalize()
