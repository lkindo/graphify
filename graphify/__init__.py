"""graphify - extract · build · cluster · analyze · report."""

from __future__ import annotations

import inspect

try:
    from networkx.readwrite import json_graph
except ImportError:
    json_graph = None


def _patch_networkx_node_link_compat() -> None:
    """Allow both NetworkX node-link keyword styles across 3.x variants."""
    if json_graph is None:
        return
    data_params = inspect.signature(json_graph.node_link_data).parameters
    if "edges" not in data_params:
        _orig_node_link_data = json_graph.node_link_data

        def _compat_node_link_data(G, *args, **kwargs):
            if "edges" in kwargs and "link" not in kwargs:
                kwargs["link"] = kwargs.pop("edges")
            return _orig_node_link_data(G, *args, **kwargs)

        json_graph.node_link_data = _compat_node_link_data

    graph_params = inspect.signature(json_graph.node_link_graph).parameters
    if "edges" not in graph_params:
        _orig_node_link_graph = json_graph.node_link_graph

        def _compat_node_link_graph(data, *args, **kwargs):
            if "edges" in kwargs and "link" not in kwargs:
                kwargs["link"] = kwargs.pop("edges")
            return _orig_node_link_graph(data, *args, **kwargs)

        json_graph.node_link_graph = _compat_node_link_graph


_patch_networkx_node_link_compat()


def __getattr__(name):
    # Lazy imports so `graphify install` works before heavy deps are in place.
    _map = {
        "extract": ("graphify.extract", "extract"),
        "collect_files": ("graphify.extract", "collect_files"),
        "build_from_json": ("graphify.build", "build_from_json"),
        "cluster": ("graphify.cluster", "cluster"),
        "score_all": ("graphify.cluster", "score_all"),
        "cohesion_score": ("graphify.cluster", "cohesion_score"),
        "god_nodes": ("graphify.analyze", "god_nodes"),
        "surprising_connections": ("graphify.analyze", "surprising_connections"),
        "suggest_questions": ("graphify.analyze", "suggest_questions"),
        "generate": ("graphify.report", "generate"),
        "to_json": ("graphify.export", "to_json"),
        "to_html": ("graphify.export", "to_html"),
        "to_svg": ("graphify.export", "to_svg"),
        "to_canvas": ("graphify.export", "to_canvas"),
        "to_wiki": ("graphify.wiki", "to_wiki"),
    }
    if name in _map:
        import importlib
        mod_name, attr = _map[name]
        mod = importlib.import_module(mod_name)
        return getattr(mod, attr)
    raise AttributeError(f"module 'graphify' has no attribute {name!r}")
