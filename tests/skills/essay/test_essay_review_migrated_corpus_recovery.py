"""Behavioral coverage for the essay-review migrated-corpus recovery path
(issue #881).

`essay-review.md` step 1 is documented (see
`test_essay_review_migrated_corpus_doc.py`) to use
`anvil.lib.critics._has_recognizable_review` for its idempotency check
(content-aware, not bare directory-existence) and
`anvil.lib.sidecar.stage_replace` / `commit_replace` / `abort_replace` to
land a genuine new review into a `<thread>.{N}.review/` dir that a
migration left occupied by foreign content only (e.g. a legacy single-file
`review.md`).

essay-review itself is a markdown-driven command with no direct Python
entry point, so this suite exercises the load-bearing PRIMITIVES an
agent following the doc would call, against realistic essay-review sidecar
shapes — the essay required-files manifest
(`verdict.md`/`scoring.md`/`comments.md`/`_summary.md`/`_gate.json`/
`_meta.json`/`_progress.json`) plus a preserved legacy `review.md`.

Covers the issue's test plan:
- a version whose `<thread>.{N}.review/` exists with only foreign content
  (no `_review.json`) is NOT silently treated as reviewed, and does NOT
  crash the sidecar guard when landed via `stage_replace`/`commit_replace`;
- a REAL anvil review dir still idempotent-skips (regression, #350 intact);
- `project-migrate --adopt-review` still finds the legacy `review.md`
  afterward (cross-check);
- the **cross-session** crash path: the session dies between
  `stage_replace` and `commit_replace` (no `except` handler survives to
  call `abort_replace`), and the NEXT run — executing step 1 exactly as
  documented — recovers the legacy `review.md` instead of stranding it in
  a hidden `.bak` sibling.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.lib.critics import _has_recognizable_review
from anvil.lib.sidecar import (
    SidecarIncompleteError,
    abort_replace,
    backup_path_for,
    cleanup_one_staging,
    cleanup_stale_staging,
    commit_replace,
    commit_staged,
    recover_interrupted_replace,
    stage_enter,
    stage_replace,
    staging_path_for,
)

ESSAY_REVIEW_REQUIRED = (
    "verdict.md",
    "scoring.md",
    "comments.md",
    "_summary.md",
    "_gate.json",
    "_meta.json",
    "_progress.json",
)

LEGACY_REVIEW_PROSE = (
    "# Review: the-loop-is-the-unit.2\n\n"
    "Solid piece. Two independent review passes on this thread; the\n"
    "corrections here are the audit trail for the finisher-spread fix.\n"
)


def _write_essay_review_files(staging: Path) -> None:
    for name in ESSAY_REVIEW_REQUIRED:
        staging.joinpath(name).write_text(f"placeholder for {name}\n")


class TestForeignOnlyDirIsNotIdempotentSkip:
    """The bare-existence bug this issue reports: a migrated dir holding
    ONLY `review.md` must NOT be treated as "already reviewed"."""

    def test_foreign_only_dir_fails_recognizability_check(self, tmp_path):
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        (version_review_dir / "review.md").write_text(LEGACY_REVIEW_PROSE)

        # This is the exact check step 1 must use instead of bare
        # dir.exists() — it must return False for foreign-only content.
        assert _has_recognizable_review(version_review_dir) is False

    def test_stage_replace_lands_new_review_without_filesystem_error(
        self, tmp_path
    ):
        """The FileExistsError / exit-3 crash the issue reports is avoided:
        stage_replace succeeds on an occupied-but-unrecognized dir."""
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        (version_review_dir / "review.md").write_text(LEGACY_REVIEW_PROSE)

        staging = stage_replace(version_review_dir)
        assert staging == staging_path_for(version_review_dir)
        assert not version_review_dir.exists()

        _write_essay_review_files(staging)

        committed = commit_replace(
            version_review_dir,
            required_files=("review.md",) + ESSAY_REVIEW_REQUIRED,
        )

        assert committed == version_review_dir
        assert version_review_dir.exists()
        # The legacy prose survives byte-identical, under its original name.
        assert (
            version_review_dir / "review.md"
        ).read_text() == LEGACY_REVIEW_PROSE
        # Every real anvil review file landed too.
        for name in ESSAY_REVIEW_REQUIRED:
            assert (version_review_dir / name).exists()
        # No leftover staging/backup dirs.
        assert not staging_path_for(version_review_dir).exists()
        assert not backup_path_for(version_review_dir).exists()


class TestRealAnvilReviewStillIdempotentSkips:
    """Regression: a REAL essay review (the verdict/scoring/comments
    triple `essay-review` itself writes) must still be treated as
    already-reviewed — the #350 guard is untouched by this issue's fix."""

    def test_real_review_dir_is_recognizable(self, tmp_path):
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        for name in ("verdict.md", "scoring.md", "comments.md"):
            (version_review_dir / name).write_text(f"real {name}")

        assert _has_recognizable_review(version_review_dir) is True

    def test_stage_replace_refuses_a_real_review_dir(self, tmp_path):
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        for name in ESSAY_REVIEW_REQUIRED:
            (version_review_dir / name).write_text(f"real {name}")

        with pytest.raises(FileExistsError):
            stage_replace(version_review_dir)

        # Untouched — a real review is never moved aside.
        for name in ESSAY_REVIEW_REQUIRED:
            assert (version_review_dir / name).exists()
        assert not backup_path_for(version_review_dir).exists()


