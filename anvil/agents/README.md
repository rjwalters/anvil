# anvil/agents/

Canonical Anvil **subagent** registrations. Each `anvil-*.md` file is a
thin frontmatter + system-prompt shim that mirrors Loom's
`.claude/agents/loom-*.md` pattern. The installer
(`scripts/install-anvil.sh`, Stage 7.5) copies these files into a
consumer's `.claude/agents/anvil-*.md` so the harness's
`Agent(subagent_type="anvil-...")` call can resolve them.

Issue #377 — v0 of the subagent pattern. Per-skill-phase vocabulary
(`anvil-<skill>-<phase>`); the per-skill specialist exceptions are the
three deck critics that own specific rubric-dim groups
(`anvil-deck-narrative`, `anvil-deck-market`, `anvil-deck-design`).

## Why a sibling directory instead of `anvil/skills/<skill>/agent.md`?

A subagent is a distinct artifact from the skill it points at:

- It has its own tool-scope discipline (drafter ≠ reviewer ≠ reviser).
- It is install-gated separately (the agents/ copy can ship without
  the skills/ copy, e.g. for a future bridge-only release).
- It is doc-coverage-tested as a list (the registry has a well-defined
  cardinality the tests enforce; that's cleaner with one directory than
  with a per-skill subtree).

The pattern mirrors Loom's `.claude/agents/loom-*.md` placement.

## File layout

Each `anvil-<skill>-<phase>.md` has:

```yaml
---
name: anvil-<skill>-<phase>
description: <one-line dispatch description>
tools: <comma-separated harness tool names>
staging_pattern: ".{thread}.{N}.<phase>.tmp/"   # critic phases only
expected_outputs:                                # critic phases only
  - <sidecar filename>
  - ...
---
You are the Anvil <Display Name> for the {{workspace}} repository.

Your role is to <one-line summary>.

Follow the complete command definition in `.anvil/skills/<skill>/commands/<command>.md` for:
- <bullet 1>
- ...
```

## Regeneration

The files in this directory are produced by
`scripts/generate-anvil-agents.py`. The script reads each skill's command
list and emits the agent files. Run it (and commit the diff) when:

- A skill gains or loses a lifecycle command
  (`<skill>-{draft,review,revise,audit,figures}.md`).
- The frontmatter schema changes
  (`tools` list, `staging_pattern`, `expected_outputs`).
- The system-prompt template changes.

A regression test
(`tests/agents/test_generator_idempotent.py`) keeps the checked-in files
in sync with the generator.

## Tests

- `tests/agents/test_agent_registry.py` — every file parses, every
  agent body references a real command, the registry set matches the
  (skill, phase) cross-product derived from the existing commands.
- `tests/agents/test_agent_frontmatter_schema.py` — required + optional
  field set, tool allowlist, well-formed `staging_pattern` and
  `expected_outputs`.
- `tests/agents/test_tool_scope_by_role.py` — drafter / reviewer /
  reviser / auditor / figurer tool profiles are enforced; reviewers
  forbid `Edit`; specialists forbid `Edit` + `Task`.
- `tests/agents/test_install_anvil_agents.py` — the install script
  copies all agents into `.claude/agents/`, preserves non-anvil agents
  through reinstall, and the dry-run path is side-effect-free.
- `tests/agents/test_generator_idempotent.py` — re-running the
  generator must produce byte-identical output to the checked-in files.

## Deferred scope

Per the curator enrichment on #377, the v0 registry excludes:

- Specialty / non-lifecycle agents (`*-vision`, `*-perspective`,
  `*-imagegen`, `*-imagegen-adapter`, ip-uspto §101 / §112 / claims /
  intake / inventorship / prior-art / pre-flight / finalize, memo
  citations / hyperlinks / image-accessibility / figure-content /
  render / migrate / migrate-refs, report claim-figure-grounding /
  figure-content, paper-litsearch, slides-outline / handout / rehearse,
  deck-brief / imagegen / imagegen-adapter, proposal-synthesize /
  proposal-perspective).
- Bridge tool agents (`anvil-project-migrate`,
  `anvil-rubric-rebackport`) — one-shot human-invocable; no fan-out
  benefit.
- The daemon analog of `loom-daemon` and the tmux + multi-account
  orchestration cross-pollination.

Three follow-up issues are planned for these (see PR #377 description).
