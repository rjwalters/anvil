"""Doc-coverage guard for deck-economics staged-sidecar wiring (issue #350).

Modeled on tests/skills/deck/test_deck_market_sidecar_atomicity_doc.py.
Per issue #551, the new deck-economics critic ships with the canonical
sidecar-atomicity contract (issue #350 / #376) wired into its procedure
prose. These tests pin the load-bearing tokens so a future edit cannot
silently drift the new critic away from the framework atomicity primitive.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "anvil" / "skills" / "deck" / "commands" / "deck-economics.md"


def _read() -> str:
    return DOC.read_text(encoding="utf-8")


def test_deck_economics_doc_references_staged_sidecar_primitive():
    text = _read()
    assert "anvil/lib/sidecar.py" in text
    assert "staged_sidecar" in text


def test_deck_economics_doc_names_required_files_manifest():
    text = _read()
    for name in (
        "_summary.md",
        "findings.md",
        "comments.md",
        "_meta.json",
        "_progress.json",
    ):
        assert name in text, f"required file {name!r} missing from prose"


def test_deck_economics_doc_step_1_invokes_cleanup_sweep():
    text = _read()
    assert "cleanup_one_staging" in text


def test_deck_economics_doc_describes_atomic_rename_contract():
    text = _read()
    assert "atomically" in text.lower() or "atomic" in text.lower()
    assert "leading-dot" in text or ".tmp" in text


def test_deck_economics_doc_references_issue_350():
    text = _read()
    assert "#350" in text
