"""Tests for the pytest workflow's trigger surface (issue #1525).

``.github/workflows/pytest.yml`` used to carry a path allowlist under
``pull_request``. That filter hid a real regression: PR #1524 changed only
``.github/workflows/version-bump-gate.yml`` — a path outside the allowlist —
so pytest never ran on it, even though
``tests/scripts/test_check_surface_version_bump.py`` asserts on that file's
text and fails on the tree it shipped. Path filtering is an optimisation, not
a correctness tool (.loom/docs/ci-principles.md): a check that cannot run must
never look like one that passed.

The workflow is now unfiltered and also fires on ``merge_group``, making it a
required-grade gate on both PRs and the combined tree a merge queue would
land. These assertions pin that contract so a future edit cannot quietly
reintroduce the filter or drop the merge-group trigger. Distinct file basename
per the #58 cross-skill collision convention.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pytest.yml"


def _workflow_text() -> str:
    assert WORKFLOW.is_file(), f"missing {WORKFLOW}"
    return WORKFLOW.read_text(encoding="utf-8")


def test_pull_request_trigger_has_no_path_filter() -> None:
    """Every PR runs pytest — a path filter is what hid the #1524 regression."""
    text = _workflow_text()
    assert "pull_request:" in text
    assert "paths:" not in text, (
        "a path filter on pull_request hides regressions on filtered paths "
        "(issue #1525)"
    )


def test_merge_group_trigger_is_checks_requested() -> None:
    """The merge queue's combined tree must run the suite (#1525)."""
    text = _workflow_text()
    assert "merge_group:" in text
    assert "types: [checks_requested]" in text


def test_concurrency_never_cancels_a_merge_group_run() -> None:
    """PR runs cancel superseded runs; a started merge-group run is never cancelled."""
    text = _workflow_text()
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text


def test_concurrency_group_is_unique_per_merge_group_commit() -> None:
    """A pending merge-group run must not be superseded by another run."""
    text = _workflow_text()
    assert "github.event.merge_group.head_sha" in text
