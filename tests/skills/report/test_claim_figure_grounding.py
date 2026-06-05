"""Tests for ``anvil/skills/report/lib/claim_figure_grounding.py`` (Epic #328 Phase 6).

Per-skill test filename convention (#58): this file is named
``test_claim_figure_grounding.py`` and lives under ``tests/skills/report/``;
the ``tests/skills/report/__init__.py`` chain prevents collision with any
sibling skill that ships a same-named detector test in the future.

The fixture suite locks in:

- The three prose-detection regex classes (prepositional / subject-verb /
  parenthetical) with positive cases for each.
- The label-id vocabulary (integer, dotted, single uppercase letter).
- The three ground-truth roster sources (LaTeX ``\\label{}`` macros,
  markdown ``{#prefix:id}`` anchors, filename-derived labels in
  ``figures/`` and ``exhibits/`` subdirs).
- The closest-match suggestion (numeric distance for integer ids,
  ``difflib.get_close_matches`` for alphabetic ids, class-restricted).
- The dedupe-on-``(label_class, label_id)`` contract.
- The critical-flag heuristic (raised on any missing label).
- The false-positive disciplines (quoted material, fenced code, inline
  backticks).
- The auto-discovery contract (``<version_dir>.claim-figure-grounding/``
  sibling is recognized by ``anvil/lib/critics.py::discover_critics``).
- The CLI entry-point shape (exit codes, ``--write-review`` opt-in).
- Doc-coverage on ``commands/report-claim-figure-grounding.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib.critics import aggregate, discover_critics, load_review
from anvil.lib.review_schema import Kind, Review
from anvil.skills.report.lib.claim_figure_grounding import (
    CRITIC_ID,
    CRITICAL_FLAG_TYPE,
    DIM_CLAIM_FIGURE_GROUNDING,
    GROUNDING_SUFFIX,
    LABEL_CLASS_CHART,
    LABEL_CLASS_FIGURE,
    LABEL_CLASS_TABLE,
    GroundingResult,
    MissingFigure,
    PromisedReference,
    collect_known_labels,
    scan,
    scan_version_dir,
)


# ---------------------------------------------------------------------------
# Module surface guards
# ---------------------------------------------------------------------------


def test_critic_id_matches_sibling_tag():
    """The critic-id constant matches the sibling-dir tag convention."""
    assert CRITIC_ID == "claim-figure-grounding"
    assert GROUNDING_SUFFIX == CRITIC_ID


def test_critical_flag_type_matches_issue_body():
    """The critical-flag type matches the issue body's suggested name."""
    assert CRITICAL_FLAG_TYPE == "critical_promised_figure_missing"


def test_label_class_vocabulary_canonical_forms():
    """The canonical label classes are Figure / Table / Chart."""
    assert LABEL_CLASS_FIGURE == "Figure"
    assert LABEL_CLASS_TABLE == "Table"
    assert LABEL_CLASS_CHART == "Chart"


def test_grounding_result_total_findings_counts_missing():
    """``total_findings`` is the count of deduplicated missing-label entries."""
    result = GroundingResult(
        missing_figures=[
            MissingFigure(
                label_class="Figure",
                label_id="3",
                first_line=1,
                first_text="see Figure 3",
                additional_references=0,
                closest_match=None,
                suggested_fix="",
            )
        ]
    )
    assert result.total_findings == 1


def test_grounding_result_emits_tool_evidence_review():
    """``to_review`` yields a ``kind=tool_evidence`` review that validates."""
    result = GroundingResult(
        missing_figures=[
            MissingFigure(
                label_class="Figure",
                label_id="3",
                first_line=1,
                first_text="see Figure 3",
                additional_references=0,
                closest_match=None,
                suggested_fix="add or remove",
            )
        ],
        body_path="report.md",
    )
    review = result.to_review(version_dir="report.1")
    assert isinstance(review, Review)
    assert review.kind == Kind.TOOL_EVIDENCE
    assert review.critic_id == CRITIC_ID
    assert len(review.scores) == 1
    # The single null-scored row owns no rubric dim.
    assert review.scores[0].score is None
    assert review.scores[0].dimension == DIM_CLAIM_FIGURE_GROUNDING
    # Every finding must carry tool_calls=[] when kind=tool_evidence.
    for finding in review.findings:
        assert finding.tool_calls == []


