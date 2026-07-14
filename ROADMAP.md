# Anvil Roadmap

**Mission**: Make iterative AI-assisted authoring of long-form artifacts as principled as software engineering is — versioned, reviewable, resumable, and audit-trailed.

Anvil orchestrates drafting, review, audit, and revision of memos, research papers, patent applications (non-provisional and provisional), pitch decks, talk slides, technical reports, IC/component datasheets, art-installation concepts, customer proposals, voice-grounded essays, pedagogical primers, and normative specifications. Each artifact lives in an immutable versioned directory; each review pass writes to a read-only sibling; each revision consumes both and produces the next version. The version history *is* the audit trail.

We use the **filesystem as substrate** so the pattern works on a single laptop with no GitHub account, no SaaS dependency, and no proprietary lock-in. We use a **scored rubric** (9 weighted dimensions / 44 — the two `ip-uspto` skills on /45, `deck` on /49 — ≥35 to advance, ≥39 for customer-facing and legal work, critical-flag short-circuit) so the convergence criterion is mechanical, not vibes. We use **N parallel critics → one reviser** as a first-class primitive so subject-matter critics can be added by composition, not orchestration.

## Design Philosophy

1. **Skill identity = artifact identity.** One skill per standardized artifact type, not parameterized meta-skills with `--type` flags. When two skills share infrastructure (renderer, palette, scoring), the sharing lives in `anvil/lib/`, not by collapsing the skills.

2. **Filesystem as substrate.** Versioned directories are the unit of state; sibling directories are the unit of review output; `_progress.json` is the unit of resumability. No database, no forge dependency, no orchestration daemon.

3. **Deterministic gates before judgment.** Cheap mechanical checks (overflow lint, render-gate, page-fit, compile success, placeholder scan) fire *before* the expensive content review. Don't spend an 8-dimension web-fact-checking review on an artifact that doesn't even fit the page contract.

4. **Separation of concerns.** Review is read-only. Revision is separate. Audit is a distinct tool-augmented fact-check (`kind: tool_evidence`). Figure generation is its own role. Rendered-artifact review (`kind: vision`) is a fourth.

5. **Opinionated defaults, override liberally.** Anvil-shipped skills are starting points. Consumers extend them per-project via `.anvil/skills/<name>/` — voice, rubric overlays, templates, asset generators, custom critics.

6. **Subprocess-only by default; Python deps are always optional.** The core install requires no Python packages — renderers (`marp`, `mmdc`, `pdfjam`, `pdftoppm`, `xelatex`, `pandoc`) are subprocess calls. Advanced detectors that need a Python library are exposed as opt-in extras (`uv pip install -e .[auto_shrink]`).

