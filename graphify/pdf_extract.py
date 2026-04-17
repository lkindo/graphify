from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _make_id(*parts: str) -> str:
    """Build a stable node ID from one or more name parts."""
    combined = "_".join(p.strip("_.") for p in parts if p)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", combined)
    return cleaned.strip("_").lower()


_HEADING_PATTERNS = [
    re.compile(r"^(\d+(?:\.\d+)*)\.?\s+([A-Z].+)$"),
    re.compile(r"^((?:CHAPTER|SECTION)\s+\w+)[:\s]+(.+)$", re.IGNORECASE),
    re.compile(r"^(APPENDIX\s+\w+)[:\s]+(.+)$", re.IGNORECASE),
]

_KNOWN_HEADINGS = {
    "abstract", "introduction", "background", "related work",
    "methodology", "methods", "method", "approach", "model",
    "architecture", "design", "implementation",
    "experiments", "experiment", "evaluation", "results",
    "discussion", "analysis", "conclusion", "conclusions",
    "future work", "acknowledgments", "acknowledgements",
    "references", "bibliography", "appendix",
    "overview", "motivation", "problem statement",
    "summary", "table of contents", "contents",
    "executive summary", "scope", "objectives",
    "requirements", "specifications", "glossary",
    "terms and conditions", "definitions",
}


def _is_heading(line: str) -> tuple[str, str] | None:
    """Return (section_number, title) if line looks like a heading, else None."""
    stripped = line.strip()
    if not stripped or len(stripped) > 200:
        return None
    for pat in _HEADING_PATTERNS:
        m = pat.match(stripped)
        if m:
            return (m.group(1).strip(), m.group(2).strip())
    lower = stripped.lower().rstrip(":")
    if lower in _KNOWN_HEADINGS:
        return ("", stripped)
    if stripped.isupper() and 3 <= len(stripped) <= 80 and " " in stripped:
        return ("", stripped.title())
    return None


_DOI_PATTERN = re.compile(r"10\.\d{4,}/[^\s]+")
_ARXIV_PATTERN = re.compile(r"\d{4}\.\d{4,5}")


def _extract_references(text: str) -> list[dict[str, Any]]:
    """Pull out DOIs and arXiv IDs from the text."""
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in _DOI_PATTERN.finditer(text):
        doi = m.group(0).rstrip(".,;)")
        if doi not in seen:
            seen.add(doi)
            refs.append({"type": "doi", "value": doi})
    for m in _ARXIV_PATTERN.finditer(text):
        aid = m.group(0)
        if aid not in seen:
            seen.add(aid)
            refs.append({"type": "arxiv", "value": aid})
    return refs


def _extract_tables_pdfplumber(path: Path) -> list[dict[str, Any]]:
    """Try pdfplumber for table extraction and return table dicts."""
    try:
        import pdfplumber
    except ImportError:
        return []
    tables_out: list[dict[str, Any]] = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                for table in page.extract_tables():
                    if not table or len(table) < 2:
                        continue
                    header = [str(c or "").strip() for c in table[0]]
                    rows = [[str(c or "").strip() for c in row] for row in table[1:]]
                    tables_out.append({
                        "page": page_num,
                        "header": header,
                        "rows": rows,
                        "row_count": len(rows),
                    })
    except Exception:
        pass
    return tables_out


def _extract_metadata(path: Path) -> dict[str, Any]:
    """Pull PDF metadata (title, author, subject, creator, page_count) via pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        meta = reader.metadata or {}
        return {
            "title": getattr(meta, "title", None) or None,
            "author": getattr(meta, "author", None) or None,
            "subject": getattr(meta, "subject", None) or None,
            "creator": getattr(meta, "creator", None) or None,
            "page_count": len(reader.pages),
        }
    except Exception:
        return {
            "title": None,
            "author": None,
            "subject": None,
            "creator": None,
            "page_count": 0,
        }


def extract_pdf(path: Path) -> dict:
    """Extract structured nodes and edges from a PDF file locally."""
    from .detect import extract_pdf_text

    text = extract_pdf_text(path)
    if not text.strip():
        return {"nodes": [], "edges": [], "input_tokens": 0, "output_tokens": 0}

    stem = path.stem
    str_path = str(path)
    file_nid = _make_id(stem)
    nodes: list[dict] = []
    edges: list[dict] = []

    metadata = _extract_metadata(path)
    file_label = metadata.get("title") or stem
    nodes.append({
        "id": file_nid,
        "label": file_label,
        "file_type": "paper",
        "source_file": str_path,
        "source_location": None,
        "pdf_author": metadata.get("author"),
        "pdf_page_count": metadata.get("page_count", 0),
    })

    lines = text.split("\n")
    sections: list[dict[str, Any]] = []
    for line_num, line in enumerate(lines, 1):
        heading = _is_heading(line)
        if heading is None:
            continue
        sec_num, sec_title = heading
        sec_label = f"{sec_num} {sec_title}".strip() if sec_num else sec_title
        sec_nid = _make_id(stem, sec_label)
        if any(n["id"] == sec_nid for n in nodes):
            continue
        sections.append({"nid": sec_nid, "label": sec_label, "line": line_num})
        nodes.append({
            "id": sec_nid,
            "label": sec_label,
            "file_type": "paper",
            "source_file": str_path,
            "source_location": f"L{line_num}",
        })
        edges.append({
            "source": file_nid,
            "target": sec_nid,
            "relation": "contains",
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": str_path,
            "source_location": f"L{line_num}",
            "weight": 1.0,
        })

    for i in range(len(sections) - 1):
        edges.append({
            "source": sections[i]["nid"],
            "target": sections[i + 1]["nid"],
            "relation": "followed_by",
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": str_path,
            "source_location": f"L{sections[i]['line']}",
            "weight": 0.5,
        })

    tables = _extract_tables_pdfplumber(path)
    for idx, table in enumerate(tables):
        header_str = ", ".join(table["header"][:5])
        if len(table["header"]) > 5:
            header_str += "..."
        table_label = f"Table {idx + 1}: {header_str}" if header_str else f"Table {idx + 1}"
        table_nid = _make_id(stem, f"table_{idx + 1}")
        nodes.append({
            "id": table_nid,
            "label": table_label,
            "file_type": "paper",
            "source_file": str_path,
            "source_location": f"p{table['page']}",
            "table_columns": table["header"],
            "table_row_count": table["row_count"],
        })
        edges.append({
            "source": file_nid,
            "target": table_nid,
            "relation": "contains",
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": str_path,
            "source_location": f"p{table['page']}",
            "weight": 1.0,
        })

    refs = _extract_references(text)
    for ref in refs:
        ref_label = f"{ref['type'].upper()}: {ref['value']}"
        ref_nid = _make_id(stem, ref["type"], ref["value"])
        if any(n["id"] == ref_nid for n in nodes):
            continue
        nodes.append({
            "id": ref_nid,
            "label": ref_label,
            "file_type": "paper",
            "source_file": str_path,
            "source_location": None,
        })
        edges.append({
            "source": file_nid,
            "target": ref_nid,
            "relation": "cites",
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": str_path,
            "source_location": None,
            "weight": 1.0,
        })

    return {"nodes": nodes, "edges": edges, "input_tokens": 0, "output_tokens": 0}
