"""Doc-coverage smoke tests for the proposal refs-back-check contract (issue #166).

Per issue #166 acceptance criteria: cheap "grep-the-doc" regression guard
that the source-of-truth ``refs/`` contract stays documented in the five
files it touches (SKILL.md, proposal-draft.md, proposal-audit.md,
proposal-review.md, rubric.md) and that the existing per-priced-line
sourceability walk is preserved (i.e., the new non-cost back-check role
is **additive**, not replacing).

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The lifecycle commands themselves are
LLM-driven, so behavioural assertions belong in consumer-side integration
tests, not here.

Per-skill test filename convention (#58): this file is named with a
``test_proposal_`` prefix so it never collides with a similarly-shaped
``test_refs_back_check_doc`` another skill might pick.

Specific guards this file owns (per the curator notes on #166):

  1. The ``CONTRADICTED`` verdict tag — the load-bearing detection
     requirement that the contract exists to catch.
  2. The audit-owned framing — the back-check primarily lives in
     ``proposal-audit`` (dim 6 Cost credibility); ``proposal-review``
     gestures rather than duplicates (dim 4 Scope completeness).
  3. The existing critical flags 2 (Cost estimate not credible /
     sourceable) and 4 (Internal inconsistency) MUST be named as the
     escalation path for CONTRADICTED claims — no new flag is created.
  4. Backward-compat with empty / generic-only ``refs/`` — the existing
     cost-only sourceability walk MUST remain intact and the new
     non-cost back-check MUST document explicit fallback behaviour
     when no source-of-truth materials are present.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "proposal"
SKILL_MD = SKILL_ROOT / "SKILL.md"
RUBRIC_MD = SKILL_ROOT / "rubric.md"
DRAFT_MD = SKILL_ROOT / "commands" / "proposal-draft.md"
AUDIT_MD = SKILL_ROOT / "commands" / "proposal-audit.md"
REVIEW_MD = SKILL_ROOT / "commands" / "proposal-review.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SKILL.md — §"Source-of-truth materials" subsection exists alongside the
# existing refs/ contract (additive, not replacing)
# ---------------------------------------------------------------------------


def test_skill_md_has_source_of_truth_subsection():
    body = _read(SKILL_MD)
    assert "Source-of-truth materials" in body, (
        "SKILL.md MUST contain a 'Source-of-truth materials' subsection "
        "(issue #166 acceptance criterion)"
    )


def test_skill_md_preserves_existing_refs_contract():
    """Pre-#166 regression guard — the existing refs/ contract in the
    artifact-contract block MUST remain intact."""
    body = _read(SKILL_MD)
    assert "refs/" in body, (
        "SKILL.md MUST preserve the existing 'refs/' contract prose"
    )


def test_skill_md_documents_audit_owned_framing():
    """The back-check is primarily audit-owned (dim 6) per the curator's
    per-skill dim mapping. The reviewer's role is light (dim 4 gesture)."""
    body = _read(SKILL_MD).lower()
    # The phrase "audit-owned" appears in the source-of-truth subsection.
    assert "audit-owned" in body or "audit owned" in body, (
        "SKILL.md MUST document the audit-owned framing of the refs "
        "back-check (the proposal rubric splits review subjective quality "
        "from audit verifiable correctness)"
    )


def test_skill_md_documents_coexistence_in_same_directory():
    body = _read(SKILL_MD).lower()
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
    # Cost-bearing shapes.
    assert "quote-" in body or "vendor-quote" in body or "vendor quote" in body, (
        "SKILL.md MUST name vendor quotes as a canonical source-of-truth shape"
    )
    assert "datasheet-" in body or "datasheet" in body, (
        "SKILL.md MUST name datasheets as a canonical source-of-truth shape"
    )
    # Scope-bearing shapes.
    assert "sow-" in body or "sow." in body or "sow " in body, (
        "SKILL.md MUST name SOW templates as a canonical scope-bearing "
        "source-of-truth shape"
    )
    # Deliverability-bearing shapes (CVs of leads).
    assert "cv-" in body or "cv." in body, (
        "SKILL.md MUST name CVs as a canonical deliverability-bearing "
        "source-of-truth shape"
    )
    # Comparable-bearing shapes.
    assert "comparables" in body or "comparable" in body, (
        "SKILL.md MUST name comparables as a canonical source-of-truth shape"
    )


