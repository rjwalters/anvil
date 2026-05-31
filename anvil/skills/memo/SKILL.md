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

**Optional `.latest` convenience symlinks.** Consumers may add per-project convenience symlinks (`memo.latest -> memo.{max_N}`, `memo.latest.review -> memo.{max_N}.review`) so that downstream tooling — cross-artifact citations, share scripts, `pdfinfo` checks in CI — can target a stable path without parsing N. The convention is documented in `anvil/lib/snippets/version_layout.md` (section "Convenience `.latest` symlinks"). Anvil-shipped memo commands do not write or require these symlinks in v0; they are consumer-maintained. The discovery globs above match only digit-N suffixes, so a `.latest` symlink is invisible to the state-machine enumeration and cannot perturb anvil's derivation logic.

## State machine

Per-thread state, derived from on-disk evidence (not flags):

```
EMPTY → DRAFTED → REVIEWED → REVISED → … → READY
                                          ↘ AUDITED  (optional, via auditor critic sibling)
```

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

The canonical `.anvil.json` shape with both knobs set:

```json
{
  "max_iterations": 4,
  "target_length": { "words": [1800, 2400] }
}
```

`target_length` is an object with **exactly one** of two range keys:

| Key | Shape | Meaning |
|---|---|---|
| `words` | `[min, max]` | Target word count for `memo.md` (primary, deterministic, no rendering required). |
| `pages` | `[min, max]` | Target rendered page count. Converted internally at **600 words/page** (so `pages: [3, 4]` becomes `words: [1800, 2400]`). |

`words` is the primary spec form. `pages` is accepted as ergonomic shorthand for authors who think in pages, but the comparison logic always operates on word count — anvil:memo is markdown-first (no native page count without rendering) and the 600-words/page conversion is the documented, stable proxy.

Both `min` and `max` are integers; `min <= max`. The range is inclusive on both ends: a word count between `min` and `max` (inclusive) is on-target.

**Backward compatibility.** `target_length` is purely additive. A thread with no `.anvil.json`, an `.anvil.json` missing `target_length`, or a malformed `target_length` (wrong shape, non-integer values, both `words` and `pages` set) falls back to the implicit "reasonable for the decision" behavior. Parse errors are tolerated, never fatal — this mirrors the precedent set by `_read_anvil_json` in `anvil/lib/rubric.py`.

**Per-version overrides are intentionally not supported in v0.** The expand/tighten cadence that motivated this field (load new content at v9, re-tighten at v10) is handled in v0 by editing `<thread>/.anvil.json` between revise calls. Per-version overrides (`target_length.overrides.v{N}`) ship as a separate follow-on issue once we see how the thread-level field is actually used.

## Command dispatch

| Command | Role | Reads | Writes |
|---|---|---|---|
| `memo` | portfolio orchestrator | all `<thread>.*` dirs under cwd | (none; reports state per thread + recommends next command) |
| `memo-draft <thread>` | drafter | `<thread>/BRIEF.md` (+ `<thread>/refs/`); for revisions, also `<thread>.{N}/` + all `<thread>.{N}.*/` siblings | `<thread>.1/` (or `<thread>.{N+1}/` on revise-from-feedback path; see `memo-revise`) |
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

## Defaults and overrides

This skill ships with opinionated defaults. Consumers are expected to override liberally via `.anvil/skills/memo/` in their own repo:

- `voice.md` (optional) — Author or fund voice/style guidance the drafter reads in addition to its base prompt.
- `rubric.overrides.md` (optional) — Add domain-specific critical-flag examples or adjust the open-ended "any-deal-breaker" instruction.
- Reference brief shapes: `templates/BRIEF.fresh.md.example` (new-thread case — no prior version, no migration context, idea seed only) and `templates/BRIEF.migration.md.example` (migrate-from-prior-pipeline case — carries forward a prior version body, prior critic siblings, and a named delta to land). Both are freeform prose with optional YAML frontmatter. Copy whichever shape matches the thread state into `<thread>/BRIEF.md` and edit in place.
