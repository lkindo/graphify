from pathlib import Path

import pytest

from graphify.extract import collect_files, extract
from graphify.pdf_extract import (
    _extract_references,
    _is_heading,
    _make_id,
    extract_pdf,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_PDF = FIXTURES / "sample.pdf"


def test_make_id_normalizes_strings():
    assert _make_id("Sample", "Table 1") == "sample_table_1"


def test_heading_detection_numbered():
    assert _is_heading("1.2 Model Architecture") == ("1.2", "Model Architecture")


def test_heading_detection_known_heading():
    assert _is_heading("Abstract") == ("", "Abstract")


def test_extract_references_finds_doi_and_arxiv():
    refs = _extract_references("DOI 10.1234/fake.5678 and arXiv: 1706.03762")
    values = {r["value"] for r in refs}
    assert "10.1234/fake.5678" in values
    assert "1706.03762" in values


def test_extract_pdf_returns_schema():
    result = extract_pdf(SAMPLE_PDF)
    assert "nodes" in result and "edges" in result
    assert result["input_tokens"] == 0
    assert result["output_tokens"] == 0


def test_extract_pdf_includes_file_node():
    result = extract_pdf(SAMPLE_PDF)
    file_nodes = [n for n in result["nodes"] if n.get("file_type") == "paper"]
    assert any(n["id"] == "sample" for n in file_nodes)


def test_extract_pdf_extracts_sections():
    result = extract_pdf(SAMPLE_PDF)
    labels = {n["label"].lower() for n in result["nodes"]}
    assert "abstract" in labels
    assert any("introduction" in l for l in labels)


def test_extract_pdf_extracts_citation_edges():
    result = extract_pdf(SAMPLE_PDF)
    cite_edges = [e for e in result["edges"] if e["relation"] == "cites"]
    assert len(cite_edges) >= 2
    assert all(e["confidence"] == "EXTRACTED" for e in cite_edges)


def test_collect_files_includes_pdf():
    files = collect_files(FIXTURES)
    assert SAMPLE_PDF in files


def test_extract_dispatch_includes_pdf_nodes():
    result = extract([SAMPLE_PDF])
    assert len(result["nodes"]) > 0
    assert result["input_tokens"] == 0
    assert result["output_tokens"] == 0


def test_extract_pdf_empty_text(monkeypatch):
    import graphify.pdf_extract as mod

    monkeypatch.setattr(mod, "_extract_metadata", lambda _: {"title": None, "author": None, "page_count": 0})
    monkeypatch.setattr("graphify.detect.extract_pdf_text", lambda _: "")
    result = extract_pdf(SAMPLE_PDF)
    assert result == {"nodes": [], "edges": [], "input_tokens": 0, "output_tokens": 0}


def test_table_extraction_degrades_without_pdfplumber(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pdfplumber":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = extract_pdf(SAMPLE_PDF)
    assert any(n["id"] == "sample" for n in result["nodes"])


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample fixture not generated")
def test_sample_pdf_fixture_exists():
    assert SAMPLE_PDF.exists()
