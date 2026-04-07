"""Local embedding generation for semantic similarity edges."""

from __future__ import annotations
import math
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import networkx as nx


def _is_file_node(G: nx.Graph, node_id: str) -> bool:
    """
    Return True if this node is a file-level hub node (e.g. 'client', 'models')
    or an AST method stub (e.g. '.auth_flow()', '.__init__()').

    These are synthetic nodes created by the AST extractor and should be excluded
    from embedding generation as they represent structural artifacts, not semantic concepts.
    """
    attrs = G.nodes[node_id]
    label = attrs.get("label", "")
    if not label:
        return False
    # File-level hub: label matches the actual source filename (not just any label ending in .py)
    source_file = attrs.get("source_file", "")
    if source_file:
        from pathlib import Path as _Path

        if label == _Path(source_file).name:
            return True
    # Method stub: AST extractor labels methods as '.method_name()'
    if label.startswith(".") and label.endswith("()"):
        return True
    # Module-level function stub: labeled 'function_name()' - only has a contains edge
    # These are real functions but structurally isolated by definition; not a meaningful concept for embedding
    if label.endswith("()") and G.degree(node_id) <= 1:
        return True
    return False


def _compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    if len(vec1) != len(vec2):
        raise ValueError(f"Vectors must have same length: {len(vec1)} vs {len(vec2)}")

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


def _get_node_content(G: nx.Graph, node_id: str) -> str:
    """Extract content for embedding from a node."""
    attrs = G.nodes[node_id]
    label = attrs.get("label", "")
    # Include both label and any docstring/comment content if available
    content = label
    if "docstring" in attrs:
        content += " " + str(attrs["docstring"])
    if "comment" in attrs:
        content += " " + str(attrs["comment"])
    return content.strip()


def generate_embeddings(
    G: nx.Graph, backend: str = "auto", model: str = "gemma4", threshold: float = 0.82
) -> Dict[str, List[float]]:
    """
    Generate embeddings for all real entity nodes in the graph.

    Args:
        G: NetworkX graph with nodes to embed
        backend: 'llama_cpp', 'ollama', or 'auto' to detect available
        model: Model identifier to use
        threshold: Similarity threshold for edges

    Returns:
        Dict mapping node_id to embedding vector
    """
    # Filter out synthetic nodes (file hubs, method stubs)
    real_nodes = [nid for nid in G.nodes() if not _is_file_node(G, nid)]

    # For now, use mock embeddings for testing
    # In real implementation, we'd call the embedding backend here
    embeddings = {}

    if backend == "mock":
        # Mock implementation for testing
        for node_id in real_nodes:
            content = _get_node_content(G, node_id)
            # Create deterministic mock embedding based on content hash
            content_hash = hashlib.md5(content.encode()).hexdigest()
            # Convert hash to pseudo-vector (values between -1 and 1)
            vector = []
            for i in range(0, len(content_hash), 2):
                if i + 1 < len(content_hash):
                    byte_val = int(content_hash[i : i + 2], 16)
                    normalized = (byte_val / 128.0) - 1.0  # Normalize to [-1, 1]
                    vector.append(normalized)
            embeddings[node_id] = (
                vector[:32] if len(vector) > 32 else vector + [0.0] * (32 - len(vector))
            )
    else:
        # Real implementation would use llama-cpp-python or ollama
        if backend == "auto":
            backend = _detect_available_backend()

        if backend == "llama_cpp":
            from llama_cpp import Llama

            # Initialize model
            llm = Llama(model_path=_get_model_path(model), embedding=True)
            for node_id in real_nodes:
                content = _get_node_content(G, node_id)
                embedding_result = llm.create_embedding(content)
                embeddings[node_id] = embedding_result["data"][0]["embedding"]
        elif backend == "ollama":
            import ollama

            for node_id in real_nodes:
                content = _get_node_content(G, node_id)
                embedding_result = ollama.embeddings(model=model, prompt=content)
                embeddings[node_id] = embedding_result["embedding"]
        else:
            raise ValueError(f"Unknown backend: {backend}")

    return embeddings


