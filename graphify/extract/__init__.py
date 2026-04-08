"""graphify.extract — deterministic structural extraction from source code using tree-sitter.

This package was refactored from a single 2000+ line module into focused submodules:
  _base.py          — ExtractionContext, LanguageConfig, shared helpers
  _imports.py       — language-specific import handlers
  _configs.py       — LanguageConfig instances and extra walk functions
  _generic.py       — generic AST extractor driven by LanguageConfig
  _go.py            — Go extractor (custom walk)
  _rust.py          — Rust extractor (custom walk)
  _zig.py           — Zig extractor (custom walk)
  _powershell.py    — PowerShell extractor (custom walk)
  _python_extra.py  — Python rationale extraction + cross-file import resolution
  _dispatch.py      — extract(), collect_files(), per-language wrapper functions

All public symbols are re-exported here for backwards compatibility.
"""
from ._base import _make_id, LanguageConfig, ExtractionContext
from ._dispatch import (
    extract,
    collect_files,
    extract_python,
    extract_js,
    extract_java,
    extract_c,
    extract_cpp,
    extract_ruby,
    extract_csharp,
    extract_kotlin,
    extract_scala,
    extract_php,
    extract_lua,
    extract_swift,
)
from ._elixir import extract_elixir
from ._go import extract_go
from ._objc import extract_objc
from ._rust import extract_rust
from ._zig import extract_zig
from ._powershell import extract_powershell

__all__ = [
    "extract",
    "collect_files",
    "_make_id",
    "LanguageConfig",
    "ExtractionContext",
    "extract_python",
    "extract_js",
    "extract_java",
    "extract_c",
    "extract_cpp",
    "extract_ruby",
    "extract_csharp",
    "extract_kotlin",
    "extract_scala",
    "extract_php",
    "extract_lua",
    "extract_swift",
    "extract_elixir",
    "extract_go",
    "extract_objc",
    "extract_rust",
    "extract_zig",
    "extract_powershell",
]
