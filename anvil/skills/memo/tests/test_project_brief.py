"""Tests for ``anvil.skills.memo.lib.project_brief`` (issue #285).

Covers the typed parser for the project-level ``BRIEF.md`` schema
shipped as sub-deliverable 2 of #283. The discovery primitive
(sub-deliverable 1 / #284) is tested independently in
``test_project_discovery.py``; this file is scoped to the parser
behavior.

Test coverage map (from issue #285 AC list):

- **Well-formed BRIEF** — every field parses and the typed model
  matches the on-disk shape.
- **Missing optional fields** — empty ``audience`` and ``hard_rules``
  are tolerated (lists default to empty).
- **Unknown ``artifact_type``** — closed-ended enum rejects unknown
  values with a clear error listing the registered set.
- **Slug-directory mismatch (Open Question #1)** — listed-but-missing
  warns; on-disk-but-unlisted raises.
- **Duplicate slugs** — within the documents list raises with the
  offending slug + indices.
- **Empty documents list** — raises (a BRIEF with empty documents does
  not even pass the layout-dispatch gate in #284).
- **Missing slug** — required field, raises.
- **Malformed ``target_length``** — flat-shape only, integer bounds,
  min<=max.
- **Absence-tolerant** — lenient returns None for missing BRIEF;
  strict raises FileNotFoundError.
- **On-disk fixtures** — a well-formed BRIEF fixture under
  ``fixtures/project_brief_parser/`` exercises the canonical
  brains-for-robots shape end-to-end (regression anchor for sub-
  deliverable 3 / #286 when it wires the overlay selector).

Fixtures live under ``fixtures/project_brief_parser/`` — distinct from
``fixtures/project_brief/`` (created by #284 for discovery tests) so
the two test files do not collide on the same fixtures tree.

Per the #58 packaging convention, this file's filename
(``test_project_brief.py``) is unique across the
``anvil/skills/*/tests/`` tree so the cross-skill pytest discovery
does not collide on basename.

Runs under either ``python -m unittest discover anvil/skills/memo/tests/``
or ``pytest anvil/skills/memo/tests/``.
"""

from __future__ import annotations

import sys
import textwrap
import unittest
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory


# The memo skill keeps its lib modules under its own ``lib/`` per the
# CLAUDE.md "skill-local first, lib promotion later" pattern. Add it to
# ``sys.path`` so tests import without a package install step — mirrors
# ``test_anvil_config.py`` and ``test_project_discovery.py`` exactly.
_HERE = Path(__file__).resolve().parent
_LIB = _HERE.parent / "lib"
sys.path.insert(0, str(_LIB))

from project_brief import (  # noqa: E402
    ArtifactType,
    BriefDocument,
    ProjectBrief,
    REGISTERED_ARTIFACT_TYPES,
    TargetLengthRange,
    load_project_brief,
    load_project_brief_strict,
)
from project_discovery import BRIEF_FILENAME  # noqa: E402


_FIXTURES = _HERE / "fixtures" / "project_brief_parser"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_brief(
    directory: Path,
    frontmatter: str,
    body: str = "\n# Project BRIEF\n",
) -> Path:
    """Write ``<directory>/BRIEF.md`` with the given frontmatter body.

    ``frontmatter`` is the raw text inserted between the opening and
    closing ``---`` delimiters (without the delimiters themselves).
    Caller passes already-dedented text (``textwrap.dedent(...).rstrip()``)
    — we do NOT re-dedent here because an interpolated multi-line value
    breaks the common-leading-whitespace rule that ``textwrap.dedent``
    relies on.
    """
    directory.mkdir(parents=True, exist_ok=True)
    brief = directory / BRIEF_FILENAME
    brief.write_text(
        f"---\n{frontmatter}\n---\n{body}",
        encoding="utf-8",
    )
    return brief


def _well_formed_frontmatter() -> str:
    """Return a canonical, valid project BRIEF frontmatter body.

    Mirrors the brains-for-robots fixture shape so tests that need a
    baseline "everything works" parse can use this directly.
    """
    return textwrap.dedent(
        """\
        project: brains-for-robots
        audience:
          - Sphere internal leadership (primary)
          - VC investors (secondary)
        hard_rules:
          - Avoid speculative claims without an evidence anchor.
          - Cite every number; cite every claim with a defensible mechanism.
        documents:
          - slug: investment-memo
            artifact_type: investment-memo
            target_length: { words: [8000, 11000] }
          - slug: latency-wall
            artifact_type: position-paper
            target_length: { words: [5000, 8000] }
          - slug: technical-vision
            artifact_type: vision-document
            target_length: { words: [3000, 4500] }
          - slug: execution-plan
            artifact_type: tactical-plan
            target_length: { words: [3000, 4500] }
          - slug: team-thesis
            artifact_type: descriptive-thesis
            target_length: { words: [2500, 4000] }
        """
    ).rstrip()


