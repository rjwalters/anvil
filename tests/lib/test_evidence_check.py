"""Tests for ``anvil/lib/evidence_check.py`` (issue #464).

Covers the acceptance criteria from the issue curation:

- Quote extraction: straight + curly double quotes, the
  ``MIN_QUOTE_CHARS`` cutoff, multiple spans per table cell.
- Normalization: whitespace collapse, markdown emphasis stripping,
  curly-quote folding; matching is case-sensitive.
- Classification matrix: matching span → pass; ceiling-by-absence →
  pass; spans-present-but-none-match → major ``fabricated_evidence``;
  no spans → minor ``missing_evidence`` advisory — including the
  calibration-suffix case (a non-matching rubric-prose quote alongside
  one matching body quote → pass).
- Body resolution: ``<thread>.md`` and ``main.tex`` variants; missing
  body → exit 2.
- CLI: version-dir critic-sibling discovery, ``--scoring`` single-file
  mode, exit codes 0/1/2, JSON output shape.
- Doc coverage: ``memo-review.md`` wires the self-check; the rubric
  snippet and ``voice_grounding.md`` cross-reference each other.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from anvil.lib.evidence_check import (
    ELISION_WINDOW_CHARS,
    FABRICATED_EVIDENCE,
    MIN_QUOTE_CHARS,
    MISSING_EVIDENCE,
    SEVERITY_MAJOR,
    SEVERITY_MINOR,
    check_scoring_text,
    check_version_dir,
    classify_justification,
    discover_scoring_files,
    extract_quoted_spans,
    has_absence_marker,
    main,
    normalize,
    span_matches_body,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


BODY = """# Acme seed memo

## Recommendation

We recommend a $500K pre-seed check into Acme, conditional on the
pilot converting to a paid contract by Q3.

## Thesis

The thesis is that **warehouse robotics retrofits** beat greenfield
automation on payback period. The retrofit market is underserved by
incumbents chasing greenfield deployments.

## Risks

The single-customer concentration risk is named explicitly and
mitigated by the LOI pipeline.
"""


def scoring_table(rows: List[Tuple[str, int, object, str]]) -> str:
    """Build a memo-shaped scoring.md table from (dim, weight, score, just)."""
    out = [
        "| # | Dimension | Weight | Score | Justification |",
        "|---|---|---|---|---|",
    ]
    for i, (dim, weight, score, just) in enumerate(rows, start=1):
        out.append(f"| {i} | {dim} | {weight} | {score} | {just} |")
    return "\n".join(out) + "\n"


def make_memo_version_dir(tmp_path: Path, body: str = BODY, slug: str = "acme-seed") -> Path:
    """Build a #295-shaped memo version dir: <slug>/<slug>.1/<slug>.md."""
    version_dir = tmp_path / slug / f"{slug}.1"
    version_dir.mkdir(parents=True)
    (version_dir / f"{slug}.md").write_text(body, encoding="utf-8")
    return version_dir


MATCHING_JUST = (
    'Sharp ask: "conditional on the pilot converting to a paid contract" '
    "(— §Recommendation)."
)
FABRICATED_JUST = (
    'Claims "the founders previously exited a robotics startup" but the '
    "memo never says this."
)
MISSING_JUST = "Solid evidence trail throughout the memo."


# ---------------------------------------------------------------------------
# Quote extraction
# ---------------------------------------------------------------------------


