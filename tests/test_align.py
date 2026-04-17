from graphify.align import canonicalize, normalize_identifier
from graphify.build import build_from_json


def test_normalize_identifier_splits_camel_and_snake_case():
    assert normalize_identifier("SentenceTransformer") == "sentence transformer"
    assert normalize_identifier("sentence_transformer") == "sentence transformer"
    assert normalize_identifier("HTTPClient_v2") == "http client v2"


def test_canonicalize_collapses_spacing_and_case():
    assert canonicalize("SentenceTransformer") == "sentencetransformer"
    assert canonicalize("sentence transformer") == "sentencetransformer"
    assert canonicalize("sentence-transformer") == "sentencetransformer"


def test_build_uses_canonical_node_ids_and_aliases():
    extraction = {
        "nodes": [
            {"id": "ast_sentence_transformer", "label": "SentenceTransformer", "file_type": "code", "source_file": "model.py"},
            {"id": "sem_sentence_transformer", "label": "sentence transformer", "file_type": "document", "source_file": "notes.md"},
        ],
        "edges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }

    G = build_from_json(extraction, directed=True)

    assert "sentencetransformer" in G
    node = G.nodes["sentencetransformer"]
    assert node["canonical_id"] == "sentencetransformer"
    assert "SentenceTransformer" in node["aliases"]
    assert "sentence transformer" in node["aliases"]


def test_build_links_semantic_nodes_to_code_nodes():
    extraction = {
        "nodes": [
            {"id": "api_client_code", "label": "ApiClient", "file_type": "code", "source_file": "client.py"},
            {"id": "api_client_guide", "label": "API Client Guide", "file_type": "document", "source_file": "README.md"},
        ],
        "edges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }

    G = build_from_json(extraction, directed=True)

    assert G.has_edge("apiclient", "apiclientguide")
    assert G.edges["apiclient", "apiclientguide"]["relation"] == "implements"


def test_build_resolves_fuzzy_duplicate_entities():
    extraction = {
        "nodes": [
            {"id": "api_client_code", "label": "ApiClient", "file_type": "code", "source_file": "client.py"},
            {"id": "api_client_doc", "label": "API Client", "file_type": "document", "source_file": "README.md"},
        ],
        "edges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }

    G = build_from_json(extraction, directed=True)

    assert len(G.nodes) == 1
    assert "apiclient" in G


def test_build_links_parenthetical_code_descriptions_to_semantic_nodes():
    extraction = {
        "nodes": [
            {
                "id": "enrich_document",
                "label": "enrich_document (index keywords, find cross-references)",
                "file_type": "code",
                "source_file": "worked/example/raw/processor.py",
            },
            {
                "id": "cross_references",
                "label": "Cross-references",
                "file_type": "document",
                "source_file": "worked/example/raw/architecture.md",
            },
        ],
        "edges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }

    G = build_from_json(extraction, directed=True)

    assert "enrichdocument" in G
    assert "crossreferences" in G
    assert G.has_edge("enrichdocument", "crossreferences")
    assert G.edges["enrichdocument", "crossreferences"]["relation"] == "implements"


def test_build_preserves_existing_edges_while_remapping_to_canonical_ids():
    extraction = {
        "nodes": [
            {"id": "n_transformer", "label": "Transformer", "file_type": "code", "source_file": "model.py"},
            {"id": "n_attention", "label": "MultiHeadAttention", "file_type": "code", "source_file": "model.py"},
        ],
        "edges": [
            {"source": "n_transformer", "target": "n_attention", "relation": "contains", "confidence": "EXTRACTED", "source_file": "model.py", "weight": 1.0},
        ],
        "input_tokens": 0,
        "output_tokens": 0,
    }

    G = build_from_json(extraction, directed=True)

    assert G.has_edge("transformer", "multiheadattention")
    assert G.edges["transformer", "multiheadattention"]["relation"] == "contains"
