"""Cross-runtime (Claude/Codex) parity tests for installed skill registration.

Issue #1005 (final phase of the #1000 epic, "Make Anvil artifact skills
discoverable in Claude and Codex"). #1003 (closed via PR #1010) added a Codex
CLI registration shim at ``.agents/skills/anvil-<name>/SKILL.md``, written in
parallel to the pre-existing Claude shim at
``.claude/skills/anvil-<name>/SKILL.md`` via ``write_codex_shim()`` /
``write_shim()``. #1004 (closed via PR #1014) added the ``AGENTS.md`` entry
point (Codex's analog of ``CLAUDE.md``) and unioned both shim globs into
``anvil:help``'s degraded-mode introspection.

Neither #1003 nor #1004 has a test asserting the two runtimes' registrations
actually **resolve back to the same canonical content** rather than silently
forking or duplicating it. That is this module's job: for the ``paper``
skill's ``draft``/``review``/``revise``/``status`` commands (``status`` is
the base ``paper.md`` portfolio-orchestrator command -- ``paper`` ships no
separate ``paper-status.md``) and the ``help`` utility skill, confirm:

  * both shims point at the exact same canonical
    ``.anvil/skills/<name>/SKILL.md`` path string (neither runtime resolves
    to a runtime-local fork of the skill identity);
  * the two shim files are byte-identical except for the runtime-label
    phrase ("Claude" vs "Codex CLI") -- i.e. one shared template, not two
    independently hand-maintained bodies that could drift;
  * neither shim embeds a copy of any command body -- each shim is a thin
    pointer, and the canonical ``.anvil/skills/<name>/commands/*.md`` files
    are the single, non-duplicated source of command content for both
    runtimes.

This is deliberately compositional, narrower scope than #1003/#1004's own
unit coverage (``tests/scripts/test_install_codex_shim.py``,
``tests/scripts/test_install_agents_md_merge.py``): those pin each phase's
own mechanics in isolation, this module pins that the two phases' outputs
actually agree with each other. Distinct filename per the #58 packaging
convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

# The two skills the #1000 epic's acceptance criteria name explicitly: the
# `paper` artifact skill (draft/review/revise/status) and the `help` utility
# skill.
PARITY_SKILLS = ["paper", "help"]

# paper's draft/review/revise/status commands, mapped to their on-disk
# command filenames. `status` has no `paper-status.md` -- the base `paper.md`
# file IS the status/portfolio-orchestrator command (see its own
# frontmatter: "Writes: nothing on disk. Returns a status report.").
PAPER_COMMAND_FILES = {
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


def _install_parity_target(tmp_path: Path, name: str) -> Path:
    target = tmp_path / name
    target.mkdir()
    _assert_ok(_run_install(target, f"--skills={','.join(PARITY_SKILLS)}"))
    return target


# ---------------------------------------------------------------------------
# Both shims point back at the SAME canonical SKILL.md path -- neither
# runtime resolves the skill identity to a runtime-local fork.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill", PARITY_SKILLS)
def test_claude_and_codex_shim_reference_identical_canonical_path(
    tmp_path: Path, skill: str
) -> None:
    target = _install_parity_target(tmp_path, f"parity-canonical-path-{skill}")

    claude_shim = target / ".claude" / "skills" / f"anvil-{skill}" / "SKILL.md"
    codex_shim = target / ".agents" / "skills" / f"anvil-{skill}" / "SKILL.md"
    assert claude_shim.is_file(), f"Claude shim missing for {skill!r}"
    assert codex_shim.is_file(), f"Codex shim missing for {skill!r}"

    canonical_ref = f".anvil/skills/{skill}/SKILL.md"
    claude_text = claude_shim.read_text(encoding="utf-8")
    codex_text = codex_shim.read_text(encoding="utf-8")

    assert canonical_ref in claude_text, (
        f"Claude shim for {skill!r} does not reference the canonical path "
        f"{canonical_ref!r}:\n{claude_text}"
    )
    assert canonical_ref in codex_text, (
        f"Codex shim for {skill!r} does not reference the canonical path "
        f"{canonical_ref!r}:\n{codex_text}"
    )

    canonical = target / ".anvil" / "skills" / skill / "SKILL.md"
    assert canonical.is_file(), f"canonical SKILL.md missing for {skill!r}"


# ---------------------------------------------------------------------------
# The two shim bodies are one shared template -- byte-identical except for
# the runtime-label phrase ("Claude" vs "Codex CLI").
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill", PARITY_SKILLS)
def test_claude_and_codex_shim_bodies_differ_only_in_runtime_label(
    tmp_path: Path, skill: str
) -> None:
    target = _install_parity_target(tmp_path, f"parity-shim-diff-{skill}")

    claude_shim = target / ".claude" / "skills" / f"anvil-{skill}" / "SKILL.md"
    codex_shim = target / ".agents" / "skills" / f"anvil-{skill}" / "SKILL.md"
    claude_text = claude_shim.read_text(encoding="utf-8")
    codex_text = codex_shim.read_text(encoding="utf-8")

    assert claude_text != codex_text, (
        f"Claude and Codex shims for {skill!r} are byte-identical -- expected "
        "at least the runtime-label word to differ ('Claude Code' vs "
        "'Codex CLI'); either the fixture is stale or one shim silently "
        "became a literal duplicate template."
    )

    # The runtime-label phrase differs in wording, not just a single word
    # ("Claude" vs "Codex CLI") -- normalize both to the same placeholder.
    normalized_claude = claude_text.replace("Claude", "RUNTIME")
    normalized_codex = codex_text.replace("Codex CLI", "RUNTIME")
    assert normalized_claude == normalized_codex, (
        "Claude and Codex shim bodies diverge beyond the runtime-label word "
        f"-- one runtime's shim forked the shared template.\n"
        f"--- Claude ({claude_shim}) ---\n{claude_text}\n"
        f"--- Codex ({codex_shim}) ---\n{codex_text}"
    )


# ---------------------------------------------------------------------------
# Neither shim embeds a copy of any command body -- the canonical
# `.anvil/skills/<name>/commands/*.md` files are the single source for both
# runtimes' draft/review/revise/status resolution.
# ---------------------------------------------------------------------------


def test_paper_command_bodies_have_a_single_canonical_source_both_runtimes(
    tmp_path: Path,
) -> None:
    target = _install_parity_target(tmp_path, "parity-paper-commands")

    canonical_commands_dir = target / ".anvil" / "skills" / "paper" / "commands"
    claude_shim = target / ".claude" / "skills" / "anvil-paper" / "SKILL.md"
    codex_shim = target / ".agents" / "skills" / "anvil-paper" / "SKILL.md"
    claude_text = claude_shim.read_text(encoding="utf-8")
    codex_text = codex_shim.read_text(encoding="utf-8")

    for phase, filename in PAPER_COMMAND_FILES.items():
        canonical_file = canonical_commands_dir / filename
        assert canonical_file.is_file(), (
            f"canonical command file missing for paper {phase!r}: "
            f"{canonical_file}"
        )
        # Pull a distinctive, non-boilerplate line out of the real command
        # body (its `description:` frontmatter line is unique per command)
        # and assert it appears in NEITHER shim -- if it did, that shim
        # would be a fork/duplicate of the command content rather than a
        # thin pointer back to the one canonical copy.
        body_lines = canonical_file.read_text(encoding="utf-8").splitlines()
        description_line = next(
            (line for line in body_lines if line.startswith("description:")),
            None,
        )
        assert description_line, (
            f"paper {phase!r} command file has no description: line to use "
            f"as a distinctive fingerprint: {canonical_file}"
        )
        assert description_line not in claude_text, (
            f"Claude shim for 'paper' embeds a copy of the {phase!r} command "
            f"body instead of pointing at the canonical file:\n{claude_text}"
        )
        assert description_line not in codex_text, (
            f"Codex shim for 'paper' embeds a copy of the {phase!r} command "
            f"body instead of pointing at the canonical file:\n{codex_text}"
        )

    # Neither shim's own directory carries a `commands/` subdirectory -- the
    # shim is genuinely thin, not a runtime-local mirror of the command set.
    assert not (target / ".claude" / "skills" / "anvil-paper" / "commands").exists()
    assert not (target / ".agents" / "skills" / "anvil-paper" / "commands").exists()


def test_help_command_body_has_a_single_canonical_source_both_runtimes(
    tmp_path: Path,
) -> None:
    target = _install_parity_target(tmp_path, "parity-help-command")

    canonical_help_cmd = target / ".anvil" / "skills" / "help" / "commands" / "help.md"
    assert canonical_help_cmd.is_file(), "canonical help.md command file missing"

    claude_shim = target / ".claude" / "skills" / "anvil-help" / "SKILL.md"
    codex_shim = target / ".agents" / "skills" / "anvil-help" / "SKILL.md"
    claude_text = claude_shim.read_text(encoding="utf-8")
    codex_text = codex_shim.read_text(encoding="utf-8")

    usage_line = "/anvil:help <skill>        # one skill's command set, rubric, thread layout"
    assert usage_line in canonical_help_cmd.read_text(encoding="utf-8"), (
        "fixture assumption stale: expected usage line not found in the "
        f"canonical help.md, update the fingerprint: {canonical_help_cmd}"
    )
    assert usage_line not in claude_text, (
        f"Claude shim for 'help' embeds a copy of the command body:\n{claude_text}"
    )
    assert usage_line not in codex_text, (
        f"Codex shim for 'help' embeds a copy of the command body:\n{codex_text}"
    )

    assert not (target / ".claude" / "skills" / "anvil-help" / "commands").exists()
    assert not (target / ".agents" / "skills" / "anvil-help" / "commands").exists()
