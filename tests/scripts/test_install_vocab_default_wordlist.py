"""Regression tests: installer ships the vocab_reminder default word list.

Issue #800: ``anvil/lib/vocab_reminder.py``'s ``DEFAULT_WORD_LIST_PATH`` is
computed relative to ``__file__`` as
``<lib>/../templates/voice/vocab.words.txt`` — a path that resolves
correctly in the dev tree (``anvil/lib/../templates/voice/vocab.words.txt``
== ``anvil/templates/voice/vocab.words.txt``) but is dead on arrival in an
installed consumer repo, where the module lives at
``.anvil/anvil/lib/vocab_reminder.py`` and the same relative math resolves
to ``.anvil/anvil/templates/voice/vocab.words.txt`` — a destination
``install-anvil.sh`` never populated pre-#800 (Stage 5 copied only
``anvil/lib``; Stage 7.9 scaffolds the same source file to a *different*,
consumer-owned destination, ``.anvil/voice/VOCABULARY.words.txt``, and only
when ``essay``/``memo`` is selected).

The fix: Stage 5 gains one narrow, unconditional copy —
``anvil/templates/voice/vocab.words.txt`` ->
``.anvil/anvil/templates/voice/vocab.words.txt`` — mirroring the
"importable mirror, always refreshed" discipline already used for
``anvil/lib -> .anvil/anvil/lib``, rather than a whole-``anvil/templates``
mirror (the ``themes/`` and ``voice/`` subtrees already have their own
dedicated consumer-facing scaffold stages).

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point a consumer hits. Pattern mirrors
``test_install_theme_scaffold.py`` (single-asset copy assertions) and
``test_install_dry_run_honesty.py`` (dry-run assertion pattern). Distinct
filename per the #58 packaging convention.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from anvil.lib.testing import assert_ok as _assert_ok

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

DEFAULT_WORD_LIST_SRC = REPO_ROOT / "anvil" / "templates" / "voice" / "vocab.words.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the installer with ``args`` and capture text stdout+stderr.

    ``--no-sync`` keeps the tests independent of ``uv`` availability and
    fast for the copy-only assertions; the end-to-end CLI assertion below
    opts into a real ``uv sync`` separately.
    """

    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _uv_present() -> bool:
    import shutil

    return shutil.which("uv") is not None


def _sanitized_env() -> dict[str, str]:
    """Strip any REPO_ROOT entry from PYTHONPATH (see test_install_uv_runnable.py)."""

    env = dict(os.environ)
    pythonpath = env.get("PYTHONPATH", "")
    if pythonpath:
        keep = [
            part
            for part in pythonpath.split(os.pathsep)
            if part and not part.startswith(str(REPO_ROOT))
        ]
        if keep:
            env["PYTHONPATH"] = os.pathsep.join(keep)
        else:
            env.pop("PYTHONPATH", None)
    return env


# ---------------------------------------------------------------------------
# Source-tree shape
# ---------------------------------------------------------------------------


def test_source_default_word_list_exists() -> None:
    assert DEFAULT_WORD_LIST_SRC.is_file(), (
        f"missing shipped default word list: {DEFAULT_WORD_LIST_SRC}"
    )


# ---------------------------------------------------------------------------
# Fresh install ships the file into the importable mirror
# ---------------------------------------------------------------------------


def test_fresh_install_ships_default_word_list_into_lib_mirror(
    tmp_path: Path,
) -> None:
    """Any fresh install populates .anvil/anvil/templates/voice/vocab.words.txt.

    Unconditional — not gated on ``essay``/``memo`` selection, unlike Stage
    7.9's consumer-owned scaffold. ``--skills=help`` selects neither.
    """

    target = tmp_path / "fresh-target"
    target.mkdir()

    result = _run("--skills=help", str(target))
    _assert_ok(result)

    dst = target / ".anvil" / "anvil" / "templates" / "voice" / "vocab.words.txt"
    assert dst.is_file(), (
        f"fresh install did not ship the default word list to {dst}; "
        f"stdout:\n{result.stdout}"
    )
    assert dst.read_text(encoding="utf-8") == DEFAULT_WORD_LIST_SRC.read_text(
        encoding="utf-8"
    ), "installed default word list differs from the shipped source (byte-identity)"