def test_skill_md_documents_text_vs_presence_only_split():
    """v0 reads text-readable files (md, txt, json) into context; PDFs and
    images are presence-only signals. The split MUST be explicit."""
    body = _read(SKILL_MD).lower()
    assert "presence-only" in body or "presence only" in body, (
        "SKILL.md MUST document the presence-only treatment of PDFs/images "
        "in v0 (text extraction is out of scope per issue #167)"
    )


def test_skill_md_cross_references_four_consumers():
    """The SKILL.md prose MUST point at proposal-draft, proposal-audit,
    proposal-review, and rubric.md so the contract surfaces are
    discoverable in any direction."""
    body = _read(SKILL_MD)
    idx = body.find("Source-of-truth materials")
    assert idx >= 0, "Source-of-truth subsection missing"
    sub = body[idx:]
    assert "proposal-draft" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST cross-reference proposal-draft.md"
    )
    assert "proposal-audit" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST cross-reference proposal-audit.md"
    )
    assert "proposal-review" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST cross-reference proposal-review.md"
    )
    assert "rubric.md" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST cross-reference rubric.md"
    )


# ---------------------------------------------------------------------------
# proposal-draft.md — step 3 documents source-of-truth ingestion
# ---------------------------------------------------------------------------


def test_proposal_draft_step_3_references_source_of_truth():
    body = _read(DRAFT_MD).lower()
    assert "source-of-truth" in body, (
        "proposal-draft.md MUST reference 'source-of-truth' in step 3 "
        "(issue #166 drafter contract)"
    )


def test_proposal_draft_names_text_readable_ingestion():
    body = _read(DRAFT_MD).lower()
    assert ".md" in body and (".txt" in body or "text" in body) and ".json" in body, (
        "proposal-draft.md MUST name the text-readable file shapes "
        "ingested into drafter context (.md, .txt, .json)"
    )


def test_proposal_draft_documents_refs_wins_conflict_rule():
    """If a claim conflicts with a refs/ source-of-truth document, the
    refs/ document wins."""
    body = _read(DRAFT_MD).lower()
    haystack = body.replace("`", "")
    assert "refs/ document wins" in haystack or "refs document wins" in haystack, (
        "proposal-draft.md MUST document the 'refs/ document wins' rule "
        "for conflicts between claims and source-of-truth materials"
    )


def test_proposal_draft_references_source_of_truth_subsection():
    """proposal-draft.md step 3 should reference SKILL.md
    §'Source-of-truth materials'."""
    body = _read(DRAFT_MD)
    assert "Source-of-truth materials" in body, (
        "proposal-draft.md MUST reference SKILL.md §'Source-of-truth "
        "materials' so the drafter contract is anchored to the "
        "SKILL-level convention"
    )


# ---------------------------------------------------------------------------
# proposal-audit.md — extends sourceability walk to non-cost claims
# ---------------------------------------------------------------------------


def test_proposal_audit_has_refs_back_check_substep():
    body = _read(AUDIT_MD).lower()
    assert "refs back-check" in body or "refs back check" in body, (
        "proposal-audit.md MUST document the refs back-check sub-step "
        "for non-cost claims (issue #166 auditor contract)"
    )


