"""Tests for ``anvil.skills.deck.lib.marp_lint``.

Each test exercises one fixture in ``tests/fixtures/marp_lint/`` against
``lint_deck``. The fixtures correspond to AC4 on issue #31:

- ``overflow_figure_plus_bullets.md`` reproduces the #24 pattern (image + 4
  bullets + footer line). Expected: 1 error.
- ``overflow_ask_h1_plus_h2.md`` reproduces the #25 pattern (`_class: ask`
  with both H1 and H2 plus bullets). Expected: 1 error.
- ``clean_figure_plus_supporting_line.md`` is the working idiom from #24
  (one figure + one italic supporting line). Expected: 0 errors, 0 warnings.
- ``borderline_dense_bullets.md`` is a dense slide that overflows the
  warning threshold but stays under the error threshold. Expected:
  0 errors, 1 warning.
- ``escape_hatch_disabled.md`` is the #24 overflow case with the
  ``<!-- anvil-lint-disable: slide-content-overflow -->`` directive — the
  finding must be downgraded to ``info`` (escape hatch tested for AC5).

Runs under either ``python -m unittest discover anvil/skills/deck/tests/``
or ``pytest anvil/skills/deck/tests/``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


# The deck skill keeps the lint module under its own ``lib/`` per the curator
# addendum on issue #31 (D4). Add it to ``sys.path`` here so the tests can
# import the module without a package install step.
_HERE = Path(__file__).resolve().parent
_LIB = _HERE.parent / "lib"
sys.path.insert(0, str(_LIB))

from marp_lint import lint_deck, lint_source, Finding, LintResult  # noqa: E402

_FIXTURES = _HERE / "fixtures" / "marp_lint"


class TestOverflowFigurePlusBullets(unittest.TestCase):
    """The #24 repro — one image + 4 bullets + footer line. Expected: 1 error."""

    def test_one_error_one_slide(self) -> None:
        result = lint_deck(_FIXTURES / "overflow_figure_plus_bullets.md")
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(result.errors[0].slide, 1)
        self.assertEqual(result.errors[0].rule, "slide-content-overflow")
        self.assertEqual(result.errors[0].severity, "error")


class TestOverflowAskH1PlusH2(unittest.TestCase):
    """The #25 repro — `_class: ask` with H1 + H2 + bullets. Expected: 1 error."""

    def test_one_error_one_slide(self) -> None:
        result = lint_deck(_FIXTURES / "overflow_ask_h1_plus_h2.md")
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(result.errors[0].slide, 1)
        self.assertEqual(result.errors[0].rule, "slide-content-overflow")

    def test_message_mentions_h1_and_h2(self) -> None:
        result = lint_deck(_FIXTURES / "overflow_ask_h1_plus_h2.md")
        msg = result.errors[0].message
        # The top-costs roll-up should surface both heading levels for the
        # H1+H2 anti-pattern slide — the heuristic exists precisely because
        # both headings contribute to the overflow.
        self.assertIn("h1", msg)
        self.assertIn("h2", msg)


class TestCleanFigurePlusSupportingLine(unittest.TestCase):
    """The working idiom — one figure + one italic line. No findings."""

    def test_no_findings(self) -> None:
        result = lint_deck(_FIXTURES / "clean_figure_plus_supporting_line.md")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(len(result.infos), 0)


class TestBorderlineDenseBullets(unittest.TestCase):
    """A slide near but below the error threshold. One warning, no error."""

    def test_one_warning_no_error(self) -> None:
        result = lint_deck(_FIXTURES / "borderline_dense_bullets.md")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].slide, 1)
        self.assertEqual(result.warnings[0].severity, "warning")


