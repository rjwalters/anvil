"""Tests for the cross-section checks in ``anvil/lib/numeric_consistency.py``
(issue #1399): ``quoted_variant`` and ``unbridged_headline_pair``.

Fixtures are seeded from the #1396 examples (unnamed-mesh residuals quoted
as 2e-4 / 1e-4 %, "0 to 14" vs "6.4-13.5", paired headline values
2.68/4.10 vs 2.70/4.11).
"""

from __future__ import annotations

from anvil.lib.numeric_consistency import (
    QUOTED_VARIANT,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    UNBRIDGED_HEADLINE_PAIR,
    check_text,
)


def _codes(text: str, **kw):
    findings, _n, _c = check_text(text, **kw)
    return [f for f in findings if f.code in (QUOTED_VARIANT, UNBRIDGED_HEADLINE_PAIR)]


class TestQuotedVariant:
    def test_scientific_residual_variants_across_sections(self) -> None:
        body = (
            "# Abstract\n\n"
            "The converged solution residual is 2e-4 % overall.\n\n"
            "# Results\n\n"
            "The converged solution residual is 1e-4 % overall.\n"
        )
        got = _codes(body)
        assert [f.code for f in got] == [QUOTED_VARIANT]
        assert got[0].severity == SEVERITY_WARNING
        assert got[0].line == 7

    def test_rounding_variant_across_sections(self) -> None:
        body = (
            "# Intro\n\nMean turbulence intensity reached 3.14 % downstream.\n\n"
            "# Discussion\n\nMean turbulence intensity reached 3.1 % downstream.\n"
        )
        assert [f.code for f in _codes(body)] == [QUOTED_VARIANT]

    def test_range_variant_across_sections(self) -> None:
        body = (
            "# Abstract\n\nThe pressure coefficient ranges from 0 to 14 kPa along the wall.\n\n"
            "# Results\n\nThe pressure coefficient spans 6.4-13.5 kPa along the wall.\n"
        )
        assert [f.code for f in _codes(body)] == [QUOTED_VARIANT]

    def test_latex_sections_delimit(self) -> None:
        body = (
            "\\section{Intro}\n\nMean turbulence intensity reached 3.14 \\% downstream.\n\n"
            "\\section{Discussion}\n\nMean turbulence intensity reached 3.1 \\% downstream.\n"
        )
        assert [f.code for f in _codes(body, latex=True)] == [QUOTED_VARIANT]

    def test_same_section_never_pairs(self) -> None:
        body = (
            "# Results\n\nMean turbulence intensity reached 3.14 % downstream.\n\n"
            "Mean turbulence intensity reached 3.1 % downstream.\n"
        )
        assert _codes(body) == []

    def test_negative_distinct_quantities_sharing_a_unit(self) -> None:
        body = (
            "# Intro\n\nThe pump latency was 5 ms on the bench.\n\n"
            "# Results\n\nThe sensor jitter was 5.1 ms in the field.\n"
        )
        assert _codes(body) == []

    def test_negative_distinguishing_qualifier(self) -> None:
        body = (
            "# Intro\n\nThe coarse mesh residual is 2e-4 % overall.\n\n"
            "# Results\n\nThe fine mesh residual is 1e-4 % overall.\n"
        )
        assert _codes(body) == []

    def test_negative_identical_and_point_inside_range(self) -> None:
        body = (
            "# A\n\nThe pressure coefficient ranges from 0 to 14 kPa along the wall.\n\n"
            "# B\n\nThe pressure coefficient reached 6 kPa along the wall.\n\n"
            "# C\n\nThe pressure coefficient ranges from 0 to 14 kPa along the wall.\n"
        )
        assert _codes(body) == []

    def test_suppression_downgrades_to_info(self) -> None:
        body = (
            "# Abstract\n\nThe converged solution residual is 2e-4 % overall.\n\n"
            "# Results\n\n<!-- anvil-lint-disable: numeric_consistency -->\n"
            "The converged solution residual is 1e-4 % overall.\n"
        )
        got = _codes(body)
        assert len(got) == 1 and got[0].suppressed
        assert got[0].severity == SEVERITY_INFO


