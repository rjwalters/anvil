---
name: spec
description: Draft, review, audit, revise, and illustrate normative technical specifications (protocol whitepapers, wire-format specs, consensus rules) maintained truthfully against an implementation, through the canonical anvil lifecycle. LaTeX source-of-truth with an optional PDF render; ends at AUDITED. Normative correctness is the owned dominant rubric dimension; an optional code_ref companion input feeds a spec↔implementation consistency audit.
domain: spec
type: skill
user-invocable: false
---

# anvil:spec — Normative technical specifications (maintained truthfully against an implementation)

The `spec` skill produces **normative technical specifications** — protocol whitepapers, wire-format specs, consensus rules, API contracts — through the report-shaped anvil lifecycle: `draft → review + audit (parallel) → revise → … → READY/AUDITED → figures`. The canonical model is a **consensus / protocol spec that lives in the same repo as its implementation** and must stay truthful to it: every normative claim (a constant, a struct layout, a formula, a validity predicate) either matches the implementation, or is explicitly marked as target-state with the gap tracked.

What makes the class distinct is **normative correctness**: the artifact succeeds or fails on whether its claims are *true of the thing it describes*, not on whether it teaches from intuition (that is `primer`) and not on evidentiary persuasion (that is `report`). A spec is an **audit-grade artifact** — an implementer reads it as the source of truth, so a claim that has drifted from the implementation is a defect, not a stylistic nit. The rubric is therefore weighted so that **dim 1 (Normative correctness) dominates** (weight 7), the way `primer` tilts toward pedagogy and `essay` toward voice, with internal-consistency and claim-precision heavy behind it and voice/rhetoric (dim 9) residual.

## Relationship to `anvil:primer` and `anvil:report`

`spec` borrows `report`'s / `primer`'s **lifecycle shape** (draft → parallel review+audit → revise → AUDITED, plus a figures phase and a source-of-truth + optional-PDF output) as its closest precedent. It is **a new skill, not a `primer` or `report` parameterization** — per the CLAUDE.md convention "**skill identity = artifact identity**" (Anvil ships one skill per standardized artifact type, not parameterized meta-skills with a `--type` flag). Where these skills share infrastructure (the render pipeline, the sidecar primitive, the rubric-stamping contract, the companion-ref resolver family) that sharing lives in `anvil/lib/`, not in a unified skill.

The single sharpest way to see the difference is the **companion input**, which is the *mirror image* of primer's:

| | `anvil:report` | `anvil:primer` | **`anvil:spec` (this skill)** |
|---|---|---|---|
| Genre | evidentiary findings | teach-from-intuition | **normative specification** |
| Dominant rubric dim | substance + evidence | Pedagogical scaffolding (w7) | **Normative correctness (w7)** |
| Advance threshold | ≥39/44 (customer-facing) | ≥35/44 (general) | **≥39/44 (audit-grade / legal band)** |
| Companion input | `prior_reports[]` | `spec_ref` (the formal spec it teaches *alongside*) | **`code_ref` (the implementation it *describes*)** |
| Audit checks | factual / evidence | factual + spec-consistency | **factual + spec↔implementation consistency** |
| Source-of-truth | markdown | markdown | **LaTeX (multi-file friendly) + optional PDF** |

A `spec` `documents:` entry declares `artifact_type: spec`; memo commands fail loudly when pointed at it (it selects no memo rubric overlay — it is a skill-identity artifact type, not a memo subtype).

## Artifact contract

