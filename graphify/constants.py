# Shared constants - file extensions, thresholds, and configuration values.
# Single source of truth to avoid duplication across detect, analyze, watch, and hooks.
from __future__ import annotations

CODE_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".ts", ".js", ".tsx", ".go", ".rs", ".java",
    ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp",
    ".rb", ".swift", ".kt", ".kts", ".cs", ".scala", ".php",
    ".lua", ".toc", ".zig", ".ps1", ".ex", ".exs", ".m", ".mm",
})

DOC_EXTENSIONS: frozenset[str] = frozenset({".md", ".txt", ".rst"})

PAPER_EXTENSIONS: frozenset[str] = frozenset({".pdf"})

IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
})

OFFICE_EXTENSIONS: frozenset[str] = frozenset({".docx", ".xlsx"})

# Union of all extensions that the watcher should react to
WATCHED_EXTENSIONS: frozenset[str] = CODE_EXTENSIONS | DOC_EXTENSIONS | PAPER_EXTENSIONS | IMAGE_EXTENSIONS
