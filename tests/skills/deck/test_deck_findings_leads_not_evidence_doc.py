"""Doc-coverage smoke tests for the deck-side "findings are leads, not
evidence" contract (issue #749).

Issue #749 is a memo-originated defect: a reviser trusted a citation
anchor invented in review-sidecar prose instead of re-verifying it, and a
subsequent reviewer's own remediation note repeated the mistake. The
memo fix (see ``tests/skills/memo/test_memo_findings_leads_not_evidence_doc.py``)
adds a reviser-side "findings are leads, not evidence" contract rule plus
a changelog correction-note requirement, and a reviewer-side finding-
hygiene clause. Per the issue's acceptance sketch, sibling skills with
the same reviser pattern (deck, proposal, report) inherit the same
wording "when convenient."

The deck skill has a clean analog: ``deck-review.md``'s dim 5/6 refs
back-check sub-step (issue #166) writes ``refs/<file>`` anchors into
``comments.md`` exactly like memo's dim 3 refs back-check, and
``deck-revise.md`` step 7 "Build a revision plan" / step 11
``_revision-log.md`` mirror memo-revise's step 7 / step 9 shape. This
file guards the deck-side prose additions.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. Per-skill test filename convention (#58):
this file is named with a ``test_deck_`` prefix.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.testing import read_text as _read

SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"
REVISE_MD = SKILL_ROOT / "commands" / "deck-revise.md"
REVIEW_MD = SKILL_ROOT / "commands" / "deck-review.md"


def test_revise_documents_findings_are_leads_not_evidence():
    body = _read(REVISE_MD)
    assert "Findings are leads, not evidence" in body, (
        "deck-revise.md MUST document the 'Findings are leads, not "
        "evidence' contract rule (issue #749)"
    )
    assert "#749" in body


def test_revise_documents_citation_correction_note():
    body = _read(REVISE_MD)
    assert "Review-supplied citation correction" in body, (
        "deck-revise.md MUST document the review-supplied citation "
        "correction note requirement (issue #749)"
    )


def test_revise_findings_are_leads_references_refs_back_check():
    body = _read(REVISE_MD)
    idx = body.find("Findings are leads, not evidence")
    assert idx >= 0
    sub = body[idx : idx + 800]
    assert "Refs back-check" in sub, (
        "deck-revise.md 'Findings are leads, not evidence' rule MUST "
        "cross-reference rubric.md's 'Refs back-check (dims 5, 6)' "
        "precedent"
    )


def test_review_documents_finding_hygiene_clause():
    body = _read(REVIEW_MD)
    assert "Finding hygiene" in body, (
        "deck-review.md MUST document the 'Finding hygiene' clause "
        "(issue #749)"
    )
    assert "#749" in body


def test_review_finding_hygiene_references_refs_back_check():
    body = _read(REVIEW_MD)
    idx = body.find("Finding hygiene")
    assert idx >= 0
    sub = body[idx : idx + 800]
    assert "back-check" in sub.lower(), (
        "deck-review.md 'Finding hygiene' clause MUST cross-reference the "
        "refs back-check discipline it borrows from"
    )
