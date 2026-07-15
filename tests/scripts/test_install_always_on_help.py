"""Regression test: ``anvil:help`` is installed unconditionally (#728).

Issue #728: ``anvil:help`` is the onboarding/orientation entry point — it
answers "what Anvil skills are installed here and what's the workflow?". That
value is *highest* in a filtered install (e.g. ``--skills=memo,deck``), yet
that is exactly where a uniform Stage 4 filter would omit it. The fix adds an
installer-hardcoded always-on allowlist (``ALWAYS_ON_SKILLS=("help")``) that
is unioned into ``SELECTED_SKILLS`` *after* the ``--skills=`` filter and its
validation run, with a dedup guard so it is a no-op on full installs and on
explicit ``--skills=help,...`` requests.

Mechanism chosen (per the #728 curator note): an installer allowlist in
``scripts/install-anvil.sh``, NOT a ``SKILL.md`` frontmatter marker. Always-on
is a maintainer/installer-architecture decision — it mirrors the existing
hardcoded ``lib``/``roles`` always-installed precedent — and is a smaller,
more auditable diff than introducing the repo's first behavioral frontmatter
key. Scope is ``help`` only; other broadly-useful utilities (e.g.
``project-scout``) remain filterable.

These tests exercise the installer end-to-end via ``subprocess`` against a
``tmp_path`` target, mirroring the pattern established by
``test_install_skills_validation.py`` (#82) and
``test_install_dry_run_honesty.py`` (#81). Real installs use ``--yes`` for
non-interactive mode (the installer also auto-detects a non-TTY stdin, but the
flag is explicit and stable under the test harness).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the installer with ``args`` and capture text stdout+stderr."""

    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _installed_skills(target: Path) -> list[str]:
    """Return the ``installed_skills`` array from the target's manifest."""

    manifest = target / ".anvil" / "install-metadata.json"
    assert manifest.exists(), (
        f"expected manifest at {manifest} but it does not exist; target tree:\n"
        f"{sorted(p.relative_to(target) for p in target.rglob('*'))}"
    )
    data = json.loads(manifest.read_text())
    skills = data.get("installed_skills")
    assert isinstance(skills, list), (
        f"installed_skills is not a JSON array in {manifest}: {skills!r}"
    )
    return skills


