"""Canonical identity, entity resolution, and semantic↔code linking."""
from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
import re

import networkx as nx

from .detect import CODE_EXTENSIONS, DOC_EXTENSIONS, IMAGE_EXTENSIONS, PAPER_EXTENSIONS


_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ACRONYM_BOUNDARY_RE = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_PAREN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
_PAREN_CONTENT_RE = re.compile(r"\(([^)]*)\)")


def normalize_identifier(value: str) -> str:
    """Normalize identifiers into a tokenized lowercase form."""
    if not value:
        return ""
    value = value.replace("_", " ")
    value = _ACRONYM_BOUNDARY_RE.sub(" ", value)
    value = _CAMEL_BOUNDARY_RE.sub(" ", value)
    value = _NON_ALNUM_RE.sub(" ", value.lower())
    return " ".join(part for part in value.split() if part)


def canonicalize(label: str) -> str:
    return (
        (label or "")
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
        .strip()
    )


def _source_category(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in CODE_EXTENSIONS:
        return "code"
    if suffix in PAPER_EXTENSIONS:
        return "paper"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in DOC_EXTENSIONS:
        return "document"
    return ""


def _is_code_node(data: dict) -> bool:
    source_category = _source_category(str(data.get("source_file", "")))
    return source_category == "code" or data.get("file_type") == "code"


def _is_semantic_node(data: dict) -> bool:
    source_category = _source_category(str(data.get("source_file", "")))
    if source_category in {"document", "paper", "image"}:
        return True
    return data.get("file_type") in {"document", "concept", "paper", "image", "rationale"}


def _strip_parenthetical_suffix(value: str) -> str:
    return _PAREN_SUFFIX_RE.sub("", value or "").strip()


def canonical_label(label: str) -> str:
    stripped = _strip_parenthetical_suffix(label or "")
    return stripped or (label or "")


def _parenthetical_aliases(value: str) -> list[str]:
    aliases: list[str] = []
    for match in _PAREN_CONTENT_RE.findall(value or ""):
        text = match.strip()
        if not text:
            continue
        aliases.append(text)
        for piece in re.split(r",|;|\band\b", text):
            piece = piece.strip()
            if piece:
                aliases.append(piece)
    return aliases


def _alias_values(data: dict) -> list[str]:
    values: list[str] = []
    label = str(data.get("label") or "").strip()
    if label:
        values.append(label)
        stripped = _strip_parenthetical_suffix(label)
        if stripped and stripped != label:
            values.append(stripped)
        values.extend(_parenthetical_aliases(label))
    for alias in data.get("aliases", []) or []:
        alias = str(alias).strip()
        if alias:
            values.append(alias)
            stripped = _strip_parenthetical_suffix(alias)
            if stripped and stripped != alias:
                values.append(stripped)
            values.extend(_parenthetical_aliases(alias))
    for raw_id in data.get("raw_ids", []) or []:
        raw_id = str(raw_id).strip()
        if raw_id:
            values.append(raw_id)
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _identity_alias_values(data: dict) -> list[str]:
    values: list[str] = []
    label = str(data.get("label") or "").strip()
    if label:
        values.append(label)
        stripped = _strip_parenthetical_suffix(label)
        if stripped and stripped != label:
            values.append(stripped)
    for alias in data.get("aliases", []) or []:
        alias = str(alias).strip()
        if alias:
            values.append(alias)
            stripped = _strip_parenthetical_suffix(alias)
            if stripped and stripped != alias:
                values.append(stripped)
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def similarity(n1: dict, n2: dict) -> float:
    best = 0.0
    for left in _alias_values(n1):
        for right in _alias_values(n2):
            l1 = canonicalize(left)
            l2 = canonicalize(right)
            if not l1 or not l2:
                continue
            if l1 == l2:
                return 1.0
            best = max(best, SequenceMatcher(None, l1, l2).ratio())
    return best


def _identity_similarity(n1: dict, n2: dict) -> float:
    best = 0.0
    for left in _identity_alias_values(n1):
        for right in _identity_alias_values(n2):
            l1 = canonicalize(left)
            l2 = canonicalize(right)
            if not l1 or not l2:
                continue
            if l1 == l2:
                return 1.0
            best = max(best, SequenceMatcher(None, l1, l2).ratio())
    return best


def _merge_unique_list(*values: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for items in values:
        for item in items:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                merged.append(text)
    return merged


def merge_attributes(existing: dict, incoming: dict) -> None:
    existing["canonical_id"] = existing.get("canonical_id") or incoming.get("canonical_id") or canonicalize(
        str(existing.get("label") or incoming.get("label") or "")
    )
    existing["aliases"] = _merge_unique_list(
        existing.get("aliases", []),
        incoming.get("aliases", []),
        [existing.get("label", ""), incoming.get("label", "")],
    )
    existing["raw_ids"] = _merge_unique_list(
        existing.get("raw_ids", []),
        incoming.get("raw_ids", []),
        [incoming.get("id", "")],
    )
    if len(str(incoming.get("label", ""))) > len(str(existing.get("label", ""))):
        existing["label"] = incoming["label"]
    for key, value in incoming.items():
        if key in {"aliases", "raw_ids", "canonical_id", "id"}:
            continue
        if key not in existing or existing[key] in ("", None):
            existing[key] = value


def merge_nodes(graph: nx.Graph, keep_id: str, drop_id: str) -> str:
    if keep_id == drop_id or keep_id not in graph or drop_id not in graph:
        return keep_id

    keep_data = graph.nodes[keep_id]
    drop_data = graph.nodes[drop_id]
    merge_attributes(keep_data, drop_data)

    if graph.is_directed():
        for src, _, attrs in list(graph.in_edges(drop_id, data=True)):
            if src == keep_id:
                continue
            if graph.has_edge(src, keep_id):
                graph.edges[src, keep_id].update({k: v for k, v in attrs.items() if k not in {"_src", "_tgt"}})
            else:
                new_attrs = dict(attrs)
                new_attrs["_src"] = src
                new_attrs["_tgt"] = keep_id
                graph.add_edge(src, keep_id, **new_attrs)
        for _, tgt, attrs in list(graph.out_edges(drop_id, data=True)):
            if tgt == keep_id:
                continue
            if graph.has_edge(keep_id, tgt):
                graph.edges[keep_id, tgt].update({k: v for k, v in attrs.items() if k not in {"_src", "_tgt"}})
            else:
                new_attrs = dict(attrs)
                new_attrs["_src"] = keep_id
                new_attrs["_tgt"] = tgt
                graph.add_edge(keep_id, tgt, **new_attrs)
    else:
        for neighbor, attrs in list(graph[drop_id].items()):
            if neighbor == keep_id:
                continue
            if graph.has_edge(keep_id, neighbor):
                graph.edges[keep_id, neighbor].update(attrs)
            else:
                graph.add_edge(keep_id, neighbor, **dict(attrs))

    graph.remove_node(drop_id)
    return keep_id


def resolve_entities(graph: nx.Graph) -> nx.Graph:
    changed = True
    while changed:
        changed = False
        nodes = list(graph.nodes(data=True))
        for index, (id1, n1) in enumerate(nodes):
            if id1 not in graph:
                continue
            for id2, n2 in nodes[index + 1:]:
                if id2 not in graph or id1 == id2:
                    continue
                score = _identity_similarity(n1, n2)
                if score > 0.85:
                    merge_nodes(graph, id1, id2)
                    changed = True
                    break
            if changed:
                break
    return graph


def tokens(text: str) -> set[str]:
    """Extract lowercase alphabetic tokens from text for matching."""
    return set(re.findall(r"[a-zA-Z]+", text.lower()))


def _infer_entity_type(node_data: dict) -> str | None:
    """Infer entity type (function, method, class) from label and context.
    
    Heuristics:
    - Label ends with "()": function or method
    - Label starts with ".": method
    - Doesn't end with "()": likely a class or type
    """
    label = str(node_data.get("label", "")).strip()
    if not label:
        return None
    
    # Already has type set
    if node_data.get("type"):
        return node_data["type"]
    
    # Method: starts with dot
    if label.startswith("."):
        return "method"
    
    # Function/method: ends with ()
    if label.endswith("()"):
        # Could be function or method - check if it has a parent class
        return "function"  # Default to function, will be updated if nested
    
    # Default: might be a class, struct, enum, etc.
    return None


def mark_entity_types(graph: nx.Graph) -> nx.Graph:
    """Add or infer entity types for code nodes."""
    for node_id, node_data in graph.nodes(data=True):
        if not _is_code_node(node_data):
            continue
        
        # Skip if already marked
        if node_data.get("type"):
            continue
        
        entity_type = _infer_entity_type(node_data)
        if entity_type:
            node_data["type"] = entity_type
    
    return graph


def link_code_to_concepts(graph: nx.Graph) -> nx.Graph:
    """Link fine-grained code entities (functions, classes) to semantic concepts.
    
    Matches on:
    1. High string similarity (>0.75)
    2. Token overlap (any token in code label appears in concept label)
    """
    # Find code nodes that look like entities (functions, classes, etc.)
    code_nodes = []
    for n, d in graph.nodes(data=True):
        if not _is_code_node(d):
            continue
        label = str(d.get("label", "")).strip()
        # Skip file-level nodes and module-level nodes
        if label.endswith(".py") or label.endswith(".ts") or not label:
            continue
        # Only process if it has type hint or looks like a function/class
        if d.get("type") in ("function", "method", "class") or label.endswith("()") or not label.endswith(")"):
            code_nodes.append((n, d))
    
    concept_nodes = [
        (n, d) for n, d in graph.nodes(data=True)
        if _is_semantic_node(d)
    ]
    
    for cid, cdata in code_nodes:
        c_label = str(cdata.get("canonical_id", "")).lower()
        if not c_label:
            c_label = str(cdata.get("label", "")).lower().strip("().")
        
        if not c_label or len(c_label) < 2:
            continue
        
        c_tokens = tokens(c_label)
        
        for sid, sdata in concept_nodes:
            if cid == sid or graph.has_edge(cid, sid):
                continue
            
            s_label = str(sdata.get("canonical_id", "")).lower()
            if not s_label:
                s_label = str(sdata.get("label", "")).lower()
            
            if not s_label or len(s_label) < 2:
                continue
            
            s_tokens = tokens(s_label)
            
            # String similarity check
            score = SequenceMatcher(None, c_label, s_label).ratio()
            
            # Token overlap bonus
            if c_tokens & s_tokens:
                score += 0.2
                score = min(score, 1.0)
            
            # Link if high similarity or token overlap
            if score > 0.75 or bool(c_tokens & s_tokens):
                graph.add_edge(
                    cid,
                    sid,
                    relation="implements",
                    confidence="INFERRED",
                    confidence_score=round(score, 3),
                    source_file=cdata.get("source_file") or sdata.get("source_file", ""),
                    source_location=cdata.get("source_location"),
                    weight=round(score, 3),
                    _src=cid,
                    _tgt=sid,
                )
    
    return graph


def link_concepts(graph: nx.Graph) -> nx.Graph:
    """Link semantic concepts to each other based on similarity.
    
    Concepts with >0.8 similarity are connected with "related_to" edges.
    """
    concepts = [
        (n, d) for n, d in graph.nodes(data=True)
        if _is_semantic_node(d)
    ]
    
    for i, (id1, n1) in enumerate(concepts):
        s1 = str(n1.get("canonical_id", "")).lower() or str(n1.get("label", "")).lower()
        if not s1:
            continue
        
        for id2, n2 in concepts[i + 1:]:
            if id1 == id2 or graph.has_edge(id1, id2) or graph.has_edge(id2, id1):
                continue
            
            s2 = str(n2.get("canonical_id", "")).lower() or str(n2.get("label", "")).lower()
            if not s2:
                continue
            
            score = SequenceMatcher(None, s1, s2).ratio()
            
            if score > 0.8:
                graph.add_edge(
                    id1,
                    id2,
                    relation="related_to",
                    confidence="INFERRED",
                    confidence_score=round(score, 3),
                    source_file=n1.get("source_file") or n2.get("source_file", ""),
                    weight=round(score, 3),
                    _src=id1,
                    _tgt=id2,
                )
    
    return graph


def link_semantic_to_code(graph: nx.Graph) -> nx.Graph:
    code_nodes = [node_id for node_id, data in graph.nodes(data=True) if _is_code_node(data)]
    semantic_nodes = [node_id for node_id, data in graph.nodes(data=True) if _is_semantic_node(data)]

    for code_id in code_nodes:
        for semantic_id in semantic_nodes:
            if code_id == semantic_id or graph.has_edge(code_id, semantic_id):
                continue
            score = similarity(graph.nodes[code_id], graph.nodes[semantic_id])
            if score > 0.7:
                graph.add_edge(
                    code_id,
                    semantic_id,
                    relation="implements",
                    type="implements",
                    confidence="INFERRED",
                    confidence_score=round(score, 3),
                    source_file=graph.nodes[code_id].get("source_file") or graph.nodes[semantic_id].get("source_file", ""),
                    source_location=graph.nodes[code_id].get("source_location"),
                    weight=round(score, 3),
                    aligned_by="semantic_code_linking",
                    _src=code_id,
                    _tgt=semantic_id,
                )
    return graph


def align_nodes(graph: nx.Graph) -> nx.Graph:
    mark_entity_types(graph)
    resolve_entities(graph)
    link_semantic_to_code(graph)
    link_code_to_concepts(graph)
    link_concepts(graph)
    return graph
