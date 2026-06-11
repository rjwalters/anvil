# Anvil - Repository Guide

**Anvil Version**: 0.5.0
**Status**: canary-hardened; **14 skills shipped** (10 artifact-class skills + 2 bridge tools: `anvil:project-migrate`, `anvil:rubric-rebackport` + 1 packaging utility: `anvil:project-share` + 1 discovery utility: `anvil:project-scout`); artifact-class rubrics on /44 with dim 9 *Rhetorical economy* (the two ip skills on /45: ip-uspto with dim 9 *Claim-spec correspondence*, ip-uspto-provisional with enablement-depth-dominant weights and dim 9 *Conversion readiness*); per-review version stamping (`rubric_id` / `rubric_total` / `advance_threshold`) shipped in v0.4.0; sidecar atomicity primitive (`anvil/lib/sidecar.py`) consumed by 43 critic-writing commands across all 10 artifact-class skills. See `ROADMAP.md` for current state, `WORK_LOG.md` for merge history, `WORK_PLAN.md` for backlog.

## What is Anvil?

Anvil is a sibling framework to [Loom](https://github.com/rjwalters/loom). Where Loom orchestrates AI code development using GitHub/Gitea as the coordination layer, Anvil orchestrates AI artifact creation using the **filesystem** as the coordination layer.

Ten artifact classes ship as skills (`anvil:memo`, `anvil:pub`, `anvil:report`, `anvil:deck`, `anvil:slides`, `anvil:ip-uspto`, `anvil:installation`, `anvil:proposal`, `anvil:datasheet` (#418) for customer-facing IC/component datasheets, plus `anvil:ip-uspto-provisional` (#433) for USPTO provisional applications — claims-optional, enablement-depth-first, the conversion seed for `anvil:ip-uspto`). Each composes a `draft → review → revise → (audit) → figures` lifecycle, a tunable 9-dimension /44 rubric (the two ip skills on /45), opinionated templates, and a worked example (the datasheet and ip-uspto-provisional worked examples are tracked follow-ups). See `README.md` for the consumer-facing install + usage guide. Two **bridge tool** skills ship alongside: `anvil:project-migrate` (#297) migrates existing studio projects to the post-#295 / post-#296 canonical model (project root + `BRIEF.md` absorbing all config + `<slug>.md` body filename); `anvil:rubric-rebackport` (#358) stamps or rescores legacy /40 reviews under the per-review version stamping contract shipped in v0.4.0. Two **utility** skills round out the set: `anvil:project-share` (#396) collects each thread's `.latest`-resolved source + PDF + assets + per-thread refs and the shared `research/` pool into one shareable, provenance-stamped `SHARE/` folder (marker-guarded blow-away rebuild; `--dry-run` / `--zip` flags); `anvil:project-scout` (#407) is the strictly read-only repo-wide survey — it walks a tree, classifies anvil-adoptable document clusters into an adoption taxonomy (with a foreign-grammar guard that runs BEFORE any `detect_shape` delegation), and reports the recommended next command per cluster.

## Pattern overview

Anvil codifies a pattern for iterative AI-assisted authoring:

- **Versioned directories** (`{thread}.{N}/`) are the unit of artifact state. Each version is immutable.
- **Sibling critic directories** (`.review/`, `.audit/`, `.<critic>/`) hold read-only review output.
- **9-dimension scored rubric** (/44 total; the two ip skills on /45) drives convergence. General threshold ≥35 to advance; ≥39 for customer-facing or legal work (`report`, `deck`, `ip-uspto`, `ip-uspto-provisional`, `datasheet`); critical-flag short-circuits. Per-review version stamping (`rubric_id`/`rubric_total`/`advance_threshold` in `_meta.json`) lets legacy /40 reviews and new /44+ reviews coexist without verdict-logic ambiguity.
- **`_progress.json` checkpointing** per version directory tracks phase state and enables resume.
- **State machine**: `EMPTY → DRAFTED → REVIEWED → REVISED → … → READY → AUDITED` (with skill-specific extensions like `CUSTOMER-READY` for `report` and `FINALIZED` for `ip-uspto`).
- **Command set per skill**: `draft → review → revise → audit → figures`, plus per-skill specialists.
- **N parallel critics, one reviser**: multiple critic siblings feed a single reviser pass — first-class primitive.
- **Deterministic pre-flight before judgment**: cheap mechanical gates (overflow lint, render-gate, page-fit, compile success, placeholder scan) fire *before* the expensive content review.
- **Subprocess-only by default**: renderers (`marp`, `mmdc`, `pdfjam`, `pdftoppm`, `xelatex`, `pandoc`) are CLI binaries. Python deps are optional extras (see `pyproject.toml`).

This is a general pattern for rigorous review/revise loops, designed for AI-agent orchestration but applicable to any structured authoring workflow.

## Repository layout

```
anvil/
  skills/        Per-artifact-type skills (memo, pub, report, deck, slides,
                 ip-uspto, ip-uspto-provisional, installation, proposal,
                 datasheet) plus two bridge tools
                 (project-migrate, rubric-rebackport), one packaging
                 utility (project-share), and one discovery utility
                 (project-scout). Each has SKILL.md +
                 commands/ + (optional) rubric.md, templates/, assets/,
                 examples/, tests/, lib/.
  lib/           Shared framework primitives.
    snippets/    Pure-markdown conventions every skill reads.
    review_schema.py + .json    Typed _review.json contract.
    critics.py                  Discovery + aggregation + verdict.
    convergence.py              Stable-score termination (STALLED verdict).
    cite.py                     DOI/arXiv resolver, BibTeX writer.
    rubric.py + rubric_schema.json    Venue-pinned rubric overlays.
    render.py                   Marp/pandoc/PDF→PNG + preflight helpers.
    vision.py                   VLM critic primitive.
    render_gate.py              LaTeX-skill analog of marp_lint.
    sidecar.py                  staged_sidecar context manager + atomic
                                rename for crash-safe critic-sibling writes.
    figures/                    palette.py + anvil.mplstyle + mermaid-theme.json.
    marp/                       Pinned Marp config.
  templates/     SKILL.md scaffolds.
  roles/         Generic role definitions.

scripts/
  install-anvil.sh   Install anvil into a target repo (--skills= / --dry-run /
                     --check-deps).
  version.sh         Version management across CLAUDE.md + pyproject.toml.

tests/
  lib/           Framework-level tests (schema, critics, cite, convergence,
                 rubric, render, vision, render_gate, figures, imports).
  scripts/       Install-script + version-drift regression tests.

pyproject.toml   Anvil's Python deps (uv-shaped): base dep pydantic;
                 optional extras (e.g. [auto_shrink] for the Marp
                 auto-shrink detector).

README.md        Consumer-facing install + usage guide.
ROADMAP.md       Mission, design philosophy, current state, near-term themes.
AGENTS.md        Loom agent-archetype reference for ongoing development.
WORK_LOG.md      Chronological record of merged PRs and closed issues.
WORK_PLAN.md     Prioritized backlog from current label state.
CHANGELOG.md     Per-version release notes (Keep-a-Changelog format).
```

## Conventions

- **Skill namespace**: `anvil:<type>` (mirrors Loom's `loom:<role>`).
- **Skill files**: `anvil/skills/<type>/SKILL.md` with frontmatter (`name`, `description`, `domain`, `type`, `user-invocable`).
- **Skill identity = artifact identity.** Anvil ships one skill per standardized artifact type (`anvil:memo`, `anvil:ip-uspto`, `anvil:deck`, etc.), not parameterized meta-skills with `--type` flags. When two artifacts share infrastructure (renderer, asset pipeline, scoring primitive), the sharing lives in `anvil/lib/`, not in a unified skill.
- **Presentation renderer**: Anvil-shipped presentation skills (`anvil:deck`, `anvil:slides`) use **Markdown + Marp** as the canonical renderer. The pinned Marp config lives at `anvil/lib/marp/config.yml`; `mmdc → PNG` is the documented working diagram path (inline mermaid leaks as raw code in PDF — see `WORK_LOG.md` PR #72).
- **Versioning**: SemVer, managed by `scripts/version.sh`. Two version-bearing files: `CLAUDE.md`'s `Anvil Version` line and `pyproject.toml`'s `[project] version` line. `version.sh check` enforces drift between them.
- **Python deps**: subprocess-only by default. `pydantic>=2.0` is the lone declared base dep (load-bearing for the schema layer in `anvil/lib/review_schema.py`). Detector-style deps go under `[project.optional-dependencies]` (see `pyproject.toml` top comment).
- **License**: MIT.
- **Coexistence**: Anvil installs alongside Loom in the same consumer repo. CLAUDE.md sections are additive — the installer appends an Anvil section, never overwrites a Loom section.

## Working on this repo (for AI sessions)

Anvil is past the bootstrap phase. Active work is driven by canary friction (the [2AM Logic Studio](https://2amlogic.com) consumer running the framework against real authoring) — *not* by speculative design. See `WORK_PLAN.md` for the live prioritization and `ROADMAP.md` "Near-Term Themes" for recurring patterns likely to drive future issues.

When adding to this repo:

- **Follow the canary signal.** Issues labeled `tier:goal-supporting` are canary-surfaced production friction; `tier:maintenance` is editorial / technical-debt cleanup. New work should usually trace back to one of these.
- **Skill-local first, lib promotion later.** New primitives ship under `anvil/skills/<skill>/lib/` until duplication is observed across skills. The lib extraction pattern (#10, #26, #69, #102, …) is "wait for the second consumer before generalizing."
- **Add Python deps only when subprocess won't do.** The optional-extras philosophy (`pyproject.toml` top comment) is the contract. The `check_*_available()` family in `anvil/lib/render.py` is the precedent for graceful-degradation preflight.
- **Test discipline**: per-skill tests use distinct filenames per the #58 packaging convention; the cross-skill pytest filename collision is solved by `__init__.py` chains in every test directory.
- **Loom orchestrates Anvil-the-framework's development.** This repo uses `loom:issue` / `loom:building` / `loom:review-requested` / `loom:pr` labels and the curate → build → judge → merge cycle. See `AGENTS.md` for the agent-archetype reference.

When implementing or modifying a skill: follow its documented lifecycle commands, use the standard state machine, and produce a `{thread}.{N}/` version dir with sibling `.review/` (and optional `.audit/`, `.<critic>/`) per the framework. Note in the commit message what design decisions were made and any trade-offs considered.

## Status of work

Tracked as open issues at https://github.com/rjwalters/anvil/issues. The v0 punch list is **complete** (8 skills + lib substrate + installer + repo-management discipline; see `CHANGELOG.md` "0.1.0" entry for the full set). Ongoing work is recorded chronologically in `WORK_LOG.md` and prioritized in `WORK_PLAN.md`. Future themes (per-skill audit migrations, memo-side gates, cross-skill lint sharing, render-gate consumer ergonomics) are sketched in `ROADMAP.md` "Near-Term Themes."

<!-- BEGIN LOOM ORCHESTRATION -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration. See `.loom/CLAUDE.md` for the full guide (roles, labels, worktrees, configuration).
<!-- END LOOM ORCHESTRATION -->
