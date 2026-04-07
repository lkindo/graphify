"""Main graphify pipeline that integrates embedding functionality."""

from __future__ import annotations
import json
import sys
from pathlib import Path
import networkx as nx
from .build import build_from_json
from .cluster import cluster, score_all
from .analyze import god_nodes, surprising_connections, suggest_questions
from .report import generate
from .export import to_json, to_html
from .embed import generate_embeddings_with_cache, add_similarity_edges


def run_embedding_pass(
    G: nx.Graph,
    communities: dict[int, list[str]],
    root: Path = Path("."),
    embeddings_flag: bool = False,
    embed_threshold: float = 0.82,
    embed_backend: str = "auto",
    embed_model: str = "gemma4",
) -> tuple[nx.Graph, dict[int, list[str]]]:
    """
    Run the embedding pass to add semantically_similar_to edges to the graph.

    Args:
        G: The graph to add embeddings to
        communities: Current community assignments
        root: Root directory for caching
        embeddings_flag: Whether to run the embedding pass
        embed_threshold: Cosine similarity threshold for new edges
        embed_backend: Backend to use ('llama_cpp', 'ollama', 'auto')
        embed_model: Model to use for embeddings

    Returns:
        Updated (graph, communities) tuple
    """
    if not embeddings_flag:
        return G, communities

    print(
        f"[graphify] Running embedding pass with threshold={embed_threshold}, backend={embed_backend}, model={embed_model}"
    )

    # Generate embeddings with caching
    embeddings = generate_embeddings_with_cache(
        G,
        backend=embed_backend,
        model=embed_model,
        threshold=embed_threshold,
        root=root,
    )

    # Add similarity edges to the graph
    edges_added = add_similarity_edges(G, embeddings, threshold=embed_threshold)

    print(
        f"[graphify] Added {edges_added} semantically_similar_to edges via embedding pass"
    )

    # Since we added new edges, we should potentially re-cluster to account for new connections
    # But for now, return the same communities - in a full implementation,
    # we might want to optionally re-cluster
    return G, communities


def run_full_pipeline(
    extraction: dict,
    detection: dict,
    root: Path = Path("."),
    embeddings_flag: bool = False,
    embed_threshold: float = 0.82,
    embed_backend: str = "auto",
    embed_model: str = "gemma4",
) -> dict:
    """
    Run the complete graphify pipeline including optional embedding pass.

    Args:
        extraction: Result from extraction phase
        detection: Result from detection phase
        root: Root directory for output and caching
        embeddings_flag: Whether to run the embedding pass
        embed_threshold: Cosine similarity threshold for new edges
        embed_backend: Backend to use ('llama_cpp', 'ollama', 'auto')
        embed_model: Model to use for embeddings

    Returns:
        Dictionary with pipeline results including graph, communities, etc.
    """
    # Step 1: Build graph from extraction
    G = build_from_json(extraction)

    # Step 2: Cluster the graph
    communities = cluster(G)
    cohesion = score_all(G, communities)

    # Step 3: Run embedding pass if requested (this modifies the graph)
    G, communities = run_embedding_pass(
        G,
        communities,
        root,
        embeddings_flag,
        embed_threshold,
        embed_backend,
        embed_model,
    )

    # Step 4: Analyze the (potentially updated) graph
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    labels = {cid: "Community " + str(cid) for cid in communities}
    questions = suggest_questions(G, communities, labels)

    # Step 5: Generate outputs
    tokens = {
        "input": extraction.get("input_tokens", 0),
        "output": extraction.get("output_tokens", 0),
    }

    # Create output directory
    out_dir = root / "graphify-out"
    out_dir.mkdir(exist_ok=True)

    # Generate report
    report = generate(
        G,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        tokens,
        str(root),
        suggested_questions=questions,
    )

    # Save JSON
    json_path = out_dir / "graph.json"
    to_json(G, communities, str(json_path))

    # Save report
    report_path = out_dir / "GRAPH_REPORT.md"
    report_path.write_text(report, encoding="utf-8")

    # Also generate HTML
    html_path = out_dir / "graph.html"
    to_html(G, communities, str(html_path), community_labels=labels)

    # Save analysis results
    analysis = {
        "communities": {str(k): v for k, v in communities.items()},
        "cohesion": {str(k): v for k, v in cohesion.items()},
        "gods": gods,
        "surprises": surprises,
        "questions": questions,
        "graph_nodes": G.number_of_nodes(),
        "graph_edges": G.number_of_edges(),
    }

    return {
        "graph": G,
        "communities": communities,
        "cohesion": cohesion,
        "gods": gods,
        "surprises": surprises,
        "questions": questions,
        "report": report,
        "analysis": analysis,
        "output_dir": out_dir,
    }
