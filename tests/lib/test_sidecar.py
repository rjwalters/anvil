"""Tests for ``anvil.lib.sidecar`` (issue #350).

Coverage:

- **Happy path** — ``staged_sidecar`` writes all required files into
  the staging dir, then atomically renames to the final dir.
- **Missing required file** — clean context exit with a required file
  missing raises :class:`SidecarIncompleteError` and leaves the staging
  dir in place.
- **Exception in body** — exception in the ``with`` block propagates and
  leaves the staging dir in place (no rename).
- **Pre-existing final dir** — :class:`FileExistsError` on entry; we
  refuse to stage over an existing target.
- **Pre-existing staging dir** — a leftover staging dir from a prior
  interrupt is removed before we re-enter (forward-progress contract).
- **cleanup_stale_staging** — removes leading-dot ``*.tmp/`` dirs;
  leaves non-staging siblings alone (final-named critic dirs, hidden
  non-tmp dirs like ``.git/``).
- **Discovery isolation** — ``discover_critics`` does not match a
  leading-dot staging dir, even when it carries a valid
  ``_review.json``.
- **Canary-replay** — synthesize the 13 partial-sidecar shapes (one
  through six of the six required files present, with random subsets)
  and verify ``discover_critics`` finds zero of them (because the final
  name was never created), and the next ``cleanup_stale_staging`` call
  removes all of them.
"""

from __future__ import annotations

import itertools
import json
import logging
import shutil
from pathlib import Path

import pytest

from anvil.lib.critics import CANONICAL_REVIEW_FILENAME, discover_critics
from anvil.lib.review_schema import Kind, Review, Score
from anvil.lib.sidecar import (
    STAGING_SUFFIX,
    SidecarCopyVerificationError,
    SidecarIncompleteError,
    abort_replace,
    backup_path_for,
    cleanup_one_staging,
    cleanup_stale_staging,
    commit_replace,
    commit_staged,
    copy_bytes,
    main,
    recover_interrupted_replace,
    stage_enter,
    stage_replace,
    staged_sidecar,
    staging_path_for,
    write_critic_review_dir,
)


# Memo-shaped six-file sidecar manifest (the canonical post-Wave-1 memo
# review sibling shape: verdict.md + scoring.md + comments.md + _summary.md
# + _meta.json + _progress.json).
MEMO_REVIEW_REQUIRED = (
    "verdict.md",
    "scoring.md",
    "comments.md",
    "_summary.md",
    "_meta.json",
    "_progress.json",
)


def _write_all(staging: Path, names) -> None:
    """Write a non-empty placeholder to each given basename in ``staging``."""
    for name in names:
        (staging / name).write_text(f"placeholder for {name}\n")


# ---------------------------------------------------------------------------
# staging_path_for
# ---------------------------------------------------------------------------


def test_staging_path_for_sibling_of_final(tmp_path):
    final_dir = tmp_path / "acme-seed.3.review"
    staging = staging_path_for(final_dir)
    assert staging.parent == final_dir.parent
    assert staging.name == ".acme-seed.3.review.tmp"


def test_staging_path_for_pure_function(tmp_path):
    """staging_path_for never touches the filesystem."""
    final_dir = tmp_path / "does-not-exist.7.review"
    staging = staging_path_for(final_dir)
    # Verify we got a path back without anything being created.
    assert not staging.exists()
    assert not final_dir.exists()


# ---------------------------------------------------------------------------
# staged_sidecar happy path
# ---------------------------------------------------------------------------


def test_staged_sidecar_happy_path_renames_on_clean_exit(tmp_path):
    final = tmp_path / "acme-seed.3.review"

    with staged_sidecar(final, required_files=MEMO_REVIEW_REQUIRED) as staging:
        # Staging dir exists with the .tmp leading-dot shape.
        assert staging.exists()
        assert staging.name.startswith(".")
        assert staging.name.endswith(STAGING_SUFFIX)
        # Final dir does NOT exist yet.
        assert not final.exists()
        _write_all(staging, MEMO_REVIEW_REQUIRED)

    # After context exit: final dir exists, staging dir is gone.
    assert final.exists()
    assert final.is_dir()
    assert not staging.exists()
    for name in MEMO_REVIEW_REQUIRED:
        assert (final / name).read_text() == f"placeholder for {name}\n"


def test_staged_sidecar_creates_intermediate_parents(tmp_path):
    """The default ``parents=True`` creates intermediate dirs."""
    final = tmp_path / "deeply" / "nested" / "thread.1.review"
    with staged_sidecar(final, required_files=("verdict.md",)) as staging:
        (staging / "verdict.md").write_text("ok")
    assert final.exists()
    assert (final / "verdict.md").read_text() == "ok"


# ---------------------------------------------------------------------------
# Missing-required-file branch
# ---------------------------------------------------------------------------


def test_staged_sidecar_missing_required_raises_and_preserves_staging(
    tmp_path,
):
    final = tmp_path / "acme-seed.3.review"

    with pytest.raises(SidecarIncompleteError) as excinfo:
        with staged_sidecar(
            final, required_files=MEMO_REVIEW_REQUIRED
        ) as staging:
            # Write only three of the six required files.
            _write_all(staging, ["verdict.md", "scoring.md", "comments.md"])

    # The final dir was NOT created (no rename).
    assert not final.exists()
    # The staging dir IS still present, with the three files we wrote.
    staging_dir = staging_path_for(final)
    assert staging_dir.exists()
    assert (staging_dir / "verdict.md").exists()
    assert (staging_dir / "scoring.md").exists()
    assert (staging_dir / "comments.md").exists()
    assert not (staging_dir / "_summary.md").exists()

    # Error message names the missing files.
    msg = str(excinfo.value)
    assert "_summary.md" in msg
    assert "_meta.json" in msg
    assert "_progress.json" in msg


def test_staged_sidecar_missing_only_progress_json(tmp_path):
    """The studio canary's canonical failure shape: five of six present,
    only _progress.json missing (because it is written last).
    """
    final = tmp_path / "citation-clear.4.review"

    five_of_six = [n for n in MEMO_REVIEW_REQUIRED if n != "_progress.json"]
    with pytest.raises(SidecarIncompleteError) as excinfo:
        with staged_sidecar(
            final, required_files=MEMO_REVIEW_REQUIRED
        ) as staging:
            _write_all(staging, five_of_six)

    assert not final.exists()
    assert staging_path_for(final).exists()
    assert "_progress.json" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Exception in body
# ---------------------------------------------------------------------------


def test_staged_sidecar_exception_in_body_no_rename(tmp_path):
    final = tmp_path / "acme-seed.3.review"

    class _SimulatedLLMError(RuntimeError):
        pass

    with pytest.raises(_SimulatedLLMError):
        with staged_sidecar(
            final, required_files=MEMO_REVIEW_REQUIRED
        ) as staging:
            (staging / "verdict.md").write_text("partial work")
            raise _SimulatedLLMError("simulated mid-write LLM crash")

    # Staging dir is preserved with the partial work.
    assert not final.exists()
    staging_dir = staging_path_for(final)
    assert staging_dir.exists()
    assert (staging_dir / "verdict.md").read_text() == "partial work"


# ---------------------------------------------------------------------------
# Pre-existing final or staging dirs
# ---------------------------------------------------------------------------


def test_staged_sidecar_refuses_if_final_exists(tmp_path):
    final = tmp_path / "acme-seed.3.review"
    final.mkdir()

    with pytest.raises(FileExistsError) as excinfo:
        with staged_sidecar(final, required_files=("verdict.md",)) as _staging:
            # Should not reach the body.
            raise AssertionError("entered context manager despite final exists")

    assert "already exists" in str(excinfo.value)


def test_staged_sidecar_clears_prior_staging_dir(tmp_path):
    """A leftover staging dir from a prior crashed attempt is removed on
    re-entry so we can make forward progress.
    """
    final = tmp_path / "acme-seed.3.review"
    staging = staging_path_for(final)
    staging.mkdir(parents=True)
    (staging / "leftover-from-prior-crash.md").write_text("stale")

    with staged_sidecar(
        final, required_files=("verdict.md",)
    ) as new_staging:
        # The leftover file must be gone — staging dir was wiped.
        assert not (new_staging / "leftover-from-prior-crash.md").exists()
        (new_staging / "verdict.md").write_text("fresh write")

    assert final.exists()
    assert (final / "verdict.md").read_text() == "fresh write"
    assert not (final / "leftover-from-prior-crash.md").exists()


