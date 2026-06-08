"""Doc-coverage guard for the memo-review `--rescore-mode` wiring (issue #368).

PR #362 / issue #358 landed `anvil:rubric-rebackport` with the marker-file
dispatch convention: when `--rescore --apply` runs, the tool writes a
placeholder `_meta.json` at `<thread>.{N}.review.rescore-<id>/` carrying
`rescore_state: "scheduled"`. The per-skill reviewer command then learns
a `--rescore-mode <id>` flag that:

1. Re-routes the staged_sidecar output to the rescore sidecar path
   (`<thread>.{N}.review.rescore-<id>/`).
2. Re-targets the prior-review lookup to `<thread>.{N}.review/`
   (NOT `<thread>.{N-1}.review/`) because the legacy review on the same
   version IS the prior review for a rescore pass.
3. Stamps `_meta.json` with `rescore_state: "completed"` + the rescore_id,
   overwriting the tool-written `"scheduled"` placeholder.

This file pins the memo-review.md prose shape so the wiring can't silently
drift.

Per the per-skill test filename convention (#58 — distinct filenames across
skills, ``__init__.py`` chains in every test dir), this file is named
``test_memo_review_rescore_mode_doc.py`` to avoid collision with the other
``test_memo_review_*_doc.py`` files in the same dir.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MEMO_REVIEW_DOC = (
    REPO_ROOT / "anvil" / "skills" / "memo" / "commands" / "memo-review.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_memo_review_doc_references_rescore_mode_flag():
    """The literal `--rescore-mode` token must appear in the command file body.

    This is the marker `anvil:rubric-rebackport`'s `check_rescore_hook(skill)`
    scans for. Its presence asserts the reviewer-hook contract has shipped
    for this skill.
    """
    text = _read(MEMO_REVIEW_DOC)
    assert "--rescore-mode" in text, (
        "memo-review.md must document the `--rescore-mode` flag "
        "(issue #368) — the marker `anvil:rubric-rebackport`'s "
        "`check_rescore_hook('memo')` scans for the literal token."
    )


def test_memo_review_doc_describes_rescore_sidecar_routing():
    """The prose must explicitly name the rescore sidecar path shape."""
    text = _read(MEMO_REVIEW_DOC)
    assert "review.rescore-" in text, (
        "memo-review.md must document re-routing the staged_sidecar "
        "output to the `<thread>.{N}.review.rescore-<id>/` path shape "
        "(issue #368)."
    )


def test_memo_review_doc_describes_rescore_state_completed_stamp():
    """The prose must explicitly state `rescore_state: \"completed\"` is written."""
    text = _read(MEMO_REVIEW_DOC)
    assert "rescore_state" in text and "completed" in text, (
        "memo-review.md must document stamping `rescore_state: "
        "\"completed\"` on `_meta.json` (overwriting the rebackport "
        "tool's `\"scheduled\"` placeholder; issue #368)."
    )


def test_memo_review_doc_describes_prior_rubric_lookup_at_n_not_n_minus_one():
    """The prose must explicitly state that under rescore mode the prior-review
    lookup targets `<thread>.{N}.review/`, not `<thread>.{N-1}.review/`.

    The rescore pass re-scores the SAME version's body against an updated
    rubric — the version's legacy review IS the prior review, so the
    lookup must NOT walk back to N-1.
    """
    text = _read(MEMO_REVIEW_DOC)
    # The prose must explicitly contrast N vs N-1 to make the re-target
    # contract unambiguous.
    assert "N-1" in text or "N - 1" in text, (
        "memo-review.md must explicitly contrast the rescore-mode prior-"
        "review lookup at `<thread>.{N}.review/` against the default-mode "
        "lookup at `<thread>.{N-1}.review/` (issue #368)."
    )
    # And the rescore-mode prose must name the N-targeting branch.
    rescore_block_start = text.find("--rescore-mode")
    assert rescore_block_start != -1
    # Take a slice from the first --rescore-mode mention onward.
    rescore_slice = text[rescore_block_start:]
    assert "<thread>.{N}.review/" in rescore_slice, (
        "memo-review.md's `--rescore-mode` block must explicitly name "
        "the `<thread>.{N}.review/_meta.json` target for the prior-rubric "
        "lookup under rescore mode (issue #368)."
    )


def test_memo_review_doc_references_issue_368():
    """Audit-trail: the issue number must appear in the doc for traceability."""
    text = _read(MEMO_REVIEW_DOC)
    assert "#368" in text, (
        "memo-review.md must reference issue #368 in the `--rescore-mode` "
        "prose block for audit-trail traceability."
    )
