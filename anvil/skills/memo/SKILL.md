---
name: memo
description: Draft, review, and revise investment memos and internal analytical documents using the standard anvil lifecycle.
domain: memo
type: skill
user-invocable: false
---

# anvil:memo — Investment memos and internal documents

The `memo` skill produces defensible investment memos (and structurally similar internal analytical documents) through the canonical anvil lifecycle: `draft → review → revise → figures`, with `revise` looping to `review` until the rubric threshold is met or the iteration cap is reached.

## Artifact contract

A **memo thread** is a single decision artifact (typically: invest / pass / conditional on terms) authored across one or more revisions. A thread is identified by a slug (e.g., `acme-seed`, `q3-thesis-update`). Each thread occupies a portfolio directory that contains:

```
<portfolio>/
  <thread>/                Optional thread root with brief and reference material
    BRIEF.md               Optional structured or freeform brief (frontmatter + prose)
    refs/                  Optional reference material (decks, transcripts, data); also the home for drafter-written citation stubs created during draft (see memo-draft Evidence contract and §Citation stubs below)
  <thread>.0.perspective/  Optional pre-draft external-substrate sibling (read-only)
    notes.md               Narrative synthesis: comparable / market positioning + gaps
    candidates.md          Structured candidates (comparables, cited research, market reports, customer evidence, regulatory) with source URLs
    _meta.json             { critic: perspective, scorecard_kind: human-verdict, search_params: { ... } }
    _progress.json         Phase state (phase: perspective)
  <thread>.1/              First drafted version (immutable once written)
    memo.md                Memo body
    exhibits/              Inline exhibits referenced from body
    _progress.json         Phase state for this version
    changelog.md           (revisions only) Maps prior critic notes to changes
  <thread>.1.review/       Reviewer output for version 1 (read-only)
    verdict.md             Top-level decision (advance / block) + total /44
    scoring.md             Per-dimension scores against the memo rubric
    comments.md            Line-level comments keyed to memo.md
    _meta.json             scorecard kind + provenance; full required field set in lib/snippets/scorecard_kind.md
    _progress.json         Phase state for the reviewer
  <thread>.1.audit/        Optional auditor critic sibling (fact-check)
  <thread>.1.critic/       Optional substantive critic sibling
  <thread>.2.plan/         Optional change-set preview written by `memo-revise <thread> --plan`
    plan.md                Per-item planned-edit table (operator edits in place to decline items)
    _meta.json             { critic: plan, scorecard_kind: planner }
    _progress.json         Phase state for the plan (phase: plan)
  <thread>.2/              Revised version (after revise consumes v1 + all critic siblings; or `--apply` against `<thread>.2.plan/`)
  <thread>.2.review/
  ...
  <thread>.{N}/            Terminal version, marked READY in its _progress.json
```

Versioned dirs (`<thread>.{N}/`) and critic sibling dirs (`<thread>.{N}.<critic>/`) are **immutable once their `_progress.json` records the phase as `done`**. Revisions are produced as a new version dir, never by editing in place.

### Citation stubs

The drafter is permitted (and per `memo-draft` step 6 *Evidence* sometimes required) to write `<thread>/refs/<key>.md` stubs during draft to satisfy the citation-hook contract. A stub MAY be as minimal as `# TODO: source for <claim>` — its *existence* is the contract, its *completeness* is not.

These stubs are author scratchpad — not exhibits — and live at the **thread level** (`<thread>/refs/`, not under any `<thread>.{N}/` version dir) so they survive version transitions and accumulate as research lands across revisions. The reviewer reads them only to verify their existence as evidence of the citation-hook contract being honored; their content is not scored.

See `commands/memo-draft.md` §Procedure step 6 for the drafter contract and `rubric.md` §"Citation hooks (dim 3)" for the reviewer-side deduction rule.

### Source-of-truth materials

`<thread>/refs/` is **also** the canonical home for **author-supplied source-of-truth materials**: documents the memo's claims are evaluated against. This role coexists with the citation-stub role above — both file shapes live in the same directory, disambiguated by **filename + extension** (no manifest, no registry in v0).

Typical source-of-truth materials:

- `cv.pdf` / `cv.md` — founder CV(s); load-bearing for any team / founder-market-fit section.
- `transcript-*.md` — founder interview transcripts; load-bearing for direct-quote claims and for tone.
- `filing-*.pdf` — public filings, S-1s, government program announcements; load-bearing for sized public claims.
- `paper-*.pdf` — research papers cited in the memo; load-bearing for technical-claim citations.
- `email-*.md` — explicit-permission email or letter excerpts (LOIs, design-partner intent); load-bearing for traction claims.
- `image-*.{png,jpg}` — cleared-for-the-memo imagery (logos, product shots).
- `prior/<vN>.{pdf,md}` — prior versions of this memo (e.g., a pre-anvil LaTeX memo migrating in); load-bearing for "what's changed across the revision arc."

The list is illustrative, not exhaustive. The contract is: *"if a claim's evidentiary basis lives in a file, that file goes in `<thread>/refs/`."* Source-of-truth materials are typically named for their **content** (`cv.pdf`, `filing-s1.pdf`); citation stubs (above) are typically named for their **citation key** (`<key>.md`) and carry a `# TODO: source for <claim>` placeholder. The disambiguation is left to filename convention — a markdown file matching the TODO-stub shape is a stub; a markdown file named for its content (`cv.md`, `transcript-foo.md`, `email-loi-bigcorp.md`) is a source-of-truth material.

