"""Doc-coverage tests for the report pending-marker gate (issue #841).

Wires the framework `anvil/lib/pending_marker.py` primitive (shipped for
`anvil:paper` under issue #842) into `anvil:report`, following the
"adopting the convention in a skill" recipe in
`anvil/lib/snippets/pending_marker.md`:

1. `report-review.md` step 4f runs the gate against `report.md` (via
   `--body`, since the module's `<slug>.md`/`main.tex` auto-detect does not
   match this skill's fixed body filename) and documents the distinct
   non-blocking `pending_dependency` flag.
2. `report-audit.md` re-runs the gate as the terminal check before
   `AUDITED`, folded into a gate separate from the `pass` field.
3. `report-revise.md` carries the no-fabrication carve-out.
4. `report-promote.md` re-checks the gate before `CUSTOMER-READY` as
   defense-in-depth alongside the machine-checkable `AUDITED` precondition.
5. `rubric.md` documents the no-dimension-penalty note and the
   "Outstanding dependencies (not critical flags)" section.

Per the #58 packaging convention, this filename
(`test_report_pending_marker_doc.py`) is unique across `tests/skills/*/`.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.testing import read_text as _read

# tests/skills/report → anvil/skills/report
SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "report"
RUBRIC = SKILL_ROOT / "rubric.md"
REVIEW_COMMAND = SKILL_ROOT / "commands" / "report-review.md"
AUDIT_COMMAND = SKILL_ROOT / "commands" / "report-audit.md"
REVISE_COMMAND = SKILL_ROOT / "commands" / "report-revise.md"
PROMOTE_COMMAND = SKILL_ROOT / "commands" / "report-promote.md"
ORCHESTRATOR = SKILL_ROOT / "commands" / "report.md"


# ---------------------------------------------------------------------------
# report-review.md
# ---------------------------------------------------------------------------


def test_review_invokes_pending_marker_module() -> None:
    body = _read(REVIEW_COMMAND)
    assert "anvil.lib.pending_marker" in body
    assert "--body report.md" in body


def test_review_documents_distinct_flag_type() -> None:
    body = _read(REVIEW_COMMAND)
    assert "pending_dependency" in body
    assert "blocking_critical_flags" in body


def test_review_documents_no_dimension_penalty() -> None:
    body = _read(REVIEW_COMMAND)
    assert "no dimension penalty" in body.lower()


def test_review_verdict_has_outstanding_dependencies_note() -> None:
    body = _read(REVIEW_COMMAND)
    assert "Outstanding dependencies" in body


# ---------------------------------------------------------------------------
# report-audit.md
# ---------------------------------------------------------------------------


def test_audit_invokes_pending_marker_module() -> None:
    body = _read(AUDIT_COMMAND)
    assert "anvil.lib.pending_marker" in body
    assert "--body report.md" in body


def test_audit_terminal_gate_separate_from_pass() -> None:
    body = _read(AUDIT_COMMAND)
    assert "Terminal-state gate for `AUDITED`" in body


def test_audit_verdict_has_outstanding_dependencies_note() -> None:
    body = _read(AUDIT_COMMAND)
    assert "Outstanding dependencies" in body


# ---------------------------------------------------------------------------
# report-revise.md
# ---------------------------------------------------------------------------


def test_revise_carve_out_present() -> None:
    body = _read(REVISE_COMMAND)
    assert "pending_dependency" in body
    assert "NEVER fabricate a value" in body


# ---------------------------------------------------------------------------
# report-promote.md
# ---------------------------------------------------------------------------


def test_promote_precondition_present() -> None:
    body = _read(PROMOTE_COMMAND)
    assert "No unresolved pending marker" in body
    assert "anvil.lib.pending_marker" in body


# ---------------------------------------------------------------------------
# report.md (portfolio orchestrator)
# ---------------------------------------------------------------------------


def test_orchestrator_documents_pending_gate() -> None:
    body = _read(ORCHESTRATOR)
    assert "pending_dependency" in body


# ---------------------------------------------------------------------------
# rubric.md
# ---------------------------------------------------------------------------


def test_rubric_documents_no_dimension_penalty_section() -> None:
    body = _read(RUBRIC)
    assert "Pending-measurement markers do not incur a dimension penalty" in body


def test_rubric_documents_outstanding_dependencies_section() -> None:
    body = _read(RUBRIC)
    assert "Outstanding dependencies (not critical flags" in body
