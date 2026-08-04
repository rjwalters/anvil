"""Regression tests: installer ships a self-contained ``.anvil/.gitignore`` (#674).

Every consumer command that runs ``uv run --project .anvil ...`` (each critic
that imports ``anvil.lib.*``) leaves ``__pycache__/*.pyc`` bytecode caches under
the ``.anvil/anvil/`` mirror, and the Stage 10.5 ``uv sync`` creates a venv at
``.anvil/.venv/`` *and* — because the consumer ``.anvil/pyproject.toml``
declares ``build-backend = "setuptools.build_meta"``, so the sync is an editable
install — a ``.anvil/anvil.egg-info/`` metadata directory (#877). Without ignore
coverage those artifacts dirty ``git status`` in every worktree, every time.
Stage 8.6 writes a self-contained ``.anvil/.gitignore`` (patterns
``__pycache__/``, ``*.py[cod]``, ``.venv/``, ``*.egg-info/``) so they never show
up as untracked.

The write contract (deliberately distinct from the Stage 7.9 voice-grounding
append):

  * **Self-contained** — the patterns live in ``.anvil/.gitignore``, an
    installer-owned generated file; the consumer's root ``.gitignore`` is never
    touched (that append helper is reserved for the voice-grounding posture).
  * **Unconditional** — fires on every install regardless of ``--skills=``
    selection (unlike the skill-gated voice patterns), since every install
    creates the ``.anvil/anvil/`` mirror and the ``.anvil/.venv`` target.
  * **Skip-if-exists** — matching the Stage 7.8 starter-theme convention: the
    file is written once and a consumer hand-edit is never clobbered.
  * **Append-only reconciliation** (#877) — a pattern added to the template
    after a given install shipped is appended to the existing file if missing,
    never duplicated and never at the cost of rewriting the file. Covered in
    detail by ``test_install_anvil_gitignore_tracked_hint.py``.
  * **``--dry-run`` aware** — reports the would-write and writes nothing.

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point. Distinct filename per the #58 packaging
convention (sibling to ``test_install_voice_gitignore.py`` /
``test_install_uv_runnable.py``).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

EXPECTED_PATTERNS = ("__pycache__/", "*.py[cod]", ".venv/", "*.egg-info/")


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


def _tools_present() -> bool:
    """Both ``uv`` and ``git`` are required for the end-to-end sync assertion."""
    return shutil.which("uv") is not None and shutil.which("git") is not None


def _gitignore_lines(gi: Path) -> list[str]:
    if not gi.is_file():
        return []
    return [
        line.strip()
        for line in gi.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# ---------------------------------------------------------------------------
# Fresh install writes the file with the expected patterns
# ---------------------------------------------------------------------------


def test_fresh_install_writes_anvil_gitignore(tmp_path: Path) -> None:
    """A fresh install creates ``.anvil/.gitignore`` with all runtime patterns."""
    target = tmp_path / "fresh"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    gi = target / ".anvil" / ".gitignore"
    assert gi.is_file(), (
        f"installer did not write .anvil/.gitignore; stdout:\n{result.stdout}"
    )
    lines = _gitignore_lines(gi)
    for pat in EXPECTED_PATTERNS:
        assert pat in lines, (
            f"missing pattern {pat!r} in .anvil/.gitignore: {lines}"
        )


def test_write_is_unconditional_across_skill_selections(tmp_path: Path) -> None:
    """The write is unconditional — it fires regardless of --skills= selection.

    Unlike the skill-gated voice patterns, the .anvil/.gitignore must appear
    for a non-voice skill selection too (every install creates the Python
    mirror + venv target).
    """
    for skills in ("--skills=memo", "--skills=paper", "--skills=essay"):
        target = tmp_path / skills.replace("=", "_").replace("--", "")
        target.mkdir()

        result = _run(skills, str(target))
        _assert_ok(result)

        gi = target / ".anvil" / ".gitignore"
        assert gi.is_file(), (
            f"{skills}: .anvil/.gitignore not written (should be unconditional); "
            f"stdout:\n{result.stdout}"
        )
        lines = _gitignore_lines(gi)
        for pat in EXPECTED_PATTERNS:
            assert pat in lines, f"{skills}: missing {pat!r}: {lines}"


# ---------------------------------------------------------------------------
# Idempotent re-install preserves a consumer hand-edit (skip-if-exists)
# ---------------------------------------------------------------------------


def test_reinstall_preserves_consumer_hand_edit(tmp_path: Path) -> None:
    """A re-install must not clobber a consumer-customized .anvil/.gitignore."""
    target = tmp_path / "hand-edited"
    target.mkdir()

    # First install writes the canonical file.
    _assert_ok(_run("--skills=memo", str(target)))
    gi = target / ".anvil" / ".gitignore"
    assert gi.is_file()

    # Consumer adds a local pattern of their own.
    hand_edited = gi.read_text(encoding="utf-8") + "\n# local addition\nscratch/\n"
    gi.write_text(hand_edited, encoding="utf-8")

    # Re-install must leave the hand-edit untouched (skip-if-exists).
    second = _run("--skills=memo", str(target))
    _assert_ok(second)

    assert gi.read_text(encoding="utf-8") == hand_edited, (
        "re-install clobbered the consumer's hand-edited .anvil/.gitignore"
    )
    assert "scratch/" in _gitignore_lines(gi), "consumer's local pattern was lost"
    # The skip note fires on the re-run.
    assert "existing .anvil/.gitignore detected" in second.stdout, (
        f"expected the skip-if-exists note on re-install; got:\n{second.stdout}"
    )


# ---------------------------------------------------------------------------
# Root .gitignore is untouched (monorepo-coexistence contract)
# ---------------------------------------------------------------------------


def test_root_gitignore_untouched_for_non_voice_skill(tmp_path: Path) -> None:
    """The consumer's root .gitignore is not written for a non-voice install.

    Only .anvil/.gitignore should be created; the root .gitignore write footprint
    is unaffected by this change (Stage 7.9 voice append is skill-gated and does
    not fire for a non-voice skill).

    NOTE: the skill here must be neither voice-consuming (essay/memo — Stage 7.9)
    nor vision-capable (paper/report/deck/slides — Stage 7.10, issue #738), since
    both of those stages DO append to the root .gitignore. ``proposal`` is
    neither, so it exercises the Stage 8.6 self-contained-write contract in
    isolation.
    """
    target = tmp_path / "root-untouched"
    target.mkdir()

    result = _run("--skills=proposal", str(target))
    _assert_ok(result)

    assert (target / ".anvil" / ".gitignore").is_file(), (
        ".anvil/.gitignore should be written unconditionally"
    )
    assert not (target / ".gitignore").exists(), (
        "installer wrote a root .gitignore for a non-voice install; "
        "the Stage 8.6 write must be self-contained under .anvil/"
    )


# ---------------------------------------------------------------------------
# --dry-run honesty (issue #81)
# ---------------------------------------------------------------------------


def test_dry_run_reports_and_writes_nothing(tmp_path: Path) -> None:
    """``--dry-run`` reports the would-write and writes no .anvil/.gitignore."""
    target = tmp_path / "dry-run"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=memo", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    assert "[dry-run] write .anvil/.gitignore" in result.stdout, (
        f"expected the dry-run write action line; got:\n{result.stdout}"
    )
    assert not (target / ".anvil" / ".gitignore").exists(), (
        "--dry-run wrote a .anvil/.gitignore to the target"
    )


# ---------------------------------------------------------------------------
# End-to-end: install + `uv sync` leaves `git status` clean (#877)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _tools_present(), reason="uv and/or git not on PATH")
def test_install_with_sync_then_commit_leaves_git_status_clean(tmp_path: Path) -> None:
    """The property the ignore file and the README both promise.

    Reproduces the reported sequence exactly: install (Stage 10.5 runs
    ``uv sync --project .anvil`` itself), then ``git add -A`` + commit, then
    re-sync. ``uv sync`` performs an *editable* install of the consumer project
    (``.anvil/pyproject.toml`` declares
    ``build-backend = "setuptools.build_meta"``), which materializes
    ``.anvil/anvil.egg-info/`` alongside the venv and the bytecode caches.
    Before #877 the ignore file covered only two of those three artifact
    classes, so the ``git add -A`` swept five egg-info build artifacts into the
    consumer's install commit.

    Scope note: ``uv sync`` also writes ``.anvil/uv.lock``. That is a resolved
    *lockfile*, not a regenerated build artifact — it is written once and stays
    stable, so committing it with the install (as this test does) is the normal
    outcome and it is deliberately NOT part of the ignore set.
    """
    target = tmp_path / "sync-clean"
    target.mkdir()

    subprocess.run(["git", "-C", str(target), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(target), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(target), "config", "user.name", "Test"], check=True
    )

    # NOTE: no --no-sync here — Stage 10.5's `uv sync` is what generates the
    # artifacts under test.
    install = subprocess.run(
        ["bash", str(INSTALLER), "-y", "--skills=memo", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(install)

    # The egg-info directory is genuinely produced — otherwise this test would
    # pass vacuously if a future uv/setuptools change stopped emitting it.
    egg_infos = list((target / ".anvil").glob("*.egg-info"))
    assert egg_infos, (
        "the install's uv sync produced no *.egg-info/ under .anvil/ — the "
        "regression this test guards is no longer reproducible; revisit the "
        f"fixture. Installer output:\n{install.stdout}"
    )

    subprocess.run(["git", "-C", str(target), "add", "-A"], check=True)

    # The reported symptom: build artifacts staged into the install commit.
    staged = subprocess.run(
        ["git", "-C", str(target), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    swept = [p for p in staged if ".egg-info/" in p]
    assert not swept, (
        "`git add -A` after an install staged egg-info build artifacts; "
        f".anvil/.gitignore must suppress them:\n{swept}"
    )

    subprocess.run(
        ["git", "-C", str(target), "commit", "-q", "-m", "install anvil"], check=True
    )

    # A subsequent sync must leave the tree clean, too.
    sync = subprocess.run(
        ["uv", "sync", "--project", ".anvil"],
        capture_output=True,
        text=True,
        cwd=target,
    )
    assert sync.returncode == 0, (
        f"uv sync failed:\n--- stdout ---\n{sync.stdout}\n"
        f"--- stderr ---\n{sync.stderr}"
    )

    status = subprocess.run(
        ["git", "-C", str(target), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout.strip() == "", (
        "uv sync dirtied git status in the consumer repo; the .anvil/.gitignore "
        f"patterns do not cover everything the sync generates:\n{status.stdout}"
    )