def test_filtered_install_ships_help_alongside_requested(tmp_path: Path) -> None:
    """``--skills=memo,deck`` installs ``help`` too (three skills, not two).

    ``help`` is NOT explicitly requested here, yet the always-on carve-out
    must materialize it on disk (both under ``.anvil/skills/`` and as a
    ``.claude/skills/anvil-help/`` registration shim) and list it in the
    manifest's ``installed_skills`` alongside the requested ``memo`` and
    ``deck``.
    """

    target = tmp_path / "filtered-target"
    target.mkdir()

    result = _run("--skills=memo,deck", "--yes", str(target))

    assert result.returncode == 0, (
        f"--skills=memo,deck should succeed but exited {result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    skills = _installed_skills(target)
    for expected in ("memo", "deck", "help"):
        assert expected in skills, (
            f"expected {expected!r} in installed_skills but got {skills!r}"
        )

    # help materialized on disk in both install locations.
    assert (target / ".anvil" / "skills" / "help").is_dir(), (
        "expected .anvil/skills/help/ to exist under a filtered install"
    )
    assert (target / ".claude" / "skills" / "anvil-help").is_dir(), (
        "expected .claude/skills/anvil-help/ registration shim to exist"
    )


def test_explicit_help_request_is_not_duplicated(tmp_path: Path) -> None:
    """``--skills=help,memo`` installs ``help`` exactly once (no duplicate).

    The always-on union must dedup against ``SELECTED_SKILLS``, so an explicit
    ``help`` request does not gain a second entry in ``installed_skills``.
    """

    target = tmp_path / "explicit-help-target"
    target.mkdir()

    result = _run("--skills=help,memo", "--yes", str(target))

    assert result.returncode == 0, (
        f"--skills=help,memo should succeed but exited {result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    skills = _installed_skills(target)
    assert skills.count("help") == 1, (
        f"expected 'help' exactly once in installed_skills but got {skills!r}"
    )
    assert "memo" in skills, (
        f"expected 'memo' in installed_skills but got {skills!r}"
    )


def test_full_install_lists_help_exactly_once(tmp_path: Path) -> None:
    """A no-``--skills=`` (full) install lists ``help`` once — no inflation.

    On the install-everything path ``help`` is already present via
    ``ALL_SKILLS``; the always-on union must be a no-op there rather than
    appending a duplicate.
    """

    target = tmp_path / "full-target"
    target.mkdir()

    result = _run("--yes", str(target))

    assert result.returncode == 0, (
        f"full install should succeed but exited {result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    skills = _installed_skills(target)
    assert skills.count("help") == 1, (
        f"expected 'help' exactly once in a full install but got {skills!r}"
    )
    # No duplicates anywhere — the union must not inflate the manifest.
    assert len(skills) == len(set(skills)), (
        f"installed_skills contains duplicates on a full install: {skills!r}"
    )


def test_dry_run_reflects_help_under_filter(tmp_path: Path) -> None:
    """``--dry-run --skills=memo`` lists ``help`` as would-install, writes nothing.

    The dry-run "would install:" summary is load-bearing (operators run it to
    learn what a real run would touch); the union must be reflected there. And
    per the dry-run honesty contract, the target filesystem stays untouched.
    """

    target = tmp_path / "dry-run-target"
    target.mkdir()

    result = _run("--dry-run", "--skills=memo", str(target))

    assert result.returncode == 0, (
        f"--dry-run --skills=memo should succeed but exited "
        f"{result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    would_install_lines = [
        line for line in result.stdout.splitlines() if "would install:" in line
    ]
    assert would_install_lines, (
        f"could not isolate 'would install:' line; got:\n{result.stdout}"
    )
    line = would_install_lines[0]
    assert "help" in line, (
        f"'would install:' line does not name always-on 'help': {line!r}"
    )
    assert "memo" in line, (
        f"'would install:' line does not name requested 'memo': {line!r}"
    )

    # Dry-run must not touch the target filesystem.
    leftovers = sorted(p.relative_to(target) for p in target.rglob("*"))
    assert leftovers == [], (
        f"--dry-run left artifacts in target: {leftovers}"
    )


def test_carveout_does_not_widen_to_other_utilities(tmp_path: Path) -> None:
    """Negative control: ``project-scout`` stays EXCLUDED under ``--skills=memo``.

    The carve-out is scoped to ``help`` alone. A different broadly-useful
    utility skill (``project-scout``) must NOT be pulled in by the always-on
    logic — proving the allowlist is ``help``-only, not "all utilities".
    """

    target = tmp_path / "negative-control-target"
    target.mkdir()

    result = _run("--skills=memo", "--yes", str(target))

    assert result.returncode == 0, (
        f"--skills=memo should succeed but exited {result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    skills = _installed_skills(target)
    assert "project-scout" not in skills, (
        f"project-scout must not be always-on; installed_skills={skills!r}"
    )
    assert not (target / ".anvil" / "skills" / "project-scout").exists(), (
        "project-scout must not materialize under a help-only carve-out"
    )
    # Sanity: help IS present (proving the carve-out fired at all).
    assert "help" in skills, (
        f"expected always-on 'help' in installed_skills but got {skills!r}"
    )


def test_typo_still_errors_before_union(tmp_path: Path) -> None:
    """``--skills=memoo`` (typo) still errors; the union does not mask it.

    Input validation for the user-supplied ``--skills=`` list runs BEFORE the
    always-on union, so a typo'd skill name still triggers the existing
    ``unknown skill:`` error and aborts the install (help is never silently
    substituted for the operator's mistake).
    """

    target = tmp_path / "typo-target"
    target.mkdir()

    result = _run("--skills=memoo", "--yes", str(target))

    assert result.returncode != 0, (
        f"--skills=memoo (typo) should have errored but exited 0:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "unknown skill: memoo" in result.stderr, (
        f"--skills=memoo did not emit expected 'unknown skill: memoo' error; "
        f"got stderr:\n{result.stderr}"
    )
    # The install must have aborted before touching the target.
    assert not (target / ".anvil").exists(), (
        "typo'd --skills= created .anvil/ despite failing validation"
    )
