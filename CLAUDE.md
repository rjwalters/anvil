# Anvil - Repository Guide

**Anvil Version**: 0.0.1
**Status**: Alpha — skeleton only, skills being implemented

## What is Anvil?

Anvil is a sibling framework to [Loom](https://github.com/rjwalters/loom). Where Loom orchestrates AI code development using GitHub/Gitea as the coordination layer, Anvil orchestrates AI artifact creation (investment memos, patents, papers, decks, reports) using the **filesystem** as the coordination layer.

## Pattern overview

Anvil codifies a pattern for iterative AI-assisted authoring:

- **Versioned directories** (`{thread}.{N}/`) are the unit of artifact state. Each version is immutable.
- **Sibling critic directories** (`.review/`, `.audit/`, `.critic/`, etc.) hold read-only review output.
- **8-dimension scored rubric** (/40 total) drives convergence. Threshold ≥32 to advance; ≥35 for legal/customer-facing work; critical-flag short-circuits.
- **`_progress.json` checkpointing** per version directory tracks phase state and enables resume.
- **State machine**: `EMPTY → DRAFTED → REVIEWED → REVISED → … → READY → AUDITED`.
- **Command set per skill**: `draft → review → revise → audit → figures`, plus a portfolio orchestrator.
- **N parallel critics, one reviser**: multiple critic siblings feed a single reviser pass — first-class primitive.

This is a general pattern for rigorous review/revise loops, designed for AI-agent orchestration but applicable to any structured authoring workflow.

## Repository layout

```
anvil/
  skills/        Per-artifact-type skills
  lib/           Framework code (Python, planned)
  templates/     SKILL.md scaffolds
  roles/         Generic role definitions
scripts/
  install-anvil.sh
  version.sh
```

## Conventions

- **Skill namespace**: `anvil:<type>` (mirrors Loom's `loom:<role>`).
- **Skill files**: `anvil/skills/<type>/SKILL.md` with frontmatter (`name`, `description`, `domain`, `type`, `user-invocable`).
- **Skill identity = artifact identity.** Anvil ships one skill per standardized artifact type (`anvil:memo`, `anvil:ip-uspto`, `anvil:deck`, etc.), not parameterized meta-skills with `--type` flags. When two artifacts share infrastructure (renderer, asset pipeline), the sharing lives in `anvil/lib/`, not in a unified skill.
- **Presentation renderer**: Anvil-shipped presentation skills (`anvil:deck`, `anvil:slides`) use **Markdown + Marp** as the canonical renderer. Beamer LaTeX is available only as a consumer-side override (for users with hard constraints like conference proceedings requiring LaTeX submission). The shared Marp + figure pipeline lands in `anvil/lib/` per #10.
- **Versioning**: SemVer, managed by `scripts/version.sh`. `CLAUDE.md`'s `Anvil Version` line is the source of truth.
- **License**: MIT.
- **Coexistence**: Anvil installs alongside Loom in the same consumer repo. CLAUDE.md sections are additive — the installer appends an Anvil section, never overwrites a Loom section.

## Working on this repo (for AI sessions)

This repo is being bootstrapped. **Do not add speculative code.** Implement skills directly from the documented pattern (state machine, rubric, version-dir + sibling-critic layout). The framework `lib/` emerges from observed duplication after the first few skill implementations land — do not design it up-front.

When implementing a skill: follow the documented lifecycle commands (draft/review/revise/audit/figures), use the standard state machine, and produce a `{thread}.{N}/` version dir with sibling `.review/` (and optional `.audit/`, `.critic/`, etc.) per the framework. Note in the commit message what design decisions were made and any trade-offs considered.

## Status of work

Tracked as open issues at https://github.com/rjwalters/anvil/issues. v0 punch list:

- ~~#1~~ — Resolved: install layout = `.anvil/skills/<name>/` + thin `.claude/skills/anvil/<name>/` registration
- ~~#2~~ — Resolved: `anvil:deck` and `anvil:slides` are separate skills (skill identity = artifact identity); both required to use Marp (renderer pinned at framework level)
- #3 — Implement `anvil:memo` skill *(in flight: PR #13 awaiting merge)*
- #4 — Implement `anvil:ip-uspto` skill
- #5 — Implement `anvil:pub` skill
- #6 — Implement `anvil:deck` skill (Marp)
- #7 — Implement `anvil:slides` skill (Marp)
- #8 — Implement `anvil:report` skill
- ~~#9~~ — Deferred from v0 (KB violates load-bearing primitives; revisit under a future "reference skill" category)
- #10 — Implement `anvil/lib/` framework primitives (blocked by ≥2 skill implementations; includes shared Marp/figure pipeline for presentation skills)
- #11 — Implement `scripts/install-anvil.sh`
- ~~#12~~ — Reverted: unified `anvil:presentation` was the wrong design move (would have been the only meta-skill in an artifact-identified catalog)

<!-- BEGIN LOOM ORCHESTRATION -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration. See `.loom/CLAUDE.md` for the full guide (roles, labels, worktrees, configuration).
<!-- END LOOM ORCHESTRATION -->
