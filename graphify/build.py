# assemble node+edge dicts into a NetworkX graph, preserving edge direction
#
# Node deduplication — three layers:
#
# 1. Within a file (AST): each extractor tracks a `seen_ids` set. A node ID is
#    emitted at most once per file, so duplicate class/function definitions in
#    the same source file are collapsed to the first occurrence.
#
# 2. Between files (build): NetworkX G.add_node() is idempotent — calling it
#    twice with the same ID overwrites the attributes with the second call's
#    values. Nodes are added in extraction order (AST first, then semantic),
#    so if the same entity is extracted by both passes the semantic node
#    silently overwrites the AST node. This is intentional: semantic nodes
#    carry richer labels and cross-file context, while AST nodes have precise
#    source_location. If you need to change the priority, reorder extractions
#    passed to build().
#
# 3. Semantic merge (skill): before calling build(), the skill merges cached
#    and new semantic results using an explicit `seen` set keyed on node["id"],
#    so duplicates across cache hits and new extractions are resolved there
#    before any graph construction happens.
#
from __future__ import annotations
import sys
import networkx as nx
from .align import align_nodes, canonical_label, canonicalize, merge_attributes
from .validate import validate_extraction


def build_from_json(extraction: dict, *, directed: bool = False) -> nx.Graph:
    """Build a NetworkX graph from an extraction dict.

    directed=True produces a DiGraph that preserves edge direction (source→target).
    directed=False (default) produces an undirected Graph for backward compatibility.
    """
    errors = validate_extraction(extraction)
    # Dangling edges (stdlib/external imports) are expected - only warn about real schema errors.
    real_errors = [e for e in errors if "does not match any node id" not in e]
    if real_errors:
        print(f"[graphify] Extraction warning ({len(real_errors)} issues): {real_errors[0]}", file=sys.stderr)
    G: nx.Graph = nx.DiGraph() if directed else nx.Graph()
    id_map: dict[str, str] = {}
    for node in extraction.get("nodes", []):
        label = str(node.get("label") or node.get("id") or "")
        identity_label = canonical_label(label)
        canonical_id = node.get("canonical_id") or canonicalize(label)
        if identity_label:
            canonical_id = node.get("canonical_id") or canonicalize(identity_label)
        if not canonical_id:
            canonical_id = str(node["id"])
        id_map[str(node["id"])] = canonical_id
        node_attrs = {k: v for k, v in node.items() if k != "id"}
        node_attrs["canonical_id"] = canonical_id
        node_attrs["aliases"] = list(dict.fromkeys([*(node.get("aliases", []) or []), label]))
        node_attrs["raw_ids"] = list(dict.fromkeys([*(node.get("raw_ids", []) or []), str(node["id"])]))
        if canonical_id in G:
            merge_attributes(G.nodes[canonical_id], {"id": node["id"], **node_attrs})
        else:
            G.add_node(canonical_id, **node_attrs)
    node_set = set(G.nodes())
    for edge in extraction.get("edges", []):
        src = id_map.get(str(edge["source"]))
        tgt = id_map.get(str(edge["target"]))
        if src not in node_set or tgt not in node_set:
            continue  # skip edges to external/stdlib nodes - expected, not an error
        attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
        # Preserve original edge direction - undirected graphs lose it otherwise,
        # causing display functions to show edges backwards.
        attrs["_src"] = src
        attrs["_tgt"] = tgt
        G.add_edge(src, tgt, **attrs)
    hyperedges = extraction.get("hyperedges", [])
    if hyperedges:
        remapped_hyperedges = []
        for hyperedge in hyperedges:
            remapped_hyperedge = dict(hyperedge)
            remapped_hyperedge["nodes"] = [
                id_map[node_id]
                for node_id in hyperedge.get("nodes", [])
                if str(node_id) in id_map
            ]
            remapped_hyperedges.append(remapped_hyperedge)
        G.graph["hyperedges"] = remapped_hyperedges
    align_nodes(G)
    return G


def build(extractions: list[dict], *, directed: bool = False) -> nx.Graph:
    """Merge multiple extraction results into one graph.

    directed=True produces a DiGraph that preserves edge direction (source→target).
    directed=False (default) produces an undirected Graph for backward compatibility.

    Extractions are merged in order. For nodes with the same ID, the last
    extraction's attributes win (NetworkX add_node overwrites). Pass AST
    results before semantic results so semantic labels take precedence, or
    reverse the order if you prefer AST source_location precision to win.
    """
    combined: dict = {"nodes": [], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0}
    for ext in extractions:
        combined["nodes"].extend(ext.get("nodes", []))
        combined["edges"].extend(ext.get("edges", []))
        combined["hyperedges"].extend(ext.get("hyperedges", []))
        combined["input_tokens"] += ext.get("input_tokens", 0)
        combined["output_tokens"] += ext.get("output_tokens", 0)
    return build_from_json(combined, directed=directed)
