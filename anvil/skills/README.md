# anvil/skills/

Per-artifact-type skills. Each subdirectory is one skill, registered as `anvil:<type>` when installed into a consumer repo.

## Skill structure

```
anvil/skills/<type>/
  SKILL.md           Frontmatter + skill prompt
  rubric.md          8-dimension /40 review rubric (domain-specific weights)
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

## Adding a new skill

Use the scaffold (planned: `anvil/templates/SKILL.md.j2`). Until that lands, copy an existing skill and edit. Skills should consume `anvil/lib/` primitives rather than reimplementing state machine, rubric, or checkpointing logic.
