"""Tests for hierarchical Leiden community detection."""
import networkx as nx
from graphify.cluster import hierarchical_cluster


def _make_clusterable_graph() -> nx.Graph:
    """Build a graph with clear community structure for testing."""
    G = nx.Graph()
    # Community A: tightly connected
    for i in range(5):
        for j in range(i + 1, 5):
            G.add_edge(f"a{i}", f"a{j}")
    # Community B: tightly connected
    for i in range(5):
        for j in range(i + 1, 5):
            G.add_edge(f"b{i}", f"b{j}")
    # Community C: tightly connected
    for i in range(4):
        for j in range(i + 1, 4):
            G.add_edge(f"c{i}", f"c{j}")
    # Weak bridges between communities
    G.add_edge("a0", "b0")
    G.add_edge("b0", "c0")
    return G


def test_hierarchical_returns_all_levels():
    G = _make_clusterable_graph()
    hierarchy = hierarchical_cluster(G)
    assert len(hierarchy) == 3  # default 3 resolutions
    assert 0 in hierarchy
    assert 1 in hierarchy
    assert 2 in hierarchy


def test_hierarchical_covers_all_nodes():
    G = _make_clusterable_graph()
    hierarchy = hierarchical_cluster(G)
    all_nodes = set(G.nodes)
    for level, communities in hierarchy.items():
        level_nodes = {n for nodes in communities.values() for n in nodes}
        assert level_nodes == all_nodes, f"Level {level} missing nodes: {all_nodes - level_nodes}"


def test_hierarchical_coarse_has_fewer_communities():
    """Lower resolution should produce fewer (or equal) communities than higher."""
    G = _make_clusterable_graph()
    hierarchy = hierarchical_cluster(G)
    # Level 0 (res=0.5) should have <= communities than level 2 (res=2.0)
    assert len(hierarchy[0]) <= len(hierarchy[2])


def test_hierarchical_custom_resolutions():
    G = _make_clusterable_graph()
    hierarchy = hierarchical_cluster(G, resolutions=[1.0, 3.0])
    assert len(hierarchy) == 2


def test_hierarchical_empty_graph():
    G = nx.Graph()
    hierarchy = hierarchical_cluster(G)
    assert len(hierarchy) == 3
    for level in hierarchy.values():
        assert level == {}


def test_hierarchical_no_edges():
    G = nx.Graph()
    G.add_nodes_from(["a", "b", "c"])
    hierarchy = hierarchical_cluster(G)
    for level, communities in hierarchy.items():
        # Each node should be its own community
        all_nodes = {n for nodes in communities.values() for n in nodes}
        assert all_nodes == {"a", "b", "c"}


def test_hierarchical_directed_graph():
    """DiGraphs should be handled (converted to undirected internally)."""
    G = nx.DiGraph()
    G.add_edge("a", "b")
    G.add_edge("b", "c")
    G.add_edge("c", "a")
    hierarchy = hierarchical_cluster(G)
    assert len(hierarchy) == 3
    for level, communities in hierarchy.items():
        all_nodes = {n for nodes in communities.values() for n in nodes}
        assert all_nodes == {"a", "b", "c"}


def test_hierarchical_community_ids_are_sorted_by_size():
    G = _make_clusterable_graph()
    hierarchy = hierarchical_cluster(G)
    for level, communities in hierarchy.items():
        sizes = [len(nodes) for cid, nodes in sorted(communities.items())]
        # Community 0 should be largest or tied
        if sizes:
            assert sizes[0] >= sizes[-1], f"Level {level}: community 0 not largest"
