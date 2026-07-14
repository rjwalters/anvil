"""Regression tests: installer ships a self-contained ``.anvil/.gitignore`` (#674).

Every consumer command that runs ``uv run --project .anvil ...`` (each critic
that imports ``anvil.lib.*``) leaves ``__pycache__/*.pyc`` bytecode caches under
the ``.anvil/anvil/`` mirror, and the Stage 10.5 ``uv sync`` creates a venv at
``.anvil/.venv/``. Without ignore coverage those artifacts dirty ``git status``
in every worktree, every time. Stage 8.6 writes a self-contained
``.anvil/.gitignore`` (patterns ``__pycache__/``, ``*.py[cod]``, ``.venv/``) so
they never show up as untracked.

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
  * **``--dry-run`` aware** — reports the would-write and writes nothing.

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point. Distinct filename per the #58 packaging
convention (sibling to ``test_install_voice_gitignore.py`` /
``test_install_uv_runnable.py``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

EXPECTED_PATTERNS = ("__pycache__/", "*.py[cod]", ".venv/")


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
    not fire for paper).
    """
    target = tmp_path / "root-untouched"
    target.mkdir()

    result = _run("--skills=paper", str(target))
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
