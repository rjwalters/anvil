# Anvil - Repository Guide

**Anvil Version**: 0.11.0
**Status**: canary-hardened; **24 skills shipped** (14 artifact-class skills + 2 bridge tools: `anvil:project-migrate`, `anvil:rubric-rebackport` + 1 packaging utility: `anvil:project-share` + 1 discovery utility: `anvil:project-scout` + 1 provenance utility: `anvil:project-photos` + 1 assembly utility: `anvil:project-book` + 1 orientation utility: `anvil:help` + 1 prose-cleanup utility: `anvil:deslop` (#898) — iterates arbitrary AI-drafted prose living outside any anvil-authored project (site copy, README fragments, existing markdown/HTML, pasted text) clean of AI-tell rhetoric and voice mismatch via a deterministic-lint (`anvil/lib/rhetoric_lint.py`) + LLM-critique loop reusing `anvil/lib/convergence.py` / `anvil/lib/critics.py` unmodified, honoring a consumer's declared `voice.rhetoric_rules` / voice-grounding docs when pointed at a project; NEVER auto-edits the source, emits cleaned text + rationale + a ready-to-apply diff instead — v1 scope explicitly excludes JSX/TSX source-literal extraction) + 1 diff-viewer utility: `anvil:diff` (#925) — a local, ephemeral, read-only viewer that renders a stdlib-only (`http.server` + `difflib`), word-level (not line-level) side-by-side HTML diff between two anvil version dirs (resolved via `anvil/lib/latest_resolution.py`), a deslop origin/`cleaned.txt` pair, or two arbitrary files, with an optional `.review/` sidecar (`anvil/lib/review_schema.py` scores/findings) + `rhetoric_lint` overlay anchored to the lines they describe; binds `127.0.0.1` only, never writes to any input path, no CDN assets, no in-browser editing in v1 + 1 prior-art-search utility: `anvil:ip-search` (#957) — the missing input half of the ip suite's prior-art workflow: it derives queries from a thread's `BRIEF.md` §3 inventive-feature inventory (the same disclosure denominator the `s112` critic scores against), queries a live corpus via stdlib `urllib` on the `anvil/lib/cite.py` precedent (PatentsView Search primary, USPTO Open Data Portal secondary; API keys read from `PATENTSVIEW_API_KEY` / `USPTO_API_KEY`, Google Patents a documented MANUAL fallback since it has no public API), and writes one `<thread>/prior-art/<slug>.md` per reference in exactly the frontmatter shape `ip-uspto-prior-art` / `ip-uspto-provisional-prior-art` already parse (`title`/`inventors`/`publication_date`/`kind`/`summary` plus a `patent_number`/`assignee`/`url`/`source`/`retrieved` provenance superset); no key degrades gracefully — writes NOTHING, prints the constructed queries + a Google Patents URL per query, exits 0; writes `<thread>/prior-art/` and nothing else (version dirs and critic siblings are refused structurally before any file is opened), never overwrites an already-collected reference without `--force`, and renders no positioning verdict — dim 5 stays the critics'; explicitly a drafting aid, never an attorney clearance search; artifact-class rubrics on /44 with dim 9 *Rhetorical economy* (the two ip skills on /45: ip-uspto with dim 9 *Claim-spec correspondence*, ip-uspto-provisional with enablement-depth-dominant weights and dim 9 *Conversion readiness*; deck on /49 ≥43 with dim 10 *Business-model & unit-economics credibility* post-#550; essay with voice-dominant weights — dim 2 *Voice fidelity* at weight 7 — and a load-bearing dim 9; primer with pedagogy-dominant weights — dim 1 *Pedagogical scaffolding / learnability* at weight 7 — and an optional `spec_ref` companion input feeding a spec-consistency audit; spec with normative-correctness-dominant weights — dim 1 *Normative correctness* at weight 7, ≥39 audit-grade band — and an optional `code_ref` companion input, the mirror image of primer's `spec_ref`, feeding a spec↔implementation consistency audit — the #697 epic is complete: skeleton #706, three-way audit verdict + implementation-status register #707, deterministic constant-consistency gate #708, and a vendored AUDITED worked example #709; memoir (#740) with sourcing-fidelity-dominant weights — dim 1 *Sourcing fidelity* at weight 7, ≥39 audit-grade band — composing dual-corpus claim provenance (#597) and dual voice tiers (#598) active at once in one chapter-threaded, AUDITED-terminal artifact, with the first exhaustive `kind: tool_evidence` corpus-audit critic sibling and photo-placement macros for `anvil:project-photos`); per-review version stamping (`rubric_id` / `rubric_total` / `advance_threshold`) shipped in v0.4.0; sidecar atomicity primitive (`anvil/lib/sidecar.py`) consumed by critic-writing commands across all 14 artifact-class skills (plus terminal package assemblers such as `ip-uspto-provisional-finalize`). See `ROADMAP.md` for current state, `WORK_LOG.md` for merge history, `WORK_PLAN.md` for backlog.

## What is Anvil?

Anvil is a sibling framework to [Loom](https://github.com/rjwalters/loom). Where Loom orchestrates AI code development using GitHub/Gitea as the coordination layer, Anvil orchestrates AI artifact creation using the **filesystem** as the coordination layer.

Fourteen artifact classes ship as skills (`anvil:memo`, `anvil:paper`, `anvil:report`, `anvil:deck`, `anvil:slides`, `anvil:ip-uspto`, `anvil:installation`, `anvil:proposal`, `anvil:datasheet` (#418) for customer-facing IC/component datasheets, `anvil:ip-uspto-provisional` (#433) for USPTO provisional applications — claims-optional, enablement-depth-first, the conversion seed for `anvil:ip-uspto` — `anvil:essay` (#460) for short-form voice-grounded essays/blog posts: markdown-only, voice fidelity as the owned dim 2 consuming the #461 grounding contract, convergence-blocking numeric/link gates, READY-terminal with a documented publish handoff — `anvil:primer` (#686) for long-form pedagogical explainers: a teach-from-intuition companion to a formal spec, report-shaped lifecycle with parallel review+audit, pedagogical scaffolding as the owned dominant dim 1, an optional `spec_ref` companion input feeding a spec-consistency audit, markdown source-of-truth with an optional PDF, AUDITED-terminal — plus `anvil:spec` (#697/#706) for normative technical specifications maintained truthfully against an implementation: report-shaped lifecycle with parallel review+audit, normative correctness as the owned dominant dim 1 on the ≥39 audit-grade band, an optional `code_ref` companion input (the mirror image of primer's `spec_ref`) feeding a spec↔implementation consistency audit, LaTeX source-of-truth with an optional PDF, AUDITED-terminal; the #697 epic is complete — skeleton #706, three-way audit verdict + implementation-status register #707, deterministic constant-consistency gate #708, and a vendored AUDITED worked example #709 — plus `anvil:memoir` (#740) for chaptered narrative nonfiction reconstructed from a private evidentiary corpus: chapter-thread-native (one thread per chapter, assembled via `anvil:project-book`), sourcing fidelity as the owned dominant dim 1 on the ≥39 audit-grade band, composing dual-corpus claim provenance (#597) and dual voice tiers (#598) active at once, audit-mandatory with `AUDITED` as the terminal state). Each composes a `draft → review → revise → (audit) → figures` lifecycle (essay deliberately ships draft/review/revise/status only — no audit, no figures, no PDF), a tunable 9-dimension /44 rubric (the two ip skills on /45; deck on 10-dim /49 post-#550), opinionated templates, and a worked example. See `README.md` for the consumer-facing install + usage guide. Two **bridge tool** skills ship alongside: `anvil:project-migrate` (#297) migrates existing studio projects to the post-#295 / post-#296 canonical model (project root + `BRIEF.md` absorbing all config + `<slug>.md` body filename); `anvil:rubric-rebackport` (#358) stamps or rescores legacy /40 reviews under the per-review version stamping contract shipped in v0.4.0. Six **utility** skills round out the set: `anvil:project-share` (#396) collects each thread's `.latest`-resolved source + PDF + assets + per-thread refs and the shared `research/` pool into one shareable, provenance-stamped `SHARE/` folder (marker-guarded blow-away rebuild; `--dry-run` / `--zip` flags); `anvil:project-scout` (#407) is the strictly read-only repo-wide survey — it walks a tree, classifies anvil-adoptable document clusters into an adoption taxonomy (with a foreign-grammar guard that runs BEFORE any `detect_shape` delegation), and reports the recommended next command per cluster; `anvil:project-photos` (#599) reads a human-authored numbering doc for a scanned-photo archive and emits a deterministic `manifest.json` provenance map (original capture → stable name + archive item IDs + rotation hint + `multi_item` flag, plus a `missing_captures` list) — strictly read-only over the source images, byte-identical re-runs, image manipulation stays consumer-native; `anvil:project-book` (#596) assembles a multi-thread project into one compiled book — it stages the `.latest`-resolved version of every chapter thread into a consumer-owned master LaTeX document (`book.tex`, controlled by a skill-local `build:` block in `BRIEF.md`), two-pass compiles it via `compile_and_gate`, and writes a per-thread `BOOK_REPORT.md` (state/score/audit + next command); build-does-not-block-on-quality (EMPTY/missing threads get placeholder chapters, below-READY threads warn), marker-guarded blow-away rebuild of the chapters dir, `--dry-run`; and `anvil:help` (#725) is the strictly read-only orientation utility — it introspects the installed skill set (from `.anvil/install-metadata.json`'s `installed_skills`, falling back to a `.claude/skills/anvil-*/` directory scan in degraded mode) and prints a two-tier view: `anvil:help` gives a one-screen overview (installed skills grouped into artifact-class vs utility/bridge-tool, the common artifact lifecycle with its documented per-skill variations, and a "start here" pointer), `anvil:help <skill>` gives one skill's real command set (derived from its `commands/*.md`), rubric total/threshold (when a `rubric.md` exists), and thread layout; it describes only what is installed, never the upstream catalog, and writes nothing; and `anvil:deslop` (#898) iterates arbitrary AI-drafted prose that lives OUTSIDE any anvil-authored project (website copy, README fragments, existing markdown/HTML files, pasted text) clean of AI-tell rhetoric and voice mismatch — ingest extracts prose from a file path (markdown/HTML passthrough or visible-text extraction) or pasted text with a map back to the origin, then a draft → lint → critique → revise loop runs to convergence: the deterministic `anvil/lib/rhetoric_lint.py` pass honors a consumer's declared `voice.rhetoric_rules` when pointed at a project via `--project`, the LLM critique pass scores a two-dimension mini rubric (rhetorical economy always, voice adherence only when `anvil/lib/project_brief.py::resolve_voice_docs` resolves grounding docs) written as canonical `_review.json`, and `anvil/lib/critics.py` / `anvil/lib/convergence.py` drive aggregation and termination unmodified; it NEVER writes to the ingested source, emitting cleaned text + a per-change rationale + a ready-to-apply diff instead — JSX/TSX/JS/TS source-literal string extraction is explicitly out of scope for v1 (tracked as a follow-up).

## Pattern overview

Anvil codifies a pattern for iterative AI-assisted authoring:

- **Versioned directories** (`{thread}.{N}/`) are the unit of artifact state. Each version is immutable.
- **Sibling critic directories** (`.review/`, `.audit/`, `.<critic>/`) hold read-only review output.
- **9-dimension scored rubric** (/44 total; the two ip skills on /45; deck on 10 dims /49) drives convergence. General threshold ≥35 to advance; ≥39 for customer-facing or legal work (`report`, `ip-uspto`, `ip-uspto-provisional`, `datasheet`; deck ≥43/49); critical-flag short-circuits. Per-review version stamping (`rubric_id`/`rubric_total`/`advance_threshold` in `_meta.json`) lets legacy /40 reviews and new /44+ reviews coexist without verdict-logic ambiguity.
- **`_progress.json` checkpointing** per version directory tracks phase state and enables resume.
- **State machine**: `EMPTY → DRAFTED → REVIEWED → REVISED → … → READY → AUDITED` (with skill-specific extensions like `CUSTOMER-READY` for `report`, `FINALIZED` for `ip-uspto`, and the `NO-GO` thesis-failure terminal for `memo`).
- **Command set per skill**: `draft → review → revise → audit → figures`, plus per-skill specialists.
- **N parallel critics, one reviser**: multiple critic siblings feed a single reviser pass — first-class primitive.
- **Deterministic pre-flight before judgment**: cheap mechanical gates (overflow lint, render-gate, page-fit, compile success, placeholder scan) fire *before* the expensive content review.
- **Subprocess-only by default**: renderers (`marp`, `mmdc`, `pdfjam`, `pdftoppm`, `xelatex`, `pandoc`) are CLI binaries. Python deps are optional extras (see `pyproject.toml`).

This is a general pattern for rigorous review/revise loops, designed for AI-agent orchestration but applicable to any structured authoring workflow.

## Repository layout

```
anvil/
  skills/        Per-artifact-type skills (memo, paper, report, deck, slides,
                 ip-uspto, ip-uspto-provisional, installation, proposal,
                 datasheet, essay, primer, spec, memoir) plus two bridge tools
                 (project-migrate, rubric-rebackport), one packaging
                 utility (project-share), one discovery utility
                 (project-scout), one provenance utility
                 (project-photos), one assembly utility
                 (project-book), one orientation utility
                 (help), one prose-cleanup utility
                 (deslop), one diff-viewer utility
                 (diff), and one prior-art-search utility
                 (ip-search). Each has SKILL.md +
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
  roles/         Generic role definitions (planned).
  agents/        Checked-in per-(skill, phase) agent definitions
                 (anvil-<skill>-<phase>.md), regenerated by
                 scripts/generate-anvil-agents.py.

scripts/
  install-anvil.sh   Install anvil into a target repo (--skills= / --dry-run /
                     --check-deps).
  version.sh         Version management across CLAUDE.md + pyproject.toml.
  generate-anvil-agents.py   Regenerate the checked-in anvil/agents/ files
                     from each skill's command list.
  resync-installed.sh   Refresh installed Anvil surfaces in a consumer repo
                     from the recorded source checkout (#894 — C7).

tests/
  lib/           Framework-level tests (schema, critics, cite, convergence,
                 rubric, render, vision, render_gate, figures, imports).
  scripts/       Install-script + version-drift regression tests.
  agents/        Agent-registry generation + frontmatter-schema tests.
  skills/        Per-skill test packages (one dir per skill).

docs/          Working notes and adapter docs (codex-skill-adapter,
               research/).

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
- **Changelog discipline is part of the PR, not part of the release.** Every `feat` / `fix` / `security` PR records its own `CHANGELOG.md` `[Unreleased]` entry and states a `CHANGELOG:` line in its body. See "Changelog discipline" below for the full contract — this is a real Judge check, not a nicety.
- **The Loom cycle is for substantive work, not every change.** It exists so framework changes get curated, reviewed, and traced to a canary signal — that value is real for a skill, a lib primitive, or a contract shift, and absent for a typo, a stale doc line, a gitignore rule, or a tool-version bump. Small mechanical changes may be committed directly to `main` with a descriptive message; no issue, no branch, no PR. Loom itself does not require the ceremony (its only blocking rules are `gh pr merge` → `.loom/scripts/merge-pr.sh` and no editable installs inside worktrees), so routing trivia through it is a choice, and usually the wrong one. When in doubt about which side a change falls on, ask rather than defaulting to either.

When implementing or modifying a skill: follow its documented lifecycle commands, use the standard state machine, and produce a `{thread}.{N}/` version dir with sibling `.review/` (and optional `.audit/`, `.<critic>/`) per the framework. Note in the commit message what design decisions were made and any trade-offs considered.

### Changelog discipline (the `CHANGELOG:` line)

**The problem this closes** (#1037): at the v0.11.0 cut, a merged-work coverage check found `[Unreleased]` covering ~28 items while the cycle had merged ~50 more `feat`/`fix`/`security` PRs with no entry at all — including two entire new skills (`anvil:ip-search` #969, `anvil:diff` #931) and the Codex CLI parity install path (#1010/#1014). All were reconstructed by hand at release time, which is exactly the expensive archaeology a changelog convention exists to prevent. The convention was real; nothing in the Builder → Judge cycle ever looked, so it degraded silently over one release cycle.

**This lives here, in `CLAUDE.md`, on purpose.** The natural homes for it — `.claude/commands/loom/builder-pr.md`, `.claude/commands/loom/judge.md`, `.claude/commands/repo/release.md` — are *vendored copies* of upstream Loom / Repo-Skills defaults, refreshed wholesale by `.loom/scripts/resync-installed.sh` and `install.sh`. An edit there survives until the next resync and then vanishes. `CLAUDE.md` is anvil-owned, read by every agent session, and outranks role guidance for repo-specific conventions. (A generic version of this rule may be worth proposing upstream to Loom; that would be an issue in `rjwalters/loom`, not a local patch to a synced file.)

**Builder — when your PR title is a `feat`, `fix`, or `security` conventional commit:**

1. Add the entry to `CHANGELOG.md` under `## [Unreleased]`, in the same PR as the change (create the `## [Unreleased]` heading directly under `# Changelog` if the last release consumed it — the release flow promotes that heading to `## [X.Y.Z] — DATE` and does not leave a fresh one behind).
2. State the claim in the PR body's `## Test Plan` section, next to the `TDD:` line:

```
CHANGELOG: yes — <category + one-line summary of the entry you added>
CHANGELOG: no — <reason, e.g. "internal refactor with no user-visible behavior change">
```

Every other conventional-commit type (`docs`, `chore`, `test`, `refactor`, `ci`, `build`, `style`, `perf`) is **exempt**: omit the line, or write `CHANGELOG: no — <reason>`. Do not invent an entry to satisfy the checkpoint; a changelog padded with `chore` noise is worse than a short one.

Write the entry for the *reader of the release notes*, not for the diff: what changed for someone using anvil, with the issue/PR number. Match the surrounding style in `CHANGELOG.md` (Keep-a-Changelog categories: `### Added`, `### Changed`, `### Fixed`, `### Removed`, `### Deprecated`, `### Security`).

**Judge — verify the claim against the diff**, exactly as you already do for `TDD: yes` (`judge.md` § "Test-First (TDD) Claim Verification"):

```bash
./scripts/check-changelog-entry.sh <pr-number>     # 0 = entry or exemption, 1 = missing, 2 = could not check
```

| `CHANGELOG:` line | Diff evidence | Judge action |
|---|---|---|
| `yes` | `CHANGELOG.md` in the diff | pass (skim that the entry actually landed under `[Unreleased]` and is legible) |
| `yes` | no `CHANGELOG.md` in the diff | **blocking finding** — a false `yes` is the same contradiction tier as a false `TDD: yes` |
| `no — <reason>` | — | advisory; weigh the reason, block only if the change is plainly user-facing |
| absent, `feat`/`fix`/`security` title | no `CHANGELOG.md` in the diff | request the entry — this is the silent skip that produced #1037 |
| absent, exempt title | — | pass, no comment |
| any, non-conventional title | — | exit 2 — the check declines to guess; classify by hand and fix the title (`builder-pr.md` § "PR Titles" already requires the format) |

The check is a deterministic pre-flight in the sense of "Pattern overview" above: run it *before* the expensive content review, and treat it as a reporter, not a merge gate. It renders no quality verdict on the entry's prose.

**The release-time coverage check is the backstop, not the mechanism.** `/repo:release` Phase 5 still cross-references merged PRs since the last tag against the drafted entry (`.claude/commands/repo/release.md` § "Merged-work coverage check (advisory)"), and it stays — but it is a *last* line of defense that costs a human release-time reconstruction every time it fires. If it reports a non-trivial gap at the next cut, the fix belongs upstream in this per-PR discipline, not in a better reconstruction script.

## Status of work<!-- BEGIN LOOM ORCHESTRATION -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration — see the Loom repository for the full guide (roles, labels, worktrees, configuration). When installed, Loom also writes a locally-substituted copy of that guide to `.loom/CLAUDE.md`.
<!-- END LOOM ORCHESTRATION -->
<!-- BEGIN REPO-SKILLS -->
This repository has [Repo Skills](https://github.com/rjwalters/repo) v0.10.0 installed —
general repository hygiene and environment commands invoked as `/repo:<command>`. Run
`/repo:help` for the command list, or see `.claude/skills/repo/SKILL.md` for the full
guide. Hygiene commands apply safe, reversible fixes by default and report each
change; run with `--ask` to review first, and `--prune` to allow irreversible
removals. Managed by `install.sh` — edit outside the markers only.
<!-- END REPO-SKILLS -->
