"""Doc-coverage smoke tests for the report-side "findings are leads, not
evidence" contract (issue #749).

See ``tests/skills/memo/test_memo_findings_leads_not_evidence_doc.py``
for the full background. The report skill's citation authority is
**audit-owned**: ``report-audit.md`` step 5 builds the claim inventory
(the ``Cited source`` / ``Verified?`` columns of ``findings.md``), the
report-skill analog of memo's dim 3 refs back-check. ``report-review.md``
does not do citation work at all, so the finding-hygiene clause lands in
``report-audit.md`` instead. ``report-revise.md`` reads BOTH
``.review/`` and ``.audit/`` siblings (both REQUIRED for this skill), so
its "findings are leads" rule and changelog correction-note requirement
cover claims sourced from either sibling.

These tests assert on substring presence only. Per-skill test filename
convention (#58): this file is named with a ``test_report_`` prefix.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.testing import read_text as _read

SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "report"
REVISE_MD = SKILL_ROOT / "commands" / "report-revise.md"
AUDIT_MD = SKILL_ROOT / "commands" / "report-audit.md"


def test_revise_documents_findings_are_leads_not_evidence():
    body = _read(REVISE_MD)
    assert "Findings are leads, not evidence" in body, (
        "report-revise.md MUST document the 'Findings are leads, not "
        "evidence' contract rule (issue #749)"
    )
    assert "#749" in body


def test_revise_documents_citation_correction_note():
    body = _read(REVISE_MD)
    assert "Review-supplied citation correction" in body, (
        "report-revise.md MUST document the review-supplied citation "
        "correction note requirement (issue #749)"
    )


def test_revise_findings_are_leads_references_audit_claim_inventory():
    body = _read(REVISE_MD)
    idx = body.find("Findings are leads, not evidence")
    assert idx >= 0
    sub = body[idx : idx + 800]
    assert "report-audit" in sub, (
        "report-revise.md 'Findings are leads, not evidence' rule MUST "
        "cross-reference report-audit.md's claim-inventory discipline"
    )


def test_audit_documents_finding_hygiene_clause():
    body = _read(AUDIT_MD)
    assert "Finding hygiene" in body, (
        "report-audit.md MUST document the 'Finding hygiene' clause "
        "(issue #749) — the audit sibling owns citation verification for "
        "this skill"
    )
    assert "#749" in body


def test_audit_finding_hygiene_precedes_data_contract_step():
    """The finding-hygiene clause belongs to step 5 (claim inventory),
    which must come before step 6 (data-contract back-check) in
    document order."""
    body = _read(AUDIT_MD)
    hygiene_idx = body.find("Finding hygiene")
    step6_idx = body.find("6. **Data-contract back-check**")
    assert hygiene_idx >= 0
    assert step6_idx >= 0
    assert hygiene_idx < step6_idx, (
        "report-audit.md 'Finding hygiene' clause MUST appear before "
        "step 6 (it belongs to step 5's claim inventory)"
    )