class TestQuoteExtraction:
    def test_straight_quotes_extracted(self) -> None:
        spans = extract_quoted_spans(MATCHING_JUST)
        assert spans == ["conditional on the pilot converting to a paid contract"]

    def test_curly_quotes_extracted(self) -> None:
        spans = extract_quoted_spans(
            "Names the risk: “single-customer concentration risk” (§Risks)."
        )
        assert spans == ["single-customer concentration risk"]

    def test_min_length_cutoff_drops_trivial_quotes(self) -> None:
        # "why now" and "soft target" are idiomatic quoting, not evidence.
        assert extract_quoted_spans('Strong "why now" framing.') == []
        assert len(normalize("why now")) < MIN_QUOTE_CHARS

    def test_multiple_spans_per_cell(self) -> None:
        just = (
            'Quotes "conditional on the pilot converting" and also '
            '"underserved by incumbents chasing greenfield" in one cell.'
        )
        assert len(extract_quoted_spans(just)) == 2

    def test_mixed_straight_and_curly(self) -> None:
        just = 'One "straight quoted span here" and one “curly quoted span here”.'
        assert len(extract_quoted_spans(just)) == 2


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_whitespace_collapse_matches_across_line_breaks(self) -> None:
        # The body wraps "beat greenfield\nautomation" across a line break.
        finding = classify_justification(
            dimension="Thesis coherence",
            score=5,
            weight=6,
            justification='"beat greenfield automation on payback period" (§Thesis)',
            normalized_body=normalize(BODY),
        )
        assert finding is None

    def test_markdown_emphasis_stripped_both_sides(self) -> None:
        # Body has **warehouse robotics retrofits**; the quote has none.
        finding = classify_justification(
            dimension="Thesis coherence",
            score=5,
            weight=6,
            justification='"warehouse robotics retrofits" plus more grounding prose',
            normalized_body=normalize(BODY),
        )
        assert finding is None

    def test_curly_quote_folding(self) -> None:
        finding = classify_justification(
            dimension="Risk honesty",
            score=5,
            weight=6,
            justification="Names “single-customer concentration risk” head-on.",
            normalized_body=normalize(BODY),
        )
        assert finding is None

    def test_matching_is_case_sensitive(self) -> None:
        finding = classify_justification(
            dimension="Risk honesty",
            score=5,
            weight=6,
            justification='"Single-Customer Concentration Risk" is addressed.',
            normalized_body=normalize(BODY),
        )
        assert finding is not None
        assert finding.code == FABRICATED_EVIDENCE


# ---------------------------------------------------------------------------
# Classification matrix
# ---------------------------------------------------------------------------


def _classify(score: Optional[int], weight: int, just: str):
    return classify_justification(
        dimension="dim",
        score=score,
        weight=weight,
        justification=just,
        normalized_body=normalize(BODY),
    )


class TestClassification:
    def test_matching_span_passes(self) -> None:
        assert _classify(4, 5, MATCHING_JUST) is None

    def test_ceiling_by_absence_passes(self) -> None:
        assert _classify(4, 4, "Tight throughout — no instance of multi-paragraph hedging found.") is None

    def test_absence_marker_below_ceiling_is_missing_evidence(self) -> None:
        finding = _classify(3, 4, "no instance of hedging found, but other gaps.")
        assert finding is not None
        assert finding.code == MISSING_EVIDENCE
        assert finding.severity == SEVERITY_MINOR

    def test_fabricated_evidence_is_major(self) -> None:
        finding = _classify(5, 6, FABRICATED_JUST)
        assert finding is not None
        assert finding.code == FABRICATED_EVIDENCE
        assert finding.severity == SEVERITY_MAJOR
        assert "fabricated" in finding.message

    def test_no_spans_is_minor_advisory(self) -> None:
        finding = _classify(4, 6, MISSING_JUST)
        assert finding is not None
        assert finding.code == MISSING_EVIDENCE
        assert finding.severity == SEVERITY_MINOR
        assert finding.spans_extracted == 0

    def test_calibration_suffix_quote_tolerated_alongside_matching_quote(self) -> None:
        # A rubric_overrides calibration suffix legitimately quotes rubric
        # prose that is NOT in the body; one matching body quote → pass.
        just = (
            '"underserved by incumbents chasing greenfield" (§Thesis). '
            'calibration applied: "score on integration quality not on fresh sizing"'
        )
        assert _classify(4, 4, just) is None

    def test_null_score_row_is_skipped(self) -> None:
        assert _classify(None, 6, "") is None

    def test_full_weight_without_marker_or_quote_is_missing_evidence(self) -> None:
        finding = _classify(4, 4, "Flawless dimension.")
        assert finding is not None
        assert finding.code == MISSING_EVIDENCE
        assert "no instance of <X> found" in finding.message

    def test_empty_justification_is_missing_evidence(self) -> None:
        finding = _classify(2, 6, "")
        assert finding is not None
        assert finding.code == MISSING_EVIDENCE


