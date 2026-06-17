"""Behavioral two-critic fan-out regression guard (issue #593 / #376).

This module pins the parallel-safety contract that issue #376 (rediscovered
independently by issue #593's fresh canary repro) established for the
per-critic staging-cleanup sweep in :mod:`anvil.lib.sidecar`.

The canary repro that motivated this guard (2AM Logic Studio): a
``proposal-review`` and a ``proposal-audit`` were fanned out **concurrently
on the same version dir** (``internal-dc-program.3``). The auditor, following
its entry-step instruction *literally*, called the portfolio-wide
``cleanup_stale_staging(<portfolio_root>)`` — which removed a live
``.internal-dc-program.3.review.tmp/`` staging dir belonging to the
concurrent reviewer. Under that timing the swept dir happened to be a
post-rename orphan, but under slightly different timing the sweep silently
destroys a concurrent critic's in-flight output.

The fix (PR #381) was to migrate every per-critic entry step from the
portfolio-wide ``cleanup_stale_staging`` to the per-critic, parallel-safe
``cleanup_one_staging(final_dir)``. The residual gap closed here is the
**behavioral regression guard**: a test that exercises the real
``sidecar.py`` functions in a two-critic fan-out and proves that:

1. ``cleanup_one_staging`` is parallel-safe — a critic's entry-step sweep
   removes only its OWN staging dir and never touches a sibling critic's
   in-flight staging dir, even when both critics are mid-write under the
   same version dir.
2. ``cleanup_stale_staging`` is NOT parallel-safe — it sweeps EVERY
   ``.tmp/`` staging dir under the portfolio root, including a sibling
   critic's in-flight staging dir. This is the documented operator-only
   contract and the precise behavior that caused the canary repro; we pin
   it as a negative control so a future "simplification" that points a
   per-critic entry step back at the portfolio-wide sweep is caught.

This complements the lower-level discrimination tests in
``tests/lib/test_sidecar.py`` by reproducing the specific
review+audit-on-the-same-version-dir scenario from the #593 repro and by
making the unsafe-vs-safe contrast explicit and self-documenting.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import List, Tuple

from anvil.lib.sidecar import (
    cleanup_one_staging,
    cleanup_stale_staging,
    staged_sidecar,
    staging_path_for,
)


# The canary repro's exact shape: a review critic and an audit critic fanned
# out on the SAME version dir. Each writes a distinct critic sibling.
VERSION_DIR_NAME = "internal-dc-program.3"
REVIEW_TAG = "review"
AUDIT_TAG = "audit"

# A minimal two-file manifest is sufficient to exercise the stage→rename
# lifecycle; the manifest content is not what this guard is about.
MANIFEST = ("verdict.md", "scoring.md")


def _final_dir(portfolio: Path, tag: str) -> Path:
    return portfolio / f"{VERSION_DIR_NAME}.{tag}"


# ---------------------------------------------------------------------------
# cleanup_one_staging — the parallel-safe per-critic entry-step sweep
# ---------------------------------------------------------------------------


def test_cleanup_one_staging_entry_sweep_spares_concurrent_critic(tmp_path):
    """Reproduce the #593 canary scenario with the SAFE primitive.

    A reviewer is mid-write (its staging dir exists with partial content)
    when an auditor fans out on the same version dir and runs its entry-step
    sweep. With ``cleanup_one_staging`` the auditor's sweep is bounded to its
    OWN staging path — the reviewer's in-flight staging dir survives intact.
    """
    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()

    review_final = _final_dir(portfolio, REVIEW_TAG)
    audit_final = _final_dir(portfolio, AUDIT_TAG)

    # Reviewer is mid-write: its staging dir exists with partial output.
    review_staging = staging_path_for(review_final)
    review_staging.mkdir()
    (review_staging / "verdict.md").write_text("reviewer verdict, in flight")

    # Auditor's entry-step sweep targets only the auditor's own final_dir.
    swept = cleanup_one_staging(audit_final)

    # No auditor staging dir existed yet, so nothing was swept — and,
    # critically, the reviewer's in-flight staging dir is untouched.
    assert swept is False
    assert review_staging.exists()
    assert (review_staging / "verdict.md").read_text() == (
        "reviewer verdict, in flight"
    )


def test_two_critics_fan_out_on_same_version_dir_land_intact(tmp_path):
    """Full behavioral fan-out: a review critic and an audit critic run the
    real ``cleanup_one_staging`` entry sweep + ``staged_sidecar`` lifecycle
    concurrently on the SAME version dir. Both critics' final sidecars must
    land intact, and neither entry sweep may disturb the other's in-flight
    staging dir.

    Each critic is pre-seeded with a stale staging dir from a hypothetical
    prior crash; each critic's own entry sweep must remove ITS stale dir
    while leaving the sibling's (in-flight) staging dir alone.
    """
    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()

    critics: Tuple[str, ...] = (REVIEW_TAG, AUDIT_TAG)
    final_dirs = {tag: _final_dir(portfolio, tag) for tag in critics}

    # Pre-seed a stale staging dir per critic (simulating a prior interrupt).
    for tag in critics:
        staging = staging_path_for(final_dirs[tag])
        staging.mkdir()
        (staging / "stale-from-prior-crash.md").write_text("stale")

    enter_barrier = threading.Barrier(len(critics))
    mid_write_barrier = threading.Barrier(len(critics))
    errors: List[Tuple[str, str]] = []

    def run(tag: str) -> None:
        final_dir = final_dirs[tag]
        try:
            # Interleave the entry-step sweeps to maximize the race window.
            enter_barrier.wait(timeout=5)
            cleanup_one_staging(final_dir)
            with staged_sidecar(final_dir, required_files=MANIFEST) as staging:
                # Our own stale dir was swept; we are writing fresh.
                assert not (staging / "stale-from-prior-crash.md").exists()
                (staging / "verdict.md").write_text(f"verdict::{tag}")
                # Hold both critics inside their staging dirs at once so a
                # sibling-sweeping entry step (the #376 bug) would strike.
                mid_write_barrier.wait(timeout=5)
                (staging / "scoring.md").write_text(f"scoring::{tag}")
        except Exception as exc:  # pragma: no cover - only on regression
            errors.append((tag, f"{type(exc).__name__}: {exc}"))

    threads = [threading.Thread(target=run, args=(tag,)) for tag in critics]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors == [], f"Concurrent critics disturbed each other: {errors}"
    for tag in critics:
        final_dir = final_dirs[tag]
        assert final_dir.exists(), f"{tag} final dir missing — race struck"
        assert (final_dir / "verdict.md").read_text() == f"verdict::{tag}"
        assert (final_dir / "scoring.md").read_text() == f"scoring::{tag}"
        # The staging dir was atomically renamed away; nothing lingers.
        assert not staging_path_for(final_dir).exists()


# ---------------------------------------------------------------------------
# cleanup_stale_staging — the operator-only portfolio-wide sweep (NEGATIVE
# control: documents WHY it is not parallel-safe)
# ---------------------------------------------------------------------------


def test_cleanup_stale_staging_sweeps_concurrent_critic_negative_control(
    tmp_path,
):
    """Negative control pinning the documented unsafe behavior of the
    operator-only ``cleanup_stale_staging`` portfolio-wide sweep.

    This is the EXACT failure mode from the #593 canary repro: an auditor
    that (incorrectly) runs the portfolio-wide sweep at its entry step
    ``rmtree``\\ s the concurrent reviewer's in-flight staging dir. We assert
    that behavior here so that the contract — "per-critic entry steps MUST
    use cleanup_one_staging, never cleanup_stale_staging" — is pinned by a
    test, not just by prose. If a future change makes the portfolio-wide
    sweep accidentally parallel-safe, this control fires and the author must
    re-examine the whole contract.
    """
    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()

    review_staging = staging_path_for(_final_dir(portfolio, REVIEW_TAG))
    audit_staging = staging_path_for(_final_dir(portfolio, AUDIT_TAG))
    review_staging.mkdir()
    (review_staging / "verdict.md").write_text("reviewer verdict, in flight")
    audit_staging.mkdir()
    (audit_staging / "verdict.md").write_text("auditor verdict, in flight")

    # The auditor (wrongly) runs the portfolio-wide sweep at its entry step.
    removed = cleanup_stale_staging(portfolio)

    # It swept BOTH staging dirs — including the reviewer's in-flight one.
    removed_names = sorted(p.name for p in removed)
    assert removed_names == [
        f".{VERSION_DIR_NAME}.{AUDIT_TAG}.tmp",
        f".{VERSION_DIR_NAME}.{REVIEW_TAG}.tmp",
    ]
    # The concurrent reviewer's in-flight staging dir was destroyed — the
    # data-loss the per-critic sweep exists to prevent.
    assert not review_staging.exists()
    assert not audit_staging.exists()
