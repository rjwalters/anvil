---
name: ip-uspto-provisional
description: Draft, review, and revise USPTO provisional patent applications (specification + drawings, claims optional, enablement-depth-first) through the canonical anvil lifecycle. The conversion seed for a later anvil:ip-uspto non-provisional filing.
domain: ip
type: skill
user-invocable: false
---

# anvil:ip-uspto-provisional — USPTO provisional patent applications

The `ip-uspto-provisional` skill produces **provisional patent applications** targeting filing at the United States Patent and Trademark Office under 35 U.S.C. §111(b). A provisional is a different artifact class than the non-provisional utility application `anvil:ip-uspto` produces: there is **no claims requirement**, no per-claim inventorship attribution, no 37 CFR 1.77(b) formal-section regime, and no examination — the provisional is never examined on the merits. Its sole legal job is to **attach a priority date to what it discloses**: under §119(e), a later non-provisional can claim the provisional's filing date only for subject matter the provisional supports at §112(a) written-description-and-enablement depth.

That inversion drives everything in this skill. Where `anvil:ip-uspto` is claim-centric (flat-weighted rubric, dedicated `claims` and `s101` critics, claim-spec correspondence as dim 9), this skill is **enablement-depth-dominant**: the dominant risk in a provisional is a thin disclosure that *names* an inventive feature without *enabling* it — priority silently fails to attach, and the gap is discovered 12 months later during conversion, when it is too late to fix. The rubric (`anvil-ip-provisional-v1`, /45, ≥39 — see `rubric.md`) weights §112(a) enablement depth highest, and the `s112` critic is the load-bearing critic.

**Relationship to `anvil:ip-uspto`** (per the skill-identity-is-artifact-identity convention — CLAUDE.md): the two are sibling skills sharing substrate through `anvil/lib/` (staged-sidecar atomicity, machine-summary scorecard kind, `_progress.json` conventions, critic discovery/aggregation) and through the ip-uspto skill's `assets/` (the `anvil-uspto.cls` LaTeX class and spec template are reused — see "Install coupling" below). The natural consumer flow is: **provisional thread → (≤12 months) → `anvil:ip-uspto` non-provisional conversion referencing it**. The conversion linkage (priority-claim text, 12-month deadline surfacing) is a tracked follow-up; in Phase 1 the connection is operational, not mechanical.

## Claims-optional posture (load-bearing)

A provisional **does not require claims**, and this skill never penalizes their absence:

- A thread with no `claims.tex` is a fully valid thread. **The absence of claims is never a finding, never a deduction, and never a critical flag** — on any dimension, by any critic.
- A **claim-seed** section is *encouraged* for conversion readiness: a `claims.tex` carrying draft claim language (or a claim-seed subsection in the spec) sharpens the articulation of the inventive features and gives the eventual non-provisional drafter a head start. When present, critics MAY read it as positive evidence toward dim 9 (*Conversion readiness*) — the interaction is **opportunistic, not punitive**, mirroring the perspective-rubric contract in `anvil/lib/snippets/rubric.md`: a claim-seed can move dim 9 up, never down, and removing it never raises a score.
- Defects *inside* a present claim-seed (a seed claim contradicting the spec, a seed limitation with no disclosure) are legitimate findings — they pollute the conversion — but cap at severity `major` (seed claims are not filed claims) **except** where the defect evidences a disclosure gap, in which case the finding belongs to the disclosure dimension (1–3) at whatever severity the gap warrants.

## Artifact contract

A **provisional thread** is a single provisional application authored across one or more revisions, identified by a slug (e.g., `acme-widget-prov`). Each thread occupies a portfolio directory:

