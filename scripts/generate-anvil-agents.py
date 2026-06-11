#!/usr/bin/env python3
"""Generate the canonical agent definitions under anvil/agents/.

The agent files written by this script are checked into the repo (NOT
generated at install time or runtime). The script exists so the doc-coverage
tests have a single source of truth for the v0 agent registry — re-run it
whenever a skill's command list grows / shrinks a lifecycle phase, then
commit the diff. The generated agents are not runtime dependencies; the
shipping artifact is the markdown under `anvil/agents/`.

Issue #377 — Loom-style subagent pattern. Per-skill-phase vocabulary
(`anvil-<skill>-<phase>`). Lifecycle roles: drafter, reviewer, reviser,
auditor, figurer. Plus 3 deck specialists called out as load-bearing for the
24-critic fan-out (narrative, market, design).

Curator-chosen scope (v0): one agent per (skill, phase) where the
corresponding `commands/<skill>-<phase>.md` file exists, plus the 3 deck
specialists. The arithmetic in the curator's enrichment ("29 lifecycle
types") is off by a few entries — the actual count derived from existing
commands is 38 lifecycle + 3 specialists = 41. See PR description for the
scope-clarification note.
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "anvil" / "skills"
AGENTS_DIR = REPO_ROOT / "anvil" / "agents"

# Lifecycle phases that map to a per-skill-phase agent type. Order matters
# for the per-skill commit grouping in the generated files (drafter comes
# first because the lifecycle starts there).
LIFECYCLE_PHASES = ["draft", "review", "revise", "audit", "figures"]

# The artifact-class skills shipped in anvil/skills/ (8 at v0 + datasheet
# under issue #418 + ip-uspto-provisional under issue #433). Bridge tools
# (project-migrate, rubric-rebackport) and the utility skills
# (project-share packaging, project-scout discovery) are intentionally
# excluded — they are human-invocable utilities, not fan-out targets.
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

# Phase → role display name (used in agent display string).
PHASE_ROLE = {
    "draft": "Drafter",
    "review": "Reviewer",
    "revise": "Reviser",
    "audit": "Auditor",
    "figures": "Figurer",
}

# Phase → agent suffix (e.g., `draft` → `drafter` per the curator's
# vocabulary). The agent name is `anvil-<skill>-<suffix>`.
PHASE_SUFFIX = {
    "draft": "drafter",
    "review": "reviewer",
    "revise": "reviser",
    "audit": "auditor",
    "figures": "figurer",
}

# Tool-scope per phase. Mirrors the curator's table; reviewers do NOT carry
# `Edit` (they write fresh sidecar dirs, not in-place); revisers carry
# `Edit`; drafters carry `Write` for the new version directory.
PHASE_TOOLS = {
    "draft": "Read, Glob, Grep, Write, Bash",
    "review": "Read, Glob, Grep, Bash, Write",
    "revise": "Read, Glob, Grep, Edit, Write, Bash",
    "audit": "Read, Glob, Grep, Bash, Write",
    "figures": "Read, Glob, Grep, Bash, Write, Edit",
}

# Phase → expected output filenames (sidecar contract). Empty list means
# the phase writes a new `<thread>.{N+1}/` version dir rather than a
# sibling sidecar; the harness Write-heuristic doesn't trip on the
# version-dir path so the allowlist is only meaningful for sidecar writers.
PHASE_EXPECTED_OUTPUTS = {
    "draft": [],
    "review": [
        "verdict.md",
        "scoring.md",
        "comments.md",
        "_meta.json",
        "_progress.json",
    ],
    "revise": [],
    "audit": [
        "verdict.md",
        "findings.md",
        "comments.md",
        "_meta.json",
        "_progress.json",
    ],
    "figures": [],
}

# Phase → staging-name pattern used by `anvil/lib/sidecar.py`. The pattern
# uses `{thread}` and `{N}` placeholders mirroring the docs in
# `cleanup_one_staging`. Drafter/reviser write version dirs (no sidecar
# staging pattern); reviewer/auditor/figurer write sidecar dirs.
PHASE_STAGING_PATTERN = {
    "draft": "",
    "review": ".{thread}.{N}.review.tmp/",
    "revise": "",
    "audit": ".{thread}.{N}.audit.tmp/",
    "figures": "",
}

# Phase → one-line role summary surfaced in the agent's body.
PHASE_ROLE_SUMMARY = {
    "draft": "produce the next `{thread}.{N+1}/` version directory by following the canonical drafter procedure",
    "review": "score the latest `{thread}.{N}/` against the rubric and write a read-only review sibling directory",
    "revise": "consume all critic siblings of the latest `{thread}.{N}/` and produce a single revised `{thread}.{N+1}/`",
    "audit": "run the audit gate against a READY version and produce an audit sibling with verdict / findings",
    "figures": "regenerate or update figures and exhibits under the latest `{thread}.{N}/exhibits/`",
}

# Specialist agents for the deck skill (issue #377 friction point 3 — the
# 24-critic fan-out). Each tuple is (suffix, command-stem, role-display,
# one-line-summary, owned-dims).
DECK_SPECIALISTS = [
    (
        "narrative",
        "deck-narrative",
        "Narrative-arc Critic",
        "evaluate the deck as a single narrative argument and score rubric dims 1 (narrative arc) and 7 (ask specificity)",
        "1, 7",
    ),
    (
        "market",
        "deck-market",
        "Market / Competitor Critic",
        "verify TAM/SAM/SOM arithmetic and competitive framing; score rubric dims 3 (market size credibility) and 4 (solution differentiation)",
        "3, 4",
    ),
    (
        "design",
        "deck-design",
        "Design Critic",
        "render the deck to PDF + per-slide PNGs and score rubric dim 8 (design polish) on the rendered artifact",
        "8",
    ),
]
DECK_SPECIALIST_TOOLS = "Read, Glob, Grep, Bash, Write"
DECK_SPECIALIST_EXPECTED_OUTPUTS = [
    "_summary.md",
    "findings.md",
    "comments.md",
    "_meta.json",
    "_progress.json",
]


def render_yaml_list(items: list[str], indent: str = "  ") -> str:
    """Render a list of strings as a YAML block sequence.

    Empty list returns the inline `[]` form so the frontmatter parser sees a
    well-formed empty list rather than the field being absent. The non-empty
    branch returns a leading newline + block-sequence body so the caller can
    write `f"expected_outputs:{render_yaml_list(xs)}"` and get well-formed
    YAML (no trailing space on the key line, no double newline).
    """
    if not items:
        return " []"
    return "\n" + "\n".join(f"{indent}- {item}" for item in items)


def render_lifecycle_agent(skill: str, phase: str) -> str:
    """Render the markdown body for an `anvil-<skill>-<phase>` lifecycle agent."""
    suffix = PHASE_SUFFIX[phase]
    role = PHASE_ROLE[phase]
    tools = PHASE_TOOLS[phase]
    expected_outputs = PHASE_EXPECTED_OUTPUTS[phase]
    staging_pattern = PHASE_STAGING_PATTERN[phase]
    role_summary = PHASE_ROLE_SUMMARY[phase]

    agent_name = f"anvil-{skill}-{suffix}"
    command_stem = f"{skill}-{phase}"
    command_path = f".anvil/skills/{skill}/commands/{command_stem}.md"

    description = (
        f"Anvil {skill.replace('-', ' ').title()} {role} - "
        f"Dedicated subagent that executes the `anvil:{command_stem}` lifecycle command. "
        f"Use when running the {phase} phase of the {skill} skill, including parallel fan-out."
    )

    frontmatter_lines = [
        "---",
        f"name: {agent_name}",
        f"description: {description}",
        f"tools: {tools}",
    ]
    if staging_pattern:
        frontmatter_lines.append(f"staging_pattern: \"{staging_pattern}\"")
    frontmatter_lines.append(
        f"expected_outputs:{render_yaml_list(expected_outputs)}"
    )
    frontmatter_lines.append("---")
    frontmatter = "\n".join(frontmatter_lines)

    body = f"""
