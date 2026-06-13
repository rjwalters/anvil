"""Tests for ``anvil/lib/numeric_consistency.py`` (issue #462).

Covers the acceptance criteria from the issue:

- The spread-failure fixture (70 / 56 / 54; "70-point spread" +
  "16 points ahead" where the named gap is 14) produces exactly two
  findings: one ``unbridged_population``, one ``gap_mismatch`` with the
  actual arithmetic in the message.
- A clean document with internally consistent arithmetic produces ZERO
  findings (the inactive-when-empty contract).
- The rounding tolerance (±1 unit / ±5% relative) is documented and
  tested — a "50%" claim over 47/94-style values passes.
- Advisory mode emits no ``CriticalFlag``; ``blocking=True`` emits
  flags that force ``Verdict.BLOCK`` through ``compute_verdict``.
- The sidecar ``<thread>.{N}.numeric/_review.json`` validates against
  the review schema and is discovered by ``critics.discover_critics``
  with no aggregator change.
- ``<!-- anvil-lint-disable: numeric_consistency -->`` suppression
  works (suppressed hits surface as info, never gate).
- Edge cases: numbers inside code fences / URLs / citation keys are
  NOT extracted; percentages vs absolute counts in the same window do
  not cross-match.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from anvil.lib.critics import aggregate, compute_verdict, discover_critics
from anvil.lib.numeric_consistency import (
    _FRACTION_RES,
    _PAIR_RES,
    GAP_MISMATCH,
    MULTIPLIER_MISMATCH,
    PERCENT_MISMATCH,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    UNBRIDGED_POPULATION,
    _extract_shapes,
    _paragraph_index,
    check_numeric_consistency,
    check_text,
    main,
    within_tolerance,
    write_review_dir,
)
from anvil.lib.review_schema import Review, Verdict


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


SPREAD_FAILURE_BODY = """# Season recap

Alpha ended the season on 70 points, while Beta closed at 56 and Gamma
collapsed to 54 after the winter break.

Alpha therefore finished 16 points ahead of Beta, and the final table
showed a 70-point spread from top to bottom.
"""

CLEAN_BODY = """# Season recap

Alpha ended the season on 70 points, while Beta closed at 56 and Gamma
collapsed to 54 after the winter break.

Alpha therefore finished 14 points ahead of Beta, and the final table
showed a 16-point spread from top to bottom.
"""


def make_memo_version_dir(tmp_path: Path, body: str, slug: str = "acme-seed") -> Path:
    """Build a #295-shaped memo version dir: <slug>/<slug>.1/<slug>.md."""
    version_dir = tmp_path / slug / f"{slug}.1"
    version_dir.mkdir(parents=True)
    (version_dir / f"{slug}.md").write_text(body, encoding="utf-8")
    return version_dir


# ---------------------------------------------------------------------------
# AC: spread-failure fixture
# ---------------------------------------------------------------------------


class TestSpreadFailureFixture:
    def test_two_findings_unbridged_and_gap_mismatch(self) -> None:
        findings, _numbers, _claims = check_text(SPREAD_FAILURE_BODY)
        assert len(findings) == 2
        codes = sorted(f.code for f in findings)
        assert codes == [GAP_MISMATCH, UNBRIDGED_POPULATION]

    def test_gap_mismatch_message_carries_actual_arithmetic(self) -> None:
        findings, _, _ = check_text(SPREAD_FAILURE_BODY)
        gap = next(f for f in findings if f.code == GAP_MISMATCH)
        # The named gap: 70 − 56 = 14, claim says 16.
        assert gap.claimed == 16
        assert gap.computed == 14
        assert "70" in gap.message
        assert "56" in gap.message
        assert "14" in gap.message

    def test_unbridged_population_names_the_raw_value(self) -> None:
        findings, _, _ = check_text(SPREAD_FAILURE_BODY)
        unbridged = next(f for f in findings if f.code == UNBRIDGED_POPULATION)
        assert unbridged.claimed == 70
        # The population spread max 70 − min 54 = 16.
        assert unbridged.computed == 16
        assert "unbridged" in unbridged.message

    def test_filesystem_entry_point(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, SPREAD_FAILURE_BODY)
        result = check_numeric_consistency(version_dir)
        assert not result.passed()
        assert len(result.findings) == 2
        assert result.body_path == "acme-seed.md"