Accepted file shapes for source-of-truth materials in v0: markdown (`.md`), plain text (`.txt`), JSON (`.json`), PDFs (`.pdf`), images (`.png`, `.jpg`, `.jpeg`). The drafter **reads text-readable files** (markdown, text, JSON) into context as authoritative. **When `pdftotext` is available** (preflighted via `anvil/skills/memo/lib/refs_pdf.py::check_pdftotext_available()` — issue #167), the drafter ALSO extracts PDF text via `extract_pdf_text(...)` and reads it as authoritative source-of-truth content alongside the text-readable path; see `commands/memo-draft.md` step 3 for the drafter contract and `commands/memo-review.md` step 5 for the reviewer-side back-check. When `pdftotext` is absent, PDFs degrade to **presence-only signals** — the drafter is aware they exist by filename and respects the rule that claims about the subject of the file SHOULD NOT be made unless backed by content the drafter can verify; the reviewer records an info-level lint entry in `_summary.md.lint.refs_pdf_extraction` with the install story so the consumer sees how to enable the opt-in path. Images (`.png`, `.jpg`, `.jpeg`) remain presence-only in all v0 paths — OCR / vision back-check is deferred.

**Portfolio-level shared evidence** (issue #280): when `<thread>/` lives under a portfolio dir that ALSO carries a sibling `<portfolio>/research/` directory (the canary-surfaced multi-thread shape — five memo threads sharing one body of vertical briefs, comp matrices, and case studies), `<portfolio>/research/` is treated as a portfolio-level evidence pool that EVERY sibling thread's drafter ingestion and reviewer back-check resolve against, in addition to their own `<thread>/refs/`. Discovery is **opt-in by directory presence** (no manifest required), matching anvil's absence-tolerant pattern. The resolution helper is `anvil/skills/memo/lib/refs_resolver.py::resolve_refs_dirs(thread_dir)`; it returns the ordered list `[<thread>/refs/, <portfolio>/research/]` (each entry omitted when the corresponding directory does not exist). **Per-thread precedence on filename collision**: `<thread>/refs/` always comes first in the resolved list, so a thread that wants to override a portfolio-level fact with its own copy (e.g., a per-thread `cv.pdf` that supersedes a portfolio-level `cv.pdf`) wins via pick-first iteration. **Citation-token convention extension**: the existing `[refs/<file>]` citation token (for per-thread hits) is joined by `[research/<file>]` for portfolio-level hits — the reviewer's `comments.md` verdict-tag prose extends from `-> refs/<file>` to `-> <refs-dir-basename>/<file>` so the audit trail surfaces WHICH layer of the resolved list the evidence came from. **Backwards compatibility**: a thread without a sibling `<portfolio>/research/` directory produces a one-entry resolved list (`[<thread>/refs/]`), byte-identical to the pre-#280 behavior. Future-deferred: a portfolio-level `<portfolio>/.anvil.json` with a configurable `shared_refs:` path; v1 ships directory-presence-only per the absence-tolerant precedent set by `lib/anvil_config.py`.

See `commands/memo-draft.md` §Procedure step 3 for the drafter contract (ingestion of `refs/` source-of-truth materials), `commands/memo-review.md` §Procedure step 5 for the reviewer back-check sub-step, and `rubric.md` §"Refs back-check (dim 3)" for the per-instance deduction rule. The contract degrades gracefully: when `refs/` contains no source-of-truth materials (only citation stubs, or empty), the back-check is inactive and dim 3 falls back to the citation-hook behavior alone.

### Per-revision directives

A **per-revision directive** is operator-authored prose guidance for the *next* `memo-revise` pass — content beats, hard rules, or scope guidance that is too specific for `BRIEF.md` (which is thread-wide and authored before any revision) and too pre-revision for `changelog.md` (which is reviser-authored and post-hoc). The directive sits between the two as an operator-written input that briefs the reviser before the revision plan is built. The convention is **opt-in, advisory, and non-gating** — the reviser reads directive files when present and ignores them when absent, the same shape as the optional `.audit/` / `.critic/` siblings.

**What it is.** Prose markdown written by the operator before invoking `memo-revise`. Typical contents: "drop §3 entirely — it's not load-bearing for the recommendation"; "raise the conditional terms from a single sentence to a 3-bullet block citing the escrow language"; "this revision should NOT add new exhibits — tighten what's there"; "address the dim 3 evidence-quality miss in §5 by pulling the Gartner cite from `refs/gartner-2025.pdf`"; "preserve the §"Why now" framing — the reviewer's "reduce" tag on it is wrong". Directives are the operator's authoring intent for v{N+1} expressed as prose, not as JSON or scorecard data.

**Where it lives.** Two accepted file shapes — operators pick whichever fits the authoring cadence:

1. **`<thread>/REVISION_DIRECTIVE.md`** — single active directive at the thread root. Each new revision pass reads this file (if present) and the operator either edits in place between revisions or deletes the file when the directive no longer applies. This is the simpler shape — one file, always names the *next* revision pass. Matches the bessemer-style operator workflow documented in `BRIEF.md`-citation form in the studio canary.
2. **`<thread>/_directives/v<N>.md`** — versioned per-revision directives. The file at `_directives/v{N+1}.md` is the directive consumed by the next `memo-revise` pass producing `<thread>.{N+1}/`; older `_directives/v<K>.md` files (K ≤ N) are historical context preserved across revisions for forensic readers and future operators reconstructing intent. Use this shape when retaining prior-revision directives matters (typically: long-arc threads where the directive sequence is itself part of the audit trail). The `_directives/` underscore prefix matches the existing `_progress.json` / `_meta.json` / `_summary.md` convention for "operator/agent-managed metadata, not artifact content."

Both shapes coexist with `BRIEF.md` and `refs/` at the thread root. A thread MAY use both shapes simultaneously (single-shot `REVISION_DIRECTIVE.md` for the current pass, archival `_directives/v<N>.md` for historical context); the reviser reads both and merges them (newer instruction wins on conflict, with the merge surfaced in `changelog.md` per the convention below).

**Reviser contract.** The reviser at `commands/memo-revise.md` step 6 *Read inputs* reads the directive files (if present) alongside `verdict.md`, `scoring.md`, `comments.md`, and any optional `.audit/` / `.critic/` siblings. The directive informs revision-plan prioritization at step 7 — content beats are honored, hard rules are obeyed, scope guidance is respected. When a directive is consumed, the reviser annotates the `changelog.md` header with a `> Consumed <directive-path> (paraphrase of key beats).` blockquote per the documented `changelog.md` header-note convention (see `commands/memo-revise.md` step 9). Absence of the field is tolerated by readers and treated as "no directive consumed" — every pre-this-change `changelog.md` omits the annotation.

**Out of scope.** The convention does NOT change the rubric, does NOT introduce a new state-machine transition, does NOT carry a render path, and does NOT bypass the iteration cap or the verdict pre-check. Directives are advisory operator input — they inform prioritization within the existing revision-plan contract; they do NOT override critical-flag handling, do NOT bypass the `--scope` filter, and do NOT bypass the `≥35/44` rubric threshold. A directive that asks the reviser to ignore a critical flag is ignored on the critical-flag clause; the reviser still addresses the critical flag. Directives are NOT scored — the reviewer at the next pass does NOT read directive files and does NOT special-case "this version was authored under a directive"; it scores `<thread>.{N+1}/` on its own rubric merits.

**Phase A / second-consumer discipline.** The convention is documented here at zero layout cost — it formalizes the bessemer-style operator workaround surfaced by the studio canary (1 of 21 studio threads, per the curation in issue #237) without committing to a layout change. A future Phase B (a documented `directives/` slot in the canonical layout, drafter-side ingestion, or `_progress.json` integration) is gated on a second consumer signaling the same need, per the repo's `wait for the second consumer` lib-promotion discipline (CLAUDE.md, §"Working on this repo"). Operators who do not write directives are unaffected; the reviser's contract is "read if present, ignore if absent."

### Critics → reviser: scope tagging on `comments.md`

Per `rubric.md` §"Scope tagging (comments.md)" and `commands/memo-review.md` step 8, every entry in `<thread>.{N}.review/comments.md` carries a `scope: preserve | expand | reduce` label alongside its severity grouping (issue #242, Phase A — reviewer-prose-only, no `anvil/lib/` schema changes). The label is the operator-visible signal that the critic is surfacing both directions, not just additions: a `scope: reduce` comment proposes compression (drop a redundant subsection, fold an oversized footnote); a `scope: expand` comment proposes addition (a new paragraph, a new exhibit); a `scope: preserve` comment proposes a change that does not alter content volume (a reword, a typo fix). The mechanical surfacing tie: every dim 9 *Rhetorical economy* anti-pattern instance cited in `scoring.md` also appears as a `scope: reduce` `comments.md` entry, so the reviser sees the trim directive in the comment stream it consumes — not just in the score-justification prose. `_summary.md` carries a top-level `scope_distribution` block reporting `{preserve, expand, reduce}` counts; a review with `scope_distribution.reduce == 0` AND `dimensions.9 < 4` is malformed per the dim 9 echo rule. The reviser at #241 reads scope when present, falls back to severity-only ordering when absent (backwards-compat with legacy review siblings).

### Summary-detail consistency back-check

In addition to the refs back-check above (memo claim ↔ `refs/` source-of-truth), the reviewer performs an **intra-memo summary-detail consistency back-check** on every memo with a callout, abstract, TL;DR, or thesis block — see `rubric.md` §"Summary-detail consistency" and `commands/memo-review.md` §Procedure step 4e. The back-check enumerates load-bearing summary claims, locates the detail section that elaborates each claim, and classifies the relationship as `MATCH` / `ABSENT` / `CONTRADICTED` / `DIVERGENT` with severity `critical` / `important` / `suggestion`. A `CONTRADICTED` finding at `critical` severity (e.g., a callout that assigns one generation's behavior to a different generation) raises a `Summary-detail consistency: CONTRADICTED` critical flag and forces `advance: false` regardless of the rubric total.

This is the **intra-memo** leg of the back-check triangle (memo A summary ↔ memo A detail); the refs back-check above is the source-of-truth leg (memo A claim ↔ memo A `refs/`); the cross-thread analog (§"Cross-thread citation back-check" below, #236) covers memo A claim ↔ memo B §N. Phase A ships as reviewer-prose discipline (no Python detector); a Phase B detector at `anvil/skills/memo/lib/summary_detail.py` is a follow-on gated on canary signal. The canary-anchor fixture under `tests/fixtures/summary_detail_consistency/raytheon_gen_attribution/` preserves the Studio Raytheon-pitch memo.3 Gen-attribution swap as the regression-test anchor for Phase B.

### Cross-thread citation back-check

In addition to the intra-memo back-check above and the refs back-check (memo A claim ↔ memo A `refs/`), the reviewer performs a **cross-thread citation back-check** on every memo that cites other anvil threads — see `rubric.md` §"Cross-thread citation back-check (dim 3)" and `commands/memo-review.md` §Procedure step 4f. The back-check enumerates cross-thread citations in `memo.md` (literal-path / short-form / relative-path / backtick-wrapped shapes), resolves each to the cited thread's latest version, and classifies the section anchor as `ANCHOR-FOUND` / `ANCHOR-MISSING-BUT-THREAD-PRESENT` / `ANCHOR-CONTRADICTED` / `THREAD-NOT-FOUND` with severity `critical` / `important` / `suggestion`. An `ANCHOR-CONTRADICTED` finding at `critical` severity (e.g., a cite whose cited content materially contradicts the claim the citing memo attributes to it) raises a `Cross-thread cite: ANCHOR-CONTRADICTED` critical flag and forces `advance: false` regardless of the rubric total. This closes the **back-check triangle** (memo A claim ↔ memo A `refs/` + memo A summary ↔ memo A §N + memo A claim ↔ memo B §N). Phase A ships as reviewer-prose discipline (no Python detector); a Phase B detector at `anvil/skills/memo/lib/cross_thread_cite.py` is a follow-on gated on a second canary instance. The canary-anchor fixture under `tests/fixtures/cross_thread_cite_consistency/raytheon_brasidas_stale_anchor/` preserves the Studio Raytheon-pitch memo.1 → brasidas-synthesis.2 §3.1 stale-anchor catch as the regression-test anchor for Phase B.

### Project-level `BRIEF.md` (multi-document projects)

Two on-disk layouts are recognized by the memo lifecycle (see `anvil/skills/memo/lib/project_discovery.py` — sub-deliverable 1 of #283):

1. **Classic siblings-under-portfolio.** Each thread is a standalone directory with its own `BRIEF.md` and (optionally) its own `.anvil.json`. This is the documented v0 shape — every existing memo thread uses it and continues to work unchanged.
2. **Project-as-thread-root.** A single project-level `BRIEF.md` at the project root carries shared context (audience, voice, hard rules) and enumerates per-document metadata in its YAML frontmatter. Per-document slug directories hold version dirs only — no per-thread `BRIEF.md` is required. This is the studio-canary-driven shape for multi-document projects:

   ```
   <project>/
     BRIEF.md                ← project-level BRIEF (frontmatter + prose)
     .anvil.json             ← project-level defaults (sub-deliverable 3 / #286)
     <slug-a>/
       <slug-a>.1/ ...
     <slug-b>/
       <slug-b>.1/ ...
     research/               ← shared evidence pool (issue #281)
   ```

The project BRIEF's frontmatter shape:

```yaml
---
project: <name>
audience: [<primary>, <secondary>, ...]
hard_rules: [<rule>, <rule>, ...]
documents:
  - slug: <slug-a>
    artifact_type: <one-of-the-registered-types>
    target_length: { words: [min, max] }
  - slug: <slug-b>
    artifact_type: <one-of-the-registered-types>
    target_length: { pages: [min, max] }
---
```

**Registered `artifact_type` values** (closed-ended enum per Open Question #5 of #283):

- `investment-memo` — ranked-recommendation invest / pass / conditional with check size. The default memo shape.
- `position-paper` — argumentative case for a specific viewpoint (e.g., the canary's "latency wall" thesis).
- `tactical-plan` — execution plan with prioritized actions and ownership.
- `vision-document` — long-horizon technical or strategic vision.
- `descriptive-thesis` — descriptive case for a team / market / shape (e.g., the canary's "team thesis").

Unknown `artifact_type` values are rejected with an error listing the registered set. Adding a new artifact type requires a code change in `anvil/skills/memo/lib/project_brief.py::REGISTERED_ARTIFACT_TYPES`.

**Parser.** The typed parser at `anvil/skills/memo/lib/project_brief.py::load_project_brief(project_dir)` returns a `ProjectBrief` (or `None` if no BRIEF is present). The strict variant `load_project_brief_strict(project_dir)` raises `FileNotFoundError` on absence and `ValueError` on any schema violation (unknown `artifact_type`, duplicate slug, malformed `target_length`, empty `documents` list, etc.). Both loaders accept an optional `validate_dirs=True` flag that walks the project directory and applies the slug-directory divergence rule (Open Question #1 of #283): listed-but-missing slugs warn and proceed (a draft may not have been started yet); on-disk-but-unlisted slugs raise (configuration drift that would break overlay selection downstream).

**Status.** This BRIEF parser is the load-bearing primitive for sub-deliverable 3 of #283 (rubric overlay selection from project BRIEF, #286) and the cross-thread reference validation in #287. It does NOT yet read `<project>/.anvil.json` — that's deferred to #286. Lifecycle commands (`memo-draft`, `memo-review`, etc.) do not yet dispatch on project-BRIEF layout; the wiring lands with #286.

### Optional `.latest` convenience symlinks

Consumers may add per-project convenience symlinks (`memo.latest -> memo.{max_N}`, `memo.latest.review -> memo.{max_N}.review`, etc.) so that downstream tooling — cross-artifact citations, share scripts, `pdfinfo` checks in CI — can target a stable path without parsing N. The convention is documented in `anvil/lib/snippets/version_layout.md` (section "Convenience `.latest` symlinks"). Resolution semantics for the memo lifecycle commands:

- **`memo-revise` does not follow `.latest`.** It enumerates numbered `<thread>.{N}/` directories and picks the highest N (see `commands/memo-revise.md` step 1). A `.latest` symlink in the portfolio dir is inert — the digit-N anchor in `enumerate_versions` (see `anvil/lib/snippets/thread_state.md`) ignores it.
- **`memo-revise` does not update `.latest`.** After writing `<thread>.{N+1}/`, the symlink (if present) still points at the prior N until the consumer's own script (or hand-`ln`) re-points it. Anvil-shipped memo commands do not write, require, or read `.latest` symlinks in v0; maintenance is consumer-side.
- **`memo-review` and the `memo` portfolio orchestrator do not dereference `.latest`.** They enumerate the same digit-N directories as the reviser. A `.latest` symlink does not perturb state-machine derivation (`enumerate_versions` / `enumerate_siblings` regex-exclude it; see `anvil/lib/snippets/thread_state.md`).

The symlinks are therefore **purely advisory** — supported in the sense that nothing anvil does will remove or break them, but not produced or consumed by the framework. If consumers want anvil:memo to auto-update `<thread>.latest` after each revise, file a follow-on issue.

## State machine

Per-thread state, derived from on-disk evidence (not flags):

```
EMPTY → DRAFTED → REVIEWED → REVISED → … → READY
        ↑                                  ↘ AUDITED  (optional, via auditor critic sibling)
        (optional .0.perspective/ may exist before DRAFTED; it does not gate the machine)
```

The perspective sibling is intentionally allowed at `.0.perspective/` (before the first drafted version) AND at `.{N}.perspective/` (after a reviewer points out a substrate gap on `<thread>.{N}/`). Both follow the same "N parallel critics, one reviser" rule: when present at `<thread>.{N}.perspective/`, the next `memo-revise` pass consumes it alongside `.review/` and any `.audit/` / `.critic/` siblings. Per `anvil/lib/snippets/perspective.md` §"State-machine non-gating", absence of a perspective sibling does NOT block draft / review / revise — a memo thread with no perspective sibling proceeds normally. The memo-skill lifecycle (`draft → review → revise → figures`) MUST NOT list `perspective` as a required phase; it is opt-in input, not required output. See `commands/memo-perspective.md` for the command spec.

| State | Evidence |
|---|---|
| `EMPTY` | No `<thread>.{N}/` directories exist |
| `DRAFTED` | Latest `<thread>.{N}/` exists with `memo.md` and `_progress.json.draft == done`; no sibling review at the same `N` |
| `REVIEWED` | `<thread>.{N}.review/verdict.md` exists for the latest `N` |
| `REVISED` | A `<thread>.{N+1}/` exists after a prior `<thread>.{N}.review/` |
| `READY` | Latest `<thread>.{N}.review/verdict.md` records `advance: true` AND no unresolved critical flag |
| `AUDITED` | `<thread>.{N}.audit/` exists alongside a `READY` version |

Thresholds: ≥35/44 advances. <35/44 requires revision. Any critical flag short-circuits regardless of total — block until addressed.

**Plan siblings do NOT advance state.** A `<thread>.{N+1}.plan/` directory (written by `memo-revise <thread> --plan` — see §"Operator-confirmable change-set preview" below) is a critic-sibling-shaped artifact, NOT a version dir. Its presence does NOT advance the thread to `REVISED`: the state stays `REVIEWED` until `memo-revise <thread> --apply` writes the matching `<thread>.{N+1}/memo.md`. The state-machine derivation table above continues to use `<thread>.{N+1}/` presence as the `REVISED` evidence; plan siblings are invisible to it. This preserves the existing immutability contract (a half-built version dir without a `memo.md` is never `REVISED`) and keeps the two-phase flow audit-trailable on disk.

Iteration cap: default `max_iterations: 4` (so worst-case terminal version is `<thread>.5/`). The cap is configurable per-thread by writing `{ "max_iterations": <N> }` to `<thread>/.anvil.json` in the thread root. Exceeding the cap marks the thread `BLOCKED` (in the portfolio orchestrator's report) and requires human review.

### Operator-initiated polish passes

A `READY` thread is the normal terminus, but operators MAY invoke `memo-revise <thread> --polish "<reason>"` to produce one additional revision pass that targets the line-level signal the default-refuse path would skip. The polish-pass entry point exists because the studio canary's 15/15 reviewed memos landed `advance:true` + 0 critical, universally blocking the polish-pass use case under the default verdict pre-check (issue #201).

What `--polish` polishes against:

1. **Sub-threshold per-dimension justifications** in `<thread>.{N}.review/scoring.md` — any dimension where the reviewer flagged room to grow (e.g., "5/6 — the recommendation is clear but the conditional terms could be sharper").
2. **`comments.md` line-level notes** tagged `nit` or untagged — i.e., suggestions the default "fix what's broken" pass would skip because they did not rise to `blocker` / `major`.
3. Any optional `<thread>.{N}.audit/` or other critic siblings, on the same terms as a normal revise pass.

The polish-pass output is a normal `<thread>.{N+1}/` version dir (immutable, follows the reviser contract). It carries two skill-specific `metadata` extensions as the on-disk audit trail:

- `metadata.revision_mode = "polish"` (default is `"normal"` or absent).
- `metadata.revise_force_reason = "<verbatim operator-supplied reason>"` (default is `null` or absent).

The reason argument to `--polish` is **required**: empty, whitespace-only, or missing values are rejected with a clear error and the thread is left untouched. This mirrors the deck skill's `iteration_cap_rationale` rejection pattern at §"Per-thread override contract" (around line 182) — an unjustified override is treated as malformed. Unlike the deck override (which lives in `<thread>/.anvil.json`), `--polish` is a CLI flag because the polish pass is a per-invocation operator decision, not a per-thread configuration.

What `--polish` bypasses: **step 4 (verdict pre-check) only.** The iteration-cap check (step 3) still applies — a polish pass against a thread at `max_iterations` still hits the BLOCKED notice. The "fresh review required" check (step 1) still applies — running `--polish` twice in a row without an intervening `memo-review` is rejected (no fresh review to polish against). The flag is single-pass: it produces exactly one `<thread>.{N+1}/`, never loops, never consults a target score, never re-invokes itself.

The polish pass re-enters the state machine at `REVISED`. The next `memo-review` pass derives state from on-disk evidence as usual; the reviewer does NOT read `revision_mode` or `revise_force_reason` and does NOT special-case the polish pass — it scores the polished version on its own rubric merits. The state-machine derivation in the table above is unchanged; `revision_mode` is audit-trail-only — not scored, not gating, no state-machine impact.

See `commands/memo-revise.md` §"CLI flags" for the full reviser-side contract.

### Operator-confirmable change-set preview

A normal `memo-revise` invocation produces `<thread>.{N+1}/memo.md` directly — the reviser picks the revision plan, applies the edits, and writes the version dir in a single pass. Operators MAY instead invoke a **two-phase** revision via `memo-revise <thread> --plan` followed by `memo-revise <thread> --apply` to materialize a change-set preview before any edit is committed. The two-phase mode exists because the studio canary surfaced a structural gap (issue #243): the default-path reviser produces a defensible higher-scoring version that nonetheless drifts away from operator intent ("clean and forceful presentation" — the rubric scores defensibility, the operator scores clarity), and the drift surfaces only after the edit is written.

**Phase 1 — `--plan`.** `memo-revise <thread> --plan` writes a change-set preview at `<thread>.{N+1}.plan/plan.md` and exits WITHOUT producing `<thread>.{N+1}/memo.md`. The plan describes each planned edit (source critic, priority, insertion site, one-line summary, expected words delta, expected dim delta) plus an aggregate footer with the projected new word count and a target-length flag (`within_target` / `exceeds_max` / `under_min` / `no_target`). The canonical shape is documented in `templates/plan.md.template`.

**Phase 2 — `--apply`.** `memo-revise <thread> --apply` reads `<thread>.{N+1}.plan/plan.md`, validates that the plan is still fresh (verdict mtime, critic-sibling set, age cap), and produces `<thread>.{N+1}/memo.md` + `changelog.md` per the existing reviser contract. The status line is annotated `(via plan)` so downstream tooling sees the two-phase path was taken.

**Per-item rejection.** Operators reject planned items by **editing `plan.md` in place** between `--plan` and `--apply`. Three accepted edit shapes — pick whichever fits the editor flow:

1. Same-line `<!-- declined: <reason> -->` comment appended to the table row.
2. Row deletion (treated as `Resolution: declined — removed from plan` at apply time).
3. `Priority: declined` + `[declined: <reason>]` bracketed addition to the `Summary` cell.

Declined items become `Resolution: declined — <reason>` rows in `<thread>.{N+1}/changelog.md`. The reason flows verbatim — `--apply` MUST NOT paraphrase or shorten. This is the in-band, durable, git-diffable alternative to an out-of-band AskUserQuestion prompt; the plan artifact is reviewable after the fact, archivable in git history, and portable across orchestrators (Studio, raw `claude` CLI, future TUI, batch CI).

**Plan validity.** `--apply` REFUSES the plan in five cases: no matching plan exists, the source review verdict was re-run after the plan was written, a new critic sibling was added since the plan was written, the plan is older than `plan_max_age_days` (default 7, configurable via `<thread>/.anvil.json` `{"plan_max_age_days": <N>}`), or `<thread>.{N+1}/` already exists. Each rejection points at remediation (typically: re-run `--plan` to refresh).

**Composition with `--polish`.** `memo-revise <thread> --polish "<reason>" --plan` writes a polish-pass plan; `memo-revise <thread> --apply` against a polish-mode plan threads the polish-pass `revision_mode` + `revise_force_reason` audit trail through to the produced version dir. The operator does NOT re-pass `--polish "<reason>"` on the `--apply` invocation — the plan IS the audit trail. The composed flow produces `metadata.revision_mode = "polish_plan_then_apply"`.

**State-machine impact: none.** The plan sibling does NOT advance the thread to `REVISED` (see §"State machine" above). The next `memo-review` pass scores the produced version on its own rubric merits — the reviewer does NOT read `revision_mode` and does NOT special-case the via-plan path. The audit-trail fields are operator-side disclosure only, same constraints as the polish-pass entry above.

See `commands/memo-revise.md` §"Plan-then-apply mode" for the full reviser-side procedure and `templates/plan.md.template` for the canonical plan artifact shape.

## Length targets

A memo thread can declare an optional **target length** in `<thread>/.anvil.json`. The drafter and reviser pass this target into the LLM prompt as a soft length budget, and the reviewer uses it as the comparison anchor for rubric dim 7 (*Scope discipline*). When `target_length` is absent the skill behaves exactly as it does without the field — the reviewer falls back to the implicit "reasonable for the decision being made" judgment.

`target_length` accepts **two schema shapes** — both produce the same `(min_words, max_words)` resolved target. Authors pick whichever shape fits their authoring cadence:

### Flat shape (legacy, simple thread-level target)

```json
{
  "max_iterations": 4,
  "target_length": { "words": [1800, 2400] }
}
```

The flat shape applies to every version of the thread. This is the shape PR #122 shipped and continues to work unchanged — no migration required.

### Extended shape (per-version overrides)

```json
{
  "max_iterations": 12,
  "target_length": {
    "default": { "words": [1800, 2400] },
    "overrides": {
      "v9":  { "pages":  [5, 7] },
      "v10": { "words": [2000, 2800] }
    }
  }
}
```

`default` is the fallback used when no override matches the current version. `overrides` is a map from version key (`v{N}` where `N` is the positive integer matching the version dir suffix — e.g., `v9` matches `<thread>.9/`) to a `{ words: [min, max] }` or `{ pages: [min, max] }` range. Each override fully replaces `default` for its version — no partial-merge semantics; if you want a different range, write the full range.

Either `default` or `overrides` may be omitted. A thread that declares only `default` behaves identically to the legacy flat shape; a thread that declares only `overrides` falls back to no target for versions not in the override map.

### Range shape (both flat and extended forms)

Inside any `default` block, override value, or legacy flat `target_length`, the range is an object with **exactly one** of two keys:

| Key | Shape | Meaning |
|---|---|---|
| `words` | `[min, max]` | Target word count for `memo.md` (primary, deterministic, no rendering required). |
| `pages` | `[min, max]` | Target rendered page count. Converted internally at **600 words/page** (so `pages: [3, 4]` becomes `words: [1800, 2400]`). |

`words` is the primary spec form. `pages` is accepted as ergonomic shorthand for authors who think in pages, but the comparison logic always operates on word count — anvil:memo is markdown-first (no native page count without rendering) and the 600-words/page conversion is the documented, stable proxy.

Both `min` and `max` are integers; `min <= max`. The range is inclusive on both ends: a word count between `min` and `max` (inclusive) is on-target.

### Resolution order

When `memo-draft` or `memo-revise` is about to produce version `N+1`, or when `memo-review` is about to review version `N`, the resolution helper applies the following order with the target version number as input:

1. If `target_length.overrides.v{N}` is set (and well-formed), use that range.
2. Else if `target_length.default` is set (and well-formed), use that range.
3. Else (the legacy flat shape), use the top-level `target_length` directly.
4. Else, no target — fall back to the implicit "reasonable for the decision being made" behavior.

The resolved `(min_words, max_words)` is recorded in the version dir's `_progress.json.metadata.target_length_resolved` with a `source` field naming which branch fired (`"overrides.v{N}"`, `"default"`, `"legacy_flat"`, or `"none"`). The drafter and reviser write this field when initializing the version dir; the reviewer reads it rather than re-resolving — this prevents drift between the target the artifact was authored against and the target it is scored against. See `commands/memo-draft.md` step 4, `commands/memo-revise.md` step 5, and `commands/memo-review.md` step 4 for the per-command plumbing.

### Backward compatibility

`target_length` and the new `overrides` block are purely additive. A thread with no `.anvil.json`, an `.anvil.json` missing `target_length`, or a malformed `target_length` falls back to the implicit "reasonable for the decision" behavior. Specifically the following are treated as malformed (no target set, no exception raised):

- A `target_length` with both flat keys (`words`/`pages`) AND extended keys (`default`/`overrides`) — ambiguous shape, fall back to no target.
- A range with both `words` and `pages` set, or with non-integer values, or with `min > max`.
- An `overrides` value that is not a dict, or an override key that does not match `v{positive integer}`.
- An override value that is itself malformed by the rules above.

Parse errors are tolerated, never fatal — this mirrors the precedent set by `_read_anvil_json` in `anvil/lib/rubric.py`. A thread written for PR #122's flat shape continues to produce identical behavior under the resolution helper; no consumer needs to migrate.

### Render-gate `words_per_page` override (per-thread page_cap calibration)

The `memo-render` command's render gate uses a **600 words-per-page (wpp)** proxy to convert a `target_length.words` range into a derived page-count range for the advisory `memo_page_fit` warning. 600 wpp is calibrated for **dense-prose** memo bodies (the canary's investment-memo example); table-dense memos (financial models, comp tables, sensitivity matrices) typically run effective ~300-400 wpp once table whitespace is accounted for, and the 600-wpp default systematically over-derives the page range on those threads.

A thread can opt into a per-thread calibration via the optional `render_gate.words_per_page` field:

```json
{
  "max_iterations": 4,
  "target_length": { "words": [9000, 13000] },
  "render_gate": {
    "words_per_page": 400
  }
}
```

Field rules:

- **Type**: positive number (int or float). Non-numeric / boolean / `<= 0` values silently fall back to the 600-wpp default (no error raised; mirrors the malformed-shape contract above).
- **Scope**: only affects the `target_length.words → derived page range` conversion in the render gate's `memo_page_fit` dimension. When `target_length.pages` is declared directly, the override is a no-op.
- **Authoritative dimension**: the rubric's dim 7 *Scope discipline* word-count proxy remains the load-bearing length judgment. `memo_page_fit` is an advisory second layer; the override exists to suppress noise on table-dense threads where the proxy's calibration drifts from prose-density.
- **Discoverability**: the effective wpp used is recorded in the `memo_page_fit` finding message (e.g., `... @ 400 wpp`) and in the in-range informational reason so a reviewer can see which calibration the gate applied.

See `anvil/lib/render_gate.py` module docstring §"page_cap calibration" for the implementation contract and `commands/memo-render.md` step 4b for the plumbing.

## Rendering

Memo threads can OPTIONALLY render `memo.md` → `memo.pdf` via `memo-render`. Rendering is an **opt-in, asset-producing sub-step** of the canonical `draft → review → revise → figures` lifecycle — it does NOT add a new state, it does NOT add a required phase, and it is fully backward-compat with memo versions written before the renderer shipped.

The optional-render contract:

- **Sub-step of `DRAFTED` and `REVISED`, not a new state.** `_progress.json.phases.render` records whether the renderer ran for a given version directory. Absence of the `phases.render` block is **fully legal** — it means the version was never rendered (the case for every legacy memo, and for consumers who run without pandoc / weasyprint installed). The state-machine derivation in §"State machine" above is **unchanged**: `DRAFTED` is still derived from `phases.draft == done` regardless of whether render ran; `REVISED` is still derived from the presence of `<thread>.{N+1}/` after a prior review.
- **Non-blocking on failure.** A missing renderer, a render-gate finding, or even a hard pandoc failure does NOT abort `memo-draft` or `memo-revise`. The failure is recorded in `_progress.json.phases.render` and `_progress.json.render_gate`, and the upstream command completes normally. See `commands/memo-render.md` §"Failure modes" for the full table.
- **Markdown-first; PDF is derived.** `memo.md` is the source-of-truth. `memo.pdf` is a one-way derivation produced by `memo-render`; it is **regenerated on every render** and MUST NEVER be hand-edited. If the rendered output looks wrong, fix the markdown or the styles, never the PDF.
- **Lifecycle wiring.** `memo-draft` and `memo-revise` call `memo-render` after their respective writing pass (drafter step 9.5; reviser step 9.7). Both calls are non-blocking. The drafter / reviser still report success even when render is unavailable or the gate finds issues; the render outcome is for the operator and the Phase 4 reviewer-side integration to surface.
- **Composable re-run.** `memo-render <thread>` is independently re-runnable. The consumer can tweak `<consumer>/.anvil/lib/memo/styles.css` (or the framework `anvil/lib/memo/styles.css`) and re-invoke the command WITHOUT going through draft / revise. The PDF picks up the new styles; `memo.md` is untouched. See `commands/memo-render.md` §"Re-run pattern".
- **Render gate.** The five-dimension `render_gate.gate(kind="memo")` (Phase 2 / PR #185) runs as part of every render — `memo_compile_success`, `memo_page_fit`, `memo_overfull_check`, `memo_image_refs_exist`, `memo_placeholder_scan`. Findings land in `_progress.json.render_gate.findings`. Phase 4 will wire the reviewer to surface them in `_summary.md.render_gate`; in Phase 3 the findings are recorded but not yet read by the reviewer.

The full command contract — preflight, gate invocation, `_progress.json` shape, failure modes, re-run pattern — lives in `commands/memo-render.md`. The render-chain dependencies (pandoc + weasyprint / wkhtmltopdf / xelatex + optional pdfinfo) and the renderer-detection priority order are documented in `anvil/lib/memo/README.md` §"The rendering chain" and surfaced via `MEMO_RENDERER_REMEDIATION` in `anvil/lib/render.py`.

## Command dispatch

| Command | Role | Reads | Writes |
|---|---|---|---|
| `memo` | portfolio orchestrator | all `<thread>.*` dirs under cwd | (none; reports state per thread + recommends next command) |
| `memo-perspective <thread>` | external-substrate critic (optional, read-only) | `<thread>/BRIEF.md`, `<thread>/refs/**`; for re-run, also latest `<thread>.{N}/memo.md` and `.review/comments.md` evidence / market / comparables / risk findings | `<thread>.0.perspective/` (initial) or `<thread>.{N}.perspective/` (re-run); both non-gating; may side-effect-write to `<thread>/refs/<key>.md` citation stubs |
| `memo-draft <thread>` | drafter | `<thread>/BRIEF.md` (+ `<thread>/refs/`), AND any `<thread>.0.perspective/` sibling (optional load-bearing context if present); for revisions, also `<thread>.{N}/` + all `<thread>.{N}.*/` siblings | `<thread>.1/` (or `<thread>.{N+1}/` on revise-from-feedback path; see `memo-revise`) |
| `memo-review <thread>` | reviewer | latest `<thread>.{N}/` | `<thread>.{N}.review/` |
| `memo-revise <thread> [--polish "<reason>"] [--plan|--apply]` | reviser | latest `<thread>.{N}/` + all `<thread>.{N}.*/` critic siblings (and `<thread>.{N+1}.plan/` on `--apply`) | `<thread>.{N+1}/` with `changelog.md` (default path; `--apply` path); OR `<thread>.{N+1}.plan/plan.md` only (on `--plan`); with `--polish`, also `metadata.revision_mode = "polish"` + `metadata.revise_force_reason` audit trail; with `--plan`/`--apply`, also `metadata.revision_mode = "plan_then_apply"` (or `"polish_plan_then_apply"` when composed with `--polish`). `--plan` and `--apply` are mutually exclusive. See §"Operator-confirmable change-set preview" + §"Operator-initiated polish passes" for the full two-phase + polish-pass contracts. |
| `memo-render <thread>` | PDF renderer (optional, non-blocking) | latest `<thread>.{N}/memo.md`, `<thread>.{N}/_progress.json.metadata.target_length_resolved` | `<thread>.{N}/memo.pdf` (on success); `<thread>.{N}/_progress.json.phases.render` + `_progress.json.render_gate` always |
| `memo-figures <thread>` | figurer | latest `<thread>.{N}/memo.md` | figures/tables under `<thread>.{N}/exhibits/` |
| `memo-migrate-refs <thread>` | refs/ seeder (idempotent re-run path; auto-invoked as step 13 by `memo-migrate`) | `<thread>/BRIEF.md` (specifically the `## Sources` section) | `<thread>/refs/<key>.md` stubs (one per §Sources entry; idempotent by default — existing stubs skipped; `--force` overwrites) |

The portfolio orchestrator is the user-facing entry point for status; the four lifecycle commands are dispatched from it (or invoked directly by the orchestrating agent).

## Progress tracking

Each `<thread>.{N}/` directory contains `_progress.json` recording phase state. The canonical schema, read-merge-write recipe, and crash recovery contract live in `anvil/lib/snippets/progress.md` (in an installed consumer repo: `.anvil/lib/snippets/progress.md`); every command in this skill follows that convention.

Version-dir sample (no `for_version` — that field is only on critic siblings):

```json
{
  "version": 1,
  "thread": "<thread>",
  "phases": {
    "draft":   { "state": "done",        "started": "2026-05-28T14:00:00Z", "completed": "2026-05-28T14:12:00Z" },
    "figures": { "state": "in_progress", "started": "2026-05-28T14:15:00Z" }
  },
  "metadata": {
    "iteration": 1,
    "max_iterations": 4
  }
}
```

Critic-sibling sample (adds `for_version` naming the version critiqued):

```json
{
  "version": 1,
  "thread": "<thread>",
  "for_version": 1,
  "phases": {
    "review": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Phase states: `pending`, `in_progress`, `done`, `failed`. Validation is **by file existence** (does `memo.md` exist? does the exhibit referenced as `exhibits/fig-1.png` exist?), not by flag — `_progress.json` is a resume hint, not a source of truth. A phase that crashed mid-write should be re-runnable from `pending` after deleting any partial output.

Critic siblings (e.g., `<thread>.{N}.review/`) follow the `human-verdict` scorecard kind documented in `anvil/lib/snippets/scorecard_kind.md`: they emit `verdict.md` + `scoring.md` + `comments.md` for human consumption. A `_meta.json` with `{"scorecard_kind": "human-verdict"}` is recommended for discovery purposes (other agents can detect the scorecard kind without inspecting filenames; absence defaults to `human-verdict`), but it is a **required output** of the `memo-review` command — the reviewer always writes it.

## Rubric

See `rubric.md` for the 9-dimension /44 scoring schema, the ≥35 advance threshold, and the critical-flag short-circuit policy.

## Skill-specific phases

**None.** Memo lifecycle is exactly `draft → review → revise → figures`. No pre-draft research phase, no separate audit phase in v0 (fact-check is rolled into the reviewer's "Evidence quality" dimension; an `auditor` sibling critic can be added later by an installing repo without changing this skill's contract).

## Pre-flight lints (review-phase)

A pre-flight lint runs as part of `memo-review` (step 4b) before the LLM-judgment pass. The lint is **review-phase only** — the drafter and reviser do not invoke it; the drafter is intentionally allowed to produce the failure mode so the reviser sees it, mirroring the deck-review step 5b precedent (issue #31 / AC6).

| Lint | Module | Rule | What it catches |
|---|---|---|---|
| `memo_image_refs_exist` | `anvil/skills/memo/lib/memo_image_refs.py` | `memo_image_refs_exist` | Every markdown `![alt](path)` and HTML `<img src="...">` reference in `memo.md` resolves to an existing file relative to the version directory. URL refs and absolute filesystem paths are skipped. Suppression directive: `<!-- anvil-lint-disable: memo_image_refs_exist -->` on the same line as a ref or on the line immediately above. The canary mode is the `cp -r .../old/exhibits .../new/` footgun (issue #146) — when a missing ref names a subdirectory and a same-basename file exists at the version-dir root, the diagnostic surfaces this shape explicitly. |

When the lint reports `errors > 0`, `memo-review` forces `advance: false` and lists `Memo image refs (lint)` under the verdict's critical flags. The lint result is written to the review sibling's `_summary.md` under a `lint.memo_image_refs` block; see `commands/memo-review.md` step 9 for the JSON shape.

**Skill-local first.** This lib lives under `anvil/skills/memo/lib/` per the CLAUDE.md "skill-local first, lib promotion later" pattern. Promotion to `anvil/lib/` is a follow-on once `anvil:pub` and `anvil:report` (the likely second consumers — both also reference inline figures) exhibit the same pattern.

## Defaults and overrides

This skill ships with opinionated defaults. Consumers are expected to override liberally via `.anvil/skills/memo/` in their own repo:

- `voice.md` (optional) — Author or fund voice/style guidance the drafter reads in addition to its base prompt.
- `rubric.overrides.md` (optional) — Add domain-specific critical-flag examples or adjust the open-ended "any-deal-breaker" instruction.
- Reference brief shapes: `templates/BRIEF.fresh.md.example` (new-thread case — no prior version, no migration context, idea seed only) and `templates/BRIEF.migration.md.example` (migrate-from-prior-pipeline case — carries forward a prior version body, prior critic siblings, and a named delta to land). Both are freeform prose with optional YAML frontmatter. Copy whichever shape matches the thread state into `<thread>/BRIEF.md` and edit in place.
- Reference rubric-override shapes (issue #233): `templates/.anvil.json.synthesis-brief.example` and `templates/.anvil.json.feedback-memo.example` are full, copy-and-edit `.anvil.json` configs calibrated from the two canary threads documented below. Copy whichever shape matches your memo into `<thread>/.anvil.json` and tune the calibration prose from there.

## Rubric overrides and non-investment-memo shapes

`anvil:memo` ships a single rubric calibrated for **investment memos** — Recommendation clarity = "single unambiguous recommendation with check size" (dim 1), Market & competitive framing = "TAM/SAM/SOM sized to the artifact" (dim 5), Financial reasoning = "unit economics + scenario math" (dim 6), Scope discipline = "2000–3000 word memo expectation" (dim 7). Studio canary use (2026-06-02) surfaced two READY threads at 39/40 that are **not** investment memos: a decision-framework portfolio synthesis (~11K words across 5 vertical sub-recommendations) and a studio-side feedback memo TO a third party (~5K words validating + sharpening another document). Both threads worked around the rubric mismatch via per-dimension reviewer-guidance prose telling the reviewer how to interpret dims 1, 5, 6, 7 for the non-standard shape.

Two consumer surfaces support this calibration. The **structured config** (recommended) is the `rubric_overrides` block in `<thread>/.anvil.json`; the **unstructured fallback** (legacy) is a "Critical reviewer guidance" section in `BRIEF.md`. When BOTH surfaces are present the structured config wins — see `commands/memo-review.md` §"Reader dispatch order" for the precedence contract.

### Structured config: `rubric_overrides` in `<thread>/.anvil.json`

Per-thread rubric calibration lives in the `rubric_overrides` block of `<thread>/.anvil.json`. The block is **optional**: when absent, the memo skill behaves exactly as it does today (investment-memo rubric, no calibration suffixes — zero-impact for existing consumers). The full schema-of-record is the module docstring of `anvil/skills/memo/lib/anvil_config.py`; the on-disk shape is:

```json
{
  "max_iterations": 8,
  "target_length": { "words": [9000, 13000] },
  "rubric_overrides": {
    "memo_subtype": "synthesis-brief",
    "dim_1_calibration": "decision-framework — score on framework clarity + sub-recommendation sharpness, not on single ranked recommendation",
    "dim_5_calibration": "defers to underlying market models — score on integration quality not on fresh sizing",
    "dim_6_calibration": "defers to underlying market models — score on whether financial framing supports positioning",
    "dim_7_calibration": "target length 9000-13000 words; score against declared target",
    "target_length": { "words": [9000, 13000] }
  }
}
```

Recognized keys (all optional; absent keys yield byte-identical-to-pre-#233 reviewer behavior):

- **`memo_subtype`** (`string`) — Free-string label naming the shape (e.g., `"synthesis-brief"`, `"feedback-memo"`, `"decision-framework"`). Opaque to the loader and the reviewer logic; intended for human reference and audit-trail visibility in `_summary.md.rubric_overrides.memo_subtype`. Anvil does NOT ship a fixed `memo_subtype` enum in v0 — the canary subtypes documented below are conventions, not contracts. A future shipped enum (Option C in #233) is deferred until 3–4 more non-investment-memo threads accumulate.
- **`dim_N_calibration`** (`string`, `N` in 1–9) — Per-dimension calibration prose. The reviewer appends the verbatim text as a `"calibration applied: <text>"` suffix to that dimension's `scoring.md` justification (see `commands/memo-review.md` step 5 §"Rubric overrides (rubric_overrides) — calibration suffixes"). The author's exact wording is the load-bearing audit trail — no rewording, no truncation, no normalization. Only dimensions with a `dim_N_calibration` declared carry a suffix; other dimensions are byte-identical to their pre-#233 form.
- **`target_length`** (object with `words` or `pages` range) — Optional per-thread length-target override. Same flat-shape semantics as the top-level `target_length` field (see §"Length targets" above); per-version overrides are NOT supported inside `rubric_overrides` (use the top-level extended shape for that). The reviewer does NOT consume `rubric_overrides.target_length` directly for dim 7 scoring — the dim 7 anchor is the resolved range cached in `_progress.json.metadata.target_length_resolved` by the drafter / reviser. `rubric_overrides.target_length` is the **drafter / reviser** consumer surface; the reviewer's `_summary.md` records its presence as `target_length_present: bool` for the audit trail.

Tolerance and validation (lenient by default — parse errors degrade to "no overrides" rather than raising). A missing `.anvil.json`, malformed JSON, a non-dict `rubric_overrides`, or a per-field validation failure all yield an empty `RubricOverrides` and the reviewer's behavior is byte-identical to the pre-#233 status quo. Per-field validation warnings (non-string `memo_subtype`, out-of-range dim number, non-string calibration value, malformed `target_length`) are emitted via `warnings.warn` (category `UserWarning`) but never block the lifecycle. **Unknown keys** in `rubric_overrides` (anything that is not `memo_subtype`, `dim_N_calibration`, or `target_length`) are preserved verbatim under `RubricOverrides.unknown_keys` and surfaced in `_summary.md.rubric_overrides.unknown_keys` — this is the forward-compat path: a future shipped `memo_subtype` enum, a "Concision Discipline" knob, or any other key can land in `.anvil.json` ahead of loader support without breaking existing consumers.

### Worked example: `synthesis-brief` (brasidas-synthesis canary)

A decision-framework portfolio synthesis that reads across an analytical bundle and is deliberately **non-prescriptive** on the portfolio-shape choice. The reader is expected to extract the framework and apply judgment; the memo commits clearly to several sub-recommendations but explicitly defers the portfolio-shape choice to the reader. The bundle is large (~75K words of source material); the synthesis is correspondingly longer than a typical investment memo (~11K words). Without calibration, the reviewer would deduct on dim 1 ("no single recommendation"), dims 5/6 ("under-developed market/financial framing"), and dim 7 ("doc is 3–5× too long for an investment memo").

Drop `templates/.anvil.json.synthesis-brief.example` into `<thread>/.anvil.json` and tune from there. The example calibrates dims 1, 5, 6, 7 (the canary's load-bearing recalibrations) with prose drawn directly from the canary thread's `BRIEF.md` "Critical reviewer guidance" section, and sets `target_length` to `[9000, 13000]` words.

### Worked example: `feedback-memo` (raytheon-pitch-strategy canary)

A studio-side feedback memo TO a third party on a draft roadmap thesis (~5K words). The memo engages another document directly, validates parts, recommends sharpening, and proposes a concrete pitch backbone. There is **no "the company," no ask, no founder section** — the recommendation target is **positional** (sharpen the thesis, adopt the pitch backbone), not financial. Forceful brevity is load-bearing for this shape; every other rubric dim rewards additions, so the calibration prose tells the reviewer to score on positional clarity rather than investment-memo coverage. Without calibration, the reviewer would deduct on dim 1 ("no invest/pass recommendation"), dims 5/6 ("missing TAM/SAM/SOM and unit economics"), and dim 7 ("too short for a real investment memo").

Drop `templates/.anvil.json.feedback-memo.example` into `<thread>/.anvil.json` and tune from there. The example calibrates dims 1, 4, 5, 6, 7 with prose framed around the positional-recommendation shape, and sets `target_length` to `[4000, 6000]` words.

### Unstructured fallback: `BRIEF.md` "Critical reviewer guidance" (Option A)

Before the structured config shipped, the two canary threads carried per-dimension reviewer guidance as a prose section inside `BRIEF.md` — a section titled something like "Critical reviewer guidance" or "Reviewer guidance" telling the reviewer how to interpret specific dimensions for the non-standard shape. The convention works because the reviewer is briefed to read `BRIEF.md` early in `memo-review` and respects the guidance inline. Reviewer's `commands/memo-review.md` step 4g §"Reader dispatch order" formalizes this fallback: when `.anvil.json` carries no `rubric_overrides` block (or no `.anvil.json` at all), the reviewer reads any `BRIEF.md` reviewer-guidance section and respects it inline in its `scoring.md` justifications — no suffix mechanism is applied because the prose is author-written prose, not loader-typed data. When **both** sources are present, the structured config wins and the `BRIEF.md` guidance is treated as documented fallback / context only (the reviewer does NOT re-apply its prose as a suffix — that would double-count the calibration in the audit trail).

Typical `BRIEF.md` guidance shape (verbatim from the studio canary):

> **Dim 1 (Recommendation clarity).** This brief is *intentionally non-prescriptive on the strategic shape choice*. The brief commits clearly to several sub-recommendations [...] but explicitly defers the portfolio-shape choice [...] to the studio CEO. **Do not score down dim 1 for "no single recommendation" — score dim 1 on whether the decision framework itself is clearly stated and whether the sub-recommendations are sharp.**
>
> **Dim 5 (Market & competitive framing) and Dim 6 (Financial reasoning).** This brief deliberately defers detailed market sizing and quantitative scenario modeling to the underlying per-vertical market models [...] **Score these dimensions on whether the synthesis correctly integrates the model outputs into the strategic framework, not on whether the synthesis itself does original financial modeling.**
>
> **Dim 7 (Scope discipline).** Target length is [9000, 13000] words. This is materially longer than the typical investment-memo target because the brief synthesizes ~75K words of source material. **Score dim 7 against the declared target, not against a 2000-3000 word memo expectation.**

The structured `rubric_overrides` block is the recommended steady-state surface for new threads; the `BRIEF.md` convention is documented here so legacy threads continue to read correctly and so consumers who prefer the prose surface have an authoritative reference. See `commands/memo-review.md` §"Reader dispatch order: `.anvil.json` vs `BRIEF.md` 'Critical reviewer guidance'" for the full precedence contract.
