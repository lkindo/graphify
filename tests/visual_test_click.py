#!/usr/bin/env python3
"""Visual browser test for node click detection.

Generates an HTML file with a rich mixed graph (code, document, paper, image,
rationale nodes — mirroring both tree-sitter and LLM extraction paths) and
opens it in the default browser. A debug overlay shows real-time event feedback.

Manual verification steps:
  1. Hover over a node   -> overlay shows "HOVER: <label>"
  2. Click the node      -> overlay shows "CLICK: <label>", METHOD: hover-track
  3. Click empty canvas  -> overlay shows "CLICK: (empty)"
  4. Click a SMALL node (paper/image) — these are low-degree and hardest to hit
  5. Click a neighbor link in the sidebar -> verify it focuses that node
  6. Check edge tooltips  -> INFERRED/AMBIGUOUS edges should show dashed styles
  7. Repeat on several nodes across different types
"""
from __future__ import annotations

import json
import tempfile
import webbrowser
from pathlib import Path

from graphify.build import build_from_json
from graphify.cluster import cluster
from graphify.export import to_html


def _build_mixed_extraction() -> dict:
    """Build a synthetic extraction covering all content types graphify produces.

    Includes code nodes (tree-sitter path), document/paper/image/rationale nodes
    (LLM path), and edges with EXTRACTED/INFERRED/AMBIGUOUS confidence levels.
    """
    return {
        "nodes": [
            # --- Code nodes (tree-sitter extraction) ---
            {"id": "api_server", "label": "APIServer", "file_type": "code",
             "source_file": "server.py", "source_location": "L1"},
            {"id": "api_auth", "label": "AuthMiddleware", "file_type": "code",
             "source_file": "auth.py", "source_location": "L15"},
            {"id": "api_router", "label": "Router", "file_type": "code",
             "source_file": "router.py", "source_location": "L8"},
            {"id": "api_handler", "label": "RequestHandler", "file_type": "code",
             "source_file": "handler.py", "source_location": "L22"},
            {"id": "api_cache", "label": "CacheLayer", "file_type": "code",
             "source_file": "cache.py", "source_location": "L5"},
            {"id": "api_db", "label": "DatabasePool", "file_type": "code",
             "source_file": "db.py", "source_location": "L1"},
            {"id": "api_models", "label": "UserModel", "file_type": "code",
             "source_file": "models.py", "source_location": "L30"},
            {"id": "api_serializer", "label": "JSONSerializer", "file_type": "code",
             "source_file": "serializer.py", "source_location": "L10"},

            # --- Document nodes (LLM extraction — docs/markdown) ---
            {"id": "doc_arch", "label": "Architecture Overview", "file_type": "document",
             "source_file": "docs/architecture.md", "source_location": "§1"},
            {"id": "doc_auth_guide", "label": "Authentication Guide", "file_type": "document",
             "source_file": "docs/auth.md", "source_location": "§2"},
            {"id": "doc_api_ref", "label": "API Reference", "file_type": "document",
             "source_file": "docs/api-ref.md", "source_location": "§1"},
            {"id": "doc_caching", "label": "Caching Strategy", "file_type": "document",
             "source_file": "docs/caching.md", "source_location": "§3"},

            # --- Paper nodes (LLM extraction — academic papers) ---
            {"id": "paper_oauth", "label": "OAuth 2.0 Framework (RFC 6749)",
             "file_type": "paper", "source_file": "papers/rfc6749.pdf",
             "source_location": "§4.1"},
            {"id": "paper_cache", "label": "Cache Invalidation Strategies",
             "file_type": "paper", "source_file": "papers/cache_inv.pdf",
             "source_location": "§2"},

            # --- Image nodes (LLM extraction — diagrams) ---
            {"id": "img_arch", "label": "System Architecture Diagram",
             "file_type": "image", "source_file": "docs/arch_diagram.png",
             "source_location": None},
            {"id": "img_flow", "label": "Request Flow Diagram",
             "file_type": "image", "source_file": "docs/req_flow.png",
             "source_location": None},

            # --- Rationale nodes (tree-sitter Python docstring extraction) ---
            {"id": "rat_auth_why", "label": "Why token-based auth",
             "file_type": "rationale", "source_file": "auth.py",
             "source_location": "L3"},
            {"id": "rat_cache_why", "label": "Why LRU over TTL",
             "file_type": "rationale", "source_file": "cache.py",
             "source_location": "L2"},
        ],
        "edges": [
            # --- EXTRACTED edges (tree-sitter: contains, imports) ---
            {"source": "api_server", "target": "api_router",
             "relation": "contains", "confidence": "EXTRACTED",
             "source_file": "server.py", "weight": 1.0},
            {"source": "api_server", "target": "api_auth",
             "relation": "contains", "confidence": "EXTRACTED",
             "source_file": "server.py", "weight": 1.0},
            {"source": "api_router", "target": "api_handler",
             "relation": "contains", "confidence": "EXTRACTED",
             "source_file": "router.py", "weight": 1.0},
            {"source": "api_handler", "target": "api_db",
             "relation": "calls", "confidence": "EXTRACTED",
             "source_file": "handler.py", "weight": 1.0},
            {"source": "api_handler", "target": "api_cache",
             "relation": "calls", "confidence": "EXTRACTED",
             "source_file": "handler.py", "weight": 1.0},
            {"source": "api_handler", "target": "api_serializer",
             "relation": "calls", "confidence": "EXTRACTED",
             "source_file": "handler.py", "weight": 1.0},
            {"source": "api_db", "target": "api_models",
             "relation": "imports", "confidence": "EXTRACTED",
             "source_file": "db.py", "weight": 1.0},

            # --- INFERRED edges (LLM: references, implements) ---
            {"source": "doc_arch", "target": "api_server",
             "relation": "references", "confidence": "INFERRED",
             "source_file": "docs/architecture.md", "weight": 0.8},
            {"source": "doc_auth_guide", "target": "api_auth",
             "relation": "references", "confidence": "INFERRED",
             "source_file": "docs/auth.md", "weight": 0.8},
            {"source": "doc_api_ref", "target": "api_handler",
             "relation": "references", "confidence": "INFERRED",
             "source_file": "docs/api-ref.md", "weight": 0.8},
            {"source": "doc_caching", "target": "api_cache",
             "relation": "references", "confidence": "INFERRED",
             "source_file": "docs/caching.md", "weight": 0.8},
            {"source": "api_auth", "target": "paper_oauth",
             "relation": "implements", "confidence": "INFERRED",
             "source_file": "auth.py", "weight": 0.8},
            {"source": "api_cache", "target": "paper_cache",
             "relation": "implements", "confidence": "INFERRED",
             "source_file": "cache.py", "weight": 0.8},

            # --- AMBIGUOUS edges (LLM: semantic similarity, weak links) ---
            {"source": "img_arch", "target": "doc_arch",
             "relation": "semantically_similar_to", "confidence": "AMBIGUOUS",
             "source_file": "docs/arch_diagram.png", "weight": 0.5},
            {"source": "img_flow", "target": "api_router",
             "relation": "references", "confidence": "AMBIGUOUS",
             "source_file": "docs/req_flow.png", "weight": 0.5},
            {"source": "paper_cache", "target": "doc_caching",
             "relation": "cites", "confidence": "INFERRED",
             "source_file": "papers/cache_inv.pdf", "weight": 0.8},

            # --- Rationale edges (tree-sitter: rationale_for) ---
            {"source": "rat_auth_why", "target": "api_auth",
             "relation": "rationale_for", "confidence": "EXTRACTED",
             "source_file": "auth.py", "weight": 1.0},
            {"source": "rat_cache_why", "target": "api_cache",
             "relation": "rationale_for", "confidence": "EXTRACTED",
             "source_file": "cache.py", "weight": 1.0},
        ],
    }

