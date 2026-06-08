"""Doc-coverage guard for the memo-review staged-sidecar wiring (issue #350).

The Studio canary surfaced 13 partial critic-sibling directories from
mid-cycle interrupts — see issue #350 for the failure landscape. The
pilot-on-memo migration ships in two layers:

1. ``anvil/lib/sidecar.py`` — the framework primitive (``staged_sidecar``
   context manager + ``cleanup_stale_staging`` startup sweep). Covered
   by ``tests/lib/test_sidecar.py``.
2. ``anvil/skills/memo/commands/memo-review.md`` — the per-command
   migration that wires the primitive into the reviewer's procedure.
   This file pins the prose shape so the wiring can't silently drift
   back to a pre-#350 form.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_memo_review_sidecar_atomicity_doc.py`` to avoid collision
with the other ``test_memo_review_*_doc.py`` files in the same dir.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MEMO_REVIEW_DOC = (
    REPO_ROOT / "anvil" / "skills" / "memo" / "commands" / "memo-review.md"
)
PROGRESS_SNIPPET = REPO_ROOT / "anvil" / "lib" / "snippets" / "progress.md"
SIDECAR_LIB = REPO_ROOT / "anvil" / "lib" / "sidecar.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Lib-side guards
# ---------------------------------------------------------------------------


def test_sidecar_lib_module_exists():
    assert SIDECAR_LIB.exists(), (
        "anvil/lib/sidecar.py must exist — the staged-sidecar primitive "
        "issue #350 ships."
    )


def test_sidecar_lib_exposes_required_api():
    """The reference API documented in memo-review.md must exist."""
    from anvil.lib.sidecar import (  # noqa: F401
        STAGING_SUFFIX,
        SidecarIncompleteError,
        cleanup_stale_staging,
        staged_sidecar,
        staging_path_for,
    )


def test_sidecar_reexported_from_anvil_lib_package():
    """The eager re-export contract from ``anvil/lib/__init__.py`` must
    include the sidecar primitives so callers can do ``from anvil.lib
    import staged_sidecar``.
    """
    import anvil.lib

    assert hasattr(anvil.lib, "staged_sidecar")
    assert hasattr(anvil.lib, "cleanup_stale_staging")
    assert hasattr(anvil.lib, "staging_path_for")
    assert hasattr(anvil.lib, "SidecarIncompleteError")


# ---------------------------------------------------------------------------
# memo-review.md prose guards
# ---------------------------------------------------------------------------


def test_memo_review_doc_references_staged_sidecar_primitive():
    """Step 3 (Initialize) must name the staged_sidecar context manager
    from anvil.lib.sidecar.
    """
    text = _read(MEMO_REVIEW_DOC)
    assert "anvil/lib/sidecar.py" in text
    assert "staged_sidecar" in text


def test_memo_review_doc_names_required_files_manifest():
    """The six-file manifest is the load-bearing memo-review contract;
    it must appear verbatim in the staged_sidecar invocation prose.
    """
    text = _read(MEMO_REVIEW_DOC)
    for name in (
        "verdict.md",
        "scoring.md",
        "comments.md",
        "_summary.md",
        "_meta.json",
        "_progress.json",
    ):
        assert name in text, f"required file {name!r} missing from prose"


def test_memo_review_doc_step_1_invokes_cleanup_sweep():
    """The Discover state step MUST invoke cleanup_stale_staging on the
    portfolio root before the resume check fires.
    """
    text = _read(MEMO_REVIEW_DOC)
    assert "cleanup_stale_staging" in text


def test_memo_review_doc_describes_atomic_rename_contract():
    """The Outputs section MUST describe the atomic rename contract —
    final-named dir exists iff complete; staging dir is leading-dot.
    """
    text = _read(MEMO_REVIEW_DOC)
    assert "atomically" in text.lower() or "atomic" in text.lower()
    assert "leading-dot" in text or ".tmp" in text


def test_memo_review_doc_references_issue_350():
    """Audit-trail: the issue number must appear in the doc for traceability."""
    text = _read(MEMO_REVIEW_DOC)
    assert "#350" in text


# ---------------------------------------------------------------------------
# progress.md snippet prose guards
# ---------------------------------------------------------------------------


def test_progress_snippet_documents_critic_sidecar_shape():
    """The Crash recovery contract section must document the sidecar-dir
    shape distinctly from the version-dir shape.
    """
    text = _read(PROGRESS_SNIPPET)
    assert "Critic sidecar dir" in text
    assert "staged_sidecar" in text
    assert "atomic rename" in text.lower()


def test_progress_snippet_distinguishes_version_dir_from_sidecar_dir():
    """The Crash recovery contract section must explicitly distinguish
    the single-canonical-output check (version dir) from the
    staged-rename check (sidecar dir). Both shapes must appear under
    section headings or labeled paragraphs.
    """
    text = _read(PROGRESS_SNIPPET)
    assert "Version dir" in text  # the single-canonical-output check
    assert "single-canonical-output" in text or "single canonical" in text


def test_progress_snippet_references_cleanup_stale_staging():
    """The sweep is the load-bearing operator-facing surface — it must
    be named in the snippet."""
    text = _read(PROGRESS_SNIPPET)
    assert "cleanup_stale_staging" in text