class TestEscapeHatchDisabled(unittest.TestCase):
    """``anvil-lint-disable`` downgrades the finding to ``info``."""

    def test_finding_downgraded_to_info(self) -> None:
        result = lint_deck(_FIXTURES / "escape_hatch_disabled.md")
        # The slide would normally be an error (it's a copy of the #24 case);
        # the directive must downgrade it.
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(len(result.infos), 1)
        self.assertEqual(result.infos[0].slide, 1)
        self.assertEqual(result.infos[0].severity, "info")

    def test_review_is_not_blocked(self) -> None:
        """The escape hatch must mean ``advance`` is not forced false.

        We don't simulate the review pipeline here, but we do assert the
        ``errors`` list is empty — which is the input the review machinery
        uses to set ``advance: false``. If this is empty, advance is not
        forced false by the lint.
        """
        result = lint_deck(_FIXTURES / "escape_hatch_disabled.md")
        self.assertEqual(len(result.errors), 0)


class TestLintResultShape(unittest.TestCase):
    """AC1: ``LintResult`` exposes structured ``Finding``s with the documented schema."""

    def test_finding_fields(self) -> None:
        result = lint_deck(_FIXTURES / "overflow_figure_plus_bullets.md")
        finding = result.errors[0]
        self.assertIsInstance(finding, Finding)
        self.assertIsInstance(finding.slide, int)
        self.assertIsInstance(finding.line, int)
        self.assertIsInstance(finding.rule, str)
        self.assertIsInstance(finding.severity, str)
        self.assertIsInstance(finding.message, str)
        # ``line`` should point inside the source file (1-based).
        self.assertGreaterEqual(finding.line, 1)

    def test_to_summary_shape(self) -> None:
        result = lint_deck(_FIXTURES / "overflow_figure_plus_bullets.md")
        summary = result.to_summary()
        self.assertTrue(summary["ran"])
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["warnings"], 0)
        self.assertIn("errors_by_slide", summary)
        self.assertEqual(summary["errors_by_slide"][0]["slide"], 1)
        self.assertEqual(summary["errors_by_slide"][0]["rule"], "slide-content-overflow")


class TestInlineDisplayGridDropped(unittest.TestCase):
    """``<div style="display:grid;...">`` — silently dropped by Marp foreignObject SVG render."""

    def test_one_warning(self) -> None:
        result = lint_deck(_FIXTURES / "inline_display_grid_dropped.md")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].slide, 1)
        self.assertEqual(result.warnings[0].rule, "inline-display-style-dropped")
        self.assertEqual(result.warnings[0].severity, "warning")

    def test_message_includes_detected_value(self) -> None:
        result = lint_deck(_FIXTURES / "inline_display_grid_dropped.md")
        msg = result.warnings[0].message
        self.assertIn("display:grid", msg)
        self.assertIn("foreignObject", msg)


class TestInlineDisplayFlexDropped(unittest.TestCase):
    """``<div style="display:flex;...">`` — silently dropped, same path."""

    def test_one_warning(self) -> None:
        result = lint_deck(_FIXTURES / "inline_display_flex_dropped.md")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].slide, 1)
        self.assertEqual(result.warnings[0].rule, "inline-display-style-dropped")
        self.assertIn("display:flex", result.warnings[0].message)


class TestInlineDisplayInlineGridDropped(unittest.TestCase):
    """``display:inline-grid`` variant — case-insensitive, no whitespace around ``:``."""

    def test_one_warning(self) -> None:
        result = lint_deck(_FIXTURES / "inline_display_inline_grid_dropped.md")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].rule, "inline-display-style-dropped")
        self.assertIn("display:inline-grid", result.warnings[0].message)


class TestInlineDisplaySafe(unittest.TestCase):
    """Frontmatter ``style: |`` + ``<div class="row">`` — the workaround. No findings."""

    def test_no_findings(self) -> None:
        result = lint_deck(_FIXTURES / "inline_display_safe.md")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(len(result.infos), 0)


class TestInlineDisplayOtherStyleSafe(unittest.TestCase):
    """Inline ``style="color: red"`` etc. — the rule must NOT fire on non-`display:` rules."""

    def test_no_findings(self) -> None:
        result = lint_deck(_FIXTURES / "inline_display_other_style_safe.md")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(
            len([f for f in result.warnings if f.rule == "inline-display-style-dropped"]),
            0,
        )