DEBUG_OVERLAY_CSS = """
#debug-overlay {
  position: fixed; bottom: 0; left: 0; right: 280px;
  background: rgba(0,0,0,0.85); color: #0f0; font-family: monospace;
  font-size: 13px; padding: 8px 14px; z-index: 9999;
  border-top: 2px solid #0f0; display: flex; gap: 24px;
}
#debug-overlay .label { color: #888; }
#debug-overlay .value { color: #0f0; font-weight: bold; }
#debug-overlay .fail  { color: #f44; font-weight: bold; }
"""

DEBUG_OVERLAY_HTML = """
<div id="debug-overlay">
  <span><span class="label">HOVER: </span><span id="dbg-hover" class="value">—</span></span>
  <span><span class="label">CLICK: </span><span id="dbg-click" class="value">—</span></span>
  <span><span class="label">METHOD: </span><span id="dbg-method" class="value">—</span></span>
  <span><span class="label">EVENTS: </span><span id="dbg-count" class="value">0</span></span>
</div>
"""

DEBUG_OVERLAY_JS = r"""
// --- Debug overlay instrumentation ---
(function() {
  var clickCount = 0;
  var hoverEl = document.getElementById('dbg-hover');
  var clickEl = document.getElementById('dbg-click');
  var methodEl = document.getElementById('dbg-method');
  var countEl = document.getElementById('dbg-count');

  // Patch into existing hoverNode/blurNode
  var origHovered = null;
  network.on('hoverNode', function(p) {
    origHovered = p.node;
    var n = RAW_NODES.find(function(x) { return x.id === p.node; });
    hoverEl.textContent = n ? n.label : p.node;
    hoverEl.className = 'value';
  });
  network.on('blurNode', function() {
    origHovered = null;
    hoverEl.textContent = '—';
  });

  // Listen for DOM click (hover-based path)
  container.addEventListener('click', function() {
    if (origHovered !== null) {
      var n = RAW_NODES.find(function(x) { return x.id === origHovered; });
      clickEl.textContent = n ? n.label : origHovered;
      clickEl.className = 'value';
      methodEl.textContent = 'hover-track';
      methodEl.className = 'value';
      clickCount++;
      countEl.textContent = clickCount;
    }
  });

  // Listen for vis-network click (fallback path)
  network.on('click', function(params) {
    if (params.nodes.length > 0) {
      var nid = params.nodes[0];
      var n = RAW_NODES.find(function(x) { return x.id === nid; });
      clickEl.textContent = n ? n.label : nid;
      clickEl.className = 'value';
      // Only mark method as 'network.click' if hover-track didn't already fire
      if (origHovered === null) {
        methodEl.textContent = 'network.click (fallback)';
        methodEl.className = 'value';
      }
      clickCount++;
      countEl.textContent = clickCount;
    } else if (origHovered === null) {
      clickEl.textContent = '(empty)';
      clickEl.className = 'fail';
      methodEl.textContent = '—';
      methodEl.className = 'value';
    }
  });
})();
"""


