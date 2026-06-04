"""Shape tests for the body_filename end-to-end fixtures (issue #279).

Two fixtures under ``tests/fixtures/body_filename/`` exercise the
backward-compat and paper-shape paths for the per-thread ``body_filename``
customization shipped under issue #279:

- ``backward_compat/`` — a thread with no ``.anvil.json``. The default
  ``body_filename`` resolution path applies: body markdown lives at
  ``<thread>.{N}/memo.md``.
- ``paper_shape/`` — a thread declaring ``body_filename: "paper.md"``.
  The override resolution path applies: body markdown lives at
  ``<thread>.{N}/paper.md`` (NOT ``memo.md``).

These tests are **shape-only**: they assert the on-disk layout, exercise
the ``load_body_filename`` reader against each fixture's thread root, and
verify the state-machine ``DRAFTED`` evidence check (does
``<body_filename>`` exist in the version dir?) returns the expected
answer for each shape. Behavioral round-trips through the six memo
commands are out of scope for Phase A per issue #279 (per the curator
brief, the prose-level wiring is the primary coverage; these fixtures
exist as anchors for a future Phase B behavioral suite if the canary
surfaces a regression).

Runs under either ``python -m unittest discover anvil/skills/memo/tests/``
or ``pytest anvil/skills/memo/tests/`` per the issue #58 cross-skill
packaging convention.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


# The memo skill keeps its lib modules under its own ``lib/`` per the
# CLAUDE.md "skill-local first, lib promotion later" pattern. Add it to
# ``sys.path`` so tests import without a package install step.
_HERE = Path(__file__).resolve().parent
_LIB = _HERE.parent / "lib"
sys.path.insert(0, str(_LIB))

from anvil_config import load_body_filename  # noqa: E402


_FIXTURE_ROOT = _HERE / "fixtures" / "body_filename"
_BACKWARD_COMPAT_ROOT = _FIXTURE_ROOT / "backward_compat"
_PAPER_SHAPE_ROOT = _FIXTURE_ROOT / "paper_shape"


class TestFixtureFilesPresent(unittest.TestCase):
    """The two fixtures + the README are on disk and well-formed."""

    def test_readme_exists(self) -> None:
        self.assertTrue(
            (_FIXTURE_ROOT / "README.md").is_file(),
            "fixtures/body_filename/README.md must exist",
        )

    def test_backward_compat_layout(self) -> None:
        thread_dir = _BACKWARD_COMPAT_ROOT / "demo-thread"
        version_dir = _BACKWARD_COMPAT_ROOT / "demo-thread.1"
        self.assertTrue(thread_dir.is_dir(), f"{thread_dir} must exist")
        self.assertTrue(
            (thread_dir / "BRIEF.md").is_file(),
            "backward_compat fixture must contain BRIEF.md at the thread root",
        )
        self.assertFalse(
            (thread_dir / ".anvil.json").exists(),
            "backward_compat fixture must NOT carry an .anvil.json "
            "(that's the load-bearing default-resolution case)",
        )
        self.assertTrue(version_dir.is_dir(), f"{version_dir} must exist")
        self.assertTrue(
            (version_dir / "memo.md").is_file(),
            "backward_compat fixture must contain memo.md in the version dir "
            "(default body filename)",
        )

    def test_paper_shape_layout(self) -> None:
        thread_dir = _PAPER_SHAPE_ROOT / "latency-wall"
        version_dir = _PAPER_SHAPE_ROOT / "latency-wall.1"
        self.assertTrue(thread_dir.is_dir(), f"{thread_dir} must exist")
        self.assertTrue(
            (thread_dir / "BRIEF.md").is_file(),
            "paper_shape fixture must contain BRIEF.md at the thread root",
        )
        self.assertTrue(
            (thread_dir / ".anvil.json").is_file(),
            "paper_shape fixture must carry .anvil.json declaring body_filename",
        )
        self.assertTrue(version_dir.is_dir(), f"{version_dir} must exist")
        self.assertTrue(
            (version_dir / "paper.md").is_file(),
            "paper_shape fixture must contain paper.md (NOT memo.md) in the version dir",
        )
        self.assertFalse(
            (version_dir / "memo.md").exists(),
            "paper_shape fixture must NOT contain memo.md "
            "(the override fully replaces the default body filename)",
        )


class TestBackwardCompatResolution(unittest.TestCase):
    """The backward-compat fixture resolves to the default ``"memo.md"``."""

    def test_loader_returns_default(self) -> None:
        thread_dir = _BACKWARD_COMPAT_ROOT / "demo-thread"
        resolved = load_body_filename(thread_dir)
        self.assertEqual(
            resolved, "memo.md",
            "backward_compat thread (no .anvil.json) must resolve to memo.md",
        )

    def test_drafted_evidence_check(self) -> None:
        """The state-machine ``DRAFTED`` evidence is `<thread>.{N}/<body_filename>` presence."""
        thread_dir = _BACKWARD_COMPAT_ROOT / "demo-thread"
        version_dir = _BACKWARD_COMPAT_ROOT / "demo-thread.1"
        body_filename = load_body_filename(thread_dir)
        # The check: does `<version_dir>/<body_filename>` exist?
        self.assertTrue(
            (version_dir / body_filename).is_file(),
            "backward_compat DRAFTED evidence check (memo.md presence) must pass",
        )


class TestPaperShapeResolution(unittest.TestCase):
    """The paper-shape fixture resolves to ``"paper.md"`` (override)."""

    def test_loader_returns_override(self) -> None:
        thread_dir = _PAPER_SHAPE_ROOT / "latency-wall"
        resolved = load_body_filename(thread_dir)
        self.assertEqual(
            resolved, "paper.md",
            "paper_shape thread (body_filename: paper.md) must resolve to paper.md",
        )

    def test_drafted_evidence_check(self) -> None:
        """The state-machine ``DRAFTED`` evidence uses the resolved override."""
        thread_dir = _PAPER_SHAPE_ROOT / "latency-wall"
        version_dir = _PAPER_SHAPE_ROOT / "latency-wall.1"
        body_filename = load_body_filename(thread_dir)
        # The check: does `<version_dir>/<body_filename>` exist?
        self.assertTrue(
            (version_dir / body_filename).is_file(),
            "paper_shape DRAFTED evidence check (paper.md presence) must pass",
        )
        # And the inverse: memo.md must NOT exist (the override replaces it).
        self.assertFalse(
            (version_dir / "memo.md").exists(),
            "paper_shape thread must NOT have memo.md (the override is exclusive)",
        )

    def test_pdf_basename_derivation(self) -> None:
        """The PDF basename derives from the body filename: paper.md → paper.pdf."""
        thread_dir = _PAPER_SHAPE_ROOT / "latency-wall"
        body_filename = load_body_filename(thread_dir)
        # The basename rule applied by render_gate._gate_memo when out_pdf
        # is not explicitly supplied: strip the trailing ".md".
        self.assertTrue(body_filename.endswith(".md"))
        pdf_basename = body_filename[:-3] + ".pdf"
        self.assertEqual(pdf_basename, "paper.pdf")


class TestRubricOverridesCoexistence(unittest.TestCase):
    """The paper-shape fixture also carries `rubric_overrides`; the two readers don't conflict."""

    def test_both_readers_succeed(self) -> None:
        """`load_body_filename` and `load_rubric_overrides` against the same thread both work."""
        from anvil_config import load_rubric_overrides  # noqa: E402

        thread_dir = _PAPER_SHAPE_ROOT / "latency-wall"

        # body_filename reader
        body_fn = load_body_filename(thread_dir)
        self.assertEqual(body_fn, "paper.md")

        # rubric_overrides reader on the same thread
        overrides = load_rubric_overrides(thread_dir)
        self.assertEqual(overrides.memo_subtype, "latency-wall")
        self.assertIsNotNone(overrides.calibration_for(1))
        self.assertIn(
            "position paper",
            overrides.calibration_for(1),
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
