"""Tests for graphify CLI graph path validation."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import networkx as nx
import pytest
from networkx.readwrite import json_graph

from graphify.__main__ import main


def _make_graph() -> nx.Graph:
    G = nx.Graph()
    G.add_node("n1", label="authentication", source_file="auth.py", source_location="L1", community=0)
    G.add_node("n2", label="api_handler", source_file="api.py", source_location="L5", community=0)
    G.add_edge("n1", "n2", relation="calls", confidence="EXTRACTED")
    return G


def _write_graph(path: Path) -> None:
    data = json_graph.node_link_data(_make_graph(), edges="links")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_query_reads_graph_from_graphify_out(tmp_path, monkeypatch, capsys):
    graph_path = tmp_path / "graphify-out" / "graph.json"
    _write_graph(graph_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["graphify", "query", "authentication"])

    main()

    out = capsys.readouterr().out
    assert "authentication" in out


def test_query_rejects_graph_outside_graphify_out(tmp_path, monkeypatch, capsys):
    (tmp_path / "graphify-out").mkdir()
    outside_path = tmp_path / "outside.json"
    _write_graph(outside_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["graphify", "query", "authentication", "--graph", str(outside_path)])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "Only paths inside graphify-out/" in err


def test_benchmark_rejects_graph_outside_graphify_out(tmp_path, monkeypatch, capsys):
    (tmp_path / "graphify-out").mkdir()
    outside_path = tmp_path / "outside.json"
    _write_graph(outside_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["graphify", "benchmark", str(outside_path)])

    with patch("graphify.benchmark.run_benchmark") as mock_run_benchmark, patch("graphify.benchmark.print_benchmark") as mock_print_benchmark:
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1
    mock_run_benchmark.assert_not_called()
    mock_print_benchmark.assert_not_called()
    err = capsys.readouterr().err
    assert "Only paths inside graphify-out/" in err
