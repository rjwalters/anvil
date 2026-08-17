"""Cross-runtime (Claude/Codex) upgrade + removal ownership tests.

Issue #1005 -- the final phase of the #1000 epic ("Make Anvil artifact
skills discoverable in Claude and Codex"). #1003 (phase 2) added the Codex
CLI registration shim (``.agents/skills/anvil-<name>/SKILL.md``) alongside
the pre-existing Claude shim (``.claude/skills/anvil-<name>/SKILL.md``).
#1004 (phase 3) added the additive, marker-bounded ``AGENTS.md`` entry point
alongside the pre-existing ``CLAUDE.md`` one.

Both prior issues' own suites already exercise their runtime in isolation:

* ``test_install_codex_shim.py::test_codex_shim_regenerated_on_consumer_modified_skip``
  -- a single-skill body hand-edit, checked against Codex's shim alone.
* ``test_install_agents_md_merge.py`` -- ``AGENTS.md``'s create / replace /
  append mechanics, checked in isolation from ``CLAUDE.md``.
* ``test_install_skill_removal_prune.py`` / ``test_install_codex_shim.py::
  test_narrowed_reinstall_prunes_stale_codex_shim`` -- single-narrowing
  removal, checked per test.

This module's scope is the COMBINED, cross-runtime claim #1005's Acceptance
Criteria actually ask for: that a single upgrade or narrowing pass carries
BOTH runtimes' ownership guarantees together, not just each runtime's own
guarantee in isolation. Concretely:

1. Upgrade ownership: a consumer-owned skill-body edit AND simultaneous
   append-content in both ``CLAUDE.md`` and ``AGENTS.md`` all survive one
   re-install pass, while both runtimes' shims regenerate and both markdown
   files' framework-owned marker blocks still get rewritten.
2. Removal ownership: a multi-step ``--skills=`` narrowing sequence keeps
   both runtimes' registrations in lockstep at every step -- not just the
   final state of a single narrowing.

These tests run the installer end-to-end via ``subprocess`` (mirroring
``test_install_codex_shim.py``) so the contract is enforced at the real
entry point a consumer hits. Distinct filename per the #58 packaging
convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from anvil.lib.testing import assert_ok as _assert_ok

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

ANVIL_MARK_BEGIN = "<!-- BEGIN ANVIL -->"


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


def _runtime_shim_dirs(target: Path, skill: str) -> tuple[Path, Path]:
    return (
        target / ".claude" / "skills" / f"anvil-{skill}",
        target / ".agents" / "skills" / f"anvil-{skill}",
    )


# ---------------------------------------------------------------------------
# Upgrade ownership: a skill-body edit AND both marker files' consumer
# content all survive one combined re-install pass.
# ---------------------------------------------------------------------------


def test_skill_body_edit_and_dual_markdown_appends_all_survive_one_upgrade(
    tmp_path: Path,
) -> None:
    """A single re-install preserves THREE consumer-owned edits at once:

    1. A hand-edit to the shared canonical skill body backing both shims
       (the installer's documented "skip without --force" override target).
    2. Consumer-authored content appended to ``CLAUDE.md`` (outside the
       Anvil marker block).
    3. Consumer-authored content appended to ``AGENTS.md`` (outside the
       Anvil marker block) -- the Codex-side equivalent per #1004.

    ...while framework-owned surfaces still update: both runtime shims
    regenerate (pointing at the still-edited-but-preserved canonical body),
    and a DIFFERENT, untouched skill (``memo``) continues to be normally
    tracked/re-synced rather than being frozen by the unrelated skip.
    """

    target = tmp_path / "combined-upgrade-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper,memo"))

    # 1. Hand-edit the shared canonical skill body (the ONE override surface
    #    both runtimes' shims point at).
    paper_body = target / ".anvil" / "skills" / "paper" / "SKILL.md"
    original_paper_body = paper_body.read_text(encoding="utf-8")
    paper_body.write_text(
        original_paper_body + "\n<!-- consumer edit: paper -->\n",
        encoding="utf-8",
    )

    # 2 & 3. Consumer content prepended to CLAUDE.md / AGENTS.md, ahead of
    # the Anvil marker block that a fresh install already wrote.
    claude_md = target / "CLAUDE.md"
    agents_md = target / "AGENTS.md"
    claude_consumer_line = "<!-- consumer note: CLAUDE.md must keep this -->\n"
    agents_consumer_line = "<!-- consumer note: AGENTS.md must keep this -->\n"
    claude_md.write_text(
        claude_consumer_line + claude_md.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    agents_md.write_text(
        agents_consumer_line + agents_md.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = _run_install(target, "--skills=paper,memo")
    _assert_ok(result)
    assert "skipped: consumer-modified" in result.stdout, (
        f"expected the paper skill body edit to trigger an override-skip "
        f"warning; got:\n{result.stdout}"
    )

    # --- Ownership guarantee 1: the skill-body edit survived. ---
    assert "<!-- consumer edit: paper -->" in paper_body.read_text(
        encoding="utf-8"
    ), "consumer edit to the shared canonical skill body did not survive"

    # --- Ownership guarantee 2 & 3: both marker-file appends survived. ---
    assert claude_consumer_line in claude_md.read_text(encoding="utf-8"), (
        "consumer content prepended to CLAUDE.md did not survive the upgrade"
    )
    assert agents_consumer_line in agents_md.read_text(encoding="utf-8"), (
        "consumer content prepended to AGENTS.md did not survive the upgrade"
    )
    # Framework-owned marker blocks are still present (rewritten, not lost).
    assert claude_md.read_text(encoding="utf-8").count(ANVIL_MARK_BEGIN) == 1
    assert agents_md.read_text(encoding="utf-8").count(ANVIL_MARK_BEGIN) == 1

    # --- Framework-owned surfaces still update: both shims for the edited
    #     skill regenerate, pointing at the (preserved-edit) canonical body.
    claude_shim, codex_shim = _runtime_shim_dirs(target, "paper")
    assert (claude_shim / "SKILL.md").is_file()
    assert (codex_shim / "SKILL.md").is_file()
    for shim in (claude_shim / "SKILL.md", codex_shim / "SKILL.md"):
        assert ".anvil/skills/paper/SKILL.md" in shim.read_text(encoding="utf-8")

    # --- An untouched sibling skill (memo) is unaffected by paper's skip;
    #     it stays normally tracked on both runtimes.
    memo_claude_shim, memo_codex_shim = _runtime_shim_dirs(target, "memo")
    assert memo_claude_shim.is_dir()
    assert memo_codex_shim.is_dir()
    assert (target / ".anvil" / "skills" / "memo").is_dir()


def test_lib_mirror_still_upgrades_for_a_skipped_skill_on_both_runtimes(
    tmp_path: Path,
) -> None:
    """Even when a skill's BODY is skipped as consumer-modified, its
    importable lib mirror is unconditional framework-owned code that must
    still refresh -- and both runtime shims must still regenerate pointing
    at the (unmodified) canonical body location, not go stale or missing.
    """

    target = tmp_path / "lib-mirror-upgrade-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper"))

    paper_body = target / ".anvil" / "skills" / "paper" / "SKILL.md"
    paper_body.write_text(
        paper_body.read_text(encoding="utf-8") + "\n<!-- hand edit -->\n",
        encoding="utf-8",
    )

    result = _run_install(target, "--skills=paper")
    _assert_ok(result)
    assert "skipped: consumer-modified" in result.stdout

    # The importable mirror + documented direct-invocation lib copy are
    # unconditional, framework-owned code -- both must still exist.
    pylib_mirror = target / ".anvil" / "anvil" / "skills" / "paper" / "lib"
    bodylib_copy = target / ".anvil" / "skills" / "paper" / "lib"
    assert pylib_mirror.is_dir(), "importable lib mirror missing after skip"
    assert bodylib_copy.is_dir(), "documented-invocation lib copy missing after skip"

    claude_shim, codex_shim = _runtime_shim_dirs(target, "paper")
    assert (claude_shim / "SKILL.md").is_file()
    assert (codex_shim / "SKILL.md").is_file()


# ---------------------------------------------------------------------------
# Removal ownership: a multi-step --skills= narrowing sequence keeps both
# runtimes in lockstep at EVERY step, not just the final state.
# ---------------------------------------------------------------------------


def test_multi_step_narrowing_keeps_both_runtimes_in_lockstep(
    tmp_path: Path,
) -> None:
    """Three skills installed, then narrowed down one at a time. At each
    step, the just-dropped skill's registrations are gone from BOTH
    runtimes and every still-selected skill's registrations survive on
    BOTH runtimes -- checked after each narrowing, not only the final one.
    """

    target = tmp_path / "multi-step-narrow-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper,memo,deck"))
    for skill in ("paper", "memo", "deck"):
        claude_shim, codex_shim = _runtime_shim_dirs(target, skill)
        assert claude_shim.is_dir(), f"{skill} missing Claude shim after fresh install"
        assert codex_shim.is_dir(), f"{skill} missing Codex shim after fresh install"

    # Step 1: drop "deck".
    _assert_ok(_run_install(target, "--skills=paper,memo"))
    deck_claude, deck_codex = _runtime_shim_dirs(target, "deck")
    assert not deck_claude.exists(), "deck Claude shim survived step-1 narrowing"
    assert not deck_codex.exists(), "deck Codex shim survived step-1 narrowing"
    for skill in ("paper", "memo"):
        claude_shim, codex_shim = _runtime_shim_dirs(target, skill)
        assert claude_shim.is_dir(), f"{skill} Claude shim wrongly pruned at step 1"
        assert codex_shim.is_dir(), f"{skill} Codex shim wrongly pruned at step 1"

    # Step 2: drop "memo" too, leaving only "paper" (+ always-on "help").
    _assert_ok(_run_install(target, "--skills=paper"))
    memo_claude, memo_codex = _runtime_shim_dirs(target, "memo")
    assert not memo_claude.exists(), "memo Claude shim survived step-2 narrowing"
    assert not memo_codex.exists(), "memo Codex shim survived step-2 narrowing"
    paper_claude, paper_codex = _runtime_shim_dirs(target, "paper")
    assert paper_claude.is_dir(), "paper Claude shim wrongly pruned at step 2"
    assert paper_codex.is_dir(), "paper Codex shim wrongly pruned at step 2"
    # Deck stays gone (no resurrection from an earlier install state).
    assert not deck_claude.exists()
    assert not deck_codex.exists()
    # help (always-on) survives every narrowing.
    help_claude, help_codex = _runtime_shim_dirs(target, "help")
    assert help_claude.is_dir()
    assert help_codex.is_dir()

    # The canonical .anvil/skills/ tree matches the shim state on both
    # runtimes at the final step -- no orphaned canonical bodies either.
    anvil_skills = target / ".anvil" / "skills"
    installed_canonical = {p.name for p in anvil_skills.iterdir() if p.is_dir()}
    assert installed_canonical == {"paper", "help"}, (
        f"canonical .anvil/skills/ tree out of sync with runtime shims: "
        f"{sorted(installed_canonical)}"
    )


def test_narrowing_removes_registrations_from_both_runtimes_in_one_pass(
    tmp_path: Path,
) -> None:
    """The direct AC-3 scenario: install both runtimes present, narrow via
    ``--skills=`` on a re-install, confirm both runtimes' registrations for
    the removed skill are cleaned up and the kept skill's are untouched --
    verified together with the manifest's ``installed_skills`` list and the
    CLAUDE.md/AGENTS.md marker blocks (which are NOT per-skill and so must
    remain present and singular regardless of the narrowing).
    """

    target = tmp_path / "single-pass-narrow-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=paper,memo"))

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)

    paper_claude, paper_codex = _runtime_shim_dirs(target, "paper")
    assert not paper_claude.exists(), "removed skill's Claude shim not cleaned up"
    assert not paper_codex.exists(), "removed skill's Codex shim not cleaned up"
    assert not (target / ".anvil" / "skills" / "paper").exists(), (
        "removed skill's canonical body not cleaned up"
    )

    memo_claude, memo_codex = _runtime_shim_dirs(target, "memo")
    assert memo_claude.is_dir(), "kept skill's Claude shim disturbed by narrowing"
    assert memo_codex.is_dir(), "kept skill's Codex shim disturbed by narrowing"

    import json

    manifest = json.loads(
        (target / ".anvil" / "install-metadata.json").read_text(encoding="utf-8")
    )
    assert "paper" not in manifest["installed_skills"]
    assert "memo" in manifest["installed_skills"]

    # The global (non-per-skill) marker files are untouched by the
    # per-skill narrowing -- both still carry exactly one Anvil block.
    claude_md = (target / "CLAUDE.md").read_text(encoding="utf-8")
    agents_md = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert claude_md.count(ANVIL_MARK_BEGIN) == 1
    assert agents_md.count(ANVIL_MARK_BEGIN) == 1
