"""Go language extractor (custom walk — not driven by LanguageConfig)."""
from __future__ import annotations

from pathlib import Path

from ._base import ExtractionContext, _make_id, _read_text, make_error_result


def extract_go(path: Path) -> dict:
    """Extract functions, methods, type declarations, and imports from a .go file."""
    try:
        import tree_sitter_go as tsgo
        from tree_sitter import Language, Parser
    except ImportError:
        return make_error_result("tree-sitter-go not installed")

    try:
        language = Language(tsgo.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return make_error_result(str(e))

    ctx = ExtractionContext(path, source)

    def walk(node) -> None:
        t = node.type

        if t == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                func_nid = _make_id(ctx.stem, func_name)
                ctx.add_node(func_nid, f"{func_name}()", line)
                ctx.add_edge(ctx.file_nid, func_nid, "contains", line)
                body = node.child_by_field_name("body")
                if body:
                    ctx.function_bodies.append((func_nid, body))
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
                    parent_nid = _make_id(ctx.stem, receiver_type)
                    ctx.add_node(parent_nid, receiver_type, line)
                    method_nid = _make_id(parent_nid, method_name)
                    ctx.add_node(method_nid, f".{method_name}()", line)
                    ctx.add_edge(parent_nid, method_nid, "method", line)
                else:
                    method_nid = _make_id(ctx.stem, method_name)
                    ctx.add_node(method_nid, f"{method_name}()", line)
                    ctx.add_edge(ctx.file_nid, method_nid, "contains", line)
                body = node.child_by_field_name("body")
                if body:
                    ctx.function_bodies.append((method_nid, body))
            return

        if t == "type_declaration":
            for child in node.children:
                if child.type == "type_spec":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        type_name = _read_text(name_node, source)
                        line = child.start_point[0] + 1
                        type_nid = _make_id(ctx.stem, type_name)
                        ctx.add_node(type_nid, type_name, line)
                        ctx.add_edge(ctx.file_nid, type_nid, "contains", line)
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
                                ctx.add_edge(ctx.file_nid, tgt_nid, "imports_from", spec.start_point[0] + 1)
                elif child.type == "import_spec":
                    path_node = child.child_by_field_name("path")
                    if path_node:
                        raw = _read_text(path_node, source).strip('"')
                        module_name = raw.split("/")[-1]
                        tgt_nid = _make_id(module_name)
                        ctx.add_edge(ctx.file_nid, tgt_nid, "imports_from", child.start_point[0] + 1)
            return

        for child in node.children:
            walk(child)

    walk(root)

    def walk_calls(node, caller_nid: str, label_to_nid: dict, seen_call_pairs: set) -> None:
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
                        ctx.add_edge(caller_nid, tgt_nid, "calls", line,
                                     confidence="INFERRED", weight=0.8)
        for child in node.children:
            walk_calls(child, caller_nid, label_to_nid, seen_call_pairs)

    ctx.run_call_graph_pass(walk_calls)
    return ctx.finalize()