# ---------------------------------------------------------------------------
# Positive prose-detection cases — references the detector MUST flag (when
# unground)
# ---------------------------------------------------------------------------


def test_positive_prepositional_see_figure_integer():
    """``see Figure 3`` is detected as a prepositional reference."""
    body = "The model converges quickly; see Figure 3 for the curve.\n"
    result = scan(body, known_labels=set())
    assert len(result.missing_figures) == 1
    assert result.missing_figures[0].label_class == "Figure"
    assert result.missing_figures[0].label_id == "3"


def test_positive_prepositional_as_shown_in_chart_letter():
    """``as shown in Chart B`` is detected (single uppercase letter id)."""
    body = "Latency drops as shown in Chart B at the 99th percentile.\n"
    result = scan(body, known_labels=set())
    assert any(
        m.label_class == "Chart" and m.label_id == "B"
        for m in result.missing_figures
    )


def test_positive_prepositional_per_table_integer():
    """``per Table 2`` is detected (prepositional, integer id)."""
    body = "Revenue grew 12% per Table 2 in the appendix.\n"
    result = scan(body, known_labels=set())
    assert any(
        m.label_class == "Table" and m.label_id == "2"
        for m in result.missing_figures
    )


def test_positive_prepositional_in_figure_dotted():
    """``in Figure 3.1`` is detected (dotted id)."""
    body = "The architecture in Figure 3.1 shows the new layer.\n"
    result = scan(body, known_labels=set())
    assert any(
        m.label_class == "Figure" and m.label_id == "3.1"
        for m in result.missing_figures
    )


def test_positive_subject_verb_figure_illustrates():
    """``Figure 3 illustrates`` is detected (subject-verb shape)."""
    body = "Figure 3 illustrates the latency distribution.\n"
    result = scan(body, known_labels=set())
    assert any(
        m.label_class == "Figure" and m.label_id == "3"
        for m in result.missing_figures
    )


def test_positive_subject_verb_table_reports():
    """``Table N reports`` is detected per the issue body's example."""
    body = "Table 2 reports the breakdown by segment.\n"
    result = scan(body, known_labels=set())
    assert any(
        m.label_class == "Table" and m.label_id == "2"
        for m in result.missing_figures
    )


def test_positive_subject_verb_chart_shows():
    """``Chart N shows`` is detected per the issue body's example."""
    body = "Chart 1 shows the trend across the cohort.\n"
    result = scan(body, known_labels=set())
    assert any(
        m.label_class == "Chart" and m.label_id == "1"
        for m in result.missing_figures
    )


def test_positive_parenthetical_figure():
    """``(Figure 3)`` is detected (parenthetical shape)."""
    body = "The signal is strong (Figure 3) across all segments.\n"
    result = scan(body, known_labels=set())
    assert any(
        m.label_class == "Figure" and m.label_id == "3"
        for m in result.missing_figures
    )


def test_positive_parenthetical_table():
    """``(Table N)`` per the issue body's ``Figure N (`` / ``Table N (`` shape."""
    body = "The breakdown is clear (Table 2) for the major segments.\n"
    result = scan(body, known_labels=set())
    assert any(
        m.label_class == "Table" and m.label_id == "2"
        for m in result.missing_figures
    )


def test_positive_fig_abbreviation_with_period():
    """``Fig. 3`` is normalized to ``Figure 3``."""
    body = "see Fig. 3 for the result.\n"
    result = scan(body, known_labels=set())
    assert any(
        m.label_class == "Figure" and m.label_id == "3"
        for m in result.missing_figures
    )


