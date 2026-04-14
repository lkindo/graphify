from pathlib import Path


def test_windows_launchers_exist_and_prefer_local_python():
    root = Path(__file__).resolve().parents[1]
    cmd = root / "graphify.cmd"
    ps1 = root / "graphify.ps1"

    assert cmd.exists()
    assert ps1.exists()

    cmd_text = cmd.read_text(encoding="utf-8")
    assert "-m graphify" in cmd_text
    assert "py -3" in cmd_text
    assert "python" in cmd_text

    ps1_text = ps1.read_text(encoding="utf-8")
    assert ".venv\\Scripts\\python.exe" in ps1_text
    assert "py" in ps1_text
    assert "-m graphify" in ps1_text


def test_readme_mentions_windows_source_checkout():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert "Run from a cloned checkout on Windows" in readme
    assert ".\\graphify.ps1 update ." in readme
    assert "graphify.cmd update ." in readme