# ---------------------------------------------------------------------------
# cleanup_stale_staging
# ---------------------------------------------------------------------------


def test_cleanup_stale_staging_removes_leading_dot_tmp_dirs(tmp_path):
    # Synthesize three leftover staging dirs and two unrelated dirs.
    for slug in ("acme-seed.3.review", "meridian.7.audit", "foo.1.narrative"):
        d = tmp_path / f".{slug}.tmp"
        d.mkdir()
        (d / "partial.md").write_text("partial work")
    # An unrelated final-named critic dir (must NOT be removed).
    (tmp_path / "acme-seed.3.review").mkdir()
    (tmp_path / "acme-seed.3.review" / "verdict.md").write_text("ok")
    # An unrelated hidden non-tmp dir (e.g., .git).
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main")
    # A non-staging plain file.
    (tmp_path / "README.md").write_text("portfolio readme")

    removed = cleanup_stale_staging(tmp_path)

    names = sorted(p.name for p in removed)
    # Alphabetical, because `names` is sorted() above — not the order the
    # dirs were created in.
    assert names == [
        ".acme-seed.3.review.tmp",
        ".foo.1.narrative.tmp",
        ".meridian.7.audit.tmp",
    ]
    # The final-named critic dir is preserved.
    assert (tmp_path / "acme-seed.3.review").exists()
    assert (tmp_path / "acme-seed.3.review" / "verdict.md").exists()
    # The .git dir is preserved (hidden but does not end in .tmp).
    assert (tmp_path / ".git").exists()
    assert (tmp_path / ".git" / "HEAD").exists()
    # Plain file is preserved.
    assert (tmp_path / "README.md").exists()


def test_cleanup_stale_staging_idempotent(tmp_path):
    (tmp_path / ".thread.1.review.tmp").mkdir()
    first = cleanup_stale_staging(tmp_path)
    second = cleanup_stale_staging(tmp_path)
    assert len(first) == 1
    assert second == []


def test_cleanup_stale_staging_safe_on_nonexistent_parent(tmp_path):
    nonexistent = tmp_path / "no-such-portfolio"
    assert cleanup_stale_staging(nonexistent) == []


def test_cleanup_stale_staging_safe_on_file_parent(tmp_path):
    fake_parent = tmp_path / "i-am-a-file"
    fake_parent.write_text("not a directory")
    assert cleanup_stale_staging(fake_parent) == []


def test_cleanup_stale_staging_skips_files_with_matching_shape(tmp_path):
    """A file (not a dir) whose name looks like a staging name is left alone.
    cleanup is dir-scoped — we never delete files.
    """
    (tmp_path / ".something.tmp").write_text("but it is a file")
    removed = cleanup_stale_staging(tmp_path)
    assert removed == []
    assert (tmp_path / ".something.tmp").exists()


def test_cleanup_stale_staging_skips_bare_dot_tmp(tmp_path):
    """A directory literally named ``.tmp`` (no body between dot and
    suffix) is conservatively left alone.
    """
    (tmp_path / ".tmp").mkdir()
    removed = cleanup_stale_staging(tmp_path)
    assert removed == []
    assert (tmp_path / ".tmp").exists()


def test_cleanup_stale_staging_logs_at_info(tmp_path, caplog):
    (tmp_path / ".thread.1.review.tmp").mkdir()
    (tmp_path / ".thread.1.audit.tmp").mkdir()
    with caplog.at_level(logging.INFO, logger="anvil.lib.sidecar"):
        removed = cleanup_stale_staging(tmp_path)
    assert len(removed) == 2
    # Find the single summary log line.
    sweep_records = [
        r for r in caplog.records if "cleanup_stale_staging" in r.message
    ]
    assert len(sweep_records) == 1
    assert ".thread.1.review.tmp" in sweep_records[0].message
    assert ".thread.1.audit.tmp" in sweep_records[0].message


# ---------------------------------------------------------------------------
# cleanup_one_staging — per-critic entry-step sweep (issue #376)
# ---------------------------------------------------------------------------


def test_cleanup_one_staging_targets_only_named_staging_path(tmp_path):
    """The narrowed sweep removes ONLY the staging path corresponding to
    the given ``final_dir``; sibling staging dirs under the same parent
    are preserved (issue #376 parallel-safety contract).
    """
    portfolio = tmp_path / "p"
    portfolio.mkdir()
    a_staging = portfolio / ".thread.4.perspective.tmp"
    b_staging = portfolio / ".thread.4.hyperlinks.tmp"
    a_staging.mkdir()
    (a_staging / "marker").write_text("A")
    b_staging.mkdir()
    (b_staging / "marker").write_text("B")

    removed = cleanup_one_staging(portfolio / "thread.4.perspective")

    assert removed is True
    assert not a_staging.exists()
    # Sibling staging dir is preserved — the parallel-safety guarantee.
    assert b_staging.exists()
    assert (b_staging / "marker").read_text() == "B"


def test_cleanup_one_staging_noop_when_staging_missing(tmp_path):
    """No staging dir present → returns False, no-op."""
    portfolio = tmp_path / "p"
    portfolio.mkdir()
    removed = cleanup_one_staging(portfolio / "thread.4.review")
    assert removed is False


def test_cleanup_one_staging_idempotent(tmp_path):
    """Second call returns False because the first removed the target."""
    portfolio = tmp_path / "p"
    portfolio.mkdir()
    staging = portfolio / ".thread.4.review.tmp"
    staging.mkdir()

    first = cleanup_one_staging(portfolio / "thread.4.review")
    second = cleanup_one_staging(portfolio / "thread.4.review")
    assert first is True
    assert second is False
    assert not staging.exists()


def test_cleanup_one_staging_safe_when_parent_missing(tmp_path):
    """A non-existent parent directory yields a False no-op."""
    final = tmp_path / "no-such-portfolio" / "thread.4.review"
    removed = cleanup_one_staging(final)
    assert removed is False


def test_cleanup_one_staging_does_not_touch_final_dir(tmp_path):
    """The final dir is never touched — only the staging path is swept."""
    portfolio = tmp_path / "p"
    portfolio.mkdir()
    final = portfolio / "thread.4.review"
    final.mkdir()
    (final / "verdict.md").write_text("complete review")

    removed = cleanup_one_staging(final)

    assert removed is False
    assert final.exists()
    assert (final / "verdict.md").read_text() == "complete review"


def test_cleanup_one_staging_skips_file_with_staging_shape(tmp_path):
    """If the staging path is a file (not a dir), it is left alone."""
    portfolio = tmp_path / "p"
    portfolio.mkdir()
    fake = portfolio / ".thread.4.review.tmp"
    fake.write_text("but I am a file")

    removed = cleanup_one_staging(portfolio / "thread.4.review")

    assert removed is False
    assert fake.exists()
    assert fake.read_text() == "but I am a file"


def test_cleanup_one_staging_logs_at_info(tmp_path, caplog):
    """A successful removal logs at INFO level."""
    portfolio = tmp_path / "p"
    portfolio.mkdir()
    (portfolio / ".thread.4.review.tmp").mkdir()

    with caplog.at_level(logging.INFO, logger="anvil.lib.sidecar"):
        removed = cleanup_one_staging(portfolio / "thread.4.review")

    assert removed is True
    records = [r for r in caplog.records if "cleanup_one_staging" in r.message]
    assert len(records) == 1
    assert ".thread.4.review.tmp" in records[0].message


# ---------------------------------------------------------------------------
# Parallel-fan-out regression (issue #376)
# ---------------------------------------------------------------------------


