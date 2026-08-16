"""Doc-coverage smoke tests for the "findings are leads, not evidence"
contract (issue #749).

Per issue #749: revisers historically treated review-sidecar prose
(comments.md / verdict.md critical-flag prose) as trusted input — nothing
in the lifecycle verified claims that originate *inside a review itself*.
The refs back-check machinery (rubric.md sec "Refs back-check (dim 3)")
audits memo *bodies*; review sidecars were never audited, so a citation or
anchor invented in review prose could flow unchecked into the next body
revision. The canary evidence was a two-generation error chain: a
mis-anchored citation in memo.3.review's critical-flag prose was trusted
verbatim by the memo.4 reviser, and memo.4.review's own remediation note
then guessed the correct location wrong a second time.

This is a Phase A, prose-discipline-only fix (no new modules, no schema
changes) mirroring the existing refs back-check precedent:

  1. memo-revise.md step 7 gains a "Findings are leads, not evidence"
     contract rule: any citation/anchor/quote a revision writes MUST be
     verified against the source file at write time, even when the value
     was supplied by a review finding, audit sibling, or directive.
  2. memo-revise.md step 9 gains a changelog.md note requirement: when a
     review-supplied anchor is corrected during revision, log the
     correction.
  3. memo-review.md step 8 gains a finding-hygiene clause: when a
     finding's remediation prose names a source location, the reviewer
     must have resolved that location using the same back-check
     machinery it already applies to body citations.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The lifecycle commands themselves are
LLM-driven, so behavioural assertions belong in consumer-side integration
tests, not here.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with a similarly-shaped
``test_findings_leads_not_evidence_doc`` another skill might pick.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.testing import read_text as _read

SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
REVISE_MD = SKILL_ROOT / "commands" / "memo-revise.md"
REVIEW_MD = SKILL_ROOT / "commands" / "memo-review.md"


# ---------------------------------------------------------------------------
# memo-revise.md — step 7 "Findings are leads, not evidence" contract rule
# ---------------------------------------------------------------------------


def test_revise_documents_findings_are_leads_not_evidence():
    body = _read(REVISE_MD)
    assert "Findings are leads, not evidence" in body, (
        "memo-revise.md MUST document the 'Findings are leads, not "
        "evidence' contract rule (issue #749)"
    )


def test_revise_requires_verification_even_when_review_supplied():
    """The rule MUST apply even when the citation/anchor/quote was
    supplied by a review finding, audit sibling, or directive — not just
    when the reviser originates the citation itself."""
    body = _read(REVISE_MD)
    idx = body.find("Findings are leads, not evidence")
    assert idx >= 0
    sub = body[idx : idx + 1500]
    assert "comments.md` finding" in sub or "review finding" in sub, (
        "memo-revise.md 'Findings are leads, not evidence' rule MUST "
        "explicitly cover citations/anchors supplied by review findings"
    )
    assert "verify" in sub.lower() or "resolve" in sub.lower(), (
        "memo-revise.md 'Findings are leads, not evidence' rule MUST "
        "require verification/resolution against the source file"
    )


def test_revise_references_issue_749():
    body = _read(REVISE_MD)
    assert "#749" in body, (
        "memo-revise.md MUST reference issue #749 near the new contract "
        "rule(s) so the audit trail is discoverable"
    )


def test_revise_references_refs_back_check_precedent():
    """The new rule should be anchored to the existing refs back-check
    precedent (rubric.md dim 3), not introduced as a free-floating rule."""
    body = _read(REVISE_MD)
    idx = body.find("Findings are leads, not evidence")
    assert idx >= 0
    sub = body[idx : idx + 1500]
    assert "Refs back-check" in sub, (
        "memo-revise.md 'Findings are leads, not evidence' rule MUST "
        "cross-reference rubric.md's 'Refs back-check (dim 3)' precedent"
    )


# ---------------------------------------------------------------------------
# memo-revise.md — step 9 changelog.md correction-note requirement
# ---------------------------------------------------------------------------


def test_revise_documents_citation_correction_note():
    body = _read(REVISE_MD)
    assert "Review-supplied citation correction note" in body, (
        "memo-revise.md MUST document the 'Review-supplied citation "
        "correction note' changelog.md requirement (issue #749)"
    )


def test_revise_correction_note_is_conditional_not_always_written():
    """The correction note is only written when verification actually
    corrected something — it is NOT a mandatory row on every revision."""
    body = _read(REVISE_MD)
    # The step-9 header occurrence (not the step-7 forward-reference) is
    # where the "default and unremarkable absence" language lives.
    idx = body.rfind("Review-supplied citation correction note")
    assert idx >= 0
    sub = body[idx : idx + 1200]
    assert "default" in sub.lower() or "absence" in sub.lower(), (
        "memo-revise.md MUST document that the correction note's absence "
        "(nothing to correct) is the default, unremarkable case"
    )


# ---------------------------------------------------------------------------
# memo-review.md — step 8 finding-hygiene clause
# ---------------------------------------------------------------------------


def test_review_documents_finding_hygiene_clause():
    body = _read(REVIEW_MD)
    assert "Finding hygiene" in body, (
        "memo-review.md MUST document the 'Finding hygiene' clause "
        "(issue #749)"
    )


def test_review_finding_hygiene_references_refs_back_check():
    body = _read(REVIEW_MD)
    idx = body.find("Finding hygiene")
    assert idx >= 0
    sub = body[idx : idx + 1200]
    assert "Refs back-check" in sub, (
        "memo-review.md 'Finding hygiene' clause MUST cross-reference "
        "rubric.md's 'Refs back-check (dim 3)' precedent — the reviewer's "
        "own prose is held to the same standard it applies to the body"
    )


def test_review_finding_hygiene_references_issue_749():
    body = _read(REVIEW_MD)
    idx = body.find("Finding hygiene")
    assert idx >= 0
    sub = body[idx : idx + 300]
    assert "#749" in sub, (
        "memo-review.md 'Finding hygiene' clause MUST reference issue #749"
    )


def test_review_finding_hygiene_precedes_summary_write():
    """The finding-hygiene clause belongs to step 8 (comments.md), which
    must come before step 9 (_summary.md write) in document order."""
    body = _read(REVIEW_MD)
    hygiene_idx = body.find("Finding hygiene")
    summary_idx = body.find('9. **Write `_summary.md`**')
    assert hygiene_idx >= 0
    assert summary_idx >= 0
    assert hygiene_idx < summary_idx, (
        "memo-review.md 'Finding hygiene' clause MUST appear before the "
        "step 9 '_summary.md' write (it belongs to step 8)"
    )
