#!/usr/bin/env python3
"""Fail if pyproject.toml contains floating dependency specs."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graphify.dependency_policy import find_unpinned_dependencies, format_unpinned_dependencies


def main() -> int:
    pyproject = PROJECT_ROOT / "pyproject.toml"
    unpinned = find_unpinned_dependencies(pyproject)
    if not unpinned:
        print("All dependency declarations use exact pins.")
        return 0

    print(format_unpinned_dependencies(unpinned), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
