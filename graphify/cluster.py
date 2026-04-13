"""Community detection on NetworkX graphs. Uses Leiden (graspologic) if available, falls back to Louvain (networkx). Splits oversized communities. Returns cohesion scores.

Hierarchical clustering: two-pass Leiden produces L0 topics → L1 communities → L2 nodes.
"""
from __future__ import annotations
import contextlib
import inspect
import io
import sys
from dataclasses import dataclass, field
import networkx as nx


def _suppress_output():
    """Context manager to suppress stdout/stderr during library calls.

    graspologic's leiden() emits ANSI escape sequences (progress bars,
    colored warnings) that corrupt PowerShell 5.1's scroll buffer on
    Windows (see issue #19). Redirecting stdout/stderr to devnull during
    the call prevents this without losing any graphify output.
    """
    return contextlib.redirect_stdout(io.StringIO())


def _partition(G: nx.Graph) -> dict[str, int]:
    """Run community detection. Returns {node_id: community_id}.

    Tries Leiden (graspologic) first — best quality.
    Falls back to Louvain (built into networkx) if graspologic is not installed.

    Output from graspologic is suppressed to prevent ANSI escape codes
    from corrupting terminal scroll buffers on Windows PowerShell 5.1.
    """
    try:
        from graspologic.partition import leiden
        # Suppress graspologic output to prevent ANSI escape codes from
        # corrupting PowerShell 5.1 scroll buffer (issue #19)
        old_stderr = sys.stderr
        try:
            sys.stderr = io.StringIO()
            with _suppress_output():
                result = leiden(G)
        finally:
            sys.stderr = old_stderr
        return result
    except ImportError:
        pass

    # Fallback: networkx louvain (available since networkx 2.7).
    # Inspect kwargs to stay compatible across NetworkX versions — max_level
    # was added in a later release and prevents hangs on large sparse graphs.
    kwargs: dict = {"seed": 42, "threshold": 1e-4}
    if "max_level" in inspect.signature(nx.community.louvain_communities).parameters:
        kwargs["max_level"] = 10
    communities = nx.community.louvain_communities(G, **kwargs)
    return {node: cid for cid, nodes in enumerate(communities) for node in nodes}


_MAX_COMMUNITY_FRACTION = 0.25   # communities larger than 25% of graph get split
_MIN_SPLIT_SIZE = 10             # only split if community has at least this many nodes


def cluster(G: nx.Graph) -> dict[int, list[str]]:
    """Run Leiden community detection. Returns {community_id: [node_ids]}.

    Community IDs are stable across runs: 0 = largest community after splitting.
    Oversized communities (> 25% of graph nodes, min 10) are split by running
    a second Leiden pass on the subgraph.

    Accepts directed or undirected graphs. DiGraphs are converted to undirected
    internally since Louvain/Leiden require undirected input.
    """
    if G.number_of_nodes() == 0:
        return {}
    if G.is_directed():
        G = G.to_undirected()
    if G.number_of_edges() == 0:
        return {i: [n] for i, n in enumerate(sorted(G.nodes))}

    # Leiden warns and drops isolates - handle them separately
    isolates = [n for n in G.nodes() if G.degree(n) == 0]
    connected_nodes = [n for n in G.nodes() if G.degree(n) > 0]
    connected = G.subgraph(connected_nodes)

    raw: dict[int, list[str]] = {}
    if connected.number_of_nodes() > 0:
        partition = _partition(connected)
        for node, cid in partition.items():
            raw.setdefault(cid, []).append(node)

    # Each isolate becomes its own single-node community
    next_cid = max(raw.keys(), default=-1) + 1
    for node in isolates:
        raw[next_cid] = [node]
        next_cid += 1

    # Split oversized communities
    max_size = max(_MIN_SPLIT_SIZE, int(G.number_of_nodes() * _MAX_COMMUNITY_FRACTION))
    final_communities: list[list[str]] = []
    for nodes in raw.values():
        if len(nodes) > max_size:
            final_communities.extend(_split_community(G, nodes))
        else:
            final_communities.append(nodes)

    # Re-index by size descending for deterministic ordering
    final_communities.sort(key=len, reverse=True)
    return {i: sorted(nodes) for i, nodes in enumerate(final_communities)}


def _split_community(G: nx.Graph, nodes: list[str]) -> list[list[str]]:
    """Run a second Leiden pass on a community subgraph to split it further."""
    subgraph = G.subgraph(nodes)
    if subgraph.number_of_edges() == 0:
        # No edges - split into individual nodes
        return [[n] for n in sorted(nodes)]
    try:
        sub_partition = _partition(subgraph)
        sub_communities: dict[int, list[str]] = {}
        for node, cid in sub_partition.items():
            sub_communities.setdefault(cid, []).append(node)
        if len(sub_communities) <= 1:
            return [sorted(nodes)]
        return [sorted(v) for v in sub_communities.values()]
    except Exception:
        return [sorted(nodes)]


def cohesion_score(G: nx.Graph, community_nodes: list[str]) -> float:
    """Ratio of actual intra-community edges to maximum possible."""
    n = len(community_nodes)
    if n <= 1:
        return 1.0
    subgraph = G.subgraph(community_nodes)
    actual = subgraph.number_of_edges()
    possible = n * (n - 1) / 2
    return round(actual / possible, 2) if possible > 0 else 0.0


def score_all(G: nx.Graph, communities: dict[int, list[str]]) -> dict[int, float]:
    return {cid: cohesion_score(G, nodes) for cid, nodes in communities.items()}


# ---------------------------------------------------------------------------
# Hierarchical clustering: L0 topics → L1 communities → L2 nodes
# ---------------------------------------------------------------------------