# ---------------------------------------------------------------------------
# AC: clean document → zero findings
# ---------------------------------------------------------------------------


class TestCleanDocument:
    def test_consistent_arithmetic_zero_findings(self) -> None:
        findings, numbers, claims = check_text(CLEAN_BODY)
        assert findings == []
        assert claims == 2  # both claims were checked, both passed
        assert numbers > 0

    def test_no_numbers_zero_findings(self) -> None:
        findings, numbers, claims = check_text("Just prose. No quantities here.\n")
        assert findings == []
        assert numbers == 0
        assert claims == 0

    def test_clean_result_passes(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, CLEAN_BODY)
        result = check_numeric_consistency(version_dir)
        assert result.passed()
        assert result.to_json()["findings"] == []
        assert result.to_json()["pass"] is True


# ---------------------------------------------------------------------------
# AC: tolerance policy (±1 unit / ±5% relative)
# ---------------------------------------------------------------------------


class TestTolerance:
    def test_within_tolerance_contract(self) -> None:
        assert within_tolerance(50, 50.0)
        assert within_tolerance(15, 14)        # ±1 unit
        assert within_tolerance(105, 100)      # ±5% relative
        assert not within_tolerance(17, 14)    # off by 3: >1 unit, >5%
        assert not within_tolerance(70, 16)

    def test_50_percent_claim_over_47_of_94_passes(self) -> None:
        body = (
            "We surveyed the full cohort.\n\n"
            "Exactly 50% of respondents (47 of 94) preferred the new flow.\n"
        )
        findings, _, claims = check_text(body)
        assert claims == 1
        assert findings == []

    def test_38_percent_claim_over_47_of_94_fails_with_arithmetic(self) -> None:
        body = (
            "We surveyed the full cohort.\n\n"
            "Exactly 38% of respondents (47 of 94) preferred the new flow.\n"
        )
        findings, _, _ = check_text(body)
        assert len(findings) == 1
        f = findings[0]
        assert f.code == PERCENT_MISMATCH
        assert "50.0%" in f.message
        assert "47" in f.message and "94" in f.message

    def test_off_by_one_point_lead_passes(self) -> None:
        body = "Alpha scored 70 and Beta scored 56, a 15-point lead for Alpha.\n"
        findings, _, _ = check_text(body)
        assert findings == []

    def test_off_by_three_point_lead_fails(self) -> None:
        body = "Alpha scored 70 and Beta scored 56, a 17-point lead for Alpha.\n"
        findings, _, _ = check_text(body)
        assert len(findings) == 1
        assert findings[0].code == GAP_MISMATCH
        assert findings[0].computed == 14


# ---------------------------------------------------------------------------
# Multiplier + relative-percent claims (pair-shape gated)
# ---------------------------------------------------------------------------