```
<portfolio>/
  <thread>/                       Thread root with brief and reference material
    BRIEF.md                      Structured inventor brief (same shape as ip-uspto intake output)
    refs/                         Optional reference material (transcripts, sketches, lab notebooks)
    prior-art/                    Operator-supplied prior art (PDFs or markdown summaries)
    .anvil.json                   Optional per-thread overrides (max_iterations, critic set)
  <thread>.1/                     First drafted version (immutable once written)
    spec.tex                      Specification (LaTeX, \documentclass{anvil-uspto})
    anvil-uspto.cls               Class file, copied alongside so the version dir compiles standalone
    claims.tex                    OPTIONAL claim-seed block (encouraged, never required)
    drawings/
      drawing-descriptions.md     Stub descriptions for human illustrator (default v0)
      (or fig-1.svg / fig-1.pdf when rendered drawings exist)
    _outline.json                 Section-by-section drafting plan (same schema as ip-uspto; see below)
    _progress.json                Phase state for this version
    _revision-log.md              (revisions only) Maps prior critic findings to changes
  <thread>.1.review/              General reviewer sibling
  <thread>.1.s112/                §112(a) enablement-depth critic (the load-bearing critic)
  <thread>.1.priorart/            Prior-art positioning critic
  <thread>.1.audit/               Final fact-check (audit phase; command is a tracked follow-up)
  <thread>.2/                     Revised version (after revise consumes ALL critic siblings)
  ...
  <thread>.{N}/                   Terminal version, marked READY (then AUDITED once audit ships)
```

There is **no `abstract.txt`** (a provisional requires no abstract), **no `inventorship.md` gate** (no per-claim attribution without required claims; an inventorship-lite pass is a tracked follow-up), and **no `<thread>.final/`** in Phase 1 (the provisional filing package — spec.pdf + drawings.pdf + cover-sheet placeholder + counsel memo — ships with the deferred COUNSEL-READY phase).

Versioned dirs (`<thread>.{N}/`) and critic sibling dirs (`<thread>.{N}.<tag>/`) are **immutable once their `_progress.json` records the phase as `done`**. Revisions are produced as a new version dir, never by editing in place.

### `_outline.json`