# ---------------------------------------------------------------------------
# Ellipsis elision (issue #478)
# ---------------------------------------------------------------------------


class TestElision:
    def test_ascii_ellipsis_elision_passes(self) -> None:
        # The issue-body repro: both fragments verbatim, '...' elides.
        finding = _classify(
            3, 5, '"The thesis is that ... beat greenfield automation"'
        )
        assert finding is None

    def test_unicode_ellipsis_elision_passes(self) -> None:
        finding = _classify(
            3, 5, '"The thesis is that … beat greenfield automation"'
        )
        assert finding is None

    def test_four_dot_run_is_an_elision_marker(self) -> None:
        body = normalize(BODY)
        assert span_matches_body(
            "The thesis is that .... beat greenfield automation", body
        )

    def test_out_of_order_fragments_are_fabricated(self) -> None:
        # Body order is "The thesis is that ... beat greenfield automation";
        # reversed fragments must NOT pass (anti-stitching ordering).
        finding = _classify(
            3, 5, '"beat greenfield automation ... The thesis is that"'
        )
        assert finding is not None
        assert finding.code == FABRICATED_EVIDENCE
        assert finding.severity == SEVERITY_MAJOR

    def test_short_fragment_fails_per_fragment_floor(self) -> None:
        # "The thesis" (10 chars) is below the per-fragment floor even
        # though it is verbatim and in order — trivial-stitching guard.
        assert len(normalize("The thesis")) < MIN_QUOTE_CHARS
        finding = _classify(
            3, 5, '"The thesis ... beat greenfield automation on payback"'
        )
        assert finding is not None
        assert finding.code == FABRICATED_EVIDENCE

    def test_distant_fragments_outside_window_are_rejected(self) -> None:
        # Two verbatim, floor-clearing, in-order fragments separated by
        # more than ELISION_WINDOW_CHARS must NOT stitch into a pass.
        filler = "filler sentence padding the gap. " * 40  # ~1320 chars
        body = normalize(
            "The retrofit thesis opens the memo here. "
            + filler
            + "The closing ask lands at the very end."
        )
        span = (
            "The retrofit thesis opens the memo ... "
            "closing ask lands at the very end"
        )
        assert not span_matches_body(span, body)
        finding = classify_justification(
            dimension="d",
            score=3,
            weight=5,
            justification=f'"{span}"',
            normalized_body=body,
        )
        assert finding is not None
        assert finding.code == FABRICATED_EVIDENCE

    def test_nearby_fragments_inside_window_pass(self) -> None:
        # Same shape as the window-rejection test but within the window.
        body = normalize(
            "The retrofit thesis opens the memo here. One short bridge "
            "sentence sits between. The closing ask lands at the very end."
        )
        assert span_matches_body(
            "The retrofit thesis opens the memo ... "
            "closing ask lands at the very end",
            body,
        )

    def test_window_constant_is_canary_tunable_documented(self) -> None:
        # Ship-as-constant posture (MIN_QUOTE_CHARS precedent).
        assert ELISION_WINDOW_CHARS == 500

    def test_leading_ellipsis_degrades_to_plain_span(self) -> None:
        finding = _classify(
            3, 5, '"... beat greenfield automation on payback period"'
        )
        assert finding is None

    def test_trailing_ellipsis_degrades_to_plain_span(self) -> None:
        finding = _classify(
            3, 5, '"The retrofit market is underserved by incumbents ..."'
        )
        assert finding is None

    def test_literal_body_ellipsis_is_preserved_by_normalize(self) -> None:
        # Elision handling lives in span matching, NOT normalize() —
        # body text containing a literal ellipsis must survive intact.
        assert "..." in normalize("The plan is simple... ship it now.")
        assert "…" in normalize("The plan is simple… ship it now.")

    def test_literal_body_ellipsis_quote_matches_verbatim(self) -> None:
        # A verbatim quote of a literal body ellipsis passes via the
        # plain-substring check even though its second fragment would
        # fail the per-fragment floor under elision splitting.
        body = normalize("The plan is simple... ship it. Nothing else.")
        assert span_matches_body("The plan is simple... ship it", body)

    def test_two_dots_are_not_an_elision_marker(self) -> None:
        body = normalize(BODY)
        assert not span_matches_body(
            "The thesis is that .. beat greenfield automation", body
        )

    def test_three_fragment_elision_in_order(self) -> None:
        finding = _classify(
            3,
            5,
            '"The thesis is that ... beat greenfield automation '
            '... underserved by incumbents"',
        )
        assert finding is None


