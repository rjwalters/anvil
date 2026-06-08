"""Doc-coverage guard for pub-audit staged-sidecar wiring (issue #350)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "anvil" / "skills" / "pub" / "commands" / "pub-audit.md"


def _read() -> str:
    return DOC.read_text(encoding="utf-8")


def test_pub_audit_doc_references_staged_sidecar_primitive():
    text = _read()
    assert "anvil/lib/sidecar.py" in text
    assert "staged_sidecar" in text


def test_pub_audit_doc_names_required_files_manifest():
    text = _read()
    for name in (
        "citation-audit.md",
        "numerical-audit.md",
        "flags.md",
        "compile-log.txt",
        "_meta.json",
        "_progress.json",
    ):
        assert name in text, f"required file {name!r} missing from prose"


def test_pub_audit_doc_step_1_invokes_cleanup_sweep():
    text = _read()
    assert "cleanup_stale_staging" in text


def test_pub_audit_doc_describes_atomic_rename_contract():
    text = _read()
    assert "atomically" in text.lower() or "atomic" in text.lower()
    assert "leading-dot" in text or ".tmp" in text


def test_pub_audit_doc_references_issue_350():
    text = _read()
    assert "#350" in text
