"""Doc-coverage smoke tests for the deck refs-back-check contract (issue #166).

Per issue #166 acceptance criteria: cheap "grep-the-doc" regression guard
that the source-of-truth ``refs/`` contract stays documented in the four
files it touches (SKILL.md, deck-draft.md, deck-review.md, rubric.md) and
that the existing BRIEF cross-check / no-fabrication contract is
preserved (i.e., the new source-of-truth role is **additive**, not
replacing).

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The lifecycle commands themselves are
LLM-driven, so behavioural assertions belong in consumer-side integration
tests, not here.

Per-skill test filename convention (#58): this file is named with a
``test_deck_`` prefix so it never collides with a similarly-shaped
``test_refs_back_check_doc`` another skill might pick.

Specific guards this file owns (per the curator notes on #166):

  1. The ``CONTRADICTED`` verdict tag — the load-bearing detection
     requirement that the contract exists to catch (the canary failure
     mode: a factual founder-bio error propagating through TWO deck
     versions because no reviewer back-checked against the CV).
  2. The dim 5 / dim 6 binding — deck's evidentiary load is split across
     Traction (dim 5) and Team credibility (dim 6); the back-check
     MUST bind to BOTH, NOT to a single "Evidence quality" dim (which
     does not exist on the deck rubric).
  3. The existing critical flags 1 (Fabricated traction) and 2
     (Fabricated team credentials) MUST be named as the escalation
     path for CONTRADICTED claims — no new flag is created.
  4. Backward-compat with empty / generic-only ``refs/``. The deck's
     existing BRIEF-only cross-check MUST remain intact and the refs
     back-check MUST document explicit fallback behaviour when no
     source-of-truth materials are present.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"
SKILL_MD = SKILL_ROOT / "SKILL.md"
RUBRIC_MD = SKILL_ROOT / "rubric.md"
DRAFT_MD = SKILL_ROOT / "commands" / "deck-draft.md"
REVIEW_MD = SKILL_ROOT / "commands" / "deck-review.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SKILL.md — §"Source-of-truth materials" subsection exists alongside the
# existing refs/ / assets/ contract (additive, not replacing)
# ---------------------------------------------------------------------------


def test_skill_md_has_source_of_truth_subsection():
    body = _read(SKILL_MD)
    assert "Source-of-truth materials" in body, (
        "SKILL.md MUST contain a 'Source-of-truth materials' subsection "
        "(issue #166 acceptance criterion)"
    )


def test_skill_md_preserves_existing_refs_assets_contract():
    """Pre-#166 regression guard — the existing refs/ + assets/ contract
    in the artifact-contract block MUST remain intact. The
    source-of-truth role is additive, not replacing."""
    body = _read(SKILL_MD)
    # The artifact-contract block names refs/ and assets/.
    assert "refs/" in body, (
        "SKILL.md MUST preserve the existing 'refs/' contract prose"
    )
    assert "assets/" in body, (
        "SKILL.md MUST preserve the existing 'assets/' contract prose"
    )


def test_skill_md_preserves_brief_is_the_contract_rule():
    """The 'brief is the contract' rule MUST remain intact — refs/
    source-of-truth is back-check substrate, NOT slide-content
    authority."""
    body = _read(SKILL_MD)
    # The phrase appears in the source-of-truth subsection as a
    # precedence guard.
    assert "brief" in body.lower(), (
        "SKILL.md MUST preserve the brief-is-the-contract precedence rule"
    )
    idx = body.find("Source-of-truth materials")
    assert idx >= 0
    sub = body[idx:]
    # The source-of-truth subsection MUST acknowledge brief precedence.
    assert "Brief precedence" in sub or "brief precedence" in sub or "brief is the contract" in sub.lower(), (
        "SKILL.md §'Source-of-truth materials' MUST acknowledge the "
        "brief-is-the-contract precedence rule (refs/ is back-check "
        "substrate, not slide-content authority)"
    )


def test_skill_md_documents_coexistence_in_same_directory():
    body = _read(SKILL_MD).lower()
    # The two roles share the refs/ directory; the disambiguation is
    # filename + extension. This MUST be stated explicitly.
    assert "coexist" in body or "both file" in body or "same directory" in body, (
        "SKILL.md MUST document that source-of-truth materials and the "
        "existing reference-material role coexist in the same "
        "<thread>/refs/ directory"
    )
    assert "filename" in body, (
        "SKILL.md MUST document that source-of-truth vs generic-refs "
        "disambiguation is by filename + extension"
    )


def test_skill_md_names_canonical_source_of_truth_shapes():
    body = _read(SKILL_MD).lower()
    # The contract is grounded in the canonical filename conventions
    # specific to the deck use case.
    assert "cv." in body, (
        "SKILL.md MUST name CV as a canonical source-of-truth shape"
    )
    # Team-bearing materials.
    assert "founder-bio" in body or "founder bio" in body, (
        "SKILL.md MUST name founder-bio as a canonical source-of-truth shape"
    )
    # Traction-bearing materials.
    assert "loi-" in body or "loi" in body, (
        "SKILL.md MUST name LOI files as a canonical traction-bearing "
        "source-of-truth shape"
    )


def test_skill_md_documents_text_vs_presence_only_split():
    """v0 reads text-readable files (md, txt, json) into context; PDFs and
    images are presence-only signals. The split MUST be explicit."""
    body = _read(SKILL_MD).lower()
    assert "presence-only" in body or "presence only" in body, (
        "SKILL.md MUST document the presence-only treatment of PDFs/images "
        "in v0 (text extraction is out of scope per issue #167)"
    )


def test_skill_md_cross_references_three_consumers():
    """The SKILL.md prose MUST point at deck-draft, deck-review, and
    rubric.md so the contract surfaces are discoverable in any direction."""
    body = _read(SKILL_MD)
    idx = body.find("Source-of-truth materials")
    assert idx >= 0, "Source-of-truth subsection missing"
    sub = body[idx:]
    assert "deck-draft" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST cross-reference deck-draft.md"
    )
    assert "deck-review" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST cross-reference deck-review.md"
    )
    assert "rubric.md" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST cross-reference rubric.md"
    )


# ---------------------------------------------------------------------------
# deck-draft.md — step 5 documents source-of-truth ingestion
# ---------------------------------------------------------------------------


def test_deck_draft_step_5_references_source_of_truth():
    body = _read(DRAFT_MD).lower()
    assert "source-of-truth" in body, (
        "deck-draft.md MUST reference 'source-of-truth' in step 5 "
        "(issue #166 drafter contract)"
    )


def test_deck_draft_names_text_readable_ingestion():
    body = _read(DRAFT_MD).lower()
    # The drafter reads md / txt / json into context; PDFs/images are
    # presence-only.
    assert ".md" in body and (".txt" in body or "text" in body) and ".json" in body, (
        "deck-draft.md MUST name the text-readable file shapes ingested "
        "into drafter context (.md, .txt, .json)"
    )


def test_deck_draft_documents_refs_wins_conflict_rule():
    """If a claim conflicts with a refs/ source-of-truth document, the
    refs/ document wins. This is the load-bearing drafter discipline."""
    body = _read(DRAFT_MD).lower()
    # The phrase "refs/ document wins" may appear with backticks around
    # `refs/`, so strip backticks before searching.
    haystack = body.replace("`", "")
    assert "refs/ document wins" in haystack or "refs document wins" in haystack, (
        "deck-draft.md MUST document the 'refs/ document wins' rule for "
        "conflicts between claims and source-of-truth materials"
    )


def test_deck_draft_preserves_brief_is_the_contract():
    """The brief-is-the-contract rule MUST remain authoritative — refs/
    is back-check substrate, NOT slide-content authority."""
    body = _read(DRAFT_MD).lower()
    # The phrase "brief is the contract" appears in multiple places.
    assert "brief is the contract" in body or "brief-is-the-contract" in body, (
        "deck-draft.md MUST preserve the 'brief is the contract' rule "
        "(refs/ is back-check substrate, not slide-content authority)"
    )


def test_deck_draft_references_source_of_truth_subsection():
    """deck-draft.md step 5 should reference SKILL.md §'Source-of-truth
    materials' so the drafter knows where the on-disk contract lives."""
    body = _read(DRAFT_MD)
    assert "Source-of-truth materials" in body, (
        "deck-draft.md MUST reference SKILL.md §'Source-of-truth materials' "
        "so the drafter contract is anchored to the SKILL-level convention"
    )


