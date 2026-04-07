# Objective-C Support Design

**Date:** 2026-04-07

**Goal:** Add first-pass Objective-C support to graphify so mixed iOS repositories that use Swift + Objective-C can be discovered and graphed without dropping the Objective-C portion of the codebase.

## Scope

This design targets the "mixed engineering repo first" use case rather than full Objective-C semantic analysis.

In scope:
- Discover `.m` and `.h` files as code inputs
- Parse Objective-C structure with `tree-sitter`
- Extract class, protocol, method, inheritance, and import structure
- Merge extracted Objective-C entities into the existing graph pipeline
- Preserve existing behavior for Java, Kotlin, and Swift extraction

Out of scope for the first version:
- Full `.mm` Objective-C++ support
- Complete Objective-C call graph extraction
- Fine-grained modeling for categories, properties, ivars, and macros
- Deep Swift/Objective-C bridge analysis

## Recommended Approach

Use the existing `LanguageConfig + _extract_generic()` framework in
[`graphify/extract.py`](../../graphify/extract.py) and add an Objective-C language configuration plus an `extract_objc()` entrypoint.

This keeps Objective-C on the same implementation path as Java, Kotlin, Swift, and the other AST-backed languages instead of introducing a second parser pipeline.

## Required Code Changes

### 1. File discovery

Update [`graphify/detect.py`](../../graphify/detect.py):
- Add `.m` to `CODE_EXTENSIONS`
- Keep `.h` classified as code because it is already supported today

Update [`graphify/extract.py`](../../graphify/extract.py):
- Add `.m` to `collect_files()`
- Route `.m` to the Objective-C extractor in `_DISPATCH`
- Do not blindly reroute all `.h` files to Objective-C
- Add a content-aware header routing step so C/C++ headers keep their current extractor path while Objective-C headers can be parsed as Objective-C

### 2. Parser dependency

Update [`pyproject.toml`](../../pyproject.toml):
- Add an Objective-C `tree-sitter` Python package dependency

Selection criteria:
- Python package exposes a usable language handle
- Maintained grammar with acceptable license
- Parses common `.m` and `.h` Objective-C syntax reliably

### 3. AST extraction

Update [`graphify/extract.py`](../../graphify/extract.py):
- Add `_OBJC_CONFIG`
- Add Objective-C import handling for `#import` and `@import`
- Add `extract_objc(path: Path) -> dict`
- Add a small header classifier such as `_looks_like_objc_header(path)` or equivalent content sniffing logic

The first version should extract:
- Class nodes from `@interface` and `@implementation`
- Protocol nodes from `@protocol`
- Method nodes from instance and class methods
- Inheritance edges for superclass and protocol inheritance
- Import edges for imported headers and frameworks
- Containment edges between classes or protocols and methods

### 4. Data model mapping

Reuse the current node and edge schema:
- class/protocol/method nodes use existing node shapes
- `imports`, `inherits`, `contains`, and `method` edges reuse existing relation types

For protocol adoption such as `@interface Foo : NSObject <BarDelegate>`:
- Prefer mapping to an existing relation type in the first version
- Avoid introducing a brand-new exported edge type unless clearly necessary

### 5. Testing

Add fixtures:
- `tests/fixtures/sample.h`
- `tests/fixtures/sample.m`

Add tests:
- Objective-C file discovery tests for `.m`
- Header routing tests that prove:
  - Objective-C headers are routed to the Objective-C extractor
  - existing C/C++ headers still use the current extractor path
- Extractor tests for class, protocol, method, import, and inheritance extraction
- Dispatch tests to confirm `.m` and `.h` are routed correctly
- Regression coverage to confirm no behavior change for existing Java/Kotlin/Swift support

## Parsing Rules For Version 1

Version 1 should favor stable structural extraction over deep semantic completeness.

Expected behaviors:
- Extract class names from `@interface` and `@implementation`
- Extract protocol names from `@protocol`
- Extract selector-style method names such as `tableView:didSelectRowAtIndexPath:`
- Extract superclass names
- Extract adopted protocol names when easy to identify
- Extract imports from local and framework headers

Graceful degradations:
- If a class appears only in `.m`, still emit it
- If a header contains only declarations, still emit structure nodes
- Categories may be flattened into the owning class for the first version
- Dynamic runtime behavior is ignored

## Risks

- The largest implementation risk is the exact AST shape exposed by the Objective-C grammar
- Header routing is a compatibility risk because `.h` is already used by the C extractor today
- Header and implementation separation may make entity stitching looser than in Swift or Java
- Objective-C's dynamic dispatch model makes high-confidence call graph extraction hard; it should not be a first-version goal
- `.mm` support should be treated as a follow-up feature, not a first-version acceptance criterion

## Success Criteria

The feature is successful when a mixed Swift + Objective-C iOS repository can be scanned and the Objective-C portion contributes usable graph structure:
- classes
- protocols
- methods
- inheritance
- imports

without regressing the current Java, Kotlin, or Swift extraction paths.
