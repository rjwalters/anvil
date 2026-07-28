"""Doc-coverage smoke tests for the proposal-side "findings are leads,
not evidence" contract (issue #749).

See ``tests/skills/memo/test_memo_findings_leads_not_evidence_doc.py``
for the full background. The proposal skill's refs back-check is
**audit-owned** (``proposal-audit.md``'s "Refs back-check sub-step for
non-cost claims", issue #166) rather than review-owned, so the
finding-hygiene clause lands in ``proposal-audit.md`` (the sibling that
writes ``findings.md`` rows naming ``refs/<file>`` anchors) instead of
``proposal-review.md``. ``proposal-revise.md`` reads BOTH ``.review/``
and ``.audit/`` siblings, so its "findings are leads" rule and changelog
correction-note requirement cover both source formats (synthesis path
and per-sibling fallback path).

These tests assert on substring presence only. Per-skill test filename
convention (#58): this file is named with a ``test_proposal_`` prefix.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "proposal"
REVISE_MD = SKILL_ROOT / "commands" / "proposal-revise.md"
AUDIT_MD = SKILL_ROOT / "commands" / "proposal-audit.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_revise_documents_findings_are_leads_not_evidence():
    body = _read(REVISE_MD)
    assert "Findings are leads, not evidence" in body, (
        "proposal-revise.md MUST document the 'Findings are leads, not "
        "evidence' contract rule (issue #749)"
    )
    assert "#749" in body


def test_revise_documents_citation_correction_note():
    body = _read(REVISE_MD)
    assert "Review-supplied citation correction" in body, (
        "proposal-revise.md MUST document the review-supplied citation "
        "correction note requirement (issue #749)"
    )


def test_revise_findings_are_leads_references_refs_back_check():
    body = _read(REVISE_MD)
    idx = body.find("Findings are leads, not evidence")
    assert idx >= 0
    sub = body[idx : idx + 800]
    assert "Refs back-check" in sub, (
        "proposal-revise.md 'Findings are leads, not evidence' rule MUST "
        "cross-reference rubric.md's 'Refs back-check (dim 6 + dim 4)' "
        "precedent"
    )


def test_revise_findings_are_leads_applies_to_both_source_paths():
    """The rule must precede the 7a/7b synthesis-vs-fallback split so it
    is unambiguously read as applying to both."""
    body = _read(REVISE_MD)
    leads_idx = body.find("Findings are leads, not evidence")
    path_7a_idx = body.find("**7a. Primary path")
    assert leads_idx >= 0
    assert path_7a_idx >= 0
    assert leads_idx < path_7a_idx, (
        "proposal-revise.md 'Findings are leads, not evidence' rule MUST "
        "appear before the 7a/7b source-path split so it applies to both"
    )


def test_audit_documents_finding_hygiene_clause():
    body = _read(AUDIT_MD)
    assert "Finding hygiene" in body, (
        "proposal-audit.md MUST document the 'Finding hygiene' clause "
        "(issue #749) — the audit sibling owns the refs back-check for "
        "this skill"
    )
    assert "#749" in body


def test_audit_finding_hygiene_references_refs_back_check():
    body = _read(AUDIT_MD)
    idx = body.find("Finding hygiene")
    assert idx >= 0
    sub = body[max(0, idx - 200) : idx + 800]
    assert "back-check" in sub.lower(), (
        "proposal-audit.md 'Finding hygiene' clause MUST cross-reference "
        "the refs back-check discipline it borrows from"
    )
