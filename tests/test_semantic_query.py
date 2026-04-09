from __future__ import annotations

import json

import networkx as nx
import numpy as np
from networkx.readwrite import json_graph

from graphify.export import to_json
from graphify.semantic import (
    _get_backend,
    _graph_hash_for_current_file,
    build_semantic_index,
    graph_content_hash,
    load_semantic_index,
    semantic_search,
)
from graphify.serve import _hybrid_seed_nodes


class FakeBackend:
    def __init__(self, mapping: dict[str, list[float]]):
        self.mapping = {k: np.asarray(v, dtype=np.float32) for k, v in mapping.items()}

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self.mapping[text] for text in texts]).astype(np.float32)


def _make_graph() -> nx.Graph:
    G = nx.Graph()
    G.add_node("auth", label="Authentication Flow", source_file="auth.py", file_type="code")
    G.add_node("login", label="Login Handler", source_file="login.py", file_type="code")
    G.add_node("ui", label="UI Renderer", source_file="ui.py", file_type="code")
    G.add_edge("auth", "login", relation="calls", confidence="EXTRACTED")
    return G


def test_build_and_load_semantic_index(tmp_path):
    G = _make_graph()
    graph_file = tmp_path / "graph.json"
    data = json_graph.node_link_data(G, edges="links")
    graph_file.write_text(json.dumps(data), encoding="utf-8")

    backend = FakeBackend(
        {
            "Authentication Flow | auth.py | code": [1.0, 0.0],
            "Login Handler | login.py | code": [0.9, 0.1],
            "UI Renderer | ui.py | code": [0.0, 1.0],
        }
    )
    meta = build_semantic_index(graph_file, backend=backend, model_name="fake")
    index = load_semantic_index(graph_file)

    assert meta["count"] == 3
    assert index is not None
    assert len(index.nodes) == 3
    assert index.embeddings.shape == (3, 2)


def test_semantic_search_returns_best_match(tmp_path):
    G = _make_graph()
    graph_file = tmp_path / "graph.json"
    data = json_graph.node_link_data(G, edges="links")
    graph_file.write_text(json.dumps(data), encoding="utf-8")

    backend = FakeBackend(
        {
            "Authentication Flow | auth.py | code": [1.0, 0.0],
            "Login Handler | login.py | code": [0.9, 0.1],
            "UI Renderer | ui.py | code": [0.0, 1.0],
            "how sign in works": [0.95, 0.05],
        }
    )
    build_semantic_index(graph_file, backend=backend, model_name="fake")
    results = semantic_search(graph_file, "how sign in works", backend=backend, model_name="fake")

    assert results
    assert results[0]["id"] == "auth"


def test_semantic_search_uses_preloaded_index(tmp_path):
    G = _make_graph()
    graph_file = tmp_path / "graph.json"
    data = json_graph.node_link_data(G, edges="links")
    graph_file.write_text(json.dumps(data), encoding="utf-8")

    backend = FakeBackend(
        {
            "Authentication Flow | auth.py | code": [1.0, 0.0],
            "Login Handler | login.py | code": [0.9, 0.1],
            "UI Renderer | ui.py | code": [0.0, 1.0],
            "how sign in works": [0.95, 0.05],
        }
    )
    build_semantic_index(graph_file, backend=backend, model_name="fake")
    index = load_semantic_index(graph_file)

    assert index is not None
    results = semantic_search(graph_file, "how sign in works", index=index, backend=backend, model_name="fake")
    assert results[0]["id"] == "auth"


def test_hybrid_seed_nodes_falls_back_to_semantic(tmp_path):
    G = _make_graph()
    graph_file = tmp_path / "graph.json"
    to_json(G, {0: ["auth", "login"], 1: ["ui"]}, str(graph_file))

    backend = FakeBackend(
        {
            "Authentication Flow | auth.py | code": [1.0, 0.0],
            "Login Handler | login.py | code": [0.9, 0.1],
            "UI Renderer | ui.py | code": [0.0, 1.0],
            "sign in experience": [0.95, 0.05],
        }
    )
    build_semantic_index(graph_file, backend=backend, model_name="fake", force=True)
    import graphify.serve as serve_module

    original = serve_module.semantic_search
    serve_module.semantic_search = lambda *args, **kwargs: semantic_search(*args, backend=backend, model_name="fake", **kwargs)
    try:
        seeds = _hybrid_seed_nodes(G, str(graph_file), "sign in experience")
    finally:
        serve_module.semantic_search = original

    assert seeds
    assert any(seed["source"] == "semantic" and seed["id"] == "auth" for seed in seeds)


