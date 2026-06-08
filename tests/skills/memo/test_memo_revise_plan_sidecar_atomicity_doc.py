"""Doc-coverage guard for memo-revise plan-sibling staged-sidecar wiring
(issue #350).

Mirrors `test_memo_review_sidecar_atomicity_doc.py` from the memo-review
pilot (PR #354). Only the `--plan`-mode plan-sibling write path is in
scope here — the default-path version-dir output is governed by the
version-dir single-canonical-output crash-recovery contract, NOT the
sidecar contract (curator note on issue #359).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "anvil" / "skills" / "memo" / "commands" / "memo-revise.md"


def _read() -> str:
    return DOC.read_text(encoding="utf-8")


def test_memo_revise_plan_doc_references_staged_sidecar_primitive():
    text = _read()
    assert "anvil/lib/sidecar.py" in text
    assert "staged_sidecar" in text


def test_memo_revise_plan_doc_names_required_files_manifest():
    text = _read()
    for name in ("plan.md", "_meta.json", "_progress.json"):
        assert name in text, f"required file {name!r} missing from prose"


def test_memo_revise_plan_doc_invokes_cleanup_sweep():
    text = _read()
    assert "cleanup_stale_staging" in text


def test_memo_revise_plan_doc_describes_atomic_rename_contract():
    text = _read()
    assert "atomically" in text.lower() or "atomic" in text.lower()
    assert "leading-dot" in text or ".tmp" in text


def test_memo_revise_plan_doc_references_issue_350():
    text = _read()
    assert "#350" in text
