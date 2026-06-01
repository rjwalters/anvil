"""Doc-coverage smoke tests for the memo refs-back-check contract (issue #144).

Per issue #144 acceptance criteria: cheap "grep-the-doc" regression guard
that the source-of-truth ``refs/`` contract stays documented in the four
files it touches (SKILL.md, memo-draft.md, memo-review.md, rubric.md) and
that the existing PR #140 citation-stubs semantic is preserved (i.e., the
new source-of-truth role is **additive**, not replacing).

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The lifecycle commands themselves are
LLM-driven, so behavioural assertions belong in consumer-side integration
tests, not here.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with a similarly-shaped
``test_refs_back_check_doc`` another skill might pick.

Specific guards this file owns (per the curator notes on #144):

  1. The ``CONTRADICTED`` verdict tag — the load-bearing detection
     requirement that the contract exists to catch (the canary failure
     mode: a factual founder-bio error propagating through five memo
     versions because no reviewer back-checked against the CV).
  2. Backward-compat with empty / citation-stub-only ``refs/``. The
     §"Citation stubs" subsection from PR #140 MUST remain intact and the
     refs back-check MUST document explicit fallback behaviour when no
     source-of-truth materials are present.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
RUBRIC_MD = SKILL_ROOT / "rubric.md"
DRAFT_MD = SKILL_ROOT / "commands" / "memo-draft.md"
REVIEW_MD = SKILL_ROOT / "commands" / "memo-review.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SKILL.md — §"Source-of-truth materials" subsection exists alongside
# §"Citation stubs" (additive, not replacing)
# ---------------------------------------------------------------------------


def test_skill_md_has_source_of_truth_subsection():
    body = _read(SKILL_MD)
    assert "Source-of-truth materials" in body, (
        "SKILL.md MUST contain a 'Source-of-truth materials' subsection "
        "(issue #144 acceptance criterion)"
    )


def test_skill_md_preserves_citation_stubs_subsection():
    """PR #140 regression guard — the existing Citation stubs subsection
    MUST remain intact after the additive source-of-truth subsection
    is added."""
    body = _read(SKILL_MD)
    assert "### Citation stubs" in body, (
        "SKILL.md MUST preserve the '### Citation stubs' subsection from "
        "PR #140; the source-of-truth role is additive, not replacing"
    )
    # The minimal stub form must still be documented verbatim.
    assert "TODO: source for" in body, (
        "SKILL.md MUST preserve the minimal '# TODO: source for <claim>' "
        "stub form from PR #140"
    )


def test_skill_md_documents_coexistence_in_same_directory():
    body = _read(SKILL_MD).lower()
    # The two roles share the refs/ directory; the disambiguation is
    # filename + extension. This MUST be stated explicitly.
    assert "coexist" in body or "both file" in body or "same directory" in body, (
        "SKILL.md MUST document that source-of-truth materials and citation "
        "stubs coexist in the same <thread>/refs/ directory"
    )
    assert "filename" in body, (
        "SKILL.md MUST document that source-of-truth vs citation-stub "
        "disambiguation is by filename + extension"
    )


def test_skill_md_names_canonical_source_of_truth_shapes():
    body = _read(SKILL_MD).lower()
    # The contract is grounded in the canonical filename conventions.
    assert "cv." in body, (
        "SKILL.md MUST name CV as a canonical source-of-truth shape"
    )
    assert "transcript-" in body, (
        "SKILL.md MUST name transcripts as a canonical source-of-truth shape"
    )
    assert "filing-" in body, (
        "SKILL.md MUST name public filings as a canonical source-of-truth shape"
    )


def test_skill_md_documents_text_vs_presence_only_split():
    """v0 reads text-readable files (md, txt, json) into context; PDFs and
    images are presence-only signals. The split MUST be explicit."""
    body = _read(SKILL_MD).lower()
    assert "presence-only" in body or "presence only" in body, (
        "SKILL.md MUST document the presence-only treatment of PDFs/images "
        "in v0 (text extraction is out of scope)"
    )


def test_skill_md_cross_references_three_consumers():
    """The SKILL.md prose MUST point at memo-draft, memo-review, and
    rubric.md so the contract surfaces are discoverable in any direction."""
    body = _read(SKILL_MD)
    # Locate the source-of-truth subsection and inspect its cross-references.
    idx = body.find("Source-of-truth materials")
    assert idx >= 0, "Source-of-truth subsection missing"
    sub = body[idx:]
    assert "memo-draft" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST cross-reference memo-draft.md"
    )
    assert "memo-review" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST cross-reference memo-review.md"
    )
    assert "rubric.md" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST cross-reference rubric.md"
    )


# ---------------------------------------------------------------------------
# memo-draft.md — step 3 documents source-of-truth ingestion
# ---------------------------------------------------------------------------


def test_memo_draft_step_3_references_source_of_truth():
    body = _read(DRAFT_MD).lower()
    assert "source-of-truth" in body, (
        "memo-draft.md MUST reference 'source-of-truth' in step 3 "
        "(issue #144 drafter contract)"
    )


def test_memo_draft_names_text_readable_ingestion():
    body = _read(DRAFT_MD).lower()
    # The drafter reads md / txt / json into context; PDFs/images are
    # presence-only.
    assert ".md" in body and (".txt" in body or "text" in body) and ".json" in body, (
        "memo-draft.md MUST name the text-readable file shapes ingested "
        "into drafter context (.md, .txt, .json)"
    )


def test_memo_draft_documents_refs_wins_conflict_rule():
    """If a claim conflicts with a refs/ source-of-truth document, the
    refs/ document wins. This is the load-bearing drafter discipline."""
    body = _read(DRAFT_MD).lower()
    # The phrase "refs/ document wins" may appear with backticks around
    # `refs/`, so strip backticks before searching.
    haystack = body.replace("`", "")
    assert "refs/ document wins" in haystack or "refs document wins" in haystack, (
        "memo-draft.md MUST document the 'refs/ document wins' rule for "
        "conflicts between claims and source-of-truth materials"
    )


def test_memo_draft_documents_refs_inline_citation_hook():
    """The [refs/<file>] inline pointer is honored as if it were a
    footnote. The drafter MUST know this so it knows how to cite."""
    body = _read(DRAFT_MD)
    assert "[refs/" in body, (
        "memo-draft.md MUST document the [refs/<file>] inline citation hook"
    )


# ---------------------------------------------------------------------------
# memo-review.md — step 5 documents refs back-check sub-step
# ---------------------------------------------------------------------------


def test_memo_review_step_5_has_refs_back_check_substep():
    body = _read(REVIEW_MD).lower()
    assert "refs back-check" in body or "refs back check" in body, (
        "memo-review.md MUST document the dim 3 refs back-check sub-step "
        "(issue #144 reviewer contract)"
    )


def test_memo_review_names_all_four_verdict_tags():
    """The four verdict tags VERIFIED / UNVERIFIED / CONTRADICTED /
    NOT-IN-REFS MUST all be documented so the reviewer knows the schema."""
    body = _read(REVIEW_MD)
    assert "VERIFIED" in body, "memo-review.md MUST document VERIFIED verdict tag"
    assert "UNVERIFIED" in body, "memo-review.md MUST document UNVERIFIED verdict tag"
    assert "CONTRADICTED" in body, (
        "memo-review.md MUST document CONTRADICTED verdict tag — the "
        "load-bearing detection requirement of issue #144"
    )
    assert "NOT-IN-REFS" in body, (
        "memo-review.md MUST document NOT-IN-REFS verdict tag"
    )


def test_memo_review_one_per_type_back_check_floor():
    """The reviewer is required to back-check AT LEAST ONE claim per
    refs-document type present — not every claim, not zero. The floor
    MUST be documented so the reviewer knows the obligation."""
    body = _read(REVIEW_MD).lower()
    assert "at least one claim" in body, (
        "memo-review.md MUST document the 'at least one claim per refs-document "
        "type' back-check floor"
    )


def test_memo_review_documents_contradicted_critical_flag_candidate():
    """A CONTRADICTED claim against a source-of-truth ref is a
    critical-flag candidate — the canary detection requirement."""
    body = _read(REVIEW_MD)
    # The contract names CONTRADICTED claims as critical-flag candidates.
    assert "critical-flag candidate" in body or "critical flag candidate" in body, (
        "memo-review.md MUST document that CONTRADICTED back-check verdicts "
        "are critical-flag candidates (issue #144 canary detection)"
    )


def test_memo_review_documents_empty_refs_fallback():
    """When refs/ contains no source-of-truth materials, the back-check
    sub-step MUST be inactive — backward-compat with PR #140."""
    body = _read(REVIEW_MD).lower()
    assert "inactive" in body or "falls back" in body, (
        "memo-review.md MUST document the empty/citation-stub-only refs/ "
        "fallback behavior (backward-compat with PR #140)"
    )