You are the Anvil {skill.replace('-', ' ').title()} {role} for the {{{{workspace}}}} repository.

Your role is to {role_summary} for the `anvil:{skill}` skill.

Follow the complete command definition in `{command_path}` for:
- Required inputs (BRIEF.md, latest `<thread>.{{N}}/` dir, critic siblings, refs/, exhibits/)
- Phase outputs and the `_progress.json` checkpoint contract
- Rubric dimensions owned by this phase (when applicable)
- Atomicity / staging contract (the staged_sidecar primitive in `anvil/lib/sidecar.py`)
- Verdict / findings / scoring file shape and the read-only-once-written discipline

Important: This subagent is dispatched parallel-safe. Use the staging pattern declared in this file's frontmatter (`staging_pattern`) and do NOT sweep sibling critic staging directories outside that pattern — the per-critic cleanup contract (issue #381) is load-bearing for parallel fan-out.
"""

    return frontmatter + body


def render_deck_specialist_agent(
    suffix: str, command_stem: str, role: str, summary: str, owned_dims: str
) -> str:
    """Render the markdown body for a deck-specialist agent."""
    agent_name = f"anvil-deck-{suffix}"
    command_path = f".anvil/skills/deck/commands/{command_stem}.md"
    staging_pattern = f".{{thread}}.{{N}}.{suffix}.tmp/"

    description = (
        f"Anvil Deck {role} - "
        f"Specialist subagent that executes the `anvil:{command_stem}` critic command. "
        f"Owns rubric dimensions {owned_dims} of the /40 deck rubric. "
        f"Use when running parallel specialist critics on a deck version directory."
    )

    frontmatter_lines = [
        "---",
        f"name: {agent_name}",
        f"description: {description}",
        f"tools: {DECK_SPECIALIST_TOOLS}",
        f"staging_pattern: \"{staging_pattern}\"",
        f"expected_outputs:{render_yaml_list(DECK_SPECIALIST_EXPECTED_OUTPUTS)}",
        "---",
    ]
    frontmatter = "\n".join(frontmatter_lines)

    body = f"""
