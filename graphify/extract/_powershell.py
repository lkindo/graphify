"""PowerShell language extractor (custom walk — not driven by LanguageConfig)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ._base import ExtractionContext, _make_id, _read_text, make_error_result


def extract_powershell(path: Path) -> dict:
    """Extract functions, classes, methods, and using statements from a .ps1 file."""
    try:
        import tree_sitter_powershell as tsps
        from tree_sitter import Language, Parser
    except ImportError:
        return make_error_result("tree_sitter_powershell not installed")

    try:
        language = Language(tsps.language())
        parser = Parser(language)
        source = path.read_bytes()
        tree = parser.parse(source)
        root = tree.root_node
    except Exception as e:
        return make_error_result(str(e))

    ctx = ExtractionContext(path, source)

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
                func_nid = _make_id(ctx.stem, func_name)
                ctx.add_node(func_nid, f"{func_name}()", line)
                ctx.add_edge(ctx.file_nid, func_nid, "contains", line)
                body = _find_script_block_body(node)
                if body:
                    ctx.function_bodies.append((func_nid, body))
            return

        if t == "class_statement":
            name_node = next((c for c in node.children if c.type == "simple_name"), None)
            if name_node:
                class_name = _read_text(name_node, source)
                line = node.start_point[0] + 1
                class_nid = _make_id(ctx.stem, class_name)
                ctx.add_node(class_nid, class_name, line)
                ctx.add_edge(ctx.file_nid, class_nid, "contains", line)
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
                    ctx.add_node(method_nid, f".{method_name}()", line)
                    ctx.add_edge(parent_class_nid, method_nid, "method", line)
                else:
                    method_nid = _make_id(ctx.stem, method_name)
                    ctx.add_node(method_nid, f"{method_name}()", line)
                    ctx.add_edge(ctx.file_nid, method_nid, "contains", line)
                body = _find_script_block_body(node)
                if body:
                    ctx.function_bodies.append((method_nid, body))
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
                        ctx.add_edge(ctx.file_nid, _make_id(module_name), "imports_from",
                                     node.start_point[0] + 1)
            return

        for child in node.children:
            walk(child, parent_class_nid)

    walk(root)

    def walk_calls(node, caller_nid: str, label_to_nid: dict, seen_call_pairs: set) -> None:
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
                            ctx.add_edge(caller_nid, tgt_nid, "calls",
                                         node.start_point[0] + 1,
                                         confidence="INFERRED", weight=0.8)
        for child in node.children:
            walk_calls(child, caller_nid, label_to_nid, seen_call_pairs)

    ctx.run_call_graph_pass(walk_calls)
    return ctx.finalize()