def test_parallel_staged_sidecars_do_not_disturb_each_other(tmp_path):
    """The race window from issue #376: spawn N staged_sidecar context
    managers concurrently under the SAME portfolio root with DISTINCT
    ``final_dir`` values. Each entry uses ``cleanup_one_staging`` (the
    parallel-safe per-critic sweep). All threads should hold their
    staging dirs open simultaneously, then rename to their final dirs
    without disturbing each other's staging dirs.

    Pre-issue-#376 code paths used ``cleanup_stale_staging(parent)`` at
    entry, which would have nuked sibling critics' in-flight staging
    dirs — this test would have surfaced the race. The new contract
    bounds each entry sweep to its own staging path.
    """
    import threading

    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()

    names = ("perspective", "hyperlinks", "citations", "image-accessibility")
    final_dirs = [portfolio / f"thread.4.{n}" for n in names]

    # Pre-seed one stale staging dir per critic to verify each
    # entry-step sweep removes ITS OWN stale staging dir without
    # touching siblings.
    for fd in final_dirs:
        staging = staging_path_for(fd)
        staging.mkdir()
        (staging / "stale-leftover.md").write_text("from a prior crash")

    barrier = threading.Barrier(len(names))
    mid_barrier = threading.Barrier(len(names))
    errors: List[tuple] = []

    def run(final_dir: Path, name: str) -> None:
        try:
            # Maximize interleaving of entry sweeps.
            barrier.wait(timeout=5)
            cleanup_one_staging(final_dir)
            with staged_sidecar(
                final_dir, required_files=("verdict.md", "scoring.md")
            ) as staging:
                # Verify the stale leftover is gone — our own sweep
                # removed it.
                assert not (staging / "stale-leftover.md").exists()
                (staging / "verdict.md").write_text(f"verdict for {name}")
                # Hold all critics inside their staging dirs
                # simultaneously to maximize the race window.
                mid_barrier.wait(timeout=5)
                (staging / "scoring.md").write_text(f"scoring for {name}")
        except Exception as e:  # pragma: no cover — only on regression
            errors.append((name, type(e).__name__, str(e)))

    threads = [
        threading.Thread(target=run, args=(fd, n))
        for fd, n in zip(final_dirs, names)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors == [], f"Parallel critics disturbed each other: {errors}"
    for fd, name in zip(final_dirs, names):
        assert fd.exists(), f"Final dir {fd} missing — race window struck"
        assert (fd / "verdict.md").read_text() == f"verdict for {name}"
        assert (fd / "scoring.md").read_text() == f"scoring for {name}"
        # The pre-seeded stale-leftover.md is gone (sweep removed it).
        assert not (fd / "stale-leftover.md").exists()


def test_cleanup_stale_staging_would_disturb_parallel_critics(tmp_path):
    """Counter-example: the operator-facing ``cleanup_stale_staging``
    sweeps ALL ``.tmp/`` dirs under the parent — pinning the
    documented unsafe-for-per-critic-entry contract from issue #376.

    This test confirms that the legacy primitive's behavior is unchanged
    (backwards-compatible) AND that its scope is portfolio-wide — which
    is why a parallel fan-out workflow MUST use ``cleanup_one_staging``
    instead.
    """
    portfolio = tmp_path / "p"
    portfolio.mkdir()
    a = portfolio / ".thread.4.perspective.tmp"
    b = portfolio / ".thread.4.hyperlinks.tmp"
    a.mkdir()
    b.mkdir()

    removed = cleanup_stale_staging(portfolio)

    # The legacy sweep removed BOTH — demonstrating why it is unsafe
    # to call from a per-critic entry step in a parallel workflow.
    assert sorted(p.name for p in removed) == [
        ".thread.4.hyperlinks.tmp",
        ".thread.4.perspective.tmp",
    ]
    assert not a.exists()
    assert not b.exists()


# ---------------------------------------------------------------------------
# Discovery isolation
# ---------------------------------------------------------------------------


def test_discover_critics_does_not_match_staging_dirs(tmp_path):
    """A staging dir at ``.<slug>.{N}.<tag>.tmp/`` that even carries a
    canonical ``_review.json`` is NOT discovered.
    """
    (tmp_path / "acme-seed.3").mkdir()

    # Synthesize a fully-formed _review.json inside a staging dir.
    staging = tmp_path / ".acme-seed.3.review.tmp"
    staging.mkdir()
    review = Review(
        schema_version="1",
        kind=Kind.JUDGMENT,
        version_dir="acme-seed.3",
        critic_id="review",
        scores=[Score(dimension="d1", score=4, max=5)],
        findings=[],
        critical_flags=[],
    )
    (staging / CANONICAL_REVIEW_FILENAME).write_text(
        review.model_dump_json(indent=2)
    )

    found = discover_critics(tmp_path / "acme-seed.3")
    # The staging dir must not appear in the result.
    assert staging not in found
    assert found == []


def test_discover_critics_finds_final_but_not_staging_when_both_present(
    tmp_path,
):
    """Even when a staging dir and a final dir coexist temporarily (e.g.
    during the rename window of a long-running write), discovery sees
    only the final dir.
    """
    (tmp_path / "acme-seed.3").mkdir()

    # Final dir with valid review.
    final = tmp_path / "acme-seed.3.review"
    final.mkdir()
    review = Review(
        schema_version="1",
        kind=Kind.JUDGMENT,
        version_dir="acme-seed.3",
        critic_id="review",
        scores=[Score(dimension="d1", score=4, max=5)],
    )
    (final / CANONICAL_REVIEW_FILENAME).write_text(
        review.model_dump_json(indent=2)
    )

    # Staging dir, also carrying a _review.json shape.
    staging = tmp_path / ".acme-seed.3.review.tmp"
    staging.mkdir()
    (staging / CANONICAL_REVIEW_FILENAME).write_text(
        review.model_dump_json(indent=2)
    )

    found = discover_critics(tmp_path / "acme-seed.3")
    assert found == [final]


# ---------------------------------------------------------------------------
# Canary-replay test
# ---------------------------------------------------------------------------


def test_canary_replay_all_proper_subsets_undiscovered_and_swept(tmp_path):
    """Synthesize partial-sidecar shapes (the studio canary's 13 partial
    sidecars from mid-cycle interrupts) and verify:

    1. None of the synthesized partial-staging dirs are discovered by
       ``discover_critics`` (because the final-named dir was never
       created).
    2. ``cleanup_stale_staging`` removes all of them.

    The studio's 13 partials each carried a different subset of the
    six-file memo-review manifest. We exhaustively enumerate all
    non-empty *proper* subsets (63 of them — 2^6 - 1 minus the
    all-present case) as the canary-replay corpus; this is strictly
    more thorough than the literal 13 and covers every shape the studio
    could have produced.
    """
    (tmp_path / "studio-thread.5").mkdir()

    partial_shapes = [
        subset
        for size in range(1, len(MEMO_REVIEW_REQUIRED))
        for subset in itertools.combinations(MEMO_REVIEW_REQUIRED, size)
    ]
    assert len(partial_shapes) == 62  # C(6,1)+C(6,2)+...+C(6,5)

    synthesized_staging_dirs = []
    for idx, subset in enumerate(partial_shapes):
        # Encode each partial under a different fake tag so they don't
        # collide on the filesystem.
        tag = f"partial{idx:02d}"
        staging = tmp_path / f".studio-thread.5.{tag}.tmp"
        staging.mkdir()
        _write_all(staging, subset)
        # Plausibly include a malformed _review.json shape on some to
        # exercise the "discoverable-looking but isn't" path.
        if "_progress.json" in subset:
            (staging / "_review.json").write_text(
                json.dumps({"schema_version": "1", "version_dir": "studio-thread.5"})
            )
        synthesized_staging_dirs.append(staging)

    # 1. None of them are discovered by discover_critics.
    found = discover_critics(tmp_path / "studio-thread.5")
    assert found == []

    # 2. cleanup_stale_staging removes every one.
    removed = cleanup_stale_staging(tmp_path)
    assert len(removed) == len(synthesized_staging_dirs)
    for staging in synthesized_staging_dirs:
        assert not staging.exists()


# ---------------------------------------------------------------------------
# Split stage_enter / commit_staged surface (issue #645)
# ---------------------------------------------------------------------------


def test_stage_enter_then_commit_staged_round_trip(tmp_path):
    """stage_enter creates the staging dir; commit_staged verifies the
    manifest and atomically renames — the two-process analog of
    staged_sidecar, used by the CLI.
    """
    final = tmp_path / "thread.3.review"

    staging = stage_enter(final)
    assert staging.exists()
    assert staging == staging_path_for(final)
    assert not final.exists()

    _write_all(staging, MEMO_REVIEW_REQUIRED)

    committed = commit_staged(final, MEMO_REVIEW_REQUIRED)
    assert committed == final
    assert final.exists()
    assert not staging.exists()
    for name in MEMO_REVIEW_REQUIRED:
        assert (final / name).exists()


def test_stage_enter_refuses_if_final_exists(tmp_path):
    final = tmp_path / "thread.3.review"
    final.mkdir()
    with pytest.raises(FileExistsError):
        stage_enter(final)


def test_stage_enter_wipes_prior_staging_dir(tmp_path):
    """A leftover staging dir from a prior interrupt is wiped on re-entry
    (matches staged_sidecar's forward-progress contract).
    """
    final = tmp_path / "thread.3.review"
    staging = staging_path_for(final)
    staging.mkdir(parents=True)
    (staging / "stale.md").write_text("from a prior crash")

    returned = stage_enter(final)
    assert returned == staging
    assert not (staging / "stale.md").exists()


def test_commit_staged_missing_required_raises_and_preserves(tmp_path):
    final = tmp_path / "thread.3.review"
    staging = stage_enter(final)
    _write_all(staging, ["verdict.md", "scoring.md"])

    with pytest.raises(SidecarIncompleteError) as excinfo:
        commit_staged(final, MEMO_REVIEW_REQUIRED)

    # Final dir not created; staging dir preserved for forensics.
    assert not final.exists()
    assert staging.exists()
    assert (staging / "verdict.md").exists()
    assert "_meta.json" in str(excinfo.value)


def test_commit_staged_missing_staging_dir_raises(tmp_path):
    """commit_staged with no staging dir present raises FileNotFoundError."""
    final = tmp_path / "thread.3.review"
    with pytest.raises(FileNotFoundError):
        commit_staged(final, ("verdict.md",))


def test_commit_staged_refuses_if_final_exists(tmp_path):
    """If final_dir appeared between stage and commit, refuse the rename."""
    final = tmp_path / "thread.3.review"
    staging = stage_enter(final)
    (staging / "verdict.md").write_text("ok")
    # A concurrent writer landed the final dir first.
    final.mkdir()

    with pytest.raises(FileExistsError):
        commit_staged(final, ("verdict.md",))
    # Staging dir preserved (not renamed over the existing final).
    assert staging.exists()


# ---------------------------------------------------------------------------
# CLI surface — main() (issue #645)
# ---------------------------------------------------------------------------


def test_cli_stage_prints_staging_path_and_exit_zero(tmp_path, capsys):
    final = tmp_path / "thread.3.review"
    rc = main(["stage", str(final)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(staging_path_for(final))
    assert staging_path_for(final).exists()


def test_cli_stage_refuses_existing_final_exit_three(tmp_path, capsys):
    final = tmp_path / "thread.3.review"
    final.mkdir()
    rc = main(["stage", str(final)])
    assert rc == 3
    err = capsys.readouterr().err
    assert "already exists" in err


def test_cli_stage_write_commit_happy_path(tmp_path, capsys):
    """The documented manual recipe: stage → write required files into the
    printed path → commit → atomic rename lands the complete final dir.
    """
    final = tmp_path / "thread.3.review"

    assert main(["stage", str(final)]) == 0
    staging = Path(capsys.readouterr().out.strip())
    _write_all(staging, MEMO_REVIEW_REQUIRED)

    rc = main(["commit", str(final), "--required", ",".join(MEMO_REVIEW_REQUIRED)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(final)
    assert final.exists()
    assert not staging.exists()
    for name in MEMO_REVIEW_REQUIRED:
        assert (final / name).exists()


def test_cli_commit_missing_required_exit_one_preserves_staging(
    tmp_path, capsys
):
    """commit with a missing required file exits 1 (the SidecarIncomplete
    analog) and leaves the staging dir in place — no partial final dir.
    """
    final = tmp_path / "thread.3.review"
    main(["stage", str(final)])
    staging = Path(capsys.readouterr().out.strip())
    _write_all(staging, ["verdict.md", "scoring.md"])

    rc = main(
        ["commit", str(final), "--required", "verdict.md,scoring.md,_meta.json"]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "_meta.json" in err
    # No partial final dir; staging preserved for forensics.
    assert not final.exists()
    assert staging.exists()


def test_cli_commit_missing_staging_exit_three(tmp_path, capsys):
    """commit before any stage exits 3 (precondition/invocation error)."""
    final = tmp_path / "thread.3.review"
    rc = main(["commit", str(final), "--required", "verdict.md"])
    assert rc == 3


def test_cli_commit_refuses_existing_final_exit_three(tmp_path, capsys):
    final = tmp_path / "thread.3.review"
    main(["stage", str(final)])
    staging = Path(capsys.readouterr().out.strip())
    (staging / "verdict.md").write_text("ok")
    final.mkdir()

    rc = main(["commit", str(final), "--required", "verdict.md"])
    assert rc == 3
    assert staging.exists()


def test_cli_commit_required_tolerates_whitespace_and_empties(tmp_path, capsys):
    """The --required parser strips whitespace and ignores empty segments
    (e.g. a trailing comma).
    """
    final = tmp_path / "thread.3.review"
    main(["stage", str(final)])
    staging = Path(capsys.readouterr().out.strip())
    (staging / "verdict.md").write_text("v")
    (staging / "scoring.md").write_text("s")

    rc = main(
        ["commit", str(final), "--required", " verdict.md , scoring.md ,"]
    )
    assert rc == 0
    assert final.exists()


def test_cli_cleanup_removes_staging_and_is_idempotent(tmp_path, capsys):
    final = tmp_path / "thread.3.review"
    main(["stage", str(final)])
    capsys.readouterr()  # drain stage output
    staging = staging_path_for(final)
    assert staging.exists()

    rc = main(["cleanup", str(final)])
    assert rc == 0
    assert "removed staging dir" in capsys.readouterr().out
    assert not staging.exists()

    # Idempotent second call: still exit 0, reports nothing removed.
    rc = main(["cleanup", str(final)])
    assert rc == 0
    assert "no staging dir to remove" in capsys.readouterr().out


def test_cli_missing_subcommand_errors(tmp_path):
    """Invoking with no subcommand is an argparse error (SystemExit)."""
    with pytest.raises(SystemExit):
        main([])


# ---------------------------------------------------------------------------
# Migrated-corpus replace surface (issue #881)
# ---------------------------------------------------------------------------


def test_stage_replace_moves_dir_aside_and_copies_contents(tmp_path):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("legacy foreign review prose")

    staging = stage_replace(final)

    assert staging == staging_path_for(final)
    assert not final.exists()
    assert backup_path_for(final).exists()
    assert (staging / "review.md").read_text() == "legacy foreign review prose"


def test_stage_replace_refuses_when_existing_backup_holds_unpreserved_content(
    tmp_path,
):
    """Finding #1 (issue #885): `stage_replace` must not unconditionally
    `rmtree` an existing backup that `recover_interrupted_replace`
    deliberately preserved because it could not prove the content was
    redundant. The essay-review flow's documented next step after an
    ambiguous `recover_interrupted_replace` WARNING is exactly `stage_replace`
    — this pins that it refuses instead of silently destroying the backup.
    """
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "notes.md").write_text("side notes\n")

    # Recreate the exact ambiguous state test_recover_keeps_a_backup_holding_
    # unpreserved_content produces: a backup exists holding `notes.md` that
    # is absent from the (externally recreated) final_dir. final_dir is left
    # holding only `review.md` — foreign, non-anvil-recognizable content
    # (NOT the memo legacy triple), matching essay-review's "dir exists, not
    # recognizable" branch that dispatches to stage_replace next.
    staging = stage_replace(final)
    (staging / "notes.md").unlink()
    (staging / "review.md").write_text("externally recreated content")
    staging.rename(final)
    assert recover_interrupted_replace(final) is False  # left ambiguous, by design
    backup = backup_path_for(final)
    assert backup.exists()

    with pytest.raises(FileExistsError) as exc:
        stage_replace(final)
    assert "notes.md" in str(exc.value)
    assert "recover_interrupted_replace" in str(exc.value)

    # The backup (and its unrecoverable-elsewhere content) survives.
    assert backup.exists()
    assert (backup / "notes.md").read_text() == "side notes\n"
    # final_dir itself is untouched (no move-aside happened).
    assert final.exists()
    assert (final / "review.md").read_text() == "externally recreated content"


def test_stage_replace_drops_a_provably_redundant_existing_backup(tmp_path, caplog):
    """The happy-path counterpart: when an existing backup's content IS
    provably redundant, `stage_replace` still drops it (logging that it did
    so) before the move-aside — no refusal, no behavior change for the
    common case. (`final_dir.rename(backup)` a few lines later would recreate
    a non-empty `backup` regardless, so the observable signal that the OLD
    backup was actually dropped — rather than the rename simply failing on a
    non-empty directory — is the redundant-drop log line.)
    """
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("legacy foreign review prose")

    # A backup already on disk, byte-identical to final_dir's current
    # content (e.g. left over from a fully-landed prior commit_replace whose
    # backup-drop step alone was interrupted).
    backup = backup_path_for(final)
    shutil.copytree(final, backup)

    with caplog.at_level(logging.INFO, logger="anvil.lib.sidecar"):
        staging = stage_replace(final)

    assert (staging / "review.md").read_text() == "legacy foreign review prose"
    assert any(
        "dropping provably-redundant existing backup" in r.message
        for r in caplog.records
    )


def test_stage_replace_refuses_when_final_dir_absent(tmp_path):
    final = tmp_path / "thread.1.review"
    with pytest.raises(FileNotFoundError):
        stage_replace(final)


def test_stage_replace_refuses_when_final_dir_already_recognizable(tmp_path):
    """The #350 immutability guard stays intact: a REAL anvil review is
    never replaced, even via the new #881 surface.
    """
    final = tmp_path / "thread.1.review"
    final.mkdir()
    _write_all(final, MEMO_REVIEW_REQUIRED)  # a real recognizable review

    with pytest.raises(FileExistsError):
        stage_replace(final)

    # Untouched — no move-aside happened.
    assert final.exists()
    for name in MEMO_REVIEW_REQUIRED:
        assert (final / name).exists()
    assert not backup_path_for(final).exists()


def test_stage_replace_recognizable_via_canonical_review_json(tmp_path):
    """A sidecar carrying only `_review.json` (no legacy triple) is also
    recognized and refused — the same recognizability rule `essay-review`'s
    step 1 must use, not a bare-existence check.
    """
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / CANONICAL_REVIEW_FILENAME).write_text("{}")

    with pytest.raises(FileExistsError):
        stage_replace(final)


def test_stage_replace_then_commit_replace_round_trip(tmp_path):
    """The full #881 recipe: replace an occupied-but-unrecognized dir with
    a genuine new review while preserving the foreign content byte-
    identical alongside it.
    """
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("legacy foreign review prose")

    staging = stage_replace(final)
    _write_all(staging, MEMO_REVIEW_REQUIRED)

    required = ("review.md",) + MEMO_REVIEW_REQUIRED
    committed = commit_replace(final, required)

    assert committed == final
    assert final.exists()
    assert not staging.exists()
    assert not backup_path_for(final).exists()
    # Foreign content preserved byte-identical under its original name.
    assert (final / "review.md").read_text() == "legacy foreign review prose"
    # New sidecar files landed alongside it.
    for name in MEMO_REVIEW_REQUIRED:
        assert (final / name).exists()
    # The merged dir is now a recognizable anvil review (idempotent-skip
    # on any future rerun; discoverable by discover_critics).
    from anvil.lib.critics import _has_recognizable_review

    assert _has_recognizable_review(final)


def test_commit_replace_missing_required_preserves_staging_and_backup(tmp_path):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("legacy")

    staging = stage_replace(final)
    _write_all(staging, ["verdict.md", "scoring.md"])  # incomplete

    with pytest.raises(SidecarIncompleteError):
        commit_replace(final, ("review.md",) + MEMO_REVIEW_REQUIRED)

    assert not final.exists()
    assert staging.exists()
    assert backup_path_for(final).exists()


def test_commit_replace_missing_staging_dir_raises(tmp_path):
    final = tmp_path / "thread.1.review"
    with pytest.raises(FileNotFoundError):
        commit_replace(final, ("verdict.md",))


def test_abort_replace_restores_backup_and_discards_staging(tmp_path):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("to be restored")

    staging = stage_replace(final)
    (staging / "verdict.md").write_text("partial write")

    restored = abort_replace(final)

    assert restored is True
    assert final.exists()
    assert (final / "review.md").read_text() == "to be restored"
    assert not (final / "verdict.md").exists()
    assert not staging.exists()
    assert not backup_path_for(final).exists()


def test_abort_replace_idempotent_noop_when_nothing_to_abort(tmp_path):
    final = tmp_path / "thread.1.review"
    assert abort_replace(final) is False
    assert not final.exists()


def test_abort_replace_does_not_clobber_a_final_dir_that_reappeared(tmp_path):
    """Defensive: if final_dir exists (e.g. commit_replace already ran),
    abort_replace must not overwrite it with a stale backup.
    """
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("legacy")

    staging = stage_replace(final)
    _write_all(staging, MEMO_REVIEW_REQUIRED)
    commit_replace(final, ("review.md",) + MEMO_REVIEW_REQUIRED)

    # Backup already removed by commit_replace; final_dir now the real one.
    assert abort_replace(final) is False
    assert (final / "review.md").read_text() == "legacy"


# ---------------------------------------------------------------------------
# CLI surface — replace / commit-replace / abort-replace (issue #881)
# ---------------------------------------------------------------------------


def test_cli_replace_prints_staging_path_and_exit_zero(tmp_path, capsys):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("legacy")

    rc = main(["replace", str(final)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(staging_path_for(final))
    assert (staging_path_for(final) / "review.md").read_text() == "legacy"


def test_cli_replace_refuses_absent_final_dir_exit_three(tmp_path, capsys):
    final = tmp_path / "thread.1.review"
    rc = main(["replace", str(final)])
    assert rc == 3
    err = capsys.readouterr().err
    assert "does not exist" in err


def test_cli_replace_refuses_recognizable_final_dir_exit_three(tmp_path, capsys):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    _write_all(final, MEMO_REVIEW_REQUIRED)

    rc = main(["replace", str(final)])
    assert rc == 3
    err = capsys.readouterr().err
    assert "recognizable" in err


def test_cli_replace_write_commit_replace_happy_path(tmp_path, capsys):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("legacy foreign review prose")

    assert main(["replace", str(final)]) == 0
    staging = Path(capsys.readouterr().out.strip())
    _write_all(staging, MEMO_REVIEW_REQUIRED)

    required = "review.md," + ",".join(MEMO_REVIEW_REQUIRED)
    rc = main(["commit-replace", str(final), "--required", required])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(final)
    assert final.exists()
    assert not staging.exists()
    assert (final / "review.md").read_text() == "legacy foreign review prose"
    for name in MEMO_REVIEW_REQUIRED:
        assert (final / name).exists()


def test_cli_commit_replace_missing_required_exit_one_preserves_staging_and_backup(
    tmp_path, capsys
):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("legacy")

    main(["replace", str(final)])
    staging = Path(capsys.readouterr().out.strip())
    (staging / "verdict.md").write_text("v")

    rc = main(
        ["commit-replace", str(final), "--required", "review.md,verdict.md,scoring.md"]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "scoring.md" in err
    assert not final.exists()
    assert staging.exists()
    assert backup_path_for(final).exists()


def test_cli_abort_replace_restores_backup(tmp_path, capsys):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("to be restored")

    main(["replace", str(final)])
    capsys.readouterr()  # drain

    rc = main(["abort-replace", str(final)])
    assert rc == 0
    assert "restored" in capsys.readouterr().out
    assert final.exists()
    assert (final / "review.md").read_text() == "to be restored"


def test_cli_abort_replace_idempotent_noop(tmp_path, capsys):
    final = tmp_path / "thread.1.review"
    rc = main(["abort-replace", str(final)])
    assert rc == 0
    assert "nothing to restore" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Cross-session replace recovery (issue #881 review feedback)
# ---------------------------------------------------------------------------
#
# abort_replace() closes the SAME-session failure (the caller's except handler
# runs). It cannot close the CROSS-session one: when the process that called
# stage_replace() dies before reaching any handler, final_dir is absent and the
# only copy of its former content is in a `.bak` sibling that neither
# cleanup_one_staging nor cleanup_stale_staging recognizes. These tests pin the
# entry-step recovery sweep (recover_interrupted_replace) and the
# defense-in-depth refusals that make the silent-loss path unreachable.


def _simulate_dead_session_mid_replace(final: Path) -> Path:
    """stage_replace + partial writes, then the session vanishes — no
    abort_replace, no commit_replace. Returns the orphaned staging dir."""
    staging = stage_replace(final)
    (staging / "verdict.md").write_text("half-written verdict")
    return staging


def test_dot_bak_is_not_swept_by_either_tmp_sweep(tmp_path):
    """Pins the asymmetry that made the loss silent: the `.bak` crash path is
    invisible to both `.tmp` sweeps."""
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY AUDIT TRAIL\n")

    _simulate_dead_session_mid_replace(final)

    assert cleanup_one_staging(final) is True  # sweeps the .tmp only
    assert cleanup_stale_staging(tmp_path) == []  # never matches .bak
    assert backup_path_for(final).exists()
    assert not final.exists()


def test_recover_interrupted_replace_restores_after_a_dead_session(tmp_path):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY AUDIT TRAIL\n")

    staging = _simulate_dead_session_mid_replace(final)

    # A brand-new process (no handler, no context) recovers at entry.
    assert recover_interrupted_replace(final) is True

    assert final.exists()
    assert (final / "review.md").read_text() == "LEGACY AUDIT TRAIL\n"
    assert not (final / "verdict.md").exists()  # partial write discarded
    assert not staging.exists()
    assert not backup_path_for(final).exists()


def test_recover_interrupted_replace_is_noop_without_a_backup(tmp_path):
    final = tmp_path / "thread.1.review"
    assert recover_interrupted_replace(final) is False

    final.mkdir()
    (final / "review.md").write_text("untouched")
    assert recover_interrupted_replace(final) is False
    assert (final / "review.md").read_text() == "untouched"


def test_recover_interrupted_replace_is_idempotent(tmp_path):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY\n")
    _simulate_dead_session_mid_replace(final)

    assert recover_interrupted_replace(final) is True
    assert recover_interrupted_replace(final) is False
    assert (final / "review.md").read_text() == "LEGACY\n"


def test_recover_drops_redundant_backup_after_a_landed_swap(tmp_path):
    """Crash in commit_replace's sub-millisecond window between the rename
    and the backup drop: final_dir is correct and the backup is redundant."""
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY\n")

    staging = stage_replace(final)
    _write_all(staging, MEMO_REVIEW_REQUIRED)
    staging.rename(final)  # commit_replace's rename... and then the kill.
    assert backup_path_for(final).exists()

    assert recover_interrupted_replace(final) is True
    assert not backup_path_for(final).exists()
    assert (final / "review.md").read_text() == "LEGACY\n"


def test_recover_keeps_a_backup_holding_unpreserved_content(tmp_path):
    """Never deletes content it cannot prove is preserved: a backup entry
    absent from final_dir keeps the whole backup on disk."""
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY\n")
    (final / "notes.md").write_text("side notes\n")

    staging = stage_replace(final)
    (staging / "notes.md").unlink()  # the swap would have dropped this
    _write_all(staging, MEMO_REVIEW_REQUIRED)
    staging.rename(final)

    assert recover_interrupted_replace(final) is False
    backup = backup_path_for(final)
    assert backup.exists()
    assert (backup / "notes.md").read_text() == "side notes\n"


def test_recover_keeps_a_backup_whose_same_named_file_differs_in_content(
    tmp_path,
):
    """The predicate is content-aware, not name-only (issue #885): a
    same-named entry existing in final_dir is NOT sufficient — the bytes
    must match too, or the backup's copy is not provably redundant.
    """
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY BYTES\n")

    staging = stage_replace(final)
    # Simulate final_dir being externally recreated with a DIFFERENT
    # review.md before the (never-run) commit_replace landed.
    (staging / "review.md").write_text("DIFFERENT BYTES\n")
    _write_all(staging, MEMO_REVIEW_REQUIRED)
    staging.rename(final)

    assert recover_interrupted_replace(final) is False
    backup = backup_path_for(final)
    assert backup.exists()
    assert (backup / "review.md").read_text() == "LEGACY BYTES\n"


def test_recover_drops_backup_with_identical_nested_subdirectory_content(
    tmp_path,
):
    """The predicate recurses into subdirectories (issue #885) — a nested
    file with byte-identical content at the same relative path counts as
    preserved, not just a top-level name match.
    """
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "assets").mkdir()
    (final / "assets" / "diagram.png").write_bytes(b"\x89PNG fake bytes")

    staging = stage_replace(final)
    _write_all(staging, MEMO_REVIEW_REQUIRED)
    staging.rename(final)  # commit_replace's rename, then the kill.

    assert recover_interrupted_replace(final) is True
    assert not backup_path_for(final).exists()
    assert (final / "assets" / "diagram.png").read_bytes() == b"\x89PNG fake bytes"


def test_recover_keeps_backup_with_differing_nested_subdirectory_content(
    tmp_path,
):
    """The recursive comparison also catches a nested mismatch — not just a
    top-level one."""
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "assets").mkdir()
    (final / "assets" / "diagram.png").write_bytes(b"original bytes")

    staging = stage_replace(final)
    (staging / "assets" / "diagram.png").write_bytes(b"different bytes!!")
    _write_all(staging, MEMO_REVIEW_REQUIRED)
    staging.rename(final)

    assert recover_interrupted_replace(final) is False
    backup = backup_path_for(final)
    assert backup.exists()
    assert (backup / "assets" / "diagram.png").read_bytes() == b"original bytes"


def test_recover_ignores_a_backup_path_that_is_a_file(tmp_path):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    backup_path_for(final).write_text("not a directory")

    assert recover_interrupted_replace(final) is False
    assert backup_path_for(final).is_file()


def test_stage_enter_refuses_while_an_orphaned_backup_exists(tmp_path):
    """Defense in depth: the fresh-staging path cannot commit over the gap
    an interrupted replace left behind, even if the entry sweep is skipped."""
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY AUDIT TRAIL\n")
    _simulate_dead_session_mid_replace(final)
    cleanup_one_staging(final)

    with pytest.raises(FileExistsError) as exc:
        stage_enter(final)
    assert "recover-replace" in str(exc.value)

    # The legacy content is still recoverable — nothing was lost.
    assert recover_interrupted_replace(final) is True
    assert (final / "review.md").read_text() == "LEGACY AUDIT TRAIL\n"


def test_staged_sidecar_is_exempt_from_the_orphaned_backup_guard(tmp_path):
    """`allow_orphaned_backup=True` is the explicit, narrow opt-out (issue
    #885) for a live Python driver that manages its own same-named `.bak`
    move-aside around the call and is guaranteed to run its `except`
    handler — exactly `project-migrate`'s adopt_review driver's shape.
    Without the flag (see the next test), the guard fires.
    """
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY\n")

    # Exactly adopt_review.py::_convert_one's shape: driver-owned move-aside
    # to the same .bak path, then staged_sidecar into the vacated name.
    backup = backup_path_for(final)
    final.rename(backup)
    with staged_sidecar(
        final, MEMO_REVIEW_REQUIRED, allow_orphaned_backup=True
    ) as staging:
        _write_all(staging, MEMO_REVIEW_REQUIRED)
        (staging / "review.md").write_text((backup / "review.md").read_text())
    shutil.rmtree(backup)

    assert (final / "review.md").read_text() == "LEGACY\n"


def test_staged_sidecar_refuses_orphaned_backup_by_default(tmp_path):
    """The default (`allow_orphaned_backup=False`) closes the exemption for
    every caller except the ones that explicitly opt in (issue #885): a
    driverless session that dies mid-`stage_replace` and a later
    `staged_sidecar` caller skipping the entry sweep must not be able to
    commit a fresh sidecar over the orphaned backup.
    """
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY AUDIT TRAIL\n")
    _simulate_dead_session_mid_replace(final)
    cleanup_one_staging(final)

    with pytest.raises(FileExistsError) as exc:
        with staged_sidecar(final, MEMO_REVIEW_REQUIRED) as staging:
            raise AssertionError("entered context manager despite orphaned backup")
    assert "recover-replace" in str(exc.value)

    # Nothing was lost — the backup is still recoverable.
    assert recover_interrupted_replace(final) is True
    assert (final / "review.md").read_text() == "LEGACY AUDIT TRAIL\n"


def test_commit_staged_refuses_while_a_backup_exists(tmp_path):
    """Mis-sequencing guard: `commit` instead of `commit-replace` after a
    `replace` would strand the backup — refuse instead."""
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY\n")

    staging = stage_replace(final)
    _write_all(staging, MEMO_REVIEW_REQUIRED)

    with pytest.raises(FileExistsError) as exc:
        commit_staged(final, MEMO_REVIEW_REQUIRED)
    assert "recover-replace" in str(exc.value)
    assert not final.exists()

    # commit_replace (the right call) still works from that exact state.
    commit_replace(final, ("review.md",) + tuple(MEMO_REVIEW_REQUIRED))
    assert (final / "review.md").read_text() == "LEGACY\n"


def test_stage_replace_error_points_at_recovery_when_a_backup_exists(tmp_path):
    """The misleading-message half of the review feedback: with a `.bak`
    holding the only copy, stage_replace must NOT steer at stage_enter."""
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY\n")
    _simulate_dead_session_mid_replace(final)
    cleanup_one_staging(final)

    with pytest.raises(FileNotFoundError) as exc:
        stage_replace(final)
    message = str(exc.value)
    assert "recover_interrupted_replace" in message
    assert "recover-replace" in message
    # stage_enter is named only to warn AGAINST it, never as the remedy.
    assert "do NOT fall through to stage_enter" in message


def test_stage_replace_absent_dir_message_unchanged_without_a_backup(tmp_path):
    """Regression: the ordinary absent-final_dir message still steers at
    stage_enter when there is genuinely nothing to recover."""
    final = tmp_path / "thread.1.review"
    with pytest.raises(FileNotFoundError) as exc:
        stage_replace(final)
    assert "stage_enter" in str(exc.value)
    assert "recover_interrupted_replace" not in str(exc.value)


def test_cli_recover_replace_restores_after_a_dead_session(tmp_path, capsys):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY AUDIT TRAIL\n")

    main(["replace", str(final)])  # session dies right here
    capsys.readouterr()  # drain

    rc = main(["recover-replace", str(final)])
    assert rc == 0
    assert "recovered" in capsys.readouterr().out
    assert (final / "review.md").read_text() == "LEGACY AUDIT TRAIL\n"


def test_cli_recover_replace_idempotent_noop(tmp_path, capsys):
    final = tmp_path / "thread.1.review"
    rc = main(["recover-replace", str(final)])
    assert rc == 0
    assert "nothing to recover" in capsys.readouterr().out


def test_cli_stage_refuses_orphaned_backup_exit_three(tmp_path, capsys):
    final = tmp_path / "thread.1.review"
    final.mkdir()
    (final / "review.md").write_text("LEGACY\n")
    main(["replace", str(final)])
    main(["cleanup", str(final)])
    capsys.readouterr()  # drain

    rc = main(["stage", str(final)])
    assert rc == 3
    assert "recover-replace" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Binary/bulk-asset copy primitive — copy_bytes / CLI `copy` (issue #1017)
# ---------------------------------------------------------------------------
#
# The sanctioned binary/bulk channel for a session whose editing tool is
# text-only (and whose Bash channel may be blocked by a consumer's
# worktree-isolation hook): figure/PDF carry-forward between versions and
# raw compile-log capture into a sidecar, both "move existing bytes into a
# staging dir," not "generate new bytes."


def test_copy_bytes_file_happy_path(tmp_path):
    src = tmp_path / "compile.log"
    src.write_bytes(b"pdflatex output line 1\nline 2\n" * 100)
    dst = tmp_path / "out" / "compile-log.txt"

    landed = copy_bytes(src, dst)

    assert landed == dst
    assert dst.read_bytes() == src.read_bytes()
    # No leftover staging sibling after a clean landing.
    assert not staging_path_for(dst).exists()


def test_copy_bytes_directory_happy_path_byte_identical_recursive(tmp_path):
    src = tmp_path / "thread.2" / "figures"
    (src / "src").mkdir(parents=True)
    (src / "scaling.pdf").write_bytes(b"%PDF-1.4 fake figure bytes\n" * 50)
    (src / "src" / "scaling.py").write_text("import matplotlib\n# render script\n")

    dst = tmp_path / "thread.3" / "figures"

    landed = copy_bytes(src, dst)

    assert landed == dst
    assert (dst / "scaling.pdf").read_bytes() == (src / "scaling.pdf").read_bytes()
    assert (dst / "src" / "scaling.py").read_text() == (
        src / "src" / "scaling.py"
    ).read_text()
    assert not staging_path_for(dst).exists()


def test_copy_bytes_missing_source_raises(tmp_path):
    src = tmp_path / "does-not-exist.pdf"
    dst = tmp_path / "dst.pdf"

    with pytest.raises(FileNotFoundError):
        copy_bytes(src, dst)

    assert not dst.exists()


def test_copy_bytes_refuses_existing_destination_without_force(tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"new content")
    dst = tmp_path / "dst.pdf"
    dst.write_bytes(b"old content - must not be clobbered")

    with pytest.raises(FileExistsError):
        copy_bytes(src, dst)

    assert dst.read_bytes() == b"old content - must not be clobbered"


def test_copy_bytes_overwrite_replaces_existing_destination(tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"new content")
    dst = tmp_path / "dst.pdf"
    dst.write_bytes(b"stale content")

    landed = copy_bytes(src, dst, overwrite=True)

    assert landed == dst
    assert dst.read_bytes() == b"new content"


def test_copy_bytes_creates_missing_parent_dirs(tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"bytes")
    dst = tmp_path / "a" / "b" / "c" / "dst.pdf"

    copy_bytes(src, dst)

    assert dst.read_bytes() == b"bytes"


def test_copy_bytes_removes_stale_staging_sibling_from_prior_interrupt(tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"bytes")
    dst = tmp_path / "dst.pdf"

    stale_staging = staging_path_for(dst)
    stale_staging.parent.mkdir(parents=True, exist_ok=True)
    stale_staging.write_bytes(b"leftover from a killed prior attempt")

    copy_bytes(src, dst)

    assert dst.read_bytes() == b"bytes"


def test_copy_bytes_verification_failure_leaves_staged_copy_unrenamed(
    tmp_path, monkeypatch
):
    import anvil.lib.sidecar as sidecar_module

    src = tmp_path / "src.pdf"
    src.write_bytes(b"the real bytes")
    dst = tmp_path / "dst.pdf"

    def _corrupt_copy2(_src, _dst, *args, **kwargs):
        Path(_dst).write_bytes(b"corrupted during copy")

    monkeypatch.setattr(sidecar_module.shutil, "copy2", _corrupt_copy2)

    with pytest.raises(SidecarCopyVerificationError):
        copy_bytes(src, dst)

    staged = staging_path_for(dst)
    assert staged.exists()
    assert staged.read_bytes() == b"corrupted during copy"
    assert not dst.exists()


def test_copy_bytes_no_verify_skips_the_check(tmp_path, monkeypatch):
    import anvil.lib.sidecar as sidecar_module

    src = tmp_path / "src.pdf"
    src.write_bytes(b"the real bytes")
    dst = tmp_path / "dst.pdf"

    def _corrupt_copy2(_src, _dst, *args, **kwargs):
        Path(_dst).write_bytes(b"corrupted during copy")

    monkeypatch.setattr(sidecar_module.shutil, "copy2", _corrupt_copy2)

    landed = copy_bytes(src, dst, verify=False)

    assert landed == dst
    assert dst.read_bytes() == b"corrupted during copy"


# --- CLI surface: `copy` (issue #1017) ---------------------------------


def test_cli_copy_file_prints_dst_and_exit_zero(tmp_path, capsys):
    src = tmp_path / "compile.log"
    src.write_bytes(b"raw pdflatex bytes\n" * 10)
    dst = tmp_path / "thread.3.audit-staging" / "compile-log.txt"

    rc = main(["copy", str(src), str(dst)])

    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(dst)
    assert dst.read_bytes() == src.read_bytes()


def test_cli_copy_directory_prints_dst_and_exit_zero(tmp_path, capsys):
    src = tmp_path / "thread.2" / "figures"
    src.mkdir(parents=True)
    (src / "plot.pdf").write_bytes(b"%PDF fake\n" * 5)
    dst = tmp_path / "thread.3" / "figures"

    rc = main(["copy", str(src), str(dst)])

    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(dst)
    assert (dst / "plot.pdf").read_bytes() == (src / "plot.pdf").read_bytes()


def test_cli_copy_missing_source_exit_three(tmp_path, capsys):
    src = tmp_path / "missing.pdf"
    dst = tmp_path / "dst.pdf"

    rc = main(["copy", str(src), str(dst)])

    assert rc == 3
    err = capsys.readouterr().err
    assert "does not exist" in err
    assert not dst.exists()


def test_cli_copy_existing_destination_exit_three_without_force(tmp_path, capsys):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"new")
    dst = tmp_path / "dst.pdf"
    dst.write_bytes(b"old")

    rc = main(["copy", str(src), str(dst)])

    assert rc == 3
    err = capsys.readouterr().err
    assert "refusing to overwrite" in err
    assert dst.read_bytes() == b"old"


def test_cli_copy_force_overwrites_existing_destination(tmp_path, capsys):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"new")
    dst = tmp_path / "dst.pdf"
    dst.write_bytes(b"old")

    rc = main(["copy", str(src), str(dst), "--force"])

    assert rc == 0
    assert dst.read_bytes() == b"new"


def test_cli_copy_verification_failure_exit_one(tmp_path, capsys, monkeypatch):
    import anvil.lib.sidecar as sidecar_module

    src = tmp_path / "src.pdf"
    src.write_bytes(b"real bytes")
    dst = tmp_path / "dst.pdf"

    def _corrupt_copy2(_src, _dst, *args, **kwargs):
        Path(_dst).write_bytes(b"corrupted")

    monkeypatch.setattr(sidecar_module.shutil, "copy2", _corrupt_copy2)

    rc = main(["copy", str(src), str(dst)])

    assert rc == 1
    err = capsys.readouterr().err
    assert "did not match source" in err
    assert not dst.exists()


def test_cli_copy_no_verify_flag_skips_verification(tmp_path, capsys, monkeypatch):
    import anvil.lib.sidecar as sidecar_module

    src = tmp_path / "src.pdf"
    src.write_bytes(b"real bytes")
    dst = tmp_path / "dst.pdf"

    def _corrupt_copy2(_src, _dst, *args, **kwargs):
        Path(_dst).write_bytes(b"corrupted")

    monkeypatch.setattr(sidecar_module.shutil, "copy2", _corrupt_copy2)

    rc = main(["copy", str(src), str(dst), "--no-verify"])

    assert rc == 0
    assert dst.read_bytes() == b"corrupted"


# ---------------------------------------------------------------------------
# write_critic_review_dir — critic-sidecar writer consolidation (issue #1086)
# ---------------------------------------------------------------------------


def _make_review(version_dir_name: str = "acme-seed.1") -> Review:
    return Review(
        schema_version="1",
        kind=Kind.TOOL_EVIDENCE,
        version_dir=version_dir_name,
        critic_id="fake-critic",
        scores=[Score(dimension="d1", score=None, max=1, critical=False)],
        findings=[],
        critical_flags=[],
    )


class TestWriteCriticReviewDir:
    def test_atomic_default_writes_review_only(self, tmp_path: Path) -> None:
        """Default call (no ``findings_json``) writes only ``_review.json``,
        atomically, via ``staged_sidecar`` — the four-of-seven single-file
        convention."""
        version_dir = tmp_path / "acme-seed.1"
        version_dir.mkdir()
        review = _make_review()

        out = write_critic_review_dir(version_dir, "fake", review)

        final = tmp_path / "acme-seed.1.fake"
        assert out == final / "_review.json"
        assert out.is_file()
        assert sorted(p.name for p in final.iterdir()) == ["_review.json"]
        # No leftover staging dir.
        assert not (tmp_path / ".acme-seed.1.fake.tmp").exists()

        loaded = Review.model_validate_json(out.read_text(encoding="utf-8"))
        assert loaded.critic_id == "fake-critic"

    def test_atomic_with_findings_json_writes_both_files(
        self, tmp_path: Path
    ) -> None:
        """``findings_json`` given writes a ``_findings.json`` companion —
        the three-of-seven companion-file convention."""
        version_dir = tmp_path / "acme-seed.1"
        version_dir.mkdir()
        review = _make_review()

        out = write_critic_review_dir(
            version_dir,
            "fake",
            review,
            findings_json={"critic": "fake-critic", "total_findings": 0},
        )

        final = tmp_path / "acme-seed.1.fake"
        assert out == final / "_review.json"
        assert sorted(p.name for p in final.iterdir()) == [
            "_findings.json",
            "_review.json",
        ]
        findings = json.loads((final / "_findings.json").read_text())
        assert findings == {"critic": "fake-critic", "total_findings": 0}

    def test_atomic_regenerate_true_replaces_prior_run(
        self, tmp_path: Path
    ) -> None:
        """A second call with ``regenerate=True`` (the default) replaces an
        existing sibling dir from a prior deterministic run — no
        ``FileExistsError``, no leftover staging dir."""
        version_dir = tmp_path / "acme-seed.1"
        version_dir.mkdir()

        first = write_critic_review_dir(version_dir, "fake", _make_review())
        second = write_critic_review_dir(version_dir, "fake", _make_review())

        assert first == second
        assert second.is_file()
        leftovers = [
            p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")
        ]
        assert leftovers == []

    def test_atomic_regenerate_false_raises_on_existing_final_dir(
        self, tmp_path: Path
    ) -> None:
        """``regenerate=False`` reproduces ``staged_sidecar``'s own
        one-shot immutability default: a rerun is a hard error, not a
        silent overwrite."""
        version_dir = tmp_path / "acme-seed.1"
        version_dir.mkdir()

        write_critic_review_dir(
            version_dir, "fake", _make_review(), regenerate=False
        )
        with pytest.raises(FileExistsError):
            write_critic_review_dir(
                version_dir, "fake", _make_review(), regenerate=False
            )

    def test_atomic_sweeps_leftover_staging_from_prior_interrupt(
        self, tmp_path: Path
    ) -> None:
        """A leftover ``.tmp`` staging dir from a prior interrupted run of
        THIS critic on THIS version is swept before staging fresh (issue
        #376's per-critic entry-step sweep, exercised through the shared
        helper)."""
        version_dir = tmp_path / "acme-seed.1"
        version_dir.mkdir()
        stale_staging = tmp_path / ".acme-seed.1.fake.tmp"
        stale_staging.mkdir()
        (stale_staging / "partial.txt").write_text("orphaned")

        out = write_critic_review_dir(version_dir, "fake", _make_review())

        assert out.is_file()
        assert not stale_staging.exists()

    def test_atomic_leaves_staging_dir_on_body_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A crash mid-write (simulated via a corrupt manifest) leaves the
        staging dir in place for forensics, matching
        :func:`staged_sidecar`'s own contract — the crash-safety
        ``atomic=True`` is meant to buy."""
        version_dir = tmp_path / "acme-seed.1"
        version_dir.mkdir()

        class _ExplodingReview:
            def model_dump(self, mode: str = "json") -> dict:
                raise RuntimeError("boom mid-serialize")

        with pytest.raises(RuntimeError, match="boom mid-serialize"):
            write_critic_review_dir(version_dir, "fake", _ExplodingReview())

        final = tmp_path / "acme-seed.1.fake"
        assert not final.exists()

    def test_non_atomic_mkdir_write_text_shape(self, tmp_path: Path) -> None:
        """``atomic=False`` reproduces the pre-#1086 plain
        ``mkdir(parents=True, exist_ok=...)`` + ``write_text`` shape — no
        staging dir involved at all."""
        version_dir = tmp_path / "acme-seed.1"
        version_dir.mkdir()

        out = write_critic_review_dir(
            version_dir, "fake", _make_review(), atomic=False
        )

        final = tmp_path / "acme-seed.1.fake"
        assert out == final / "_review.json"
        assert out.is_file()
        assert not (tmp_path / ".acme-seed.1.fake.tmp").exists()

    def test_non_atomic_regenerate_false_raises_on_rerun(
        self, tmp_path: Path
    ) -> None:
        """``atomic=False, regenerate=False`` mirrors ``exist_ok=False``:
        a rerun over an existing sibling dir is a hard error."""
        version_dir = tmp_path / "acme-seed.1"
        version_dir.mkdir()

        write_critic_review_dir(
            version_dir, "fake", _make_review(), atomic=False, regenerate=False
        )
        with pytest.raises(FileExistsError):
            write_critic_review_dir(
                version_dir,
                "fake",
                _make_review(),
                atomic=False,
                regenerate=False,
            )

    def test_return_value_matches_seven_pre_1086_copies_contract(
        self, tmp_path: Path
    ) -> None:
        """Returns the ``_review.json`` path, NOT the sibling dir itself —
        matches every pre-#1086 copy's own return contract."""
        version_dir = tmp_path / "acme-seed.1"
        version_dir.mkdir()

        out = write_critic_review_dir(version_dir, "fake", _make_review())

        assert out.name == "_review.json"
        assert out.parent.name == "acme-seed.1.fake"