# ---------------------------------------------------------------------------
# rubric.md — §"Refs back-check (dim 3)" subsection exists with deduction
# schedule
# ---------------------------------------------------------------------------


def test_rubric_has_refs_back_check_subsection():
    body = _read(RUBRIC_MD)
    assert "Refs back-check" in body, (
        "rubric.md MUST contain a 'Refs back-check' subsection "
        "(issue #144 acceptance criterion)"
    )


def test_rubric_refs_back_check_binds_to_dim_3():
    body = _read(RUBRIC_MD).lower()
    # The subsection heading MUST bind to dim 3 (NOT dim 2 — the original
    # issue body's dim numbering was wrong; the curator corrected it).
    idx = body.find("refs back-check")
    assert idx >= 0
    # The dim 3 binding should be in the section heading or adjacent prose.
    nearby = body[max(0, idx - 50):idx + 200]
    assert "dim 3" in nearby, (
        "rubric.md §'Refs back-check' MUST bind to dim 3 Evidence quality "
        "(not dim 2 — the original issue body had the wrong dim number)"
    )


def test_rubric_preserves_citation_hooks_subsection():
    """PR #140 regression guard — §"Citation hooks (dim 3)" MUST remain
    intact. The new §"Refs back-check (dim 3)" is a SIBLING, not a
    replacement."""
    body = _read(RUBRIC_MD)
    assert "## Citation hooks (dim 3)" in body, (
        "rubric.md MUST preserve the '## Citation hooks (dim 3)' subsection "
        "from PR #140; the refs back-check is a sibling, not a replacement"
    )


