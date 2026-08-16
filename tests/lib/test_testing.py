"""Tests for the shared test-support tree-hashing primitive (issue #1125).

``anvil/lib/testing.py::tree_hash`` consolidates 11 distinct drifted
variants of a directory-snapshot-hashing helper (``_tree_hash`` /
``_tree_digest`` / ``_tree_hashes``) that had accumulated across 28 test
files in 10 skills. This module tests the shared primitive directly; the
28 call sites already have their own behavioral coverage (each skill's
zero-mutation / dry-run / idempotency test suite), which continues to
pass unmodified against the now-imported function.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.testing import tree_hash


def test_empty_dir_hashes_to_empty_dict(tmp_path: Path) -> None:
    assert tree_hash(tmp_path) == {}


def test_same_tree_hashes_equal(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("world")

    assert tree_hash(tmp_path) == tree_hash(tmp_path)


def test_content_change_is_detected(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    before = tree_hash(tmp_path)

    (tmp_path / "a.txt").write_text("goodbye")
    after = tree_hash(tmp_path)

    assert before != after


def test_new_file_is_detected(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    before = tree_hash(tmp_path)

    (tmp_path / "b.txt").write_text("new")
    after = tree_hash(tmp_path)

    assert before != after
    assert "b.txt" in after
    assert "a.txt" in after


def test_empty_subdir_appearing_is_detected(tmp_path: Path) -> None:
    """A directory-only structural change must be visible (issue #1125).

    At least one pre-consolidation variant iterated ``root.rglob("*")``
    but only recorded entries where ``path.is_file()``, so an empty
    subdirectory appearing or disappearing was silently invisible to it.
    The canonical helper must not regress that detection.
    """

    before = tree_hash(tmp_path)

    (tmp_path / "empty_subdir").mkdir()
    after = tree_hash(tmp_path)

    assert before != after


def test_empty_subdir_disappearing_is_detected(tmp_path: Path) -> None:
    (tmp_path / "empty_subdir").mkdir()
    before = tree_hash(tmp_path)

    (tmp_path / "empty_subdir").rmdir()
    after = tree_hash(tmp_path)

    assert before != after


def test_relative_paths_use_posix_separators(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("world")

    snapshot = tree_hash(tmp_path)
    assert "sub/b.txt" in snapshot


def test_exclude_omits_matching_component(tmp_path: Path) -> None:
    (tmp_path / "kept.txt").write_text("keep me")
    excluded_dir = tmp_path / "excluded"
    excluded_dir.mkdir()
    (excluded_dir / "ignored.txt").write_text("ignore me")

    snapshot = tree_hash(tmp_path, exclude="excluded")

    assert "kept.txt" in snapshot
    assert not any("excluded" in key for key in snapshot)


def test_exclude_ignores_writes_under_excluded_dir(tmp_path: Path) -> None:
    (tmp_path / "kept.txt").write_text("keep me")
    excluded_dir = tmp_path / "excluded"
    excluded_dir.mkdir()

    before = tree_hash(tmp_path, exclude="excluded")
    (excluded_dir / "new.txt").write_text("added under excluded dir")
    after = tree_hash(tmp_path, exclude="excluded")

    assert before == after


def test_directory_and_file_entries_cannot_collide(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "sub").mkdir()

    snapshot = tree_hash(tmp_path)

    assert snapshot["a.txt"] != snapshot["sub"]
    assert snapshot["sub"] == "<dir>"