def test_ships_regardless_of_essay_memo_selection(tmp_path: Path) -> None:
    """The copy is unconditional — it must not depend on Stage 7.9 firing.

    Confirms the fix is independent of the consumer-owned voice scaffold:
    ``.anvil/voice/`` (Stage 7.9's destination) is absent for a skill
    selection that excludes essay/memo, while the importable-mirror copy
    (Stage 5) still lands.
    """

    target = tmp_path / "no-voice-scaffold-target"
    target.mkdir()

    result = _run("--skills=help", str(target))
    _assert_ok(result)

    assert not (target / ".anvil" / "voice").exists(), (
        "test assumption violated: --skills=help unexpectedly scaffolded "
        ".anvil/voice/ (Stage 7.9 should be skill-gated to essay/memo)"
    )
    dst = target / ".anvil" / "anvil" / "templates" / "voice" / "vocab.words.txt"
    assert dst.is_file(), (
        "the importable-mirror copy must not depend on the essay/memo-gated "
        f"Stage 7.9 voice scaffold; stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# --dry-run honesty (issue #81)
# ---------------------------------------------------------------------------


def test_dry_run_reports_copy_and_writes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "dry-run-target"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=help", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    assert "[dry-run] install" in result.stdout and "vocab.words.txt" in result.stdout, (
        "expected a '[dry-run] install .../vocab.words.txt ...' action line; "
        f"got:\n{result.stdout}"
    )
    assert not (target / ".anvil").exists(), "--dry-run wrote .anvil/ to the target"


# ---------------------------------------------------------------------------
# Idempotent re-install
# ---------------------------------------------------------------------------


def test_reinstall_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "reinstall-target"
    target.mkdir()

    first = _run("--skills=help", str(target))
    _assert_ok(first)
    second = _run("--skills=help", str(target))
    _assert_ok(second)

    dst = target / ".anvil" / "anvil" / "templates" / "voice" / "vocab.words.txt"
    assert dst.is_file()
    assert dst.read_text(encoding="utf-8") == DEFAULT_WORD_LIST_SRC.read_text(
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# End-to-end: the documented zero-config fallback actually works
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _uv_present(), reason="uv not on PATH")
def test_vocab_reminder_cli_works_post_install_with_no_brief(
    tmp_path: Path,
) -> None:
    """The exact repro from issue #800: works out of the box, no BRIEF.md.

    ``python -m anvil.lib.vocab_reminder`` before any project ``BRIEF.md``
    exists must fall through to the shipped default and print a sample —
    not ``no words available to sample`` / exit 1.
    """

    target = tmp_path / "cli-target"
    target.mkdir()

    install = _run("--skills=memo,help", str(target))
    _assert_ok(install)

    env = _sanitized_env()
    sync = subprocess.run(
        ["uv", "sync", "--project", ".anvil"],
        capture_output=True,
        text=True,
        cwd=target,
        env=env,
    )
    assert sync.returncode == 0, (
        f"uv sync failed at {target!r}:\n"
        f"--- stdout ---\n{sync.stdout}\n--- stderr ---\n{sync.stderr}"
    )

    invoke = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            ".anvil",
            "python",
            "-m",
            "anvil.lib.vocab_reminder",
            "5",
            "--project-dir",
            ".",
            "--seed",
            "42",
        ],
        capture_output=True,
        text=True,
        cwd=target,
        env=env,
    )
    assert invoke.returncode == 0, (
        f"vocab_reminder CLI failed post-install with no BRIEF.md at "
        f"{target!r}:\n--- stdout ---\n{invoke.stdout}\n"
        f"--- stderr ---\n{invoke.stderr}"
    )
    assert "no words available to sample" not in invoke.stderr
    assert "VOCABULARY REMINDER" in invoke.stdout