# ---------------------------------------------------------------------------
# Dash folding (issue #478)
# ---------------------------------------------------------------------------


DASH_BODY = """# Dash memo

Retrofits — not greenfield builds — win on payback math today.
The en-dash range 2024–2026 covers the pilot window. Run the
self-check with the --scoring flag before the sidecar lands.
"""


class TestDashFolding:
    def test_double_hyphen_quote_matches_em_dash_body(self) -> None:
        body = normalize(DASH_BODY)
        assert span_matches_body(
            "Retrofits -- not greenfield builds -- win on payback math",
            body,
        )

    def test_verbatim_em_dash_quote_still_passes(self) -> None:
        body = normalize(DASH_BODY)
        assert span_matches_body(
            "Retrofits — not greenfield builds — win on payback math",
            body,
        )

    def test_triple_hyphen_quote_matches_em_dash_body(self) -> None:
        body = normalize(DASH_BODY)
        assert span_matches_body(
            "Retrofits --- not greenfield builds --- win on payback math",
            body,
        )

    def test_en_dash_folds_symmetrically(self) -> None:
        body = normalize(DASH_BODY)
        assert span_matches_body("en-dash range 2024--2026 covers", body)
        assert span_matches_body("en-dash range 2024–2026 covers", body)

    def test_double_hyphen_literal_stays_self_consistent(self) -> None:
        # `--scoring`-style literals fold identically on both sides.
        body = normalize(DASH_BODY)
        assert span_matches_body(
            "self-check with the --scoring flag before", body
        )

    def test_single_hyphen_is_not_folded(self) -> None:
        # Compound words keep their hyphen — "self-check" must not
        # match a body that spells it "self—check".
        assert normalize("self-check") == "self-check"
        assert not span_matches_body("self-check", normalize("self—check"))

    def test_tex_body_dash_markup(self, tmp_path: Path) -> None:
        # LaTeX bodies use --/--- as en/em dash markup; a reviewer
        # quoting the rendered dash (or the source markup) must pass.
        version_dir = tmp_path / "paper" / "paper.1"
        version_dir.mkdir(parents=True)
        (version_dir / "main.tex").write_text(
            "\\section{Method}\n"
            "Retrofits---not greenfield builds---win on payback math; "
            "the 2024--2026 pilot window confirms it.\n",
            encoding="utf-8",
        )
        review = version_dir.parent / "paper.1.review"
        review.mkdir()
        (review / "scoring.md").write_text(
            scoring_table(
                [
                    (
                        "Methodology",
                        6,
                        5,
                        '"Retrofits—not greenfield builds—win on payback '
                        'math" and "the 2024–2026 pilot window confirms it"',
                    )
                ]
            ),
            encoding="utf-8",
        )
        result = check_version_dir(version_dir)
        assert result.passed()


