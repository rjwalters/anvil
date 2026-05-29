---
name: proposal
description: Draft, review, audit, and revise buildable-system proposals — the pre-commitment document pitching a concrete buildable system to whoever holds the commitment — using the standard anvil lifecycle.
domain: proposal
type: skill
user-invocable: false
---

# anvil:proposal — Buildable-system proposals

The `proposal` skill produces defensible proposals for **buildable systems** — the pre-commitment document that pitches a concrete buildable system (a fiber network, a fabrication, a deployment) to whoever holds the commitment. A proposal argues for the resources to build something; its "customer" is whoever approves the commitment:

- an **external client** (e.g. Gossamer LAN pitched to a palazzo owner), or
- an **internal budget sponsor** (an internal build spec is a proposal whose customer is the budget).

It runs the canonical anvil lifecycle with a **mandatory audit pass**: `draft → review + audit (parallel, both default) → revise → … → READY → AUDITED → figures`, with `revise` looping to `review + audit` until the rubric threshold is met or the iteration cap is reached.

These artifacts are *memo-shaped* — a LaTeX prose document with a Premise callout, multi-section priced BOM / cost tables, and an Open Decisions close. The structure mirrors **`anvil:installation`** (the sibling LaTeX-prose skill) almost file-for-file; the audit-by-default discipline mirrors **`anvil:report`**; the lifecycle/rubric format follows **`anvil:memo`**. Only the section template, the rubric dimensions, the steel-blue accent, and the worked example are specific to proposals.

## Bookend relationship to `anvil:report`

A proposal is the **pre-commitment bookend** to the existing **`anvil:report`** skill (the post-commitment deliverable):

```
proposal  →  (commitment)  →  report
 (pitch)      (money moves)     (delivery)
```

There is deliberately **no separate `anvil:spec` skill** — internal build specs are proposals answering to a budget rather than a client, scored on the same dimensions (set `customer_kind: internal`). The two bookends share the **audit-by-default discipline**: both `proposal` and `report` run their auditor sibling by default because both are documents someone relies on to *make* (proposal) or *honor* (report) a financial commitment, so correctness stakes are high. The proposal does NOT, however, adopt report's `CUSTOMER-READY`/`-promote` two-stage gate — that is report's delivery-acceptance concern; a proposal's terminal state is `AUDITED`.

## Artifact contract

A **proposal thread** is a single proposal for one buildable system, authored across one or more revisions. A thread is identified by a slug (e.g., `gossamer-lan`). Each thread occupies a portfolio directory that contains:

```
<portfolio>/
  <thread>/                Optional thread root with brief and reference material
    BRIEF.md               Optional structured or freeform brief (frontmatter + prose)
    refs/                  Optional reference material (site plans, datasheets, vendor quotes)
    .anvil.json            Optional per-thread overrides: max_iterations, customer_kind
  <thread>.1/              First drafted version (immutable once written)
    proposal.tex           Proposal body (XeLaTeX; uses templates/anvil-proposal.cls)
    anvil-proposal.cls     Class file, copied alongside so the version dir compiles standalone
    figures/               Topology diagrams, site/routing plans referenced from body
    _progress.json         Phase state for this version
    changelog.md           (revisions only) Maps prior critic notes to changes
  <thread>.1.review/       Reviewer output for version 1 (read-only)
    verdict.md             Top-level decision (advance / block) + total /40
    scoring.md             Per-dimension scores against the proposal rubric
    comments.md            Line-level comments keyed to proposal.tex
    _meta.json             { critic, scorecard_kind: "human-verdict", ... } (see lib/snippets/scorecard_kind.md)
    _progress.json         Phase state for the reviewer
  <thread>.1.audit/        Auditor output for version 1 (read-only, REQUIRED by default)
    verdict.md             Audit decision (pass / fail) + critical-flag list
    findings.md            Per-claim audit log (BOM arithmetic, spec/link-budget, sourceability)
    evidence.md            Source → dependent-claims traceability map
    _meta.json             { critic: "audit", scorecard_kind: "human-verdict", ... }
    _progress.json         Phase state for the auditor
  <thread>.2/              Revised version (after revise consumes v1 + ALL critic siblings)
  ...
  <thread>.{N}/            Terminal version, marked READY/AUDITED in its _progress.json
```

Versioned dirs (`<thread>.{N}/`) and critic sibling dirs (`<thread>.{N}.<critic>/`) are **immutable once their `_progress.json` records the phase as `done`**. Revisions are produced as a new version dir, never by editing in place.

## State machine

Per-thread state, derived from on-disk evidence (not flags):

```
EMPTY → DRAFTED → REVIEWED+AUDITED → REVISED → … → READY → AUDITED → figures
                       ↘ (either critic alone is insufficient — both required to leave DRAFTED) ↗
```