def test_rubric_documents_contradicted_two_point_deduction():
    body = _read(RUBRIC_MD).lower()
    # CONTRADICTED → 2-point deduction + critical-flag candidate.
    idx = body.find("refs back-check")
    assert idx >= 0
    sub = body[idx:]
    assert "two-point" in sub or "2-point" in sub or "two point" in sub, (
        "rubric.md §'Refs back-check' MUST document the two-point deduction "
        "for CONTRADICTED claims"
    )
    assert "contradicted" in sub, (
        "rubric.md §'Refs back-check' MUST document the CONTRADICTED verdict"
    )
    assert "critical-flag" in sub or "critical flag" in sub, (
        "rubric.md §'Refs back-check' MUST document the critical-flag "
        "candidacy of CONTRADICTED claims"
    )


def test_rubric_documents_unverified_one_point_deduction():
    body = _read(RUBRIC_MD).lower()
    idx = body.find("refs back-check")
    assert idx >= 0
    sub = body[idx:]
    assert "one-point" in sub or "1-point" in sub or "one point" in sub, (
        "rubric.md §'Refs back-check' MUST document the one-point deduction "
        "for UNVERIFIED claims"
    )
    assert "unverified" in sub, (
        "rubric.md §'Refs back-check' MUST document the UNVERIFIED verdict"
    )


def test_rubric_documents_not_in_refs_no_deduction():
    body = _read(RUBRIC_MD).lower()
    idx = body.find("refs back-check")
    assert idx >= 0
    sub = body[idx:]
    assert "not-in-refs" in sub, (
        "rubric.md §'Refs back-check' MUST document the NOT-IN-REFS verdict"
    )
    # NOT-IN-REFS is informational only; the no-deduction property MUST be
    # documented so the reviewer doesn't accidentally deduct.
    assert "no deduction" in sub or "informational" in sub, (
        "rubric.md §'Refs back-check' MUST document that NOT-IN-REFS is "
        "informational only (no deduction)"
    )


def test_rubric_documents_empty_refs_fallback():
    """Backward-compat — when refs/ has no source-of-truth materials, the
    sub-rule is inactive and dim 3 falls back to citation-hooks behavior
    alone."""
    body = _read(RUBRIC_MD).lower()
    idx = body.find("refs back-check")
    assert idx >= 0
    sub = body[idx:]
    assert "inactive" in sub or "falls back" in sub or "backward compat" in sub, (
        "rubric.md §'Refs back-check' MUST document the empty-refs fallback "
        "behavior (backward-compat with PR #140)"
    )


def test_rubric_preserves_length_targets_subsection():
    """Length targets (dim 7) was added in issue #121. The new
    §'Refs back-check (dim 3)' MUST NOT displace it."""
    body = _read(RUBRIC_MD)
    assert "Length targets" in body, (
        "rubric.md MUST preserve the 'Length targets (dim 7)' subsection"
    )


# ---------------------------------------------------------------------------
# Cross-doc coherence — the four docs reference each other correctly
# ---------------------------------------------------------------------------


def test_skill_md_source_of_truth_references_rubric_subsection_name():
    """SKILL.md should point at the rubric's §'Refs back-check (dim 3)'
    subsection by name so the reviewer-side deduction rule is
    discoverable."""
    body = _read(SKILL_MD)
    idx = body.find("Source-of-truth materials")
    assert idx >= 0
    sub = body[idx:]
    assert "Refs back-check" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST reference rubric.md's "
        "§'Refs back-check (dim 3)' subsection by name"
    )


def test_memo_draft_references_source_of_truth_subsection():
    """memo-draft.md step 3 should reference SKILL.md §'Source-of-truth
    materials' so the drafter knows where the on-disk contract lives."""
    body = _read(DRAFT_MD)
    assert "Source-of-truth materials" in body, (
        "memo-draft.md MUST reference SKILL.md §'Source-of-truth materials' "
        "so the drafter contract is anchored to the SKILL-level convention"
    )


def test_memo_review_references_skill_source_of_truth():
    """memo-review.md step 5 should point at SKILL.md §'Source-of-truth
    materials' for the canonical filename disambiguation rule."""
    body = _read(REVIEW_MD)
    assert "Source-of-truth materials" in body, (
        "memo-review.md MUST reference SKILL.md §'Source-of-truth materials' "
        "so the reviewer knows the source-of-truth vs citation-stub "
        "disambiguation rule"
    )
