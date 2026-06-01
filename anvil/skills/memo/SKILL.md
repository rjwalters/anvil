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
    _convictions.md        (revisions only, optional) Reviser-written carry-forward
                           positions — advisory only; see §Convictions ledger below
  <thread>.1.review/       Reviewer output for version 1 (read-only)
    verdict.md             Top-level decision (advance / block) + total /40
    scoring.md             Per-dimension scores against the memo rubric
    comments.md            Line-level comments keyed to memo.md
    _meta.json             scorecard kind + provenance; full required field set in lib/snippets/scorecard_kind.md
    _progress.json         Phase state for the reviewer
  <thread>.1.audit/        Optional auditor critic sibling (fact-check)
  <thread>.1.critic/       Optional substantive critic sibling
  <thread>.2/              Revised version (after revise consumes v1 + all critic siblings)
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

See `commands/memo-draft.md` §Procedure step 3 for the drafter contract (ingestion of `refs/` source-of-truth materials), `commands/memo-review.md` §Procedure step 5 for the reviewer back-check sub-step, and `rubric.md` §"Refs back-check (dim 3)" for the per-instance deduction rule. The contract degrades gracefully: when `refs/` contains no source-of-truth materials (only citation stubs, or empty), the back-check is inactive and dim 3 falls back to the citation-hook behavior alone.

### Convictions ledger

`<thread>.{N}/_convictions.md` is an **optional, advisory** file written by the reviser to carry settled positions forward across versions. It exists to solve a single observed friction: a reviser at version `N+1` re-litigating an issue that was already settled — by a critic challenge or by a prior reviser decision — at version `N` (or earlier).

The contract is narrowly scoped on purpose:

- **Writer**: `memo-revise` only. Written immediately after the `changelog.md` step in the reviser procedure. The drafter does not write it; reviewers do not write it; auditors do not write it.
- **Reader**: the *next* `memo-revise` invocation only. The reviser reads the convictions from `<thread>.{N}/_convictions.md` before planning the v{N+2} revision — specifically to avoid reopening positions that have already survived an explicit critic challenge or an explicit reviser decision.
- **What counts as a "conviction"**: a position that has either (a) survived an explicit critic challenge in a prior review/audit pass, or (b) survived an explicit reviser decision (e.g., a `Resolution: declined` row in a prior `changelog.md`). A drafter-introduced position with no prior challenge is **not** a conviction in this contract — only contested-and-held positions qualify.
- **Body-anchor requirement**: each conviction entry MUST name a specific section heading or paragraph anchor in the current `memo.md` that the conviction attaches to (e.g., "§Risks ¶3" or "§Recommendation ¶1"). A conviction whose named anchor no longer exists in the latest `memo.md` is automatically **stale** and should be removed (or rewritten against the new structure) on the next revise pass. This anchor requirement is the load-bearing safeguard against the ledger drifting free of the artifact it is supposed to describe.
- **Schema**: free-form prose. No JSON, no required headings, no scored fields. A single conviction entry is typically one short paragraph (anchor + position + the prior challenge it survived). See `templates/BRIEF.migration.md.example` §Convictions for a shape demonstration.

**Advisory: not scored, not gating, no state-machine impact.** `_convictions.md` does not appear in the rubric (no dimension reads it; no deduction is applied for its presence or absence). It does not appear in the state machine (`READY` and `AUDITED` derivation ignore it). The reviewer does not read it. It is purely a reviser-to-next-reviser channel. Its absence is fully normal; its presence is fully optional.

**Phase B kill switch.** This contract ships as Phase A of an explicitly staged rollout (Epic #142). If the canary does not consume `_convictions.md` within 2–4 weeks of merge, the file and its references are removed entirely per the PR #40 / PR #72 negative-result precedent. The single named consumer is the next reviser at the next version — if that consumer never reads the file, the contract has no audience and the work closes.

**Optional `.latest` convenience symlinks.** Consumers may add per-project convenience symlinks (`memo.latest -> memo.{max_N}`, `memo.latest.review -> memo.{max_N}.review`, etc.) so that downstream tooling — cross-artifact citations, share scripts, `pdfinfo` checks in CI — can target a stable path without parsing N. The convention is documented in `anvil/lib/snippets/version_layout.md` (section "Convenience `.latest` symlinks"). Resolution semantics for the memo lifecycle commands:

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

Thresholds: ≥32/40 advances. <32/40 requires revision. Any critical flag short-circuits regardless of total — block until addressed.

Iteration cap: default `max_iterations: 4` (so worst-case terminal version is `<thread>.5/`). The cap is configurable per-thread by writing `{ "max_iterations": <N> }` to `<thread>/.anvil.json` in the thread root. Exceeding the cap marks the thread `BLOCKED` (in the portfolio orchestrator's report) and requires human review.

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

## Command dispatch

| Command | Role | Reads | Writes |
|---|---|---|---|
| `memo` | portfolio orchestrator | all `<thread>.*` dirs under cwd | (none; reports state per thread + recommends next command) |
| `memo-perspective <thread>` | external-substrate critic (optional, read-only) | `<thread>/BRIEF.md`, `<thread>/refs/**`; for re-run, also latest `<thread>.{N}/memo.md` and `.review/comments.md` evidence / market / comparables / risk findings | `<thread>.0.perspective/` (initial) or `<thread>.{N}.perspective/` (re-run); both non-gating; may side-effect-write to `<thread>/refs/<key>.md` citation stubs |
| `memo-draft <thread>` | drafter | `<thread>/BRIEF.md` (+ `<thread>/refs/`), AND any `<thread>.0.perspective/` sibling (optional load-bearing context if present); for revisions, also `<thread>.{N}/` + all `<thread>.{N}.*/` siblings | `<thread>.1/` (or `<thread>.{N+1}/` on revise-from-feedback path; see `memo-revise`) |
| `memo-review <thread>` | reviewer | latest `<thread>.{N}/` | `<thread>.{N}.review/` |
| `memo-revise <thread>` | reviser | latest `<thread>.{N}/` + all `<thread>.{N}.*/` critic siblings | `<thread>.{N+1}/` with `changelog.md` |
| `memo-figures <thread>` | figurer | latest `<thread>.{N}/memo.md` | figures/tables under `<thread>.{N}/exhibits/` |

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

See `rubric.md` for the 8-dimension /40 scoring schema, the ≥32 advance threshold, and the critical-flag short-circuit policy.

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