You are the Anvil Deck {role} for the {{{{workspace}}}} repository.

Your role is to {summary} for the `anvil:deck` skill.

Follow the complete command definition in `{command_path}` for:
- Required inputs (latest `<thread>.{{N}}/deck.md`, `BRIEF.md`, any supporting figures / refs)
- Owned rubric dimensions ({owned_dims}) and the partial-coverage `_summary.md` shape (un-owned dims remain `null`)
- Sidecar output filenames and the read-only-once-written discipline
- Atomicity / staging contract via `anvil/lib/sidecar.py::staged_sidecar`

Important: This subagent is dispatched parallel-safe alongside the other deck critics. Use the staging pattern `staging_pattern` declared in this file's frontmatter and do NOT sweep sibling critic staging directories — the per-critic cleanup contract (issue #381) is load-bearing for parallel fan-out.
"""

    return frontmatter + body


def enumerate_agents() -> list[tuple[str, str]]:
    """Return [(agent_name, body), ...] for all v0 agent types.

    Only emits an agent when the corresponding `commands/<skill>-<phase>.md`
    file actually exists in the source tree — keeps the registry honest
    against the existing skill surface.
    """
    agents: list[tuple[str, str]] = []
    for skill in ARTIFACT_SKILLS:
        for phase in LIFECYCLE_PHASES:
            command_path = (
                SKILLS_DIR / skill / "commands" / f"{skill}-{phase}.md"
            )
            if not command_path.exists():
                continue
            suffix = PHASE_SUFFIX[phase]
            agent_name = f"anvil-{skill}-{suffix}"
            body = render_lifecycle_agent(skill, phase)
            agents.append((agent_name, body))
    for suffix, command_stem, role, summary, owned_dims in DECK_SPECIALISTS:
        command_path = (
            SKILLS_DIR / "deck" / "commands" / f"{command_stem}.md"
        )
        if not command_path.exists():
            print(
                f"warn: deck specialist command not found: {command_path}",
                file=sys.stderr,
            )
            continue
        agent_name = f"anvil-deck-{suffix}"
        body = render_deck_specialist_agent(
            suffix, command_stem, role, summary, owned_dims
        )
        agents.append((agent_name, body))
    return agents


def main() -> int:
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    agents = enumerate_agents()
    seen: set[str] = set()
    for agent_name, body in agents:
        if agent_name in seen:
            print(f"error: duplicate agent name: {agent_name}", file=sys.stderr)
            return 1
        seen.add(agent_name)
        agent_path = AGENTS_DIR / f"{agent_name}.md"
        agent_path.write_text(body, encoding="utf-8")
    print(f"wrote {len(agents)} agent files under {AGENTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
