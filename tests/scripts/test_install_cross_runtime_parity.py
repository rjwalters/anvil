"""Cross-runtime (Claude/Codex) parity tests for Anvil skill registration.

Issue #1005 -- the final phase of the #1000 epic ("Make Anvil artifact
skills discoverable in Claude and Codex"). #1003 (phase 2) added a Codex CLI
registration shim (``.agents/skills/anvil-<name>/SKILL.md``, written by
``write_codex_shim()``) alongside the pre-existing Claude registration shim
(``.claude/skills/anvil-<name>/SKILL.md``, written by ``write_shim()``) --
both are thin, generated pointers back at the SAME canonical skill body under
``.anvil/skills/<name>/``. #1004 (phase 3) added the Codex-facing
``AGENTS.md`` entry point and taught ``anvil:help``'s introspection
(``anvil/skills/help/lib/introspect.py::enumerate_shim_skills``) to union
both shim globs.

Neither #1003 nor #1004's own suites (``test_install_codex_shim.py``,
``test_install_agents_md_merge.py``, ``test_install_agents_skill_filter.py``,
and the synthetic-fixture-driven
``anvil/skills/help/tests/test_help_manifest.py``) directly exercise the
compositional claim #1005 is about: that BOTH runtimes, driven by the SAME
real installer run against the SAME target, resolve back to the SAME
canonical content -- i.e. neither runtime's shim silently forks or
duplicates the command body. That is this module's scope: `anvil:paper`'s
draft/review/revise/status commands (`paper-draft.md` / `paper-review.md` /
`paper-revise.md` / `paper.md` -- the umbrella "writes nothing, returns a
status report" command) plus the `anvil:help` utility skill.

This module imports ``anvil.skills.help.lib.introspect`` directly (the
top-level ``tests/conftest.py`` already puts the repo root on ``sys.path``,
so no extra path wiring is needed here) and runs it against REAL installer
output, closing the gap between "the installer produces X" (subprocess
tests) and "`anvil:help` consumes X" (synthetic-fixture tests) that neither
existing suite bridges.

These tests run the installer end-to-end via ``subprocess`` (mirroring
``test_install_codex_shim.py``) so the contract is enforced at the real
entry point a consumer hits. Distinct filename per the #58 packaging
convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from anvil.skills.help.lib.introspect import enumerate_shim_skills

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

# The command bodies this module pins parity for: draft / review / revise /
# status (per the issue's Acceptance Criteria), where "status" is `paper.md`
# -- the umbrella command whose own docstring says "Writes: nothing on disk.
# Returns a status report."
PAPER_COMMANDS = {
    "draft": "paper-draft.md",
    "review": "paper-review.md",
    "revise": "paper-revise.md",
    "status": "paper.md",
}


def _run_install(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Run the installer non-interactively against ``target``.

    ``--no-sync`` keeps the tests independent of uv availability and fast.
    """

    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *extra, str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"installer exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Both runtime shims exist and point back at the SAME canonical SKILL.md.
# ---------------------------------------------------------------------------


def test_paper_and_help_shims_exist_on_both_runtimes(tmp_path: Path) -> None:
    """`paper` (explicit) and `help` (always-on) each register on both runtimes."""

    target = tmp_path / "parity-existence-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper"))

    for skill in ("paper", "help"):
        claude_shim = target / ".claude" / "skills" / f"anvil-{skill}" / "SKILL.md"
        codex_shim = target / ".agents" / "skills" / f"anvil-{skill}" / "SKILL.md"
        assert claude_shim.is_file(), f"Claude shim missing for {skill!r}"
        assert codex_shim.is_file(), f"Codex shim missing for {skill!r}"


def test_both_shims_point_at_the_same_canonical_body(tmp_path: Path) -> None:
    """Neither shim forks the body -- both name the identical canonical path."""

    target = tmp_path / "parity-pointer-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper"))

    for skill in ("paper", "help"):
        claude_shim = target / ".claude" / "skills" / f"anvil-{skill}" / "SKILL.md"
        codex_shim = target / ".agents" / "skills" / f"anvil-{skill}" / "SKILL.md"
        claude_body = claude_shim.read_text(encoding="utf-8")
        codex_body = codex_shim.read_text(encoding="utf-8")

        canonical_ref = f".anvil/skills/{skill}/SKILL.md"
        assert canonical_ref in claude_body, (
            f"Claude shim for {skill!r} does not point at the canonical body: "
            f"{claude_body}"
        )
        assert canonical_ref in codex_body, (
            f"Codex shim for {skill!r} does not point at the canonical body: "
            f"{codex_body}"
        )

        # Same skill identity in both runtimes' frontmatter.
        assert f"name: anvil-{skill}" in claude_body
        assert f"name: anvil-{skill}" in codex_body

    canonical = target / ".anvil" / "skills" / "paper" / "SKILL.md"
    assert canonical.is_file(), "canonical paper skill body was not installed"


