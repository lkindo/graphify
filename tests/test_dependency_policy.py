import textwrap
from pathlib import Path
import subprocess
import sys

import pytest


def _write_pyproject(tmp_path, body: str):
    path = tmp_path / "pyproject.toml"
    path.write_text(textwrap.dedent(body))
    return path


def test_find_unpinned_dependencies_reports_floating_specs(tmp_path):
    from graphify.dependency_policy import find_unpinned_dependencies

    pyproject = _write_pyproject(
        tmp_path,
        """
        [build-system]
        requires = ["setuptools>=80"]

        [project]
        dependencies = [
            "networkx==3.6.1",
            "faster-whisper",
        ]

        [project.optional-dependencies]
        video = [
            "faster-whisper",
            "graspologic; python_version < '3.13'",
        ]
        """,
    )

    assert find_unpinned_dependencies(pyproject) == [
        ("build-system.requires", "setuptools>=80"),
        ("project.dependencies", "faster-whisper"),
        ("project.optional-dependencies.video", "faster-whisper"),
        ("project.optional-dependencies.video", "graspologic; python_version < '3.13'"),
    ]


def test_find_unpinned_dependencies_accepts_exact_pins_with_markers(tmp_path):
    from graphify.dependency_policy import find_unpinned_dependencies

    pyproject = _write_pyproject(
        tmp_path,
        """
        [build-system]
        requires = ["setuptools==80.9.0"]

        [project]
        dependencies = ["networkx==3.6.1"]

        [project.optional-dependencies]
        video = ["faster-whisper==1.2.1"]
        leiden = ["graspologic==0.3.1; python_version < '3.13'"]

        [dependency-groups]
        dev = ["pytest==9.0.3", "pip-audit==2.10.0"]
        """,
    )

    assert find_unpinned_dependencies(pyproject) == []


def test_format_unpinned_dependencies_is_human_readable():
    from graphify.dependency_policy import format_unpinned_dependencies

    formatted = format_unpinned_dependencies(
        [
            ("project.dependencies", "faster-whisper"),
            ("project.optional-dependencies.video", "graspologic; python_version < '3.13'"),
        ]
    )

    assert "Found unpinned dependencies:" in formatted
    assert "- project.dependencies: faster-whisper" in formatted
    assert "- project.optional-dependencies.video: graspologic; python_version < '3.13'" in formatted


def test_format_unpinned_dependencies_requires_exact_pins():
    from graphify.dependency_policy import format_unpinned_dependencies

    formatted = format_unpinned_dependencies([("build-system.requires", "setuptools>=80")])

    assert "Pin every dependency with ==" in formatted


def test_policy_script_runs_successfully_for_repo_pyproject():
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "scripts/check_pinned_dependencies.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "All dependency declarations use exact pins." in result.stdout
