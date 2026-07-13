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
from pathlib import Path

import pytest

from anvil.lib.critics import CANONICAL_REVIEW_FILENAME, discover_critics
from anvil.lib.review_schema import Kind, Review, Score
from anvil.lib.sidecar import (
    STAGING_SUFFIX,
    SidecarIncompleteError,
    cleanup_one_staging,
    cleanup_stale_staging,
    commit_staged,
    main,
    stage_enter,
    staged_sidecar,
    staging_path_for,
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
    for slug in ("acme-seed.3.review", "brasidas.7.audit", "foo.1.narrative"):
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
    assert names == [
        ".acme-seed.3.review.tmp",
        ".brasidas.7.audit.tmp",
        ".foo.1.narrative.tmp",
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
