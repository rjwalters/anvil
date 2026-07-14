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
- Body resolution: ``<thread>.md`` slug-echo (with precedence over the
  fixed names) and every fixed name in ``FIXED_BODY_NAMES`` —
  ``main.tex``, ``report.md``, ``deck.md``, ``proposal.tex``,
  ``installation.tex``, ``datasheet.tex``, ``spec.tex`` (issue #475);
  missing body → exit 2 with the full chain in the message.
- CLI: version-dir critic-sibling discovery, ``--scoring`` single-file
  mode, exit codes 0/1/2, JSON output shape.
- Doc coverage: ``memo-review.md`` wires the self-check; the rubric
  snippet and ``voice_grounding.md`` cross-reference each other; the
  #475 rollout guards — 8 table-shaped reviewers wire the quote rule +
  self-check, and all 10 rubrics carry the pointer paragraph. Issue
  #496: the 2 machine-summary ip reviewers now wire the active
  write-time ``--scoring _summary.md`` self-check (the #475 deferral
  sentence is gone) and both ip rubrics describe the JSON ``dimensions``
  block (not a markdown table).
- Machine-summary scorecard (issue #496): ``parse_machine_summary_
  dimensions`` extracts non-null scored dims from a ``_summary.md`` JSON
  ``dimensions`` block (sibling ``rubric`` key ignored, ``null`` scores
  skipped, per-dim ``weight`` read incl. provisional D9 ``/6``,
  malformed/absent JSON → empty rows); ``check_summary_text`` /
  ``check_version_dir`` route it through the SAME classifier; the
  ``--scoring _summary.md`` CLI resolves ``spec.tex`` and preserves exit
  codes 0/1/2; discovery routes machine-summary siblings via
  ``_meta.json`` ``scorecard_kind``.
- Specialist rollout (issue #497): the 9 scored-justification specialist
  critics (3 deck specialists + 6 ip/ip-provisional verifying critics)
  wire the quote sub-bullet + the ``--scoring _summary.md`` write-time
  self-check, mirroring the #475/#496 pattern; the ~22 structurally
  exempt commands (``*-audit``, ``*-vision``, ``*-figure-content``,
  ``*-perspective``, ``ip-uspto-adversary``, ``ip-uspto-fto``) stay
  unwired — a negative guard locks that scope decision into the suite.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from anvil.lib.evidence_check import (
    ELISION_WINDOW_CHARS,
    FABRICATED_EVIDENCE,
    FIXED_BODY_NAMES,
    MIN_QUOTE_CHARS,
    MISSING_EVIDENCE,
    SEVERITY_MAJOR,
    SEVERITY_MINOR,
    MACHINE_SUMMARY_KIND,
    SummaryDimension,
    check_scoring_text,
    check_summary_text,
    check_version_dir,
    classify_justification,
    discover_scoring_files,
    extract_quoted_spans,
    has_absence_marker,
    main,
    normalize,
    parse_machine_summary_dimensions,
    scorecard_kind_for,
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

    def test_tex_body_quote_from_input_child_passes(self, tmp_path: Path) -> None:
        # Issue #643: a paper multi-file thread's body lives in \input-ed
        # section files. A reviewer quoting a child section must validate
        # against the RESOLVED body, not the ~90-line main.tex shell —
        # otherwise a legitimate quote trips a false fabricated_evidence.
        version_dir = tmp_path / "paper" / "paper.1"
        (version_dir / "sections").mkdir(parents=True)
        (version_dir / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\n"
            "\\input{sections/method}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        (version_dir / "sections" / "method.tex").write_text(
            "\\section{Method}\n"
            "We evaluate on a held-out corpus of 4,200 documents.\n",
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
                        '"held-out corpus of 4,200 documents"',
                    )
                ]
            ),
            encoding="utf-8",
        )
        result = check_version_dir(version_dir)
        # The quote is verbatim from sections/method.tex — it must pass
        # because the resolved body includes the \input child.
        assert result.passed(), (
            "quote drawn from an \\input-ed child must validate against the "
            "resolved body (issue #643), not be flagged fabricated"
        )

    def test_tex_single_file_thread_unchanged(self, tmp_path: Path) -> None:
        # Regression: a single-file thread (no \input/\include) behaves
        # byte-identically to the pre-#643 main.tex-only check — a fabricated
        # quote is still caught.
        version_dir = tmp_path / "paper" / "paper.1"
        version_dir.mkdir(parents=True)
        (version_dir / "main.tex").write_text(
            "\\section{Method}\nThe real body text lives here.\n",
            encoding="utf-8",
        )
        review = version_dir.parent / "paper.1.review"
        review.mkdir()
        (review / "scoring.md").write_text(
            scoring_table(
                [("Methodology", 6, 5, '"a quote that is nowhere in the body"')]
            ),
            encoding="utf-8",
        )
        result = check_version_dir(version_dir)
        assert not result.passed()
        codes = {f.code for f in result.findings}
        assert FABRICATED_EVIDENCE in codes

    @pytest.mark.parametrize(
        "body_name,child_rel",
        [
            ("installation.tex", "figures/site-plan.tex"),
            ("proposal.tex", "figures/topology.tex"),
        ],
    )
    def test_tex_body_quote_from_input_child_passes_per_skill(
        self, tmp_path: Path, body_name: str, child_rel: str
    ) -> None:
        # Issue #653 (follow-up to #643): installation / proposal both ship a
        # first-class \input{figures/<name>.tex} TikZ-standalone convention, so
        # their review commands now read the RESOLVED body. The verifier side
        # (check_version_dir) already handles any .tex body generically via
        # FIXED_BODY_NAMES + resolve_tex_inputs — this locks that coverage in
        # per-skill (the pre-existing guard only exercised main.tex).
        version_dir = tmp_path / "thread" / "thread.1"
        (version_dir / "figures").mkdir(parents=True)
        (version_dir / body_name).write_text(
            "\\documentclass{article}\n\\begin{document}\n"
            f"\\input{{{child_rel[:-4]}}}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        (version_dir / child_rel).write_text(
            "% TikZ standalone site/topology diagram\n"
            "The circulation loop routes visitors past the north gallery.\n",
            encoding="utf-8",
        )
        review = version_dir.parent / "thread.1.review"
        review.mkdir()
        (review / "scoring.md").write_text(
            scoring_table(
                [
                    (
                        "Spatial resolution",
                        6,
                        5,
                        '"circulation loop routes visitors past the north gallery"',
                    )
                ]
            ),
            encoding="utf-8",
        )
        result = check_version_dir(version_dir)
        assert result.body_path == body_name
        assert result.passed(), (
            f"quote drawn from an \\input-ed child of {body_name} must "
            "validate against the resolved body (issue #653/#643), not be "
            "flagged fabricated"
        )

    def test_datasheet_single_file_thread_unchanged(self, tmp_path: Path) -> None:
        # Issue #653: datasheet is \includegraphics-only (no in-body \input
        # convention), so its review reads datasheet.tex alone — documented
        # safe. The verifier's generic .tex handling must still behave
        # byte-identically for a single-file datasheet body: a real quote
        # passes, and the existing detection chain resolves datasheet.tex.
        version_dir = tmp_path / "chip" / "chip.1"
        version_dir.mkdir(parents=True)
        (version_dir / "datasheet.tex").write_text(
            "\\section{General Description}\n"
            "The AX101 integrates a 16-lane MIPI receiver and an on-die ISP.\n",
            encoding="utf-8",
        )
        review = version_dir.parent / "chip.1.review"
        review.mkdir()
        (review / "scoring.md").write_text(
            scoring_table(
                [
                    (
                        "Completeness",
                        6,
                        5,
                        '"16-lane MIPI receiver and an on-die ISP"',
                    )
                ]
            ),
            encoding="utf-8",
        )
        result = check_version_dir(version_dir)
        assert result.body_path == "datasheet.tex"
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

    @pytest.mark.parametrize("body_name", FIXED_BODY_NAMES)
    def test_fixed_body_names_resolve(
        self, tmp_path: Path, body_name: str
    ) -> None:
        # Issue #475: report.md / deck.md / proposal.tex /
        # installation.tex / datasheet.tex / spec.tex join main.tex in
        # the fixed-name detection chain.
        version_dir = tmp_path / "thread" / "thread.1"
        version_dir.mkdir(parents=True)
        (version_dir / body_name).write_text(
            "The retrofit market is underserved by incumbents chasing "
            "greenfield deployments.\n",
            encoding="utf-8",
        )
        review = version_dir.parent / "thread.1.review"
        review.mkdir()
        (review / "scoring.md").write_text(
            scoring_table(
                [
                    (
                        "Evidence quality",
                        6,
                        4,
                        '"retrofit market is underserved by incumbents" '
                        "(— §2).",
                    )
                ]
            ),
            encoding="utf-8",
        )
        result = check_version_dir(version_dir)
        assert result.body_path == body_name
        assert result.passed()

    def test_slug_echo_wins_over_fixed_names(self, tmp_path: Path) -> None:
        # Slug-echo (#295) resolves FIRST even when a fixed name is also
        # present in the version dir.
        version_dir = tmp_path / "acme" / "acme.1"
        version_dir.mkdir(parents=True)
        (version_dir / "acme.md").write_text(
            "slug-echo body wins the detection chain\n", encoding="utf-8"
        )
        (version_dir / "report.md").write_text(
            "fixed-name body must not be selected\n", encoding="utf-8"
        )
        result = check_version_dir(version_dir)
        assert result.body_path == "acme.md"

    def test_missing_body_raises(self, tmp_path: Path) -> None:
        version_dir = tmp_path / "empty" / "empty.1"
        version_dir.mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            check_version_dir(version_dir)

    def test_missing_body_error_lists_full_chain(
        self, tmp_path: Path
    ) -> None:
        # Issue #475 AC: the exit-code-2 message lists the full
        # detection chain (slug-echo + every fixed name).
        version_dir = tmp_path / "empty" / "empty.1"
        version_dir.mkdir(parents=True)
        with pytest.raises(FileNotFoundError) as excinfo:
            check_version_dir(version_dir)
        message = str(excinfo.value)
        assert "empty.md" in message
        for name in FIXED_BODY_NAMES:
            assert name in message

    def test_missing_version_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            check_version_dir(tmp_path / "nope" / "nope.1")


# The canary's legacy paper.tex body carries a quotable span so a
# matching justification validates against the overridden body.
PAPER_TEX_BODY = (
    "\\section{Method}\n"
    "We ablate the encoder depth across four settings and report the "
    "median across five seeds.\n"
)
PAPER_TEX_JUST = '"ablate the encoder depth across four settings"'


def _paper_tex_scoring(version_dir: Path) -> Path:
    """Write a critic-sibling scoring.md whose quote is verbatim from PAPER_TEX_BODY."""
    review = version_dir.parent / f"{version_dir.name}.review"
    review.mkdir()
    (review / "scoring.md").write_text(
        scoring_table([("Methodology", 6, 5, PAPER_TEX_JUST)]),
        encoding="utf-8",
    )
    return review / "scoring.md"


class TestBodyOverride:
    """The #670 body-path override — ``body=`` kwarg + CLI ``--body``.

    ``evidence_check`` has no sidecar / ``--write-review`` (per its
    module docstring); the override just lets the verifier point at a
    non-canonical entry point (``paper.tex``) and records the resolved
    portfolio-relative path in ``body_path``.
    """

    def _legacy_dir(self, tmp_path: Path, body_name: str = "paper.tex") -> Path:
        version_dir = tmp_path / "tractatus" / "tractatus.1"
        version_dir.mkdir(parents=True)
        (version_dir / body_name).write_text(PAPER_TEX_BODY, encoding="utf-8")
        return version_dir

    def test_relative_override_locates_non_canonical_body(self, tmp_path: Path) -> None:
        version_dir = self._legacy_dir(tmp_path)
        _paper_tex_scoring(version_dir)
        result = check_version_dir(version_dir, body=Path("paper.tex"))
        assert result.body_path == "paper.tex"
        assert result.passed()

    def test_no_override_still_hard_fails_on_legacy_thread(self, tmp_path: Path) -> None:
        # Without the override, paper.tex is outside the discovery chain.
        version_dir = self._legacy_dir(tmp_path)
        with pytest.raises(FileNotFoundError):
            check_version_dir(version_dir)

    def test_absolute_override_outside_version_dir(self, tmp_path: Path) -> None:
        version_dir = self._legacy_dir(tmp_path, body_name="placeholder.tex")
        _paper_tex_scoring(version_dir)
        scratch = tmp_path / "tractatus" / "scratch"
        scratch.mkdir(parents=True)
        staged = scratch / "paper.tex"
        staged.write_text(PAPER_TEX_BODY, encoding="utf-8")
        result = check_version_dir(version_dir, body=staged)
        # Outside version_dir but under portfolio root (tmp_path).
        assert result.body_path == "tractatus/scratch/paper.tex"
        assert result.passed()

    def test_missing_override_raises_naming_the_override(self, tmp_path: Path) -> None:
        version_dir = self._legacy_dir(tmp_path)
        with pytest.raises(FileNotFoundError) as excinfo:
            check_version_dir(version_dir, body=Path("does-not-exist.tex"))
        assert "does-not-exist.tex" in str(excinfo.value)

    def test_cli_body_flag_locates_non_canonical_body(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = self._legacy_dir(tmp_path)
        _paper_tex_scoring(version_dir)
        rc = main([str(version_dir), "--body", "paper.tex"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["body_path"] == "paper.tex"
        assert payload["pass"] is True

    def test_cli_missing_override_exit_code_two(self, tmp_path: Path) -> None:
        version_dir = self._legacy_dir(tmp_path)
        assert main([str(version_dir), "--body", "nope.tex"]) == 2

    def test_body_and_scoring_combine(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        # The canary shape: --scoring <path> --body paper.tex validates
        # quoted evidence against paper.tex directly.
        version_dir = self._legacy_dir(tmp_path)
        staging = version_dir.parent / f".{version_dir.name}.review.tmp"
        staging.mkdir()
        scoring = staging / "scoring.md"
        scoring.write_text(
            scoring_table([("Methodology", 6, 5, FABRICATED_JUST)]),
            encoding="utf-8",
        )
        rc = main([str(version_dir), "--scoring", str(scoring), "--body", "paper.tex"])
        assert rc == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["body_path"] == "paper.tex"
        assert payload["findings"][0]["code"] == FABRICATED_EVIDENCE


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


# ---------------------------------------------------------------------------
# Doc coverage — issue #475 rollout to the remaining main reviewers
# ---------------------------------------------------------------------------


# (skill, reviewer command, body filename quoted in the rule, self-check step)
TABLE_SHAPED_REVIEWERS = [
    ("paper", "paper-review.md", "main.tex", "5b"),
    ("report", "report-review.md", "report.md", "5b"),
    ("deck", "deck-review.md", "deck.md", "8b"),
    ("slides", "slides-review.md", "deck.md", "7b"),
    ("proposal", "proposal-review.md", "proposal.tex", "5b"),
    ("installation", "installation-review.md", "installation.tex", "5b"),
    ("datasheet", "datasheet-review.md", "datasheet.tex", "5b"),
    ("essay", "essay-review.md", "<thread>.md", "6b"),
]

# Machine-summary scorecards: issue #496 upgrades these from the #475
# Option-A prose-only rule to the active deterministic write-time
# --scoring _summary.md self-check, mirroring the table-shaped
# reviewers. (skill, reviewer command, body filename, self-check step)
MACHINE_SUMMARY_REVIEWERS = [
    ("ip-uspto", "ip-uspto-review.md", "spec.tex", "9b"),
    ("ip-uspto-provisional", "ip-uspto-provisional-review.md", "spec.tex", "9b"),
]

ROLLOUT_RUBRIC_SKILLS = [
    "paper",
    "report",
    "deck",
    "slides",
    "proposal",
    "installation",
    "datasheet",
    "ip-uspto",
    "ip-uspto-provisional",
    "essay",
]


@pytest.mark.parametrize(
    "skill,command,body,step", TABLE_SHAPED_REVIEWERS
)
def test_review_doc_wires_the_self_check(
    skill: str, command: str, body: str, step: str
) -> None:
    doc = (
        REPO_ROOT / f"anvil/skills/{skill}/commands/{command}"
    ).read_text(encoding="utf-8")
    # Edit 1: the quote sub-bullet in the scoring step.
    assert "Quoted-evidence requirement (issue #464 / #475)" in doc
    if skill == "paper":
        # Issue #643: paper (renamed from `pub`, #694) is the multi-file LaTeX skill; the quote rule was
        # broadened from "verbatim quote from `main.tex`" to "verbatim quote
        # from the resolved body" (main.tex OR its \input/\include children).
        # The load-bearing claim is still that a verbatim quote is required
        # and the body source is named.
        assert "verbatim quote from the resolved body" in doc
        assert "`main.tex`" in doc
    else:
        assert f"verbatim quote from `{body}`" in doc
    assert "no instance of <X> found" in doc
    assert "Elision with `...` / `…` is permitted" in doc
    assert "ELISION_WINDOW_CHARS" in doc
    # Edit 2: the write-time self-check sub-step.
    assert f"{step}. **Validate quoted evidence" in doc
    assert "anvil.lib.evidence_check" in doc
    assert "--scoring" in doc
    assert "fabricated_evidence" in doc
    assert "missing_evidence" in doc


@pytest.mark.parametrize(
    "skill,command,body,step", MACHINE_SUMMARY_REVIEWERS
)
def test_ip_review_doc_wires_the_self_check(
    skill: str, command: str, body: str, step: str
) -> None:
    doc = (
        REPO_ROOT / f"anvil/skills/{skill}/commands/{command}"
    ).read_text(encoding="utf-8")
    # The prose quote rule still binds.
    assert "Quoted-evidence requirement (issue #464 / #475" in doc
    assert f"verbatim quote from `{body}`" in doc
    assert "no instance of <X> found" in doc
    assert "Elision with `...` / `…` is permitted" in doc
    assert "ELISION_WINDOW_CHARS" in doc
    # Issue #496: the deferral sentence is gone; the active write-time
    # --scoring _summary.md self-check is now wired.
    assert "Deterministic self-check deferred to issue #496" not in doc
    assert f"{step}. **Validate quoted evidence" in doc
    assert "anvil.lib.evidence_check" in doc
    assert "--scoring" in doc
    assert "_summary.md" in doc
    assert "fabricated_evidence" in doc
    assert "missing_evidence" in doc


def test_ip_rubrics_describe_json_dimensions_not_table() -> None:
    """Issue #496: the stale 'markdown table' scorecard prose is fixed."""
    for skill in ("ip-uspto", "ip-uspto-provisional"):
        doc = (
            REPO_ROOT / f"anvil/skills/{skill}/rubric.md"
        ).read_text(encoding="utf-8")
        # The scorecard description is now the JSON dimensions block.
        assert "JSON `dimensions` block" in doc
        # The deferral wording is gone; the self-check is wired.
        assert "is **deferred** for this skill" not in doc
        assert "is **wired** for this skill" in doc


@pytest.mark.parametrize("skill", ROLLOUT_RUBRIC_SKILLS)
def test_rollout_rubric_points_to_snippet_rule(skill: str) -> None:
    doc = (
        REPO_ROOT / f"anvil/skills/{skill}/rubric.md"
    ).read_text(encoding="utf-8")
    assert "Quoted evidence (issue #464 / #475)" in doc
    assert 'Dimension scoring guidance" rule' in doc
    assert "evidence_check" in doc
    # No weight / threshold changes shipped with the pointer paragraph.
    assert "No weight or threshold changes" in doc


# ---------------------------------------------------------------------------
# Machine-summary JSON scorecard parser (issue #496)
# ---------------------------------------------------------------------------


# A spec.tex body whose passages the justifications below quote verbatim.
SPEC_TEX = r"""\documentclass{anvil-uspto}
\begin{document}
\section{Detailed Description}
The apparatus comprises a controller \refnum{10} that modulates the
adaptive bias loop \refnum{20} in response to a sensed temperature.
In one embodiment, the bias loop operates across a range of 5--80 GHz.
The brief description of drawings lists every figure shown in the
detailed description, and every reference numeral appears in at least
one drawing.
\end{document}
"""


def summary_md(
    dimensions: dict,
    *,
    critic: str = "review",
    rubric_total: int = 45,
) -> str:
    """Build a machine-summary ``_summary.md`` with a JSON dimensions block.

    ``dimensions`` maps each dim key to ``None`` (un-owned) or a dict
    carrying ``score`` / ``weight`` / ``justification`` — the exact
    shape the two ip reviewers emit.
    """
    payload = {
        "critic": critic,
        "for_version": 1,
        "rubric": {
            "id": "anvil-ip-uspto-v2",
            "total": rubric_total,
            "advance_threshold": 39,
            "dimensions": 9,
        },
        "dimensions": dimensions,
        "critical_flag": False,
    }
    return (
        "# Review summary\n\n```json\n"
        + json.dumps(payload, indent=2)
        + "\n```\n"
    )


def make_ip_version_dir(
    tmp_path: Path, body: str = SPEC_TEX, slug: str = "acme-widget"
) -> Path:
    """Build an ip-uspto-shaped version dir: <slug>/<slug>.1/spec.tex."""
    version_dir = tmp_path / slug / f"{slug}.1"
    version_dir.mkdir(parents=True)
    (version_dir / "spec.tex").write_text(body, encoding="utf-8")
    return version_dir


# Justifications quoting SPEC_TEX verbatim / fabricated / by-absence.
SPEC_MATCHING_JUST = (
    'Detailed description covers it ("modulates the adaptive bias loop" '
    "— ¶[0012])."
)
SPEC_FABRICATED_JUST = (
    'Claims the spec teaches "a quantum entanglement coupler" but it '
    "does not appear in spec.tex."
)
SPEC_ABSENCE_JUST = (
    "no instance of orphan reference numeral found across spec and "
    "drawings."
)
SPEC_MISSING_JUST = "Solid disclosure throughout, well organized."


class TestParseMachineSummaryDimensions:
    def test_parses_scored_dims_and_skips_null(self) -> None:
        text = summary_md(
            {
                "claim_breadth": None,
                "specification_completeness": {
                    "weight": 5,
                    "score": 4,
                    "justification": SPEC_MATCHING_JUST,
                },
            }
        )
        rows = parse_machine_summary_dimensions(text)
        by_name = {r.dimension: r for r in rows}
        assert by_name["claim_breadth"].score is None
        spec = by_name["specification_completeness"]
        assert spec.score == 4
        assert spec.weight == 5
        assert spec.justification == SPEC_MATCHING_JUST

    def test_sibling_rubric_key_is_ignored(self) -> None:
        # The rubric block is a sibling key; only `dimensions` is read.
        text = summary_md({"formal_compliance": {"score": 3, "justification": "x"}})
        rows = parse_machine_summary_dimensions(text)
        assert [r.dimension for r in rows] == ["formal_compliance"]

    def test_provisional_d9_weight_six_read(self) -> None:
        text = summary_md(
            {
                "claim_spec_correspondence": {
                    "weight": 6,
                    "score": 6,
                    "justification": SPEC_ABSENCE_JUST,
                }
            }
        )
        rows = parse_machine_summary_dimensions(text)
        assert rows[0].weight == 6
        assert rows[0].score == 6

    def test_weight_defaults_to_score_when_absent(self) -> None:
        # No `weight` key: defaults to the score so a full-weight
        # by-absence justification still clears rule 2.
        text = summary_md(
            {"drawing_text_correspondence": {"score": 5, "justification": SPEC_ABSENCE_JUST}}
        )
        rows = parse_machine_summary_dimensions(text)
        assert rows[0].weight == 5

    def test_null_score_dim_emits_skippable_row(self) -> None:
        text = summary_md({"novelty": {"score": None, "justification": "n/a"}})
        rows = parse_machine_summary_dimensions(text)
        assert rows[0].score is None

    def test_malformed_json_returns_empty(self) -> None:
        text = "# Review\n\n```json\n{ not valid json ,,, }\n```\n"
        assert parse_machine_summary_dimensions(text) == []

    def test_absent_json_block_returns_empty(self) -> None:
        text = "# Review\n\nNo fenced json block here at all.\n"
        assert parse_machine_summary_dimensions(text) == []

    def test_block_without_dimensions_key_returns_empty(self) -> None:
        text = "# Review\n\n```json\n{ \"critic\": \"review\" }\n```\n"
        assert parse_machine_summary_dimensions(text) == []

    def test_first_dimensions_block_wins(self) -> None:
        # A leading non-dimensions json block is skipped; the second
        # (carrying `dimensions`) is parsed.
        text = (
            "# Review\n\n```json\n{ \"meta\": 1 }\n```\n\n"
            + summary_md({"formal_compliance": {"score": 3, "justification": "x"}})
        )
        rows = parse_machine_summary_dimensions(text)
        assert [r.dimension for r in rows] == ["formal_compliance"]

    def test_bare_numeric_dim_value_tolerated(self) -> None:
        text = summary_md({"formal_compliance": 3})
        rows = parse_machine_summary_dimensions(text)
        assert rows[0].score == 3
        assert rows[0].justification is None

    def test_float_score_narrowed_to_int(self) -> None:
        text = summary_md(
            {"formal_compliance": {"score": 4.0, "weight": 5, "justification": "x"}}
        )
        rows = parse_machine_summary_dimensions(text)
        assert rows[0].score == 4


class TestCheckSummaryText:
    def test_matching_span_passes(self) -> None:
        text = summary_md(
            {
                "specification_completeness": {
                    "weight": 5,
                    "score": 4,
                    "justification": SPEC_MATCHING_JUST,
                }
            }
        )
        findings, checked = check_summary_text(text, SPEC_TEX)
        assert checked == 1
        assert findings == []

    def test_fabricated_span_is_major(self) -> None:
        text = summary_md(
            {
                "specification_completeness": {
                    "weight": 5,
                    "score": 4,
                    "justification": SPEC_FABRICATED_JUST,
                }
            }
        )
        findings, checked = check_summary_text(text, SPEC_TEX)
        assert checked == 1
        assert findings[0].code == FABRICATED_EVIDENCE
        assert findings[0].severity == SEVERITY_MAJOR

    def test_no_span_is_minor_missing(self) -> None:
        text = summary_md(
            {
                "formal_compliance": {
                    "weight": 5,
                    "score": 3,
                    "justification": SPEC_MISSING_JUST,
                }
            }
        )
        findings, _ = check_summary_text(text, SPEC_TEX)
        assert findings[0].code == MISSING_EVIDENCE
        assert findings[0].severity == SEVERITY_MINOR

    def test_full_weight_by_absence_passes(self) -> None:
        text = summary_md(
            {
                "drawing_text_correspondence": {
                    "weight": 5,
                    "score": 5,
                    "justification": SPEC_ABSENCE_JUST,
                }
            }
        )
        findings, _ = check_summary_text(text, SPEC_TEX)
        assert findings == []

    def test_provisional_d9_six_by_absence_passes(self) -> None:
        # D9 /6: ceiling-by-absence requires score == weight == 6.
        text = summary_md(
            {
                "claim_spec_correspondence": {
                    "weight": 6,
                    "score": 6,
                    "justification": SPEC_ABSENCE_JUST,
                }
            }
        )
        findings, _ = check_summary_text(text, SPEC_TEX)
        assert findings == []

    def test_calibration_suffix_quote_alongside_match_passes(self) -> None:
        # The carried-over #475 calibration risk: ip justifications quote
        # rubric/claim language heavily. A non-matching rubric-prose
        # quote ALONGSIDE one matching spec.tex quote must pass (rule 1).
        just = (
            'Meets the "sophisticated patent attorney would have no '
            'substantive objection" calibration bar; the spec '
            '"modulates the adaptive bias loop" (— ¶[0012]) is fully '
            "described."
        )
        text = summary_md(
            {
                "specification_completeness": {
                    "weight": 5,
                    "score": 5,
                    "justification": just,
                }
            }
        )
        findings, _ = check_summary_text(text, SPEC_TEX)
        assert findings == []

    def test_elision_span_across_nearby_passages_passes(self) -> None:
        # Two ≥MIN_QUOTE_CHARS fragments, each verbatim in SPEC_TEX, in
        # document order, within the proximity window.
        just = (
            'Disclosed: "The apparatus comprises a controller ... that '
            'modulates the adaptive bias loop" (— ¶[0012]).'
        )
        text = summary_md(
            {
                "specification_completeness": {
                    "weight": 5,
                    "score": 4,
                    "justification": just,
                }
            }
        )
        findings, _ = check_summary_text(text, SPEC_TEX)
        assert findings == []

    def test_null_scores_not_counted(self) -> None:
        text = summary_md(
            {
                "claim_breadth": None,
                "novelty": {"score": None, "justification": "n/a"},
            }
        )
        findings, checked = check_summary_text(text, SPEC_TEX)
        assert checked == 0
        assert findings == []


def summary_md_table(
    rows: List[Tuple[str, int, object, str]],
    *,
    rubric_total: int = 45,
) -> str:
    """Build a table-shaped machine-summary ``_summary.md``.

    Mirrors the shape the ip ``_summary.md`` scorecards actually carry
    (issue #536): a JSON *rubric metadata* block (NO ``dimensions``
    object) followed by the ``| # | Dimension | Weight | Score |
    Justification |`` markdown table. ``rows`` are
    ``(dim, weight, score, just)`` tuples — pass ``"null"`` for an
    un-owned dim's score.
    """
    rubric = {
        "id": "anvil-ip-provisional-v1",
        "total": rubric_total,
        "advance_threshold": 39,
        "dimensions": 9,
        "prior_rubric_id": None,
    }
    return (
        "# s112 critic summary\n\n## Rubric block\n\n```json\n"
        + json.dumps(rubric, indent=2)
        + "\n```\n\n## Scorecard\n\n"
        + scoring_table(rows)
    )


class TestMachineSummaryTableFallback:
    """The table-shaped machine-summary scorecard is checked (issue #536).

    The ip commands/examples emit the scored dims in a markdown TABLE,
    not a fenced-JSON ``dimensions`` block. ``check_summary_text`` must
    fall back to the table parser so the write-time self-check is
    non-vacuous (``dimensions_checked > 0``) in real ip reviews.
    """

    def test_table_only_summary_is_checked_genuine_quotes(self) -> None:
        # No JSON dimensions block — only the rubric metadata + table.
        text = summary_md_table(
            [
                ("Specification completeness", 5, 4, SPEC_MATCHING_JUST),
                ("Drawings sufficiency", 5, "null", "n/a — see review"),
            ]
        )
        # Sanity: the JSON path finds nothing to check here.
        assert parse_machine_summary_dimensions(text) == []
        findings, checked = check_summary_text(text, SPEC_TEX)
        assert checked == 1  # one owned dim; the null row is skipped
        assert findings == []

    def test_table_fallback_catches_fabricated_quote(self) -> None:
        # Proves the fallback runs a LIVE check, not just a row count.
        text = summary_md_table(
            [("Specification completeness", 5, 4, SPEC_FABRICATED_JUST)]
        )
        findings, checked = check_summary_text(text, SPEC_TEX)
        assert checked == 1
        assert len(findings) == 1
        assert findings[0].code == FABRICATED_EVIDENCE
        assert findings[0].severity == SEVERITY_MAJOR

    def test_multiple_owned_dims_all_checked(self) -> None:
        text = summary_md_table(
            [
                ("Specification completeness", 5, 4, SPEC_MATCHING_JUST),
                ("Drawing-text correspondence", 5, 5, SPEC_ABSENCE_JUST),
                ("Prior-art positioning", 4, "null", "n/a — see priorart"),
                ("Conversion readiness", 6, 4, SPEC_FABRICATED_JUST),
            ]
        )
        findings, checked = check_summary_text(text, SPEC_TEX)
        assert checked == 3  # two genuine + one fabricated; null skipped
        assert len(findings) == 1
        assert findings[0].code == FABRICATED_EVIDENCE

    def test_json_path_still_preferred_when_present(self) -> None:
        # A summary carrying a real JSON dimensions block uses it (the
        # fallback only fires when JSON yields no checkable rows).
        text = summary_md(
            {
                "specification_completeness": {
                    "weight": 5,
                    "score": 4,
                    "justification": SPEC_FABRICATED_JUST,
                }
            }
        )
        findings, checked = check_summary_text(text, SPEC_TEX)
        assert checked == 1
        assert findings[0].code == FABRICATED_EVIDENCE


def _write_meta(critic_dir: Path, kind: str) -> None:
    (critic_dir / "_meta.json").write_text(
        json.dumps({"critic": "review", "scorecard_kind": kind}),
        encoding="utf-8",
    )


class TestMachineSummaryFilesystem:
    def test_scoring_summary_single_file_mode(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = make_ip_version_dir(tmp_path)
        staging = version_dir.parent / f".{version_dir.name}.review.tmp"
        staging.mkdir()
        summary = staging / "_summary.md"
        summary.write_text(
            summary_md(
                {
                    "specification_completeness": {
                        "weight": 5,
                        "score": 4,
                        "justification": SPEC_MATCHING_JUST,
                    }
                }
            ),
            encoding="utf-8",
        )
        rc = main([str(version_dir), "--scoring", str(summary)])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["body_path"] == "spec.tex"
        assert payload["dimensions_checked"] == 1
        assert payload["pass"] is True

    def test_scoring_summary_fabricated_exit_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = make_ip_version_dir(tmp_path)
        staging = version_dir.parent / f".{version_dir.name}.review.tmp"
        staging.mkdir()
        summary = staging / "_summary.md"
        summary.write_text(
            summary_md(
                {
                    "specification_completeness": {
                        "weight": 5,
                        "score": 4,
                        "justification": SPEC_FABRICATED_JUST,
                    }
                }
            ),
            encoding="utf-8",
        )
        rc = main([str(version_dir), "--scoring", str(summary)])
        assert rc == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["findings"][0]["code"] == FABRICATED_EVIDENCE

    def test_discovery_routes_machine_summary_via_meta(
        self, tmp_path: Path
    ) -> None:
        version_dir = make_ip_version_dir(tmp_path)
        review = version_dir.parent / f"{version_dir.name}.review"
        review.mkdir()
        (review / "_summary.md").write_text(
            summary_md(
                {
                    "specification_completeness": {
                        "weight": 5,
                        "score": 4,
                        "justification": SPEC_FABRICATED_JUST,
                    }
                }
            ),
            encoding="utf-8",
        )
        _write_meta(review, MACHINE_SUMMARY_KIND)
        result = check_version_dir(version_dir)
        assert result.scoring_files == [str(review / "_summary.md")]
        assert result.dimensions_checked == 1
        assert result.findings[0].code == FABRICATED_EVIDENCE

    def test_scorecard_kind_for_reads_meta(self, tmp_path: Path) -> None:
        review = tmp_path / "x.1.review"
        review.mkdir()
        summary = review / "_summary.md"
        summary.write_text("x", encoding="utf-8")
        _write_meta(review, MACHINE_SUMMARY_KIND)
        assert scorecard_kind_for(summary) == MACHINE_SUMMARY_KIND

    def test_scorecard_kind_for_missing_meta_is_none(
        self, tmp_path: Path
    ) -> None:
        review = tmp_path / "x.1.review"
        review.mkdir()
        summary = review / "_summary.md"
        summary.write_text("x", encoding="utf-8")
        assert scorecard_kind_for(summary) is None

    def test_aggregator_critic_summary_chosen_over_table(
        self, tmp_path: Path
    ) -> None:
        # A critic carrying BOTH files + machine-summary meta: only the
        # _summary.md is checked (the scorecard of record).
        version_dir = make_ip_version_dir(tmp_path)
        review = version_dir.parent / f"{version_dir.name}.review"
        review.mkdir()
        (review / "_summary.md").write_text(
            summary_md(
                {
                    "specification_completeness": {
                        "weight": 5,
                        "score": 4,
                        "justification": SPEC_MATCHING_JUST,
                    }
                }
            ),
            encoding="utf-8",
        )
        (review / "scoring.md").write_text(
            scoring_table([("Specification", 5, 4, FABRICATED_JUST)]),
            encoding="utf-8",
        )
        _write_meta(review, MACHINE_SUMMARY_KIND)
        result = check_version_dir(version_dir)
        assert result.scoring_files == [str(review / "_summary.md")]
        # The summary justification matches → clean; the table's
        # fabricated quote is NOT checked.
        assert result.passed()


# ---------------------------------------------------------------------------
# Doc coverage — issue #497 rollout to the scored specialist critics
# ---------------------------------------------------------------------------


# The 9 scored-justification specialist critics: the 3 scored deck
# specialists + the 6 scored ip/ip-provisional verifying critics. Each
# emits a machine-summary _summary.md scorecard (JSON dimensions block or
# a markdown scoring table inside _summary.md) and owns ≥1 non-null
# per-dimension justification, so the quoted-evidence contract fits.
# (skill, command, body filename quoted in the rule, self-check step)
SCORED_SPECIALIST_CRITICS = [
    ("deck", "deck-narrative.md", "deck.md", "9b"),
    ("deck", "deck-market.md", "deck.md", "8b"),
    ("deck", "deck-design.md", "deck.md", "9b"),
    ("ip-uspto", "ip-uspto-claims.md", "spec.tex", "13b"),
    ("ip-uspto", "ip-uspto-112.md", "spec.tex", "14b"),
    ("ip-uspto", "ip-uspto-101.md", "spec.tex", "10b"),
    ("ip-uspto", "ip-uspto-prior-art.md", "spec.tex", "10b"),
    ("ip-uspto-provisional", "ip-uspto-provisional-112.md", "spec.tex", "11b"),
    (
        "ip-uspto-provisional",
        "ip-uspto-provisional-prior-art.md",
        "spec.tex",
        "9b",
    ),
]

# Structurally exempt commands that MUST NOT carry the self-check wiring
# (issue #497 curation scope decision): findings-only critics (all-null
# scorecard), VLM critics (evidence is a decoded image, not a text
# span), and audit commands (own no rubric dimension). A future
# blanket-rollout PR must not silently mis-wire any of these.
# (skill, command)
EXEMPT_UNWIRED_COMMANDS = [
    ("ip-uspto", "ip-uspto-adversary.md"),  # findings-only, all-null
    ("ip-uspto", "ip-uspto-fto.md"),  # findings-only, all-null
    ("deck", "deck-vision.md"),  # VLM — evidence is a decoded image
    ("ip-uspto", "ip-uspto-audit.md"),  # auditor owns no dimension
]


@pytest.mark.parametrize("skill,command,body,step", SCORED_SPECIALIST_CRITICS)
def test_specialist_critic_doc_wires_the_self_check(
    skill: str, command: str, body: str, step: str
) -> None:
    doc = (
        REPO_ROOT / f"anvil/skills/{skill}/commands/{command}"
    ).read_text(encoding="utf-8")
    # Edit 1: the quote sub-bullet in the scoring step.
    assert "Quoted-evidence requirement (issue #464 / #475)" in doc
    assert f"verbatim quote from `{body}`" in doc
    assert "no instance of <X> found" in doc
    assert "Elision with `...` / `…` is permitted" in doc
    assert "ELISION_WINDOW_CHARS" in doc
    # Edit 2: the write-time --scoring _summary.md self-check sub-step.
    assert f"{step}. **Validate quoted evidence" in doc
    assert "anvil.lib.evidence_check" in doc
    assert "--scoring" in doc
    assert "_summary.md" in doc
    assert "fabricated_evidence" in doc
    assert "missing_evidence" in doc


@pytest.mark.parametrize("skill,command", EXEMPT_UNWIRED_COMMANDS)
def test_exempt_critic_doc_stays_unwired(skill: str, command: str) -> None:
    """Issue #497: the exempt families MUST NOT be spuriously wired.

    Locks the scope decision into the suite — a future blanket rollout
    can't silently force a body-quote contract onto a VLM critic, an
    audit command, or a findings-only critic. The guard: no
    ``**Validate quoted evidence`` self-check sub-step exists, and the
    #475-shaped quote sub-bullet is absent.
    """
    doc = (
        REPO_ROOT / f"anvil/skills/{skill}/commands/{command}"
    ).read_text(encoding="utf-8")
    assert "**Validate quoted evidence" not in doc
    assert "Quoted-evidence requirement (issue #464 / #475)" not in doc
