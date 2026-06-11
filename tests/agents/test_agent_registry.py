"""Doc-coverage tests for the v0 Anvil subagent registry.

Issue #377 — Loom-style subagent pattern. Per-skill-phase vocabulary
(`anvil-<skill>-<phase>`). The shipping artifact is the markdown under
``anvil/agents/``; these tests enforce the on-disk contract:

- Every file under ``anvil/agents/`` parses to valid YAML frontmatter.
- Every agent's ``name`` matches the filename stem (no drift between
  filename and registry name).
- Every agent body references a real ``anvil/skills/<skill>/commands/
  <command>.md`` path (delegate-to-command contract).
- The set of agents derived from the (skill, phase) cross-product matches
  the on-disk file set (no missing lifecycle agents for a skill that has
  the corresponding command; no orphan agents whose command doesn't exist).
- Net-new frontmatter fields (``staging_pattern``, ``expected_outputs``)
  are well-formed when present.

These tests are pure file-existence + parse + cross-reference; they do NOT
attempt to dispatch a subagent (the harness integration is out of scope for
a pure pytest run).
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "anvil" / "agents"
SKILLS_DIR = REPO_ROOT / "anvil" / "skills"


# Curator-chosen v0 scope (issue #377), grown per-skill as artifact classes
# ship (datasheet under issue #418, ip-uspto-provisional under issue #433).
# Each artifact-class skill gets lifecycle agents for every phase whose
# command exists; deck additionally gets 3 specialist agents (narrative,
# market, design).
ARTIFACT_SKILLS = [
    "memo",
    "deck",
    "report",
    "proposal",
    "installation",
    "pub",
    "slides",
    "ip-uspto",
    "ip-uspto-provisional",
    "datasheet",
]
LIFECYCLE_PHASES = ["draft", "review", "revise", "audit", "figures"]
PHASE_SUFFIX = {
    "draft": "drafter",
    "review": "reviewer",
    "revise": "reviser",
    "audit": "auditor",
    "figures": "figurer",
}
DECK_SPECIALISTS = ["narrative", "market", "design"]


def parse_frontmatter(path: pathlib.Path) -> tuple[dict, str]:
    """Return (frontmatter-dict, body-text) for an agent markdown file."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, (
        f"{path.name}: malformed frontmatter (missing `---` delimiters)"
    )
    meta = yaml.safe_load(parts[1])
    assert isinstance(meta, dict), (
        f"{path.name}: frontmatter did not parse to a dict"
    )
    body = parts[2]
    return meta, body


def expected_agent_names() -> set[str]:
    """Compute the expected v0 agent name set from the source tree.

    Mirrors ``scripts/generate-anvil-agents.py``'s enumeration. We compute
    it here from the disk so the test catches the case where a phase is
    added/removed from a skill (e.g., a new ``installation-audit.md``
    command lands) and the registry hasn't been regenerated.
    """
    expected: set[str] = set()
    for skill in ARTIFACT_SKILLS:
        for phase in LIFECYCLE_PHASES:
            command_path = (
                SKILLS_DIR / skill / "commands" / f"{skill}-{phase}.md"
            )
            if command_path.exists():
                expected.add(f"anvil-{skill}-{PHASE_SUFFIX[phase]}")
    for spec in DECK_SPECIALISTS:
        if (SKILLS_DIR / "deck" / "commands" / f"deck-{spec}.md").exists():
            expected.add(f"anvil-deck-{spec}")
    return expected


def test_agents_dir_exists() -> None:
    """The canonical agent registry directory ships with the repo."""
    assert AGENTS_DIR.is_dir(), (
        f"missing canonical agents dir: {AGENTS_DIR} "
        "(run scripts/generate-anvil-agents.py)"
    )


def test_agent_set_matches_expected() -> None:
    """The on-disk agent set matches the (skill, phase) cross-product.

    Catches three drift modes at once:
    - A new skill command lands (e.g., installation gains an audit command)
      and the agent for that lifecycle phase is missing.
    - A skill command is removed and the agent file remains orphaned.
    - The deck specialist set drifts (one of narrative/market/design is
      removed or renamed without a corresponding agent rename).
    """
    expected = expected_agent_names()
    actual = {
        p.stem for p in AGENTS_DIR.glob("anvil-*.md") if p.is_file()
    }
    missing = expected - actual
    extra = actual - expected
    assert not missing and not extra, (
        f"agent registry drift:\n"
        f"  missing (expected but absent): {sorted(missing)}\n"
        f"  extra   (present but unexpected): {sorted(extra)}\n"
        f"re-run scripts/generate-anvil-agents.py to sync."
    )


@pytest.mark.parametrize("agent_path", sorted(AGENTS_DIR.glob("anvil-*.md")))
def test_each_agent_has_valid_frontmatter(agent_path: pathlib.Path) -> None:
    """Every agent file parses to YAML with the required field set."""
    meta, body = parse_frontmatter(agent_path)
    assert meta["name"] == agent_path.stem, (
        f"{agent_path.name}: `name` ({meta['name']}) does not match filename "
        f"stem ({agent_path.stem})"
    )
    assert "description" in meta and isinstance(meta["description"], str), (
        f"{agent_path.name}: missing `description` field"
    )
    assert "tools" in meta and isinstance(meta["tools"], str), (
        f"{agent_path.name}: missing `tools` field"
    )
    assert "expected_outputs" in meta and isinstance(
        meta["expected_outputs"], list
    ), (
        f"{agent_path.name}: missing or non-list `expected_outputs` field"
    )
    # Body must be non-empty and reference the workspace template variable
    # — the Loom convention for agent system prompts.
    assert body.strip(), f"{agent_path.name}: body is empty"
    assert "{{workspace}}" in body, (
        f"{agent_path.name}: missing `{{{{workspace}}}}` template placeholder"
    )


@pytest.mark.parametrize("agent_path", sorted(AGENTS_DIR.glob("anvil-*.md")))
def test_each_agent_references_real_command(agent_path: pathlib.Path) -> None:
    """Each agent body must point at a real ``commands/<stem>.md`` path.

    The agent shim's load-bearing job is to delegate to a canonical command
    file (mirroring Loom's ``.loom/roles/<role>.md`` delegation). If the
    referenced command file is missing, the agent is a dead-end — the
    subagent reads it and finds nothing.
    """
    _, body = parse_frontmatter(agent_path)
    matches = re.findall(
        r"\.anvil/skills/([\w\-]+)/commands/([\w\-]+\.md)", body
    )
    assert matches, (
        f"{agent_path.name}: body does not reference any "
        ".anvil/skills/<skill>/commands/<command>.md path"
    )
    for skill, command in matches:
        src_path = SKILLS_DIR / skill / "commands" / command
        assert src_path.exists(), (
            f"{agent_path.name}: referenced command file does not exist: "
            f"{src_path}"
        )


@pytest.mark.parametrize("agent_path", sorted(AGENTS_DIR.glob("anvil-*.md")))
def test_unique_agent_names(agent_path: pathlib.Path) -> None:
    """Filename stems are globally unique (no duplicate agent registrations).

    Implemented as a parametrized test so a duplicate surfaces as a single
    file's failure (easier to locate than a list-level assertion).
    """
    stems = [p.stem for p in AGENTS_DIR.glob("anvil-*.md")]
    assert stems.count(agent_path.stem) == 1, (
        f"duplicate agent name: {agent_path.stem} "
        f"(stems list: {sorted(stems)})"
    )
