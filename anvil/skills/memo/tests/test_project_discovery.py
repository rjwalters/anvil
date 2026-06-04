"""Tests for ``anvil.skills.memo.lib.project_discovery`` (issue #284).

Covers the dual-layout thread-root discovery shipped as sub-deliverable
1 of #283: the classic siblings-under-portfolio layout and the new
project-as-thread-root layout (project BRIEF with non-empty
``documents:`` list).

Test coverage map (from issue #284 AC list):

- **Classic-only layout** — every existing memo thread layout returns
  the expected ``LAYOUT_CLASSIC`` result (backwards compatibility AC).
- **Project-BRIEF-only layout** — a project with a BRIEF.md containing
  a non-empty ``documents:`` list returns ``LAYOUT_PROJECT_BRIEF`` for
  every listed slug.
- **Mixed layout** — a project BRIEF coexisting with a classic thread
  elsewhere on the filesystem: each path resolves to the layout that
  matches its own tree, independently.
- **Missing BRIEF** — a project-style directory shape without a
  BRIEF.md falls back to classic discovery (the tree is just nested
  classic threads).
- **BRIEF with empty `documents:` list** — does NOT trigger
  project-brief layout; falls back to classic discovery. This is the
  load-bearing layout-precedence gate from the issue body.
- **Layout-precedence edge case (Open Question #6)** — when both a
  per-thread BRIEF and a project BRIEF could match (e.g., a project
  has only one document and the author authored both shapes),
  project-brief wins if its ``documents:`` list is non-empty AND lists
  this thread's slug; classic otherwise.
- **Walk-upward from nested path** — discovery from a file inside a
  version dir resolves to the same thread root as discovery from the
  thread root itself.
- **No thread found** — a path that is neither under a thread nor
  inside a project returns ``None``.

Tests use ``tmp_path`` per test for the directory skeleton, plus an
on-disk fixture under ``fixtures/project_brief/`` that mirrors the
Studio canary's intended five-document project shape (regression
anchor for sub-deliverables 2/3 when they wire the BRIEF parser and
overlay selection).

Per the #58 packaging convention, this file's filename
(``test_project_discovery.py``) is unique across the
``anvil/skills/*/tests/`` tree so the cross-skill pytest discovery
does not collide on basename.

Runs under either ``python -m unittest discover anvil/skills/memo/tests/``
or ``pytest anvil/skills/memo/tests/``.
"""

from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


# The memo skill keeps its lib modules under its own ``lib/`` per the
# CLAUDE.md "skill-local first, lib promotion later" pattern. Add it to
# ``sys.path`` so tests import without a package install step — mirrors
# ``test_anvil_config.py`` and ``test_refs_resolver.py`` exactly.
_HERE = Path(__file__).resolve().parent
_LIB = _HERE.parent / "lib"
sys.path.insert(0, str(_LIB))

from project_discovery import (  # noqa: E402
    BRIEF_FILENAME,
    DOCUMENTS_FRONTMATTER_KEY,
    DiscoveryResult,
    LAYOUT_CLASSIC,
    LAYOUT_PROJECT_BRIEF,
    discover_thread_root,
    has_project_brief,
)


_FIXTURES = _HERE / "fixtures" / "project_brief"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_project_brief(directory: Path, documents_yaml: str) -> Path:
    """Write a project BRIEF.md with the given ``documents:`` YAML body.

    ``documents_yaml`` is inserted under the ``documents:`` key in the
    frontmatter. Pass a YAML list literal (``"[]"`` for empty) or a
    multi-line block.
    """
    directory.mkdir(parents=True, exist_ok=True)
    brief = directory / BRIEF_FILENAME
    brief.write_text(
        textwrap.dedent(
            f"""\
            ---
            project: fixture-project
            audience: [test]
            documents: {documents_yaml}
            ---

            # Project BRIEF (fixture)
            """
        ),
        encoding="utf-8",
    )
    return brief