A **spec thread** is a single normative specification authored across one or more revisions, identified by a slug (e.g., `botho-consensus-spec`, `wire-format-v2`). Each thread lives inside a **project root** carrying a project-level `BRIEF.md` (the post-#295/#296 canonical model); the body inside each version directory **echoes the slug** (`<slug>.tex`, or a `<slug>/` multi-file LaTeX tree with a `<slug>.tex` root — see §Output format):

```
<project>/                     Project root
  BRIEF.md                     Project-level brief (frontmatter `documents:` list +
                               optional per-doc `code_ref` key — see §Code-ref contract)
  research/                    Optional shared evidence pool
  <thread>/                    Thread directory (named for the slug)
    refs/                      Optional reference material (ADRs, design notes)
    <thread>.1/                First drafted version (immutable once written)
      <thread>.tex             Spec body root (filename echoes the slug per #295); may
                               \input{sections/*.tex} for a multi-file LaTeX tree
      sections/                Optional multi-file LaTeX section tree
      exhibits/                Figures produced by spec-figures (mmdc → PNG)
      <thread>.pdf             Optional PDF render (produced by spec-figures)
      _progress.json           Phase state for this version
      changelog.md             (revisions only) Maps prior critic notes to changes
    <thread>.1.review/         Reviewer sibling (read-only once written)
      verdict.md               Advance / block + total /44 + critical flags
      scoring.md               Per-dimension scores against rubric.md
      comments.md              Line-level comments keyed to the body
      _summary.md              Machine-readable summary blocks (code_ref, gates, …)
      _meta.json               human-verdict scorecard kind + #346 rubric stamps
      _progress.json           Phase state for the reviewer
    <thread>.1.audit/          Auditor sibling (read-only once written)
      verdict.md               Audit verdict + critical audit flags
      findings.md              Per-claim factual + spec↔implementation findings
      comments.md              Line-level audit comments
      _summary.md              Machine-readable audit summary (code_ref resolution)
      _meta.json               human-verdict scorecard kind + #346 rubric stamps
      _progress.json           Phase state for the auditor
    <thread>.2/                Revised version (consumes v1 + BOTH critic siblings)
    ...
    <thread>.{N}/              Terminal version, marked AUDITED in its _progress.json
```

Versioned dirs (`<thread>.{N}/`) and critic sibling dirs (`<thread>.{N}.<critic>/`) are **immutable once their `_progress.json` records the phase as `done`**. Revisions are produced as a new version dir, never by editing in place. The review and audit siblings consume the same `<thread>.{N}/` and write to disjoint paths — they are **pure parallel critics** in the "N parallel critics, one reviser" sense (the `report`/`primer` precedent).

## Code-ref contract (optional companion input)

The defining constraint of a *specification* is: **every normative claim is true of the implementation, or is explicitly marked as target-state with the gap tracked.** To make that constraint audit-checkable, a spec thread may declare an optional `code_ref` in its `BRIEF.md` `documents:` entry — a freeform path or glob naming the **implementation** this spec normatively describes:

```yaml
documents:
  - slug: botho-consensus-spec
    artifact_type: spec
    code_ref: ../../src/**/*.rs
```

`code_ref` is the **mirror image** of primer's `spec_ref`: where a primer teaches *alongside* a formal spec, a spec *describes* an implementation. The path is resolved **project-root first, then consumer-root**, the same walk `report`'s `prior_reports[]` paths, `primer`'s `spec_ref`, and the `voice:` docs use, via `anvil/lib/project_brief.py::resolve_code_ref(project_dir, slug)` (never raises on absence; a declared-but-missing path comes back as a structured `missing: true` entry). A `code_ref` is commonly a **glob over a multi-file implementation** (`src/**/*.rs`); the resolver's glob-walk handles that shape. The activation contract follows the framework-wide #428/#449 posture exactly (`report`'s `customer:` key, `primer`'s `spec_ref` block, `essay`'s `voice:` block):

- **`code_ref` declared and resolves** → the **spec↔implementation consistency tier is ACTIVE**. `spec-audit` reads the resolved implementation and performs the consistency sweep: any spec claim that *contradicts the implementation* is the audit-side finding **"spec claim contradicts implementation."** In Phase 1 this fires as a `major` finding pending the full three-way verdict logic (spec-wrong / code-wrong / intentional-gap) that lands in Phase 2 (#707 — see §Audit verdict, below). Dim 1 (*Normative correctness*) scores against the resolved implementation.
- **`code_ref` absent (undeclared)** → the tier is **inactive / silent-off**. Dim 1 scores on the spec alone (no implementation cross-check possible — the consistency finding cannot fire), and both `spec-review` and `spec-audit` record a **`major` finding recommending the operator declare `code_ref`** (a spec with no declared implementation cannot have its defining constraint mechanically enforced — a defect to surface, never a crash, never a false critical flag). This is the standard "declared-but-missing is a defect to surface; absent-and-undeclared is silent/off" activation contract.
- **`code_ref` declared but unresolvable (bad path / empty glob)** → the tier **ACTIVATES**; `resolve_code_ref` returns a `missing: true` entry (never raises), and the breakage surfaces as a **`major` finding** directing the operator to fix the path. The audit proceeds without the cross-check (graceful degradation — the same `report` customer-context / `primer` spec-ref posture); no critical flag fires from an unresolvable `code_ref`.

## Audit verdict (Phase 1 scope — three-way verdict lands in Phase 2)

The motivating incident for this class (the botho whitepaper drifting from its implementation across eight sections) taught that the fix direction for a spec↔implementation mismatch is a **human decision, never a mechanical presumption**. The full **three-way verdict** — (a) spec wrong → revise the spec; (b) code wrong → operator escalation (file an issue, **never** silently rewrite the spec to match a vestigial code path); (c) intentional target-state gap → must be recorded in an **implementation-status register** (a first-class artifact section: live vs. target per component) — is **out of scope for Phase 1** and lands in **Phase 2 (#707)**.

**Phase 1 posture**: `spec-audit` documents the `code_ref` consistency sweep at the skeleton level and, when it detects a suspected spec/implementation mismatch, records it as a **`major` finding** pending the Phase-2 verdict logic — it does **not** attempt to adjudicate direction, and it **never** auto-rewrites the spec to match the code. The command doc marks this as the extension point Phase 2 fills in. Until Phase 2 ships, an auditor applies manual judgment against `code_ref` and escalates ambiguous-direction mismatches to the operator in the verdict prose.

## State machine

Per-thread state, derived from on-disk evidence (not flags), following the `report`/`primer` parallel-critic shape (`AUDITED` is the terminal state for Phase 1 — the two-stage `CUSTOMER-READY` promotion is deliberately NOT adopted; any new terminal state introduced by the Phase-2 implementation-status register is a Phase-2 concern, flagged as TBD here):

```
EMPTY → DRAFTED → REVIEWED+AUDITED → REVISED → … → READY → AUDITED
```

| State | Evidence |
|---|---|
| `EMPTY` | No `<thread>.{N}/` directories exist |
| `DRAFTED` | Latest `<thread>.{N}/` exists with `<thread>.tex` (slug-echo per #295) and `_progress.json.draft == done`; no critic siblings at the same `N` |
| `REVIEWED-PARTIAL` | `<thread>.{N}.review/verdict.md` exists for the latest `N` (without `.audit/`) — transient; not advance-eligible |
| `AUDITED-PARTIAL` | `<thread>.{N}.audit/verdict.md` exists for the latest `N` (without `.review/`) — transient; not advance-eligible |
| `REVIEWED+AUDITED` | BOTH `<thread>.{N}.review/verdict.md` AND `<thread>.{N}.audit/verdict.md` exist for the latest `N` |
| `REVISED` | A `<thread>.{N+1}/` exists after a prior `REVIEWED+AUDITED` state at `N` |
| `READY` | Latest `REVIEWED+AUDITED` records BOTH `advance: true` (review total ≥39/44) AND a clean audit (no unresolved audit critical flag) |
| `AUDITED` | Same as `READY` for this skill — the standard anvil terminal state, reached once both critic siblings clear. `spec-figures` typically ran earlier (any time after draft) and may be re-run here idempotently to refresh the optional `<thread>.pdf` |

Thresholds: **≥39/44 advances** (the audit-grade / legal band used by `report`/`ip-uspto`/`datasheet` — a spec is an audit-grade artifact, not general educational collateral). Any critical flag (review-side or audit-side) short-circuits regardless of total — block until addressed. Iteration cap: default `max_iterations: 4`; consumer overrides via the project-BRIEF paired override (`max_iterations` + `iteration_cap_rationale`, the #349 memo contract). Exceeding the cap marks the thread `BLOCKED` (human review).

**Why "REVIEWED+AUDITED" rather than running them serially?** Both siblings consume the same `<thread>.{N}/` and write to disjoint paths — pure parallel critics. The reviewer scores normative correctness / internal consistency / claim precision / structure (the judgment side); the auditor verifies factual correctness and (when `code_ref` is active) spec↔implementation consistency. Sequential execution buys nothing here; the reviser consumes both.

## Adopting an existing spec

Most specs **predate anvil adoption**: the botho whitepaper is already a multi-file LaTeX tree (`sections/*.tex`), already in-repo, already normatively correct-ish — it just isn't inside an anvil thread yet. Bringing a pre-existing, hand-authored spec into the `spec` grammar is a **first-class, sanctioned workflow**, modeled on `pub`'s "Migrating an existing paper" section — **not** a `project-migrate` bridge-tool mode. There are no new CLI flags and no dry-run/`--apply` machinery; adoption is a filesystem-placement step the operator performs directly:

1. **Adopting a pre-existing spec is a first-class workflow, not a workaround.** The lifecycle is class-agnostic once the spec is inside a thread — exactly as `pub`'s migration section states none of its lifecycle commands require `anvil-paper.cls` specifically.
2. **The mechanical step** is placing (or `git mv`-ing / symlinking) the existing multi-file LaTeX tree into `<project>/<slug>/<slug>.1/` under the filename `spec-draft` would otherwise produce (`<slug>.tex` as the root, `sections/*.tex` alongside), then registering the thread in `BRIEF.md` with `artifact_type: spec` (and a `code_ref` pointing at the implementation). No bridge-tool flags — this is a placement step, documented here as prose guidance exactly as `pub`'s section is prose, not a new command.
3. **`spec-draft` stays thin/optional** (§Command dispatch). Its role for an adopted spec is limited to scaffolding the sidecar dirs (`_progress.json`, etc.) and validating that the placed body compiles and matches the expected `<thread>.{N}/` shape — it does **not** synthesize new spec content from scratch (draft-from-scratch is the deferred case; see §Deferred).
4. **Once adopted, the lifecycle is class-agnostic**: `spec-review → spec-revise → spec-audit → spec-figures` all operate on the compiled spec regardless of whether it originated via adoption or a fresh `spec-draft`.
5. **Fallback**: if adoption in practice needs actual mechanical file-moving beyond "place it in the right directory" (e.g., renaming a foreign multi-file convention), only then reach for `anvil:project-migrate --adopt-family`-style tagging as a fallback — but the default v1 path is this lightweight `pub`-style placement, not a new bridge-tool mode.

## Publish handoff contract

**The skill ends at `AUDITED`.** Publishing / distribution stays **consumer-native**, exactly as `anvil:report`'s CUSTOMER-READY precedent keeps customer delivery outside the framework and `anvil:primer`'s publish handoff keeps site deploys native. What the handoff guarantees to the consumer's publish tooling:

1. **A `.latest`-resolvable body**: `<thread>/<thread>.{N}/<thread>.tex` for the highest `N`; resolution semantics per `anvil/lib/latest_resolution.py::resolve_latest`.
2. **An AUDITED version**: `<thread>.{N}.review/verdict.md` records `advance: true`, total ≥39/44, zero unresolved review critical flags; `<thread>.{N}.audit/verdict.md` records a clean audit (no unresolved factual or spec↔implementation critical flag).
3. **Stamped critic metadata**: both siblings' `_meta.json` carry `scorecard_kind: "human-verdict"` plus the #346 stamps (`rubric_id: "anvil-spec-v1"`, `rubric_total: 44`, `advance_threshold: 39`).
4. **An optional PDF with embedded figures**: when `spec-figures` has run, `<thread>.{N}/<thread>.pdf` alongside the LaTeX source, plus the rendered `exhibits/*.png` at exactly the paths the body references. The LaTeX source remains the source-of-truth. `spec-figures` is idempotent and may be re-run at the terminal `AUDITED` version to refresh the PDF.

## Operator-initiated polish passes

An `AUDITED` thread is the normal terminus, but operators MAY invoke `spec-revise <thread> --polish "<reason>"` to produce one additional revision pass that targets the line-level signal the default terminal-exit path skips — sub-threshold per-dimension justifications in the review's `scoring.md`, `nit`-tagged or untagged `comments.md` notes, and audit-side line-level findings. The entry point exists because passing the threshold and having nothing worth fixing are different states.

The full contract lives in `anvil/lib/snippets/directed_revision.md`. The load-bearing invariants:

- **The reason argument is required** — empty / whitespace-only / missing is rejected and the thread is left untouched.
- **`--polish` bypasses the step-2 combined verdict pre-check ONLY.** The dual-critic-completeness check (BOTH review AND audit still required) and the iteration cap still apply.
- **No inherited credit** — the polish-pass output is a normal `<thread>.{N+1}/` version dir; the next `spec-review` + `spec-audit` pair scores it on its own rubric merits and does NOT read the audit-trail fields.
- **Audit trail**: `metadata.revision_mode = "polish"` + `metadata.revise_force_reason = "<verbatim reason>"` (audit-trail-only — not scored, not gating, no state-machine impact). The default (no-flag) `spec-revise` behavior is byte-identical to the no-flag shape.

See `commands/spec-revise.md` §"CLI flags" for the reviser-side procedure.

## Output format

A spec's body **is LaTeX** (`<thread>.tex`, optionally `\input`-ing a `sections/*.tex` tree) — this is a deliberate departure from `primer`, whose body is markdown even though its `spec_ref` companion consumes LaTeX. The reasoning: a normative spec is an audit-grade, cross-referenced, formula-and-table-heavy document whose real-world instances (the botho whitepaper, wire-format standards) are already authored as multi-file LaTeX, and `code_ref`'s glob-walk already proves the resolver handles that shape. Markdown is the wrong source-of-truth for a document whose value is precise numbered sections, formal predicates, and cross-references. The `<thread>.pdf` is produced from the LaTeX source via `anvil/lib/render.py` + `anvil/lib/render_gate.py` (the LaTeX-skill render-gate analog of `marp_lint`) — reusing the shared render plumbing (`pub`/`datasheet`/`ip-uspto` are the LaTeX-body precedents), not a new pipeline.

Diagrams (message flows, state machines, the end-to-end walkthrough) are produced via the documented `mmdc → PNG` path (`report`/`pub`/`primer` figure primitives) and land under `<thread>.{N}/exhibits/`, referenced from the body. Following the draft-time figure-placement precedent: the drafter places the figure references in the body at draft time and records a `figure_plan` in `_progress.json`; `spec-figures` then renders to exactly those referenced paths any time after draft (no `AUDITED` gate), so review/audit can score them.

## Command dispatch

| Command | Role | Reads | Writes |
|---|---|---|---|
| `spec` | portfolio/status orchestrator (read-only) | all `<thread>.*` dirs under cwd | (none; reports state per thread + recommends next command) |
| `spec-draft <thread>` | drafter (thin — adoption-first; §Adopting an existing spec) | project `BRIEF.md` (+ optional `code_ref`), `<thread>/refs/`, shared `research/`; for revisions also prior version + critic siblings | `<thread>.{N}/<thread>.tex` + `_progress.json` |
| `spec-review <thread>` | reviewer (normative-correctness / consistency / precision critic) | latest `<thread>.{N}/`, resolved `code_ref`, `rubric.md` | `<thread>.{N}.review/` |
| `spec-audit <thread>` | auditor (factual + spec↔implementation consistency) | latest `<thread>.{N}/`, resolved `code_ref`, `rubric.md` | `<thread>.{N}.audit/` |
| `spec-revise <thread>` | reviser | latest `<thread>.{N}/` + BOTH critic siblings | `<thread>.{N+1}/` with `changelog.md`, or reports `AUDITED` |
| `spec-figures <thread>` | figurer | latest `<thread>.{N}/` (any time after draft — no AUDITED gate) + `metadata.figure_plan` | `<thread>.{N}/exhibits/` (rendered to the drafter-referenced paths) + optional `<thread>.pdf` |

## Rubric

See `rubric.md` for the 9-dimension **/44** schema (`anvil-spec-v1`), the **≥39** audit-grade advance threshold, the **normative-correctness-dominant weighting** (dim 1 *Normative correctness* at weight 7 — the class lives or dies on it, with internal-consistency and claim-precision heavy behind it), and the critical flags. Phase 1 ships the rubric's *scoring* structure for dim 1 (what a 7 vs a 3 looks like) with the automated cross-check deferred to Phase 2 (#707); the three-way audit verdict flag ("Implementation contradicts normative claim") is documented as a **forward reference to Phase 2** — Phase 1 auditors flag any suspected code/spec mismatch as a `major` finding pending that logic. The deterministic cross-table constant-consistency gate is Phase 3 (#708) and is likewise not built here.

Every critic-writing pass stamps `_meta.json` with `scorecard_kind: "human-verdict"`, `rubric_id: "anvil-spec-v1"`, `rubric_total: 44`, `advance_threshold: 39` (per-review version stamping, issue #346) and writes its sidecar atomically via `anvil/lib/sidecar.py::staged_sidecar` + the per-critic `cleanup_one_staging` sweep (issues #350/#376).

## Project BRIEF artifact type

`spec` is registered as a **skill-identity** `artifact_type` value in the shared project-BRIEF registry (`anvil/lib/project_brief.py::REGISTERED_ARTIFACT_TYPES` / `SKILL_IDENTITY_ARTIFACT_TYPES`; following the #386/#408/#432/#440/#460/#686 pattern). In a shared project BRIEF, a `documents:` entry with `artifact_type: spec` declares that this skill owns the thread. It is NOT a memo subtype: it selects no memo rubric overlay, and memo commands fail loudly when pointed at a `spec`-declared thread.

## Deferred (tracked follow-ups; deliberately NOT in Phase 1)

Per the phased epic (#697) — ship the skeleton in one right-sized PR, defer the harder logic to later phases:

- **Three-way audit verdict + implementation-status register** — Phase 2 (#707). The spec↔implementation consistency sweep's full spec-wrong / code-wrong / intentional-gap adjudication and the first-class implementation-status register section. Phase 1 documents the sweep narratively and flags mismatches as `major` findings pending this logic.
- **Deterministic cross-table constant-consistency gate** — Phase 3 (#708). A skill-local `anvil/skills/spec/lib/constant_consistency.py` (per the `datasheet` `pinmap_check.py` / `buswidth_check.py` precedent) extracting named constants from LaTeX tables/sections and flagging same-name-different-value occurrences (the botho block-time-floor 3s-vs-5s case). Phase 1 scores internal consistency by judgment only.
- **Worked example / dogfood** — Phase 4 (#709). The botho whitepaper (botho#902) as the vendored worked example under `examples/`, mirroring primer's #693/#700 pattern.
- **Draft-from-scratch** — a full generative drafter (as opposed to the thin adoption-scaffolding `spec-draft`) is deferred; adoption-mode v1 is the right-sized scope (§Adopting an existing spec).
- **Change-impact mode** — diffing a code change against the spec to find claims it invalidates — powerful but separable; deferred.

## Defaults and overrides

Consumers extend via `.anvil/skills/spec/` in their own repo:

- `rubric.overrides.md` (optional) — additive critical-flag examples; cannot reduce the base rubric.
- `templates/spec.template.tex` (optional) — replace the default spec skeleton.

Resolution rule: consumer overrides win when present, else fall back to skill defaults.

## Git sync hook (opt-in, off by default)

Consumers running anvil under an external orchestrator can opt in to a per-phase git commit hook so every lifecycle phase leaves the working tree clean: a repo-level `.anvil/config.json` with `git.commit_per_phase: true` (and optionally `git.push: true`) has each write-bearing spec command end its phase by staging only the dirs it wrote and committing as `anvil(spec/<phase>): <thread>.{N} [<state>]`. The full contract lives in `anvil/lib/snippets/git_sync.md`. All write-bearing spec commands adopt it; the read-only `spec` portfolio orchestrator is exempt by definition. When `.anvil/config.json` is absent or the knob is false, behavior is byte-identical — the hook is **default off**.