| State | Evidence |
|---|---|
| `EMPTY` | No `<thread>.{N}/` directories exist |
| `DRAFTED` | Latest `<thread>.{N}/` exists with `proposal.tex` and `_progress.json.draft == done`; no sibling review/audit at the same `N` |
| `REVIEWED` | `<thread>.{N}.review/verdict.md` exists for the latest `N` (without `.audit/`) — transient; not advance-eligible |
| `AUDITED-PARTIAL` | `<thread>.{N}.audit/verdict.md` exists for the latest `N` (without `.review/`) — transient; not advance-eligible |
| `REVIEWED+AUDITED` | BOTH `<thread>.{N}.review/verdict.md` AND `<thread>.{N}.audit/verdict.md` exist for the latest `N` |
| `REVISED` | A `<thread>.{N+1}/` exists after a prior `REVIEWED+AUDITED` state at `N` |
| `READY` | Latest `<thread>.{N}.review/verdict.md` records `advance: true` (≥32) AND latest `<thread>.{N}.audit/verdict.md` records `pass: true` AND no unresolved critical flag in either sibling |
| `AUDITED` | Same as `READY` for this skill — `AUDITED` is the standard anvil terminal state; proposal reaches it once both critic siblings clear. There is no further `CUSTOMER-READY`/`promote` stage (that is report-specific). |

**Why "REVIEWED+AUDITED" rather than running them serially?** Both siblings consume the same `<thread>.{N}/` and write to disjoint paths — they are pure parallel critics in the "N parallel critics, one reviser" sense. The reviewer scores subjective quality (`kind: judgment`); the auditor verifies externally-checkable correctness (`kind: tool_evidence` — BOM arithmetic, link budgets, sourceability). v0 runs them in parallel.

