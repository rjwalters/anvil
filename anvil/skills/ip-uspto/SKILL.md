---
name: ip-uspto
description: Draft, review, and revise USPTO non-provisional utility patent applications (specification, claims, abstract, drawings, formal sections per 37 CFR) through the canonical anvil lifecycle extended with USPTO-specific phases.
domain: ip
type: skill
user-invocable: false
---

# anvil:ip-uspto — USPTO non-provisional utility patent applications

The `ip-uspto` skill produces non-provisional utility patent applications targeting filing at the United States Patent and Trademark Office. It extends the canonical anvil lifecycle (`draft → review → revise → figures → audit`) with four USPTO-specific phases (`intake`, `inventorship`, `pre-flight`, `finalize`) and is the proving ground for the **N parallel critics, one reviser** framework primitive.

This skill targets **AIA non-provisional utility** applications (first-inventor-to-file framing, post–16 March 2013). Provisional applications and design patents are out of scope for v0.

## Artifact contract

A **patent thread** is a single patent application authored across one or more revisions. A thread is identified by a slug (e.g., `acme-widget`, `foo-method`). Each thread occupies a portfolio directory that contains:

```
<portfolio>/
  <thread>/                       Optional thread root with brief and reference material
    BRIEF.md                      Structured inventor brief (intake output, or hand-authored)
    refs/                         Optional reference material (transcripts, sketches, lab notebooks)
    prior-art/                    Operator-supplied prior art (PDFs or markdown summaries)
    inventorship.md               Inventorship matrix (inventorship phase output)
    .anvil.json                   Optional per-thread overrides (max_iterations, critic set)
  <thread>.1/                     First drafted version (immutable once written)
    spec.tex                      Specification (LaTeX, using anvil-uspto.cls)
    claims.tex                    Claims block (independent + dependent)
    abstract.txt                  Abstract (≤150 words, plain text)
    drawings/                     Figure stubs or rendered drawings
      fig-1.tex                   (TikZ flowcharts) or fig-1.svg / fig-1.pdf
      drawing-descriptions.md     Stub descriptions for human illustrator (default v0)
    _outline.json                 Section-by-section drafting plan (control surface; see "Outline control surface")
    _progress.json                Phase state for this version
    _revision-log.md              (revisions only) Maps prior critic findings to changes
  <thread>.1.review/              General reviewer sibling (clarity, structure, voice)
  <thread>.1.s101/                §101 statutory subject matter critic
  <thread>.1.s112/                §112 enablement / written description / definiteness critic
  <thread>.1.claims/              Claim breadth + dependency-tree critic
  <thread>.1.priorart/            Novelty / §102 / §103 positioning critic
  <thread>.1.audit/               Final fact-check (audit phase only; post-convergence)
  <thread>.1.preflight/           Pre-flight mechanical compliance scan (post-revise, pre-review)
  <thread>.2/                     Revised version (after revise consumes ALL critic siblings)
  <thread>.2.review/
  ...
  <thread>.{N}/                   Terminal version, marked READY then AUDITED then FINALIZED
  <thread>.final/                 Finalize phase output (assembled submission package)
    spec.pdf
    drawings.pdf
    ads-placeholder.txt
    fee-sheet-placeholder.txt
    inventorship-attestation.md
    _manifest.json
```

Versioned dirs (`<thread>.{N}/`) and critic sibling dirs (`<thread>.{N}.<tag>/`) are **immutable once their `_progress.json` records the phase as `done`**. Revisions are produced as a new version dir, never by editing in place.

## State machine

USPTO extends the standard lifecycle with four phases. Per-thread state, derived from on-disk evidence (not flags):

```
EMPTY → INTAKE_DONE → INVENTORSHIP_DONE → DRAFTED → REVIEWED → REVISED → … → READY → AUDITED → FINALIZED
                                                       ↑
                                              PRE_FLIGHT_PASSED gates the loop edge
```

| State | Evidence |
|---|---|
| `EMPTY` | No `<thread>.{N}/` directories exist; brief may or may not exist |
| `INTAKE_DONE` | `<thread>/BRIEF.md` exists and is structured (has the intake frontmatter keys) |
| `INVENTORSHIP_DONE` | `<thread>/inventorship.md` exists with at least one named inventor and a per-independent-claim attribution table |
| `DRAFTED` | Latest `<thread>.{N}/` exists with `spec.tex`, `claims.tex`, `abstract.txt`, and `_progress.json.draft == done`; no sibling critic at the same `N` |
| `REVIEWED` | All configured critic siblings (`<thread>.{N}.<tag>/`) at the latest `N` are `done` |
| `PRE_FLIGHT_PASSED` | `<thread>.{N}.preflight/_summary.md` records `passed: true` (or all blockers were waived) |
| `REVISED` | A `<thread>.{N+1}/` exists after prior critic siblings + pre-flight at `<thread>.{N}` |
| `READY` | Aggregate score from critic siblings ≥35/40 AND no critical flag at latest `N` |
| `AUDITED` | `<thread>.{N}.audit/_summary.md` records `passed: true` alongside a `READY` version |
| `FINALIZED` | `<thread>.final/_manifest.json` exists with all required submission artifacts referenced |