def test_proposal_audit_names_all_four_verdict_tags():
    """The four verdict tags VERIFIED / UNVERIFIED / CONTRADICTED /
    NOT-IN-REFS MUST all be documented."""
    body = _read(AUDIT_MD)
    assert "VERIFIED" in body, "proposal-audit.md MUST document VERIFIED verdict tag"
    assert "UNVERIFIED" in body, "proposal-audit.md MUST document UNVERIFIED verdict tag"
    assert "CONTRADICTED" in body, (
        "proposal-audit.md MUST document CONTRADICTED verdict tag — the "
        "load-bearing detection requirement of issue #166"
    )
    assert "NOT-IN-REFS" in body, (
        "proposal-audit.md MUST document NOT-IN-REFS verdict tag"
    )


def test_proposal_audit_documents_non_cost_extension():
    """The back-check extends the existing cost-only sourceability walk
    to non-cost claims (scope, deliverability, comparables)."""
    body = _read(AUDIT_MD).lower()
    # Non-cost claim classes named in the curator notes.
    assert "non-cost" in body or "non cost" in body, (
        "proposal-audit.md MUST document the extension to non-cost claims"
    )
    assert "scope" in body, (
        "proposal-audit.md MUST name scope claims as in-scope for the "
        "back-check extension"
    )
    assert "deliverability" in body, (
        "proposal-audit.md MUST name deliverability claims as in-scope "
        "for the back-check extension"
    )
    assert "comparable" in body, (
        "proposal-audit.md MUST name comparable claims as in-scope for "
        "the back-check extension"
    )


def test_proposal_audit_one_per_type_back_check_floor():
    body = _read(AUDIT_MD).lower()
    assert "at least one claim" in body, (
        "proposal-audit.md MUST document the 'at least one claim per "
        "refs-document type' back-check floor"
    )


def test_proposal_audit_documents_contradicted_critical_flag_candidate():
    body = _read(AUDIT_MD)
    assert "critical-flag candidate" in body or "critical flag candidate" in body, (
        "proposal-audit.md MUST document that CONTRADICTED back-check "
        "verdicts are critical-flag candidates (issue #166 canary "
        "detection)"
    )


def test_proposal_audit_escalates_to_existing_flags_2_and_4():
    """The escalation path uses EXISTING critical flags 2 (Cost
    estimate not credible / not sourceable) and 4 (Internal
    inconsistency)."""
    body = _read(AUDIT_MD)
    # Flag 2 — cost not credible / not sourceable.
    assert "Cost estimate not credible" in body or "cost estimate not credible" in body.lower() or "not credible" in body.lower(), (
        "proposal-audit.md MUST name 'Cost estimate not credible / "
        "not sourceable' (existing flag 2) as the escalation path for "
        "cost-bearing CONTRADICTED claims"
    )
    # Flag 4 — internal inconsistency.
    assert "Internal inconsistency" in body or "internal inconsistency" in body.lower(), (
        "proposal-audit.md MUST name 'Internal inconsistency' (existing "
        "flag 4) as the escalation path for scope / deliverability / "
        "comparable CONTRADICTED claims"
    )


def test_proposal_audit_documents_empty_refs_fallback():
    """When refs/ contains no source-of-truth materials, the back-check
    sub-step MUST be inactive — backward-compat with pre-#166
    cost-only behavior."""
    body = _read(AUDIT_MD).lower()
    assert "inactive" in body or "falls back" in body or "fall back" in body, (
        "proposal-audit.md MUST document the empty/generic-only refs/ "
        "fallback behavior (backward-compat with cost-only sourceability)"
    )


def test_proposal_audit_preserves_existing_cost_sourceability_walk():
    """The existing per-priced-line sourceability walk (step 7 in the
    current command) MUST remain intact — the non-cost back-check is
    ADDITIVE."""
    body = _read(AUDIT_MD).lower()
    # The cost-sourceability walk names planning ranges, list prices,
    # and quotes as the sourceability bases.
    assert "planning range" in body, (
        "proposal-audit.md MUST preserve the existing 'planning range' "
        "sourceability basis for cost claims"
    )
    assert "vendor list price" in body or "list price" in body, (
        "proposal-audit.md MUST preserve the existing 'vendor list "
        "price' sourceability basis for cost claims"
    )


