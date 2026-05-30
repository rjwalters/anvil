"""Tests for ``anvil.skills.slides.lib.marp_lint``.

The slides-side ``marp_lint`` is a re-export of the deck-side module (see
``anvil/skills/slides/lib/marp_lint.py``). These tests run the same fixtures
through the slides-side entry point to confirm:

1. The re-export gives the slides skill identical behaviour to the deck skill.
2. The fixtures appropriate to a slides-style talk (academic/conference) still
   trigger the right finding counts under the shared heuristic — the lint is
   renderer-pinned (Marp), not skill-pinned, so the same overflow patterns are
   defects in either context.

Mirrors ``anvil/skills/deck/tests/test_marp_lint.py``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_LIB = _HERE.parent / "lib"
sys.path.insert(0, str(_LIB))

from marp_lint import (  # noqa: E402
    Finding,
    LintResult,
    UPSTREAM_SHA,
    PORTED_RULES,
    lint_deck,
    lint_source,
)

_FIXTURES = _HERE / "fixtures" / "marp_lint"


class TestSlidesMirror(unittest.TestCase):
    """The slides-side re-export must expose the same public surface."""

    def test_public_api(self) -> None:
        # AC1 contract: lint_deck + LintResult + structured Findings.
        self.assertTrue(callable(lint_deck))
        self.assertTrue(callable(lint_source))
        # The slides skill mirrors the deck skill's marp_lint module, so
        # whatever rules the deck side ships also appear here. The contract
        # this test pins is the marp-vscode-ported rule (the one with a
        # tracked ``UPSTREAM_SHA``); Anvil-original rules grow the tuple
        # additively as they land in the deck skill.
        self.assertIn("slide-content-overflow", PORTED_RULES)
        # The upstream SHA pin is shared between deck and slides.
        self.assertTrue(UPSTREAM_SHA)
        self.assertEqual(len(UPSTREAM_SHA), 40)


class TestOverflowFigurePlusBullets(unittest.TestCase):
    """Slides analog of the #24 overflow pattern. Expected: 1 error."""

    def test_one_error_one_slide(self) -> None:
        result = lint_deck(_FIXTURES / "overflow_figure_plus_bullets.md")
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(result.errors[0].slide, 1)
        self.assertEqual(result.errors[0].rule, "slide-content-overflow")


class TestOverflowAskH1PlusH2(unittest.TestCase):
    """Slides analog of the #25 H1 + H2 pattern. Expected: 1 error."""

    def test_one_error_one_slide(self) -> None:
        result = lint_deck(_FIXTURES / "overflow_ask_h1_plus_h2.md")
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].slide, 1)


class TestCleanFigurePlusSupportingLine(unittest.TestCase):
    """Working idiom — figure + one italic supporting line. No findings."""

    def test_no_findings(self) -> None:
        result = lint_deck(_FIXTURES / "clean_figure_plus_supporting_line.md")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(len(result.infos), 0)


class TestBorderlineDenseBullets(unittest.TestCase):
    """Just-above-threshold dense slide: 0 errors, 1 warning."""

    def test_one_warning_no_error(self) -> None:
        result = lint_deck(_FIXTURES / "borderline_dense_bullets.md")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 1)


class TestEscapeHatchDisabled(unittest.TestCase):
    """``anvil-lint-disable`` downgrades the slide-content-overflow hit."""

    def test_finding_downgraded_to_info(self) -> None:
        result = lint_deck(_FIXTURES / "escape_hatch_disabled.md")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(len(result.infos), 1)
        self.assertEqual(result.infos[0].severity, "info")


if __name__ == "__main__":
    unittest.main()
