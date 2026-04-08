# Graph Report - worked/prune-example/before/raw  (2026-04-08)

## Corpus Check
- 5 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 73 nodes · 112 edges · 5 communities detected
- Extraction: 68% EXTRACTED · 32% INFERRED · 0% AMBIGUOUS · INFERRED: 36 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `ValidationError` - 11 edges
2. `_ensure_storage()` - 7 edges
3. `load_index()` - 7 edges
4. `parse_file()` - 6 edges
5. `save_index()` - 6 edges
6. `validate_document()` - 6 edges
7. `enrich_document()` - 5 edges
8. `save_parsed()` - 5 edges
9. `save_processed()` - 5 edges
10. `delete_record()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `API module - exposes the document pipeline over HTTP. Thin layer over parser, va` --uses--> `ValidationError`  [INFERRED]
  worked/prune-example/before/raw/api.py → worked/prune-example/before/raw/validator.py
- `Accept a list of file paths, run the full pipeline on each,     and return a sum` --uses--> `ValidationError`  [INFERRED]
  worked/prune-example/before/raw/api.py → worked/prune-example/before/raw/validator.py
- `Fetch a document by ID and return it.` --uses--> `ValidationError`  [INFERRED]
  worked/prune-example/before/raw/api.py → worked/prune-example/before/raw/validator.py
- `Delete a document by ID.` --uses--> `ValidationError`  [INFERRED]
  worked/prune-example/before/raw/api.py → worked/prune-example/before/raw/validator.py
- `List all document IDs in storage.` --uses--> `ValidationError`  [INFERRED]
  worked/prune-example/before/raw/api.py → worked/prune-example/before/raw/validator.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.21
Nodes (16): delete_record(), _ensure_storage(), list_records(), load_index(), load_record(), Storage module - persists documents to disk and maintains the search index. All, Load the full document index from disk., Persist the index to disk. (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.17
Nodes (15): handle_delete(), handle_enrich(), handle_get(), handle_list(), handle_search(), handle_upload(), API module - exposes the document pipeline over HTTP. Thin layer over parser, va, Accept a list of file paths, run the full pipeline on each,     and return a sum (+7 more)

### Community 2 - "Community 2"
Cohesion: 0.2
Nodes (13): batch_parse(), parse_and_save(), parse_file(), parse_json(), parse_markdown(), parse_plaintext(), Parser module - reads raw input documents and converts them into a structured fo, Read a file from disk and return a structured document. (+5 more)

### Community 3 - "Community 3"
Cohesion: 0.2
Nodes (13): enrich_document(), extract_keywords(), find_cross_references(), normalize_text(), process_and_save(), Processor module - transforms validated documents into enriched records ready fo, Lowercase, strip extra whitespace, remove control characters., Pull non-stopword tokens from text, deduplicated. (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.23
Nodes (11): check_format(), check_required_fields(), normalize_fields(), Validator module - checks that parsed documents meet schema requirements before, Run all validation checks on a parsed document. Raises ValidationError on failur, Raise if any required field is missing., Raise if the format is not in the allowed list., Clean up text fields using the processor. (+3 more)

## Knowledge Gaps
- **28 isolated node(s):** `Parser module - reads raw input documents and converts them into a structured fo`, `Read a file from disk and return a structured document.`, `Extract title, sections, and links from markdown.`, `Parse a JSON document into a structured dict.`, `Split plaintext into paragraphs.` (+23 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ValidationError` connect `Community 1` to `Community 4`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `ValidationError` (e.g. with `check_required_fields()` and `check_format()`) actually correct?**
  _`ValidationError` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `_ensure_storage()` (e.g. with `load_index()` and `save_index()`) actually correct?**
  _`_ensure_storage()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `load_index()` (e.g. with `_ensure_storage()` and `save_parsed()`) actually correct?**
  _`load_index()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `parse_file()` (e.g. with `parse_markdown()` and `parse_json()`) actually correct?**
  _`parse_file()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `save_index()` (e.g. with `_ensure_storage()` and `save_parsed()`) actually correct?**
  _`save_index()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Parser module - reads raw input documents and converts them into a structured fo`, `Read a file from disk and return a structured document.`, `Extract title, sections, and links from markdown.` to the rest of the system?**
  _28 weakly-connected nodes found - possible documentation gaps or missing edges._