# ---------------------------------------------------------------------------
# deck-review.md — step 6 documents refs back-check sub-step for dims 5+6
# ---------------------------------------------------------------------------


def test_deck_review_step_6_has_refs_back_check_substep():
    body = _read(REVIEW_MD).lower()
    assert "refs back-check" in body or "refs back check" in body, (
        "deck-review.md MUST document the dim 5 / dim 6 refs back-check "
        "sub-step (issue #166 reviewer contract)"
    )


def test_deck_review_binds_back_check_to_dim_5_and_dim_6():
    """The back-check MUST bind to BOTH dim 5 (Traction/proof) and dim 6
    (Team credibility), not just one. Deck's evidentiary load is split."""
    body = _read(REVIEW_MD).lower()
    idx = body.find("refs back-check")
    assert idx >= 0
    sub = body[idx:idx + 3000]
    assert "dim 5" in sub, (
        "deck-review.md §refs back-check MUST bind to dim 5 (Traction/proof)"
    )
    assert "dim 6" in sub, (
        "deck-review.md §refs back-check MUST bind to dim 6 (Team credibility)"
    )


def test_deck_review_names_all_four_verdict_tags():
    """The four verdict tags VERIFIED / UNVERIFIED / CONTRADICTED /
    NOT-IN-REFS MUST all be documented so the reviewer knows the schema."""
    body = _read(REVIEW_MD)
    assert "VERIFIED" in body, "deck-review.md MUST document VERIFIED verdict tag"
    assert "UNVERIFIED" in body, "deck-review.md MUST document UNVERIFIED verdict tag"
    assert "CONTRADICTED" in body, (
        "deck-review.md MUST document CONTRADICTED verdict tag — the "
        "load-bearing detection requirement of issue #166"
    )
    assert "NOT-IN-REFS" in body, (
        "deck-review.md MUST document NOT-IN-REFS verdict tag"
    )


