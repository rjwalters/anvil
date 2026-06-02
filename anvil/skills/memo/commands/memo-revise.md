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

   Both fields participate in the standard shallow-merge rule per `anvil/lib/snippets/progress.md` §"Read-merge-write recipe" — any subsequent command that touches `_progress.json` preserves them. `revision_mode` is NOT scored, NOT gating, and has NO state-machine impact — it is audit-trail-only, mirroring the `_convictions.md` advisory-only contract.
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
7. **Build a revision plan**:
   - For each rubric dimension that scored below threshold (or had a critical flag), enumerate the specific changes required to lift the score.
   - For each `comments.md` entry tagged `blocker` or `major`, plan a concrete change.
   - Resolve conflicting feedback between critic siblings explicitly (e.g., reviewer says "more risks," critic says "fewer risks but deeper" — pick a synthesis and note it in the changelog).
7.5. **Read prior convictions (before re-litigating settled issues)**: if `<thread>.{N}/_convictions.md` exists, read it before finalizing the revision plan. Each conviction names a body anchor (section heading or paragraph) in the prior `memo.md` and records a position that has already survived an explicit critic challenge or an explicit reviser decision. For each conviction:
   - If the same position is being reopened by a critic note in the current pass, the default is to **honor the conviction**: keep the position, document the disagreement in `changelog.md` as `Resolution: declined — see prior conviction at <anchor>`, and carry the conviction forward into the v{N+1} `_convictions.md` (see step 9.5). The next reviewer pass can still override.
   - If the conviction's named anchor no longer exists in the prior `memo.md` (or will be removed by the planned revision), the conviction is **stale**: drop it. Do not carry stale convictions forward.
   - If no prior `_convictions.md` exists, this step is a no-op. The file is optional and advisory — its absence is normal.

   See SKILL.md §Convictions ledger for the full contract (advisory only, not scored, not gating, no state-machine impact).
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
9.5. **Write `_convictions.md`** at `<thread>.{N+1}/_convictions.md` (optional, advisory): record positions in the just-produced v{N+1} `memo.md` that have either (a) survived an explicit critic challenge in the current or any prior pass, or (b) survived an explicit reviser decision (typically a `Resolution: declined` row in this or a prior `changelog.md`). Each entry MUST name a body anchor — a section heading or paragraph reference — in the current v{N+1} `memo.md` (e.g., "§Risks ¶3"). A conviction without a current-version anchor is automatically stale and must not be written.

   Carry forward surviving entries from `<thread>.{N}/_convictions.md` (read in step 7.5) whose anchors still resolve against the v{N+1} `memo.md`, rewriting the anchor if the section was renamed. Add new entries for positions newly contested-and-held in this revision pass (look at the `Resolution: declined` rows of the changelog you just wrote — each is a candidate).

   The file is free-form prose; one short paragraph per entry is the documented shape. If there are no contested-and-held positions to record (a normal outcome — many revisions produce no convictions), skip the file entirely. Absence is fully normal. See SKILL.md §Convictions ledger for the full contract; see `templates/BRIEF.migration.md.example` §Convictions for a shape example.

   **Advisory only.** This file is not scored, not gating, has no state-machine impact, and is read only by the next `memo-revise` invocation. The reviewer does not read it. The auditor does not read it.
9.7. **Invoke `memo-render` (optional, non-blocking)**: after the revised `memo.md`, `changelog.md`, and (optional) `_convictions.md` are written, invoke `memo-render <thread>` to render the revised `memo.md` → `memo.pdf` and write the render-gate findings into `<thread>.{N+1}/_progress.json.phases.render` + `_progress.json.render_gate`. This step is the lifecycle wiring shipped by Epic #158 Phase 3 (issue #190).

   **Non-blocking by design.** A missing renderer, a render-gate finding, or a hard pandoc failure does NOT abort `memo-revise`. The reviser still reports `Revised <thread>.{N} → <thread>.{N+1}/...` per step 11. The render outcome is recorded in `_progress.json` for the operator to surface and for the Phase 4 reviewer to read in `_summary.md.render_gate`.

   **What this preserves.** Render is a **sub-step of `REVISED`**, NOT a new state — SKILL.md §"State machine" still derives `REVISED` from the presence of `<thread>.{N+1}/` after a prior review. A `<thread>.{N+1}/` with `phases.revise == done` but no `phases.render` block is a fully legal `REVISED` state (every memo version revised before Epic #158 / Phase 3 has this shape). This step is additive and backwards-compat.

   **When to skip the call.** Two cases:
   - If `memo-render` is not on PATH (consumer hasn't installed Anvil's Phase 3 commands yet), the reviser silently skips this step.
   - If the consumer has explicitly disabled rendering via `<thread>/.anvil.json` `{"render": "skip"}` (a future config knob — NOT shipped in Phase 3), skip the call.

   See `commands/memo-render.md` §"Failure modes" and §"Composability with `memo-draft` and `memo-revise`".
10. **Update `_progress.json`**: `phases.revise.state = done`, `phases.revise.completed = <ISO>`.
11. **Report**: print the path to the new version dir and a one-line status (e.g., `Revised acme-seed.1 → acme-seed.2/ (addressed 7 notes, declined 1)`). When `metadata.revision_mode == "polish"`, include the `polish pass` annotation, e.g., `Revised acme-seed.4 → acme-seed.5/ (polish pass; addressed 6 notes, declined 0)`. The polish-pass tag in the status line is the cheap operator signal that the run took the `--polish` bypass; it complements the on-disk `_progress.json.metadata.revision_mode` audit trail.

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

`metadata.revision_mode` is `"normal"` (default) or `"polish"` (when invoked with `--polish "<reason>"`). Absence of the field is tolerated by readers and treated as `"normal"` — every pre-this-change memo version dir omits this field, and downstream consumers MUST handle that case. `metadata.revise_force_reason` is `null` (or absent) on the default path; the verbatim operator-supplied reason string when `--polish` was used. Both fields are skill-specific extensions to the `_progress.json` schema and are preserved by the shallow-merge rule per `anvil/lib/snippets/progress.md`. **These fields are audit-trail only — not scored, not gating, not state-machine inputs.** The reviewer does NOT read `revision_mode` or `revise_force_reason` and does NOT special-case the polish pass; it scores the polished version on its own rubric merits.
