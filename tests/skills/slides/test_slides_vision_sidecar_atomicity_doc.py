"""Doc-coverage guard for slides-vision staged-sidecar wiring (issue #350)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = (
    REPO_ROOT / "anvil" / "skills" / "slides" / "commands" / "slides-vision.md"
)


def _read() -> str:
    return DOC.read_text(encoding="utf-8")


def test_slides_vision_doc_references_staged_sidecar_primitive():
    text = _read()
    assert "anvil/lib/sidecar.py" in text
    assert "staged_sidecar" in text


def test_slides_vision_doc_names_required_files_manifest():
    text = _read()
    for name in ("_review.json", "_meta.json", "_progress.json"):
        assert name in text, f"required file {name!r} missing from prose"


def test_slides_vision_doc_step_1_invokes_cleanup_sweep():
    text = _read()
    assert "cleanup_one_staging" in text


def test_slides_vision_doc_describes_atomic_rename_contract():
    text = _read()
    assert "atomically" in text.lower() or "atomic" in text.lower()
    assert "leading-dot" in text or ".tmp" in text


def test_slides_vision_doc_references_issue_350():
    text = _read()
    assert "#350" in text


def test_slides_vision_doc_documents_non_python_driver_fallback():
    """Guard the #645 two-tier non-Python-driver fallback clause (#655).

    Every critic-writing doc that mandates `staged_sidecar` must also document
    the fail-open manual fallback: tier 1 = the `python -m anvil.lib.sidecar`
    CLI shim; tier 2 = the manual `mv`-based staging with a durable
    `atomicity_fallback: manual-mv` stamp.
    """
    text = _read()
    assert "Non-Python-driver ordering" in text
    assert "python -m anvil.lib.sidecar" in text
    assert "manual" in text.lower() and ("mv" in text or "`mv`" in text)
    assert "atomicity_fallback" in text or "manual-mv" in text