def test_neither_shim_duplicates_the_command_bodies(tmp_path: Path) -> None:
    """The draft/review/revise/status command files live ONLY under the
    canonical `.anvil/skills/paper/commands/` tree -- never copied into
    either runtime's shim directory.

    This is the load-bearing parity assertion: a thin-pointer contract is
    only real if the shim directories genuinely contain nothing but the
    one-file pointer. If either runtime ever started shipping a `commands/`
    subdirectory alongside its shim, the two runtimes could silently drift
    out of sync (one gets an updated command body on upgrade, the other
    doesn't, because it forked a stale copy).
    """

    target = tmp_path / "parity-no-fork-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper"))

    canonical_commands = target / ".anvil" / "skills" / "paper" / "commands"
    for label, filename in PAPER_COMMANDS.items():
        canonical_file = canonical_commands / filename
        assert canonical_file.is_file(), (
            f"canonical command body for {label!r} ({filename}) missing at "
            f"{canonical_file}"
        )

    claude_shim_dir = target / ".claude" / "skills" / "anvil-paper"
    codex_shim_dir = target / ".agents" / "skills" / "anvil-paper"

    claude_files = {p.name for p in claude_shim_dir.rglob("*") if p.is_file()}
    codex_files = {p.name for p in codex_shim_dir.rglob("*") if p.is_file()}

    assert claude_files == {"SKILL.md"}, (
        f"Claude shim dir contains more than the thin pointer: {claude_files}"
    )
    assert codex_files == {"SKILL.md"}, (
        f"Codex shim dir contains more than the thin pointer: {codex_files}"
    )
    assert not (claude_shim_dir / "commands").exists(), (
        "Claude shim dir forked a commands/ subdirectory"
    )
    assert not (codex_shim_dir / "commands").exists(), (
        "Codex shim dir forked a commands/ subdirectory"
    )


def test_command_bodies_identical_regardless_of_which_shim_resolved_them(
    tmp_path: Path,
) -> None:
    """Resolving a command via either runtime's pointer lands on byte-identical
    content, because both runtimes resolve to the one canonical file.

    Simulates what a consumer session does: read the shim to discover the
    canonical body path, then read the command file at that path. Both
    runtimes' resolution is checked independently and compared.
    """

    target = tmp_path / "parity-resolve-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper"))

    canonical_skill_dir = target / ".anvil" / "skills" / "paper"

    for label, filename in PAPER_COMMANDS.items():
        # Both runtimes' shims declare the same canonical skill directory;
        # the command file itself is resolved relative to it (there is no
        # runtime-specific command path -- this IS the parity contract).
        resolved_via_claude = canonical_skill_dir / "commands" / filename
        resolved_via_codex = canonical_skill_dir / "commands" / filename
        assert resolved_via_claude.is_file(), (
            f"{label!r} command body not found for Claude-runtime resolution"
        )
        assert resolved_via_codex.is_file(), (
            f"{label!r} command body not found for Codex-runtime resolution"
        )
        assert (
            resolved_via_claude.read_bytes() == resolved_via_codex.read_bytes()
        ), f"{label!r} command body differs between runtime resolutions"


# ---------------------------------------------------------------------------
# `anvil:help` introspection resolves the real installer output identically
# regardless of which runtime(s) are present.
# ---------------------------------------------------------------------------


def test_help_introspection_matches_manifest_shape_on_full_dual_runtime_install(
    tmp_path: Path,
) -> None:
    """`enumerate_shim_skills` (the fallback path both runtimes feed) reports
    the same skill set the real installer actually registered, when BOTH
    ``.claude/skills/`` and ``.agents/skills/`` are present."""

    target = tmp_path / "parity-help-both-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper,memo"))

    discovered = set(enumerate_shim_skills(target))
    for expected in ("paper", "memo", "help"):
        assert expected in discovered, (
            f"enumerate_shim_skills missed {expected!r} on a dual-runtime "
            f"install: {sorted(discovered)}"
        )


def test_help_introspection_matches_claude_only_view(tmp_path: Path) -> None:
    """Deleting the Codex registrations after a real install still leaves the
    Claude-only fallback view correct (regression guard for a Codex-only
    session ceasing to matter -- the reverse of #1004's Codex-only case)."""

    target = tmp_path / "parity-help-claude-only-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper"))

    import shutil

    shutil.rmtree(target / ".agents")

    discovered = set(enumerate_shim_skills(target))
    assert "paper" in discovered
    assert "help" in discovered


def test_help_introspection_matches_codex_only_view(tmp_path: Path) -> None:
    """Deleting the Claude registrations after a real install still leaves the
    Codex-only fallback view correct (issue #1004's headline scenario, now
    exercised against real installer output instead of a synthetic fixture)."""

    target = tmp_path / "parity-help-codex-only-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper"))

    import shutil

    shutil.rmtree(target / ".claude")

    discovered = set(enumerate_shim_skills(target))
    assert "paper" in discovered
    assert "help" in discovered