class TestRatioClaims:
    def test_multiplier_pass(self) -> None:
        body = "Latency fell from 120 ms to 15 ms after the rewrite, an 8x speedup.\n"
        findings, _, _ = check_text(body)
        assert findings == []

    def test_multiplier_mismatch_carries_arithmetic(self) -> None:
        body = "Latency fell from 120 ms to 15 ms after the rewrite, a 10x speedup.\n"
        findings, _, _ = check_text(body)
        assert len(findings) == 1
        f = findings[0]
        assert f.code == MULTIPLIER_MISMATCH
        assert "120" in f.message and "15" in f.message
        assert "8.0x" in f.message
        # #469: displayed division must equal the displayed result.
        self._assert_displayed_arithmetic_consistent(f)

    @staticmethod
    def _assert_displayed_arithmetic_consistent(finding) -> None:
        """Parse 'num / den = result x' from the message; assert num/den ≈ result."""
        m = re.search(
            r"computes (?P<num>[\d.,]+) / (?P<den>[\d.,]+) = (?P<res>[\d.]+)x",
            finding.message,
        )
        assert m is not None, finding.message
        num = float(m.group("num").replace(",", ""))
        den = float(m.group("den").replace(",", ""))
        res = float(m.group("res"))
        assert round(num / den, 1) == pytest.approx(res)
        assert finding.computed == pytest.approx(num / den)

    def test_multiplier_mismatch_min_max_direction_arithmetic(self) -> None:
        # #469 defect 1 repro: best ratio is min/max (0.125), so the
        # message must show 15 / 120 = 0.1x — not 120 / 15 = 0.1x.
        body = "It went from 15 ms to 120 ms and was 2x slower.\n"
        findings, _, _ = check_text(body)
        assert len(findings) == 1
        f = findings[0]
        assert f.code == MULTIPLIER_MISMATCH
        assert "15 / 120 = 0.1x" in f.message
        self._assert_displayed_arithmetic_consistent(f)

    def test_multiplier_without_pair_shape_is_silent(self) -> None:
        # No explicit "from A to B" / "A vs B" evidence in the window —
        # conservative silence, not a guess.
        body = "The new engine delivers an 8x speedup over the baseline.\n"
        findings, _, claims = check_text(body)
        assert claims == 1
        assert findings == []

    def test_percent_relative_pass(self) -> None:
        body = "Throughput rose from 100 to 150 this quarter, a 50% increase.\n"
        findings, _, _ = check_text(body)
        assert findings == []

    def test_percent_relative_mismatch(self) -> None:
        body = "Throughput rose from 100 to 150 this quarter, a 75% increase.\n"
        findings, _, _ = check_text(body)
        assert len(findings) == 1
        assert findings[0].code == PERCENT_MISMATCH
        assert "50.0%" in findings[0].message

    def test_percent_relative_mismatch_names_single_base(self) -> None:
        # #469 defect 1: best_pct is one base convention's value, so the
        # message must name that base instead of claiming "either".
        body = "Throughput rose from 100 to 150 this quarter, a 75% increase.\n"
        findings, _, _ = check_text(body)
        assert len(findings) == 1
        msg = findings[0].message
        assert "either base convention" not in msg
        assert "(base 100)" in msg


# ---------------------------------------------------------------------------
# #469 defect 2: K/M/B scale suffixes on currency-prefixed shape operands
# ---------------------------------------------------------------------------


