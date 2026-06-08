"""Doc-coverage guard for the ip-uspto-review `--rescore-mode` wiring (issue #368).

PR #362 / issue #358 landed `anvil:rubric-rebackport` with the marker-file
dispatch convention. The per-skill reviewer command learns a
`--rescore-mode <id>` flag that:

1. Re-routes the staged_sidecar output to the rescore sidecar path
   (`<thread>.{N}.review.rescore-<id>/`).
2. Re-targets the prior-review lookup to `<thread>.{N}.review/`
   (NOT `<thread>.{N-1}.review/`).
3. Stamps `_meta.json` with `rescore_state: "completed"` + the rescore_id.

ip-uspto is the only skill in the suite that emits
`scorecard_kind: "machine-summary"` (not `"human-verdict"`) and the only
one with a /45 rubric total (vs /44 for the other seven). The
`scorecard_kind` discriminator is independent of rescore-mode re-routing
per `anvil/lib/snippets/scorecard_kind.md`'s discriminator contract.

Per the per-skill test filename convention (#58), this file is named
``test_ip_uspto_review_rescore_mode_doc.py`` to avoid collision.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
IP_USPTO_REVIEW_DOC = (
    REPO_ROOT
    / "anvil"
    / "skills"
    / "ip-uspto"
    / "commands"
    / "ip-uspto-review.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ip_uspto_review_doc_references_rescore_mode_flag():
    """The literal `--rescore-mode` token must appear in the command file body."""
    text = _read(IP_USPTO_REVIEW_DOC)
    assert "--rescore-mode" in text, (
        "ip-uspto-review.md must document the `--rescore-mode` flag "
        "(issue #368) — the marker `anvil:rubric-rebackport`'s "
        "`check_rescore_hook('ip-uspto')` scans for the literal token."
    )


def test_ip_uspto_review_doc_describes_rescore_sidecar_routing():
    """The prose must explicitly name the rescore sidecar path shape."""
    text = _read(IP_USPTO_REVIEW_DOC)
    assert "review.rescore-" in text, (
        "ip-uspto-review.md must document re-routing the staged_sidecar "
        "output to the `<thread>.{N}.review.rescore-<id>/` path shape "
        "(issue #368)."
    )


def test_ip_uspto_review_doc_describes_rescore_state_completed_stamp():
    """The prose must explicitly state `rescore_state: \"completed\"` is written."""
    text = _read(IP_USPTO_REVIEW_DOC)
    assert "rescore_state" in text and "completed" in text, (
        "ip-uspto-review.md must document stamping `rescore_state: "
        "\"completed\"` on `_meta.json` (overwriting the rebackport "
        "tool's `\"scheduled\"` placeholder; issue #368)."
    )


def test_ip_uspto_review_doc_describes_prior_rubric_lookup_at_n_not_n_minus_one():
    """The prose must explicitly state that under rescore mode the prior-review
    lookup targets `<thread>.{N}.review/`, not `<thread>.{N-1}.review/`.
    """
    text = _read(IP_USPTO_REVIEW_DOC)
    assert "N-1" in text or "N - 1" in text, (
        "ip-uspto-review.md must explicitly contrast the rescore-mode "
        "prior-review lookup at `<thread>.{N}.review/` against the "
        "default-mode lookup at `<thread>.{N-1}.review/` (issue #368)."
    )
    rescore_block_start = text.find("--rescore-mode")
    assert rescore_block_start != -1
    rescore_slice = text[rescore_block_start:]
    assert "<thread>.{N}.review/" in rescore_slice, (
        "ip-uspto-review.md's `--rescore-mode` block must explicitly name "
        "the `<thread>.{N}.review/_meta.json` target for the prior-rubric "
        "lookup under rescore mode (issue #368)."
    )


def test_ip_uspto_review_doc_references_issue_368():
    """Audit-trail: the issue number must appear in the doc for traceability."""
    text = _read(IP_USPTO_REVIEW_DOC)
    assert "#368" in text, (
        "ip-uspto-review.md must reference issue #368 in the "
        "`--rescore-mode` prose block for audit-trail traceability."
    )
