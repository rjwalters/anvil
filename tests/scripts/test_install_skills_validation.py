"""Regression test: ``install-anvil.sh --skills=`` (bare/empty) must error.

Issue #82: ``scripts/install-anvil.sh`` argument parsing has two branches for
the ``--skills`` flag (in the same ``case`` block in the parser loop)::

    --skills=*) SKILLS_FILTER="${1#--skills=}"; shift ;;
    --skills)   shift; SKILLS_FILTER="${1:-}";
                [[ -z "$SKILLS_FILTER" ]] && error "--skills requires ..."; shift ;;

The space-separated form (``--skills ''``) correctly errors out when the
value is empty. The ``=``-attached form silently fell through with
``SKILLS_FILTER=""``, which is the same state as "filter not set" — so the
installer happily proceeded to install ALL skills despite the operator's
clear intent to constrain the install (an empty value can only be a typo or
a misquoted shell variable; never a legitimate request).

The fix mirrors the empty-check from the space-separated branch onto the
``=``-attached branch::

    --skills=*) SKILLS_FILTER="${1#--skills=}";
                [[ -z "$SKILLS_FILTER" ]] && error "--skills requires ..."; shift ;;

These tests exercise the installer end-to-end via ``subprocess`` so the
validation contract is enforced at the real entry point a consumer would
hit, mirroring the pattern from ``test_install_quoting.py`` (#80) and
``test_install_dry_run_honesty.py`` (#81).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

EXPECTED_ERROR_FRAGMENT = "--skills requires a comma-separated list"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the installer with ``args`` and capture text stdout+stderr."""

    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_bare_skills_equals_errors_out(tmp_path: Path) -> None:
    """``--skills=`` (empty value via the ``=``-attached form) must error.

    Pre-fix: this silently fell through to install-all-skills because the
    ``--skills=*`` branch set ``SKILLS_FILTER=""`` and the empty-check only
    fired on the space-separated branch.

    Post-fix: behaviour matches ``--skills ''`` — non-zero exit and the
    ``--skills requires a comma-separated list`` error on stderr.
    """

    target = tmp_path / "bare-skills-equals-target"
    target.mkdir()

    result = _run("--skills=", str(target))

    assert result.returncode != 0, (
        f"--skills= (empty) should have errored but exited 0:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert EXPECTED_ERROR_FRAGMENT in result.stderr, (
        f"--skills= (empty) did not emit expected error fragment "
        f"{EXPECTED_ERROR_FRAGMENT!r}; got stderr:\n{result.stderr}"
    )

    # The substantive invariant: the target must NOT have been touched
    # (the bug was that the installer proceeded to install all skills).
    assert not (target / ".anvil").exists(), (
        f"--skills= (empty) created .anvil/ in target despite failing; "
        f"tree:\n{sorted(p.relative_to(target) for p in target.rglob('*'))}"
    )
    assert not (target / ".claude").exists(), (
        f"--skills= (empty) created .claude/ in target despite failing; "
        f"tree:\n{sorted(p.relative_to(target) for p in target.rglob('*'))}"
    )


def test_space_separated_empty_skills_errors_out(tmp_path: Path) -> None:
    """Parity check: ``--skills ''`` (space-separated empty) also errors.

    This branch has always errored correctly; the test pins the message
    text so the ``=``-attached branch's new check stays in lockstep with
    the established space-separated branch (the fix is a literal mirror —
    if one drifts, both should drift together).
    """

    target = tmp_path / "space-empty-skills-target"
    target.mkdir()

    result = _run("--skills", "", str(target))

    assert result.returncode != 0, (
        f"--skills '' should have errored but exited 0:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert EXPECTED_ERROR_FRAGMENT in result.stderr, (
        f"--skills '' did not emit expected error fragment "
        f"{EXPECTED_ERROR_FRAGMENT!r}; got stderr:\n{result.stderr}"
    )


def test_skills_equals_memo_still_succeeds(tmp_path: Path) -> None:
    """Smoke test the green path: a real ``--skills=memo`` invocation works.

    Guards against an over-eager empty-check that would reject every value
    (the fix targets ONLY the empty-string case). Uses ``--dry-run`` to
    avoid actually performing the install — the parser-validation contract
    we care about is enforced before any filesystem mutation.
    """

    target = tmp_path / "valid-skills-target"
    target.mkdir()

    result = _run("--dry-run", "--skills=memo", str(target))

    assert result.returncode == 0, (
        f"--dry-run --skills=memo should succeed but exited "
        f"{result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert EXPECTED_ERROR_FRAGMENT not in result.stderr, (
        f"--skills=memo wrongly triggered the empty-check; stderr:\n"
        f"{result.stderr}"
    )
    # The dry-run summary should name `memo` as the selected skill, proving
    # the value `memo` survived parser validation intact.
    assert "memo" in result.stdout, (
        f"--dry-run --skills=memo stdout does not mention 'memo'; got:\n"
        f"{result.stdout}"
    )
