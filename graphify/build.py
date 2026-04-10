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
from .validate import validate_extraction


def edge_direction(u: str, v: str, data: dict) -> tuple[str, str]:
    """Return (source, target) for an edge, honoring the extractor's
    original direction stashed in the _src/_tgt attrs by build_from_json.

    NetworkX undirected graphs (nx.Graph) store each edge once and pick
    an arbitrary endpoint as "first" in adjacency iteration. That means
    the (u, v) tuple yielded by G.edges() is NOT guaranteed to match the
    direction the extractor produced. Export and display code that cares
    about direction (JSON graph files, Cypher, HTML visualizations,
    report arrow rendering) must route every edge through this helper.
    """
    return data.get("_src", u), data.get("_tgt", v)


def build_from_json(extraction: dict) -> nx.Graph:
    errors = validate_extraction(extraction)
    # Dangling edges (stdlib/external imports) are expected - only warn about real schema errors.
    real_errors = [e for e in errors if "does not match any node id" not in e]
    if real_errors:
        print(f"[graphify] Extraction warning ({len(real_errors)} issues): {real_errors[0]}", file=sys.stderr)
    G = nx.Graph()
    for node in extraction.get("nodes", []):
        G.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
    node_set = set(G.nodes())
    for edge in extraction.get("edges", []):
        src, tgt = edge["source"], edge["target"]
        if src not in node_set or tgt not in node_set:
            continue  # skip edges to external/stdlib nodes - expected, not an error
        attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
        # Preserve original edge direction — undirected graphs lose it
        # otherwise. Display/export sites must read these via the
        # edge_direction() helper, not rely on the (u, v) returned by
        # G.edges(), which NetworkX may have stored in the opposite order.
        attrs["_src"] = src
        attrs["_tgt"] = tgt
        G.add_edge(src, tgt, **attrs)
    hyperedges = extraction.get("hyperedges", [])
    if hyperedges:
        G.graph["hyperedges"] = hyperedges
    return G


def build(extractions: list[dict]) -> nx.Graph:
    """Merge multiple extraction results into one graph.

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
    return build_from_json(combined)