The drafter uses the same outline control surface as `anvil:ip-uspto` (see that skill's SKILL.md §"Outline control surface" for the full schema and field semantics — schema reuse, not duplication). Differences for the provisional shape:

- Required section ids: `field`, `background`, `summary`, `brief-description-of-drawings`, `detailed-description`. (No `abstract` section.)
- `claim-seed` is an **optional** section id (`file: claims.tex`, `claim_tree` shape) — present only when the operator or drafter opts into a claim-seed.
- `detailed-description` subsections carry the same `feature_ref` / `ranges` / `alternatives` / `refnums` slots — these are the enablement-depth surface the `s112` critic scores, and they matter MORE here than in the non-provisional (every disclosed alternative and range is conversion scope; every omitted one is scope the conversion cannot claim with priority).

## State machine

Per-thread state, derived from on-disk evidence (not flags):

```
EMPTY → INTAKE_DONE → DRAFTED → REVIEWED → REVISED → … → READY → AUDITED
```

| State | Evidence |
|---|---|
| `EMPTY` | No `<thread>.{N}/` directories exist; brief may or may not exist |
| `INTAKE_DONE` | `<thread>/BRIEF.md` exists and is structured (intake frontmatter keys) |
| `DRAFTED` | Latest `<thread>.{N}/` exists with `spec.tex`, `drawings/drawing-descriptions.md`, and `_progress.json.draft == done`; no sibling critic at the same `N` |
| `REVIEWED` | All configured critic siblings (`<thread>.{N}.<tag>/`) at the latest `N` are `done` |
| `REVISED` | A `<thread>.{N+1}/` exists after prior critic siblings at `<thread>.{N}` |
| `READY` | Aggregate score from critic siblings ≥39/45 AND no critical flag at latest `N` |
| `AUDITED` | `<thread>.{N}.audit/_summary.md` records `passed: true` alongside a `READY` version |

Thresholds: **≥39/45 advances** (legal artifact → the high threshold band per `anvil/lib/snippets/rubric.md`). Any `s112` critical flag short-circuits regardless of total score — a provisional whose disclosure fails to enable a named inventive feature is not worth filing. Other critic critical flags follow the same short-circuit rule.

Iteration cap: default `max_iterations: 5`, overridable via `<thread>/.anvil.json`. Exceeding the cap marks the thread `BLOCKED` (human review). Stable-score termination (`STALLED`) follows `anvil/lib/snippets/rubric.md` §"Termination resolution order".

**Phase 1 scope note**: the `AUDITED` state is defined here so the state machine is stable across phases, but the `ip-uspto-provisional-audit` command is a tracked follow-up — until it ships, `READY` is the operative terminal state. The COUNSEL-READY terminal state (counsel-memo companion + filing package) is likewise deferred (issue #433 curation, "Deferred to follow-up issues").

## Command dispatch

| Command | Role | Reads | Writes |
|---|---|---|---|
| `ip-uspto-provisional` | portfolio orchestrator | all `<thread>.*` dirs under cwd | (none; reports state per thread + recommends next command) |
| `ip-uspto-provisional-draft <thread>` | drafter | `<thread>/BRIEF.md`, `<thread>/refs/`, `<thread>/prior-art/`; for revisions also prior version + critic siblings | `<thread>.{N}/` with spec/drawings (+ optional claim-seed) |
| `ip-uspto-provisional-review <thread>` | general reviewer | latest `<thread>.{N}/` | `<thread>.{N}.review/` |
| `ip-uspto-provisional-112 <thread>` | §112(a) enablement-depth critic | latest `<thread>.{N}/` | `<thread>.{N}.s112/` |
| `ip-uspto-provisional-prior-art <thread>` | prior-art critic | latest `<thread>.{N}/` + `<thread>/prior-art/**` | `<thread>.{N}.priorart/` |
| `ip-uspto-provisional-revise <thread>` | reviser | latest `<thread>.{N}/` + ALL `<thread>.{N}.<tag>/` critic siblings | `<thread>.{N+1}/` with `_revision-log.md`, or a `READY` marker |

**Intake**: there is no `ip-uspto-provisional-intake` command in Phase 1. The brief shape is identical to the non-provisional's; run **`ip-uspto-intake <thread>`** (from `anvil:ip-uspto`) to convert a raw inventor disclosure into `<thread>/BRIEF.md`, or hand-author one to the same shape. The orchestrator recommends exactly that for `EMPTY` threads.

**No `s101` critic, no `claims` critic**: a provisional is never examined, so Alice/Mayo screening of claims that don't exist is not a useful review pass; statutory-subject-matter posture is better assessed at conversion time against real claims. The claim-seed critic is a tracked follow-up.

## Multi-critic primitive — sibling directory convention

The standard N-parallel-critics-one-reviser shape, with the default critic set `review + s112 + priorart`:

```
<thread>.{N}/                   ← the artifact (immutable once review starts)
<thread>.{N}.review/            ← general reviewer (dims 4, 6, 7, 8; joint 9)
<thread>.{N}.s112/              ← §112(a) enablement-depth critic (dims 1, 2, 3; joint 9)
<thread>.{N}.priorart/          ← prior-art positioning critic (dim 5)
<thread>.{N+1}/                 ← reviser output (consumes ALL siblings above)
```

Operators can subset via `{ "critics": ["review", "s112"] }` in `<thread>/.anvil.json` (e.g., skip `priorart` when no prior art was supplied — though that critic also degrades gracefully to a `null` score). The reviser refuses to advance without all configured critics present. **`s112` may not be subsetted out** — it owns the dominant dimension; a configuration removing it is an error the reviser reports.

### Uniform critic output schema

Every critic sibling carries the **`machine-summary`** scorecard kind per `anvil/lib/snippets/scorecard_kind.md` (same kind as `anvil:ip-uspto` — the two ip skills are the machine-summary pair in the suite):

```
<thread>.{N}.<tag>/
  _summary.md         Scorecard (9-dim /45 partial — critic fills only owned dimensions) + critical flag + rubric block
  findings.md         Itemized findings: severity, location (file:section), rationale, suggested fix
  _meta.json          { critic, role, started, finished, model, schema_version,
                        scorecard_kind: "machine-summary",
                        rubric_id: "anvil-ip-provisional-v1", rubric_total: 45, advance_threshold: 39 }
  _progress.json      Phase state for this critic
```

All three rubric-stamping fields (`rubric_id` / `rubric_total` / `advance_threshold`) are **mandatory in every critic `_meta.json`** per the per-review version stamping contract (issue #346; `anvil/lib/snippets/scorecard_kind.md` §"Rubric version stamping fields") — every critic-writing command in this skill stamps them, uniformly. Critics leave non-owned dimensions `null` (never zero); the reviser aggregates non-null scores by mean per `anvil/lib/snippets/critics.md`.

**Atomicity**: every critic sibling is written atomically via the staged-sidecar primitive (`anvil/lib/sidecar.py::staged_sidecar` + the per-critic `cleanup_one_staging` sweep, issues #350/#376). Files are staged under a leading-dot `.<thread>.{N}.<tag>.tmp/` and renamed in one atomic `Path.rename` on clean completion; the final-named dir never exists in partial form.

## Progress tracking

Each `<thread>.{N}/` carries `_progress.json` per the canonical schema, read-merge-write recipe, and crash-recovery contract in `anvil/lib/snippets/progress.md` (consumer repo: `.anvil/lib/snippets/progress.md`). Validation is by file existence, not flag. `metadata.score_history` rows carry the per-row `rubric_id` stamp: `{ "iteration": <N>, "total": <total>, "threshold": 39, "rubric_id": "anvil-ip-provisional-v1" }`.

## Rubric

See `rubric.md` for the 9-dimension **/45** schema (`anvil-ip-provisional-v1`), the **≥39** advance threshold, the **enablement-depth-dominant** weighting (dim 1 at weight 8 — the inverse of ip-uspto's flat design), and the critical-flag policy. Dim 9 is ***Conversion readiness*** — replacing ip-uspto's *Claim-spec correspondence*, which cannot apply when claims are optional.

## Install coupling

This skill **reuses `anvil:ip-uspto`'s assets**: the `anvil-uspto.cls` LaTeX class and the `template-spec.tex.j2` spec scaffold at `anvil/skills/ip-uspto/assets/` (consumer repo: `.anvil/skills/ip-uspto/assets/`). The drafter copies `anvil-uspto.cls` into each version dir so versions compile standalone. Install the two skills together:

```bash
./scripts/install-anvil.sh --skills=ip-uspto,ip-uspto-provisional /path/to/consumer
```

A consumer installing `ip-uspto-provisional` without `ip-uspto` will hit a missing-class error at draft time (the drafter reports the remediation). Intake reuse (`ip-uspto-intake`) has the same coupling. Promoting the shared class/template into `anvil/lib/` is the natural follow-up once this second consumer has proven the duplication (the "wait for the second consumer" lib-extraction pattern — this IS the second consumer; see ROADMAP).

## Defaults and overrides

Consumers extend via `.anvil/skills/ip-uspto-provisional/` in their own repo:

- `voice.md` (optional) — firm or attorney drafting-voice guidance.
- `rubric.overrides.md` (optional) — additive critical-flag examples; cannot reduce the base rubric.
- `critics/` (optional) — custom critic command files, picked up by the orchestrator's sibling glob.

## Important caveats

- **This skill does NOT file a provisional application.** It produces a filing-ready specification + drawings package precursor. Filing (cover sheet SB/16, fee, Patent Center submission) requires human + attorney action — and the counsel-memo / filing-package phase is a tracked follow-up.
- **This skill does NOT replace a licensed patent attorney.** It is a drafting and review aid.
- **The prior-art critic does NOT do its own patent search.** Operator supplies prior art in `<thread>/prior-art/`.
- **A provisional is not a placeholder for a thin disclosure.** The entire value of this skill is refusing to bless an under-enabled spec. If the rubric blocks on enablement depth, the correct fix is more disclosure from the inventors — not a lower bar.
- **The 12-month conversion clock starts at filing.** Phase 1 does not track it; the conversion-linkage follow-up will surface the deadline on the non-provisional side.

## Git sync hook (opt-in, off by default)

Consumers running anvil under an external orchestrator (a sphere channel-agent, a Loom-style daemon) can opt in to a per-phase git commit hook so every lifecycle phase leaves the working tree clean: a repo-level `.anvil/config.json` with `git.commit_per_phase: true` (and optionally `git.push: true`) has each write-bearing ip-uspto-provisional command end its phase by staging only the dirs it wrote and committing as `anvil(ip-uspto-provisional/<phase>): <thread>.{N} [<state>]`. The full contract — knob shape, defaults-off rule, commit-message format, staging scope, warn-and-continue failure semantics, and ordering after the `_progress.json` `done` write and the #350 sidecar atomic rename — lives in `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo). All 5 write-bearing ip-uspto-provisional commands adopt it; the read-only `ip-uspto-provisional` portfolio orchestrator is exempt by definition. When `.anvil/config.json` is absent or the knob is false, behavior is byte-identical to a pre-#426 install — the hook is **default off**.