class TestScaleSuffixShapes:
    def test_mixed_scale_currency_pair_true_negative(self) -> None:
        # Repro from #469: a CORRECT document must emit zero findings
        # ($1.2B vs $600M is a 50% reduction once scales are applied).
        body = "Revenue grew from $1.2B to $600M after the spinoff, a 50% reduction.\n"
        findings, _, _ = check_text(body)
        assert findings == []

    def test_mixed_scale_currency_pair_true_positive(self) -> None:
        # An INCORRECT mixed-scale claim still fires, with scaled values.
        body = "Revenue grew from $1.2B to $600M after the spinoff, a 75% reduction.\n"
        findings, _, _ = check_text(body)
        assert len(findings) == 1
        f = findings[0]
        assert f.code == PERCENT_MISMATCH
        assert "1200000000" in f.message and "600000000" in f.message
        assert "50.0%" in f.message
        assert f.computed == pytest.approx(50.0)

    def test_bare_unit_suffix_not_scaled(self) -> None:
        # Ambiguity guard: scale is currency-gated, so a bare "m"
        # (meters/minutes) is never misread as millions.
        body = "The cable run grew from 12 m to 15 m this year.\n"
        shapes = _extract_shapes(body, _paragraph_index(body), _PAIR_RES)
        assert [(s.a, s.b) for s in shapes] == [(12.0, 15.0)]

    def test_attached_unit_suffix_not_scaled(self) -> None:
        # "12ms" must not be misread as 12 million + "s".
        body = "Latency went from 12ms to 15ms overnight.\n"
        shapes = _extract_shapes(body, _paragraph_index(body), _PAIR_RES)
        assert [(s.a, s.b) for s in shapes] == [(12.0, 15.0)]

    def test_currency_pair_with_spaced_suffix_scaled(self) -> None:
        # Currency-prefixed operands honor the suffix even with a space,
        # mirroring the _CURRENCY_RE tokenizer ("$12 M" = 12 million).
        body = "Spend grew from $12 M to $15 M this year.\n"
        shapes = _extract_shapes(body, _paragraph_index(body), _PAIR_RES)
        assert [(s.a, s.b) for s in shapes] == [(12e6, 15e6)]

    def test_currency_vs_pair_scaled(self) -> None:
        body = "It was $300K vs $1.2M for the rival bid.\n"
        shapes = _extract_shapes(body, _paragraph_index(body), _PAIR_RES)
        assert [(s.a, s.b) for s in shapes] == [(300e3, 1.2e6)]

    def test_currency_fraction_of_scaled(self) -> None:
        # Fraction "of" shape with mixed-scale currency operands.
        body = "We committed $1.2B of the $2.4B budget, fully 50% of it.\n"
        findings, _, _ = check_text(body)
        assert findings == []
        shapes = _extract_shapes(body, _paragraph_index(body), _FRACTION_RES)
        assert [(s.a, s.b) for s in shapes] == [(1.2e9, 2.4e9)]

    def test_plain_fraction_shapes_unchanged(self) -> None:
        # Bare-number fractions keep their pre-#469 behavior.
        body = "Exactly 47 of 94 reviewers approved, i.e. 47/94.\n"
        shapes = _extract_shapes(body, _paragraph_index(body), _FRACTION_RES)
        assert [(s.a, s.b) for s in shapes] == [(47.0, 94.0), (47.0, 94.0)]

    # -- #491: two-letter financial suffixes (bn / mn / tn) --

    def test_bn_currency_pair_true_negative(self) -> None:
        # #491 repro: a CORRECT $5bn -> $3bn doc (40% reduction off the
        # $5bn base) must emit zero findings. Before the two-letter
        # suffix fix, "$5bn" failed the \b assertion and produced no
        # shape, so this claim was silently un-checkable.
        body = "Revenue fell from $5bn to $3bn, a 40% reduction.\n"
        findings, _, _ = check_text(body)
        assert findings == []

    def test_bn_currency_pair_true_positive(self) -> None:
        # An INCORRECT $5bn -> $3bn claim now fires, with billion-scaled
        # operands surfaced in the message.
        body = "Revenue fell from $5bn to $3bn, a 75% reduction.\n"
        findings, _, _ = check_text(body)
        assert len(findings) == 1
        f = findings[0]
        assert f.code == PERCENT_MISMATCH
        assert "5000000000" in f.message and "3000000000" in f.message
        # The checker reports the base-relative change closest to the
        # asserted 75% — here (5-3)/3 = 66.7% off the $3bn base.
        assert f.computed == pytest.approx(66.666666, abs=1e-3)

    def test_mn_currency_pair_scaled(self) -> None:
        # "$5mn vs $3mn" tokenizes the two-letter million suffix.
        body = "It was $5mn vs $3mn for the rival bid.\n"
        shapes = _extract_shapes(body, _paragraph_index(body), _PAIR_RES)
        assert [(s.a, s.b) for s in shapes] == [(5e6, 3e6)]

    def test_bn_casing_scaled(self) -> None:
        # Mixed-case "Bn" is lowercased before the scale lookup.
        body = "Spend grew from $1.2Bn to $3Bn this year.\n"
        shapes = _extract_shapes(body, _paragraph_index(body), _PAIR_RES)
        assert [(s.a, s.b) for s in shapes] == [(1.2e9, 3e9)]

    def test_tn_currency_pair_scaled(self) -> None:
        # Trillion suffix ("tn") scales too.
        body = "Debt rose from $5tn to $3tn over the decade.\n"
        shapes = _extract_shapes(body, _paragraph_index(body), _PAIR_RES)
        assert [(s.a, s.b) for s in shapes] == [(5e12, 3e12)]

    def test_bare_bn_suffix_not_scaled(self) -> None:
        # Ambiguity guard: the two-letter suffix is still currency-gated,
        # so a bare "5 bn" (no "$") is NEVER read as 5 billion.
        body = "The herd grew from 5 bn to 3 bn animals.\n"
        shapes = _extract_shapes(body, _paragraph_index(body), _PAIR_RES)
        assert [(s.a, s.b) for s in shapes] == [(5.0, 3.0)]

    def test_bn_currency_tokenizer(self) -> None:
        # The currency tokenizer (not just shapes) recognizes "$5bn".
        from anvil.lib.numeric_consistency import _extract_numbers

        tokens = _extract_numbers("$5bn and $3mn raised.", [(0, 99, 0)])
        scaled = [(t.value, t.kind) for t in tokens if t.kind == "currency"]
        assert scaled == [(5e9, "currency"), (3e6, "currency")]

    def test_single_letter_suffix_still_scaled(self) -> None:
        # Regression guard: the existing single-letter b/m branch still
        # wins when no "n" follows ("$5b" stays 5 billion).
        body = "Revenue fell from $5b to $3b last year.\n"
        shapes = _extract_shapes(body, _paragraph_index(body), _PAIR_RES)
        assert [(s.a, s.b) for s in shapes] == [(5e9, 3e9)]