Thresholds: **≥35/40 advances** (legal/customer-facing artifact per anvil's threshold table). Any §101 critical flag OR §112 critical flag short-circuits regardless of total score — block until addressed. Other critic critical flags follow the same short-circuit rule.

Iteration cap: default `max_iterations: 5`. Configurable per-thread by writing `{ "max_iterations": <N> }` to `<thread>/.anvil.json`. Exceeding the cap marks the thread `BLOCKED` and requires human review.

## Command dispatch

| Command | Role | Reads | Writes |
|---|---|---|---|
| `ip-uspto` | portfolio orchestrator | all `<thread>.*` dirs under cwd | (none; reports state per thread + recommends next command) |
| `ip-uspto-intake <thread>` | intake | inventor disclosure (transcript, brain dump, notes) in `<thread>/refs/` | `<thread>/BRIEF.md` (structured) |
| `ip-uspto-inventorship <thread>` | inventorship interviewer | `<thread>/BRIEF.md`, latest `<thread>.{N}/claims.tex` if present | `<thread>/inventorship.md` (matrix) |
| `ip-uspto-pre-flight <thread>` | pre-flight checker | latest `<thread>.{N}/` (all files) | `<thread>.{N}.preflight/` with `_summary.md`, `findings.md`, `_meta.json` |
| `ip-uspto-draft <thread>` | drafter | `<thread>/BRIEF.md`, `<thread>/inventorship.md`, `<thread>/refs/`, `<thread>/prior-art/`; for revisions also prior version + all critic siblings | `<thread>.{N}/` with spec/claims/abstract/drawings |
| `ip-uspto-review <thread>` | general reviewer | latest `<thread>.{N}/` | `<thread>.{N}.review/` |
| `ip-uspto-101 <thread>` | §101 critic | latest `<thread>.{N}/` | `<thread>.{N}.s101/` |
| `ip-uspto-112 <thread>` | §112 critic | latest `<thread>.{N}/` | `<thread>.{N}.s112/` |
| `ip-uspto-claims <thread>` | claims critic | latest `<thread>.{N}/claims.tex` + `<thread>.{N}/spec.tex` | `<thread>.{N}.claims/` |
| `ip-uspto-prior-art <thread>` | prior-art critic | latest `<thread>.{N}/` + `<thread>/prior-art/**` | `<thread>.{N}.priorart/` |
| `ip-uspto-vision <thread>` | drawing vision critic (optional) | rendered drawings under latest `<thread>.{N}/drawings/` (SVG/PNG; **drawings only — never the spec PDF**) | `<thread>.{N}.vision/` with `_review.json` (kind=vision) |
| `ip-uspto-revise <thread>` | reviser | latest `<thread>.{N}/` + ALL `<thread>.{N}.<tag>/` critic siblings | `<thread>.{N+1}/` with `_revision-log.md` |
| `ip-uspto-audit <thread>` | auditor | READY `<thread>.{N}/` | `<thread>.{N}.audit/` |
| `ip-uspto-figures <thread>` | figurer | latest `<thread>.{N}/spec.tex` + reference numerals | `<thread>.{N}/drawings/**` |
| `ip-uspto-finalize <thread>` | finalizer | AUDITED `<thread>.{N}/` + `<thread>/inventorship.md` | `<thread>.final/` with submission package |

The portfolio orchestrator is the user-facing entry point for status; the lifecycle commands are dispatched from it (or invoked directly by the orchestrating agent).

## Multi-critic primitive — sibling directory convention

Given an artifact at `<thread>.{N}/`, critic outputs land in sibling directories with the same parent and name prefix:

```
<thread>.{N}/                   ← the artifact (immutable once review starts)
<thread>.{N}.review/            ← general reviewer
<thread>.{N}.s101/              ← §101 critic
<thread>.{N}.s112/              ← §112 critic
<thread>.{N}.claims/            ← claims critic
<thread>.{N}.priorart/          ← prior-art critic
<thread>.{N}.vision/            ← drawing vision critic (optional; kind=vision, scores rendered drawings only)
<thread>.{N}.preflight/         ← pre-flight (mechanical compliance) — produced after revise, pre-review
<thread>.{N}.audit/             ← final fact-check (audit phase, post-convergence only)
<thread>.{N+1}/                 ← reviser output (consumes ALL siblings above)
```

**Naming rule**: `<thread>.{N}.<tag>/`. The `<tag>` is a single short token; no nesting, no dots within the tag. Discovery is "glob `<thread>.{N}.*/` minus the bare `<thread>.{N}/`".

### Uniform critic output schema

Every critic directory contains:

```
<thread>.{N}.<tag>/
  _summary.md         Scorecard (8-dim /40 partial — critic only fills dimensions it owns) + critical flag boolean
  findings.md         Itemized findings, each with: severity, location (file:section), rationale, suggested fix
  _meta.json          { critic: <tag>, role: <which role md>, started: <iso>, finished: <iso>, model: <hint>, schema_version: 1, scorecard_kind: "machine-summary" }
```

Uniform schema enables `ip-uspto-revise` to enumerate findings programmatically without per-critic special-casing. Critics that don't fill a rubric dimension leave it `null` rather than zero — the reviser aggregates non-null scores by mean.

**Schema note**: this schema (`_summary.md` / `findings.md` / `_meta.json`) is the canonical `machine-summary` scorecard kind documented in `anvil/lib/snippets/scorecard_kind.md`. The memo, pub, slides, and report skills use the `human-verdict` kind (`verdict.md` / `scoring.md` / `comments.md`); the deck skill is the layered/aggregator reference (both kinds present). The two-kind discriminator (set in `_meta.json` as `scorecard_kind`) is how consumers distinguish the shapes without hardcoding skill-specific knowledge — see `anvil/lib/snippets/scorecard_kind.md` and `anvil/lib/snippets/critics.md` for the aggregation rules.

### Reviser composition

`ip-uspto-revise` discovers critic siblings, aggregates their scorecards, and either advances or produces the next version. See `commands/ip-uspto-revise.md` for the full algorithm.

**Key design property**: critics are independent and parallelizable. The reviser is the synchronization point. Adding a new critic = adding a new `ip-uspto-<critic>.md` command + a new sibling tag. No reviser code changes.

### Convergence loop

Lifecycle for one revision pass:

```
DRAFTED → (run all critics) → REVIEWED → (revise consumes ALL siblings) → REVISED → (pre-flight) → loop until convergence → READY → AUDITED → FINALIZED
```

The default critic set is `review + s101 + s112 + claims + priorart`. Operator can subset by writing `{ "critics": ["review", "s101", "s112", "claims"] }` to `<thread>/.anvil.json` (e.g., skip `priorart` if no prior art was supplied; the reviser refuses to advance without all configured critics present).

**Critic concurrency in v0**: critics may be run serially or in parallel. The orchestrator (`ip-uspto.md`) reports "all configured critics done at version N" as a boolean — it does not enforce concurrency. Parallel spawn is a future enhancement that will land in `anvil/lib/critics.py` (issue #10); v0 implementations should default to serial for debuggability.

## Progress tracking

Each `<thread>.{N}/` directory contains `_progress.json` recording phase state. Schema:

```json
{
  "version": 1,
  "thread": "<thread>",
  "phases": {
    "draft":    { "state": "done",        "started": "2026-05-28T14:00:00Z", "completed": "2026-05-28T14:30:00Z" },
    "figures":  { "state": "in_progress", "started": "2026-05-28T14:35:00Z" }
  },
  "metadata": {
    "iteration": 1,
    "max_iterations": 5
  }
}
```

Phase states: `pending`, `in_progress`, `done`, `failed`. Validation is **by file existence** (does `spec.tex` exist? does `_summary.md` parse?), not by flag — `_progress.json` is a resume hint, not the source of truth. A phase that crashed mid-write should be re-runnable from `pending` after deleting any partial output.

The canonical `_progress.json` schema, read-merge-write recipe, and crash recovery contract live in `anvil/lib/snippets/progress.md` (in an installed consumer repo: `.anvil/lib/snippets/progress.md`); every command in this skill follows that convention. The merge is shallow: command updates one phase, preserves all others. All ip-uspto critic siblings (`<thread>.{N}.review/`, `.s101/`, `.s112/`, `.claims/`, `.priorart/`, `.audit/`, `.preflight/`) follow the `machine-summary` scorecard kind per `anvil/lib/snippets/scorecard_kind.md`: each emits `_summary.md` + `findings.md` + `_meta.json` (with `scorecard_kind: machine-summary`); each fills only its owned rubric dimensions and leaves others `null` for the reviser's mean aggregation.

## Outline control surface

Each `<thread>.{N}/` directory contains `_outline.json` — a typed control surface that records the section-by-section drafting plan for this version. The outline is **load-bearing**: it is the diff-able interface where an operator can inspect and edit the structure of the application before the drafter pays for full section generation, and it is the per-section resume index during drafting and revising.

The outline is **additive** to the existing draft outputs (`spec.tex`, `claims.tex`, `abstract.txt`, `drawings/drawing-descriptions.md`) — it does not replace them. Each outline section carries the file routing and heading macro the drafter uses to deterministically place its rendered output without re-deriving from the section id.

### Schema

```json
{
  "schema_version": 1,
  "thread": "<slug>",
  "title": "...",
  "iteration": 1,
  "sections": [
    {
      "id": "field",
      "file": "spec.tex",
      "heading_macro": "\\fieldoftheinvention",
      "target_tokens": 120,
      "key_points": ["..."],
      "sources_to_cite": [],
      "status": "pending"
    },
    {
      "id": "background",
      "file": "spec.tex",
      "heading_macro": "\\background",
      "target_tokens": 1200,
      "subsections": [
        {"id": "problem", "key_points": ["..."]},
        {"id": "prior-approaches", "key_points": ["..."]}
      ],
      "sources_to_cite": ["doi:...", "arxiv:..."],
      "status": "pending"
    },
    {
      "id": "summary",
      "file": "spec.tex",
      "heading_macro": "\\summary",
      "target_tokens": 800,
      "key_points": ["mirror independent claim 1 at higher level", "..."],
      "status": "pending"
    },
    {
      "id": "brief-description-of-drawings",
      "file": "spec.tex",
      "heading_macro": "\\briefdescriptionofdrawings",
      "target_tokens": 200,
      "figures": [
        {"n": 1, "caption": "..."},
        {"n": 2, "caption": "..."}
      ],
      "status": "pending"
    },
    {
      "id": "detailed-description",
      "file": "spec.tex",
      "heading_macro": "\\detaileddescription",
      "target_tokens": 6000,
      "subsections": [
        {
          "id": "feature-1",
          "feature_ref": "BRIEF.md#3.1",
          "key_points": ["..."],
          "ranges": [{"param": "freq", "range": "5GHz-80GHz", "preferred": "40GHz"}],
          "alternatives": [{"param": "substrate", "values": ["Si", "GaAs", "InP"]}],
          "refnums": [10, 12, 14, 16],
          "target_tokens": 1800
        }
      ],
      "status": "pending"
    },
    {
      "id": "claims",
      "file": "claims.tex",
      "target_tokens": 3000,
      "claim_tree": [
        {"n": 1, "type": "independent", "topic": "apparatus", "key_limitations": ["..."]},
        {"n": 2, "type": "dependent", "parent": 1, "topic": "...", "drawn_from": "feature-1#alt:Si"},
        {"n": 9, "type": "independent", "topic": "method", "key_limitations": ["..."]}
      ],
      "status": "pending"
    },
    {
      "id": "abstract",
      "file": "abstract.txt",
      "target_tokens": 200,
      "word_cap": 150,
      "status": "pending"
    }
  ]
}
```

### Field semantics

- `schema_version`: integer, currently `1`. Migrations bump this.
- `thread`: the thread slug; matches `_progress.json.thread`.
- `title`: human title (from `BRIEF.md` frontmatter).
- `iteration`: integer matching `_progress.json.metadata.iteration`. Bumped when the reviser copies the outline forward.
- `sections`: ordered array; the drafter MUST iterate in array order. The order is the authoritative render order. The minimum required section ids are `field`, `background`, `summary`, `brief-description-of-drawings`, `detailed-description`, `claims`, `abstract`.
- For each section:
  - `id`: unique within the array. Maps onto the §5a–§5i drafter steps.
  - `file`: target file (`spec.tex` | `claims.tex` | `abstract.txt`). Lets the drafter route rendered output deterministically without per-id special-casing.
  - `heading_macro`: LaTeX macro that opens the section in `spec.tex` (omitted for `claims.tex` / `abstract.txt`, which use their own structure).
  - `target_tokens`: drafter budget hint. Soft cap; the drafter MAY exceed if the inventive material justifies, but should report the overrun in its closing summary.
  - `key_points` / `subsections` / `figures` / `claim_tree`: section-specific structured content the drafter conditions on. Free-form within their typed shape.
  - `sources_to_cite`: optional citation identifiers (DOI, arXiv, USPTO publication number). Slot for future citation primitive.
  - `status`: lifecycle state, see below.

### Status lifecycle

Per-section `status` values mirror `_progress.json` phase states:

| State | Meaning |
|---|---|
| `pending` | Section has not been rendered yet for this version. |
| `in_progress` | Section render started but did not complete (crash, abort). |
| `done` | Section has been rendered; its bytes in `file` are valid. |
| `failed` | Section render attempted and failed (error captured in `_progress.json.phases.draft.errors`). |

The drafter advances a section from `pending` → `in_progress` → `done` (or `failed`) one section at a time, persisting `_outline.json` after each transition so a crash leaves a recoverable state.

### Validation rule

Consistent with the rest of the skill: **file existence and section presence in the target file win over the flag**. A section flagged `done` whose bytes are absent from `file` is treated as not-done (re-rendered on resume). A section flagged `pending` whose bytes ARE present in `file` (because, say, the operator hand-wrote it) is treated as `done` (skipped). The flag is a resume hint; the file is the source of truth — same rule as `_progress.json`.

The draft phase is `done` only when every section has `status: done` AND its bytes validate by the file-existence check.

### Schema location

The schema is documented inline here for v0. There is no separate `schemas/` directory; promotion to a versioned JSON Schema file is deferred to `anvil/lib/` extraction under issue #10.

## Rubric

See `rubric.md` for the 8-dimension /40 USPTO scoring schema, the ≥35 advance threshold, and the §101/§112 critical-flag short-circuit policy. The optional `ip-uspto-vision` critic owns a **separate drawing-vision rubric subset** (dv1–dv5, /25) documented in the same file — it critiques the rendered drawings only (legibility, line weight/contrast, label placement, figure-number visibility, cross-reference accuracy) and ships its scorecard directly as `_review.json` (canonical `kind=vision` schema) rather than the `_summary.md`/`findings.md` machine-summary shape the source-side critics use; both are discovered and aggregated uniformly by `anvil/lib/critics.py`.

## USPTO-specific phases

Beyond the standard `draft → review → revise → figures → audit` lifecycle, this skill adds four USPTO phases:

| Phase | Command | When | Purpose |
|---|---|---|---|
| **Intake** | `ip-uspto-intake` | Before first draft | Convert raw inventor disclosure into a structured brief: problem, prior approaches, key inventive features, embodiments, ranges, edge cases. Without this, the drafter hallucinates. |
| **Inventorship** | `ip-uspto-inventorship` | Before first draft; re-checked pre-finalize | Generate inventor interview prompts to attribute each independent claim concept to ≥1 named inventor. 37 CFR 1.63 inventor oath requires correct inventorship; mis-attributed inventorship is grounds for unenforceability. |
| **Pre-flight** | `ip-uspto-pre-flight` | After each revise, before next review | Mechanical compliance scan: paragraph numbering (`[0001]`, `[0002]`, ...), abstract word count ≤150, claims numbered 1..N, no multiple-dependent-on-multiple-dependent claims (37 CFR 1.75(c)), margin/font checks via LaTeX class. Deterministic-first with LLM fallback for ambiguous cases. |
| **Finalize** | `ip-uspto-finalize` | After AUDITED | Assemble submission package: `spec.pdf`, `drawings.pdf`, ADS placeholder, fee schedule placeholder, inventorship attestation. Does **not** file — that is a human + Patent Center action. |

## Defaults and overrides

This skill ships with opinionated defaults. Consumers extend liberally via `.anvil/skills/ip-uspto/` in their own repo:

- `voice.md` (optional) — Firm or attorney voice/style guidance the drafter reads in addition to its base prompt.
- `rubric.overrides.md` (optional) — Add domain-specific critical-flag examples; cannot reduce the base rubric.
- `BRIEF.md.example` — Reference brief shape; the intake command produces this shape from a disclosure.
- `critics/` (optional) — Add custom critic command files (e.g., `ip-uspto-mydomain.md`). The orchestrator picks them up automatically by glob.

## Important caveats

- **This skill does NOT file a patent application.** It produces a submission-ready package. Filing requires human review, attorney sign-off, and submission via USPTO Patent Center.
- **This skill does NOT replace a licensed patent attorney.** It is a drafting and review aid. Inventorship attestation (37 CFR 1.63), assignment, and prosecution strategy require a qualified human attorney.
- **The prior-art critic does NOT do its own patent search.** Operator must supply prior art in `<thread>/prior-art/`. Patent search is a separate role potentially shipped as a future skill.
- **Provisional applications and design patents are out of scope for v0.** Track as separate issues.
