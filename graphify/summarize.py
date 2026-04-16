"""Community summary generation with pluggable backends.

Backends:
  extractive (default) — template-based, no LLM required.
  ollama               — local Ollama model (Gemma, Llama, etc).
  claude               — Anthropic Claude API.
"""
from __future__ import annotations
import json
import os
import urllib.request
import urllib.error
import networkx as nx


def extractive_summary(
    G: nx.Graph,
    node_ids: list[str],
    *,
    max_nodes: int = 5,
    max_edges: int = 8,
) -> str:
    """Build a template-based summary from top-degree nodes and their relations.

    No LLM required — uses graph structure to produce a concise description.
    """
    if not node_ids:
        return "Empty community."

    subgraph = G.subgraph(node_ids)
    top_nodes = sorted(node_ids, key=lambda n: subgraph.degree(n), reverse=True)[:max_nodes]

    labels = [G.nodes[n].get("label", n) for n in top_nodes]
    remaining = len(node_ids) - len(top_nodes)

    # Collect key relationships
    relations: list[str] = []
    seen: set[tuple[str, str]] = set()
    for n in top_nodes:
        for neighbor in subgraph.neighbors(n):
            pair = tuple(sorted((n, neighbor)))
            if pair in seen:
                continue
            seen.add(pair)
            ed = subgraph.edges[n, neighbor]
            rel = ed.get("relation", "related_to")
            src_label = G.nodes[n].get("label", n)
            tgt_label = G.nodes[neighbor].get("label", neighbor)
            relations.append(f"{src_label} --{rel}--> {tgt_label}")
            if len(relations) >= max_edges:
                break
        if len(relations) >= max_edges:
            break

    # Source files represented
    sources = sorted({G.nodes[n].get("source_file", "") for n in node_ids} - {""})

    parts = [f"Key concepts: {', '.join(labels)}"]
    if remaining > 0:
        parts[0] += f" (+{remaining} more)"
    if relations:
        parts.append("Relationships: " + "; ".join(relations[:max_edges]))
    if sources:
        parts.append(f"Sources: {', '.join(sources[:5])}")

    return ". ".join(parts) + "."


def ollama_summary(
    G: nx.Graph,
    node_ids: list[str],
    *,
    model: str = "gemma4:latest",
    base_url: str = "http://localhost:11434",
) -> str:
    """Generate summary using a local Ollama model.

    Falls back to extractive_summary if Ollama is unreachable.
    """
    context = extractive_summary(G, node_ids)
    prompt = (
        "Summarize this knowledge graph community in 1-2 sentences. "
        "Be specific about what concepts it covers and how they relate.\n\n"
        f"{context}"
    )

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("message", {}).get("content", "").strip() or context
    except (urllib.error.URLError, TimeoutError, OSError):
        return context


def claude_summary(
    G: nx.Graph,
    node_ids: list[str],
    *,
    model: str = "claude-sonnet-4-20250514",
    api_key: str | None = None,
) -> str:
    """Generate summary using Anthropic Claude API.

    Falls back to extractive_summary if API key is missing or call fails.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return extractive_summary(G, node_ids)

    context = extractive_summary(G, node_ids)
    payload = json.dumps({
        "model": model,
        "max_tokens": 200,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Summarize this knowledge graph community in 1-2 sentences. "
                    "Be specific about what concepts it covers and how they relate.\n\n"
                    f"{context}"
                ),
            }
        ],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            content = data.get("content", [])
            if content and content[0].get("text"):
                return content[0]["text"].strip()
            return context
    except (urllib.error.URLError, TimeoutError, OSError):
        return context


_BACKENDS = {
    "extractive": extractive_summary,
    "ollama": ollama_summary,
    "claude": claude_summary,
}


def summarize_community(
    G: nx.Graph,
    node_ids: list[str],
    backend: str = "extractive",
    **kwargs,
) -> str:
    """Generate a summary for a community of nodes.

    backend: "extractive" (default, no LLM), "ollama" (local), or "claude" (API).
    Extra kwargs are passed to the backend function.
    """
    fn = _BACKENDS.get(backend)
    if fn is None:
        raise ValueError(f"Unknown summary backend: {backend!r}. Choose from: {list(_BACKENDS)}")
    return fn(G, node_ids, **kwargs)


def summarize_all_communities(
    G: nx.Graph,
    communities: dict[int, list[str]],
    backend: str = "extractive",
    **kwargs,
) -> dict[int, str]:
    """Generate summaries for all communities. Returns {community_id: summary}."""
    return {
        cid: summarize_community(G, nodes, backend=backend, **kwargs)
        for cid, nodes in communities.items()
    }