def inject_debug_overlay(html: str) -> str:
    """Inject debug overlay CSS, HTML, and JS into the generated HTML."""
    # Inject CSS before </style>
    html = html.replace("</style>", DEBUG_OVERLAY_CSS + "\n</style>", 1)

    # Inject HTML before </body>
    html = html.replace("</body>", DEBUG_OVERLAY_HTML + "\n</body>", 1)

    # Inject JS before </script>  (last occurrence — the main script block)
    # Find the last </script> and insert before it
    idx = html.rfind("</script>")
    if idx != -1:
        html = html[:idx] + "\n" + DEBUG_OVERLAY_JS + "\n" + html[idx:]

    return html


def main() -> None:
    """Build graph, generate HTML with debug overlay, and open in browser."""
    extraction = _build_mixed_extraction()
    G = build_from_json(extraction)
    communities = cluster(G)
    labels = {cid: f"Group {cid}" for cid in communities}

    with tempfile.NamedTemporaryFile(
        suffix=".html", prefix="graphify_click_test_", delete=False, mode="w"
    ) as f:
        to_html(G, communities, f.name, community_labels=labels)

        content = Path(f.name).read_text()
        content = inject_debug_overlay(content)
        Path(f.name).write_text(content)

        print(f"Visual test written to: {f.name}")
        print()
        print("Graph: 20 nodes (8 code, 4 doc, 2 paper, 2 image, 2 rationale)")
        print("       18 edges (EXTRACTED + INFERRED + AMBIGUOUS)")
        print()
        print("Verification steps:")
        print("  1. Hover a node        -> HOVER shows label")
        print("  2. Click the node      -> CLICK shows label, METHOD: hover-track")
        print("  3. Click empty canvas  -> CLICK: (empty)")
        print("  4. Click a SMALL node  -> papers/images are low-degree, hardest to hit")
        print("  5. Click neighbor link -> sidebar link should focus that node")
        print("  6. Check edge tooltips -> dashed = INFERRED/AMBIGUOUS")
        print("  7. Try all file_types  -> code, document, paper, image, rationale")
        print()

        webbrowser.open(f"file://{f.name}")


if __name__ == "__main__":
    main()
