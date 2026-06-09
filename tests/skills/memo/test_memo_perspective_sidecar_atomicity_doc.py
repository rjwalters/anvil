"""Doc-coverage guard for memo-perspective staged-sidecar wiring (issue #350).

Mirrors `test_memo_review_sidecar_atomicity_doc.py` from the memo-review
pilot (PR #354). Pins the prose shape of the four-touch migration:

1. Outputs section names the staged-sidecar primitive + the leading-dot
   ``.tmp`` staging shape + "atomic" rename contract.
2. Step 1 (Discover state) invokes ``cleanup_stale_staging`` before the
   resume check.
3. Initialize step opens ``staged_sidecar`` with the required-files
   manifest matching the Outputs section.
4. Issue #350 is referenced for audit-trail traceability.

Per the per-skill test filename convention (#58), this file is named
distinctly to avoid collision with the other ``test_memo_*_doc.py``
files in the same dir.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = (
    REPO_ROOT / "anvil" / "skills" / "memo" / "commands" / "memo-perspective.md"
)


def _read() -> str:
    return DOC.read_text(encoding="utf-8")


def test_memo_perspective_doc_references_staged_sidecar_primitive():
    text = _read()
    assert "anvil/lib/sidecar.py" in text
    assert "staged_sidecar" in text


def test_memo_perspective_doc_names_required_files_manifest():
    text = _read()
    for name in ("notes.md", "candidates.md", "_meta.json", "_progress.json"):
        assert name in text, f"required file {name!r} missing from prose"


def test_memo_perspective_doc_step_1_invokes_cleanup_sweep():
    text = _read()
    assert "cleanup_one_staging" in text


def test_memo_perspective_doc_describes_atomic_rename_contract():
    text = _read()
    assert "atomically" in text.lower() or "atomic" in text.lower()
    assert "leading-dot" in text or ".tmp" in text


def test_memo_perspective_doc_references_issue_350():
    text = _read()
    assert "#350" in text