class TestAbortRestoresOriginalOnFailure:
    def test_abort_replace_restores_legacy_review_after_a_failed_write(
        self, tmp_path
    ):
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        (version_review_dir / "review.md").write_text(LEGACY_REVIEW_PROSE)

        staging = stage_replace(version_review_dir)
        # Simulate a partial write (e.g. the LLM review pass errored
        # mid-way) then recover via abort_replace, per the documented
        # recipe.
        (staging / "verdict.md").write_text("partial")

        restored = abort_replace(version_review_dir)

        assert restored is True
        assert version_review_dir.exists()
        assert (
            version_review_dir / "review.md"
        ).read_text() == LEGACY_REVIEW_PROSE
        assert not (version_review_dir / "verdict.md").exists()

    def test_commit_replace_missing_required_leaves_recoverable_state(
        self, tmp_path
    ):
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        (version_review_dir / "review.md").write_text(LEGACY_REVIEW_PROSE)

        staging = stage_replace(version_review_dir)
        # Incomplete: only two of the seven required essay files.
        (staging / "verdict.md").write_text("v")
        (staging / "scoring.md").write_text("s")

        with pytest.raises(SidecarIncompleteError):
            commit_replace(
                version_review_dir,
                required_files=("review.md",) + ESSAY_REVIEW_REQUIRED,
            )

        assert not version_review_dir.exists()
        # abort_replace still recovers the original content cleanly.
        assert abort_replace(version_review_dir) is True
        assert (
            version_review_dir / "review.md"
        ).read_text() == LEGACY_REVIEW_PROSE


class TestCrossSessionCrashBetweenStageAndCommit:
    """The cross-session half of the recovery story.

    `TestAbortRestoresOriginalOnFailure` above models a session that
    catches its own exception and calls `abort_replace` — the SAME-session
    path. essay-review is markdown-driven: the window between
    `stage_replace` and `commit_replace` spans seven separate file-writing
    tool calls, and the session itself can end inside it (context
    exhaustion, process kill, orchestrator timeout). Nothing then runs
    `abort_replace`. These tests simulate that death and assert the NEXT
    run — a brand-new process executing step 1 as documented — recovers the
    legacy `review.md` rather than committing a fresh review over the gap
    and stranding it.
    """

    @staticmethod
    def _dead_session_mid_review(version_review_dir: Path) -> Path:
        """A first essay-review pass that opens the replace, writes two of
        its seven required files, and then simply ends. Returns the
        orphaned staging dir."""
        staging = stage_replace(version_review_dir)
        (staging / "verdict.md").write_text("partial verdict\n")
        (staging / "scoring.md").write_text("partial scoring\n")
        return staging

    def _step_1_entry_sweeps(self, version_review_dir: Path) -> None:
        """Step 1's documented entry sweeps, in documented order."""
        cleanup_one_staging(version_review_dir)
        recover_interrupted_replace(version_review_dir)

    def test_legacy_review_is_recovered_by_the_next_runs_entry_sweep(
        self, tmp_path
    ):
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        (version_review_dir / "review.md").write_text(LEGACY_REVIEW_PROSE)

        staging = self._dead_session_mid_review(version_review_dir)
        # Post-mortem state: the canonical path is GONE and the only copy of
        # the legacy prose is in the hidden backup.
        assert not version_review_dir.exists()
        assert (backup_path_for(version_review_dir) / "review.md").exists()

        # --- next essay-review run, step 1 ---
        self._step_1_entry_sweeps(version_review_dir)

        assert version_review_dir.exists()
        assert (
            version_review_dir / "review.md"
        ).read_text() == LEGACY_REVIEW_PROSE
        assert not (version_review_dir / "verdict.md").exists()
        assert not staging.exists()
        assert not backup_path_for(version_review_dir).exists()

        # And the recovered dir routes back into the migrated-corpus case,
        # so this run lands the merged review the first one failed to.
        assert _has_recognizable_review(version_review_dir) is False
        staging = stage_replace(version_review_dir)
        _write_essay_review_files(staging)
        commit_replace(
            version_review_dir,
            required_files=("review.md",) + ESSAY_REVIEW_REQUIRED,
        )
        assert (
            version_review_dir / "review.md"
        ).read_text() == LEGACY_REVIEW_PROSE
        for name in ESSAY_REVIEW_REQUIRED:
            assert (version_review_dir / name).exists()

    def test_tmp_sweep_alone_cannot_see_the_backup(self, tmp_path):
        """Why the second sweep is load-bearing: the `.tmp` sweeps are blind
        to the `.bak` crash path (the asymmetry the review flagged)."""
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        (version_review_dir / "review.md").write_text(LEGACY_REVIEW_PROSE)

        self._dead_session_mid_review(version_review_dir)

        assert cleanup_one_staging(version_review_dir) is True
        assert cleanup_stale_staging(tmp_path) == []
        assert not version_review_dir.exists()
        assert backup_path_for(version_review_dir).exists()

    def test_fresh_stage_path_refuses_instead_of_stranding_the_legacy_file(
        self, tmp_path
    ):
        """Defense in depth: even a run that skips the recovery sweep and
        follows step 1's "dir does not exist" branch cannot commit a fresh
        review over the gap — the primitive refuses, loudly, and the legacy
        prose stays recoverable."""
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        (version_review_dir / "review.md").write_text(LEGACY_REVIEW_PROSE)

        self._dead_session_mid_review(version_review_dir)
        cleanup_one_staging(version_review_dir)  # the pre-fix entry step

        assert not version_review_dir.exists()  # the misleading branch
        with pytest.raises(FileExistsError) as exc:
            stage_enter(version_review_dir)
        assert "recover" in str(exc.value)

        # Nothing lost: recovery still works after the refusal.
        assert recover_interrupted_replace(version_review_dir) is True
        assert (
            version_review_dir / "review.md"
        ).read_text() == LEGACY_REVIEW_PROSE

    def test_committing_via_the_plain_path_after_a_replace_is_refused(
        self, tmp_path
    ):
        """The mis-sequencing variant: a live session that reaches
        `commit` (not `commit-replace`) would drop the backup on the floor
        — refuse, and let `commit_replace` land the merged dir instead."""
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        (version_review_dir / "review.md").write_text(LEGACY_REVIEW_PROSE)

        staging = stage_replace(version_review_dir)
        _write_essay_review_files(staging)

        with pytest.raises(FileExistsError):
            commit_staged(version_review_dir, ESSAY_REVIEW_REQUIRED)

        commit_replace(
            version_review_dir,
            required_files=("review.md",) + ESSAY_REVIEW_REQUIRED,
        )
        assert (
            version_review_dir / "review.md"
        ).read_text() == LEGACY_REVIEW_PROSE
        assert not backup_path_for(version_review_dir).exists()

    def test_recovery_sweep_is_a_noop_on_the_ordinary_first_review(
        self, tmp_path
    ):
        """No cost to running it unconditionally at step 1 entry: with no
        backup on disk it changes nothing, and the normal fresh-staging
        path proceeds untouched."""
        version_review_dir = tmp_path / "the-loop-is-the-unit.2.review"

        self._step_1_entry_sweeps(version_review_dir)
        assert not version_review_dir.exists()

        staging = stage_enter(version_review_dir)
        _write_essay_review_files(staging)
        commit_staged(version_review_dir, ESSAY_REVIEW_REQUIRED)
        assert _has_recognizable_review(version_review_dir) is True