class TestUnbridgedHeadlinePair:
    def test_near_identical_pair_without_bridge(self) -> None:
        body = (
            "# Abstract\n\nThe headline errors are 2.68/4.10 for lift drag.\n\n"
            "# Results\n\nThe headline errors are 2.70/4.11 for lift drag.\n"
        )
        got = _codes(body)
        assert [f.code for f in got] == [UNBRIDGED_HEADLINE_PAIR]
        assert got[0].severity == SEVERITY_WARNING

    def test_bridging_cue_silences(self) -> None:
        body = (
            "# Abstract\n\nThe headline errors are 2.68/4.10 for lift drag.\n\n"
            "# Results\n\nThe values are rounded differently here. "
            "The headline errors are 2.70/4.11 for lift drag.\n"
        )
        assert _codes(body) == []

    def test_sentence_naming_both_values_bridges(self) -> None:
        body = (
            "# Abstract\n\nThe headline errors are 2.68/4.10 for lift drag.\n\n"
            "# Results\n\nEarlier 2.68 became 2.70 after the rerun. "
            "The headline errors are 2.70/4.11 for lift drag.\n"
        )
        assert _codes(body) == []

    def test_equal_pairs_and_distant_pairs_are_silent(self) -> None:
        equal = (
            "# A\n\nThe headline errors are 2.68/4.10 for lift drag.\n\n"
            "# B\n\nThe headline errors are 2.68/4.10 for lift drag.\n"
        )
        distant = (
            "# A\n\nThe headline errors are 2.68/4.10 for lift drag.\n\n"
            "# B\n\nThe headline errors are 3.90/6.20 for lift drag.\n"
        )
        assert _codes(equal) == []
        assert _codes(distant) == []

    def test_same_section_is_silent(self) -> None:
        body = (
            "# A\n\nThe headline errors are 2.68/4.10 for lift drag.\n\n"
            "The headline errors are 2.70/4.11 for lift drag.\n"
        )
        assert _codes(body) == []


class TestHeadlineValueSet:
    """Range and re-pairing forms (issue #1420), synthetic motor reduction."""

    ABSTRACT = (
        "# Abstract\n\nWarm start cuts drag error to 2.68--4.10 with seeds "
        "for the lift drag objective.\n\n"
    )
    INTRO = (
        "# Introduction\n\nOn the lift drag objective the errors are 1.71 and "
        "2.70 on the coarse space and 2.47 and 4.11 on the fine space.\n"
    )

    def test_range_vs_repairing_flags_both_values(self) -> None:
        got = _codes(self.ABSTRACT + self.INTRO)
        assert [f.code for f in got] == [UNBRIDGED_HEADLINE_PAIR] * 2
        assert {f.claim for f in got} == {"2.70", "4.11"}

    def test_latex_range_and_unicode_dash(self) -> None:
        for dash in ("--", "\u2013", " to "):
            body = self.ABSTRACT.replace("--", dash) + self.INTRO
            assert len(_codes(body)) == 2

    def test_bridge_cue_silences(self) -> None:
        body = self.ABSTRACT + self.INTRO.replace(
            "On the", "Values are rounded differently here. On the"
        )
        assert _codes(body) == []

    def test_sentence_naming_both_values_bridges_only_those(self) -> None:
        body = self.ABSTRACT + self.INTRO.replace(
            "On the", "The 2.68 bound became 2.70 after a rerun. On the"
        )
        got = _codes(body)
        assert [f.claim for f in got] == ["4.11"]

    def test_body_sections_not_compared(self) -> None:
        body = (
            "# Methods\n\nWarm start cuts drag error to 2.68--4.10 for the lift drag objective.\n\n"
            "# Results\n\nOn the lift drag objective the errors are 1.71 and 2.70 "
            "and 2.47 and 4.11.\n"
        )
        assert _codes(body) == []

    def test_equal_values_silent(self) -> None:
        body = self.ABSTRACT + self.INTRO.replace("2.70", "2.68").replace("4.11", "4.10")
        assert _codes(body) == []

    def test_written_pair_not_double_reported(self) -> None:
        body = (
            "# Abstract\n\nThe headline errors are 2.68/4.10 for lift drag.\n\n"
            "# Introduction\n\nThe headline errors are 2.70/4.11 for lift drag.\n"
        )
        assert len(_codes(body)) == 1
