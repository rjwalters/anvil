"""Tool-scope discipline per agent role.

Issue #377 — drafter / reviewer / reviser / auditor / figurer each have a
distinct tool-scope profile. Codify the profile so a future refactor of the
generator can't silently widen access (e.g., handing a reviewer ``Edit``,
which would let it mutate the version dir it's supposed to read-only-score).

Reviewer agents intentionally do NOT carry ``Edit`` — they write FRESH
sidecar directories via the staged_sidecar primitive; they never edit an
existing version-dir file in place.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "anvil" / "agents"


def load_tools(path: pathlib.Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    meta = yaml.safe_load(parts[1])
    return {t.strip() for t in meta["tools"].split(",")}


# Per-suffix tool-set assertions. Keys are the agent-name suffix
# (after the last ``-`` in the agent name); values are the required +
# forbidden tool sets for that suffix.
ROLE_PROFILES: dict[str, dict[str, set[str]]] = {
    "drafter": {
        "required": {"Read", "Write"},
        # Drafter writes the new <thread>.{N+1}/ directory from scratch; it
        # does not edit existing files. Forbidding Edit catches a class of
        # bug where a drafter accidentally mutates an immutable prior
        # version dir.
        "forbidden": {"Edit"},
    },
    "reviewer": {
        "required": {"Read", "Write"},
        # Reviewers write fresh sidecar dirs only; they never edit in place.
        "forbidden": {"Edit"},
    },
    "reviser": {
        "required": {"Read", "Edit", "Write"},
        "forbidden": set(),
    },
    "auditor": {
        "required": {"Read", "Write"},
        # Auditors write a <thread>.{N}.audit/ sidecar; they don't edit
        # the version body in place.
        "forbidden": {"Edit"},
    },
    "figurer": {
        "required": {"Read", "Write"},
        # Figurer regenerates exhibit/ files which may include both fresh
        # writes and edits; both Write and Edit are allowed (per the
        # generator's PHASE_TOOLS map).
        "forbidden": set(),
    },
}


def suffix_for(agent_stem: str) -> str:
    """Return the last hyphen-segment of the agent name (the role suffix).

    Examples:
        anvil-memo-drafter        → drafter
        anvil-ip-uspto-auditor    → auditor
        anvil-deck-narrative      → narrative (a specialist)
    """
    return agent_stem.rsplit("-", 1)[-1]


@pytest.mark.parametrize("agent_path", sorted(AGENTS_DIR.glob("anvil-*.md")))
def test_role_tool_profile(agent_path: pathlib.Path) -> None:
    """Each lifecycle agent's tool scope matches the role profile."""
    suffix = suffix_for(agent_path.stem)
    profile = ROLE_PROFILES.get(suffix)
    if profile is None:
        # Specialists (deck-narrative, deck-market, deck-design) and any
        # future specialist suffixes are out of scope for this discipline
        # test — they have a single dedicated scope tested separately.
        return
    tools = load_tools(agent_path)
    missing = profile["required"] - tools
    forbidden_present = profile["forbidden"] & tools
    assert not missing, (
        f"{agent_path.name}: {suffix} missing required tool(s): "
        f"{sorted(missing)} (has: {sorted(tools)})"
    )
    assert not forbidden_present, (
        f"{agent_path.name}: {suffix} carries forbidden tool(s): "
        f"{sorted(forbidden_present)} (full set: {sorted(tools)})"
    )


# The 3 deck specialists are critic-shaped (write sidecar, don't edit
# version body) — same scope as reviewers.
DECK_SPECIALIST_STEMS = {
    "anvil-deck-narrative",
    "anvil-deck-market",
    "anvil-deck-design",
}


@pytest.mark.parametrize(
    "agent_stem", sorted(DECK_SPECIALIST_STEMS)
)
def test_deck_specialist_tool_profile(agent_stem: str) -> None:
    """Deck specialists have the same critic-shaped tool profile as reviewers."""
    agent_path = AGENTS_DIR / f"{agent_stem}.md"
    tools = load_tools(agent_path)
    assert {"Read", "Write"}.issubset(tools), (
        f"{agent_stem}: deck specialist missing Read/Write (has: {sorted(tools)})"
    )
    assert "Edit" not in tools, (
        f"{agent_stem}: deck specialist must not carry Edit (writes sidecar only)"
    )
    assert "Task" not in tools, (
        f"{agent_stem}: deck specialist must not carry Task (no recursive fan-out)"
    )
