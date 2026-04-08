"""Rust language extractor (custom walk — not driven by LanguageConfig)."""
from __future__ import annotations

from pathlib import Path

from ._base import ExtractionContext, _make_id, _read_text, make_error_result


def extract_rust(path: Path) -> dict:
    """Extract functions, structs, enums, traits, impl methods, and use declarations from a .rs file."""
    try:
        import tree_sitter_rust as tsrust
        from tree_sitter import Language, Parser
    except ImportError:
        return make_error_result("tree-sitter-rust not installed")

    try:
        language = Language(tsrust.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return make_error_result(str(e))

    ctx = ExtractionContext(path, source)

    def walk(node, parent_impl_nid: str | None = None) -> None:
        t = node.type

        if t == "function_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                if parent_impl_nid:
                    func_nid = _make_id(parent_impl_nid, func_name)
                    ctx.add_node(func_nid, f".{func_name}()", line)
                    ctx.add_edge(parent_impl_nid, func_nid, "method", line)
                else:
                    func_nid = _make_id(ctx.stem, func_name)
                    ctx.add_node(func_nid, f"{func_name}()", line)
                    ctx.add_edge(ctx.file_nid, func_nid, "contains", line)
                body = node.child_by_field_name("body")
                if body:
                    ctx.function_bodies.append((func_nid, body))
            return

        if t in ("struct_item", "enum_item", "trait_item"):
            name_node = node.child_by_field_name("name")
            if name_node:
                item_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                item_nid = _make_id(ctx.stem, item_name)
                ctx.add_node(item_nid, item_name, line)
                ctx.add_edge(ctx.file_nid, item_nid, "contains", line)
            return

        if t == "impl_item":
            type_node = node.child_by_field_name("type")
            impl_nid: str | None = None
            if type_node:
                type_name = _read_text(type_node, source).strip()
                impl_nid = _make_id(ctx.stem, type_name)
                ctx.add_node(impl_nid, type_name, node.start_point[0] + 1)
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
                    ctx.add_edge(ctx.file_nid, tgt_nid, "imports_from", node.start_point[0] + 1)
            return

        for child in node.children:
            walk(child, parent_impl_nid=None)

    walk(root)

    def walk_calls(node, caller_nid: str, label_to_nid: dict, seen_call_pairs: set) -> None:
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
                        ctx.add_edge(caller_nid, tgt_nid, "calls", line,
                                     confidence="INFERRED", weight=0.8)
        for child in node.children:
            walk_calls(child, caller_nid, label_to_nid, seen_call_pairs)

    ctx.run_call_graph_pass(walk_calls)
    return ctx.finalize()
