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

Every critic sibling under `<thread>.{N}.<tag>/` follows the uniform schema (matches issues #4, #5):

```
<thread>.{N}.<tag>/
  _summary.md         8-dim partial scorecard (critic fills only owned dimensions; others = null) + critical flag
  findings.md         Itemized findings: severity (blocker/major/minor/nit), slide ref, rationale, suggested fix
  _meta.json          { "critic": "<tag>", "role": "deck-<tag>.md", "started": <ISO>, "finished": <ISO>, "model": "<id>" }
```

Critics fill only the rubric dimensions they own; other dimensions remain `null`. The reviser aggregates per-dimension as the **mean of non-null critic scores**. The critical flag in the aggregated scorecard is the **logical OR** of all critic critical flags.

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
| `deck-review <thread>` | general reviewer | latest `<thread>.{N}/` | `<thread>.{N}.review/` (uniform critic schema) |
| `deck-narrative <thread>` | narrative critic | latest `<thread>.{N}/deck.md` (full read, in order) | `<thread>.{N}.narrative/` (owns dims 1, 7) |
| `deck-market <thread>` | market critic | latest `<thread>.{N}/deck.md` + market exhibits + any `figures/src/*.csv` | `<thread>.{N}.market/` (owns dims 3, 4) |
| `deck-design <thread>` | design critic | latest `<thread>.{N}/deck.pdf` (renders if missing) → per-slide PNGs | `<thread>.{N}.design/` (owns dim 8) |
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
- Render: `<thread>.{N}/deck.pdf` (via `marp deck.md --pdf --theme-set <theme>`).
- Optional handoff export: `<thread>.{N}/deck.pptx` (via `marp deck.md --pptx`), opt-in.
- Theme: `anvil/skills/deck/assets/anvil-deck.css` — clean, neutral, fundraising-appropriate (large headings, generous whitespace, restrained palette). Consumers override via `.anvil/skills/deck/templates/<their-theme>.css`.

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

Until `anvil/lib/progress.py` lands (see issue #10), each command reads and writes `_progress.json` directly with a minimal JSON read-merge-write snippet. The merge is shallow: the command updates one phase, preserves all others.

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