class TestInlineDisplaySuppressed(unittest.TestCase):
    """``anvil-lint-disable: inline-display-style-dropped`` downgrades the finding."""

    def test_finding_downgraded_to_info(self) -> None:
        result = lint_deck(_FIXTURES / "inline_display_suppressed.md")
        self.assertEqual(len(result.errors), 0)
        # No warnings from THIS rule (the lint should have downgraded).
        self.assertEqual(
            len([f for f in result.warnings if f.rule == "inline-display-style-dropped"]),
            0,
        )
        inline_infos = [
            f for f in result.infos if f.rule == "inline-display-style-dropped"
        ]
        self.assertEqual(len(inline_infos), 1)
        self.assertEqual(inline_infos[0].severity, "info")


class TestInlineDisplayInCodeFenceIgnored(unittest.TestCase):
    """A ``style="display:grid"`` inside a fenced code block is documentation, not a render bug."""

    def test_no_findings_in_code_fence(self) -> None:
        source = """---
marp: true
size: 16:9
---

## Documentation slide

Here is the broken pattern:

```html
<div style="display: grid; grid-template-columns: 1fr 1fr;">
  <div>a</div>
  <div>b</div>
</div>
```

This documents the pattern but does not render it.
"""
        result = lint_source(source)
        self.assertEqual(
            len([f for f in result.warnings if f.rule == "inline-display-style-dropped"]),
            0,
        )


class TestInlineDisplaySingleQuoted(unittest.TestCase):
    """``<div style='display:grid;...'>`` — single-quoted attribute also matches."""

    def test_single_quoted_fires(self) -> None:
        source = """---
marp: true
---

## Two-column

<div style='display: grid; grid-template-columns: 1fr 1fr;'>
  <div>a</div>
  <div>b</div>
</div>
"""
        result = lint_source(source)
        inline = [
            f for f in result.warnings if f.rule == "inline-display-style-dropped"
        ]
        self.assertEqual(len(inline), 1)


class TestInlineDisplayCaseInsensitive(unittest.TestCase):
    """``style="DISPLAY: Grid"`` — the regex must be case-insensitive."""

    def test_uppercase_display_fires(self) -> None:
        source = """---
marp: true
---

## Two-column

<div style="DISPLAY: Grid; grid-template-columns: 1fr 1fr;">
  <div>a</div>
  <div>b</div>
</div>
"""
        result = lint_source(source)
        inline = [
            f for f in result.warnings if f.rule == "inline-display-style-dropped"
        ]
        self.assertEqual(len(inline), 1)


class TestPortedRulesIncludesInlineDisplay(unittest.TestCase):
    """``PORTED_RULES`` advertises the new rule alongside the existing two."""

    def test_rule_name_in_ported_rules(self) -> None:
        from marp_lint import PORTED_RULES  # noqa: WPS433
        self.assertIn("inline-display-style-dropped", PORTED_RULES)
        self.assertIn("slide-content-overflow", PORTED_RULES)
        self.assertIn("figure-italic-supporting-line-too-long", PORTED_RULES)


class TestMultiSlideSource(unittest.TestCase):
    """Multi-slide source: only the offending slides emit findings.

    Confirms the slide numbering is 1-based across an entire deck (not just
    a single-slide fixture).
    """

    def test_per_slide_findings(self) -> None:
        # Three slides: clean / overflow / clean. Expected: 1 error on slide 2.
        source = """---
marp: true
size: 16:9
---

## Clean intro slide

A single sentence introducing the deck.

---

## Market — TAM / SAM / SOM

![TAM / SAM / SOM](figures/market-sizing.png)

- **TAM**: $8.3B hardware → $11.9B by 2028 (Mordor Intelligence)
- **SAM**: $30B addressable across HNW + HENRY consumers
- **SOM Yr 3**: $5–10M (300 units × $20K, Pagani-shape)
- **Growth driver**: 18.8% CAGR in adjacent data-layer segment

_Source: Mordor Intelligence._

---

## Clean closing slide

_Thanks for your time — questions?_
"""
        result = lint_source(source)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].slide, 2)


if __name__ == "__main__":
    unittest.main()