def _make_classic_thread(parent: Path, name: str, num_versions: int = 1) -> Path:
    """Create ``<parent>/<name>/`` with a per-thread BRIEF and N version dirs."""
    thread = parent / name
    thread.mkdir(parents=True, exist_ok=True)
    (thread / BRIEF_FILENAME).write_text(
        "---\ncompany: test\n---\n\n# Per-thread BRIEF (classic)\n",
        encoding="utf-8",
    )
    for i in range(1, num_versions + 1):
        v = thread / f"{name}.{i}"
        v.mkdir(parents=True, exist_ok=True)
        (v / "memo.md").write_text("# memo body\n", encoding="utf-8")
    return thread


def _make_project_slug_dir(project: Path, slug: str, num_versions: int = 1) -> Path:
    """Create ``<project>/<slug>/`` with N version dirs but no per-thread BRIEF."""
    sd = project / slug
    sd.mkdir(parents=True, exist_ok=True)
    for i in range(1, num_versions + 1):
        v = sd / f"{slug}.{i}"
        v.mkdir(parents=True, exist_ok=True)
        (v / "memo.md").write_text("# memo body\n", encoding="utf-8")
    return sd


class _TmpRootBase(unittest.TestCase):
    """Per-test temp dir; subclasses build the on-disk skeleton in ``setUp``."""

    def setUp(self) -> None:
        self._td = TemporaryDirectory()
        self.root = Path(self._td.name)
        self.addCleanup(self._td.cleanup)


# ---------------------------------------------------------------------------
# has_project_brief — the layout-precedence gate
# ---------------------------------------------------------------------------


class TestHasProjectBrief(_TmpRootBase):
    """``has_project_brief`` returns True only when documents: is non-empty list."""

    def test_no_brief_at_all(self) -> None:
        d = self.root / "empty"
        d.mkdir()
        self.assertFalse(has_project_brief(d))

    def test_brief_with_nonempty_documents(self) -> None:
        d = self.root / "project"
        _write_project_brief(d, "[{slug: memo-a, artifact_type: investment-memo}]")
        self.assertTrue(has_project_brief(d))

    def test_brief_with_empty_documents_list_returns_false(self) -> None:
        """A BRIEF with ``documents: []`` does NOT trigger project-brief layout.

        AC from issue #284: "BRIEF with empty ``documents:`` list" is the
        edge case that must fall back to classic. This is the layout-
        precedence gate from the issue body.
        """
        d = self.root / "project"
        _write_project_brief(d, "[]")
        self.assertFalse(has_project_brief(d))

    def test_brief_with_documents_absent_returns_false(self) -> None:
        """A BRIEF with no ``documents:`` key at all returns False.

        This is the classic per-thread BRIEF shape — no documents list
        means it's a single-thread BRIEF, not a project BRIEF.
        """
        d = self.root / "thread"
        d.mkdir()
        (d / BRIEF_FILENAME).write_text(
            "---\ncompany: foo\n---\n\n# Per-thread BRIEF\n",
            encoding="utf-8",
        )
        self.assertFalse(has_project_brief(d))

    def test_brief_with_documents_as_string_returns_false(self) -> None:
        """A non-list ``documents:`` value (string, dict, scalar) returns False."""
        d = self.root / "project"
        _write_project_brief(d, "memo-a")  # scalar, not list
        self.assertFalse(has_project_brief(d))

    def test_brief_with_no_frontmatter_returns_false(self) -> None:
        d = self.root / "thread"
        d.mkdir()
        (d / BRIEF_FILENAME).write_text("# Just a BRIEF with no frontmatter\n", encoding="utf-8")
        self.assertFalse(has_project_brief(d))

    def test_brief_with_malformed_yaml_returns_false(self) -> None:
        """Malformed YAML degrades to False (absence-tolerant)."""
        d = self.root / "thread"
        d.mkdir()
        (d / BRIEF_FILENAME).write_text(
            "---\ndocuments: [unclosed list\n---\n\n# BRIEF\n",
            encoding="utf-8",
        )
        self.assertFalse(has_project_brief(d))

    def test_brief_is_a_directory_not_file_returns_false(self) -> None:
        """Defensive: BRIEF.md as a directory (broken setup) returns False."""
        d = self.root / "thread"
        d.mkdir()
        (d / BRIEF_FILENAME).mkdir()
        self.assertFalse(has_project_brief(d))