class TestCheckScoringText:
    def test_mixed_table(self) -> None:
        table = scoring_table(
            [
                ("Recommendation clarity", 5, 5, MATCHING_JUST),
                ("Thesis coherence", 6, 5, FABRICATED_JUST),
                ("Evidence quality", 6, 4, MISSING_JUST),
                ("Rhetorical economy", 4, 4, "no instance of hedging-as-cushion found"),
                ("Citation recall", 3, "null", "not owned by this critic"),
            ]
        )
        findings, checked = check_scoring_text(table, BODY)
        assert checked == 4  # null row skipped
        codes = sorted(f.code for f in findings)
        assert codes == [FABRICATED_EVIDENCE, MISSING_EVIDENCE]
        fabricated = next(f for f in findings if f.code == FABRICATED_EVIDENCE)
        assert fabricated.dimension == "Thesis coherence"

    def test_clean_table_zero_findings(self) -> None:
        table = scoring_table([("Recommendation clarity", 5, 4, MATCHING_JUST)])
        findings, checked = check_scoring_text(table, BODY)
        assert findings == []
        assert checked == 1


class TestAbsenceMarker:
    @pytest.mark.parametrize(
        "text",
        [
            "no instance of fabricated traction found",
            "No instances of scope creep found in the appendices",
        ],
    )
    def test_marker_variants(self, text: str) -> None:
        assert has_absence_marker(text)

    def test_non_marker_prose(self) -> None:
        assert not has_absence_marker("instances were found of hedging")


# ---------------------------------------------------------------------------
# Body resolution + filesystem entry point
# ---------------------------------------------------------------------------


class TestBodyResolution:
    def test_slug_md_body(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path)
        review = version_dir.parent / f"{version_dir.name}.review"
        review.mkdir()
        (review / "scoring.md").write_text(
            scoring_table([("Recommendation clarity", 5, 4, MATCHING_JUST)]),
            encoding="utf-8",
        )
        result = check_version_dir(version_dir)
        assert result.body_path == "acme-seed.md"
        assert result.passed()

    def test_main_tex_body(self, tmp_path: Path) -> None:
        version_dir = tmp_path / "paper" / "paper.1"
        version_dir.mkdir(parents=True)
        (version_dir / "main.tex").write_text(
            "\\section{Method}\nWe ablate the encoder depth across four settings.\n",
            encoding="utf-8",
        )
        review = version_dir.parent / "paper.1.review"
        review.mkdir()
        (review / "scoring.md").write_text(
            scoring_table(
                [("Methodology", 6, 5, '"ablate the encoder depth across four settings"')]
            ),
            encoding="utf-8",
        )
        result = check_version_dir(version_dir)
        assert result.body_path == "main.tex"
        assert result.passed()

    def test_missing_body_raises(self, tmp_path: Path) -> None:
        version_dir = tmp_path / "empty" / "empty.1"
        version_dir.mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            check_version_dir(version_dir)

    def test_missing_version_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            check_version_dir(tmp_path / "nope" / "nope.1")


