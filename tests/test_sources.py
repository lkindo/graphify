"""Tests for graphify.sources — source registry CRUD."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from graphify.sources import (
    add_source,
    delete_source,
    list_sources,
    load_sources,
    resolve_source_path,
    save_sources,
)


@pytest.fixture
def sources_file(tmp_path):
    return tmp_path / "graphify-out" / "sources.json"


@pytest.fixture
def corpus_dir(tmp_path):
    d = tmp_path / "my_repo"
    d.mkdir()
    return d


class TestAddSource:
    def test_adds_new_source(self, sources_file, corpus_dir):
        entry = add_source(str(corpus_dir), sources_file)
        assert entry["path"] == str(corpus_dir.resolve())
        assert "inode" in entry
        assert "added" in entry
        sources = load_sources(sources_file)
        assert len(sources) == 1
        assert sources[0]["path"] == str(corpus_dir.resolve())

    def test_stores_inode(self, sources_file, corpus_dir):
        entry = add_source(str(corpus_dir), sources_file)
        assert entry["inode"] == corpus_dir.stat().st_ino

    def test_resolves_relative_path(self, sources_file, corpus_dir):
        # Pass a str that resolves to corpus_dir
        entry = add_source(str(corpus_dir), sources_file)
        assert Path(entry["path"]).is_absolute()

    def test_rejects_nonexistent_path(self, sources_file, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            add_source(str(tmp_path / "ghost"), sources_file)

    def test_rejects_duplicate_path(self, sources_file, corpus_dir):
        add_source(str(corpus_dir), sources_file)
        with pytest.raises(ValueError, match="already registered"):
            add_source(str(corpus_dir), sources_file)

    def test_rejects_duplicate_inode(self, sources_file, corpus_dir, tmp_path):
        # Symlink to same inode — should be rejected
        link = tmp_path / "link_to_repo"
        link.symlink_to(corpus_dir)
        add_source(str(corpus_dir), sources_file)
        with pytest.raises(ValueError, match="already registered"):
            add_source(str(link), sources_file)

    def test_creates_sources_file(self, sources_file, corpus_dir):
        assert not sources_file.exists()
        add_source(str(corpus_dir), sources_file)
        assert sources_file.exists()

    def test_multiple_sources(self, sources_file, tmp_path):
        d1 = tmp_path / "repo1"
        d2 = tmp_path / "repo2"
        d1.mkdir()
        d2.mkdir()
        add_source(str(d1), sources_file)
        add_source(str(d2), sources_file)
        sources = load_sources(sources_file)
        assert len(sources) == 2


class TestDeleteSource:
    def test_removes_existing_source(self, sources_file, corpus_dir):
        add_source(str(corpus_dir), sources_file)
        ok = delete_source(str(corpus_dir), sources_file)
        assert ok is True
        assert load_sources(sources_file) == []

    def test_returns_false_for_missing(self, sources_file, corpus_dir):
        ok = delete_source(str(corpus_dir), sources_file)
        assert ok is False

    def test_removes_by_inode_when_path_matches(self, sources_file, corpus_dir):
        add_source(str(corpus_dir), sources_file)
        ok = delete_source(str(corpus_dir), sources_file)
        assert ok is True

    def test_does_not_remove_wrong_source(self, sources_file, tmp_path):
        d1 = tmp_path / "repo1"
        d2 = tmp_path / "repo2"
        d1.mkdir()
        d2.mkdir()
        add_source(str(d1), sources_file)
        ok = delete_source(str(d2), sources_file)
        assert ok is False
        assert len(load_sources(sources_file)) == 1


class TestResolveSourcePath:
    def test_returns_path_when_exists(self, corpus_dir):
        entry = {"path": str(corpus_dir), "inode": corpus_dir.stat().st_ino}
        assert resolve_source_path(entry) == corpus_dir

    def test_returns_path_without_inode(self, corpus_dir):
        entry = {"path": str(corpus_dir)}
        assert resolve_source_path(entry) == corpus_dir

    def test_returns_none_when_missing_and_no_inode(self, tmp_path):
        ghost = tmp_path / "gone"
        entry = {"path": str(ghost)}
        assert resolve_source_path(entry) is None

    def test_finds_renamed_path_by_inode(self, tmp_path):
        original = tmp_path / "original_name"
        original.mkdir()
        inode = original.stat().st_ino
        entry = {"path": str(original), "inode": inode}

        renamed = tmp_path / "new_name"
        original.rename(renamed)

        result = resolve_source_path(entry)
        assert result == renamed

    def test_returns_none_when_inode_not_found(self, tmp_path):
        ghost = tmp_path / "gone"
        entry = {"path": str(ghost), "inode": 999999999}
        assert resolve_source_path(entry) is None


class TestListSources:
    def test_empty_registry(self, sources_file):
        result = list_sources(sources_file)
        assert result == []

    def test_ok_status(self, sources_file, corpus_dir):
        add_source(str(corpus_dir), sources_file)
        result = list_sources(sources_file)
        assert len(result) == 1
        assert result[0]["status"] == "ok"

    def test_missing_status(self, sources_file, tmp_path):
        # Manually write a source for a path that doesn't exist
        ghost = tmp_path / "ghost_dir"
        save_sources([{"path": str(ghost), "inode": 99999}], sources_file)
        result = list_sources(sources_file)
        assert result[0]["status"] == "missing"

    def test_renamed_status(self, sources_file, tmp_path):
        original = tmp_path / "original"
        original.mkdir()
        inode = original.stat().st_ino
        add_source(str(original), sources_file)

        renamed = tmp_path / "renamed"
        original.rename(renamed)

        result = list_sources(sources_file)
        assert result[0]["status"] == "renamed"
        assert result[0]["current_path"] == str(renamed)

    def test_includes_all_fields(self, sources_file, corpus_dir):
        add_source(str(corpus_dir), sources_file)
        result = list_sources(sources_file)
        entry = result[0]
        assert "path" in entry
        assert "inode" in entry
        assert "added" in entry
        assert "status" in entry
