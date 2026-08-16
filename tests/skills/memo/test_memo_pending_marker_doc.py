"""Doc-coverage tests for the memo pending-marker gate (issue #841).

Wires the framework `anvil/lib/pending_marker.py` primitive (shipped for
`anvil:paper` under issue #842) into `anvil:memo`, following the "adopting
the convention in a skill" recipe in `anvil/lib/snippets/pending_marker.md`:

1. `memo-review.md` step 4n runs the gate against `<thread>.md`
   (auto-detected — no `--body` override needed, per the #295 slug-echo
   convention), documents the distinct non-blocking `pending_dependency`
   flag, and computes a `ready` gate separate from `advance` — memo has no
   separate audit phase, so this gate is the sole terminal-state hold on
   `READY`.
2. `memo-revise.md` carries the no-fabrication carve-out.
3. `memo.md` (portfolio orchestrator) documents the pending-marker
   terminal-gate hold on the `READY` state.
4. `rubric.md` documents the no-dimension-penalty note and the
   "Outstanding dependencies (not critical flags)" section.

Per the #58 packaging convention, this filename
(`test_memo_pending_marker_doc.py`) is unique across `tests/skills/*/`.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.testing import read_text as _read

# tests/skills/memo → anvil/skills/memo
SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
RUBRIC = SKILL_ROOT / "rubric.md"
REVIEW_COMMAND = SKILL_ROOT / "commands" / "memo-review.md"
REVISE_COMMAND = SKILL_ROOT / "commands" / "memo-revise.md"
ORCHESTRATOR = SKILL_ROOT / "commands" / "memo.md"


# ---------------------------------------------------------------------------
# memo-review.md
# ---------------------------------------------------------------------------


def test_review_invokes_pending_marker_module() -> None:
    body = _read(REVIEW_COMMAND)
    assert "anvil.lib.pending_marker" in body


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
    assert "Terminal-state gate for READY" in body


def test_review_verdict_has_outstanding_dependencies_note() -> None:
    body = _read(REVIEW_COMMAND)
    assert "Outstanding dependencies" in body


# ---------------------------------------------------------------------------
# memo-revise.md
# ---------------------------------------------------------------------------


def test_revise_carve_out_present() -> None:
    body = _read(REVISE_COMMAND)
    assert "pending_dependency" in body
    assert "NEVER fabricate a value" in body


# ---------------------------------------------------------------------------
# memo.md (portfolio orchestrator)
# ---------------------------------------------------------------------------


def test_orchestrator_documents_pending_gate_holds_ready() -> None:
    body = _read(ORCHESTRATOR)
    assert "pending_dependency" in body
    assert "REVIEWED" in body


# ---------------------------------------------------------------------------
# rubric.md
# ---------------------------------------------------------------------------


def test_rubric_documents_no_dimension_penalty_section() -> None:
    body = _read(RUBRIC)
    assert "Pending-measurement markers do not incur a dimension penalty" in body


def test_rubric_documents_outstanding_dependencies_section() -> None:
    body = _read(RUBRIC)
    assert "Outstanding dependencies (not critical flags" in body
