"""Regression test: ``install-anvil.sh`` must auto-proceed when stdin is not a TTY.

Issue #544: invoking the installer without ``--yes`` from an agent shell, CI
pipeline, or any context where stdin is redirected (`</dev/null`) used to
silently abort with exit 1. Under ``set -euo pipefail`` (line 77 of the
installer), the interactive ``read -r -p "Proceed? [y/N] "`` at the
confirmation prompt hit EOF, returned nonzero, and ``set -e`` aborted the
script *before* the ``|| { info "cancelled"; exit 0; }`` branch could fire.
The user-visible symptom was an install that printed the "About to install"
preamble and then died with no diagnostic.

The fix mirrors ``install-loom.sh:285-293``: after argument parsing, detect
``[[ ! -t 0 ]]`` (stdin is not a TTY) and treat it as an implicit ``--yes``.
The explicit ``--yes`` flag remains the escape hatch for TTY sessions that
want to skip the prompt; when ``--yes`` is set the auto-detect note is
suppressed (since the user already opted in explicitly).

These tests exercise the installer end-to-end via ``subprocess`` so the
regression is caught at the real entry point a consumer / wrapping agent
would hit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _assert_install_artifacts(target: Path) -> None:
    """Common post-install structural checks (mirrors test_install_quoting)."""

    assert (target / ".anvil" / "anvil" / "lib").is_dir()
    assert (target / ".anvil" / "anvil" / "__init__.py").is_file()
    assert (target / ".anvil" / "pyproject.toml").is_file()
    assert (target / ".anvil" / "roles").is_dir()
    assert (target / ".anvil" / "skills" / "memo" / "SKILL.md").is_file()
    assert (target / ".anvil" / "install-metadata.json").is_file()
    assert (target / ".claude" / "skills" / "anvil-memo" / "SKILL.md").is_file()
    assert (target / "CLAUDE.md").is_file()


def test_install_succeeds_with_non_tty_stdin(tmp_path: Path) -> None:
    """Bare ``install-anvil.sh <target> </dev/null`` (no ``--yes``) must succeed.

    Pre-fix repro on main (commit 9c936d7)::

        $ bash scripts/install-anvil.sh /tmp/anvil-bug-repro </dev/null
        > Stage 1: resolve ANVIL_ROOT
        ...
        About to install Anvil v0.6.0 into: /tmp/anvil-bug-repro
        Skills: ...
        Mode: fresh
        $ echo $?
        1
        $ ls /tmp/anvil-bug-repro    # empty — install died at the read prompt

    Post-fix: the auto-detect block flips ``NON_INTERACTIVE=true`` before the
    confirmation prompt is reached, the prompt is skipped, and the install
    completes with returncode 0 and every expected artifact in place.

    Also asserts the auto-detect note prints, so a future regression that
    silently removes the diagnostic (regressing to a "succeeds but no
    explanation" state) is still caught.
    """

    target = tmp_path / "non-tty-target"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
    )

    assert result.returncode == 0, (
        f"install failed under non-TTY stdin (no --yes):\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    # Regression guard: the diagnostic must print so wrapping agents / CI
    # logs surface *why* the installer auto-proceeded. The exact wording is
    # not part of the contract — we only assert the load-bearing phrase.
    assert "stdin is not a TTY" in result.stdout, (
        f"auto-detect note missing from stdout:\n{result.stdout}"
    )
    _assert_install_artifacts(target)


def test_install_explicit_yes_with_non_tty_stdin(tmp_path: Path) -> None:
    """Regression: explicit ``--yes`` still works (and suppresses the note).

    The ``--yes`` flag was set before the auto-detect block, so the guard
    ``[[ "$NON_INTERACTIVE" != true ]]`` is what keeps the note from firing
    on top of an explicit opt-in. We assert exit 0 (the pre-fix green path
    is preserved) and that the auto-detect note is *not* printed, so a
    future "always print the note" regression is caught here.
    """

    target = tmp_path / "explicit-yes-target"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--yes", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
    )

    assert result.returncode == 0, (
        f"install failed with --yes under non-TTY stdin:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "stdin is not a TTY" not in result.stdout, (
        "auto-detect note should be suppressed when --yes is explicit:\n"
        f"{result.stdout}"
    )
    _assert_install_artifacts(target)
