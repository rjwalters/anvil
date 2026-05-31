"""Regression test: Claude registration shims must land at depth 1.

Issue #135: ``scripts/install-anvil.sh`` previously wrote the per-skill
Claude shim to ``.claude/skills/anvil/<skill>/SKILL.md`` -- a depth-2 path.
Claude Code's skill-discovery contract only finds ``SKILL.md`` at depth 1
(``.claude/skills/<skill>/SKILL.md``), so the shim was silently skipped and
no ``/anvil-*:*`` slash command was invokable. The studio canary surfaced
this on 2026-05-30 while attempting to run ``/anvil:memo-draft``.

The fix flattens the ``anvil`` namespace into the directory name so the
shim lives at ``.claude/skills/anvil-<skill>/SKILL.md`` (depth 1). The
existing ``name: anvil-<skill>`` frontmatter inside the shim body already
matched this naming, so only the directory path needed to change.

These tests run the installer end-to-end via ``subprocess`` (mirroring the
pattern in ``test_install_quoting.py`` and ``test_install_dry_run_honesty.py``)
so the contract is enforced at the real entry point a consumer hits.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _run_install(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Run the installer non-interactively against ``target``.

    Captures stdout+stderr as text so test assertions can quote installer
    output in failure messages.
    """

    return subprocess.run(
        ["bash", str(INSTALLER), "-y", *extra, str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_shim_lands_at_depth_one(tmp_path: Path) -> None:
    """The per-skill shim must live at ``.claude/skills/anvil-<skill>/SKILL.md``.

    Pre-fix (the bug): shim was written to ``.claude/skills/anvil/<skill>/SKILL.md``
    (depth 2), which Claude Code's discovery silently skipped, so no
    ``/anvil-*:*`` slash command became invokable.

    Post-fix: shim is at ``.claude/skills/anvil-<skill>/SKILL.md`` (depth 1),
    discoverable, and slash commands surface as ``/anvil-<skill>:<command>``.
    """

    target = tmp_path / "shim-depth-target"
    target.mkdir()

    result = _run_install(target, "--skills=memo")

    assert result.returncode == 0, (
        f"install failed:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    # The shim MUST exist at the depth-1 path Claude Code actually discovers.
    expected_shim = target / ".claude" / "skills" / "anvil-memo" / "SKILL.md"
    assert expected_shim.is_file(), (
        f"expected depth-1 shim at {expected_shim} -- not found.\n"
        f"Tree under .claude/skills/:\n"
        + "\n".join(
            f"  {p.relative_to(target)}"
            for p in (target / ".claude" / "skills").rglob("*")
        )
    )

    # The shim MUST NOT exist at the legacy depth-2 path.
    legacy_shim = (
        target / ".claude" / "skills" / "anvil" / "memo" / "SKILL.md"
    )
    assert not legacy_shim.exists(), (
        f"legacy depth-2 shim still being written at {legacy_shim}; "
        "the install path was not fully migrated to depth 1."
    )


def test_shim_frontmatter_matches_directory_name(tmp_path: Path) -> None:
    """The shim's ``name:`` frontmatter must equal its enclosing directory.

    Claude Code resolves the skill identity from the ``name:`` field in the
    frontmatter. For depth-1 discovery to surface the skill consistently,
    the parent directory should also be named ``anvil-<skill>`` -- if the
    two disagree, consumer-facing slash commands silently break again.
    """

    target = tmp_path / "shim-name-target"
    target.mkdir()

    result = _run_install(target, "--skills=memo")

    assert result.returncode == 0, (
        f"install failed:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    shim = target / ".claude" / "skills" / "anvil-memo" / "SKILL.md"
    assert shim.is_file(), f"shim not present at {shim}"
    body = shim.read_text()
    assert "name: anvil-memo" in body, (
        "shim frontmatter does not declare 'name: anvil-memo'; mismatch "
        "between directory name and skill identity will break Claude Code "
        f"discovery. Body:\n{body}"
    )


def test_all_selected_skills_land_at_depth_one(tmp_path: Path) -> None:
    """Multiple selected skills must each land at depth 1.

    Guards against a partial-migration regression where one skill is
    correctly placed but another is left at depth 2 (e.g. via a stale
    second copy site).
    """

    target = tmp_path / "shim-multi-target"
    target.mkdir()

    selected = ["memo", "deck", "report"]
    result = _run_install(target, f"--skills={','.join(selected)}")

    assert result.returncode == 0, (
        f"install failed:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    for skill in selected:
        expected = target / ".claude" / "skills" / f"anvil-{skill}" / "SKILL.md"
        assert expected.is_file(), (
            f"depth-1 shim missing for skill {skill!r} at {expected}"
        )
        legacy = (
            target / ".claude" / "skills" / "anvil" / skill / "SKILL.md"
        )
        assert not legacy.exists(), (
            f"legacy depth-2 shim still being written for skill {skill!r}: "
            f"{legacy}"
        )


def test_dry_run_action_line_describes_depth_one_path(tmp_path: Path) -> None:
    """The ``--dry-run`` action line must advertise the depth-1 destination.

    The dry-run summary is the operator's truthful preview of what a real
    install would do. After the migration the ``write Claude registration
    shim at ...`` action line must name the depth-1 path -- if it still
    says ``.claude/skills/anvil/<skill>/`` the docs are lying and the
    migration is incomplete.
    """

    target = tmp_path / "shim-dryrun-target"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=memo", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0, (
        f"dry-run install failed:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    stdout = result.stdout

    # The new (correct) path must appear in the dry-run action line.
    assert ".claude/skills/anvil-memo/SKILL.md" in stdout, (
        "dry-run action line does not advertise the depth-1 shim path; "
        f"got:\n{stdout}"
    )

    # The legacy depth-2 substring must not appear (would indicate either a
    # stale code path or a stale doc string).
    assert ".claude/skills/anvil/memo/SKILL.md" not in stdout, (
        "dry-run action line still references the legacy depth-2 shim path; "
        f"got:\n{stdout}"
    )