# ---------------------------------------------------------------------------
# proposal-review.md — light step 4 mention (gestures, does not duplicate)
# ---------------------------------------------------------------------------


def test_proposal_review_step_4_mentions_source_of_truth():
    body = _read(REVIEW_MD)
    assert "Source-of-truth materials" in body or "source-of-truth" in body.lower(), (
        "proposal-review.md step 4 MUST mention source-of-truth "
        "materials (issue #166 light reviewer contract)"
    )


def test_proposal_review_documents_audit_owned_back_check():
    """The reviewer gestures, does not duplicate — the per-claim refs
    back-check is audit-owned, not review-owned."""
    body = _read(REVIEW_MD).lower()
    # The phrase "audit-owned" appears in step 4.
    assert "audit-owned" in body or "audit owned" in body, (
        "proposal-review.md MUST document that the refs back-check is "
        "audit-owned (reviewer gestures, does not duplicate)"
    )


def test_proposal_review_documents_no_duplication():
    """The reviewer MUST NOT duplicate the per-claim back-check."""
    body = _read(REVIEW_MD).lower()
    assert "duplicate" in body or "duplicat" in body, (
        "proposal-review.md MUST document that the reviewer does NOT "
        "duplicate the per-claim refs back-check (audit-owned)"
    )


def test_proposal_review_binds_light_touch_to_dim_4():
    """The light reviewer touch lives in dim 4 (Scope completeness)
    per the curator notes."""
    body = _read(REVIEW_MD).lower()
    # The step-4 prose names dim 4 explicitly.
    assert "dim 4" in body, (
        "proposal-review.md MUST bind the light source-of-truth touch "
        "to dim 4 (Scope completeness)"
    )


# ---------------------------------------------------------------------------
# rubric.md — §"Refs back-check (dim 6 + dim 4)" subsection exists with
# deduction schedule
# ---------------------------------------------------------------------------


def test_rubric_has_refs_back_check_subsection():
    body = _read(RUBRIC_MD)
    assert "Refs back-check" in body, (
        "rubric.md MUST contain a 'Refs back-check' subsection "
        "(issue #166 acceptance criterion)"
    )


def test_rubric_refs_back_check_primarily_binds_to_dim_6():
    """The rubric subsection MUST bind primarily to dim 6 (Cost
    credibility) — the audit-owned deduction lives here."""
    body = _read(RUBRIC_MD).lower()
    idx = body.find("refs back-check")
    assert idx >= 0
    nearby = body[max(0, idx - 50):idx + 400]
    assert "dim 6" in nearby, (
        "rubric.md §'Refs back-check' MUST bind to dim 6 (Cost credibility)"
    )


def test_rubric_refs_back_check_names_light_dim_4_touch():
    """The rubric MUST mention the light dim 4 touch (review-side
    gesture)."""
    body = _read(RUBRIC_MD).lower()
    idx = body.find("refs back-check")
    assert idx >= 0
    sub = body[idx:]
    assert "dim 4" in sub, (
        "rubric.md §'Refs back-check' MUST mention dim 4 (Scope "
        "completeness) as the light reviewer-side touch"
    )