# ---------------------------------------------------------------------------
# AC: advisory vs blocking severity wiring
# ---------------------------------------------------------------------------


class TestSeverityWiring:
    def _finding_result(self, tmp_path: Path):
        version_dir = make_memo_version_dir(tmp_path, SPREAD_FAILURE_BODY)
        return version_dir, check_numeric_consistency(version_dir)

    def test_advisory_emits_no_critical_flags(self, tmp_path: Path) -> None:
        version_dir, result = self._finding_result(tmp_path)
        review = result.to_review(version_dir=version_dir.name)
        assert review.critical_flags == []
        assert all(f.severity == "minor" for f in review.findings)
        assert len(review.findings) == 2

    def test_advisory_verdict_not_blocked(self, tmp_path: Path) -> None:
        version_dir, result = self._finding_result(tmp_path)
        review = result.to_review(version_dir=version_dir.name)
        agg = aggregate([review])
        assert compute_verdict(agg, threshold=35) is not Verdict.BLOCK

    def test_blocking_emits_flags_and_forces_block(self, tmp_path: Path) -> None:
        version_dir, result = self._finding_result(tmp_path)
        review = result.to_review(version_dir=version_dir.name, blocking=True)
        assert len(review.critical_flags) == 2  # one per finding-code cluster
        flag_types = {f.type for f in review.critical_flags}
        assert any(GAP_MISMATCH in t for t in flag_types)
        assert any(UNBRIDGED_POPULATION in t for t in flag_types)
        agg = aggregate([review])
        assert compute_verdict(agg, threshold=35) is Verdict.BLOCK

    def test_blocking_on_clean_result_emits_nothing(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, CLEAN_BODY)
        result = check_numeric_consistency(version_dir)
        review = result.to_review(version_dir=version_dir.name, blocking=True)
        assert review.critical_flags == []
        assert review.findings == []


# ---------------------------------------------------------------------------
# AC: sidecar write + discovery (no aggregator change)
# ---------------------------------------------------------------------------


