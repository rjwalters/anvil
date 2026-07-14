"""Regression tests: installer reconciles already-tracked ignored files (#684).

Stage 8.6 (#674/#683) ships a self-contained ``.anvil/.gitignore`` suppressing
the Python runtime artifacts the ``.anvil/`` footprint generates
(``__pycache__/``, ``*.py[cod]``, ``.venv/``). That write is correct and
sufficient for **fresh** installs — nothing under ``.anvil/`` is tracked yet, so
the ignore patterns keep those artifacts out of ``git status`` forever.

It has **no effect on upgrades from a pre-0.8.0 install** that already
``git add``ed the ``.anvil/`` tree before ``.gitignore`` existed. Git's
``.gitignore`` only suppresses *untracked* paths — an already-tracked path keeps
showing up as ``modified`` every time its content changes (which is every
``uv run --project .anvil ...`` invocation, since that regenerates
``__pycache__/*.pyc``). The tractatus canary hit this directly.

Stage 8.6b (#684) closes the gap: after writing ``.anvil/.gitignore`` it detects
tracked files under ``.anvil/`` that the ignore rules would suppress and, by
default, prints a ``warn`` + exact ``git rm -r --cached`` remediation ``note``
(consumer git state is consumer-owned — anvil never commits on the consumer's
behalf). The opt-in ``--fix-tracked`` flag performs the ``git rm -r --cached``
(index-only; never commits, never touches the working-tree files).

Contract exercised here:

  * **Warn + hint by default** on a pre-tracked ``.pyc`` / ``.venv`` tree,
    listing the actual matched paths and the exact remediation command.
  * **Silent on fresh installs** — nothing tracked ⇒ no warning.
  * **``--fix-tracked``** untracks (index-only) and reports a count, without
    creating a commit.
  * **``--fix-tracked --dry-run``** reports the would-untrack and mutates
    neither the index nor the working tree.
  * **Forge-optional no-op** — a target with no ``.git`` installs cleanly with
    no git invocation and no error.
  * **Pattern-derivation-from-file** — detection reads ``.anvil/.gitignore``'s
    own content (via ``git check-ignore``), not a second hard-coded pattern
    list, so a consumer-added pattern is honored too.

These tests exercise the installer via ``subprocess`` at the real entry point.
Distinct filename per the #58 packaging convention (sibling to
``test_install_anvil_gitignore.py``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"installer exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def _git(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(target), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    _git(target, "init", "-q")
    # Deterministic identity so `git commit` never falls back to a missing
    # global config on a bare CI host.
    _git(target, "config", "user.email", "test@example.com")
    _git(target, "config", "user.name", "Test")


def _seed_pre_080_install(
    target: Path,
    *,
    pyc: bool = True,
    venv: bool = True,
) -> list[str]:
    """Commit runtime artifacts under .anvil/ BEFORE any .anvil/.gitignore.

    Simulates a consumer who installed anvil under <=0.7.1 and committed the
    .anvil/ tree before #674/#683 shipped the ignore file. Returns the list of
    committed artifact paths (repo-relative, forward-slash).
    """
    seeded: list[str] = []
    if pyc:
        pyc_path = target / ".anvil" / "anvil" / "lib" / "__pycache__" / "foo.cpython-311.pyc"
        pyc_path.parent.mkdir(parents=True, exist_ok=True)
        pyc_path.write_bytes(b"\x00fake-bytecode\x00")
        seeded.append(".anvil/anvil/lib/__pycache__/foo.cpython-311.pyc")
    if venv:
        venv_cfg = target / ".anvil" / ".venv" / "pyvenv.cfg"
        venv_cfg.parent.mkdir(parents=True, exist_ok=True)
        venv_cfg.write_text("home = /usr/bin\n", encoding="utf-8")
        seeded.append(".anvil/.venv/pyvenv.cfg")

    # Force-add: if a .anvil/.gitignore already exists on disk (upgrade
    # scenario), a plain ``git add`` would skip these already-ignored paths.
    # A pre-0.8.0 consumer committed them *before* any ignore file, so -f
    # faithfully reproduces the tracked-despite-ignored state under test.
    _git(target, "add", "-A")
    if seeded:
        _git(target, "add", "-f", *[str(target / p) for p in seeded])
    _git(target, "commit", "-q", "-m", "pre-0.8.0 install (committed .anvil tree)")
    return seeded


def _tracked(target: Path) -> set[str]:
    out = _git(target, "ls-files").stdout
    return {line for line in out.splitlines() if line}


# ---------------------------------------------------------------------------
# Default: warn + exact remediation hint on a pre-tracked tree
# ---------------------------------------------------------------------------


def test_pre_tracked_artifacts_trigger_warn_and_hint(tmp_path: Path) -> None:
    """A pre-0.8.0 committed .pyc/.venv tree fires a warn + git rm remediation."""
    target = tmp_path / "pre-tracked"
    _init_repo(target)
    _seed_pre_080_install(target)

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    combined = result.stdout + result.stderr
    assert "tracked file(s) under .anvil/ match the new .gitignore patterns" in combined, (
        f"expected the tracked-files warn; got:\n{combined}"
    )
    # The exact remediation command is printed, scoped to actual paths.
    assert "git rm -r --cached --" in combined, (
        f"expected the git rm -r --cached remediation hint; got:\n{combined}"
    )
    assert ".anvil/anvil/lib/__pycache__/foo.cpython-311.pyc" in combined, (
        f"remediation hint should list the actual tracked .pyc path; got:\n{combined}"
    )
    assert "--fix-tracked" in combined, (
        f"hint should mention the --fix-tracked opt-in; got:\n{combined}"
    )

    # Default (no --fix-tracked) must NOT mutate the index — the artifacts stay
    # tracked.
    tracked = _tracked(target)
    assert ".anvil/anvil/lib/__pycache__/foo.cpython-311.pyc" in tracked, (
        "default detection pass must not untrack anything without --fix-tracked"
    )


# ---------------------------------------------------------------------------
# Fresh install (nothing tracked) is silent
# ---------------------------------------------------------------------------


def test_fresh_install_is_silent(tmp_path: Path) -> None:
    """A fresh git repo (nothing under .anvil/ tracked) prints no tracked warn."""
    target = tmp_path / "fresh"
    _init_repo(target)

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    combined = result.stdout + result.stderr
    assert "tracked file(s) under .anvil/ match" not in combined, (
        f"detection must be silent when nothing is tracked; got:\n{combined}"
    )


# ---------------------------------------------------------------------------
# --fix-tracked untracks (index-only) and does NOT commit
# ---------------------------------------------------------------------------


def test_fix_tracked_untracks_index_only_no_commit(tmp_path: Path) -> None:
    """--fix-tracked runs git rm --cached and creates no commit."""
    target = tmp_path / "fix-tracked"
    _init_repo(target)
    seeded = _seed_pre_080_install(target)
    head_before = _git(target, "rev-parse", "HEAD").stdout.strip()

    result = _run("--fix-tracked", "--skills=memo", str(target))
    _assert_ok(result)

    combined = result.stdout + result.stderr
    assert "untracked" in combined and "runtime artifact" in combined, (
        f"expected the untracked-count report; got:\n{combined}"
    )

    # Index: the seeded artifacts are no longer tracked.
    tracked = _tracked(target)
    for path in seeded:
        assert path not in tracked, (
            f"--fix-tracked did not untrack {path}; still in index:\n{sorted(tracked)}"
        )

    # No commit was created — HEAD is unchanged.
    head_after = _git(target, "rev-parse", "HEAD").stdout.strip()
    assert head_after == head_before, (
        "--fix-tracked created a commit; anvil must never commit on the "
        "consumer's behalf"
    )

    # Working-tree files survive (--cached is index-only, so they stay on disk
    # and stay ignored going forward).
    assert (target / ".anvil" / ".venv" / "pyvenv.cfg").is_file(), (
        "--fix-tracked (git rm --cached) must not delete the working-tree file"
    )


# ---------------------------------------------------------------------------
# --fix-tracked --dry-run mutates nothing
# ---------------------------------------------------------------------------


def test_fix_tracked_dry_run_mutates_nothing(tmp_path: Path) -> None:
    """--fix-tracked --dry-run reports the would-untrack and mutates nothing."""
    target = tmp_path / "fix-tracked-dry"
    _init_repo(target)
    # Under --dry-run the installer does not WRITE .anvil/.gitignore, so seed a
    # committed one (an upgrade from a prior 0.8.0 install) — detection derives
    # its patterns from the on-disk file, which under --dry-run is only this
    # pre-existing one. The tracked artifacts are what we assert stay tracked.
    (target / ".anvil").mkdir(parents=True, exist_ok=True)
    (target / ".anvil" / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.venv/\n", encoding="utf-8"
    )
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", "prior 0.8.0 install: .anvil/.gitignore")
    seeded = _seed_pre_080_install(target)

    result = subprocess.run(
        [
            "bash",
            str(INSTALLER),
            "--dry-run",
            "--fix-tracked",
            "--skills=memo",
            str(target),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    combined = result.stdout + result.stderr
    assert "[dry-run] git rm -r --cached" in combined, (
        f"expected the dry-run git rm action line; got:\n{combined}"
    )

    # Index untouched — the artifacts stay tracked under --dry-run.
    tracked = _tracked(target)
    for path in seeded:
        assert path in tracked, (
            f"--fix-tracked --dry-run untracked {path}; it must mutate nothing"
        )
    # The working-tree artifacts are also left in place.
    assert (target / ".anvil" / ".venv" / "pyvenv.cfg").is_file(), (
        "--dry-run must not delete the working-tree artifact"
    )


# ---------------------------------------------------------------------------
# Forge-optional: no .git → graceful no-op, no error
# ---------------------------------------------------------------------------


def test_non_git_target_no_op(tmp_path: Path) -> None:
    """A target with no .git installs cleanly; detection is skipped entirely."""
    target = tmp_path / "no-git"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    combined = result.stdout + result.stderr
    assert "tracked file(s) under .anvil/ match" not in combined, (
        f"non-git target must not surface a tracked-files warn; got:\n{combined}"
    )
    assert "fatal:" not in combined, (
        f"non-git target must not surface a git error; got:\n{combined}"
    )
    assert not (target / ".git").exists(), "test setup should have left no .git"


# ---------------------------------------------------------------------------
# --fix-tracked on a non-git target is also a graceful no-op
# ---------------------------------------------------------------------------


def test_fix_tracked_non_git_target_no_op(tmp_path: Path) -> None:
    """--fix-tracked against a non-git target does not error (nothing to fix)."""
    target = tmp_path / "no-git-fix"
    target.mkdir()

    result = _run("--fix-tracked", "--skills=memo", str(target))
    _assert_ok(result)

    combined = result.stdout + result.stderr
    assert "fatal:" not in combined, (
        f"--fix-tracked on a non-git target must not error; got:\n{combined}"
    )


# ---------------------------------------------------------------------------
# Only .venv tracked (no .pyc) — edge case from the test plan
# ---------------------------------------------------------------------------


def test_only_venv_tracked(tmp_path: Path) -> None:
    """A tree with only .venv/ tracked (no .pyc) still triggers the hint."""
    target = tmp_path / "venv-only"
    _init_repo(target)
    _seed_pre_080_install(target, pyc=False, venv=True)

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    combined = result.stdout + result.stderr
    assert "tracked file(s) under .anvil/ match" in combined, (
        f"a .venv-only tracked tree should trigger the warn; got:\n{combined}"
    )
    assert ".anvil/.venv/pyvenv.cfg" in combined, (
        f"hint should list the tracked .venv path; got:\n{combined}"
    )


# ---------------------------------------------------------------------------
# Pattern derivation reads the file: a consumer-added pattern is honored
# ---------------------------------------------------------------------------


def test_detection_honors_consumer_added_pattern(tmp_path: Path) -> None:
    """Detection derives from .anvil/.gitignore's content, not a fixed list.

    A consumer hand-edit that adds a local pattern (e.g. ``scratch/``) is
    honored by the detection pass, proving it reads the file rather than a
    hard-coded ``__pycache__ | *.py[cod] | .venv`` list. We pre-create the
    .anvil/.gitignore WITH the extra pattern (skip-if-exists preserves it),
    commit a file matching only that extra pattern, and assert the hint fires
    for it.
    """
    target = tmp_path / "consumer-pattern"
    _init_repo(target)

    # Consumer-owned .anvil/.gitignore including a local pattern, plus a tracked
    # file matching ONLY that local pattern (not the three canonical ones).
    gi = target / ".anvil" / ".gitignore"
    gi.parent.mkdir(parents=True, exist_ok=True)
    gi.write_text(
        "__pycache__/\n*.py[cod]\n.venv/\n# local addition\nscratch/\n",
        encoding="utf-8",
    )
    scratch_file = target / ".anvil" / "scratch" / "note.txt"
    scratch_file.parent.mkdir(parents=True, exist_ok=True)
    scratch_file.write_text("local scratch\n", encoding="utf-8")
    _git(target, "add", "-A")
    # Force-add the scratch file: the .anvil/.gitignore we just wrote already
    # lists ``scratch/``, so a plain ``git add`` would silently skip it. A
    # pre-0.8.0 consumer committed the artifact *before* adding the ignore
    # pattern, which is exactly the tracked-despite-ignored state under test.
    _git(target, "add", "-f", str(scratch_file))
    _git(target, "commit", "-q", "-m", "consumer hand-edit + tracked scratch file")

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    combined = result.stdout + result.stderr
    assert ".anvil/scratch/note.txt" in combined, (
        "detection must honor a consumer-added .gitignore pattern (proves it "
        f"reads the file, not a hard-coded list); got:\n{combined}"
    )
