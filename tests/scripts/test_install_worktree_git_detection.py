"""Regression tests: installer git detection handles linked worktrees (#1456).

``install-anvil.sh`` used ``[[ -d "$TARGET/.git" ]]``, which is false in a
linked worktree (``.git`` is a file). Stage 2 then printed a wrong "not a git
repository" note and the tracked-ignored pass was skipped.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = REPO_ROOT / "scripts" / "install-anvil.sh"
NOTE = "target is not a git repository"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def _install(target: Path) -> str:
    r = subprocess.run(
        ["bash", str(INSTALL), "--yes", "--dry-run", str(target)],
        capture_output=True, text=True,
    )
    return r.stdout + r.stderr


def test_linked_worktree_not_reported_as_non_git(tmp_path: Path) -> None:
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "commit", "-q", "--allow-empty", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wt-branch")
    assert (wt / ".git").is_file()
    assert NOTE not in _install(wt)


def test_plain_directory_still_gets_note(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert NOTE in _install(plain)


def test_regular_repo_no_note(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    assert NOTE not in _install(repo)