def test_rubric_documents_contradicted_two_point_deduction():
    body = _read(RUBRIC_MD).lower()
    idx = body.find("refs back-check")
    assert idx >= 0
    sub = body[idx:]
    assert "two-point" in sub or "2-point" in sub or "two point" in sub, (
        "rubric.md §'Refs back-check' MUST document the two-point "
        "deduction for CONTRADICTED claims"
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
        "rubric.md §'Refs back-check' MUST document the one-point "
        "deduction for UNVERIFIED claims"
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
    """Backward-compat — when refs/ has no source-of-truth materials,
    the sub-rule is inactive and the audit falls back to cost-only
    sourceability."""
    body = _read(RUBRIC_MD).lower()
    idx = body.find("refs back-check")
    assert idx >= 0
    sub = body[idx:]
    assert "inactive" in sub or "falls back" in sub or "backward compat" in sub or "backward-compat" in sub, (
        "rubric.md §'Refs back-check' MUST document the empty-refs "
        "fallback behavior (backward-compat with cost-only sourceability)"
    )


def test_rubric_escalates_to_existing_flags_2_and_4():
    """The escalation path uses the EXISTING critical flags 2 (Cost
    estimate not credible) and 4 (Internal inconsistency)."""
    body = _read(RUBRIC_MD)
    idx = body.find("Refs back-check")
    assert idx >= 0
    sub = body[idx:]
    assert "Cost estimate not credible" in sub or "not credible" in sub.lower() or "Cost not credible" in sub, (
        "rubric.md §'Refs back-check' MUST name 'Cost estimate not "
        "credible' (existing flag 2) as the escalation path for "
        "cost-bearing CONTRADICTED claims"
    )
    assert "Internal inconsistency" in sub or "internal inconsistency" in sub.lower(), (
        "rubric.md §'Refs back-check' MUST name 'Internal inconsistency' "
        "(existing flag 4) as the escalation path for scope / "
        "deliverability / comparable CONTRADICTED claims"
    )


def test_rubric_preserves_existing_critical_flags_section():
    """The four standing critical flags MUST remain intact — the refs
    back-check uses the existing flags as escalation, no new flags."""
    body = _read(RUBRIC_MD)
    assert "Misses a stated hard constraint" in body, (
        "rubric.md MUST preserve flag 1 (Misses a stated hard constraint)"
    )
    assert "Cost estimate not credible" in body, (
        "rubric.md MUST preserve flag 2 (Cost estimate not credible)"
    )
    assert "Not deliverable as resourced" in body, (
        "rubric.md MUST preserve flag 3 (Not deliverable as resourced)"
    )
    assert "Internal inconsistency" in body, (
        "rubric.md MUST preserve flag 4 (Internal inconsistency)"
    )


def test_rubric_preserves_dimensions_table():
    """The 8-dim /40 rubric table MUST remain — the refs back-check is
    a sibling subsection, not a replacement."""
    body = _read(RUBRIC_MD)
    assert "Intent / requirements clarity" in body, (
        "rubric.md MUST preserve dim 1 (Intent / requirements clarity)"
    )
    assert "Scope completeness" in body, (
        "rubric.md MUST preserve dim 4 (Scope completeness)"
    )
    assert "Cost credibility" in body, (
        "rubric.md MUST preserve dim 6 (Cost credibility)"
    )


# ---------------------------------------------------------------------------
# Cross-doc coherence — the five docs reference each other correctly
# ---------------------------------------------------------------------------


def test_skill_md_source_of_truth_references_rubric_subsection_name():
    """SKILL.md should point at the rubric's refs back-check subsection by
    name so the audit-side deduction rule is discoverable."""
    body = _read(SKILL_MD)
    idx = body.find("Source-of-truth materials")
    assert idx >= 0
    sub = body[idx:]
    assert "Refs back-check" in sub, (
        "SKILL.md §'Source-of-truth materials' MUST reference rubric.md's "
        "§'Refs back-check' subsection by name"
    )


def test_proposal_audit_references_skill_source_of_truth():
    """proposal-audit.md should point at SKILL.md §'Source-of-truth
    materials' for the canonical filename disambiguation rule."""
    body = _read(AUDIT_MD)
    assert "Source-of-truth materials" in body, (
        "proposal-audit.md MUST reference SKILL.md §'Source-of-truth "
        "materials' so the auditor knows the source-of-truth vs "
        "generic-refs disambiguation rule"
    )
