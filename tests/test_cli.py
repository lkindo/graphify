from pathlib import Path
from unittest.mock import patch

import pytest

from graphify.__main__ import main


FIXTURES = Path(__file__).parent / "fixtures"


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("graphify ")


def test_install_command_parses_platform():
    with patch("graphify.__main__.install") as install_mock:
        main(["install", "--platform", "codex"])
    install_mock.assert_called_once_with(platform="codex")


def test_build_command_writes_outputs(tmp_path):
    out_dir = tmp_path / "graphify-out"
    main(["build", str(FIXTURES), "--out", str(out_dir), "--no-viz"])
    assert (out_dir / "graph.json").exists()
    assert (out_dir / "GRAPH_REPORT.md").exists()
    assert (out_dir / "manifest.json").exists()
    assert not (out_dir / "graph.html").exists()


def test_build_command_requires_code_files(tmp_path, capsys):
    docs_only = tmp_path / "docs-only"
    docs_only.mkdir()
    (docs_only / "notes.md").write_text("# Notes\n\nNo code here.", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["build", str(docs_only)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "no supported code files found" in err
