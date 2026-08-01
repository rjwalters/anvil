"""Doc-coverage tests for the proposal pending-marker gate (issue #841).

Wires the framework `anvil/lib/pending_marker.py` primitive (shipped for
`anvil:paper` under issue #842) into `anvil:proposal`, following the
"adopting the convention in a skill" recipe in
`anvil/lib/snippets/pending_marker.md`:

1. `proposal-review.md` step 4l runs the gate against `proposal.tex` (via
   `--body`, since the module's `<slug>.md`/`main.tex` auto-detect does not
   match this skill's fixed body filename), documents the distinct
   non-blocking `pending_dependency` flag, and computes a `ready` gate
   separate from `advance` that holds the thread at `REVIEWED`.
2. `proposal-audit.md` re-runs the gate as a terminal check and folds it
   into a gate separate from `pass` before `AUDITED`.
3. `proposal-revise.md` carries the no-fabrication carve-out.
4. `rubric.md` documents the no-dimension-penalty note and the
   "Outstanding dependencies (not critical flags)" section.

Per the #58 packaging convention, this filename
(`test_proposal_pending_marker_doc.py`) is unique across `tests/skills/*/`.
"""

from __future__ import annotations

from pathlib import Path

# tests/skills/proposal → anvil/skills/proposal
SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "proposal"
RUBRIC = SKILL_ROOT / "rubric.md"
REVIEW_COMMAND = SKILL_ROOT / "commands" / "proposal-review.md"
AUDIT_COMMAND = SKILL_ROOT / "commands" / "proposal-audit.md"
REVISE_COMMAND = SKILL_ROOT / "commands" / "proposal-revise.md"
ORCHESTRATOR = SKILL_ROOT / "commands" / "proposal.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# proposal-review.md
# ---------------------------------------------------------------------------


def test_review_invokes_pending_marker_module() -> None:
    body = _read(REVIEW_COMMAND)
    assert "anvil.lib.pending_marker" in body
    assert "--body proposal.tex" in body


def test_review_documents_distinct_flag_type() -> None:
    body = _read(REVIEW_COMMAND)
    assert "pending_dependency" in body
    assert "blocking_critical_flags" in body


def test_review_documents_no_dimension_penalty() -> None:
    body = _read(REVIEW_COMMAND)
    assert "no dimension penalty" in body.lower()


def test_review_computes_ready_gate_separate_from_advance() -> None:
    body = _read(REVIEW_COMMAND)
    assert "ready = advance" in body
    assert "hold the thread at `REVIEWED`" in body


def test_review_verdict_has_outstanding_dependencies_note() -> None:
    body = _read(REVIEW_COMMAND)
    assert "Outstanding dependencies" in body


# ---------------------------------------------------------------------------
# proposal-audit.md
# ---------------------------------------------------------------------------


def test_audit_invokes_pending_marker_module() -> None:
    body = _read(AUDIT_COMMAND)
    assert "anvil.lib.pending_marker" in body
    assert "--body proposal.tex" in body


def test_audit_terminal_gate_separate_from_pass() -> None:
    body = _read(AUDIT_COMMAND)
    assert "Terminal-state gate for `AUDITED`" in body


def test_audit_verdict_has_outstanding_dependencies_note() -> None:
    body = _read(AUDIT_COMMAND)
    assert "Outstanding dependencies" in body


# ---------------------------------------------------------------------------
# proposal-revise.md
# ---------------------------------------------------------------------------


def test_revise_carve_out_present() -> None:
    body = _read(REVISE_COMMAND)
    assert "pending_dependency" in body
    assert "NEVER fabricate a value" in body


# ---------------------------------------------------------------------------
# proposal.md (portfolio orchestrator)
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


def test_rubric_combined_advance_gate_mentions_pending() -> None:
    body = _read(RUBRIC)
    assert "no unresolved pending marker" in body