# ---------------------------------------------------------------------------
# Classic-only layout
# ---------------------------------------------------------------------------


class TestClassicLayout(_TmpRootBase):
    """Every existing memo thread layout returns LAYOUT_CLASSIC.

    Backwards-compat AC: byte-identical behavior for every classic
    thread that exists today.
    """

    def test_classic_thread_from_thread_root(self) -> None:
        portfolio = self.root / "portfolio"
        thread = _make_classic_thread(portfolio, "demo-memo")
        result = discover_thread_root(thread)
        self.assertIsNotNone(result)
        assert result is not None  # for type narrowing
        self.assertEqual(result.thread_root, thread)
        self.assertEqual(result.layout, LAYOUT_CLASSIC)
        self.assertIsNone(result.project_root)
        self.assertEqual(result.slug, "demo-memo")

    def test_classic_thread_from_version_dir(self) -> None:
        """Walk-upward: discovery from a version dir resolves to the thread root."""
        portfolio = self.root / "portfolio"
        thread = _make_classic_thread(portfolio, "demo-memo", num_versions=2)
        version_dir = thread / "demo-memo.2"
        result = discover_thread_root(version_dir)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.thread_root, thread)
        self.assertEqual(result.layout, LAYOUT_CLASSIC)
        self.assertEqual(result.slug, "demo-memo")

    def test_classic_thread_from_nested_file(self) -> None:
        """Discovery from a file inside a version dir works."""
        portfolio = self.root / "portfolio"
        thread = _make_classic_thread(portfolio, "demo-memo")
        memo_file = thread / "demo-memo.1" / "memo.md"
        result = discover_thread_root(memo_file)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.thread_root, thread)
        self.assertEqual(result.layout, LAYOUT_CLASSIC)

    def test_classic_multiple_siblings(self) -> None:
        """Multiple sibling classic threads under one portfolio — each resolves independently."""
        portfolio = self.root / "portfolio"
        t1 = _make_classic_thread(portfolio, "alpha-memo")
        t2 = _make_classic_thread(portfolio, "beta-memo")
        r1 = discover_thread_root(t1)
        r2 = discover_thread_root(t2)
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        assert r1 is not None and r2 is not None
        self.assertEqual(r1.thread_root, t1)
        self.assertEqual(r2.thread_root, t2)
        self.assertEqual(r1.layout, LAYOUT_CLASSIC)
        self.assertEqual(r2.layout, LAYOUT_CLASSIC)

    def test_classic_thread_without_version_dirs_yet(self) -> None:
        """A classic thread with a BRIEF but no version dirs yet.

        ``has_project_brief`` returns False (no documents: list) so the
        thread is not mistaken for a project root. Discovery walks up
        past it to the portfolio dir, finds nothing, and returns None.

        This is the documented limitation: discovery requires either a
        version dir or a project BRIEF to anchor. A pre-draft classic
        thread with only a BRIEF is not yet identifiable as a thread
        root (matches the v0 contract where the drafter creates the
        first version dir before any tooling can resolve the thread).
        """
        portfolio = self.root / "portfolio"
        thread = portfolio / "demo-memo"
        thread.mkdir(parents=True)
        (thread / BRIEF_FILENAME).write_text(
            "---\ncompany: foo\n---\n# BRIEF\n",
            encoding="utf-8",
        )
        result = discover_thread_root(thread)
        # No version dirs and no project BRIEF -> not yet discoverable.
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Project-BRIEF-only layout
# ---------------------------------------------------------------------------