class _TmpProjectBase(unittest.TestCase):
    """Per-test temp dir for the project root."""

    def setUp(self) -> None:
        self._td = TemporaryDirectory()
        self.project_dir = Path(self._td.name) / "project"
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._td.cleanup)


# ---------------------------------------------------------------------------
# Well-formed BRIEF
# ---------------------------------------------------------------------------


class TestWellFormedBrief(_TmpProjectBase):
    """A canonical BRIEF parses cleanly through both loaders."""

    def test_lenient_parses_canonical_brief(self) -> None:
        _write_brief(self.project_dir, _well_formed_frontmatter())
        brief = load_project_brief(self.project_dir)

        self.assertIsNotNone(brief)
        assert brief is not None  # for type narrowing
        self.assertEqual(brief.project, "brains-for-robots")
        self.assertEqual(len(brief.audience), 2)
        self.assertIn("Sphere internal leadership (primary)", brief.audience)
        self.assertEqual(len(brief.hard_rules), 2)
        self.assertEqual(len(brief.documents), 5)

    def test_strict_parses_canonical_brief(self) -> None:
        _write_brief(self.project_dir, _well_formed_frontmatter())
        brief = load_project_brief_strict(self.project_dir)

        self.assertEqual(brief.project, "brains-for-robots")
        self.assertEqual(len(brief.documents), 5)

    def test_documents_are_typed_brief_document_instances(self) -> None:
        _write_brief(self.project_dir, _well_formed_frontmatter())
        brief = load_project_brief_strict(self.project_dir)

        for doc in brief.documents:
            self.assertIsInstance(doc, BriefDocument)
            self.assertIsInstance(doc.artifact_type, ArtifactType)

    def test_artifact_types_match_registered_enum(self) -> None:
        _write_brief(self.project_dir, _well_formed_frontmatter())
        brief = load_project_brief_strict(self.project_dir)

        types = {doc.artifact_type for doc in brief.documents}
        expected = {
            ArtifactType.INVESTMENT_MEMO,
            ArtifactType.POSITION_PAPER,
            ArtifactType.VISION_DOCUMENT,
            ArtifactType.TACTICAL_PLAN,
            ArtifactType.DESCRIPTIVE_THESIS,
        }
        self.assertEqual(types, expected)

    def test_target_length_words_pass_through(self) -> None:
        _write_brief(self.project_dir, _well_formed_frontmatter())
        brief = load_project_brief_strict(self.project_dir)

        first = brief.documents[0]
        self.assertEqual(first.slug, "investment-memo")
        self.assertIsNotNone(first.target_length)
        assert first.target_length is not None
        self.assertEqual(first.target_length.min_words, 8000)
        self.assertEqual(first.target_length.max_words, 11000)
        self.assertEqual(first.target_length.source_key, "words")

    def test_document_for_slug_accessor(self) -> None:
        _write_brief(self.project_dir, _well_formed_frontmatter())
        brief = load_project_brief_strict(self.project_dir)

        doc = brief.document_for_slug("latency-wall")
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.artifact_type, ArtifactType.POSITION_PAPER)

        missing = brief.document_for_slug("nonexistent")
        self.assertIsNone(missing)


# ---------------------------------------------------------------------------
# Missing optional fields
# ---------------------------------------------------------------------------