def test_hybrid_seed_nodes_fuses_keyword_and_semantic(tmp_path):
    G = _make_graph()
    graph_file = tmp_path / "graph.json"
    data = json_graph.node_link_data(G, edges="links")
    graph_file.write_text(json.dumps(data), encoding="utf-8")

    backend = FakeBackend(
        {
            "Authentication Flow | auth.py | code": [1.0, 0.0],
            "Login Handler | login.py | code": [0.8, 0.2],
            "UI Renderer | ui.py | code": [0.0, 1.0],
            "authentication": [1.0, 0.0],
        }
    )
    build_semantic_index(graph_file, backend=backend, model_name="fake", force=True)

    import graphify.serve as serve_module

    original = serve_module.semantic_search
    serve_module.semantic_search = lambda *args, **kwargs: semantic_search(*args, backend=backend, model_name="fake", **kwargs)
    try:
        seeds = _hybrid_seed_nodes(G, str(graph_file), "authentication")
    finally:
        serve_module.semantic_search = original

    assert seeds[0]["id"] == "auth"
    assert seeds[0]["source"] == "hybrid"


def test_load_semantic_index_rejects_invalid_meta(tmp_path):
    G = _make_graph()
    graph_file = tmp_path / "graph.json"
    data = json_graph.node_link_data(G, edges="links")
    graph_file.write_text(json.dumps(data), encoding="utf-8")

    backend = FakeBackend(
        {
            "Authentication Flow | auth.py | code": [1.0, 0.0],
            "Login Handler | login.py | code": [0.9, 0.1],
            "UI Renderer | ui.py | code": [0.0, 1.0],
        }
    )
    build_semantic_index(graph_file, backend=backend, model_name="fake")
    meta_file = graph_file.parent / "semantic.meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    meta["version"] = 999
    meta_file.write_text(json.dumps(meta), encoding="utf-8")

    assert load_semantic_index(graph_file) is None


def test_graph_content_hash_matches_chunked_read(tmp_path):
    graph_file = tmp_path / "graph.json"
    payload = b'{"nodes": [' + (b'"x",' * 10000) + b'0]}'
    graph_file.write_bytes(payload)

    assert graph_content_hash(graph_file) == __import__("hashlib").sha256(payload).hexdigest()


def test_graph_hash_cache_reuses_unchanged_file(tmp_path):
    graph_file = tmp_path / "graph.json"
    graph_file.write_text('{"nodes":[]}', encoding="utf-8")

    first = _graph_hash_for_current_file(graph_file)
    second = _graph_hash_for_current_file(graph_file)

    assert first == second


def test_semantic_search_reuses_cached_backend(tmp_path):
    G = _make_graph()
    graph_file = tmp_path / "graph.json"
    data = json_graph.node_link_data(G, edges="links")
    graph_file.write_text(json.dumps(data), encoding="utf-8")

    backend = FakeBackend(
        {
            "Authentication Flow | auth.py | code": [1.0, 0.0],
            "Login Handler | login.py | code": [0.9, 0.1],
            "UI Renderer | ui.py | code": [0.0, 1.0],
            "how sign in works": [0.95, 0.05],
        }
    )
    build_semantic_index(graph_file, backend=backend, model_name="fake")
    index = load_semantic_index(graph_file)

    class CountingBackend(FakeBackend):
        init_count = 0

        def __init__(self, model_name: str = "fake"):
            type(self).init_count += 1
            super().__init__(
                {
                    "Authentication Flow | auth.py | code": [1.0, 0.0],
                    "Login Handler | login.py | code": [0.9, 0.1],
                    "UI Renderer | ui.py | code": [0.0, 1.0],
                    "how sign in works": [0.95, 0.05],
                }
            )

    import graphify.semantic as semantic_module

    original_backend = semantic_module.SentenceTransformerBackend
    _get_backend.cache_clear()
    semantic_module.SentenceTransformerBackend = CountingBackend
    try:
        semantic_search(graph_file, "how sign in works", index=index, model_name="fake")
        semantic_search(graph_file, "how sign in works", index=index, model_name="fake")
    finally:
        semantic_module.SentenceTransformerBackend = original_backend
        _get_backend.cache_clear()

    assert CountingBackend.init_count == 1