class TestProjectBriefLayout(_TmpRootBase):
    """A project BRIEF with a non-empty documents: list triggers project-brief layout."""

    def _make_project(self) -> Path:
        project = self.root / "brains-for-robots"
        _write_project_brief(
            project,
            textwrap.dedent(
                """
                [
                  {slug: investment-memo, artifact_type: investment-memo},
                  {slug: latency-wall, artifact_type: position-paper},
                  {slug: technical-vision, artifact_type: vision-document}
                ]
                """
            ).strip(),
        )
        return project

    def test_project_brief_resolves_for_listed_slug_from_thread_root(self) -> None:
        project = self._make_project()
        thread_root = _make_project_slug_dir(project, "investment-memo")
        result = discover_thread_root(thread_root)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.thread_root, thread_root)
        self.assertEqual(result.layout, LAYOUT_PROJECT_BRIEF)
        self.assertEqual(result.project_root, project)
        self.assertEqual(result.slug, "investment-memo")

    def test_project_brief_resolves_from_version_dir(self) -> None:
        project = self._make_project()
        thread_root = _make_project_slug_dir(project, "investment-memo", num_versions=2)
        version_dir = thread_root / "investment-memo.2"
        result = discover_thread_root(version_dir)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.thread_root, thread_root)
        self.assertEqual(result.layout, LAYOUT_PROJECT_BRIEF)
        self.assertEqual(result.project_root, project)
        self.assertEqual(result.slug, "investment-memo")

    def test_project_brief_resolves_from_nested_file(self) -> None:
        project = self._make_project()
        thread_root = _make_project_slug_dir(project, "latency-wall")
        memo_file = thread_root / "latency-wall.1" / "memo.md"
        result = discover_thread_root(memo_file)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.thread_root, thread_root)
        self.assertEqual(result.layout, LAYOUT_PROJECT_BRIEF)

    def test_project_brief_resolves_for_each_listed_slug(self) -> None:
        """All listed slugs resolve, each with its own thread_root."""
        project = self._make_project()
        slugs = ["investment-memo", "latency-wall", "technical-vision"]
        for slug in slugs:
            thread_root = _make_project_slug_dir(project, slug)
            result = discover_thread_root(thread_root)
            self.assertIsNotNone(result, f"slug {slug} should resolve")
            assert result is not None
            self.assertEqual(result.thread_root, thread_root)
            self.assertEqual(result.layout, LAYOUT_PROJECT_BRIEF)
            self.assertEqual(result.project_root, project)
            self.assertEqual(result.slug, slug)

    def test_project_brief_with_no_version_dirs_yet(self) -> None:
        """A slug dir without version dirs still resolves via project-brief lookup.

        The slug subdirectory exists but no draft has been written yet.
        Discovery from inside the slug dir walks up to the project root,
        recognizes the project BRIEF lists the slug, and returns the
        slug dir as the thread root.
        """
        project = self._make_project()
        slug_dir = project / "investment-memo"
        slug_dir.mkdir(parents=True)
        # Discovery from a hypothetical path inside the slug dir.
        # The slug_dir has no version dirs, so the version-dir check
        # at slug_dir fails. The walk continues to project, which is
        # a project root, and the path's first component relative to
        # project is "investment-memo" — the listed slug.
        hypothetical = slug_dir / "investment-memo.1" / "memo.md"
        result = discover_thread_root(hypothetical)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.thread_root, slug_dir)
        self.assertEqual(result.layout, LAYOUT_PROJECT_BRIEF)
        self.assertEqual(result.project_root, project)
        self.assertEqual(result.slug, "investment-memo")

    def test_unlisted_slug_inside_project_root_returns_none(self) -> None:
        """A subdirectory of the project that is NOT in the documents list.

        Conservative behavior: a stray subdirectory inside a project
        dir that the BRIEF doesn't name is treated as not-a-thread.
        Returns None rather than guessing.
        """
        project = self._make_project()
        # "stray-dir" is NOT in the project BRIEF's documents list.
        stray = project / "stray-dir"
        stray.mkdir(parents=True)
        result = discover_thread_root(stray)
        self.assertIsNone(result)

    def test_project_root_itself_returns_none(self) -> None:
        """Discovery from the project root with no further path component returns None.

        The project root is not a thread root; without a slug-path
        component to disambiguate, we cannot determine which thread
        the caller meant. Return None rather than guessing.
        """
        project = self._make_project()
        result = discover_thread_root(project)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Mixed layout (classic + project on the same filesystem)
