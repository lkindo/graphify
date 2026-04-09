from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np

from networkx.readwrite import json_graph


_DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_EMBEDDING_MATRIX_FILE = "semantic.embeddings.npy"
_EMBEDDING_NODES_FILE = "semantic.nodes.json"
_EMBEDDING_META_FILE = "semantic.meta.json"
_SEMANTIC_INDEX_VERSION = 1
_HASH_CHUNK_SIZE = 8192


class EmbeddingBackend(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class SemanticIndex:
    nodes: list[dict]
    embeddings: np.ndarray
    meta: dict


class SentenceTransformerBackend:
    def __init__(self, model_name: str = _DEFAULT_MODEL_NAME):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "semantic embeddings require optional dependencies. Run: pip install 'graphifyy[embeddings]'"
            ) from exc
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        vectors = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float32)


def graph_output_dir(graph_path: str | Path) -> Path:
    path = Path(graph_path)
    if path.is_dir():
        return path
    return path.parent


def default_model_name() -> str:
    return _DEFAULT_MODEL_NAME


def semantic_artifact_paths(graph_path: str | Path) -> dict[str, Path]:
    out_dir = graph_output_dir(graph_path)
    return {
        "out_dir": out_dir,
        "embeddings": out_dir / _EMBEDDING_MATRIX_FILE,
        "nodes": out_dir / _EMBEDDING_NODES_FILE,
        "meta": out_dir / _EMBEDDING_META_FILE,
    }


@lru_cache(maxsize=4)
def _get_backend(model_name: str) -> SentenceTransformerBackend:
    return SentenceTransformerBackend(model_name=model_name)


def semantic_text_for_node(node_id: str, data: dict) -> str:
    parts = [
        data.get("label", node_id),
        data.get("source_file", ""),
        data.get("file_type", ""),
        data.get("source_location", ""),
    ]
    return " | ".join(part.strip() for part in parts if part and str(part).strip())


def semantic_candidate_nodes(G) -> list[dict]:
    items: list[dict] = []
    for node_id, data in G.nodes(data=True):
        label = str(data.get("label", "")).strip()
        if not label:
            continue
        text = semantic_text_for_node(node_id, data)
        items.append(
            {
                "id": node_id,
                "label": label,
                "text": text,
                "source_file": data.get("source_file", ""),
                "file_type": data.get("file_type", ""),
                "source_location": data.get("source_location", ""),
            }
        )
    return items


def graph_content_hash(graph_path: str | Path) -> str:
    sha256 = hashlib.sha256()
    with Path(graph_path).open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


@lru_cache(maxsize=32)
def _cached_graph_content_hash(graph_path: str, stat_key: tuple[int, int, int]) -> str:
    return graph_content_hash(graph_path)


def _graph_hash_for_current_file(graph_path: str | Path) -> str:
    path = Path(graph_path)
    stat_result = path.stat()
    stat_key = (stat_result.st_size, stat_result.st_mtime_ns, getattr(stat_result, "st_ino", 0))
    return _cached_graph_content_hash(str(path.resolve()), stat_key)


def save_semantic_index(graph_path: str | Path, nodes: list[dict], embeddings: np.ndarray, meta: dict) -> None:
    paths = semantic_artifact_paths(graph_path)
    paths["out_dir"].mkdir(parents=True, exist_ok=True)
    np.save(paths["embeddings"], np.asarray(embeddings, dtype=np.float32))
    paths["nodes"].write_text(json.dumps(nodes, indent=2), encoding="utf-8")
    paths["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")


def load_semantic_index(graph_path: str | Path) -> SemanticIndex | None:
    graph_path = Path(graph_path)
    paths = semantic_artifact_paths(graph_path)
    if not all(paths[name].exists() for name in ("embeddings", "nodes", "meta")):
        return None
    nodes = json.loads(paths["nodes"].read_text(encoding="utf-8"))
    embeddings = np.load(paths["embeddings"])
    meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
    current_hash = _graph_hash_for_current_file(graph_path)
    if meta.get("version") != _SEMANTIC_INDEX_VERSION:
        return None
    if meta.get("graph_sha256") != current_hash:
        return None
    if len(nodes) != len(embeddings):
        return None
    if embeddings.ndim != 2:
        return None
    if meta.get("count") != len(nodes):
        return None
    if meta.get("dim") != int(embeddings.shape[1]):
        return None
    return SemanticIndex(nodes=nodes, embeddings=np.asarray(embeddings, dtype=np.float32), meta=meta)


def build_semantic_index(
    graph_path: str | Path,
    backend: EmbeddingBackend | None = None,
    model_name: str = _DEFAULT_MODEL_NAME,
    force: bool = False,
) -> dict:
    graph_path = Path(graph_path)
    current_hash = _graph_hash_for_current_file(graph_path)
    existing = load_semantic_index(graph_path)
    if existing and not force and existing.meta.get("graph_sha256") == current_hash and existing.meta.get("model_name") == model_name:
        return existing.meta

    data = json.loads(graph_path.read_text(encoding="utf-8"))
    try:
        G = json_graph.node_link_graph(data, edges="links")
    except TypeError:
        G = json_graph.node_link_graph(data)
    nodes = semantic_candidate_nodes(G)
    if backend is None:
        backend = _get_backend(model_name)
    texts = [node["text"] for node in nodes]
    embeddings = np.asarray(backend.encode(texts), dtype=np.float32)
    dim = int(embeddings.shape[1]) if embeddings.ndim == 2 and embeddings.shape[0] else 0
    meta = {
        "version": _SEMANTIC_INDEX_VERSION,
        "model_name": model_name,
        "graph_sha256": current_hash,
        "normalized": True,
        "count": len(nodes),
        "dim": dim,
    }
    save_semantic_index(graph_path, nodes, embeddings, meta)
    return meta


def semantic_search(
    graph_path: str | Path,
    query: str,
    index: SemanticIndex | None = None,
    backend: EmbeddingBackend | None = None,
    top_k: int = 5,
    min_score: float = 0.2,
    model_name: str = _DEFAULT_MODEL_NAME,
) -> list[dict]:
    if index is None:
        index = load_semantic_index(graph_path)
    if index is None:
        raise FileNotFoundError("semantic index not found. Build it first.")
    if backend is None:
        backend = _get_backend(index.meta.get("model_name") or model_name or _DEFAULT_MODEL_NAME)
    query_embedding = np.asarray(backend.encode([query]), dtype=np.float32)
    if query_embedding.size == 0 or index.embeddings.size == 0:
        return []
    scores = index.embeddings @ query_embedding[0]
    ranked = np.argsort(scores)[::-1]
    results = []
    for idx in ranked[:top_k]:
        score = float(scores[idx])
        if score < min_score:
            continue
        results.append({**index.nodes[int(idx)], "score": round(score, 4)})
    return results