@dataclass
class HierarchicalCommunities:
    """Three-level hierarchy produced by two-pass Leiden.

    L1 communities are identical to what ``cluster()`` returns, so all
    existing code that accepts ``dict[int, list[str]]`` can use
    ``hc.l1_communities`` directly with zero changes.

    L0 topics group related L1 communities into coarser themes by running
    Leiden on the contracted community-level graph.
    """

    # L1: concept clusters (= existing flat communities)
    l1_communities: dict[int, list[str]] = field(default_factory=dict)
    # L0: topic groups (each topic contains a list of L1 community IDs)
    l0_topics: dict[int, list[int]] = field(default_factory=dict)
    # Reverse mapping: community → topic
    l1_to_l0: dict[int, int] = field(default_factory=dict)
    # Labels (populated later by the user / LLM)
    l0_labels: dict[int, str] = field(default_factory=dict)
    l1_labels: dict[int, str] = field(default_factory=dict)
    # Cohesion scores
    l0_cohesion: dict[int, float] = field(default_factory=dict)
    l1_cohesion: dict[int, float] = field(default_factory=dict)


def _build_contracted_graph(
    G: nx.Graph,
    communities: dict[int, list[str]],
) -> nx.Graph:
    """Contract nodes by community into a weighted super-graph.

    Each L1 community becomes a single node (keyed by its community ID as a
    string, since ``_partition`` expects string node IDs).  Edge weight
    between two super-nodes = number of original cross-community edges.
    """
    node_to_cid: dict[str, int] = {}
    for cid, nodes in communities.items():
        for n in nodes:
            node_to_cid[n] = cid

    edge_weights: dict[tuple[int, int], int] = {}
    for u, v in G.edges():
        cu = node_to_cid.get(u)
        cv = node_to_cid.get(v)
        if cu is None or cv is None or cu == cv:
            continue
        key = (min(cu, cv), max(cu, cv))
        edge_weights[key] = edge_weights.get(key, 0) + 1

    G_c = nx.Graph()
    for cid in communities:
        G_c.add_node(str(cid))
    for (cu, cv), w in edge_weights.items():
        G_c.add_edge(str(cu), str(cv), weight=w)
    return G_c


_MIN_COMMUNITIES_FOR_L0 = 4  # need at least this many L1 communities to form L0


def hierarchical_cluster(G: nx.Graph) -> HierarchicalCommunities:
    """Two-pass Leiden producing L0 topics → L1 communities → L2 nodes.

    Pass 1 (existing): Leiden on the original graph → L1 communities.
    Pass 2 (new):      Contract L1 communities into super-nodes, then run
                        Leiden on the contracted graph → L0 topics.

    If fewer than ``_MIN_COMMUNITIES_FOR_L0`` L1 communities exist, all
    communities are placed under a single L0 topic (no second pass).
    """
    # --- Pass 1: L1 communities (unchanged) ---
    l1_communities = cluster(G)
    l1_cohesion = score_all(G, l1_communities)

    hc = HierarchicalCommunities(
        l1_communities=l1_communities,
        l1_cohesion=l1_cohesion,
    )

    # --- Pass 2: L0 topics via contracted graph ---
    if len(l1_communities) < _MIN_COMMUNITIES_FOR_L0:
        # Too few communities – single topic containing everything
        hc.l0_topics = {0: list(l1_communities.keys())}
        hc.l1_to_l0 = {cid: 0 for cid in l1_communities}
        hc.l0_labels = {0: "All"}
        hc.l0_cohesion = {0: 1.0}
        hc.l1_labels = {cid: f"Community {cid}" for cid in l1_communities}
        return hc

    G_undirected = G.to_undirected() if G.is_directed() else G
    G_contracted = _build_contracted_graph(G_undirected, l1_communities)

    # Run community detection on contracted graph
    if G_contracted.number_of_edges() == 0:
        # No inter-community edges: each community is its own topic
        hc.l0_topics = {i: [cid] for i, cid in enumerate(sorted(l1_communities.keys()))}
        hc.l1_to_l0 = {cid: i for i, cid in enumerate(sorted(l1_communities.keys()))}
    else:
        l0_partition = _partition(G_contracted)  # {str(cid): topic_id}
        raw_topics: dict[int, list[int]] = {}
        for cid_str, tid in l0_partition.items():
            raw_topics.setdefault(tid, []).append(int(cid_str))

        # Re-index topics by total node count descending
        topic_sizes = []
        for tid, cids in raw_topics.items():
            total_nodes = sum(len(l1_communities[c]) for c in cids)
            topic_sizes.append((total_nodes, tid, cids))
        topic_sizes.sort(reverse=True)

        hc.l0_topics = {}
        hc.l1_to_l0 = {}
        for new_tid, (_, _, cids) in enumerate(topic_sizes):
            hc.l0_topics[new_tid] = sorted(cids)
            for cid in cids:
                hc.l1_to_l0[cid] = new_tid

    # Compute L0 cohesion: ratio of inter-community edges within the topic
    # to maximum possible inter-community edges within the topic
    for tid, cids in hc.l0_topics.items():
        if len(cids) <= 1:
            hc.l0_cohesion[tid] = 1.0
            continue
        cid_set = set(cids)
        internal = 0
        total_possible = len(cids) * (len(cids) - 1) // 2
        for cu in cids:
            for cv in cids:
                if cu < cv and G_contracted.has_edge(str(cu), str(cv)):
                    internal += 1
        hc.l0_cohesion[tid] = round(internal / total_possible, 2) if total_possible > 0 else 0.0

    # Default labels
    hc.l0_labels = {tid: f"Topic {tid}" for tid in hc.l0_topics}
    hc.l1_labels = {cid: f"Community {cid}" for cid in l1_communities}

    return hc