# ---------------------------------------------------------------------------
# Grounded references — references that DO have known labels and MUST NOT fire
# ---------------------------------------------------------------------------


def test_grounded_via_known_label_does_not_fire():
    """A prose reference with a matching known label produces no finding."""
    body = "see Figure 3 for the curve.\n"
    result = scan(body, known_labels={("Figure", "3")})
    assert not result.missing_figures


def test_grounded_via_latex_label_macro_in_body(tmp_path: Path):
    """A ``\\label{fig:3}`` in the body markdown grounds ``Figure 3``."""
    version_dir = _make_version_dir(
        tmp_path,
        body="see Figure 3 for the curve.\n"
        "\\begin{figure}\\label{fig:3}\\end{figure}\n",
    )
    result = scan_version_dir(version_dir)
    assert not result.missing_figures


def test_grounded_via_markdown_anchor_in_body(tmp_path: Path):
    """A ``{#fig:3}`` anchor in the body markdown grounds ``Figure 3``."""
    version_dir = _make_version_dir(
        tmp_path,
        body=(
            "see Figure 3 for the curve.\n\n"
            "## Adoption curve {#fig:3}\n\n"
            "Body text.\n"
        ),
    )
    result = scan_version_dir(version_dir)
    assert not result.missing_figures


def test_grounded_via_figures_dir_filename(tmp_path: Path):
    """``figure-3.png`` in ``figures/`` grounds the prose ``Figure 3`` reference."""
    version_dir = _make_version_dir(
        tmp_path, body="see Figure 3 for the curve.\n"
    )
    figures = version_dir / "figures"
    figures.mkdir()
    (figures / "figure-3.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    result = scan_version_dir(version_dir)
    assert not result.missing_figures


def test_grounded_via_exhibits_dir_filename(tmp_path: Path):
    """``fig-3.svg`` in ``exhibits/`` grounds the prose ``Figure 3`` reference.

    The report skill's `report-figures.md` documents `exhibits/` as the
    canonical figure subdir name; this test pins the dual-scan
    discipline (`figures/` + `exhibits/` are both walked).
    """
    version_dir = _make_version_dir(
        tmp_path, body="see Figure 3 for the curve.\n"
    )
    exhibits = version_dir / "exhibits"
    exhibits.mkdir()
    (exhibits / "fig-3.svg").write_text("<svg/>", encoding="utf-8")
    result = scan_version_dir(version_dir)
    assert not result.missing_figures


def test_grounded_via_dotted_id_in_filename(tmp_path: Path):
    """``figure-3-1.png`` grounds the prose ``Figure 3.1`` reference (dash → dot)."""
    version_dir = _make_version_dir(
        tmp_path, body="see Figure 3.1 for the architecture.\n"
    )
    figures = version_dir / "figures"
    figures.mkdir()
    (figures / "figure-3-1.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    result = scan_version_dir(version_dir)
    assert not result.missing_figures


def test_grounded_via_chart_filename(tmp_path: Path):
    """``chart-a.png`` grounds the prose ``Chart A`` reference."""
    version_dir = _make_version_dir(
        tmp_path, body="see Chart A for the trend.\n"
    )
    figures = version_dir / "figures"
    figures.mkdir()
    (figures / "chart-a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    result = scan_version_dir(version_dir)
    assert not result.missing_figures


def test_grounded_via_table_filename(tmp_path: Path):
    """``table-2.md`` grounds the prose ``Table 2`` reference."""
    version_dir = _make_version_dir(
        tmp_path, body="see Table 2 for the breakdown.\n"
    )
    figures = version_dir / "exhibits"
    figures.mkdir()
    (figures / "table-2.md").write_text("| a | b |\n", encoding="utf-8")
    result = scan_version_dir(version_dir)
    assert not result.missing_figures


# ---------------------------------------------------------------------------
# Closest-match suggestion
# ---------------------------------------------------------------------------


def test_closest_match_numeric_distance_one_suggests_nearest():
    """``Figure 4`` referenced; ``Figure 3`` in roster → suggests ``Figure 3``."""
    body = "see Figure 4 for the curve.\n"
    result = scan(body, known_labels={("Figure", "3")})
    assert len(result.missing_figures) == 1
    closest = result.missing_figures[0].closest_match
    assert closest == ("Figure", "3")
    assert "Figure 3" in result.missing_figures[0].suggested_fix


def test_closest_match_numeric_distance_two_still_suggests():
    """``Figure 5`` referenced; ``Figure 3`` in roster → suggests ``Figure 3`` (dist 2)."""
    body = "see Figure 5 for the curve.\n"
    result = scan(body, known_labels={("Figure", "3")})
    assert result.missing_figures[0].closest_match == ("Figure", "3")


def test_closest_match_numeric_distance_three_no_suggestion():
    """``Figure 10`` referenced; ``Figure 1`` in roster → NO suggestion (dist 9 > 2)."""
    body = "see Figure 10 for the curve.\n"
    result = scan(body, known_labels={("Figure", "1")})
    assert result.missing_figures[0].closest_match is None


def test_closest_match_class_restricted():
    """A ``Figure 3`` reference does NOT suggest a known ``Table 3``.

    The class mismatch is the actual defect; suggesting a wrong-class
    label is more confusing than helpful. Closest-match candidates are
    restricted to the same label class.
    """
    body = "see Figure 3 for the breakdown.\n"
    result = scan(body, known_labels={("Table", "3")})
    assert result.missing_figures[0].closest_match is None


def test_closest_match_dotted_id():
    """``Figure 3.2`` referenced; ``Figure 3.1`` in roster → suggests it via difflib."""
    body = "see Figure 3.2 for the architecture.\n"
    result = scan(body, known_labels={("Figure", "3.1")})
    closest = result.missing_figures[0].closest_match
    assert closest == ("Figure", "3.1")


# ---------------------------------------------------------------------------
# Dedupe contract — one finding per missing (label_class, label_id)
# ---------------------------------------------------------------------------


def test_dedupe_two_references_one_finding():
    """Two references to the same missing label produce one finding."""
    body = (
        "Recall the trend; see Figure 3 above.\n"
        "We expanded on this; see Figure 3 again in the appendix.\n"
    )
    result = scan(body, known_labels=set())
    assert len(result.missing_figures) == 1
    assert result.missing_figures[0].additional_references == 1


def test_dedupe_distinct_labels_separate_findings():
    """Two references to different missing labels produce two findings."""
    body = (
        "see Figure 3 above.\n"
        "Also see Table 2 in the appendix.\n"
    )
    result = scan(body, known_labels=set())
    assert len(result.missing_figures) == 2


def test_dedupe_first_reference_anchors_evidence_span():
    """The first reference's line + text anchor the deduplicated finding."""
    body = "intro\nintro\nfirst: see Figure 3 above.\nsecond: see Figure 3 again.\n"
    result = scan(body, known_labels=set())
    assert len(result.missing_figures) == 1
    assert result.missing_figures[0].first_line == 3
    assert "Figure 3" in result.missing_figures[0].first_text


# ---------------------------------------------------------------------------
# False-positive discipline
# ---------------------------------------------------------------------------


def test_false_positive_blockquoted_reference_does_not_fire():
    """A blockquoted ``see Figure 3`` does not fire (quoted material)."""
    body = "> see Figure 3 for the curve (quoted from a prior report).\n"
    result = scan(body, known_labels=set())
    assert not result.missing_figures


def test_false_positive_fenced_code_reference_does_not_fire():
    """A reference inside fenced code does not fire."""
    body = (
        "Example code:\n"
        "```\n"
        "# see Figure 3 below\n"
        "x = 1\n"
        "```\n"
    )
    result = scan(body, known_labels=set())
    assert not result.missing_figures


def test_false_positive_inline_backtick_reference_does_not_fire():
    """A reference inside inline backticks does not fire."""
    body = "The literal `see Figure 3` is documentation, not a claim.\n"
    result = scan(body, known_labels=set())
    assert not result.missing_figures


def test_false_positive_same_line_dupes_collapse():
    """Same-(class, id) on one line dedupes inside detection."""
    body = "see Figure 3, and also Figure 3 below.\n"
    result = scan(body, known_labels=set())
    # One missing finding because the dedupe also collapses cross-line.
    assert len(result.missing_figures) == 1
    # The references list also dedupes same-line same-(class, id).
    same_line_3 = [
        r for r in result.references
        if r.label_class == "Figure" and r.label_id == "3" and r.line == 1
    ]
    assert len(same_line_3) == 1


# ---------------------------------------------------------------------------
# Label roster discovery — collect_known_labels
# ---------------------------------------------------------------------------


def _make_version_dir(
    project_root: Path, body: str, version: int = 1
) -> Path:
    """Create a report thread + version dir + body markdown.

    Mirrors the report-skill shape: ``<project>/<thread>.{N}/report.md``.
    Returns the version directory path.
    """
    thread = project_root / "thread"
    version_dir = thread / f"thread.{version}"
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "report.md").write_text(body, encoding="utf-8")
    return version_dir


def test_collect_known_labels_from_latex_label_macros(tmp_path: Path):
    """``\\label{fig:adoption}`` in body markdown adds to the roster."""
    version_dir = _make_version_dir(
        tmp_path,
        body=(
            "## Adoption curve\n\n"
            "\\begin{figure}\n"
            "\\includegraphics{fig.png}\n"
            "\\label{fig:adoption}\n"
            "\\end{figure}\n"
        ),
    )
    roster = collect_known_labels(version_dir)
    assert ("Figure", "ADOPTION") in roster


def test_collect_known_labels_from_markdown_anchors(tmp_path: Path):
    """``{#fig:adoption}`` in body markdown adds to the roster."""
    version_dir = _make_version_dir(
        tmp_path,
        body=(
            "## Adoption curve {#fig:adoption}\n\n"
            "Body text.\n"
        ),
    )
    roster = collect_known_labels(version_dir)
    assert ("Figure", "ADOPTION") in roster


def test_collect_known_labels_from_figures_dir_filenames(tmp_path: Path):
    """``figure-3.png`` in ``figures/`` adds ``(Figure, 3)`` to the roster."""
    version_dir = _make_version_dir(tmp_path, body="body\n")
    figures = version_dir / "figures"
    figures.mkdir()
    (figures / "figure-3.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (figures / "figure-4.svg").write_text("<svg/>", encoding="utf-8")
    roster = collect_known_labels(version_dir)
    assert ("Figure", "3") in roster
    assert ("Figure", "4") in roster


def test_collect_known_labels_from_exhibits_dir_filenames(tmp_path: Path):
    """``table-2.md`` in ``exhibits/`` adds ``(Table, 2)`` to the roster."""
    version_dir = _make_version_dir(tmp_path, body="body\n")
    exhibits = version_dir / "exhibits"
    exhibits.mkdir()
    (exhibits / "table-2.md").write_text("| a |\n", encoding="utf-8")
    (exhibits / "chart-a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    roster = collect_known_labels(version_dir)
    assert ("Table", "2") in roster
    assert ("Chart", "A") in roster


def test_collect_known_labels_dotted_filename_normalized(tmp_path: Path):
    """``figure-3-1.png`` normalizes to ``(Figure, 3.1)`` (dash → dot)."""
    version_dir = _make_version_dir(tmp_path, body="body\n")
    figures = version_dir / "figures"
    figures.mkdir()
    (figures / "figure-3-1.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    roster = collect_known_labels(version_dir)
    assert ("Figure", "3.1") in roster


def test_collect_known_labels_ignores_unrelated_latex_prefixes(tmp_path: Path):
    """``\\label{sec:intro}`` does NOT add to the figure/table/chart roster."""
    version_dir = _make_version_dir(
        tmp_path,
        body="## Introduction\n\n\\label{sec:intro}\n",
    )
    roster = collect_known_labels(version_dir)
    # No (Section, INTRO) entry; the prefix vocabulary covers fig/tab/chart only.
    assert not any(lid == "INTRO" for (_cls, lid) in roster)


def test_collect_known_labels_ignores_non_label_files(tmp_path: Path):
    """A ``README.md`` in ``figures/`` does NOT pollute the roster."""
    version_dir = _make_version_dir(tmp_path, body="body\n")
    figures = version_dir / "figures"
    figures.mkdir()
    (figures / "README.md").write_text("Notes on figures.\n", encoding="utf-8")
    roster = collect_known_labels(version_dir)
    assert not roster


# ---------------------------------------------------------------------------
# Critical-flag heuristic
# ---------------------------------------------------------------------------


def test_critical_flag_fires_on_any_missing_label():
    """A single missing reference triggers the critical flag."""
    body = "see Figure 3 for the breakdown.\n"
    result = scan(body, known_labels=set())
    assert result.should_emit_critical_flag()
    review = result.to_review(version_dir="report.1")
    assert any(cf.type == CRITICAL_FLAG_TYPE for cf in review.critical_flags)


def test_critical_flag_does_not_fire_on_clean_scan():
    """A body with no references emits no critical flag."""
    body = "This is plain prose with no figure references.\n"
    result = scan(body, known_labels=set())
    assert not result.should_emit_critical_flag()
    review = result.to_review(version_dir="report.1")
    assert not review.critical_flags


def test_critical_flag_justification_lists_first_three_missing():
    """The critical-flag justification names the first three missing labels."""
    body = (
        "see Figure 3 above.\n"
        "see Table 2 below.\n"
        "see Chart A for the trend.\n"
        "see Figure 5 also.\n"
    )
    result = scan(body, known_labels=set())
    review = result.to_review(version_dir="report.1")
    assert len(review.critical_flags) == 1
    justification = review.critical_flags[0].justification
    assert "Figure 3" in justification
    assert "Table 2" in justification
    assert "Chart A" in justification
    assert "+1 more" in justification


# ---------------------------------------------------------------------------
# Filesystem integration — scan_version_dir
# ---------------------------------------------------------------------------


def test_scan_version_dir_returns_findings(tmp_path: Path):
    """``scan_version_dir`` runs the full pipeline from disk."""
    body = (
        "see Figure 3 above.\n"
        "see Table 2 in the appendix.\n"
    )
    version_dir = _make_version_dir(tmp_path, body=body)
    # Only Figure 3 is grounded; Table 2 should fire.
    figures = version_dir / "figures"
    figures.mkdir()
    (figures / "figure-3.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    result = scan_version_dir(version_dir)
    assert result.body_path == "report.md"
    assert len(result.missing_figures) == 1
    assert result.missing_figures[0].label_class == "Table"
    assert result.missing_figures[0].label_id == "2"


def test_scan_version_dir_missing_body_returns_empty(tmp_path: Path):
    """A missing body markdown returns an empty result (graceful-degrade)."""
    thread = tmp_path / "thread"
    version_dir = thread / "thread.1"
    version_dir.mkdir(parents=True)
    # No report.md present.
    result = scan_version_dir(version_dir)
    assert result.body_path is None
    assert not result.missing_figures


def test_scan_version_dir_custom_body_filename(tmp_path: Path):
    """``body_filename`` override lets non-standard body names work."""
    thread = tmp_path / "thread"
    version_dir = thread / "thread.1"
    version_dir.mkdir(parents=True)
    (version_dir / "custom.md").write_text(
        "see Figure 3 for context.\n", encoding="utf-8"
    )
    result = scan_version_dir(version_dir, body_filename="custom.md")
    assert result.body_path == "custom.md"
    assert len(result.missing_figures) == 1


# ---------------------------------------------------------------------------
# Auto-discovery contract — the ``.claim-figure-grounding/`` sibling is
# recognized by ``anvil/lib/critics.py::aggregate`` without code changes.
# ---------------------------------------------------------------------------


def test_aggregate_picks_up_claim_figure_grounding_sibling(tmp_path: Path):
    """Acceptance-criteria validation: aggregator auto-discovers our sibling.

    Write a ``GroundingResult.to_review()`` into
    ``<version_dir>.claim-figure-grounding/_review.json``, then call
    ``discover_critics`` + ``aggregate`` and confirm the verdict
    aggregator merges the findings + critical flag.
    """
    version_dir = _make_version_dir(
        tmp_path, body="see Figure 3 above.\n"
    )

    # Synthesize a GroundingResult with one missing label.
    result = GroundingResult(
        missing_figures=[
            MissingFigure(
                label_class="Figure",
                label_id="3",
                first_line=1,
                first_text="see Figure 3",
                additional_references=0,
                closest_match=None,
                suggested_fix="add Figure 3 or remove the reference",
            )
        ],
        body_path="report.md",
    )
    review = result.to_review(version_dir=version_dir.name)
    sibling = version_dir.parent / f"{version_dir.name}.{GROUNDING_SUFFIX}"
    sibling.mkdir()
    (sibling / "_review.json").write_text(
        review.model_dump_json(indent=2), encoding="utf-8"
    )

    # Auto-discovery should pick up the sibling.
    discovered = discover_critics(version_dir)
    assert sibling in discovered

    # Loading the review should succeed and round-trip the findings.
    loaded = load_review(sibling)
    assert loaded.kind == Kind.TOOL_EVIDENCE
    assert loaded.critic_id == CRITIC_ID
    assert len(loaded.findings) == 1
    assert loaded.findings[0].severity == "major"
    # The critical-flag short-circuits the aggregator's verdict.
    assert any(
        cf.type == CRITICAL_FLAG_TYPE for cf in loaded.critical_flags
    )

    # Aggregation merges findings without raising.
    agg = aggregate([loaded])
    assert len(agg.findings) == 1
    assert len(agg.critical_flags) == 1
    # The aggregated verdict short-circuits to BLOCK on the critical flag.
    from anvil.lib.review_schema import Verdict

    assert agg.verdict == Verdict.BLOCK


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def test_cli_main_with_write_review_writes_sibling(tmp_path: Path):
    """``--write-review`` opts in to writing the sibling critic dir.

    Mirrors the Phase 2 / 3 CLI contracts (PRs #338 / #337): writes are
    opt-in via ``--write-review``; exit code is non-zero when findings
    exist so CI pipelines can branch on it.
    """
    from anvil.skills.report.lib.claim_figure_grounding import _cli_main

    version_dir = _make_version_dir(
        tmp_path, body="see Figure 3 for the curve.\n"
    )

    rc = _cli_main([str(version_dir), "--write-review"])
    # Missing figure → exit non-zero.
    assert rc == 1

    sibling = version_dir.parent / f"{version_dir.name}.{GROUNDING_SUFFIX}"
    review_path = sibling / "_review.json"
    findings_path = sibling / "_findings.json"
    assert review_path.is_file()
    assert findings_path.is_file()

    # _review.json validates against the typed schema.
    review = Review.model_validate_json(review_path.read_text())
    assert review.kind == Kind.TOOL_EVIDENCE
    assert review.critic_id == CRITIC_ID
    assert any(
        cf.type == CRITICAL_FLAG_TYPE for cf in review.critical_flags
    )

    # _findings.json is well-formed JSON with the documented shape.
    findings_data = json.loads(findings_path.read_text())
    assert findings_data["critic"] == CRITIC_ID
    assert findings_data["total_findings"] == 1


def test_cli_main_without_write_review_does_not_write_sibling(tmp_path: Path):
    """Without ``--write-review`` the sibling critic dir is NOT created."""
    from anvil.skills.report.lib.claim_figure_grounding import _cli_main

    version_dir = _make_version_dir(
        tmp_path, body="see Figure 3 for the curve.\n"
    )

    rc = _cli_main([str(version_dir)])
    # Findings present → exit non-zero.
    assert rc == 1

    sibling = version_dir.parent / f"{version_dir.name}.{GROUNDING_SUFFIX}"
    assert not sibling.exists()


def test_cli_main_clean_scan_exits_zero(tmp_path: Path):
    """A clean scan (no missing labels) exits 0."""
    from anvil.skills.report.lib.claim_figure_grounding import _cli_main

    body = "This is plain prose with no figure references.\n"
    version_dir = _make_version_dir(tmp_path, body=body)

    rc = _cli_main([str(version_dir)])
    assert rc == 0


def test_cli_main_missing_version_dir_exits_two(tmp_path: Path):
    """A non-existent ``version_dir`` exits 2 (invocation error)."""
    from anvil.skills.report.lib.claim_figure_grounding import _cli_main

    rc = _cli_main([str(tmp_path / "does-not-exist")])
    assert rc == 2


def test_cli_main_grounded_body_exits_zero(tmp_path: Path):
    """A body whose every reference is grounded exits 0."""
    from anvil.skills.report.lib.claim_figure_grounding import _cli_main

    version_dir = _make_version_dir(
        tmp_path, body="see Figure 3 for the curve.\n"
    )
    figures = version_dir / "figures"
    figures.mkdir()
    (figures / "figure-3.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    rc = _cli_main([str(version_dir)])
    assert rc == 0


# ---------------------------------------------------------------------------
# Doc-coverage: report-claim-figure-grounding command file references the
# lib correctly.
# ---------------------------------------------------------------------------


_COMMANDS_DIR = (
    Path(__file__).resolve().parents[3]
    / "anvil"
    / "skills"
    / "report"
    / "commands"
)


def test_command_doc_exists():
    """``anvil/skills/report/commands/report-claim-figure-grounding.md`` ships."""
    doc = _COMMANDS_DIR / "report-claim-figure-grounding.md"
    assert doc.is_file()


def test_command_doc_references_lib_module():
    """The command doc points at the lib module path."""
    doc = (
        _COMMANDS_DIR / "report-claim-figure-grounding.md"
    ).read_text(encoding="utf-8")
    assert "anvil.skills.report.lib.claim_figure_grounding" in doc


def test_command_doc_documents_critical_flag():
    """The command doc names the critical-flag type so operators can grep."""
    doc = (
        _COMMANDS_DIR / "report-claim-figure-grounding.md"
    ).read_text(encoding="utf-8")
    assert "critical_promised_figure_missing" in doc


def test_command_doc_documents_sibling_dir_convention():
    """The command doc names the ``.claim-figure-grounding/`` sibling-dir tag."""
    doc = (
        _COMMANDS_DIR / "report-claim-figure-grounding.md"
    ).read_text(encoding="utf-8")
    assert ".claim-figure-grounding/" in doc


def test_command_doc_documents_three_ground_truth_sources():
    """The command doc enumerates the LaTeX / markdown / filename sources."""
    doc = (
        _COMMANDS_DIR / "report-claim-figure-grounding.md"
    ).read_text(encoding="utf-8")
    assert "\\label{" in doc
    assert "{#" in doc
    assert "figures/" in doc and "exhibits/" in doc
