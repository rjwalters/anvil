"""Doc-coverage guard for the ip-uspto-provisional skill's adoption of the per-phase
git commit/sync hook (issue #426; rolled out skill-wide in issue #436).

The hook contract lives in ``anvil/lib/snippets/git_sync.md``; this file
pins the ip-uspto-provisional-skill adoption (the #350-style phased rollout: snippet +
memo pilot in #426, remaining skills in #436) so the conditional git-sync
final step can't silently drift out of a command file in a later edit.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_ip_uspto_provisional_git_sync_doc.py``.

Issue #537 (Group A of the cross-skill rollout, mirroring the #528 memo
pilot) trimmed the verbose ~5-sentence inline git-sync paragraph down to
the canonical short pointer (``git_sync.md`` §"Adoption step") plus a
"This phase's specifics" block that keeps the load-bearing per-command
mechanics inline: the staging target, the ordering anchor, the state
bracket, and the ``anvil(ip-uspto-provisional/<phase>):`` commit token.
The two pilot assertions below pin BOTH halves — the compressed shared
contract AND the retained per-command mechanics — so a future edit can
neither re-bloat the shared prose nor drop a load-bearing per-command
specific.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
COMMANDS = REPO_ROOT / "anvil" / "skills" / "ip-uspto-provisional" / "commands"
SKILL_MD = REPO_ROOT / "anvil" / "skills" / "ip-uspto-provisional" / "SKILL.md"

# The 12 write-bearing ip-uspto-provisional commands carrying a git-sync
# section. The portfolio orchestrator (ip-uspto-provisional.md) is
# read-only and exempt by definition.
WRITE_BEARING_COMMANDS = [
    "ip-uspto-provisional-draft.md",
    "ip-uspto-provisional-review.md",
    "ip-uspto-provisional-revise.md",
    "ip-uspto-provisional-audit.md",
    "ip-uspto-provisional-figures.md",
    "ip-uspto-provisional-vision.md",
    "ip-uspto-provisional-112.md",
    "ip-uspto-provisional-prior-art.md",
    "ip-uspto-provisional-inventorship.md",
    # Issue #502: the mechanical pre-flight gate and the opt-in claim-seed
    # critic both write machine-summary siblings and adopt the hook.
    "ip-uspto-provisional-pre-flight.md",
    "ip-uspto-provisional-claims-seed.md",
    "ip-uspto-provisional-finalize.md",
]

# Read-only / non-executable files that MUST NOT adopt the hook.
EXEMPT_FILES = [
    "ip-uspto-provisional.md",
]

# Critic-sidecar-writing subset (plus the terminal-package finalize, which
# also fires after the #350 atomic rename): the hook MUST order after the
# #350 staged-sidecar atomic rename so only complete sidecars are committed.
SIDECAR_COMMANDS = [
    "ip-uspto-provisional-review.md",
    "ip-uspto-provisional-audit.md",
    "ip-uspto-provisional-vision.md",
    "ip-uspto-provisional-112.md",
    "ip-uspto-provisional-prior-art.md",
    "ip-uspto-provisional-pre-flight.md",
    "ip-uspto-provisional-claims-seed.md",
    "ip-uspto-provisional-finalize.md",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _git_sync_section(command: str) -> str:
    """Return the ``## Git sync`` section of a command file (heading to
    EOF — the section is the file's final step by contract)."""
    text = _read(COMMANDS / command)
    idx = text.find("## Git sync")
    assert idx >= 0, f"{command} missing the Git sync section"
    return text[idx:]


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_references_git_sync_snippet(command: str):
    """Every write-bearing ip-uspto-provisional command MUST reference the snippet."""
    text = _read(COMMANDS / command)
    assert "snippets/git_sync.md" in text, (
        f"{command} MUST reference anvil/lib/snippets/git_sync.md "
        f"(issue #436)"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_names_commit_per_phase_knob(command: str):
    """Every write-bearing ip-uspto-provisional command MUST name the conditional knob."""
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
    ``anvil(ip-uspto-provisional/<phase>):`` so the orchestrator-facing shape can't
    drift per-command."""
    text = _read(COMMANDS / command)
    assert "anvil(ip-uspto-provisional/" in text, (
        f"{command}'s git-sync step MUST use the anvil(ip-uspto-provisional/<phase>): "
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


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_uses_short_pointer_shared_contract(command: str):
    """Issue #537: the SHARED explanation compresses to the canonical
    short pointer from ``git_sync.md`` §"Adoption step" — the contract
    sentence ("stage only the dirs this phase wrote") and the
    warn-and-continue clause are present, while the old verbose
    boilerplate ("emit a one-line warning", "byte-identical to a
    pre-#426 install") is gone."""
    section = _git_sync_section(command)
    assert "stage only the dirs this phase wrote" in section, (
        f"{command}'s git-sync step MUST carry the canonical short-pointer "
        f"shared-contract sentence"
    )
    assert "Git failures warn and continue" in section, (
        f"{command}'s git-sync step MUST keep the warn-and-continue clause"
    )
    # The verbose pre-#537 prose must NOT re-bloat the section.
    assert "emit a one-line warning and continue" not in section, (
        f"{command} still carries the verbose pre-#537 failure prose"
    )
    assert "byte-identical to a pre-#426 install" not in section, (
        f"{command} still carries the verbose pre-#537 default-off prose"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_keeps_per_command_mechanics(command: str):
    """Issue #537: the per-command mechanics that the short pointer
    CANNOT carry MUST stay inline — the staging target (which dir THIS
    command commits) and the ordering anchor (when the hook fires)."""
    section = _git_sync_section(command)
    assert "Staging target" in section, (
        f"{command}'s git-sync step MUST keep an inline staging target"
    )
    assert "Ordering" in section, (
        f"{command}'s git-sync step MUST keep an inline ordering anchor"
    )


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
