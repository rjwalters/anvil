"""Doc-coverage guard for the memo-review scorecard arithmetic gate (#392).

Issue #392 landed `anvil/lib/scorecard_check.py` (deterministic scorecard
arithmetic validation keyed off the #346 rubric stamps) with memo-review
as the pilot write-time consumer at step 7b:

1. Step 7b invokes `check_scorecard` against the review's own scorecard
   (composing the promoted prose parsers in `anvil/lib/critics.py`) with
   the stamped pool + any artifact-type overlay weight adjustments.
2. Persisting findings force `advance: false` via the existing
   critical-flag pathway (`Scorecard arithmetic (lint)` in verdict.md).
3. The findings land in `_summary.md.scorecard_lint` and a compact
   mirror in `_meta.json.scorecard_lint`.
4. Read-time consumers of immutable legacy sidecars treat a
   finding-bearing verdict as advisory.

This file pins the memo-review.md prose shape so the wiring can't
silently drift.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_memo_review_scorecard_lint_doc.py``.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MEMO_REVIEW_DOC = (
    REPO_ROOT / "anvil" / "skills" / "memo" / "commands" / "memo-review.md"
)
SNIPPET_DOC = (
    REPO_ROOT / "anvil" / "lib" / "snippets" / "scorecard_kind.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_memo_review_doc_has_step_7b_scorecard_gate():
    """Step 7b must exist and name the lib module it invokes."""
    text = _read(MEMO_REVIEW_DOC)
    assert "7b." in text, "memo-review.md must add the step 7b gate (#392)"
    assert "anvil/lib/scorecard_check.py" in text, (
        "memo-review.md step 7b must name the lib module "
        "`anvil/lib/scorecard_check.py` (issue #392)."
    )
    assert "check_scorecard" in text


def test_memo_review_doc_composes_promoted_parsers():
    """Step 7b composes the promoted critics.py prose parsers — it does
    NOT re-implement the scoring-table parse."""
    text = _read(MEMO_REVIEW_DOC)
    assert "parse_memo_scoring_table" in text, (
        "memo-review.md step 7b must compose "
        "`critics.parse_memo_scoring_table` (issue #392 — the curator's "
        "compose-don't-reimplement constraint)."
    )


def test_memo_review_doc_names_the_finding_codes():
    text = _read(MEMO_REVIEW_DOC)
    for code in (
        "weights_sum_mismatch",
        "score_out_of_bounds",
        "total_mismatch",
        "advance_inconsistent",
        "pool_unstamped",
    ):
        assert code in text, (
            f"memo-review.md step 7b must name the `{code}` finding "
            f"code (issue #392)."
        )


def test_memo_review_doc_names_overlay_adjusted_pool():
    """The effective pool is rubric_total + overlay weight_adjustments
    (vision-document validates against 38, not the base 44)."""
    text = _read(MEMO_REVIEW_DOC)
    step_7b = text[text.find("7b.") :]
    assert "weight_adjustments" in step_7b
    assert "38" in step_7b, (
        "memo-review.md step 7b must name the overlay-adjusted pool "
        "example (vision-document -> 38) so the gate is not run against "
        "the base 44 for overlay threads (issue #392)."
    )


def test_memo_review_doc_has_scorecard_arithmetic_critical_flag():
    """Persisting findings force advance: false via the critical-flag
    pathway, named `Scorecard arithmetic (lint)` in verdict.md."""
    text = _read(MEMO_REVIEW_DOC)
    assert "Scorecard arithmetic (lint)" in text, (
        "memo-review.md must list `Scorecard arithmetic (lint)` as the "
        "critical-flag name for persisting step 7b findings (issue #392)."
    )
    assert "advance: false" in text


def test_memo_review_doc_has_summary_scorecard_lint_block():
    """`_summary.md.scorecard_lint` must appear in the step 9 JSON
    example and carry the {ran, findings} shape."""
    text = _read(MEMO_REVIEW_DOC)
    assert '"scorecard_lint"' in text, (
        "memo-review.md step 9 JSON example must include the "
        "`scorecard_lint` block (issue #392)."
    )
    assert "scorecard_lint_block" in text, (
        "memo-review.md step 7b must cache `scorecard_lint_block` for "
        "the step 9 write (issue #392)."
    )


def test_memo_review_doc_has_meta_json_compact_mirror():
    """The compact finding list mirrors into _meta.json.scorecard_lint
    (the canary shape is the documented example)."""
    text = _read(MEMO_REVIEW_DOC)
    assert "_meta.json.scorecard_lint" in text
    assert "weights_sum_mismatch: 48 != 44" in text, (
        "memo-review.md must document the compact canary example "
        "`weights_sum_mismatch: 48 != 44` (issue #392)."
    )


def test_memo_review_doc_documents_read_time_advisory_contract():
    """Read-time consumers must treat finding-bearing sidecars' verdicts
    as advisory — the sidecar is immutable."""
    text = _read(MEMO_REVIEW_DOC)
    step_7b = text[text.find("7b.") :]
    assert "advisory" in step_7b, (
        "memo-review.md step 7b must document the read-time advisory "
        "contract for immutable legacy sidecars (issue #392)."
    )
    assert "check_review_dir" in text


def test_memo_review_doc_references_issue_392():
    text = _read(MEMO_REVIEW_DOC)
    assert "#392" in text, (
        "memo-review.md must reference issue #392 in the step 7b prose "
        "for audit-trail traceability."
    )


def test_scorecard_kind_snippet_names_the_validation_consumer():
    """The #346 stamps snippet must record that the stamps are now
    consumed by arithmetic validation."""
    text = _read(SNIPPET_DOC)
    assert "scorecard_check" in text, (
        "anvil/lib/snippets/scorecard_kind.md must note that the "
        "rubric_total / advance_threshold stamps are consumed by "
        "`anvil/lib/scorecard_check.py` (issue #392)."
    )
    assert "#392" in text