class TestDiscovery:
    def test_discovers_all_critic_siblings(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path)
        for critic in ("review", "audit"):
            sibling = version_dir.parent / f"{version_dir.name}.{critic}"
            sibling.mkdir()
            (sibling / "scoring.md").write_text(
                scoring_table([("Evidence quality", 6, 4, MISSING_JUST)]),
                encoding="utf-8",
            )
        # A sibling without scoring.md (e.g. .numeric) is not discovered.
        (version_dir.parent / f"{version_dir.name}.numeric").mkdir()
        # A leading-dot staging dir is invisible to the glob.
        staging = version_dir.parent / f".{version_dir.name}.review.tmp"
        staging.mkdir()
        (staging / "scoring.md").write_text("partial", encoding="utf-8")

        found = discover_scoring_files(version_dir)
        assert [p.parent.name for p in found] == [
            "acme-seed.1.audit",
            "acme-seed.1.review",
        ]
        result = check_version_dir(version_dir)
        assert len(result.findings) == 2  # one missing_evidence per sibling
        assert result.dimensions_checked == 2

    def test_zero_siblings_is_clean_pass(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path)
        result = check_version_dir(version_dir)
        assert result.passed()
        assert result.scoring_files == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_clean_exit_code_zero_and_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = make_memo_version_dir(tmp_path)
        review = version_dir.parent / f"{version_dir.name}.review"
        review.mkdir()
        (review / "scoring.md").write_text(
            scoring_table([("Recommendation clarity", 5, 4, MATCHING_JUST)]),
            encoding="utf-8",
        )
        rc = main([str(version_dir)])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["check"] == "evidence_check"
        assert payload["pass"] is True
        assert payload["dimensions_checked"] == 1

    def test_findings_exit_code_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = make_memo_version_dir(tmp_path)
        review = version_dir.parent / f"{version_dir.name}.review"
        review.mkdir()
        (review / "scoring.md").write_text(
            scoring_table([("Thesis coherence", 6, 5, FABRICATED_JUST)]),
            encoding="utf-8",
        )
        rc = main([str(version_dir)])
        assert rc == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["findings"][0]["code"] == FABRICATED_EVIDENCE
        assert payload["findings"][0]["severity"] == SEVERITY_MAJOR

    def test_scoring_flag_single_file_mode(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = make_memo_version_dir(tmp_path)
        # Staging-dir self-check shape: scoring.md NOT in a critic sibling.
        staging = version_dir.parent / f".{version_dir.name}.review.tmp"
        staging.mkdir()
        scoring = staging / "scoring.md"
        scoring.write_text(
            scoring_table([("Evidence quality", 6, 4, MISSING_JUST)]),
            encoding="utf-8",
        )
        rc = main([str(version_dir), "--scoring", str(scoring)])
        assert rc == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["scoring_files"] == [str(scoring)]
        assert payload["findings"][0]["code"] == MISSING_EVIDENCE

    def test_missing_body_exit_code_two(self, tmp_path: Path) -> None:
        version_dir = tmp_path / "empty" / "empty.1"
        version_dir.mkdir(parents=True)
        assert main([str(version_dir)]) == 2

    def test_missing_version_dir_exit_code_two(self, tmp_path: Path) -> None:
        assert main([str(tmp_path / "nope" / "nope.1")]) == 2

    def test_missing_scoring_file_exit_code_two(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path)
        assert main([str(version_dir), "--scoring", str(tmp_path / "absent.md")]) == 2


# ---------------------------------------------------------------------------
# Doc coverage (grep-test precedent)
# ---------------------------------------------------------------------------


def test_memo_review_doc_wires_the_self_check() -> None:
    doc = (
        REPO_ROOT / "anvil/skills/memo/commands/memo-review.md"
    ).read_text(encoding="utf-8")
    assert "anvil.lib.evidence_check" in doc
    assert "fabricated_evidence" in doc
    assert "no instance of <X> found" in doc
    # Issue #478: step 5 documents the permitted elision form.
    assert "Elision with `...` / `…` is permitted" in doc
    assert "ELISION_WINDOW_CHARS" in doc


def test_rubric_snippet_carries_quoted_evidence_rule() -> None:
    doc = (
        REPO_ROOT / "anvil/lib/snippets/rubric.md"
    ).read_text(encoding="utf-8")
    assert "Quoted-evidence sub-rule" in doc
    assert "no instance of <X> found" in doc
    assert "voice_grounding.md" in doc
    assert "evidence_check" in doc
    # Issue #478: rule 1 documents the permitted elision form.
    assert "Elision with `...` / `…` is permitted" in doc
    assert "ELISION_WINDOW_CHARS" in doc


def test_voice_grounding_snippet_cross_references_back() -> None:
    doc = (
        REPO_ROOT / "anvil/lib/snippets/voice_grounding.md"
    ).read_text(encoding="utf-8")
    assert "quoted-evidence" in doc


def test_memo_rubric_points_to_snippet_rule() -> None:
    doc = (
        REPO_ROOT / "anvil/skills/memo/rubric.md"
    ).read_text(encoding="utf-8")
    assert "evidence_check" in doc
    assert "Quoted evidence" in doc
