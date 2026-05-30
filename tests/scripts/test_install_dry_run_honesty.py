"""Regression test: ``install-anvil.sh --dry-run`` must not lie about actions.

Issue #81: prior to the fix, ``scripts/install-anvil.sh --dry-run`` emitted
post-action ``ok:`` confirmations (``ok: framework lib installed``,
``ok: roles installed``, ``ok: skill 'memo' installed``) BEFORE the trailing
``warn: DRY-RUN: no files were written`` line. The Stage 11 summary also
printed ``installed skills:    memo`` — a label that asserts an action that
never happened. The filesystem was genuinely untouched, so the output lied.

The fix:
  * Suppress the three per-action ``ok:`` confirmation lines (Stages 5/6/7)
    under ``--dry-run`` via call-site guards. Stage 1-4 diagnostic ``ok:``
    lines (``ANVIL_ROOT``, ``selected:``) and Stage 10 renderer-dep ``ok:``
    lines are NOT touched — they report real environment state, not actions.
  * Relabel the Stage 11 summary under ``--dry-run`` from
    ``installed skills:`` / ``skipped overrides:`` / ``target:`` to
    ``would install:`` / ``would skip:`` / ``would target:``. The summary is
    load-bearing (operators run ``--dry-run`` precisely to learn what a real
    run would touch); keep informative, just honest.

These tests exercise the installer via ``subprocess`` so the honesty contract
is enforced at the real entry point a consumer would hit, mirroring the
pattern established by ``test_install_quoting.py`` (#80).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _run_dry_run(target: Path) -> subprocess.CompletedProcess[str]:
    """Run the installer in ``--dry-run`` mode against ``target``.

    Captures stdout+stderr as text so failure messages can include the
    installer's own log lines for diagnosis.
    """

    return subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=memo", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_dry_run_does_not_emit_lying_ok_confirmations(tmp_path: Path) -> None:
    """``--dry-run`` must not print post-action ``ok:`` confirmation lines.

    Pre-fix on main (commit c4e2a87)::

        > Stage 5: copy framework code (anvil/lib -> .anvil/lib)
          [dry-run] install /tmp/.../.anvil/lib from .../anvil/lib
          ok: framework lib installed                ← LIES (nothing copied)
        > Stage 6: copy roles (anvil/roles -> .anvil/roles)
          [dry-run] install /tmp/.../.anvil/roles from .../anvil/roles
          ok: roles installed                        ← LIES
        > Stage 7: copy selected skills
          [dry-run] install .anvil/skills/memo from source
          [dry-run] write Claude registration shim at ...
          ok: skill 'memo' installed                 ← LIES

    Post-fix: the three bare confirmations are gone; only the ``[dry-run]``
    action lines remain — those are the truthful record of "what would
    happen".
    """

    target = tmp_path / "dry-run-target"
    target.mkdir()

    result = _run_dry_run(target)

    assert result.returncode == 0, (
        f"dry-run install exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    stdout = result.stdout

    # The [dry-run] action lines describing planned writes MUST be present —
    # they are the truthful record of what a real run would do.
    assert "[dry-run] install" in stdout, (
        "expected at least one '[dry-run] install ...' action line in stdout; "
        f"got:\n{stdout}"
    )
    assert "[dry-run] write Claude registration shim" in stdout, (
        "expected '[dry-run] write Claude registration shim' action line; "
        f"got:\n{stdout}"
    )

    # The three specific lying confirmation strings MUST NOT appear under
    # --dry-run. Each was a bare-fact assertion that an action completed
    # when no action was taken.
    forbidden_confirmations = (
        "ok: framework lib installed",
        "ok: roles installed",
        "ok: skill 'memo' installed",
    )
    for confirmation in forbidden_confirmations:
        assert confirmation not in stdout, (
            f"--dry-run still emits lying confirmation {confirmation!r}; "
            f"full stdout:\n{stdout}"
        )


def test_dry_run_summary_uses_would_install_framing(tmp_path: Path) -> None:
    """Stage 11 summary must relabel under ``--dry-run``.

    The summary is load-bearing — operators run ``--dry-run`` precisely to
    learn "what would a real install touch?" Suppressing it defeats the
    purpose. Relabel it as ``would install:`` instead, keeping the
    information honest.
    """

    target = tmp_path / "summary-target"
    target.mkdir()

    result = _run_dry_run(target)

    assert result.returncode == 0, (
        f"dry-run install exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    stdout = result.stdout

    # The lying summary label MUST NOT appear under --dry-run.
    assert "installed skills:" not in stdout, (
        "Stage 11 summary still uses 'installed skills:' framing under "
        f"--dry-run; got:\n{stdout}"
    )

    # The honest replacement MUST be present and MUST name the requested
    # skill so the operator can see WHAT a real run would install.
    assert "would install:" in stdout, (
        f"Stage 11 summary missing 'would install:' label; got:\n{stdout}"
    )
    # Locate the would-install line and assert it names `memo`.
    would_install_lines = [
        line for line in stdout.splitlines() if "would install:" in line
    ]
    assert would_install_lines, (
        f"could not isolate 'would install:' line; got:\n{stdout}"
    )
    assert "memo" in would_install_lines[0], (
        f"'would install:' line does not name the requested skill 'memo': "
        f"{would_install_lines[0]!r}"
    )

    # The final dry-run warning must still be present and truthful.
    assert "DRY-RUN: no files were written" in stdout, (
        f"missing trailing 'DRY-RUN: no files were written' warning; "
        f"got:\n{stdout}"
    )


def test_dry_run_leaves_target_filesystem_untouched(tmp_path: Path) -> None:
    """The substantive check: ``--dry-run`` writes nothing to the target.

    The honesty fix is meaningful only if the underlying claim ("nothing was
    written") is true. Verify the install layout artifacts are genuinely
    absent after a dry-run.
    """

    target = tmp_path / "untouched-target"
    target.mkdir()

    result = _run_dry_run(target)

    assert result.returncode == 0, (
        f"dry-run install exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    # None of the install layout artifacts should exist after --dry-run.
    assert not (target / ".anvil").exists(), (
        f"--dry-run created .anvil/ in target; tree:\n"
        f"{sorted(p.relative_to(target) for p in target.rglob('*'))}"
    )
    assert not (target / ".claude").exists(), (
        f"--dry-run created .claude/ in target; tree:\n"
        f"{sorted(p.relative_to(target) for p in target.rglob('*'))}"
    )
    assert not (target / "CLAUDE.md").exists(), (
        "--dry-run created CLAUDE.md in target"
    )

    # Strongest invariant: target tree is completely empty.
    leftovers = sorted(p.relative_to(target) for p in target.rglob("*"))
    assert leftovers == [], (
        f"--dry-run left artifacts in target: {leftovers}"
    )