class TestMissingOptionalFields(_TmpProjectBase):
    """Empty ``audience`` and ``hard_rules`` lists are tolerated."""

    def test_empty_audience_list(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            audience: []
            hard_rules: []
            documents:
              - slug: only-doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        brief = load_project_brief_strict(self.project_dir)
        self.assertEqual(brief.audience, [])

    def test_empty_hard_rules_list(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            audience: [internal]
            hard_rules: []
            documents:
              - slug: only-doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        brief = load_project_brief_strict(self.project_dir)
        self.assertEqual(brief.hard_rules, [])

    def test_audience_and_hard_rules_omitted_entirely(self) -> None:
        """Both list fields default to empty when the key is absent."""
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: only-doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        brief = load_project_brief_strict(self.project_dir)
        self.assertEqual(brief.audience, [])
        self.assertEqual(brief.hard_rules, [])

    def test_target_length_optional(self) -> None:
        """A document without target_length is allowed."""
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: only-doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        brief = load_project_brief_strict(self.project_dir)
        self.assertIsNone(brief.documents[0].target_length)


# ---------------------------------------------------------------------------
# Unknown artifact_type
# ---------------------------------------------------------------------------


class TestUnknownArtifactType(_TmpProjectBase):
    """Closed-ended enum rejects unknown values with a clear error."""

    def test_unknown_artifact_type_raises_with_registered_set(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: weird-doc
                artifact_type: pamphlet
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)

        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)

        msg = str(cm.exception)
        # The error must surface the offending value.
        self.assertIn("pamphlet", msg)
        # The error must list the registered set so the operator can self-correct.
        for registered in REGISTERED_ARTIFACT_TYPES:
            self.assertIn(registered, msg)

    def test_unknown_artifact_type_lenient_also_raises(self) -> None:
        """Lenient still raises on schema violations (only absence is None)."""
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: weird-doc
                artifact_type: pamphlet
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError):
            load_project_brief(self.project_dir)

    def test_non_string_artifact_type(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: weird-doc
                artifact_type: 42
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("artifact_type", str(cm.exception))

    def test_missing_artifact_type(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: weird-doc
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("artifact_type", str(cm.exception))
        self.assertIn("required", str(cm.exception))


# ---------------------------------------------------------------------------
# Slug-directory mismatch (Open Question #1)
# ---------------------------------------------------------------------------


class TestSlugDirectoryDivergence(_TmpProjectBase):
    """Asymmetric rule: warn on listed-but-missing; error on on-disk-but-unlisted."""

    def _make_thread_dir(self, slug: str) -> None:
        """Create ``<project>/<slug>/<slug>.1/memo.md`` — a "started thread"."""
        thread = self.project_dir / slug
        thread.mkdir(parents=True, exist_ok=True)
        v1 = thread / f"{slug}.1"
        v1.mkdir(parents=True, exist_ok=True)
        (v1 / "memo.md").write_text("# memo\n", encoding="utf-8")

    def test_listed_but_missing_warns(self) -> None:
        """A BRIEF entry with no on-disk directory triggers a UserWarning."""
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: started-doc
                artifact_type: investment-memo
              - slug: not-yet-started
                artifact_type: position-paper
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        self._make_thread_dir("started-doc")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            brief = load_project_brief_strict(
                self.project_dir, validate_dirs=True
            )

        # Returned brief is unchanged.
        self.assertEqual(len(brief.documents), 2)

        # Exactly one warning emitted; mentions the missing slug.
        warning_msgs = [str(w.message) for w in caught]
        listed_but_missing = [
            m for m in warning_msgs if "not-yet-started" in m
        ]
        self.assertEqual(
            len(listed_but_missing),
            1,
            f"Expected exactly one warning naming 'not-yet-started'; got {warning_msgs}",
        )

    def test_on_disk_but_unlisted_raises(self) -> None:
        """A directory present on disk but absent from BRIEF.documents raises."""
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: listed-doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        self._make_thread_dir("listed-doc")
        self._make_thread_dir("unlisted-doc")  # configuration drift

        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(
                self.project_dir, validate_dirs=True
            )

        msg = str(cm.exception)
        self.assertIn("unlisted-doc", msg)
        # The error must mention "drift" or "not listed" so the operator
        # understands what's wrong.
        self.assertTrue(
            "drift" in msg.lower() or "not listed" in msg.lower(),
            f"Error message should mention configuration drift: {msg}",
        )

    def test_validate_dirs_off_by_default(self) -> None:
        """Without ``validate_dirs=True``, divergence is not checked."""
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: listed-doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        self._make_thread_dir("unlisted-doc")

        # No exception, no warning.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            brief = load_project_brief_strict(self.project_dir)
        self.assertEqual(brief.project, "tiny")
        # No divergence warnings.
        unlisted_warnings = [
            w for w in caught if "unlisted-doc" in str(w.message)
        ]
        self.assertEqual(unlisted_warnings, [])

    def test_research_dir_not_treated_as_thread_root(self) -> None:
        """``research/`` (no version dirs) is not flagged as on-disk-but-unlisted."""
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: started-doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        self._make_thread_dir("started-doc")
        # research/ is project-level infrastructure, not a thread root.
        (self.project_dir / "research").mkdir()
        (self.project_dir / "research" / "evidence.md").write_text(
            "# evidence\n", encoding="utf-8"
        )

        # Should not raise.
        brief = load_project_brief_strict(
            self.project_dir, validate_dirs=True
        )
        self.assertEqual(brief.project, "tiny")

    def test_dotted_sibling_dir_not_treated_as_thread_root(self) -> None:
        """``.review/`` / ``.audit/`` siblings are skipped (not thread roots)."""
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: started-doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        self._make_thread_dir("started-doc")
        (self.project_dir / ".cache").mkdir()

        # Should not raise.
        brief = load_project_brief_strict(
            self.project_dir, validate_dirs=True
        )
        self.assertEqual(brief.project, "tiny")


# ---------------------------------------------------------------------------
# Duplicate slugs
# ---------------------------------------------------------------------------


class TestDuplicateSlugs(_TmpProjectBase):
    """Slugs must be unique within the BRIEF's documents list."""

    def test_duplicate_slug_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: dup
                artifact_type: investment-memo
              - slug: dup
                artifact_type: position-paper
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)

        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)

        msg = str(cm.exception)
        self.assertIn("'dup'", msg)
        # The error should name both indices so the author knows where to
        # look (offending entry + first occurrence).
        self.assertIn("0", msg)
        self.assertIn("1", msg)