def _detect_available_backend() -> str:
    """Detect which embedding backend is available."""
    try:
        import llama_cpp

        return "llama_cpp"
    except ImportError:
        pass

    try:
        import ollama

        return "ollama"
    except ImportError:
        pass

    raise RuntimeError(
        "No embedding backend available. Install llama-cpp-python or ollama"
    )


def _get_model_path(model: str) -> str:
    """Get local path for the specified model."""
    # In a real implementation, this would resolve to actual model paths
    # For now, return a placeholder
    return f"models/{model}.gguf"


def add_similarity_edges(
    G: nx.Graph, embeddings: Dict[str, List[float]], threshold: float = 0.82
) -> int:
    """
    Add semantically_similar_to edges between nodes with similar embeddings.

    Args:
        G: NetworkX graph to add edges to
        embeddings: Dict mapping node_id to embedding vector
        threshold: Minimum cosine similarity to create an edge

    Returns:
        Number of edges added
    """
    edges_added = 0

    nodes = list(embeddings.keys())
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            node1, node2 = nodes[i], nodes[j]

            sim = _compute_cosine_similarity(embeddings[node1], embeddings[node2])

            if sim >= threshold:
                G.add_edge(
                    node1,
                    node2,
                    relation="semantically_similar_to",
                    confidence="INFERRED",
                    confidence_score=sim,
                    source_file="embedding_pass",  # Indicates this edge came from embedding analysis
                    weight=sim,
                )
                edges_added += 1

    return edges_added


def cache_dir(root: Path = Path(".")) -> Path:
    """Returns graphify-out/cache/embeddings/ - creates it if needed."""
    d = Path(root) / "graphify-out" / "cache" / "embeddings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_embedding_cache(
    embeddings: Dict[str, List[float]], root: Path = Path(".")
) -> None:
    """Save embedding vectors to cache."""
    import json
    import os
    from pathlib import Path

    entry = cache_dir(root) / "embeddings.json"
    tmp = entry.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(embeddings))
        os.replace(tmp, entry)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def load_embedding_cache(root: Path = Path(".")) -> Dict[str, List[float]] | None:
    """Load embedding vectors from cache."""
    import json
    from pathlib import Path

    entry = cache_dir(root) / "embeddings.json"
    if not entry.exists():
        return None
    try:
        content = entry.read_text()
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return None


def get_embedding_cache_key(G: nx.Graph) -> str:
    """Generate a cache key based on graph content."""
    import hashlib

    # Create a hash of node content to detect changes
    content_parts = []
    for node_id in sorted(G.nodes()):
        if not _is_file_node(G, node_id):
            content = _get_node_content(G, node_id)
            content_parts.append(f"{node_id}:{content}")

    full_content = "|".join(content_parts)
    return hashlib.sha256(full_content.encode()).hexdigest()


def generate_embeddings_with_cache(
    G: nx.Graph,
    backend: str = "auto",
    model: str = "gemma4",
    threshold: float = 0.82,
    root: Path = Path("."),
) -> Dict[str, List[float]]:
    """
    Generate embeddings with caching to avoid recomputation.

    Args:
        G: NetworkX graph with nodes to embed
        backend: 'llama_cpp', 'ollama', or 'auto'
        model: Model identifier to use
        threshold: Similarity threshold for edges
        root: Root directory for cache

    Returns:
        Dict mapping node_id to embedding vector
    """
    cache_key = get_embedding_cache_key(G)
    cache_entry = cache_dir(root) / f"{cache_key}.json"

    # Try to load from cache first
    if cache_entry.exists():
        try:
            import json

            content = cache_entry.read_text()
            return json.loads(content)
        except (json.JSONDecodeError, OSError):
            pass  # Cache corrupted, regenerate

    # Generate new embeddings
    embeddings = generate_embeddings(G, backend, model, threshold)

    # Save to cache
    try:
        import json
        import os

        tmp = cache_entry.with_suffix(".tmp")
        tmp.write_text(json.dumps(embeddings))
        os.replace(tmp, cache_entry)
    except Exception:
        pass  # Don't fail if caching fails

    return embeddings
