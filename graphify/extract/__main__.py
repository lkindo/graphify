"""CLI entry point: python -m graphify.extract <file_or_dir> ..."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ._dispatch import collect_files, extract

if len(sys.argv) < 2:
    print("Usage: python -m graphify.extract <file_or_dir> ...", file=sys.stderr)
    sys.exit(1)

paths: list[Path] = []
for arg in sys.argv[1:]:
    paths.extend(collect_files(Path(arg)))

result = extract(paths)
print(json.dumps(result, indent=2))
