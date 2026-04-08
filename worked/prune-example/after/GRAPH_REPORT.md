# Graph Report - worked/prune-example/after/raw  (2026-04-08)

## Corpus Check
- 3 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 42 nodes · 51 edges · 13 communities detected
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `parse_file()` - 6 edges
2. `enrich_document()` - 5 edges
3. `parse_and_save()` - 4 edges
4. `extract_keywords()` - 4 edges
5. `process_and_save()` - 4 edges
6. `parse_markdown()` - 3 edges
7. `parse_json()` - 3 edges
8. `parse_plaintext()` - 3 edges
9. `batch_parse()` - 3 edges
10. `normalize_text()` - 3 edges

## Surprising Connections (you probably didn't know these)
- `parse_file()` --calls--> `parse_json()`  [INFERRED]
  worked/prune-example/after/raw/parser.py → worked/prune-example/after/raw/parser.py  _Bridges community 2 → community 12_
- `parse_file()` --calls--> `parse_plaintext()`  [INFERRED]
  worked/prune-example/after/raw/parser.py → worked/prune-example/after/raw/parser.py  _Bridges community 2 → community 3_
- `parse_and_save()` --calls--> `parse_file()`  [INFERRED]
  worked/prune-example/after/raw/parser.py → worked/prune-example/after/raw/parser.py  _Bridges community 2 → community 4_
- `enrich_document()` --calls--> `extract_keywords()`  [INFERRED]
  worked/prune-example/after/raw/processor.py → worked/prune-example/after/raw/processor.py  _Bridges community 0 → community 5_
- `process_and_save()` --calls--> `enrich_document()`  [INFERRED]
  worked/prune-example/after/raw/processor.py → worked/prune-example/after/raw/processor.py  _Bridges community 5 → community 6_

## Communities

### Community 0 - "Community 0"
Cohesion: 0.4
Nodes (5): extract_keywords(), normalize_text(), Processor module - transforms validated documents into enriched records ready fo, Lowercase, strip extra whitespace, remove control characters., Pull non-stopword tokens from text, deduplicated.

### Community 1 - "Community 1"
Cohesion: 0.5
Nodes (3): handle_upload(), API module - exposes the document pipeline over HTTP. Thin layer over parser, va, Accept a list of file paths, run the full pipeline on each,     and return a sum

### Community 2 - "Community 2"
Cohesion: 0.5
Nodes (4): parse_file(), parse_markdown(), Read a file from disk and return a structured document., Extract title, sections, and links from markdown.

### Community 3 - "Community 3"
Cohesion: 0.5
Nodes (3): parse_plaintext(), Parser module - reads raw input documents and converts them into a structured fo, Split plaintext into paragraphs.

### Community 4 - "Community 4"
Cohesion: 0.5
Nodes (4): batch_parse(), parse_and_save(), Full pipeline: parse, validate, save. Returns the saved record ID., Parse a list of files and return their record IDs.

### Community 5 - "Community 5"
Cohesion: 0.5
Nodes (4): enrich_document(), find_cross_references(), Add keyword index and cross-references to a validated document., Look up the index and return IDs of related documents by keyword overlap.

### Community 6 - "Community 6"
Cohesion: 0.5
Nodes (4): process_and_save(), Enrich a validated document and persist it. Returns the record ID., Re-enrich all records in the index. Returns count of records updated., reprocess_all()

### Community 7 - "Community 7"
Cohesion: 1.0
Nodes (2): handle_enrich(), Re-enrich a document to pick up new cross-references.

### Community 8 - "Community 8"
Cohesion: 1.0
Nodes (2): handle_delete(), Delete a document by ID.

### Community 9 - "Community 9"
Cohesion: 1.0
Nodes (2): handle_search(), Simple keyword search over the index.     Returns documents whose keyword list o

### Community 10 - "Community 10"
Cohesion: 1.0
Nodes (2): handle_get(), Fetch a document by ID and return it.

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (2): handle_list(), List all document IDs in storage.

### Community 12 - "Community 12"
Cohesion: 1.0
Nodes (2): parse_json(), Parse a JSON document into a structured dict.

## Knowledge Gaps
- **21 isolated node(s):** `API module - exposes the document pipeline over HTTP. Thin layer over parser, va`, `Accept a list of file paths, run the full pipeline on each,     and return a sum`, `Fetch a document by ID and return it.`, `Delete a document by ID.`, `List all document IDs in storage.` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 7`** (2 nodes): `handle_enrich()`, `Re-enrich a document to pick up new cross-references.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 8`** (2 nodes): `handle_delete()`, `Delete a document by ID.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 9`** (2 nodes): `handle_search()`, `Simple keyword search over the index.     Returns documents whose keyword list o`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 10`** (2 nodes): `handle_get()`, `Fetch a document by ID and return it.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (2 nodes): `handle_list()`, `List all document IDs in storage.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (2 nodes): `parse_json()`, `Parse a JSON document into a structured dict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `parse_file()` connect `Community 2` to `Community 3`, `Community 12`, `Community 4`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `enrich_document()` connect `Community 5` to `Community 0`, `Community 6`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `parse_and_save()` connect `Community 4` to `Community 2`, `Community 3`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `parse_file()` (e.g. with `parse_markdown()` and `parse_json()`) actually correct?**
  _`parse_file()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `enrich_document()` (e.g. with `extract_keywords()` and `find_cross_references()`) actually correct?**
  _`enrich_document()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `parse_and_save()` (e.g. with `parse_file()` and `batch_parse()`) actually correct?**
  _`parse_and_save()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `extract_keywords()` (e.g. with `normalize_text()` and `enrich_document()`) actually correct?**
  _`extract_keywords()` has 2 INFERRED edges - model-reasoned connections that need verification._