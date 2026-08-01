"""Tests for ``anvil/lib/evidence_drift.py`` (issue #857).

Covers the acceptance criteria from #857:

- The shared drift-detection function compares ``BRIEF.md`` mtime + the
  max mtime under ``refs/**`` against a recorded snapshot, and returns
  an advisory result with no on-disk mutation and no gating effect.
- A snapshot is recorded (mtimes, not content) into
  ``_progress.json``'s ``metadata.evidence_snapshot`` via
  ``record_evidence_snapshot`` — the read-merge-write preserves all
  other top-level and ``metadata`` fields.
- Bootstrap case: no prior snapshot recorded reports ``NO-SNAPSHOT``
  (``drifted == False``), never a false-positive drift signal.
- Clean case: BRIEF/refs unchanged since the snapshot reports ``CLEAN``.
- Drift cases: touching ``BRIEF.md`` after the snapshot, and touching a
  file under ``refs/`` after the snapshot, both report ``EVIDENCE-DRIFT``.
- The CLI ``record``/``check`` subcommands round-trip through a real
  ``_progress.json`` and always exit ``0`` (purely advisory).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from anvil.lib.evidence_drift import (
    STATUS_CLEAN,
    STATUS_DRIFT,
    STATUS_NO_SNAPSHOT,
    check_evidence_drift,
    check_thread_evidence_drift,
    compute_evidence_snapshot,
    load_snapshot_from_progress,
    main,
    record_evidence_snapshot,
)


def _touch(path: Path, *, mtime: float | None = None, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _bump(path: Path, *, ahead_seconds: float = 5.0) -> float:
    """Rewrite ``path`` with an mtime ``ahead_seconds`` after its current mtime."""
    new_mtime = path.stat().st_mtime + ahead_seconds
    path.write_text(path.read_text(encoding="utf-8") + " updated", encoding="utf-8")
    os.utime(path, (new_mtime, new_mtime))
    return new_mtime


# ---------------------------------------------------------------------------
# compute_evidence_snapshot
# ---------------------------------------------------------------------------


class TestComputeEvidenceSnapshot:
    def test_absent_brief_and_refs_are_none(self, tmp_path: Path) -> None:
        snapshot = compute_evidence_snapshot(tmp_path)
        assert snapshot == {"brief_mtime": None, "refs_mtime": None}

    def test_brief_mtime_recorded(self, tmp_path: Path) -> None:
        _touch(tmp_path / "BRIEF.md", mtime=1_700_000_000.0)
        snapshot = compute_evidence_snapshot(tmp_path)
        assert snapshot["brief_mtime"] == pytest.approx(1_700_000_000.0)
        assert snapshot["refs_mtime"] is None

    def test_refs_max_mtime_across_nested_files(self, tmp_path: Path) -> None:
        _touch(tmp_path / "refs" / "a.txt", mtime=1_000.0)
        _touch(tmp_path / "refs" / "sub" / "b.txt", mtime=2_000.0)
        _touch(tmp_path / "refs" / "sub" / "c.txt", mtime=1_500.0)
        snapshot = compute_evidence_snapshot(tmp_path)
        assert snapshot["refs_mtime"] == pytest.approx(2_000.0)

    def test_empty_refs_dir_is_none(self, tmp_path: Path) -> None:
        (tmp_path / "refs").mkdir()
        snapshot = compute_evidence_snapshot(tmp_path)
        assert snapshot["refs_mtime"] is None


# ---------------------------------------------------------------------------
# record_evidence_snapshot / load_snapshot_from_progress
# ---------------------------------------------------------------------------


class TestRecordEvidenceSnapshot:
    def test_records_into_fresh_progress_json(self, tmp_path: Path) -> None:
        thread_dir = tmp_path / "my-thread"
        version_dir = tmp_path / "my-thread.1"
        _touch(thread_dir / "BRIEF.md", mtime=42.0)

        snapshot = record_evidence_snapshot(thread_dir, version_dir)

        assert snapshot["brief_mtime"] == pytest.approx(42.0)
        progress = json.loads((version_dir / "_progress.json").read_text())
        assert progress["metadata"]["evidence_snapshot"] == snapshot

    def test_preserves_other_progress_fields(self, tmp_path: Path) -> None:
        thread_dir = tmp_path / "my-thread"
        version_dir = tmp_path / "my-thread.1"
        version_dir.mkdir(parents=True)
        (version_dir / "_progress.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "thread": "my-thread",
                    "phases": {"draft": {"state": "done"}},
                    "metadata": {"iteration": 1, "max_iterations": 4},
                }
            ),
            encoding="utf-8",
        )
        _touch(thread_dir / "BRIEF.md", mtime=99.0)

        record_evidence_snapshot(thread_dir, version_dir)

        progress = json.loads((version_dir / "_progress.json").read_text())
        assert progress["phases"] == {"draft": {"state": "done"}}
        assert progress["metadata"]["iteration"] == 1
        assert progress["metadata"]["max_iterations"] == 4
        assert progress["metadata"]["evidence_snapshot"]["brief_mtime"] == pytest.approx(99.0)

    def test_load_snapshot_round_trips(self, tmp_path: Path) -> None:
        thread_dir = tmp_path / "t"
        version_dir = tmp_path / "t.1"
        _touch(thread_dir / "BRIEF.md", mtime=7.0)

        record_evidence_snapshot(thread_dir, version_dir)
        loaded = load_snapshot_from_progress(version_dir)

        assert loaded == {"brief_mtime": pytest.approx(7.0), "refs_mtime": None}

    def test_load_snapshot_missing_progress_json_is_none(self, tmp_path: Path) -> None:
        assert load_snapshot_from_progress(tmp_path / "nonexistent.1") is None

    def test_load_snapshot_malformed_progress_json_is_none(self, tmp_path: Path) -> None:
        version_dir = tmp_path / "t.1"
        version_dir.mkdir(parents=True)
        (version_dir / "_progress.json").write_text("not json", encoding="utf-8")
        assert load_snapshot_from_progress(version_dir) is None

    def test_load_snapshot_absent_key_is_none(self, tmp_path: Path) -> None:
        version_dir = tmp_path / "t.1"
        version_dir.mkdir(parents=True)
        (version_dir / "_progress.json").write_text(
            json.dumps({"version": 1, "thread": "t", "phases": {}, "metadata": {}}),
            encoding="utf-8",
        )
        assert load_snapshot_from_progress(version_dir) is None


# ---------------------------------------------------------------------------
# check_evidence_drift — the four required cases from the acceptance criteria
# ---------------------------------------------------------------------------


class TestCheckEvidenceDrift:
    def test_bootstrap_no_snapshot_is_not_drifted(self, tmp_path: Path) -> None:
        result = check_evidence_drift(tmp_path, None)
        assert result.status == STATUS_NO_SNAPSHOT
        assert result.drifted is False

    def test_bootstrap_snapshot_with_both_mtimes_none_is_not_drifted(
        self, tmp_path: Path
    ) -> None:
        result = check_evidence_drift(
            tmp_path, {"brief_mtime": None, "refs_mtime": None}
        )
        assert result.status == STATUS_NO_SNAPSHOT
        assert result.drifted is False

    def test_no_drift_when_unchanged(self, tmp_path: Path) -> None:
        brief = tmp_path / "BRIEF.md"
        _touch(brief, mtime=1000.0)
        snapshot = compute_evidence_snapshot(tmp_path)

        result = check_evidence_drift(tmp_path, snapshot)

        assert result.status == STATUS_CLEAN
        assert result.drifted is False
        assert result.brief_drifted is False
        assert result.refs_drifted is False

    def test_drift_when_brief_touched_after_snapshot(self, tmp_path: Path) -> None:
        brief = tmp_path / "BRIEF.md"
        _touch(brief, mtime=1000.0)
        snapshot = compute_evidence_snapshot(tmp_path)

        _bump(brief, ahead_seconds=10.0)

        result = check_evidence_drift(tmp_path, snapshot)

        assert result.status == STATUS_DRIFT
        assert result.drifted is True
        assert result.brief_drifted is True
        assert result.refs_drifted is False
        assert "BRIEF.md" in result.changed_paths()

    def test_drift_when_refs_file_touched_after_snapshot(self, tmp_path: Path) -> None:
        _touch(tmp_path / "BRIEF.md", mtime=1000.0)
        ref_file = tmp_path / "refs" / "notes.txt"
        _touch(ref_file, mtime=1000.0)
        snapshot = compute_evidence_snapshot(tmp_path)

        _bump(ref_file, ahead_seconds=10.0)

        result = check_evidence_drift(tmp_path, snapshot)

        assert result.status == STATUS_DRIFT
        assert result.drifted is True
        assert result.brief_drifted is False
        assert result.refs_drifted is True
        assert "refs/**" in result.changed_paths()

    def test_drift_when_new_refs_file_added_after_snapshot(self, tmp_path: Path) -> None:
        """A snapshot recorded before ``refs/`` existed (refs_mtime=None)
        must detect drift once a ref file is later added — the "newer
        than recorded" comparison must not treat None-vs-present as clean."""
        _touch(tmp_path / "BRIEF.md", mtime=1000.0)
        snapshot = compute_evidence_snapshot(tmp_path)
        assert snapshot["refs_mtime"] is None

        _touch(tmp_path / "refs" / "new.txt", mtime=time.time())

        result = check_evidence_drift(tmp_path, snapshot)

        assert result.status == STATUS_DRIFT
        assert result.refs_drifted is True

    def test_drift_report_is_advisory_only(self, tmp_path: Path) -> None:
        brief = tmp_path / "BRIEF.md"
        _touch(brief, mtime=1000.0)
        snapshot = compute_evidence_snapshot(tmp_path)
        _bump(brief, ahead_seconds=10.0)

        result = check_evidence_drift(tmp_path, snapshot)

        # No mutation of the thread dir beyond the test's own _bump() call.
        assert brief.is_file()
        # The result carries no verdict/score/critical-flag vocabulary.
        payload = result.to_json()
        for forbidden in ("advance", "critical_flag", "score", "verdict"):
            assert forbidden not in payload

    def test_check_thread_evidence_drift_wrapper(self, tmp_path: Path) -> None:
        thread_dir = tmp_path / "thread"
        version_dir = tmp_path / "thread.1"
        _touch(thread_dir / "BRIEF.md", mtime=1000.0)
        record_evidence_snapshot(thread_dir, version_dir)

        clean = check_thread_evidence_drift(thread_dir, version_dir)
        assert clean.status == STATUS_CLEAN

        _bump(thread_dir / "BRIEF.md", ahead_seconds=10.0)
        drifted = check_thread_evidence_drift(thread_dir, version_dir)
        assert drifted.status == STATUS_DRIFT


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_record_subcommand_writes_progress_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        thread_dir = tmp_path / "thread"
        version_dir = tmp_path / "thread.1"
        _touch(thread_dir / "BRIEF.md", mtime=123.0)

        rc = main(["record", str(thread_dir), str(version_dir)])

        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["brief_mtime"] == pytest.approx(123.0)
        progress = json.loads((version_dir / "_progress.json").read_text())
        assert progress["metadata"]["evidence_snapshot"] == out

    def test_check_subcommand_exits_zero_even_when_drifted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        thread_dir = tmp_path / "thread"
        version_dir = tmp_path / "thread.1"
        brief = thread_dir / "BRIEF.md"
        _touch(brief, mtime=1000.0)
        record_evidence_snapshot(thread_dir, version_dir)
        _bump(brief, ahead_seconds=10.0)

        rc = main(["check", str(thread_dir), str(version_dir)])

        assert rc == 0  # advisory tool — never a nonzero gate signal
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == STATUS_DRIFT
        assert out["drifted"] is True

    def test_check_subcommand_bootstrap_case(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        thread_dir = tmp_path / "thread"
        version_dir = tmp_path / "thread.1"
        version_dir.mkdir(parents=True)
        thread_dir.mkdir(parents=True)

        rc = main(["check", str(thread_dir), str(version_dir)])

        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == STATUS_NO_SNAPSHOT
        assert out["drifted"] is False

    def test_help_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