# ---------------------------------------------------------------------------


class TestMixedLayout(_TmpRootBase):
    """A project BRIEF directory coexisting with a classic thread elsewhere.

    AC from issue #284: each path resolves to the layout that matches
    its own tree, independently. The two layouts don't bleed across.
    """

    def test_classic_and_project_coexist(self) -> None:
        # Classic thread under <root>/classic-portfolio/<thread>
        classic_portfolio = self.root / "classic-portfolio"
        classic_thread = _make_classic_thread(classic_portfolio, "classic-memo")

        # Project under <root>/my-project with one document
        project = self.root / "my-project"
        _write_project_brief(
            project, "[{slug: project-memo, artifact_type: investment-memo}]"
        )
        project_thread = _make_project_slug_dir(project, "project-memo")

        # Each resolves to its own layout
        c_result = discover_thread_root(classic_thread)
        p_result = discover_thread_root(project_thread)
        self.assertIsNotNone(c_result)
        self.assertIsNotNone(p_result)
        assert c_result is not None and p_result is not None
        self.assertEqual(c_result.layout, LAYOUT_CLASSIC)
        self.assertEqual(p_result.layout, LAYOUT_PROJECT_BRIEF)
        self.assertEqual(c_result.thread_root, classic_thread)
        self.assertEqual(p_result.thread_root, project_thread)
        self.assertIsNone(c_result.project_root)
        self.assertEqual(p_result.project_root, project)


# ---------------------------------------------------------------------------
# Missing BRIEF
# ---------------------------------------------------------------------------


class TestMissingBrief(_TmpRootBase):
    """A project-style directory without a BRIEF.md falls back to classic discovery."""

    def test_no_brief_treats_subdirs_as_classic_threads(self) -> None:
        # No BRIEF at the parent. The "project" dir is just an ordinary
        # portfolio; its subdirs (if they have version dirs) are
        # classic threads.
        parent = self.root / "looks-like-project-but-isnt"
        thread = _make_classic_thread(parent, "demo-memo")
        result = discover_thread_root(thread)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.layout, LAYOUT_CLASSIC)
        self.assertIsNone(result.project_root)
        self.assertEqual(result.thread_root, thread)


# ---------------------------------------------------------------------------
# Empty documents: list
# ---------------------------------------------------------------------------


class TestEmptyDocumentsList(_TmpRootBase):
    """A BRIEF with ``documents: []`` does NOT trigger project-brief layout.

    Issue #284 AC: "BRIEF with empty ``documents:`` list" — must fall
    back to classic discovery. The presence of a BRIEF.md alone is not
    sufficient; the documents list must be non-empty.
    """

    def test_empty_documents_list_falls_back_to_classic(self) -> None:
        parent = self.root / "project-shaped-but-empty"
        _write_project_brief(parent, "[]")
        thread = _make_classic_thread(parent, "demo-memo")
        result = discover_thread_root(thread)
        self.assertIsNotNone(result)
        assert result is not None
        # Because the documents list is empty, has_project_brief
        # returns False — the classic layout wins.
        self.assertEqual(result.layout, LAYOUT_CLASSIC)
        self.assertIsNone(result.project_root)
        self.assertEqual(result.thread_root, thread)


# ---------------------------------------------------------------------------
# Layout-precedence edge case (Open Question #6)
# ---------------------------------------------------------------------------