def test_deck_review_one_per_type_back_check_floor():
    """The reviewer is required to back-check AT LEAST ONE claim per
    refs-document type present — not every claim, not zero."""
    body = _read(REVIEW_MD).lower()
    assert "at least one claim" in body, (
        "deck-review.md MUST document the 'at least one claim per "
        "refs-document type' back-check floor"
    )


def test_deck_review_documents_contradicted_critical_flag_candidate():
    """A CONTRADICTED claim against a source-of-truth ref is a
    critical-flag candidate — the canary detection requirement."""
    body = _read(REVIEW_MD)
    assert "critical-flag candidate" in body or "critical flag candidate" in body, (
        "deck-review.md MUST document that CONTRADICTED back-check verdicts "
        "are critical-flag candidates (issue #166 canary detection)"
    )


def test_deck_review_escalates_to_existing_flags_1_and_2():
    """The escalation path uses the EXISTING critical flags 1 (Fabricated
    traction) and 2 (Fabricated team credentials) — no new flag created."""
    body = _read(REVIEW_MD)
    # The deck has standing critical flags; CONTRADICTED traction → flag 1,
    # CONTRADICTED team → flag 2.
    assert "Fabricated traction" in body, (
        "deck-review.md MUST name 'Fabricated traction' as the escalation "
        "path for traction-bearing CONTRADICTED claims (existing flag 1)"
    )
    assert "Fabricated team credentials" in body, (
        "deck-review.md MUST name 'Fabricated team credentials' as the "
        "escalation path for team-bearing CONTRADICTED claims (existing flag 2)"
    )


def test_deck_review_documents_empty_refs_fallback():
    """When refs/ contains no source-of-truth materials, the back-check
    sub-step MUST be inactive — backward-compat with pre-#166 behavior."""
    body = _read(REVIEW_MD).lower()
    assert "inactive" in body or "falls back" in body or "fall back" in body, (
        "deck-review.md MUST document the empty/generic-only refs/ "
        "fallback behavior (backward-compat with BRIEF-only cross-check)"
    )


def test_deck_review_preserves_existing_brief_cross_check():
    """The existing dim 5 + dim 6 BRIEF cross-check MUST remain intact —
    the refs back-check is ADDITIVE to it, not replacing."""
    body = _read(REVIEW_MD)
    # The existing pattern: "Cross-check every number against BRIEF.md"
    # MUST stay.
    assert "Cross-check every number against `BRIEF.md`" in body or "cross-check every number against `brief.md`" in body.lower(), (
        "deck-review.md MUST preserve the existing dim 5 BRIEF "
        "cross-check (the refs back-check is additive, not replacing)"
    )
    assert "Cross-check every bio against `BRIEF.md`" in body or "cross-check every bio against `brief.md`" in body.lower(), (
        "deck-review.md MUST preserve the existing dim 6 BRIEF "
        "cross-check (the refs back-check is additive, not replacing)"
    )


# ---------------------------------------------------------------------------
# rubric.md — §"Refs back-check (dims 5, 6)" subsection exists with
# deduction schedule
# ---------------------------------------------------------------------------


def test_rubric_has_refs_back_check_subsection():
    body = _read(RUBRIC_MD)
    assert "Refs back-check" in body, (
        "rubric.md MUST contain a 'Refs back-check' subsection "
        "(issue #166 acceptance criterion)"
    )


