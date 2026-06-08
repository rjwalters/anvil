"""Doc-coverage guard for ip-uspto-finalize staged-sidecar wiring
(issue #350).

ip-uspto-finalize is the terminal `<thread>.final/` package writer — load
bearing per the curator's note: a partial submission package could
otherwise ship to a human attorney. The staged_sidecar atomic rename
guarantees the final-named dir only ever exists when the full submission
package is complete.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = (
    REPO_ROOT
    / "anvil"
    / "skills"
    / "ip-uspto"
    / "commands"
    / "ip-uspto-finalize.md"
)


def _read() -> str:
    return DOC.read_text(encoding="utf-8")


def test_ip_uspto_finalize_doc_references_staged_sidecar_primitive():
    text = _read()
    assert "anvil/lib/sidecar.py" in text
    assert "staged_sidecar" in text


def test_ip_uspto_finalize_doc_names_required_files_manifest():
    text = _read()
    for name in (
        "spec.pdf",
        "drawings.pdf",
        "abstract.txt",
        "claims.tex",
        "ads-placeholder.txt",
        "fee-sheet-placeholder.txt",
        "inventorship-attestation.md",
        "README.md",
        "_manifest.json",
        "_progress.json",
    ):
        assert name in text, f"required file {name!r} missing from prose"


def test_ip_uspto_finalize_doc_invokes_cleanup_sweep():
    text = _read()
    assert "cleanup_stale_staging" in text


def test_ip_uspto_finalize_doc_describes_atomic_rename_contract():
    text = _read()
    assert "atomically" in text.lower() or "atomic" in text.lower()
    assert "leading-dot" in text or ".tmp" in text


def test_ip_uspto_finalize_doc_references_issue_350():
    text = _read()
    assert "#350" in text
