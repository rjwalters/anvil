"""Doc-coverage guard for the essay orchestrator's sidecar cross-reference (#655).

`essay.md` is the read-only portfolio orchestrator: it opens NO `staged_sidecar`
block of its own (unlike `essay-review.md`, the doer). Per issue #655 it carries
a short cross-reference to `essay-review`'s full two-tier #645 fallback clause,
mirroring `paper-review.md`'s own Atomicity cross-reference paragraph. This guard
asserts the cross-reference is present (and, defensively, that the doc does not
silently start opening a sidecar without the fallback clause).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "anvil" / "skills" / "essay" / "commands" / "essay.md"


def _read() -> str:
    return DOC.read_text(encoding="utf-8")


def test_essay_doc_cross_references_non_python_driver_fallback():
    text = _read()
    assert "Non-Python-driver ordering" in text
    # It points at the doer doc that carries the full clause.
    assert "essay-review" in text
    assert "python -m anvil.lib.sidecar" in text
    assert "atomicity_fallback" in text or "manual-mv" in text


def test_essay_doc_does_not_open_its_own_staged_sidecar():
    text = _read()
    # The orchestrator is read-only; it must not open a staged_sidecar(...)
    # block. If that ever changes, this doc needs the full tier-1/tier-2 clause
    # and this guard should be replaced accordingly.
    assert "staged_sidecar(" not in text
