"""Helpers for enforcing exact dependency pins in pyproject.toml."""

from __future__ import annotations

from pathlib import Path
import re
import tomllib


_PIN_PATTERN = re.compile(r"^\s*[^=<>!~@\s][^;@]*==\s*[^=,\s]+(?:\s*;.*)?$")


def _iter_dependency_entries(pyproject: dict) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []

    build_requires = pyproject.get("build-system", {}).get("requires", [])
    entries.extend(("build-system.requires", entry) for entry in build_requires)

    project = pyproject.get("project", {})
    entries.extend(("project.dependencies", entry) for entry in project.get("dependencies", []))

    for group_name, deps in project.get("optional-dependencies", {}).items():
        location = f"project.optional-dependencies.{group_name}"
        entries.extend((location, entry) for entry in deps)

    for group_name, deps in pyproject.get("dependency-groups", {}).items():
        location = f"dependency-groups.{group_name}"
        entries.extend((location, entry) for entry in deps)

    return entries


def is_exact_pin(requirement: str) -> bool:
    """Return True when the dependency string uses an exact == pin."""
    return bool(_PIN_PATTERN.match(requirement.strip()))


def find_unpinned_dependencies(pyproject_path: str | Path) -> list[tuple[str, str]]:
    data = tomllib.loads(Path(pyproject_path).read_text())
    return [
        (location, requirement)
        for location, requirement in _iter_dependency_entries(data)
        if not is_exact_pin(requirement)
    ]


def format_unpinned_dependencies(unpinned: list[tuple[str, str]]) -> str:
    lines = ["Found unpinned dependencies:"]
    lines.extend(f"- {location}: {requirement}" for location, requirement in unpinned)
    lines.append("Pin every dependency with == so updates happen only through reviewed changes.")
    return "\n".join(lines)