7. **Canary-driven development.** Anvil is sharpened by being used. The [2AM Logic Studio canary](https://2amlogic.com) runs the framework against real authoring work; the friction it surfaces drives the prioritization. Issues labeled `tier:goal-supporting` are canary-surfaced production signal; `tier:maintenance` is technical debt and editorial cleanup.

---

## Current State (v0.9.0)

The complete authoring lifecycle is supported for **thirteen artifact classes**:

| Skill | Artifact type | Output |
|---|---|---|
| `anvil:memo` | Investment / decision memos, internal documents (NO-GO thesis-failure terminal) | Markdown |
| `anvil:paper` | Research papers, with venue-pinned rubric overlays + litsearch (renamed from `pub`, #694) | LaTeX → PDF |
| `anvil:report` | Customer-facing technical reports (engagement findings, audits, advisories) | Markdown / LaTeX → PDF |
| `anvil:deck` | Investor pitch decks (10-dim /49 rubric, ≥43) | Marp Markdown → PDF |
| `anvil:slides` | Talk / conference slides + speaker notes | Marp Markdown → PDF |
| `anvil:ip-uspto` | USPTO non-provisional utility patent applications (/45 rubric) | LaTeX → PDF |
| `anvil:ip-uspto-provisional` | USPTO provisional applications — claims-optional, enablement-depth-first, conversion seed for `anvil:ip-uspto` (/45) | LaTeX → PDF |
| `anvil:installation` | Experiential / installation artwork (concept proposals) | LaTeX → PDF |
| `anvil:proposal` | Buildable-system proposals (pre-contract bookend to `anvil:report`) | LaTeX → PDF |
| `anvil:datasheet` | Customer-facing IC / component datasheets (deterministic pinmap / bus-width consistency gates) | LaTeX → PDF |
| `anvil:essay` | Short-form voice-grounded essays / blog posts (voice fidelity as dominant dim 2; READY-terminal) | Markdown |
| `anvil:primer` | Long-form pedagogical explainers (pedagogy-dominant dim 1; optional `spec_ref` consistency audit) | Markdown (+ optional PDF) |
| `anvil:spec` | Normative technical specifications maintained against an implementation (normative-correctness dim 1, ≥39; optional `code_ref` consistency audit) | LaTeX (+ optional PDF) |

Each skill ships a complete `draft → review → revise → (audit) → figures` lifecycle (with skill-specific variations — e.g. `essay` ships draft/review/revise/status only), a 9-dimension /44 rubric (the two `ip-uspto` skills on /45, `deck` on 10-dim /49), opinionated templates, a worked example thread, and tests.

**Bridge + utility skills** round out the set: `anvil:project-migrate` and `anvil:rubric-rebackport` (contract-shift bridges), `anvil:project-share` (shareable provenance-stamped export), `anvil:project-scout` (read-only repo survey), `anvil:project-photos` (scanned-archive provenance manifest), and `anvil:project-book` (multi-thread book assembly). Nineteen skills ship in total.

### Shared framework primitives (`anvil/lib/`)

| Module | Purpose | Introduced |
|---|---|---|
| `snippets/` | Pure-markdown conventions every skill reads (progress, timestamp, version_layout, thread_state, state_machine, rubric, critics, scorecard_kind, audit, cite) | #10 |
| `review_schema.py` + `.json` | Typed `_review.json` contract: `kind ∈ {judgment, tool_evidence, vision}` + JSON Schema export | #26 |
| `critics.py` | Sibling-critic discovery, aggregation, verdict computation; legacy-shape adapters | #26 |
| `convergence.py` | `check_stable` + `decide_termination` — multi-iteration termination with `STALLED` verdict | #27 |
| `cite.py` | DOI / arXiv resolver, BibTeX writer, idempotent `refs.bib` (stdlib only) | #28 |
| `rubric.py` + `rubric_schema.json` | Rubric models + venue-pinned overlay discovery (`.anvil.json: venue` → optional advisory rubric) | #33 |
| `render.py` | Marp → PDF, PDF → PNGs, pandoc → PDF, matplotlib walker, `check_*_available()` preflight helpers | #30 |
| `vision.py` | `VisionCritic` + `VisionRubric` — vision-model review of rendered artifacts | #30 |
| `render_gate.py` | Deterministic gate over compiled PDFs (page-fit, overfull boxes, compile success, placeholder scan, source-driven glyph verification, embedded-image assertion); LaTeX-skill analog of `marp_lint` | #64, #692 |
| `sidecar.py` | `staged_sidecar` context manager + atomic rename for crash-safe critic-sibling writes; consumed by 60 critic-writing commands across all 13 artifact-class skills | #346 |
| `numeric_consistency.py` | Deterministic claim-vs-claim numeric-consistency gate (within a body); consumed by `essay` / `memo` / `paper` review | #462 |
| `figures/palette.py` + `anvil.mplstyle` + `mermaid-theme.json` | Shared figure-theming substrate (navy palette + 4 semantic mermaid classDefs + per-glyph font fallback for Unicode arrows) | #74, #92 |
| `marp/config.yml` | Pinned Marp config (MathJax + html, `mmdc → PNG` as the working diagram path) | #32 |

### Other shipped infrastructure

- **`scripts/install-anvil.sh`** with `--skills=` filter, `--dry-run`, `--check-deps`, quoted-path safety (#15, #80, #81, #82, #85).
- **`pyproject.toml`** with uv conventions + optional extras for opt-in Python detectors (#102/#105 — Anvil's first declared Python dep file).
- **CSS-drift guard** (#74) — unit test that fails CI if `palette.py` constants drift from `anvil-deck.css :root`.
- **`marp_lint`** (#31) + four named lint rules including `figure-italic-supporting-line-too-long` (#101) — source-side checks before render.
- **Auto-shrink detector** (#102) — image-based detection of silent Marp fit-to-frame, image-based via existing `pdftoppm` chain + Pillow + numpy.
- **Per-skill vision critics** (#45, #46, #47, #48) — slides, paper, report, ip-uspto all have rendered-artifact review.

---

## Core Challenges for AI-Assisted Authoring

These are the fundamental challenges agents face when drafting long-form artifacts, and how Anvil addresses them:

| Challenge | Description | Anvil's approach |
|---|---|---|
| Convergence is non-mechanical | "Is this good enough?" is judgment; agents don't agree | Scored rubric: 9 weighted dimensions / 44 (≥35 to advance, ≥39 customer-facing/legal), critical-flag short-circuit, stable-score termination (#27), per-review version stamping so legacy /40 and current /44+ reviews coexist |
| Drift between revisions | Critics surface findings; revisers silently lose context | Sibling-critic directories are immutable; revisers read prior version + ALL siblings + write a `changelog.md` mapping findings to changes |
| Wasted expensive reviews | Reviewer scores a 4-page memo against a 3-page contract | Deterministic pre-flight (render-gate, marp_lint, mmdc preflight) fires *before* content review |
| Single-perspective review | One reviewer = one set of blind spots | N parallel critics → one reviser (#10/#26): rubric reviewer + venue-pinned reviewer + vision critic + audit critic all feed the same reviser pass |
| Fact-check vs style-check confusion | "Is the prose good?" and "Is the cited URL real?" are different jobs | Codified `.review/` vs `.audit/` split (#29): `kind: judgment` (LLM-only) vs `kind: tool_evidence` (with `tool_calls[]`) |
| Rendered output ≠ source | Markdown looks fine; PDF clips, off-palette, wrong fonts | Vision critics (#30/#45-48), figure-theming substrate (#74/#92), `marp_lint` + auto-shrink detector (#31/#102) |
| Resumability under failure | Long pipelines + crashes = wasted work | `_progress.json` checkpointing per version directory; phases skip on resume; validation by file existence |
| Off-brand or off-tone output | Each author hand-rolls colors/fonts/voice | Shared `palette.py` + `mermaid-theme.json` + per-skill voice overrides via `.anvil/skills/<name>/voice.md` |

---

## Near-Term Themes

Active work is canary-driven — see [open issues](https://github.com/rjwalters/anvil/issues) for the live punch list. Items labeled `tier:goal-supporting` are higher-leverage canary friction; `tier:maintenance` is editorial / technical debt.

Recurring themes likely to drive future issues:

1. **Per-skill `lib/` extraction → `anvil/lib/`.** Several primitives that started skill-local (deck's `marp_lint`, deck's `auto_shrink_detector`, report's `ack.py` / `audit_flags.py` / `pdf_freshness.py`) are candidates for promotion to `anvil/lib/` once a second skill needs them. Trigger: observed duplication, not anticipated need.

2. **Audit-command migrations.** Five skills (`paper`, `report`, `deck`, `slides`, `ip-uspto`) have `*-audit` commands that pre-date the `kind: tool_evidence` codification in #29. Per-skill migrations to emit typed `_review.json` are filed separately.

3. **Memo-side gates.** `anvil:memo` is markdown-first (maintainer decision, #64); a markdown-appropriate length proxy + clean-output gate could ship as the memo analog of `render_gate` if canary friction emerges.

4. **Cross-skill lint sharing.** `marp_lint` is duplicated between deck and slides via `importlib` shim (#38); a deeper consolidation would be a `lib/` extraction following theme #1.

5. **Render-gate consumer adoption.** Five paginated skills have `render_gate` wired (#64). Per-thread `.anvil.json` overrides (page_cap, etc.) are part of the contract; consumer-side ergonomics for setting these will surface friction.

6. **Reference-skill category.** Originally floated as #9 and deferred (KB violates load-bearing primitives). May return as a distinct skill family if canary use cases emerge.

7. **Portfolio orchestrators.** Each skill is single-thread today; portfolio-level commands (e.g. `slides.md`'s gap detector, #85) are nascent. A general orchestrator pattern in `anvil/lib/` is plausible if patterns repeat.

### Candidate artifact classes (ideation)

Ideation only — **none of these is committed work.** Per theme "Canary-driven development," a new artifact class ships when a live downstream consumer produces the genre and hits friction none of the current classes fit (the way botho drove `primer` #686 and `spec` #697). This list records the candidates worth reaching for *when* that signal appears; it is not a build queue.

The bar a candidate must clear (what separated `primer`/`spec` from being `report` variants): (a) a **dominant success metric** that is a genuinely new axis, not one of an existing skill's dimensions; (b) real genre conventions a rubric can encode; (c) ideally a **companion input feeding a consistency audit** — the `spec_ref`/`code_ref` pattern is now reusable infrastructure and is anvil's differentiator over a generic "write me a doc" prompt; (d) deterministic pre-flight gates are possible.

Strongest candidates, each mapped to the pattern:

| Candidate | Dominant metric (new axis) | Companion input / audit | Notes |
|---|---|---|---|
| `app-note` (application note) | Design-in reproducibility — an engineer following it reaches a working circuit | `datasheet_ref` → does the note contradict the part's actual limits? (reuses the `code_ref` audit shape) | **Highest-signal candidate**: neighbor to the shipped `datasheet`, plausible live consumer (sphere / semiconductor). "Tutorial, for hardware." |
| `api-reference` | Accuracy + completeness against the API surface | `code_ref` / OpenAPI doc → every public symbol documented, no documented symbol that doesn't exist | Nearly falls out of `spec` for free; add a deterministic completeness gate. |
| `runbook` | Executable safety — every step unambiguous, ordered, verifiable, reversible | reference to the scripts/infra it drives | Distinct from `installation` (one-time setup) and `spec` (normative description). Natural gates: every step has a verification + a rollback. |
| `tutorial` / `how-to` | Task-completion success — reader reaches a working end state | the tool/API being taught | The task-completion sibling to `primer`'s concept-explanation. Clear boundary against `primer`. |
| `threat-model` | Attack-surface coverage + severity calibration | system architecture / code | Audit-grade like `spec`/`report`; distinctive and increasingly in demand. |

Explicitly **not** their own class (fold into an existing skill — recorded so the line is documented):

- ADR → a `memo` variant (decision record with a thesis).
- case-study, market / competitive analysis → `report` variants.
- RFP response → a `proposal` variant.
- literature review → already inside `paper` (litsearch).
- thesis, course, multi-lesson curriculum → `project-book` assembly, not a new class.
- release-notes → likely a *utility* (generated against a git range), not an authored artifact class — cf. the deferred "Reference-skill category" (theme 6).

---

## What Anvil is NOT

To keep scope honest:

- **Anvil is not a document generator.** It orchestrates *iterative authoring* — drafter, reviewer, reviser, auditor. The drafter is an LLM agent following a skill's command spec; Anvil doesn't generate the content itself.
- **Anvil is not a renderer.** It shells out to `marp`, `pandoc`, `xelatex`, `mmdc`, `pdftoppm`. The renderer choices are pinned (e.g. Marp for slides, MathJax not KaTeX) but the rendering itself happens in subprocess.
- **Anvil is not a forge.** No GitHub-style PR workflow for the artifacts. The version history is the audit trail; collaboration happens via shared filesystem + (optionally) git.
- **Anvil is not opinionated about voice.** Each skill ships defaults; consumers override via `.anvil/skills/<name>/voice.md` and other extension points.
- **Anvil is not yet** broadly distributed. The framework hardens through real use, not speculative design — v0.9.0 is driven by several live canary consumers (2AM Logic Studio; botho, which drove `primer` and `spec`; geode-fem and the Tractatus Lean-4 project on `paper`) rather than one.

---

## Release Cadence

We don't ship on a fixed cadence. Releases are cut when a coherent batch of canary-surfaced friction has been addressed and the codebase is at a clean point. See `scripts/version.sh` for the version-file list and the release skill (`/loom:release` if installed locally) for the cut process.

See [CHANGELOG.md](CHANGELOG.md) for the version history.
