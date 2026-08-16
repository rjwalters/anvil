"""Tests for the shared test-support helpers (issues #1125, #1133, #1136).

``anvil/lib/testing.py::tree_hash`` consolidates 11 distinct drifted
variants of a directory-snapshot-hashing helper (``_tree_hash`` /
``_tree_digest`` / ``_tree_hashes``) that had accumulated across 28 test
files in 10 skills. ``anvil/lib/testing.py::parse_frontmatter``
consolidates 10 byte-identical ``dict``-returning adapters over
``anvil.lib.frontmatter.extract_frontmatter`` that had accumulated across
10 more skills' test suites. ``anvil/lib/testing.py::read_text``
consolidates 99 byte-identical ``_read(p_or_path: Path) -> str`` helpers
that had accumulated across the repo's test suites. This module tests
the shared primitives directly; the call sites already have their own
behavioral coverage (each skill's zero-mutation / dry-run / idempotency,
frontmatter-parsing, or doc-content test suite), which continues to pass
unmodified against the now-imported functions.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.testing import parse_frontmatter, read_text, tree_hash


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


def test_parse_frontmatter_returns_dict() -> None:
    text = "---\ntitle: Example\nstage: DRAFT\n---\nbody text\n"
    assert parse_frontmatter(text) == {"title": "Example", "stage": "DRAFT"}


def test_parse_frontmatter_returns_empty_dict_when_absent() -> None:
    """The adapter's whole reason to exist (issue #1083 / #1133).

    ``extract_frontmatter`` returns ``None`` for text with no parseable
    frontmatter block; every consolidated call site wants ``{}`` instead
    so callers can unconditionally ``.get()`` off the result.
    """
    assert parse_frontmatter("no frontmatter here\n") == {}


def test_parse_frontmatter_returns_empty_dict_for_malformed_block() -> None:
    assert parse_frontmatter("---\ntitle: [unterminated\n---\n") == {}


def test_read_text_returns_file_contents(tmp_path: Path) -> None:
    target = tmp_path / "doc.md"
    target.write_text("hello world", encoding="utf-8")

    assert read_text(target) == "hello world"


def test_read_text_decodes_utf8(tmp_path: Path) -> None:
    target = tmp_path / "doc.md"
    target.write_text("café", encoding="utf-8")

    assert read_text(target) == "café"
