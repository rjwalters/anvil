# anvil/skills/

Per-artifact-type skills. Each subdirectory is one skill, registered as `anvil:<type>` when installed into a consumer repo.

## Skill structure

```
anvil/skills/<type>/
  SKILL.md           Frontmatter + skill prompt
  rubric.md          Review rubric with domain-specific weighted dimensions
                     (most skills ship 8-dim /40; `anvil:memo` and `anvil:proposal`
                     ship 9-dim /44 after issue #244's dim 9 *Rhetorical economy*
                     addition — see each skill's `rubric.md` for the exact shape)
  commands/          Subcommands (draft, review, revise, audit, figures, ...)
    <type>-draft.md
    <type>-review.md
    <type>-revise.md
    <type>-audit.md
    <type>-figures.md
    <type>.md        Portfolio orchestrator
```

## Frontmatter convention

```yaml
---
name: <type>
description: <one-line summary used for skill selection>
domain: <ip|pub|memo|deck|slides|report|kb>
type: skill
user-invocable: false  # true for one-shot escape hatches
---
```

## Planned v0 skills

See repository `README.md` for the v0 skill catalog.

## Shipped skills

The current skill index:

- `anvil:memo` — investment / strategy / position memo.
- `anvil:pub` — academic publication.
- `anvil:report` — customer-facing report.
- `anvil:deck` — slide deck (Marp).
- `anvil:slides` — narrated slide outline.
- `anvil:ip-uspto` — USPTO patent application.
- `anvil:installation` — installation-art concept proposal.
- `anvil:proposal` — multi-document proposal package.
- `anvil:project-migrate` — bridge tool migrating existing projects to the
  post-#295 / post-#296 model (project root + `BRIEF.md` absorbing all
  config + `<slug>.md` body filename). Opinionated, idempotent, dry-run
  first. See `project-migrate/SKILL.md`.

## Adding a new skill

Use the scaffold (planned: `anvil/templates/SKILL.md.j2`). Until that lands, copy an existing skill and edit. Skills should consume `anvil/lib/` primitives rather than reimplementing state machine, rubric, or checkpointing logic.