class TestLayoutPrecedence(_TmpRootBase):
    """Open Question #6 from the curator analysis.

    When both layouts could match (a project BRIEF AND a per-thread
    BRIEF at the slug dir), the precedence rule is: **project-brief
    wins when ``documents:`` is non-empty AND this thread's slug is
    listed**; classic otherwise.
    """

    def test_project_brief_wins_when_slug_listed(self) -> None:
        """Both per-thread BRIEF and project BRIEF — project wins.

        The slug dir carries a per-thread BRIEF (legacy / accidental
        carryover) AND the project BRIEF lists the slug. The
        project-brief layout wins per the resolution of OQ#6.
        """
        project = self.root / "project"
        _write_project_brief(project, "[{slug: demo-memo, artifact_type: investment-memo}]")
        thread = _make_classic_thread(project, "demo-memo")  # also writes a per-thread BRIEF
        result = discover_thread_root(thread)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.layout, LAYOUT_PROJECT_BRIEF)
        self.assertEqual(result.project_root, project)
        self.assertEqual(result.thread_root, thread)
        self.assertEqual(result.slug, "demo-memo")

    def test_classic_wins_when_slug_not_listed(self) -> None:
        """A project BRIEF that does NOT list this thread's slug.

        The slug is stray relative to the project BRIEF. The thread is
        treated as classic — it's identifiable by its version dirs and
        the parent's BRIEF doesn't claim it.
        """
        project = self.root / "project"
        _write_project_brief(project, "[{slug: other-memo, artifact_type: investment-memo}]")
        thread = _make_classic_thread(project, "demo-memo")
        result = discover_thread_root(thread)
        self.assertIsNotNone(result)
        assert result is not None
        # Project BRIEF lists "other-memo", not "demo-memo".
        self.assertEqual(result.layout, LAYOUT_CLASSIC)
        self.assertIsNone(result.project_root)
        self.assertEqual(result.thread_root, thread)

    def test_classic_wins_when_documents_empty(self) -> None:
        """A project BRIEF with an empty ``documents:`` list — classic wins.

        Same as TestEmptyDocumentsList but exercised in the precedence
        context: even when both shapes coexist (a per-thread BRIEF +
        version dirs + an empty project BRIEF at the parent), classic
        wins because the documents list is empty.
        """
        project = self.root / "project"
        _write_project_brief(project, "[]")
        thread = _make_classic_thread(project, "demo-memo")
        result = discover_thread_root(thread)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.layout, LAYOUT_CLASSIC)
        self.assertIsNone(result.project_root)


# ---------------------------------------------------------------------------
# No thread found
# ---------------------------------------------------------------------------


class TestNoThreadFound(_TmpRootBase):
    """Paths that are neither under a thread nor inside a project return None."""

    def test_bare_path_returns_none(self) -> None:
        """A path that is just an ordinary directory with no anvil shape."""
        d = self.root / "just-a-dir"
        d.mkdir()
        result = discover_thread_root(d)
        self.assertIsNone(result)

    def test_path_with_only_brief_but_no_documents_returns_none(self) -> None:
        """A directory with a per-thread BRIEF but no version dirs returns None.

        Without a version-dir anchor or a project BRIEF naming a slug,
        discovery cannot resolve the thread root. This is the same
        documented limitation as TestClassicLayout.test_classic_thread_without_version_dirs_yet.
        """
        d = self.root / "thread"
        d.mkdir()
        (d / BRIEF_FILENAME).write_text(
            "---\ncompany: foo\n---\n# BRIEF\n",
            encoding="utf-8",
        )
        result = discover_thread_root(d)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Fixture-based regression
# ---------------------------------------------------------------------------


