# anvil/skills/

Per-artifact-type skills. Each subdirectory is one skill, registered as `anvil:<type>` when installed into a consumer repo.

## Skill structure

```
anvil/skills/<type>/
  SKILL.md           Frontmatter + skill prompt
  rubric.md          Review rubric with domain-specific weighted dimensions
                     (artifact-class skills ship 9-dim /44; the two ip skills
                     ship 9-dim /45 — see each skill's `rubric.md` for the
                     exact shape)
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
- `anvil:paper` — academic publication (research papers).
- `anvil:report` — customer-facing report.
- `anvil:deck` — slide deck (Marp).
- `anvil:slides` — narrated slide outline.
- `anvil:ip-uspto` — USPTO non-provisional utility patent application.
- `anvil:ip-uspto-provisional` — USPTO provisional patent application
  (claims-optional, enablement-depth-first; `anvil-ip-provisional-v1`
  /45 rubric with dim 9 *Conversion readiness*; the conversion seed for
  `anvil:ip-uspto`). See `ip-uspto-provisional/SKILL.md`.
- `anvil:installation` — installation-art concept proposal.
- `anvil:proposal` — multi-document proposal package.
- `anvil:datasheet` — customer-facing IC / component datasheet (mandatory
  spec source-of-truth audit, pin-map/bus-width pre-flight, revision-history
  READY-gate, shared-die SKU coherence). See `datasheet/SKILL.md`.
- `anvil:essay` — short-form voice-grounded essay / blog post
  (markdown-only; `anvil-essay-v1` /44 rubric with voice fidelity as the
  owned dim 2 per the #461 grounding contract; convergence-blocking
  numeric-consistency + hyperlink gates; READY-terminal with a documented
  publish handoff — no audit/figures/PDF). See `essay/SKILL.md`.
- `anvil:primer` — long-form pedagogical explainer: a teach-from-intuition
  companion to a formal spec (report-shaped lifecycle with parallel
  review+audit, pedagogical scaffolding as the dominant dim 1, optional
  `spec_ref` companion input feeding a spec-consistency audit,
  markdown source-of-truth, AUDITED-terminal). See `primer/SKILL.md`.
- `anvil:spec` — normative technical specification maintained truthfully
  against an implementation (normative correctness as the dominant dim 1
  on the ≥39 audit-grade band, optional `code_ref` companion input feeding
  a spec↔implementation consistency audit, LaTeX source-of-truth,
  AUDITED-terminal). See `spec/SKILL.md`.
- `anvil:memoir` — chaptered narrative nonfiction reconstructed from a
  private evidentiary corpus (sourcing fidelity as the dominant dim 1 on
  the ≥39 audit-grade band, dual-corpus claim provenance + dual voice
  tiers, chapter-thread-native, audit-mandatory AUDITED-terminal). See
  `memoir/SKILL.md`.
- `anvil:project-migrate` — bridge tool migrating existing projects to the
  post-#295 / post-#296 model (project root + `BRIEF.md` absorbing all
  config + `<slug>.md` body filename). Opinionated, idempotent, dry-run
  first. See `project-migrate/SKILL.md`.
- `anvil:rubric-rebackport` — bridge tool stamping or rescoring legacy /40
  reviews under the per-review rubric version stamping contract
  (`rubric_id` / `rubric_total` / `advance_threshold`). See
  `rubric-rebackport/SKILL.md`.
- `anvil:project-share` — recurring packaging tool: collects each thread's
  `.latest`-resolved source + PDF + assets + refs and the shared
  `research/` pool into one shareable, provenance-stamped `SHARE/` folder
  (optionally zipped). Marker-guarded blow-away rebuild; `--dry-run` flag.
  See `project-share/SKILL.md`.
- `anvil:project-scout` — repo-wide, strictly read-only discovery of
  anvil-adoptable document clusters: walks a tree, classifies every
  version-dir family / loose document into an adoption taxonomy
  (ALREADY_MIGRATED / LEGACY_MIGRATABLE / BARE_THREADS / LOOSE_DOCUMENTS
  / FOREIGN_GRAMMAR / NOT_DOCUMENT), and reports the recommended next
  command per cluster. See `project-scout/SKILL.md`.
- `anvil:project-photos` — strictly read-only provenance tool: reads a
  human-authored numbering doc for a scanned-photo archive and emits a
  deterministic `manifest.json` provenance map (byte-identical re-runs;
  image manipulation stays consumer-native). See `project-photos/SKILL.md`.
- `anvil:project-book` — assembles a multi-thread project into one
  compiled book: stages each chapter thread's `.latest`-resolved version
  into a consumer-owned master LaTeX document, two-pass compiles it, and
  writes a per-thread `BOOK_REPORT.md`. Build-does-not-block-on-quality;
  marker-guarded blow-away rebuild; `--dry-run`. See
  `project-book/SKILL.md`.
- `anvil:help` — strictly read-only orientation utility: introspects the
  installed skill set and prints a two-tier view (overview, or one
  skill's real command set + rubric threshold + thread layout). Describes
  only what is installed; writes nothing. See `help/SKILL.md`.

## Subagent dispatch (`anvil-<skill>-<phase>`)

Issue #377 ships per-skill-phase subagent registrations alongside the
skills. The canonical agent definitions live at `anvil/agents/anvil-*.md`
(sibling to `anvil/skills/`, `anvil/lib/`, `anvil/roles/`) and the
installer copies them to `<consumer>/.claude/agents/anvil-*.md` so the
harness's `Agent(subagent_type=...)` call can resolve them.

The vocabulary is **per-skill-phase**: each agent name binds a skill to a
lifecycle phase (or, for the deck specialists, to an owned dim group).
The full registry:

- `anvil-<skill>-drafter` — calls `commands/<skill>-draft.md`.
- `anvil-<skill>-reviewer` — calls `commands/<skill>-review.md`.
- `anvil-<skill>-reviser` — calls `commands/<skill>-revise.md`.
- `anvil-<skill>-auditor` — calls `commands/<skill>-audit.md` (skills
  with an audit command: datasheet, deck, ip-uspto, ip-uspto-provisional,
  memoir, paper, primer, proposal, report, slides, spec).
- `anvil-<skill>-figurer` — calls `commands/<skill>-figures.md`.
- `anvil-deck-narrative` / `anvil-deck-market` / `anvil-deck-design` —
  deck-skill specialists owning specific rubric-dim groups (1+7, 3+4, 8).

Example consumer dispatch:

```python
Agent(
    subagent_type="anvil-deck-narrative",
    prompt="Review thread acme-pitch version 3",
)
```

Two net-new frontmatter fields beyond Loom's `name`/`description`/`tools`:

- `staging_pattern` — declared at registration so a future
  `cleanup_one_staging()` integration can scope the per-critic sweep at
  registration time (issue #381 lays the lib-side wire; this issue
  registers the patterns).
- `expected_outputs` — declared sidecar filenames. Documents the contract
  and lets a future harness bypass the Write-heuristic block on names like
  `findings.md`.

The agent registry is generated by `scripts/generate-anvil-agents.py` and
checked into `anvil/agents/`. Re-run the script when a skill's command
list grows or shrinks a lifecycle phase, then commit the diff.

**Out of v0 scope** (follow-up issues):
- Specialty / non-lifecycle agents (`*-vision`, `*-perspective`,
  `*-imagegen`, ip-uspto §101/§112/claims/etc., memo helpers,
  proposal-synthesizer).
- Bridge tool agents (`anvil-project-migrate`, `anvil-rubric-rebackport`).
- Daemon / tmux orchestration analog of `loom-daemon`.

## Adding a new skill

Start from the scaffold at `anvil/templates/SKILL.md`, or copy an existing skill and edit. Skills should consume `anvil/lib/` primitives rather than reimplementing state machine, rubric, or checkpointing logic.
