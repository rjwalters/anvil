---
name: deck
description: Draft, review, and revise pitch decks (fundraising and business pitches) using the standard anvil lifecycle plus deck-specific brief intake and three parallel critics (narrative, market, design).
domain: deck
type: skill
user-invocable: false
---

# anvil:deck — Pitch decks

The `deck` skill produces **pitch decks**: fundraising narratives (pre-seed, seed, Series A/B, growth), partnership pitches, and board updates that close with an explicit ask. It is intentionally distinct from `anvil:slides` (talk-format conference slides, issue #7): per resolved issue #2 the two are separate skills sharing `anvil/lib/`. A pitch deck is fundamentally a persuasive document with a request at the end; the rubric and command set are tuned accordingly.

## Artifact contract

A **deck thread** is a single pitch artifact (typically: one round, one ask) authored across one or more revisions. A thread is identified by a slug (e.g., `acme-seed`, `q3-board-update`). Each thread occupies a portfolio directory that contains:

```
<portfolio>/
  <thread>/                  Thread root with brief and consumer-provided assets
    BRIEF.md                 Structured brief (intake output; freeform prose with optional frontmatter)
    refs/                    Reference material (decks, transcripts, exported financials, websites)
    assets/                  Consumer-provided imagery (logos, screenshots, team photos)
  <thread>.0/                Brief-intake output (immutable once written)
    BRIEF.md                 Generated brief (if deck-brief was used to produce it)
    _progress.json
  <thread>.1/                First drafted version
    deck.md                  Marp markdown slide source (slide breaks via `---`)
    speaker-notes.md         Per-slide presenter notes (parallel structure to deck.md)
    figures/                 Mermaid sources + matplotlib scripts + rendered PNGs/SVGs
      src/                   Source files (.mmd, .py, .csv) regenerable by deck-figures
    deck.pdf                 Rendered PDF (produced by deck-figures or at READY)
    _progress.json
  <thread>.1.review/         General reviewer output (read-only)
    verdict.md               Top-level decision + total /40 + critical flags
    scoring.md               Per-dimension scores (this critic fills owned dimensions only)
    comments.md              Slide-level comments keyed to deck.md
    _summary.md              8-dim partial scorecard (other critics' dims = null) + critical flag
    findings.md              Itemized findings: severity, slide ref, rationale, suggested fix
    _meta.json               { critic, role, started, finished, model }
  <thread>.1.narrative/      Narrative-arc critic (owns dims 1, 7)
  <thread>.1.market/         Market/TAM credibility critic (owns dims 3, 4)
  <thread>.1.design/         Visual/design critic (owns dim 8)
    slides/                  Per-slide PNGs rendered from deck.pdf (this critic only)
  <thread>.2/                Revised version (aggregates ALL critic siblings at .1)
    _revision-log.md         Maps each critic finding to a change made (or "declined" with reason)
  ...
  <thread>.{N}/              Terminal version, marked READY in its _progress.json
  <thread>.{N}.audit/        Optional fact/number/citation auditor (run at or near READY)
```

Versioned dirs and critic siblings are **immutable once their `_progress.json` records the relevant phase as `done`**. Revisions are produced as a new version dir, never by editing in place.

### Sibling-critic convention

Deck is the **reference implementation** for the layered scorecard pattern documented in `anvil/lib/snippets/scorecard_kind.md`:

- **Specialist critics** (`deck-narrative`, `deck-market`, `deck-design`) emit the `machine-summary` shape: `_summary.md` + `findings.md` + `_meta.json` (with `scorecard_kind: machine-summary`). Each critic fills only the rubric dimensions it owns; other dimensions remain `null`.
- **Aggregator critic** (`deck-review`) emits BOTH shapes layered: the `human-verdict` shape (`verdict.md` + `scoring.md` + `comments.md`) AND the `machine-summary` shape (`_summary.md` + `findings.md`). The primary scorecard kind is `human-verdict` (the aggregated narrative `verdict.md` is the deliverable); the machine-summary layer lets downstream cross-skill machinery aggregate alongside other machine-summary critics if needed.

Every critic sibling under `<thread>.{N}.<tag>/` therefore declares its primary kind in `_meta.json` per `anvil/lib/snippets/scorecard_kind.md`. The specialist schema:

```
<thread>.{N}.<tag>/                                    # for deck-narrative, deck-market, deck-design
  _summary.md         8-dim partial scorecard (critic fills only owned dimensions; others = null) + critical flag
  findings.md         Itemized findings: severity (blocker/major/minor/nit), slide ref, rationale, suggested fix
  _meta.json          { "critic": "<tag>", "role": "deck-<tag>.md", "started": <ISO>, "finished": <ISO>, "model": "<id>", "scorecard_kind": "machine-summary" }
```

The aggregator schema (both layers present):

```
<thread>.{N}.review/                                   # the deck-review aggregator
  verdict.md          Aggregated decision + total /40 + critical flags (primary deliverable)
  scoring.md          Per-dimension scorecard with justifications
  comments.md         Slide-level comments
  _summary.md         8-dim partial scorecard (review owns dims 2, 5, 6; specialists fill others when aggregated)
  findings.md         Itemized findings owned by the general reviewer
  _meta.json          { ..., "scorecard_kind": "human-verdict" }   # primary intent
```

Specialists fill only their owned rubric dimensions; the aggregator reads the specialists' `_summary.md` files and combines per-dimension scores as the **mean of non-null critic scores**. The critical flag in the aggregated scorecard is the **logical OR** of all critic critical flags. See `anvil/lib/snippets/critics.md` for the canonical discovery and aggregation rules.

**Default critic set for deck**: `review + narrative + market + design`. An operator can subset (e.g., skip `design` while content is still in flux); the reviser handles missing siblings gracefully.

**Discovery glob** (used by the reviser): `<thread>.{N}.*/` minus the bare `<thread>.{N}/`.

## State machine

Per-thread state, derived from on-disk evidence (not flags):

```
EMPTY → BRIEF_DONE → DRAFTED → REVIEWED → REVISED → … → READY → AUDITED
```

| State | Evidence |
|---|---|
| `EMPTY` | No `<thread>.{N}/` directories exist; no `<thread>/BRIEF.md` |
| `BRIEF_DONE` | `<thread>/BRIEF.md` exists (either hand-written or produced by `deck-brief`) and no `<thread>.{N}/` with `deck.md` exists yet |
| `DRAFTED` | Latest `<thread>.{N}/deck.md` exists with `_progress.json.draft.state == done`; no sibling review at the same `N` |
| `REVIEWED` | At least `<thread>.{N}.review/verdict.md` exists for the latest `N` (other critics may also be present) |
| `REVISED` | A `<thread>.{N+1}/` exists after a prior `<thread>.{N}.review/` (and any other critic siblings) |
| `READY` | Latest `<thread>.{N}.review/verdict.md` records `advance: true` AND no unresolved critical flag from any critic sibling |
| `AUDITED` | `<thread>.{N}.audit/` exists alongside a `READY` version |

**Thresholds** (deck is a customer-facing artifact per `lib/README.md`'s legal/customer-facing rule — a pitch deck is the founder's pitch to external capital):

- **≥35/40** advances to `READY`.
- **<35/40** requires revision.
- **Any critical flag short-circuits** regardless of total. The four deck-specific critical flags are:
  1. **Fabricated traction** — a traction number (revenue, users, LOIs, pilots, design partners) not attested in the brief or refs.
  2. **Fabricated team credentials** — a bio claim (prior role, prior exit, degree, named hire) not attested in the brief or refs.
  3. **Market-math error** — TAM/SAM/SOM arithmetic that does not check out, OR top-down-only sizing presented as defensible.
  4. **Absent ask** — no specific round size, no use-of-funds breakdown, no runway-to-milestone framing.

Iteration cap: default `max_iterations: 4` (terminal version is `<thread>.5/`). Configurable per-thread via `<thread>/.anvil.json` (`{ "max_iterations": <N> }`). Exceeding the cap marks the thread `BLOCKED` (in the portfolio orchestrator's report) and requires human review.

## Command dispatch

| Command | Role | Reads | Writes |
|---|---|---|---|
| `deck` | portfolio orchestrator | all `<thread>.*` dirs under cwd | (none; reports state + recommends next command per thread) |
| `deck-brief <thread>` | intake | `<thread>/refs/**` (transcripts, websites, founder input) | `<thread>/BRIEF.md` (and/or `<thread>.0/BRIEF.md`) |
| `deck-draft <thread>` | drafter | `<thread>/BRIEF.md`, `<thread>/refs/**`, `<thread>/assets/**`; for revisions, also latest `<thread>.{N}/` + all `<thread>.{N}.*/` siblings (revise path is preferred via `deck-revise`) | `<thread>.{N+1}/deck.md` + `speaker-notes.md` + `figures/` + `_progress.json` |
| `deck-review <thread>` | general reviewer | latest `<thread>.{N}/` | `<thread>.{N}.review/` (uniform critic schema; also runs pre-flight `slide-content-overflow` lint per "Pre-flight overflow lint" below) |
| `deck-narrative <thread>` | narrative critic | latest `<thread>.{N}/deck.md` (full read, in order) | `<thread>.{N}.narrative/` (owns dims 1, 7) |
| `deck-market <thread>` | market critic | latest `<thread>.{N}/deck.md` + market exhibits + any `figures/src/*.csv` | `<thread>.{N}.market/` (owns dims 3, 4) |
| `deck-design <thread>` | design critic | latest `<thread>.{N}/deck.pdf` (renders if missing) → per-slide PNGs | `<thread>.{N}.design/` (owns dim 8, source-side density) |
| `deck-vision <thread>` | vision critic | latest `<thread>.{N}/deck.pdf` (renders if missing) → per-slide PNGs | `<thread>.{N}.vision/` (owns dim 8 rendered-side density + vision rubric v1–v6); produces canonical `_review.json` per #26 with `kind=vision`. See `commands/deck-vision.md` and `anvil/lib/vision.py`. |
| `deck-revise <thread>` | reviser | latest `<thread>.{N}/` + ALL `<thread>.{N}.*/` critic siblings | `<thread>.{N+1}/` with `_revision-log.md` |
| `deck-audit <thread>` | auditor | latest `<thread>.{N}/`, `<thread>/BRIEF.md`, `<thread>/refs/**` | `<thread>.{N}.audit/` |
| `deck-figures <thread>` | figurer | latest `<thread>.{N}/deck.md` + `figures/src/` | `<thread>.{N}/figures/` + `<thread>.{N}/deck.pdf` (PDF render) |

The portfolio orchestrator is the user-facing entry point for status; the lifecycle commands are dispatched from it (or invoked directly by the orchestrating agent).

## Skill-specific phases

**Brief intake** (`deck-brief`) — Recommended one-shot pre-draft phase. Pitch decks fail catastrophically when the drafter hallucinates traction or invents market numbers. The intake converts a founder's raw input (often a transcript, a website, a memo, a back-of-napkin) into a structured brief covering: stage, round target, problem statement, current product status, real traction numbers (revenue / users / LOIs / pilots / design partners), named team with verified bios, target investor profile, named competitors, prior raises with terms. **The drafter is forbidden from inventing numbers not in the brief.**

**Three parallel critics** (`deck-narrative`, `deck-market`, `deck-design`) — These run alongside the general `deck-review`. Each fills only the rubric dimensions it owns; others remain null. The reviser aggregates per-dimension as the mean of non-null critic scores.

- `deck-narrative` evaluates the deck as a single story (problem → solution → why now → why us → ask), not slide-by-slide. Owns dims 1 (Narrative arc), 7 (Ask specificity). Flags missing logical bridges, slides out of order, ask that doesn't follow from setup, "why now" missing or unconvincing, slide count off (target 10–15).
- `deck-market` evaluates TAM/SAM/SOM math, comparable transactions, competitor positioning. Owns dims 3 (Market size credibility), 4 (Solution differentiation). Verifies arithmetic; checks bottom-up vs top-down framing; flags top-down-only sizing as a near-automatic disqualifier.
- `deck-design` evaluates visual/typographic quality: slide density (≤6 bullets, ≤30 words per content slide), chart legibility, consistent palette/typography, image quality. Owns dim 8 (Design polish). **Renders the deck to per-slide PNGs first** and critiques against rendered output, not source — a markdown-source-only design critic can't see actual visual hierarchy.

**Audit** (`deck-audit`) — Sharper than the generic auditor: (a) every cited statistic resolves to a source in the brief or refs, (b) every claimed customer/partner/investor logo is attested, (c) every traction number matches the brief, (d) team bios match the brief. Critical-flag eligible (any unattested claim triggers a fabrication flag).

**Figures** (`deck-figures`) — See "Asset generation" below.

### Pre-flight overflow lint

`deck-review` runs a fast deterministic lint over `<thread>.{N}/deck.md` before scoring. The lint is a Python-stdlib port of marp-vscode's experimental `slide-content-overflow` diagnostic (see `anvil/skills/deck/lib/marp_lint.py` for the upstream SHA pin and per-rule notes). It models each slide's vertical capacity from the markdown source and emits a `slide-content-overflow` finding when the estimated content exceeds the safe area.

**What it catches** (deterministic source-only heuristics):
- The "figure + 4 bullets + footer line" idiom on 16:9 (issue #24).
- The `_class: ask` H1 + H2 + bullets anti-pattern (issue #25).
- Dense bullet lists, deep code blocks, large tables, headings stacked on a single slide.

**What it does NOT catch**:
- True rendered overflow caused by font fallback, image aspect ratio, or theme overrides — these are caught by the vision critic (issue #30).
- Semantic overflow (slide is logically too crowded but fits within the safe area). The design critic handles this.
- Off-by-one cases where a single word wraps unexpectedly at render time.

**How it gates `deck-review`**:
- `severity: error` findings hard-fail the review: `advance: false`, `Slide overflow (lint)` listed as a critical flag in `verdict.md`, and the per-slide errors emitted into `findings.md` § Lint findings.
- `severity: warning` findings are recorded in `findings.md` § Lint findings but do not block advance.
- The lint runs ONLY in `deck-review`. The drafter, auditor, figurer, and the specialist critics (`deck-narrative`, `deck-market`, `deck-design`) do not invoke it — the drafter is allowed to produce an overflowing slide so the reviser sees the failure mode.

**Escape hatch — `<!-- anvil-lint-disable: slide-content-overflow -->`**: any slide that contains this HTML comment has its `slide-content-overflow` finding downgraded to `severity: info`. The finding is still recorded (the reviser sees that the slide is dense), but `advance` is not blocked. Use this for legitimately-dense slides that have been visually validated (e.g., a deliberately busy reference grid, or a comparison table that needs all rows). Document the rationale in `speaker-notes.md` so the auditor can spot-check.

## Asset generation — hybrid policy

Pitch decks are asset-dense. Anvil ships **deterministic asset paths only**; generative imagery is consumer-extension territory.

- **Diagrams & flowcharts** — Shipped via Mermaid → SVG → PNG. Mermaid is plaintext, lives in `figures/src/*.mmd`, regenerates deterministically, and covers architecture diagrams, sequence diagrams, and flowcharts. Renders cleanly at slide scale.
- **Data charts** — Shipped via Matplotlib (Python). Source script in `figures/src/*.py`, source data in `figures/src/*.csv`, rendered PNG in `figures/`. Auditor can re-run scripts to verify chart matches data.
- **Logos, product screenshots, team photos, lifestyle imagery** — Consumer-provided. Drop into `<thread>/assets/`; brief lists what is available; drafter references by relative path. **The drafter is forbidden from inventing logos or generating product screenshots.**
- **Generative imagery (DALL-E, Midjourney, Stable Diffusion, etc.)** — Not shipped in v0. Generative imagery in a pitch deck is a credibility liability; investors notice. Leave as a consumer extension via `.anvil/skills/deck/commands/deck-imagegen.md` override.

This matches the README's "opinionated defaults, override liberally" principle: ship deterministic asset paths; leave generative imagery to consumer extensions.

## Output format

**Source format: Marp markdown.** Per the framework-level pin in `CLAUDE.md` (Conventions), anvil-shipped presentation skills use **Markdown + Marp** as the canonical renderer. Beamer LaTeX is available only as a consumer-side override for hard-constraint cases (e.g., conference proceedings requiring LaTeX submission).

Tradeoff rationale (Marp vs alternatives):

| Format | Verdict |
|---|---|
| **PowerPoint (.pptx)** | Binary; no clean diff; programmatic generation is brittle; speaker notes awkward. Rejected as source. Acceptable as export target via Marp's `--pptx`. |
| **Beamer (LaTeX)** | Heavyweight for slide-density work; visual templating painful; LaTeX-fluent reviser required. Consumer override only. |
| **HTML slides (reveal.js / Slidev)** | Web-native, rich interactivity, clean source — but PDF export quality varies, and "real" decks are usually shared as PDF. |
| **Markdown + Marp** | Plaintext source (perfect for the draft → review → revise loop); slides as `---`-separated sections; speaker notes via `<!-- _backgroundColor: ... -->` and `<!-- speaker: ... -->` comments (also captured separately in `speaker-notes.md`); clean PDF + PPTX export; templated via CSS. **Primary.** |

**Default deliverables**:
- Source: `<thread>.{N}/deck.md` (Marp markdown).
- Speaker notes: `<thread>.{N}/speaker-notes.md` (parallel structure, one section per slide).
- Render: `<thread>.{N}/deck.pdf` (via `marp deck.md --pdf --html --config-file anvil/lib/marp/config.yml --theme-set <theme>`).
- Optional handoff export: `<thread>.{N}/deck.pptx` (via `marp deck.md --pptx --html --config-file anvil/lib/marp/config.yml`), opt-in.
- Theme: `anvil/skills/deck/assets/anvil-deck.css` — clean, neutral, fundraising-appropriate (large headings, generous whitespace, restrained palette). Consumers override via `.anvil/skills/deck/templates/<their-theme>.css`.

### Math and inline HTML

The deck template pins `math: mathjax` and `html: true` in the per-document
frontmatter (`templates/deck.md.j2`); the equivalent CLI-side pin lives at
`anvil/lib/marp/config.yml` and is consumed via Marp's native
`--config-file` flag. Belt-and-suspenders by design: a `deck.md` checked
into a consumer repo renders correctly under plain `marp deck.md --pdf`
even when the config file is missing, and the CLI config handles the
theme search path + `allowLocalFiles` regardless of frontmatter.

Math syntax is standard MathJax (Marp v3 default — covers a wider LaTeX
subset than KaTeX): `$\sigma$` inline, `$$ ... $$` display.

The `html: true` pin is load-bearing for inline mermaid: Marp renders
fenced ```mermaid blocks by emitting an inline `<script>` block, which
only survives into the rendered HTML/PDF when html is enabled. See
`anvil/skills/deck/assets/marp-renderer.md` for the full figure-pipeline
worked example (matplotlib + mermaid + MathJax).

## Progress tracking

Each `<thread>.{N}/` (and each critic sibling) contains `_progress.json` recording phase state. Schema:

```json
{
  "version": 1,
  "thread": "<thread>",
  "phases": {
    "draft":   { "state": "done", "started": "<ISO>", "completed": "<ISO>" },
    "figures": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  },
  "metadata": {
    "iteration": 1,
    "max_iterations": 4
  }
}
```

Phase states: `pending`, `in_progress`, `done`, `failed`. Validation is **by file existence** (does `deck.md` exist? does the referenced PNG exist?), not by flag — `_progress.json` is a resume hint, not a source of truth. A phase that crashed mid-write should be re-runnable from `pending` after deleting any partial output.

The canonical `_progress.json` schema, read-merge-write recipe, and crash recovery contract live in `anvil/lib/snippets/progress.md` (in an installed consumer repo: `.anvil/lib/snippets/progress.md`); every command in this skill follows that convention. The merge is shallow: the command updates one phase, preserves all others.

## Rubric

See `rubric.md` for the 8-dimension /40 scoring schema, the ≥35 advance threshold, and the four critical-flag conditions.

## Defaults and overrides

This skill ships with opinionated defaults. Consumers are expected to override liberally via `.anvil/skills/deck/` in their own repo:

- `voice.md` (optional) — Founder/firm voice/tone guidance the drafter reads in addition to its base prompt.
- `rubric.overrides.md` (optional) — Add stage-specific weight notes (e.g., "weight team higher for pre-seed") or domain-specific critical-flag examples.
- `templates/<their-theme>.css` (optional) — Marp theme override.
- `commands/deck-imagegen.md` (optional) — Generative-imagery extension (not shipped in v0).

## Per CLAUDE.md

Inline helpers are acceptable. **Do not create `anvil/lib/` modules in this skill** — that extraction is issue #10 and is blocked until ≥2 skill implementations land (memo is #1; this is #2 → unblocks #10 after this merges).