class TestProjectBriefFixture(unittest.TestCase):
    """Regression: the on-disk fixture under ``fixtures/project_brief/`` resolves.

    The fixture mirrors the Studio canary's intended five-document
    project shape. It is the regression anchor for sub-deliverables
    2 (BRIEF parser, #285) and 3 (overlay selection, #286) when they
    wire the full schema parse and overlay dispatch.
    """

    def test_fixture_exists(self) -> None:
        """The fixture root should exist."""
        self.assertTrue(_FIXTURES.is_dir(), f"missing fixture root: {_FIXTURES}")

    def test_project_brief_fixture_resolves(self) -> None:
        """Each listed slug in the project BRIEF fixture resolves to project-brief."""
        project = _FIXTURES / "brains-for-robots"
        if not project.is_dir():
            self.skipTest(f"missing project fixture: {project}")
        # has_project_brief recognizes the project root.
        self.assertTrue(has_project_brief(project))

        # Each slug subdir resolves to LAYOUT_PROJECT_BRIEF.
        for slug in ("investment-memo", "latency-wall"):
            slug_dir = project / slug
            if not slug_dir.is_dir():
                continue
            result = discover_thread_root(slug_dir)
            self.assertIsNotNone(result, f"slug {slug} should resolve via fixture")
            assert result is not None
            self.assertEqual(result.layout, LAYOUT_PROJECT_BRIEF)
            self.assertEqual(result.project_root, project)
            self.assertEqual(result.slug, slug)
            self.assertEqual(result.thread_root, slug_dir)

    def test_classic_only_fixture_resolves(self) -> None:
        """A classic-only fixture (no project BRIEF) resolves to LAYOUT_CLASSIC."""
        portfolio = _FIXTURES / "classic-portfolio"
        if not portfolio.is_dir():
            self.skipTest(f"missing classic fixture: {portfolio}")
        # The fixture has one classic thread inside; iterate to find it.
        for child in portfolio.iterdir():
            if not child.is_dir():
                continue
            # Find via a version dir if present.
            for grand in child.iterdir():
                if grand.is_dir() and grand.name.startswith(child.name + "."):
                    result = discover_thread_root(grand)
                    self.assertIsNotNone(result)
                    assert result is not None
                    self.assertEqual(result.layout, LAYOUT_CLASSIC)
                    self.assertEqual(result.thread_root, child)
                    self.assertIsNone(result.project_root)
                    return
        self.skipTest("classic-only fixture has no version dirs to anchor discovery")

    def test_empty_documents_fixture_falls_back_to_classic(self) -> None:
        """A fixture with ``documents: []`` falls back to classic discovery."""
        empty = _FIXTURES / "empty-documents-project"
        if not empty.is_dir():
            self.skipTest(f"missing empty-documents fixture: {empty}")
        # has_project_brief recognizes this as NOT a project root.
        self.assertFalse(has_project_brief(empty))


# ---------------------------------------------------------------------------
# Constants are exported and stable
# ---------------------------------------------------------------------------


class TestConstants(unittest.TestCase):
    """The layout marker constants and on-disk literals are exported and stable."""

    def test_layout_constants_are_strings(self) -> None:
        self.assertIsInstance(LAYOUT_CLASSIC, str)
        self.assertIsInstance(LAYOUT_PROJECT_BRIEF, str)
        self.assertNotEqual(LAYOUT_CLASSIC, LAYOUT_PROJECT_BRIEF)

    def test_brief_filename_constant(self) -> None:
        self.assertEqual(BRIEF_FILENAME, "BRIEF.md")

    def test_documents_key_constant(self) -> None:
        self.assertEqual(DOCUMENTS_FRONTMATTER_KEY, "documents")

    def test_discovery_result_is_frozen(self) -> None:
        """DiscoveryResult should be immutable (frozen dataclass)."""
        r = DiscoveryResult(
            thread_root=Path("/tmp/x"),
            layout=LAYOUT_CLASSIC,
            project_root=None,
            slug="x",
        )
        with self.assertRaises(Exception):
            r.layout = LAYOUT_PROJECT_BRIEF  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