def test_rubric_refs_back_check_binds_to_dims_5_and_6():
    """The rubric subsection MUST bind to dims 5 AND 6 (the deck's
    evidentiary load is split across Traction and Team)."""
    body = _read(RUBRIC_MD).lower()
    idx = body.find("refs back-check")
    assert idx >= 0
    nearby = body[max(0, idx - 50):idx + 400]
    assert "dim 5" in nearby or "dims 5" in nearby, (
        "rubric.md §'Refs back-check' MUST bind to dim 5 (Traction/proof)"
    )
    assert "dim 6" in nearby or "dims 5, 6" in nearby or "dims 5 and 6" in nearby or "5 + 6" in nearby or "5, 6" in nearby, (
        "rubric.md §'Refs back-check' MUST bind to dim 6 (Team credibility)"
    )


def test_rubric_documents_contradicted_two_point_deduction():
    body = _read(RUBRIC_MD).lower()
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
    assert "no deduction" in sub or "informational" in sub, (
        "rubric.md §'Refs back-check' MUST document that NOT-IN-REFS is "
        "informational only (no deduction)"
    )


def test_rubric_documents_empty_refs_fallback():
    """Backward-compat — when refs/ has no source-of-truth materials, the
    sub-rule is inactive and dims 5/6 fall back to BRIEF-only cross-check."""
    body = _read(RUBRIC_MD).lower()
    idx = body.find("refs back-check")
    assert idx >= 0
    sub = body[idx:]
    assert "inactive" in sub or "falls back" in sub or "backward compat" in sub or "backward-compat" in sub, (
        "rubric.md §'Refs back-check' MUST document the empty-refs fallback "
        "behavior (backward-compat with pre-#166 behavior)"
    )


def test_rubric_escalates_to_existing_flags_1_and_2():
    """The escalation path uses the EXISTING critical flags 1 (Fabricated
    traction) and 2 (Fabricated team credentials)."""
    body = _read(RUBRIC_MD)
    idx = body.find("Refs back-check")
    assert idx >= 0
    sub = body[idx:]
    assert "Fabricated traction" in sub, (
        "rubric.md §'Refs back-check' MUST name 'Fabricated traction' "
        "(existing flag 1) as the escalation path for traction-bearing "
        "CONTRADICTED claims"
    )
    assert "Fabricated team credentials" in sub, (
        "rubric.md §'Refs back-check' MUST name 'Fabricated team credentials' "
        "(existing flag 2) as the escalation path for team-bearing "
        "CONTRADICTED claims"
    )


def test_rubric_preserves_existing_critical_flags_section():
    """The four standing critical flags (Fabricated traction, Fabricated
    team credentials, Market-math error, Absent ask) MUST remain
    intact."""
    body = _read(RUBRIC_MD)
    assert "Fabricated traction" in body, "rubric.md MUST preserve flag 1"
    assert "Fabricated team credentials" in body, "rubric.md MUST preserve flag 2"
    assert "Market-math error" in body, "rubric.md MUST preserve flag 3"
    assert "Absent ask" in body, "rubric.md MUST preserve flag 4"


def test_rubric_preserves_dimensions_table():
    """The 10-dim /49 rubric table MUST remain — the refs back-check is
    a sibling subsection, not a replacement.

    Post-#357 the deck rubric migrated from /40 (8 dims, ≥35) to /44
    (9 dims, ≥39) with dim 9 *Rhetorical economy* at weight 4.
    Post-#550 it migrated from /44 (9 dims, ≥39) to /49 (10 dims, ≥43)
    with dim 10 *Business-model & unit-economics credibility* at
    weight 5.
    """
    body = _read(RUBRIC_MD)
    assert "Narrative arc" in body, "rubric.md MUST preserve dim 1"
    assert "Traction / proof" in body, "rubric.md MUST preserve dim 5"
    assert "Team credibility" in body, "rubric.md MUST preserve dim 6"


# ---------------------------------------------------------------------------
# Cross-doc coherence — the four docs reference each other correctly
# ---------------------------------------------------------------------------


def test_skill_md_source_of_truth_references_rubric_subsection_name():
    """SKILL.md should point at the rubric's §'Refs back-check (dims 5, 6)'
    subsection by name so the reviewer-side deduction rule is
    discoverable."""
    body = _read(SKILL_MD)
    idx = body.find("Source-of-truth materials")
    assert idx >= 0
    sub = body[idx:]
    assert "Refs back-check" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST reference rubric.md's "
        "§'Refs back-check' subsection by name"
    )


def test_deck_review_references_skill_source_of_truth():
    """deck-review.md step 6 should point at SKILL.md §'Source-of-truth
    materials' for the canonical filename disambiguation rule."""
    body = _read(REVIEW_MD)
    assert "Source-of-truth materials" in body, (
        "deck-review.md MUST reference SKILL.md §'Source-of-truth materials' "
        "so the reviewer knows the source-of-truth vs generic-refs "
        "disambiguation rule"
    )