class TestAdoptReviewCrossCheck:
    """Cross-check (issue #881's third test-plan bullet): after
    essay-review lands a merged review via stage_replace/commit_replace,
    `project-migrate --adopt-review`'s planner must still find the
    preserved legacy `review.md` at its original path/name — and, since
    the dir is now a REAL recognizable review, correctly SKIP it (never
    attempt to convert/clobber it) rather than erroring."""

    def test_adopt_review_plan_finds_and_skips_the_merged_sidecar(
        self, tmp_path
    ):
        from anvil.lib.skill_lib_loader import load_skill_lib

        repo_root = Path(__file__).resolve().parents[3]
        lib_dir = repo_root / "anvil" / "skills" / "project-migrate" / "lib"
        lib = load_skill_lib(
            "project-migrate",
            lib_dir,
            ["adopt_review"],
            package_name="project_migrate_lib",
        )
        adopt_review = lib.adopt_review

        # Build a minimal adopted-tree shape: a version dir + its merged
        # review sidecar, named per the canonical <slug>.<N>.<tag> grammar
        # adopt_review's planner scans for.
        thread_root = tmp_path / "the-loop-is-the-unit"
        thread_root.mkdir()
        version_dir = thread_root / "the-loop-is-the-unit.2"
        version_dir.mkdir()
        (version_dir / "the-loop-is-the-unit.md").write_text("body")

        version_review_dir = thread_root / "the-loop-is-the-unit.2.review"
        version_review_dir.mkdir()
        (version_review_dir / "review.md").write_text(LEGACY_REVIEW_PROSE)

        staging = stage_replace(version_review_dir)
        _write_essay_review_files(staging)
        commit_replace(
            version_review_dir,
            required_files=("review.md",) + ESSAY_REVIEW_REQUIRED,
        )

        plan = adopt_review.build_adopt_review_plan(thread_root)

        # Not queued for stub-conversion (it's a real review now) — but
        # explicitly reported as found-and-skipped, not silently invisible.
        assert plan.conversions == []
        skipped_names = {name for name, _reason in plan.skipped}
        assert "the-loop-is-the-unit.2.review" in skipped_names
        reason = dict(plan.skipped)["the-loop-is-the-unit.2.review"]
        assert "already recognizable" in reason

        # And the legacy prose is still discoverable, byte-identical, at
        # its original filename inside the sidecar dir.
        assert (
            version_review_dir / "review.md"
        ).read_text() == LEGACY_REVIEW_PROSE