**Thresholds**: ≥32/40 advances (the internal/proposal tier, matching `anvil:memo`; not report's ≥35 customer-delivery tier). Any critical flag in EITHER `.review/` or `.audit/` short-circuits regardless of total — block until addressed.

**Iteration cap**: default `max_iterations: 4` (so worst-case terminal version is `<thread>.5/`). The cap is configurable per-thread by writing `{ "max_iterations": <N> }` to `<thread>/.anvil.json` in the thread root. Exceeding the cap marks the thread `BLOCKED` (in the portfolio orchestrator's report) and requires human review.

## Command dispatch

| Command | Role | Reads | Writes |
|---|---|---|---|
| `proposal` | portfolio orchestrator | all `<thread>.*` dirs under cwd | (none; reports state per thread + recommends next command) |
| `proposal-draft <thread>` | drafter | `<thread>/BRIEF.md` (+ `<thread>/refs/`); for revisions, also `<thread>.{N}/` + all `<thread>.{N}.*/` siblings | `<thread>.1/` (or `<thread>.{N+1}/` on revise-from-feedback path; see `proposal-revise`) |
| `proposal-review <thread>` | reviewer | latest `<thread>.{N}/` | `<thread>.{N}.review/` |
| `proposal-audit <thread>` | auditor (REQUIRED by default) | latest `<thread>.{N}/` (BOM, specs, link budgets), `<thread>/refs/` | `<thread>.{N}.audit/` |
| `proposal-revise <thread>` | reviser | latest `<thread>.{N}/` + all `<thread>.{N}.*/` critic siblings (both `.review/` and `.audit/` required) | `<thread>.{N+1}/` with `changelog.md` |
| `proposal-figures <thread>` | figurer | latest `<thread>.{N}/proposal.tex` | renders/stubs under `<thread>.{N}/figures/` |

The portfolio orchestrator is the user-facing entry point for status; the lifecycle commands are dispatched from it (or invoked directly by the orchestrating agent). `proposal-review` and `proposal-audit` run in parallel after `proposal-draft`; both must complete before `proposal-revise` (or before the thread can reach `READY`/`AUDITED`).

## Renderer

LaTeX via the shipped `templates/anvil-proposal.cls` class. PDFs are produced by **XeLaTeX** (`xelatex proposal.tex`), not pdflatex — the class uses `fontspec` for system fonts (Helvetica Neue, with a documented Latin Modern Sans fallback so it compiles on a stock TeX Live install). The `proposal.tex.j2` template is the canonical 10-section skeleton; the drafter elaborates each section into prose, tables, and figure references. The accent is steel blue (`#4A6FA5`) — the signature color of the Gossamer LAN worked instance — overridable per-brief via `signature_color`.

## The `customer_kind` knob

A single optional frontmatter key, `customer_kind: external | internal` (default `external`), captures the unifying frame (a proposal's customer is either an external client or an internal budget sponsor) with negligible surface area. It does **not** add or remove sections; it tunes emphasis in two documented places:

- **Template effect**: drives the title-block `\proposalstage` default — `DESIGN PROPOSAL --- CONCEPT STAGE` for an external pitch, `INTERNAL BUILD SPEC` for an internal allocation. An explicit `stage:` in the brief overrides either default.
- **Review effect** (see `rubric.md` and `commands/proposal-review.md`): for `external`, dimension 7 (persuasiveness / value proposition) is read as written — "why should the client say yes". For `internal`, the reviewer reads dim 7 as "justifies the budget allocation" rather than "wins the client" — same weight, reframed prompt. This is a documented reviewer instruction, not a code branch.

## Progress tracking

Each `<thread>.{N}/` directory contains `_progress.json` recording phase state. The canonical schema, read-merge-write recipe, and crash recovery contract live in `anvil/lib/snippets/progress.md` (in an installed consumer repo: `.anvil/lib/snippets/progress.md`); every command in this skill follows that convention.

Version-dir sample (no `for_version` — that field is only on critic siblings):

```json
{
  "version": 1,
  "thread": "<thread>",
  "phases": {
    "draft":   { "state": "done",        "started": "2026-05-29T14:00:00Z", "completed": "2026-05-29T14:12:00Z" },
    "figures": { "state": "in_progress", "started": "2026-05-29T14:15:00Z" }
  },
  "metadata": {
    "iteration": 1,
    "max_iterations": 4
  }
}
```

Critic-sibling sample (adds `for_version` naming the version critiqued; both `.review/` and `.audit/` use this shape):

```json
{
  "version": 1,
  "thread": "<thread>",
  "for_version": 1,
  "phases": {
    "audit": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Phase states: `pending`, `in_progress`, `done`, `failed`. Validation is **by file existence** (does `proposal.tex` exist? does the audit sibling's `verdict.md` exist?), not by flag — `_progress.json` is a resume hint, not a source of truth. A phase that crashed mid-write should be re-runnable from `pending` after deleting any partial output.

Critic siblings (`<thread>.{N}.review/`, `<thread>.{N}.audit/`) follow the `human-verdict` scorecard kind documented in `anvil/lib/snippets/scorecard_kind.md`: they emit `verdict.md` (+ `scoring.md`/`comments.md` for review, + `findings.md`/`evidence.md` for audit) for human consumption. A `_meta.json` with `{"scorecard_kind": "human-verdict"}` is recommended (the default if `_meta.json` is absent). This is the same triple the legacy adapter in `anvil/lib/critics.py` (`LEGACY_MEMO_FILES`) already reads — **no schema changes are introduced by this skill**. Per the audit migration note in `anvil/lib/snippets/audit.md`, shipped audit commands have not yet migrated to writing `_review.json` with `kind: tool_evidence`; the legacy adapter bridges the gap.

## Rubric

See `rubric.md` for the 8-dimension /40 scoring schema, the ≥32 advance threshold, and the four critical-flag short-circuit conditions. The dimensions are tuned for buildable-system proposals (intent clarity, design correctness, constraint satisfaction, scope completeness, deliverability, cost credibility, persuasiveness, open decisions). The four critical flags — *misses a stated hard constraint* · *cost estimate not credible/sourceable* · *not deliverable as resourced* · *internal inconsistency* — are the disqualifiers; three of the four are audit-owned (`kind: tool_evidence`).

## Skill-specific phases

**Audit is mandatory** (the key divergence from `anvil:installation`, which deferred audit per memo). Proposals make priced, sourceable cost claims and link-budget/throughput claims — exactly the `kind: tool_evidence` class the audit phase exists for (see `anvil/lib/snippets/audit.md`). A thread cannot reach `READY`/`AUDITED` until BOTH `.review/` and `.audit/` clear. This mirrors the post-contract bookend `anvil:report`, which runs `report-audit` by default.

A `proposal-vision` critic (rendered-artifact review of topology diagrams and routing plans) is a valuable future addition but is **out of scope for v0**: it depends on `anvil/lib/render.py` / `vision.py`, which are not yet on disk, and wiring it would violate the "no `anvil/lib/` changes" scope guard.

## Defaults and overrides

This skill ships with opinionated defaults. Consumers are expected to override liberally via `.anvil/skills/proposal/` in their own repo:

- `voice.md` (optional) — Studio or sales-engineering voice/style guidance the drafter reads in addition to its base prompt.
- `rubric.overrides.md` (optional) — Add domain-specific critical-flag examples or adjust the open-ended "any deal-breaker" instruction.
- `templates/anvil-proposal.cls` (optional) — A replacement LaTeX class (e.g., a studio house style or a different signature color).
- `BRIEF.md.example` — Reference brief shape; freeform prose with optional YAML frontmatter is accepted (see `templates/BRIEF.md.example`).
- `.anvil.json` — Per-thread overrides: `max_iterations`, `customer_kind`.