# ---------------------------------------------------------------------------
# Empty documents list / missing documents key
# ---------------------------------------------------------------------------


class TestEmptyDocumentsList(_TmpProjectBase):
    """The documents list must be non-empty."""

    def test_empty_documents_list_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents: []
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)

        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        msg = str(cm.exception)
        self.assertIn("documents", msg)
        self.assertIn("non-empty", msg)

    def test_missing_documents_key_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            audience: [test]
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)

        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        msg = str(cm.exception)
        self.assertIn("documents", msg)

    def test_documents_as_non_list_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents: a-string
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)

        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("documents", str(cm.exception))


# ---------------------------------------------------------------------------
# Missing slug
# ---------------------------------------------------------------------------


class TestMissingSlug(_TmpProjectBase):
    """slug is a required field on every document entry."""

    def test_missing_slug_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)

        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        msg = str(cm.exception)
        self.assertIn("slug", msg)

    def test_empty_string_slug_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: ""
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)

        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("slug", str(cm.exception))

    def test_whitespace_only_slug_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: "   "
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("slug", str(cm.exception))


# ---------------------------------------------------------------------------
# Malformed target_length
# ---------------------------------------------------------------------------


class TestMalformedTargetLength(_TmpProjectBase):
    """The flat target_length shape is the only accepted form."""

    def test_target_length_pages_converts_to_words(self) -> None:
        """``pages: [n, m]`` is accepted and converts at 600 wpp."""
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: short-doc
                artifact_type: investment-memo
                target_length: { pages: [4, 6] }
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        brief = load_project_brief_strict(self.project_dir)
        tl = brief.documents[0].target_length
        self.assertIsNotNone(tl)
        assert tl is not None
        self.assertEqual(tl.source_key, "pages")
        self.assertEqual(tl.min_words, 2400)
        self.assertEqual(tl.max_words, 3600)

    def test_target_length_with_both_keys_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: doc
                artifact_type: investment-memo
                target_length: { words: [100, 200], pages: [1, 2] }
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("ambiguous", str(cm.exception).lower())

    def test_target_length_min_greater_than_max_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: doc
                artifact_type: investment-memo
                target_length: { words: [200, 100] }
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("min <= max", str(cm.exception))

    def test_target_length_negative_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: doc
                artifact_type: investment-memo
                target_length: { words: [-100, 200] }
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("non-negative", str(cm.exception))

    def test_target_length_three_element_list_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: doc
                artifact_type: investment-memo
                target_length: { words: [100, 200, 300] }
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("2-element", str(cm.exception))

    def test_target_length_non_dict_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: doc
                artifact_type: investment-memo
                target_length: 1000
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("target_length", str(cm.exception))

    def test_target_length_extended_shape_keys_rejected(self) -> None:
        """``default`` / ``overrides`` (extended shape) is rejected at BRIEF level."""
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: doc
                artifact_type: investment-memo
                target_length:
                  default: { words: [100, 200] }
                  overrides: {}
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("extended-shape", str(cm.exception))

    def test_target_length_neither_words_nor_pages_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: doc
                artifact_type: investment-memo
                target_length: { paragraphs: [10, 20] }
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        msg = str(cm.exception)
        # The unknown key ('paragraphs') is rejected because the loader
        # doesn't see words/pages, OR because of a more specific message.
        self.assertIn("target_length", msg)


# ---------------------------------------------------------------------------
# Absence-tolerant behavior
# ---------------------------------------------------------------------------


