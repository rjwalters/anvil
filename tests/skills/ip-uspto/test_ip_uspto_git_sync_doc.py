"""Doc-coverage guard for the ip-uspto skill's adoption of the per-phase
git commit/sync hook (issue #426; rolled out skill-wide in issue #436).

The hook contract lives in ``anvil/lib/snippets/git_sync.md``; this file
pins the ip-uspto-skill adoption (the #350-style phased rollout: snippet +
memo pilot in #426, remaining skills in #436) so the conditional git-sync
final step can't silently drift out of a command file in a later edit.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_ip_uspto_git_sync_doc.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
COMMANDS = REPO_ROOT / "anvil" / "skills" / "ip-uspto" / "commands"
SKILL_MD = REPO_ROOT / "anvil" / "skills" / "ip-uspto" / "SKILL.md"

# The 15 write-bearing ip-uspto commands per the issue #436 curation
# inventory. The portfolio orchestrator (ip-uspto.md) is read-only and
# exempt by definition.
WRITE_BEARING_COMMANDS = [
    "ip-uspto-intake.md",
    "ip-uspto-inventorship.md",
    "ip-uspto-draft.md",
    "ip-uspto-review.md",
    "ip-uspto-revise.md",
    "ip-uspto-audit.md",
    "ip-uspto-figures.md",
    "ip-uspto-vision.md",
    "ip-uspto-claims.md",
    "ip-uspto-101.md",
    "ip-uspto-112.md",
    "ip-uspto-prior-art.md",
    "ip-uspto-adversary.md",
    "ip-uspto-pre-flight.md",
    "ip-uspto-finalize.md",
]

# Read-only / non-executable files that MUST NOT adopt the hook.
EXEMPT_FILES = [
    "ip-uspto.md",
]

# Critic-sidecar-writing subset: the hook MUST order after the #350
# staged-sidecar atomic rename so only complete sidecars are committed.
SIDECAR_COMMANDS = [
    "ip-uspto-review.md",
    "ip-uspto-audit.md",
    "ip-uspto-claims.md",
    "ip-uspto-101.md",
    "ip-uspto-112.md",
    "ip-uspto-prior-art.md",
    "ip-uspto-adversary.md",
    "ip-uspto-pre-flight.md",
    "ip-uspto-vision.md",
    "ip-uspto-finalize.md",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_references_git_sync_snippet(command: str):
    """Every write-bearing ip-uspto command MUST reference the snippet."""
    text = _read(COMMANDS / command)
    assert "snippets/git_sync.md" in text, (
        f"{command} MUST reference anvil/lib/snippets/git_sync.md "
        f"(issue #436)"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_names_commit_per_phase_knob(command: str):
    """Every write-bearing ip-uspto command MUST name the conditional knob."""
    text = _read(COMMANDS / command)
    assert "commit_per_phase" in text, (
        f"{command} MUST gate its git-sync step on git.commit_per_phase"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_git_sync_step_is_default_off(command: str):
    """The conditional step MUST state the default-off contract."""
    text = _read(COMMANDS / command).lower()
    assert "default off" in text, (
        f"{command}'s git-sync step MUST state it is default off"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_git_sync_uses_structured_message_shape(command: str):
    """The step MUST carry the structured commit-message prefix
    ``anvil(ip-uspto/<phase>):`` so the orchestrator-facing shape can't
    drift per-command."""
    text = _read(COMMANDS / command)
    assert "anvil(ip-uspto/" in text, (
        f"{command}'s git-sync step MUST use the anvil(ip-uspto/<phase>): "
        f"commit-message shape"
    )


@pytest.mark.parametrize("exempt", EXEMPT_FILES)
def test_read_only_files_are_exempt(exempt: str):
    """Read-only / non-executable files MUST NOT adopt the hook —
    read-only commands are exempt by definition (issue #436 AC)."""
    text = _read(COMMANDS / exempt)
    assert "commit_per_phase" not in text
    assert "snippets/git_sync.md" not in text


def test_skill_md_mentions_contract():
    """SKILL.md MUST mention the git-sync contract (issue #436 AC)."""
    text = _read(SKILL_MD)
    assert "git_sync.md" in text
    assert "commit_per_phase" in text
    assert ".anvil/config.json" in text


@pytest.mark.parametrize("command", SIDECAR_COMMANDS)
def test_sidecar_writing_commands_order_after_rename(command: str):
    """Critic-sidecar-writing commands MUST order the hook after the
    #350 staged-sidecar atomic rename so only complete sidecars are
    ever committed."""
    text = _read(COMMANDS / command)
    idx = text.find("## Git sync")
    assert idx >= 0, f"{command} missing the Git sync section"
    section = text[idx:]
    assert "atomic rename" in section and "#350" in section, (
        f"{command}'s git-sync step MUST fire after the #350 "
        f"staged-sidecar atomic rename"
    )