class TestSidecar:
    def test_write_review_dir_shape_and_schema(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, SPREAD_FAILURE_BODY)
        result = check_numeric_consistency(version_dir)
        out = write_review_dir(version_dir, result)
        assert out == version_dir.parent / "acme-seed.1.numeric" / "_review.json"
        assert out.is_file()
        # Round-trips through the typed schema.
        payload = json.loads(out.read_text(encoding="utf-8"))
        review = Review.model_validate(payload)
        assert review.critic_id == "numeric"
        assert review.kind.value == "tool_evidence"

    def test_discovered_by_discover_critics(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, SPREAD_FAILURE_BODY)
        result = check_numeric_consistency(version_dir)
        write_review_dir(version_dir, result)
        critics = discover_critics(version_dir)
        assert version_dir.parent / "acme-seed.1.numeric" in critics

    def test_rerun_regenerates_idempotently(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, SPREAD_FAILURE_BODY)
        result = check_numeric_consistency(version_dir)
        first = write_review_dir(version_dir, result)
        second = write_review_dir(version_dir, result)
        assert first == second
        assert second.is_file()
        # No stale staging dir left behind.
        leftovers = [p for p in version_dir.parent.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []


# ---------------------------------------------------------------------------
# AC: suppression directive
# ---------------------------------------------------------------------------


class TestSuppression:
    SUPPRESSED_BODY = (
        "Alpha ended on 70 points, Beta on 56, Gamma on 54.\n\n"
        "<!-- anvil-lint-disable: numeric_consistency -->\n"
        "The final table showed a 70-point spread from top to bottom.\n"
    )

    def test_suppressed_hit_surfaces_as_info(self) -> None:
        findings, _, _ = check_text(self.SUPPRESSED_BODY)
        assert len(findings) == 1
        f = findings[0]
        assert f.suppressed is True
        assert f.severity == SEVERITY_INFO
        assert "suppressed" in f.message

    def test_suppressed_findings_do_not_gate(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, self.SUPPRESSED_BODY)
        result = check_numeric_consistency(version_dir)
        assert result.passed()  # info-only findings never gate
        review = result.to_review(version_dir=version_dir.name)
        assert all(f.severity == "nit" for f in review.findings)
        # Even blocking mode never escalates a suppressed finding.
        blocking = result.to_review(version_dir=version_dir.name, blocking=True)
        assert blocking.critical_flags == []

    def test_unsuppressed_sibling_claim_still_fires(self) -> None:
        body = (
            "Alpha ended on 70 points, Beta on 56, Gamma on 54.\n"
            "Alpha finished 16 points ahead of Beta in the end.\n"
            "<!-- anvil-lint-disable: numeric_consistency -->\n"
            "The final table showed a 70-point spread from top to bottom.\n"
        )
        findings, _, _ = check_text(body)
        severities = sorted(f.severity for f in findings)
        assert severities == [SEVERITY_INFO, SEVERITY_WARNING]


# ---------------------------------------------------------------------------
# Edge cases: masking + class segregation
# ---------------------------------------------------------------------------


class TestExtractionEdgeCases:
    def test_code_fences_urls_citation_keys_not_extracted(self) -> None:
        body = (
            "See the [docs](https://example.com/v2/70-point-api?n=56) and\n"
            "the result of `score --max 70` per @smith2024 [-@jones1999].\n"
            "\n"
            "```python\n"
            "spread = 70 - 54  # 16\n"
            "values = [70, 56, 54]\n"
            "```\n"
        )
        findings, numbers, claims = check_text(body)
        assert numbers == 0
        assert claims == 0
        assert findings == []

    def test_masked_numbers_do_not_feed_claims(self) -> None:
        # The only raw values live inside a code fence — the spread claim
        # has <2 window candidates and stays silent (conservative).
        body = (
            "```\nAlpha 70, Beta 56, Gamma 54\n```\n"
            "\n"
            "The final table showed a 70-point spread from top to bottom.\n"
        )
        findings, _, claims = check_text(body)
        assert claims == 1
        assert findings == []

    def test_percent_tokens_do_not_bridge_point_claims(self) -> None:
        # A 34% token in the window must NOT satisfy (or pollute) the
        # "34 points ahead" claim — percent vs absolute counts never
        # cross-match. The count candidates 70/56 compute 14.
        body = (
            "Alpha holds a 34% win rate and sits on 70 points; Beta is on 56.\n"
            "Alpha is 34 points ahead of Beta.\n"
        )
        findings, _, _ = check_text(body)
        assert len(findings) == 1
        assert findings[0].code == GAP_MISMATCH
        assert findings[0].computed == 14

    def test_years_and_list_markers_excluded_from_candidates(self) -> None:
        # 2026 (year) and the "1." list marker must not become candidates;
        # the only real candidates are 70 and 56 → 14-point lead passes.
        body = (
            "In 2026 the league tightened up.\n"
            "1. Alpha finished on 70 points.\n"
            "2. Beta finished on 56 points.\n"
            "\n"
            "Alpha took a 14-point lead into the final.\n"
        )
        findings, _, _ = check_text(body)
        assert findings == []

    def test_pair_and_fraction_members_do_not_feed_point_claims(self) -> None:
        # The 120/15 latency pair and the 47/94 fraction are explicitly
        # bridged populations for their own ratio claims; they must not
        # pollute the point-difference candidate pool or its arithmetic.
        body = (
            "The incumbent holds 70 share points, the challenger 56, and the\n"
            "rest of the field trails at 54.\n"
            "\n"
            "That 16-point spread understates the race: the challenger sits\n"
            "only 14 points behind the leader. Conversion improved from\n"
            "120 ms to 15 ms, an 8x speedup, and 50% of pilot accounts\n"
            "(47 of 94) renewed.\n"
        )
        findings, _, claims = check_text(body)
        assert claims == 4
        assert findings == []  # every claim internally consistent

    def test_single_candidate_window_is_silent(self) -> None:
        body = "Alpha finished on 70 points, a 70-point spread.\n"
        findings, _, claims = check_text(body)
        assert claims == 1
        assert findings == []  # <2 candidates: insufficient evidence

    def test_latex_body_with_comments_and_cites(self, tmp_path: Path) -> None:
        version_dir = tmp_path / "paper" / "paper.1"
        version_dir.mkdir(parents=True)
        (version_dir / "main.tex").write_text(
            "Alpha scored 70 and Beta 56. % raw margin 99 here is a comment\n"
            "Alpha finished 14 points ahead of Beta \\cite{alpha2026study}.\n",
            encoding="utf-8",
        )
        result = check_numeric_consistency(version_dir)
        assert result.body_path == "main.tex"
        assert result.findings == []  # comment 99 masked; 70-56=14 passes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_findings_exit_code_and_write_review(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = make_memo_version_dir(tmp_path, SPREAD_FAILURE_BODY)
        rc = main([str(version_dir), "--write-review"])
        assert rc == 1
        out = capsys.readouterr()
        payload = json.loads(out.out)
        assert payload["check"] == "numeric_consistency"
        assert len(payload["findings"]) == 2
        sidecar = version_dir.parent / "acme-seed.1.numeric" / "_review.json"
        assert sidecar.is_file()

    def test_clean_exit_code_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        version_dir = make_memo_version_dir(tmp_path, CLEAN_BODY)
        rc = main([str(version_dir)])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["pass"] is True

    def test_missing_body_exit_code_two(self, tmp_path: Path) -> None:
        empty = tmp_path / "thread" / "thread.1"
        empty.mkdir(parents=True)
        assert main([str(empty)]) == 2

    def test_missing_version_dir_exit_code_two(self, tmp_path: Path) -> None:
        assert main([str(tmp_path / "nope" / "nope.1")]) == 2

    def test_blocking_flag_writes_flags_into_sidecar(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = make_memo_version_dir(tmp_path, SPREAD_FAILURE_BODY)
        rc = main([str(version_dir), "--write-review", "--blocking"])
        assert rc == 1
        sidecar = version_dir.parent / "acme-seed.1.numeric" / "_review.json"
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert len(payload["critical_flags"]) == 2
