"""Generic AST extractor driven by LanguageConfig."""
from __future__ import annotations

from pathlib import Path

from ._base import (
    ExtractionContext, LanguageConfig,
    _find_body, _make_id, _read_text,
    init_parser, make_error_result,
)
from ._configs import (
    _js_extra_walk, _csharp_extra_walk, _swift_extra_walk,
)


def _extract_generic(path: Path, config: LanguageConfig) -> dict:
    """Generic AST extractor driven by LanguageConfig."""
    parser, language, error = init_parser(config)
    if error:
        return make_error_result(error)

    try:
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return make_error_result(str(e))

    ctx = ExtractionContext(path, source)

    def walk(node, parent_class_nid: str | None = None) -> None:
        t = node.type

        # Import types
        if t in config.import_types:
            if config.import_handler:
                config.import_handler(node, source, ctx.file_nid, ctx.stem, ctx.edges, ctx.str_path)
            return

        # Class types
        if t in config.class_types:
            name_node = node.child_by_field_name(config.name_field)
            if name_node is None:
                for child in node.children:
                    if child.type in config.name_fallback_child_types:
                        name_node = child
                        break
            if not name_node:
                return
            class_name = _read_text(name_node, source)
            class_nid = _make_id(ctx.stem, class_name)
            line = node.start_point[0] + 1
            ctx.add_node(class_nid, class_name, line)
            ctx.add_edge(ctx.file_nid, class_nid, "contains", line)

            # Python-specific: inheritance
            if config.ts_module == "tree_sitter_python":
                args = node.child_by_field_name("superclasses")
                if args:
                    for arg in args.children:
                        if arg.type == "identifier":
                            base = _read_text(arg, source)
                            base_nid = _make_id(ctx.stem, base)
                            if base_nid not in ctx.seen_ids:
                                base_nid = _make_id(base)
                                if base_nid not in ctx.seen_ids:
                                    ctx.nodes.append({
                                        "id": base_nid,
                                        "label": base,
                                        "file_type": "code",
                                        "source_file": "",
                                        "source_location": "",
                                    })
                                    ctx.seen_ids.add(base_nid)
                            ctx.add_edge(class_nid, base_nid, "inherits", line)

            # Swift-specific: conformance / inheritance
            if config.ts_module == "tree_sitter_swift":
                for child in node.children:
                    if child.type == "inheritance_specifier":
                        for sub in child.children:
                            if sub.type in ("user_type", "type_identifier"):
                                base = _read_text(sub, source)
                                base_nid = _make_id(ctx.stem, base)
                                if base_nid not in ctx.seen_ids:
                                    base_nid = _make_id(base)
                                    if base_nid not in ctx.seen_ids:
                                        ctx.nodes.append({
                                            "id": base_nid,
                                            "label": base,
                                            "file_type": "code",
                                            "source_file": "",
                                            "source_location": "",
                                        })
                                        ctx.seen_ids.add(base_nid)
                                ctx.add_edge(class_nid, base_nid, "inherits", line)

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
                                base_nid = _make_id(ctx.stem, base)
                                if base_nid not in ctx.seen_ids:
                                    base_nid = _make_id(base)
                                    if base_nid not in ctx.seen_ids:
                                        ctx.nodes.append({
                                            "id": base_nid,
                                            "label": base,
                                            "file_type": "code",
                                            "source_file": "",
                                            "source_location": "",
                                        })
                                        ctx.seen_ids.add(base_nid)
                                ctx.add_edge(class_nid, base_nid, "inherits", line)

            body = _find_body(node, config)
            if body:
                for child in body.children:
                    walk(child, parent_class_nid=class_nid)
            return

        # Function types
        if t in config.function_types:
            if t == "deinit_declaration":
                func_name: str | None = "deinit"
            elif t == "subscript_declaration":
                func_name = "subscript"
            elif config.resolve_function_name_fn is not None:
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
                ctx.add_node(func_nid, f".{func_name}()", line)
                ctx.add_edge(parent_class_nid, func_nid, "method", line)
            else:
                func_nid = _make_id(ctx.stem, func_name)
                ctx.add_node(func_nid, f"{func_name}()", line)
                ctx.add_edge(ctx.file_nid, func_nid, "contains", line)

            body = _find_body(node, config)
            if body:
                ctx.function_bodies.append((func_nid, body))
            return

        # JS/TS arrow functions and C# namespaces — language-specific extra handling
        if config.ts_module in ("tree_sitter_javascript", "tree_sitter_typescript"):
            if _js_extra_walk(node, source, ctx.file_nid, ctx.stem, ctx.str_path,
                              ctx.nodes, ctx.edges, ctx.seen_ids, ctx.function_bodies,
                              parent_class_nid, ctx.add_node, ctx.add_edge):
                return

        if config.ts_module == "tree_sitter_c_sharp":
            if _csharp_extra_walk(node, source, ctx.file_nid, ctx.stem, ctx.str_path,
                                   ctx.nodes, ctx.edges, ctx.seen_ids, ctx.function_bodies,
                                   parent_class_nid, ctx.add_node, ctx.add_edge, walk):
                return

        if config.ts_module == "tree_sitter_swift":
            if _swift_extra_walk(node, source, ctx.file_nid, ctx.stem, ctx.str_path,
                                  ctx.nodes, ctx.edges, ctx.seen_ids, ctx.function_bodies,
                                  parent_class_nid, ctx.add_node, ctx.add_edge):
                return

        # Default: recurse
        for child in node.children:
            walk(child, parent_class_nid=None)

    walk(root)

    # ── Call-graph pass ──────────────────────────────────────────────────────
    def walk_calls(node, caller_nid: str, label_to_nid: dict, seen_call_pairs: set) -> None:
        if node.type in config.function_boundary_types:
            return

        if node.type in config.call_types:
            callee_name: str | None = None

            if config.ts_module == "tree_sitter_swift":
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
                if node.type == "function_call_expression":
                    func_node = node.child_by_field_name("function")
                    if func_node:
                        callee_name = _read_text(func_node, source)
                else:
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        callee_name = _read_text(name_node, source)
            elif config.ts_module == "tree_sitter_cpp":
                func_node = node.child_by_field_name(config.call_function_field) if config.call_function_field else None
                if func_node:
                    if func_node.type == "identifier":
                        callee_name = _read_text(func_node, source)
                    elif func_node.type in ("field_expression", "qualified_identifier"):
                        name = func_node.child_by_field_name("field") or func_node.child_by_field_name("name")
                        if name:
                            callee_name = _read_text(name, source)
            else:
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
                        callee_name = _read_text(func_node, source)

            if callee_name:
                tgt_nid = label_to_nid.get(callee_name.lower())
                if tgt_nid and tgt_nid != caller_nid:
                    pair = (caller_nid, tgt_nid)
                    if pair not in seen_call_pairs:
                        seen_call_pairs.add(pair)
                        line = node.start_point[0] + 1
                        ctx.edges.append({
                            "source": caller_nid,
                            "target": tgt_nid,
                            "relation": "calls",
                            "confidence": "INFERRED",
                            "source_file": ctx.str_path,
                            "source_location": f"L{line}",
                            "weight": 0.8,
                        })

        for child in node.children:
            walk_calls(child, caller_nid, label_to_nid, seen_call_pairs)

    ctx.run_call_graph_pass(walk_calls)
    return ctx.finalize()
