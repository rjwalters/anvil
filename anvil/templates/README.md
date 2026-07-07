# anvil/templates/

Scaffolds for new skills and rubrics. Used by a `scripts/new-skill.sh` (planned) and by humans copying a starting point.

## Shipped templates

| Template | Purpose |
|---|---|
| `themes/starter/` | Consumer starter theme (issue #471). `scripts/install-anvil.sh` Stage 7.8 scaffolds it to `<consumer>/.anvil/themes/starter/` when `memo` is among the selected skills (skip-if-exists — the installer never overwrites files under `.anvil/themes/`). Ships `theme.yml` plus a navy-accented `memo/styles.css` that preserves the framework default's functional baseline (booktabs-class tables, `@page` footer). |
| `voice/` | Starter voice-grounding docs (issue #576). De-personalized templates `STYLE_GUIDE.template.md` and `VOCABULARY.template.md` — schema, not content; every author-specific example is a marked `<!-- replace me -->` placeholder. `scripts/install-anvil.sh` Stage 7.9 scaffolds them under `<consumer>/.anvil/voice/` as `STYLE_GUIDE.md` / `VOCABULARY.md` when a voice-consuming skill (`essay` or `memo`) is selected (per-file skip-if-exists — never clobbers an existing grounding doc; prints the `voice:` YAML to paste rather than editing `BRIEF.md`). The ship-now half of the four-doc taxonomy from `anvil/lib/snippets/voice_grounding.md`; `VALUES.md` (#578), private grounding (#577), and the vocab CLI tool (#579) are deferred. See `voice/README.md`. |

## Planned templates

| Template | Purpose |
|---|---|
| `SKILL.md.j2` | Skill frontmatter + state machine + directory layout boilerplate |
| `rubric.md.j2` | 8-weighted-dimensions, /40, critical-flag review rubric |
| `command-draft.md.j2` | Draft subcommand scaffold |
| `command-review.md.j2` | Review subcommand scaffold |
| `command-revise.md.j2` | Revise subcommand scaffold |
| `command-audit.md.j2` | Audit subcommand scaffold |
| `command-figures.md.j2` | Figures/assets subcommand scaffold |

None of these exist yet.