class TestAbsenceTolerant(_TmpProjectBase):
    """Lenient returns None on absence; strict raises FileNotFoundError."""

    def test_lenient_returns_none_when_no_brief(self) -> None:
        result = load_project_brief(self.project_dir)
        self.assertIsNone(result)

    def test_lenient_returns_none_when_no_frontmatter(self) -> None:
        (self.project_dir / BRIEF_FILENAME).write_text(
            "# A BRIEF with no frontmatter at all\n", encoding="utf-8"
        )
        result = load_project_brief(self.project_dir)
        self.assertIsNone(result)

    def test_lenient_returns_none_when_yaml_unparseable(self) -> None:
        (self.project_dir / BRIEF_FILENAME).write_text(
            "---\nproject: tiny\ndocuments: [unclosed\n---\n# body\n",
            encoding="utf-8",
        )
        result = load_project_brief(self.project_dir)
        self.assertIsNone(result)

    def test_strict_raises_filenotfound_when_no_brief(self) -> None:
        with self.assertRaises(FileNotFoundError) as cm:
            load_project_brief_strict(self.project_dir)
        msg = str(cm.exception)
        self.assertIn("No BRIEF found", msg)
        self.assertIn(BRIEF_FILENAME, msg)

    def test_strict_raises_valueerror_when_no_frontmatter(self) -> None:
        (self.project_dir / BRIEF_FILENAME).write_text(
            "# A BRIEF with no frontmatter at all\n", encoding="utf-8"
        )
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("frontmatter", str(cm.exception))


# ---------------------------------------------------------------------------
# Project-name required
# ---------------------------------------------------------------------------


class TestProjectField(_TmpProjectBase):
    """``project`` is required, non-empty string."""

    def test_missing_project_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            audience: [test]
            documents:
              - slug: doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("project", str(cm.exception))

    def test_empty_project_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: ""
            documents:
              - slug: doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("project", str(cm.exception))


# ---------------------------------------------------------------------------
# Audience / hard_rules type errors
# ---------------------------------------------------------------------------


class TestAudienceHardRulesValidation(_TmpProjectBase):
    """audience / hard_rules must be lists of strings when present."""

    def test_audience_as_string_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            audience: "just a string"
            documents:
              - slug: doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("audience", str(cm.exception))

    def test_audience_with_non_string_entry_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            audience: [valid, 42]
            documents:
              - slug: doc
                artifact_type: investment-memo
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        self.assertIn("audience", str(cm.exception))


# ---------------------------------------------------------------------------
# Unknown keys on document entries
# ---------------------------------------------------------------------------


class TestUnknownDocumentKeys(_TmpProjectBase):
    """Unknown keys on a document entry raise a clear error."""

    def test_unknown_key_on_document_raises(self) -> None:
        fm = textwrap.dedent(
            """\
            project: tiny
            documents:
              - slug: doc
                artifact_type: investment-memo
                max_iterations: 8
            """
        ).rstrip()
        _write_brief(self.project_dir, fm)
        with self.assertRaises(ValueError) as cm:
            load_project_brief_strict(self.project_dir)
        msg = str(cm.exception)
        self.assertIn("max_iterations", msg)


# ---------------------------------------------------------------------------
# On-disk fixture (the brains-for-robots canary shape)
# ---------------------------------------------------------------------------


class TestOnDiskFixture(unittest.TestCase):
    """End-to-end parse against the on-disk fixture.

    Regression anchor for sub-deliverable 3 (#286) when it wires the
    overlay selector — the fixture covers the canonical five-document
    project shape and should remain parseable through both loaders as
    the parser evolves.
    """

    def test_brains_for_robots_fixture_parses(self) -> None:
        fixture = _FIXTURES / "brains-for-robots"
        self.assertTrue(
            fixture.exists(),
            f"fixture missing: {fixture}",
        )

        brief = load_project_brief_strict(fixture)
        self.assertEqual(brief.project, "brains-for-robots")
        self.assertEqual(len(brief.documents), 5)

        slugs = {doc.slug for doc in brief.documents}
        self.assertEqual(
            slugs,
            {
                "investment-memo",
                "latency-wall",
                "technical-vision",
                "execution-plan",
                "team-thesis",
            },
        )

    def test_well_formed_minimal_fixture_parses(self) -> None:
        """A minimal one-document BRIEF parses too."""
        fixture = _FIXTURES / "minimal-one-doc"
        self.assertTrue(
            fixture.exists(),
            f"fixture missing: {fixture}",
        )

        brief = load_project_brief_strict(fixture)
        self.assertEqual(brief.project, "minimal")
        self.assertEqual(len(brief.documents), 1)
        self.assertEqual(brief.documents[0].slug, "only-doc")
        self.assertEqual(
            brief.documents[0].artifact_type, ArtifactType.INVESTMENT_MEMO
        )


if __name__ == "__main__":
    unittest.main()
