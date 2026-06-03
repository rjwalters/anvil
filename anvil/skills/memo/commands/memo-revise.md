---
name: memo-revise
description: Reviser command for the memo skill. Reads the latest version + all critic siblings and produces the next version with a changelog mapping critic notes to revisions.
---

# memo-revise — Reviser

**Role**: reviser.
**Reads**: latest `<thread>.{N}/` and ALL `<thread>.{N}.*/` critic siblings (`.review/`, `.audit/`, `.critic/`, ...).
**Writes**: `<thread>.{N+1}/` containing the revised memo, exhibits, `_progress.json`, and a `changelog.md` mapping critic notes to the changes made.

This command is the canonical "N parallel critics, one reviser" pattern from anvil's design principles. It consumes any number of critic siblings at the current version and produces a single revised version that addresses them.

## Inputs

- **Thread slug** (positional argument).
- **Latest version**: highest `N` with `<thread>.{N}/memo.md`.
- **Critic siblings**: ALL `<thread>.{N}.<critic>/` directories at that `N`. At minimum the `.review/` sibling is required (the reviewer's verdict drives the dimension-by-dimension revision plan). Optional siblings (`.audit/`, `.critic/`, etc.) contribute additional findings.

## Outputs

```
<thread>.{N+1}/
  memo.md            Revised memo body
  exhibits/          Carried over and/or updated exhibits
  changelog.md       Maps each critic note (by sibling + section) to the change made in this revision
  _progress.json     Phase state with revise: done
```

## CLI flags

### `--scope <level>` (optional, default `important`)

Operator-controlled severity filter for which `comments.md` findings the reviser addresses. Valid levels are `critical-only`, `important`, and `all`. **Default is `important`** — this is a behavioral migration from the previous "address every finding regardless of severity" path (which is now opt-in via `--scope all`).

The flag honors the existing `comments.md` severity groupings already emitted by `memo-review` step 8 (`blocker` / `major` / `minor` / `nit`) — no schema change. Critics continue to emit the four-bucket grouping; the reviser teaches the grouping as a filter, not just as presentation.

**Level semantics**:

- **`--scope critical-only`** — addresses ONLY review-critical-flag (and any optional `.audit/` / `.critic/` sibling critical-flag) findings. All `blocker`, `major`, `minor`, and `nit` `comments.md` entries are deferred. Use case: a hot-fix iteration that lands the must-fix critical-flag failures (e.g., a `Summary-detail consistency: CONTRADICTED` flag from `memo-review` step 7) while explicitly punting the rest to the next pass.
- **`--scope important`** (default) — addresses critical flags + `blocker` + `major`. `minor` and `nit` are deferred. This is the default because it is the canary-surfaced structural fix for the "additivity produces document bloat" pattern documented in anvil#241 — the reviser is not "skipping work," it is letting the next `memo-review` pass re-flag findings that survived a tier filter, and the rhetorical-economy dim (rubric.md dim 9, shipped via PR #254) penalizes denser-but-not-stronger v{N+1}'s.
- **`--scope all`** — addresses every finding regardless of severity. This is the pre-issue-#241 behavior; opt-in only.

**Critical invariants (apply at every `--scope` level)**:

- **Critical-flag findings MUST always be addressed.** `--scope critical-only` does NOT skip critical-flag handling — it skips `blocker` / `major` / `minor` / `nit` while preserving the existing critical-flag-must-address rule (see §"Notes for the reviser agent" §"Critical flags trump everything").
- **Sub-threshold dimension lifts are independent of comment severity.** A rubric dimension scored below threshold (or carrying a critical flag) is always in the revision plan regardless of `--scope` — the rubric ≥35 threshold is a separate gate from the comment-severity filter.
- **Prior-pass `Resolution: declined` entries (convictions ledger) remain in scope regardless of `--scope`.** When a previous reviser pass tagged a finding `Resolution: declined — see prior conviction at <anchor>` (or any other `Resolution: declined — <reason>`), the conviction is honored across `--scope` levels — the prior critic pass already weighted the finding as worth holding ground on, and the severity filter does not override that explicit decision. If the next critic re-raises the same finding, the operator decides whether to re-uphold or reverse the conviction; the filter is silent on it.

**Reason argument**: a CLI-supplied reason is NOT required for `--scope` (this differs from the `--polish` precedent below). The default-changing-from-`all`-to-`important` is a behavioral migration, not an operator-bypass affordance; an audit-trail field in `_progress.json.metadata.scope` is sufficient.

**Composition with `--polish`.** `--scope` and `--polish` are independent flags that compose:

- `--scope` controls which comment-severity tiers the reviser addresses (default `important`).
- `--polish` bypasses the verdict pre-check at step 4 (verdict is `advance: true` + 0-critical) so the reviser can run against an already-passing memo for line-level polish.

When both are passed, the polish bypass runs first (step 4 is skipped), then the scope filter is applied to which findings the polish pass addresses (step 7). Practical compositions:

- `memo-revise <thread> --polish "<reason>"` — implicit `--scope important`; polish-pass addresses sub-threshold dim lifts + `blocker` + `major` `comments.md` entries; `minor` + `nit` are deferred. Most common polish-pass shape.
- `memo-revise <thread> --polish "<reason>" --scope all` — polish-pass addresses everything (sub-threshold dim lifts + every comment tier including `minor` + `nit`). Use when the operator explicitly wants the polish pass to sweep every line-level signal — the pre-#241 default polish-pass behavior, now opt-in.
- `memo-revise <thread> --polish "<reason>" --scope critical-only` — degenerate. By definition `--polish` requires `advance:true` + 0-critical (no critical flags exist), and `--scope critical-only` filters out everything except critical flags. The combination produces an empty revision plan (no findings to address). The reviser SHOULD print a warning naming the degeneracy (`"--polish --scope=critical-only is degenerate: polish-pass implies 0 critical flags + advance:true, and --scope=critical-only filters all severities below critical. No findings to address."`) and proceed: still write the new `<thread>.{N+1}/` version dir with `memo.md` carried over unchanged, `phases.revise.state = done`, both `metadata.revision_mode = "polish"` and `metadata.scope = "critical-only"` recorded, and a `changelog.md` containing both the polish-pass header note and a `Deferred to next iteration (scope: critical-only)` section listing every original `comments.md` entry as deferred. The new version dir is a no-op revision; the audit trail records why.

### `--polish "<reason>"` (optional)

Operator-initiated polish-pass entry point. When passed, `memo-revise` bypasses the verdict pre-check at step 4, allowing the reviser to run against an `advance:true` + 0-critical memo (which the default path correctly refuses). The polish-pass targets sub-threshold per-dimension justifications in `<thread>.{N}.review/scoring.md`, `nit`-tagged or untagged `comments.md` notes, and any optional `.audit/` / `.critic/` siblings — i.e., the line-level signal the default "fix what's broken" path would skip.

**The reason argument is required.** `--polish` without a value, `--polish ""`, and `--polish "   "` (whitespace-only) are all rejected with a clear error pointing at this rule. The reason exists as on-disk audit trail in `_progress.json.metadata.revise_force_reason` and is quoted verbatim in the `changelog.md` polish-pass header note — operators MUST supply substantive intent (e.g., *"Sharpen the conditional terms in Recommendation; reviewer noted dim 4 at 5/6 with specific suggestion."*). This mirrors the deck skill's `iteration_cap_rationale` rejection pattern at `anvil/skills/deck/SKILL.md` §"Per-thread override contract": an unjustified override is treated as malformed.

**What `--polish` bypasses.** Step 4 (verdict pre-check) only. Step 3 (iteration-cap check) still applies — `--polish` against a thread at `max_iterations` still hits the BLOCKED notice. Step 1 (review-exists check) still applies — running `--polish` twice in a row without an intervening `memo-review` is rejected (no fresh review to polish against; same shape as step 1's "no review to revise against" error). The polish pass produces exactly one new `<thread>.{N+1}/` version dir; it never loops, never consults a target score, never re-invokes itself.

**State-machine impact: none.** The polish-pass output is a normal `REVISED` version. The next `memo-review` scores `<thread>.{N+1}/` on its own rubric merits — the reviewer does NOT read `revision_mode` or `revise_force_reason`, does NOT special-case the polish pass, and does NOT apply a "be lenient because operator forced this" path. The audit-trail fields are operator-side disclosure only.

See SKILL.md §"Operator-initiated polish passes" for the user-facing shape.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/memo.md` AND at least `<thread>.{N}.review/verdict.md`. If no review exists, exit with an error ("no review to revise against; run `memo-review` first").
2. **Resume check**: if `<thread>.{N+1}/_progress.json.revise.state == done` and `memo.md` + `changelog.md` exist, the revision is complete — exit early with a notice.
3. **Iteration cap check**: read `metadata.max_iterations` from `<thread>.{N}/_progress.json` (or `<thread>/.anvil.json` override; default 4). If `N + 1 > max_iterations`, exit with a `BLOCKED` notice — human review required.
4. **Verdict pre-check**: parse `<thread>.{N}.review/verdict.md`. If `advance == true` and there are no critical flags AND `--polish` was NOT passed, exit with a notice: the thread is `READY`, no revision needed. (Default behavior is to refuse to revise an already-passing version.)

   **`--polish` bypass.** When `memo-revise <thread> --polish "<reason>"` is invoked, this step is skipped entirely; proceed to step 5 regardless of `advance:true` + 0-critical. The `--polish` flag is the in-band, audit-trailed alternative to the destructive workarounds (deleting `verdict.md`, hand-bumping `metadata.iteration`, force-editing verdict status) the default-refuse path historically forced operators into. Pre-check the flag's reason argument before bypassing: an absent / empty / whitespace-only reason is rejected with a clear error (see §"CLI flags" above); the thread is left untouched. See §"CLI flags" for the full required-reason contract.
5. **Initialize `_progress.json`**: write `phases.revise.state = in_progress`, `phases.revise.started = <ISO>`, `metadata.iteration = N+1`, `metadata.max_iterations`. Also resolve `target_length` for v{N+1} per step 6 and record `metadata.target_length_resolved` with provenance — the resolution must happen before the revision-plan prompt is built so the resolved range is in scope for both the prompt injection and the `_progress.json` provenance write.

   **Polish-pass audit trail.** Additionally write `metadata.revision_mode` and `metadata.revise_force_reason` based on the presence/absence of `--polish`:
   - Default path (no `--polish`): `metadata.revision_mode = "normal"` (or omit the field entirely — readers tolerate both shapes for backwards-compat with pre-this-change version dirs); `metadata.revise_force_reason = null` (or omit).
   - Polish path (`--polish "<reason>"`): `metadata.revision_mode = "polish"`; `metadata.revise_force_reason = "<verbatim operator-supplied reason>"`. The reason MUST be stored verbatim — no trimming, no normalization, no truncation beyond what JSON encoding requires.

   Both fields participate in the standard shallow-merge rule per `anvil/lib/snippets/progress.md` §"Read-merge-write recipe" — any subsequent command that touches `_progress.json` preserves them. `revision_mode` is NOT scored, NOT gating, and has NO state-machine impact — it is audit-trail-only (operator-side disclosure of why the polish-pass bypass was taken).

   **Scope audit trail.** Also record the resolved `--scope` level: write `metadata.scope` as one of `"critical-only"`, `"important"`, or `"all"`. The value stored is the *resolved* value at invocation time (the default `"important"` when the flag was absent, or the explicit operator-supplied value). The field participates in the shallow-merge rule per `anvil/lib/snippets/progress.md` and is preserved on subsequent writes by other commands. Absence of the field is tolerated by readers and treated as `"all"` for backwards-compat with pre-this-change version dirs. **`metadata.scope` is NOT scored, NOT gating, and has NO state-machine impact** — it is audit-trail-only, the same shape as `revision_mode`. The reviewer at the next pass does NOT read `metadata.scope` and does NOT special-case "the prior revise punted these findings" — it scores `<thread>.{N+1}/` on its own rubric merits. The audit-trail field exists for operator-side disclosure (why did the prior revise produce a deferred list?) and for the changelog header (see step 9).
6. **Read inputs**:
   - Prior version's `memo.md` and `exhibits/`.
   - `<thread>.{N}.review/verdict.md` + `scoring.md` + `comments.md`.
   - Every other `<thread>.{N}.<critic>/` sibling discovered on disk (auditor, secondary critic, etc.).
   - `<thread>/.anvil.json` — read the optional `target_length` field per the SKILL.md §Length targets contract and apply the resolution order to the version about to be produced (`N+1`):
     1. If `target_length.overrides.v{N+1}` is set and well-formed, use that range. Source: `"overrides.v{N+1}"`.
     2. Else if `target_length.default` is set and well-formed, use that range. Source: `"default"`.
     3. Else if the top-level `target_length` is the legacy flat shape (`words` or `pages` key directly), use that range. Source: `"legacy_flat"`.
     4. Else, no target. Source: `"none"`.

     Normalize the resolved range as in `memo-draft.md` step 5: `words` taken directly, `pages` converted at 600 words/page, malformed/both-keys-set/`min > max`/absent → no target. A `target_length` with both flat (`words`/`pages`) and extended (`default`/`overrides`) keys at the top level is malformed — source `"none"`, no target.

     Write the resolved range and its source into `_progress.json.metadata.target_length_resolved` as part of step 5 — shape:

     ```json
     "target_length_resolved": {
       "min_words": 2000,
       "max_words": 2800,
       "source": "overrides.v10"
     }
     ```

     When the source is `"none"`, write `{"source": "none"}` (omit `min_words`/`max_words`) or omit the field entirely; consumers tolerate both shapes.

     If a target is set, inject it into the revision-plan prompt using the exact wording: **"Target length: <min>–<max> words (~<min_pages>–<max_pages> pages at 600 words/page). Treat as a soft budget — when expanding to address reviewer notes, prefer earning the space over padding; when tightening, cut filler before substance."** The reviser does the actual expand/tighten work, so the prompt-side wording is load-bearing for reproducible behavior.
7. **Build a revision plan** — apply the `--scope` filter from step 5:
   - **Always include (no filter)**: critical-flag findings (review-critical-flag from `memo-review` step 7, plus any optional `.audit/` / `.critic/` sibling critical-flag). These are addressed regardless of `--scope` per the §"CLI flags" critical invariants.
   - **Always include (no filter)**: sub-threshold dimension lifts. For each rubric dimension that scored below threshold (or had a critical flag), enumerate the specific changes required to lift the score. The rubric ≥35 threshold is independent of comment severity — `--scope` filters comments, not dimensions.
   - **Always include (no filter)**: prior-pass `Resolution: declined` entries from the convictions ledger. When a prior reviser pass explicitly declined a finding (e.g., `Resolution: declined — see prior conviction at <anchor>`), the conviction is in scope regardless of `--scope` level — the prior critic pass already weighted the finding as worth holding ground on. The current pass either upholds the conviction (carry forward to the new `changelog.md` with the same `Resolution: declined — see prior conviction at <anchor>` reference) or reverses it (record the reversal explicitly in the new `changelog.md`); the severity filter does NOT silently drop a prior conviction.
   - **Filter `comments.md` entries by severity per the resolved `--scope` level**:
     - `--scope critical-only` — include no `comments.md` entries (the critical-flag pathway above is sufficient).
     - `--scope important` (default) — include `comments.md` entries tagged `blocker` and `major`. Defer `minor` and `nit`.
     - `--scope all` — include `comments.md` entries at all four severities (`blocker`, `major`, `minor`, `nit`).
   - **Record deferred entries**: every `comments.md` entry filtered out by the scope level is recorded for the `Deferred to next iteration` table in `changelog.md` (see step 9). The deferred list is the operator's TODO signal — the next `memo-review` pass MAY re-surface the same findings (which is correct behavior; it means the deferred items have re-aged and the operator can decide whether to lift them in the next revision).
   - Resolve conflicting feedback between critic siblings explicitly (e.g., reviewer says "more risks," critic says "fewer risks but deeper" — pick a synthesis and note it in the changelog). Conflict resolution applies to findings that survived the severity filter; conflicts among deferred findings are themselves deferred.
8. **Produce `memo.md`** at `<thread>.{N+1}/memo.md`:
   - Address each planned change.
   - Preserve sections that scored well — do not regress on dimensions that already met the standard.
   - Carry over `exhibits/` from the prior version; update or add exhibits as the revision plan requires.
9. **Write `changelog.md`**: a markdown table mapping each critic note to the change made.

   ```
   | Source                       | Note                                | Resolution                          |
   |------------------------------|-------------------------------------|-------------------------------------|
   | acme-seed.1.review (blocker) | TAM figure $40B unsourced           | Cited Gartner 2025 report; verified figure is $38B (corrected) |
   | acme-seed.1.review (major)   | Risk #2 lacks mitigation            | Added 1-paragraph mitigation referencing escrow structure        |
   | acme-seed.1.audit            | Cash burn rate disagrees with deck  | Recomputed from primary deck; updated body and exhibit          |
   ```

   For deliberate non-resolutions (e.g., critic suggested a change the reviser disagrees with), include them with `Resolution: declined — <one-line reason>`. The next reviewer pass can override or accept the reviser's judgment.

   **Polish-pass header note.** When `metadata.revision_mode == "polish"` (i.e., the reviser was invoked with `--polish "<reason>"`), prepend a blockquote header note to `changelog.md` BEFORE the table, quoting the operator's reason verbatim:

   ```
   > Polish pass — `revision_mode: polish`. Operator reason: <verbatim reason>.
   > All `advance:true` + 0-critical guards were intentionally bypassed by the operator;
   > this revision targets sub-threshold dimension scores and `comments.md` line-level
   > notes that the default revise path would have skipped.

   | Source                       | Note                                | Resolution                          |
   ...
   ```

   This makes the polish-pass disposition visible in-line for downstream readers (next reviewer, auditor, human reader of the changelog) without requiring them to inspect `_progress.json.metadata`. The reason is quoted verbatim — do NOT paraphrase or shorten. Under `--polish`, the changelog table SHOULD treat sub-threshold dimensions and `nit`/untagged comments as first-class rows (one row per addressed item); the `Source` column names the sibling and tag (e.g., `acme-seed.4.review (dim 4)`, `acme-seed.4.review (nit)`).

   **Deferred section (any non-`all` scope).** Under `--scope critical-only` or `--scope important`, append a second table to `changelog.md` after the resolutions table, listing every `comments.md` entry filtered out by the scope level. Shape:

   ```
   ## Deferred to next iteration (scope: important)

   | Source                       | Severity | Note                                       |
   |------------------------------|----------|--------------------------------------------|
   | acme-seed.1.review (minor)   | minor    | §5 risk-#3 phrasing could be tightened     |
   | acme-seed.1.review (nit)     | nit      | §2 footnote style inconsistency            |
   ```

   The scope level is named in the section header so downstream readers (next critic pass, human reviewer of the changelog) can see at a glance which tier filter was applied. Under `--scope all` the section is omitted entirely (every finding is addressed). Under `--scope critical-only` or `--scope important` the section is written even if zero entries were deferred — an empty `Deferred to next iteration (scope: ...)` table with a header row is the in-band signal that the filter was applied and nothing was caught by it.

   Deferred entries are NOT a `Resolution: declined — <reason>` — they are findings the reviser explicitly did not address this iteration because the scope filter punted them, not findings the reviser disagrees with. The next `memo-review` pass MAY re-surface the same findings (which is correct behavior; deferred items have re-aged and the operator can lift them in the next revision).

   **Composition with `--polish`.** When `--polish` is active, the polish-pass blockquote header note precedes the resolutions table (as documented above), and the `Deferred to next iteration (scope: ...)` section follows the resolutions table per the standard shape. The two annotations stack — the changelog opens with the polish-pass header, then the resolutions table, then the deferred table. The degenerate `--polish --scope=critical-only` case (see §"CLI flags" §"Composition with `--polish`") writes both the polish-pass header AND a `Deferred to next iteration (scope: critical-only)` section that lists every original `comments.md` entry as deferred — the resolutions table is empty (or omitted) because there are no findings to address.
9.7. **Invoke `memo-render` (optional, non-blocking)**: after the revised `memo.md` and `changelog.md` are written, invoke `memo-render <thread>` to render the revised `memo.md` → `memo.pdf` and write the render-gate findings into `<thread>.{N+1}/_progress.json.phases.render` + `_progress.json.render_gate`. This step is the lifecycle wiring shipped by Epic #158 Phase 3 (issue #190).

   **Non-blocking by design.** A missing renderer, a render-gate finding, or a hard pandoc failure does NOT abort `memo-revise`. The reviser still reports `Revised <thread>.{N} → <thread>.{N+1}/...` per step 11. The render outcome is recorded in `_progress.json` for the operator to surface and for the Phase 4 reviewer to read in `_summary.md.render_gate`.

   **What this preserves.** Render is a **sub-step of `REVISED`**, NOT a new state — SKILL.md §"State machine" still derives `REVISED` from the presence of `<thread>.{N+1}/` after a prior review. A `<thread>.{N+1}/` with `phases.revise == done` but no `phases.render` block is a fully legal `REVISED` state (every memo version revised before Epic #158 / Phase 3 has this shape). This step is additive and backwards-compat.

   **When to skip the call.** Two cases:
   - If `memo-render` is not on PATH (consumer hasn't installed Anvil's Phase 3 commands yet), the reviser silently skips this step.
   - If the consumer has explicitly disabled rendering via `<thread>/.anvil.json` `{"render": "skip"}` (a future config knob — NOT shipped in Phase 3), skip the call.

   See `commands/memo-render.md` §"Failure modes" and §"Composability with `memo-draft` and `memo-revise`".
10. **Update `_progress.json`**: `phases.revise.state = done`, `phases.revise.completed = <ISO>`.
11. **Report**: print the path to the new version dir and a one-line status. The status line MUST include the scope level and the deferred count alongside the existing addressed / declined counts — e.g., `Revised acme-seed.1 → acme-seed.2/ (scope: important; addressed 4 notes, deferred 3 to next iteration, declined 1)`. The scope tag is the cheap operator signal that the run took a tiered filter; the deferred count is the cheap signal of how many findings were punted. Under `--scope all` the deferred count is zero and the line MAY omit the `deferred N to next iteration` clause (or print `deferred 0 to next iteration` — readers tolerate both shapes).

   When `metadata.revision_mode == "polish"`, include the `polish pass` annotation alongside the scope annotation; both stack in the status line. Examples:
   - `Revised acme-seed.4 → acme-seed.5/ (polish pass; scope: important; addressed 4 notes, deferred 2 to next iteration, declined 0)` — polish-pass invoked with the default `--scope important`.
   - `Revised acme-seed.4 → acme-seed.5/ (polish pass; scope: all; addressed 6 notes, declined 0)` — polish-pass with explicit `--scope all` for a full line-level sweep.
   - `Revised acme-seed.4 → acme-seed.5/ (polish pass; scope: critical-only; addressed 0 notes, deferred 6 to next iteration, declined 0; degenerate composition — see changelog.md)` — the degenerate combination documented in §"CLI flags" §"Composition with `--polish`"; the trailing annotation flags the degeneracy at a glance.

   The polish-pass tag in the status line is the cheap operator signal that the run took the `--polish` bypass; the scope tag is the cheap signal of which severity tiers were addressed. Both complement the on-disk `_progress.json.metadata.revision_mode` and `_progress.json.metadata.scope` audit trails.

## Idempotence and resumability

- A completed revision (`revise.state == done` AND `memo.md` + `changelog.md` exist) is never re-run.
- A crashed revision is re-runnable after deleting partial output.

## Convergence

After this command produces `<thread>.{N+1}/`, the orchestrator should run `memo-review <thread>` on the new version. The cycle continues until:
- `verdict.md` reports `advance: true` (thread reaches `READY`), OR
- `N+1 > max_iterations` (thread is `BLOCKED` for human review).

## Notes for the reviser agent

- **Do not regress.** If a section scored 5/6 in the prior review, the next version should keep it at ≥5/6. The `changelog.md` is the audit trail proving you did not lose ground while addressing other dimensions.
- **Critical flags trump everything.** If any critic sibling raised a critical flag, the revision MUST address it — failing to do so is a worse outcome than declining a stylistic suggestion.
- **Declined notes are a feature, not a bug.** Sometimes the reviewer is wrong. Document the disagreement in `changelog.md` so the next reviewer can re-evaluate with full context.
- **Tier findings by severity.** The default `--scope important` addresses `blocker` + `major` + critical flags; `minor` and `nit` findings are deferred and recorded in `changelog.md`'s `Deferred to next iteration` section. This is the structural fix for the additivity-produces-bloat pattern documented in anvil#241 — the reviser is not "skipping work," it is letting the next `memo-review` pass re-flag findings that survived the tier filter, and the rhetorical-economy dim (rubric.md dim 9) penalizes denser-but-not-stronger v{N+1}'s. Critical flags MUST be addressed regardless of scope; deferred findings are NOT `Resolution: declined` (which means "the reviser disagrees with this finding") but a separate "punted by scope filter" category. Operators who want the pre-#241 every-finding behavior opt in via `--scope all`.
- **Convictions ledger.** Prior-pass `Resolution: declined — <reason>` entries (the convictions ledger mechanism — operator-side decisions from earlier passes recording "we considered this and held ground") remain in scope regardless of `--scope` level. The prior critic pass already weighted the finding as worth holding ground on, and the severity filter does not silently drop a prior conviction. Carry the conviction forward to the new `changelog.md` (with the same `see prior conviction at <anchor>` reference) or reverse it explicitly; never let `--scope critical-only` or `--scope important` drop a prior conviction by side effect.
- **`.latest` symlinks are not touched.** If the portfolio uses the optional `<thread>.latest` symlink convention (see SKILL.md §"Optional `.latest` convenience symlinks" and `anvil/lib/snippets/version_layout.md`), this reviser neither reads nor updates it. Symlink maintenance is consumer-side.

## `_progress.json` snippet (revised version dir)

This command writes the version-dir shape documented in `anvil/lib/snippets/progress.md`. The reviser adds a `metadata.revised_from` field naming the parent version (a memo-specific extension to the schema; the shallow-merge rule preserves it on subsequent writes):

```json
{
  "version": 1,
  "thread": "<slug>",
  "phases": {
    "revise": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  },
  "metadata": {
    "iteration": <N+1>,
    "max_iterations": 4,
    "revised_from": <N>,
    "scope": "important",
    "target_length_resolved": {
      "min_words": 2000,
      "max_words": 2800,
      "source": "overrides.v10"
    },
    "revision_mode": "polish",
    "revise_force_reason": "Sharpen the conditional terms in Recommendation; reviewer noted dim 4 at 5/6 with specific suggestion."
  }
}
```

`metadata.revised_from` helps the orchestrator's anomaly detection catch gaps in the version chain. `metadata.target_length_resolved` is the resolved target this revision was authored against, with `source` provenance — see step 6 for the resolution rules and the four documented source values (`"overrides.v{N+1}"`, `"default"`, `"legacy_flat"`, `"none"`). The reviewer reads this field rather than re-resolving from `<thread>/.anvil.json`, preventing drift if the JSON is edited between revise and review. The field is optional — its absence is tolerated for legacy version dirs (reviewer falls back to re-resolution). Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.

`metadata.scope` is the resolved `--scope` level for this revision (`"critical-only"`, `"important"` (default), or `"all"`) — see §"CLI flags" §"`--scope <level>`" for the level semantics and step 7 for the filter logic. Absence of the field is tolerated by readers and treated as `"all"` for backwards-compat with pre-this-change memo version dirs. **The field is audit-trail only — not scored, not gating, not state-machine input.** The reviewer at the next pass does NOT read `metadata.scope` and does NOT special-case "the prior revise punted these findings" — it scores `<thread>.{N+1}/` on its own rubric merits.

`metadata.revision_mode` is `"normal"` (default) or `"polish"` (when invoked with `--polish "<reason>"`). Absence of the field is tolerated by readers and treated as `"normal"` — every pre-this-change memo version dir omits this field, and downstream consumers MUST handle that case. `metadata.revise_force_reason` is `null` (or absent) on the default path; the verbatim operator-supplied reason string when `--polish` was used. All three fields (`scope`, `revision_mode`, `revise_force_reason`) are skill-specific extensions to the `_progress.json` schema and are preserved by the shallow-merge rule per `anvil/lib/snippets/progress.md`. **These fields are audit-trail only — not scored, not gating, not state-machine inputs.** The reviewer does NOT read `revision_mode`, `revise_force_reason`, or `scope` and does NOT special-case the polish pass or the scope filter; it scores the polished version on its own rubric merits.
