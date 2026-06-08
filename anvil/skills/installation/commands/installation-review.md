---
name: installation-review
description: Reviewer command for the installation skill. Scores the latest proposal version against the 9-dimension /44 rubric and writes a read-only review sibling directory.
---

# installation-review — Reviewer

**Role**: reviewer.
**Reads**: latest `<thread>.{N}/` (specifically `installation.tex` and any `figures/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/installation.tex` existing.
- **Rubric**: `anvil/skills/installation/rubric.md` (9 dimensions, /44, ≥35 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/installation/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<thread>.{N}.review/
  verdict.md       Top-level decision + total /44 + critical flags + top revision priorities
                   (carries `## Rubric version transition` subsection when prior rubric differs)
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to installation.tex sections or excerpts
  _summary.md      JSON-in-markdown scorecard carrying the top-level `rubric` block + dimensions.
                   The `rubric` block lets aggregators compare scores across rubric migrations
                   without re-reading `rubric.md`.
  _meta.json       { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version, rubric_id, rubric_total, advance_threshold }
  _progress.json   Phase state for the reviewer (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/installation.tex`. If `<thread>.{N}.review/_progress.json.review.state == done` and `verdict.md` exists, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`** for the review dir: `phases.review.state = in_progress`, `phases.review.started = <ISO>` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict`, `rubric_id: "anvil-installation-v2"`, `rubric_total: 44`, and `advance_threshold: 35` (see `anvil/lib/snippets/scorecard_kind.md` §"The discriminator" — the three rubric-stamping fields are required for new reviews per issue #346; `"anvil-installation-v2"` is the installation skill's current /44 rubric identifier per `anvil/skills/installation/rubric.md` line 3). The rubric-stamping fields let downstream consumers compare scores apples-to-apples across the `/40 → /44` migration without re-reading the skill's current `rubric.md`. Also load the **prior review sibling** at `<thread>.{N-1}.review/_meta.json` when present and cache its `rubric_id` value as `prior_rubric_id` (or `None` when the prior sibling is absent — first iteration — or lacks the field — legacy pre-#346 review). The cached `prior_rubric_id` feeds the `_summary.md.rubric` block at step 9 + the `verdict.md` rubric-transition subsection (step 9b) when the prior rubric differs from the current `"anvil-installation-v2"`.
4. **Read inputs**: load `<thread>.{N}/installation.tex`, enumerate `figures/`, load `rubric.md` and any consumer override.
4b. **Run render-gate (pre-flight)** — mirrors `deck-review.md` step 5b:
   - Invoke `anvil/lib/render_gate.py`'s `compile_and_gate(...)` against `<thread>.{N}/installation.tex` with `engine="xelatex"`. Mirror the `marp_lint.py` integration shape used in `deck-review.md` step 5b (a deterministic pre-flight that emits a typed `Review` with `kind=tool_evidence` plus a sibling `_gate.json` for CI inspection — see `anvil/lib/render_gate.py` module docstring).
   - **Inputs:**
     - `tex_path`: `<thread>.{N}/installation.tex`.
     - `engine`: `"xelatex"` (matches `installation-figures.md` and the `anvil-uspto`-style fontspec-using `anvil-installation.cls`).
     - `extra_source_paths`: any `\input`/`\include` children (none in the default skeleton, but consumer overrides may add them).
     - `page_cap=None` — installation proposals can run long (site studies, 20+ pages); the generic gate does not enforce a cap. Consumers can override per-thread via `<thread>/.anvil.json: render_gate.page_cap`.
     - `overfull_threshold_pt=5.0`, `placeholder_patterns=None` (use `DEFAULT_PLACEHOLDER_PATTERNS`).
   - **First-compile semantics**: this is the *first* command in the installation lifecycle to invoke the LaTeX compiler — no upstream command produces `installation.pdf`. The gate triggers `xelatex` and gates the resulting PDF + log in one step (`compile_and_gate`). On engine-unavailable (xelatex not on PATH), the gate degrades gracefully with `compile_status="unavailable"`; the review proceeds without enforcement and the rest of the pipeline remains usable on stock CI without LaTeX installed.
   - Write the `GateResult.to_json()` payload to `<thread>.{N}.review/_gate.json` for CI inspection.
   - On failure, the gate's `to_review(...)` Review carries one `CriticalFlag` per failed gate dimension (type prefix: `render_gate_<dim>`); the aggregator (`anvil/lib/critics.py::compute_verdict`) treats this as `BLOCK` per the standard path. No schema change needed.

5. **Score each dimension** (1–9 per rubric):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (section heading, excerpt, figure) from the proposal.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.
   - **Rhetorical economy (D9)**: orthogonal to dim 8 *Open decisions*. Dim 9 asks "is every paragraph load-bearing? Could the same argument land in fewer words?" — common failure modes for concept proposals: a sensory-vocabulary section that catalogues 12 materials when 3 anchor the argument; a precedents section that lists 8 references where 2 carry the lineage; a fabrication section that quotes vendor specs verbatim. A curator or fabricator should be able to extract the argument and the build in 5 minutes.
6. **Identify critical flags**: review the proposal against the 3 example flags in `rubric.md` (*unbuildable as specified* · *safety/consent hazard unaddressed* · *concept incoherent / premise not legible*) AND the open-ended "any issue that means the proposal cannot proceed as specified" instruction. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 35) AND (no critical flags)`.

   **Append `score_history` row with `rubric_id` (issue #346)**: the orchestrator (the command that drives review→revise iterations) appends one row to `<thread>.{N}/_progress.json.metadata.score_history` per finished review iteration. Per `anvil/lib/snippets/progress.md` §"Convergence fields → score_history", the canonical row shape is `{iteration, total, threshold, rubric_id}` — for the installation skill at /44, that's `{iteration: <N>, total: <computed-total>, threshold: 35, rubric_id: "anvil-installation-v2"}`. A thread that spans the `/40 → /44` migration records different `rubric_id` values across its rows; readers tolerate rows missing `rubric_id` per the backwards-compat contract (treat as `"unknown/legacy"`). See `convergence.check_stable` for the precedent on `None`-tolerance.
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to proposal sections — heading reference + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`).
9. **Write `verdict.md`** in the format specified in `rubric.md`:
   - Total: `XX / 44`
   - Decision: `advance: true` or `advance: false`
   - Critical flags (if any)
   - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
   - Top 3 revision priorities (if `advance: false`)

   **Also write `_summary.md` with the top-level `rubric` block (issue #346)**: emit a JSON-in-markdown `_summary.md` carrying at minimum the `rubric` block — the rubric the reviewer scored against, so a downstream consumer aggregating across versions does not need to walk back to `anvil/skills/installation/rubric.md` (which may have changed between v3 and v5 of a long thread that spanned the `/40 → /44` migration). Shape:

   ```markdown
   # Review summary

   ```json
   {
     "critic": "review",
     "for_version": <N>,
     "rubric": {
       "id": "anvil-installation-v2",
       "total": 44,
       "advance_threshold": 35,
       "dimensions": 9,
       "prior_rubric_id": "anvil-installation-v1"
     }
   }
   ```
   ```

   The `rubric` block fields:
   - `id` (`str`): the rubric identifier — `"anvil-installation-v2"` for the current /44 rubric. Mirrors `_meta.json.rubric_id`.
   - `total` (`int`): the rubric's declared `total` — `44`.
   - `advance_threshold` (`int`): the rubric's declared advance threshold — `35`.
   - `dimensions` (`int`): the count of weighted dimensions — `9`.
   - `prior_rubric_id` (`str | null`, conditional): present when the prior review sibling at `<thread>.{N-1}.review/` exists. Value is the prior `_meta.json.rubric_id` when present, or `null` when the prior sibling lacks the field (legacy pre-#346 review). **Omitted entirely** on the first iteration (no prior review sibling exists).
   - `prior_rubric_inferred` (`str`, conditional): present when `prior_rubric_id == null` AND a prior review sibling exists. Value is `"/40-legacy"` to signal "this thread's prior iteration was scored against the pre-#346 /40 rubric (whatever the skill shipped at the time)".

   The block is **observational only** — it does NOT affect verdict, critical flags, or `advance`. Backwards-compat: a legacy review sibling produced before issue #346 MAY omit `_summary.md` entirely; downstream consumers MUST tolerate the absence.

9b. **Emit rubric-version-transition subsection in `verdict.md` when the prior rubric differs (issue #346)**: when the cached `prior_rubric_id` from step 3 is non-`None` AND differs from the current `"anvil-installation-v2"`, OR when `prior_rubric_id == None` AND a prior review sibling exists (legacy pre-#346 review), append a `## Rubric version transition` subsection to `verdict.md` (the installation skill does not emit a separate `findings.md`; the verdict file is the canonical home for cross-section observations). The subsection's purpose is **operator visibility** — it surfaces, in plain prose, the fact that this iteration's score is NOT directly comparable to the prior iteration's score (the threshold pool changed, the dimension count changed, weighted contributions shifted) so an operator reading the score-delta numbers does not silently mis-judge. Three shapes:

   When the prior rubric is a different stamped id (e.g., post-#346 thread that started with one rubric and the skill ships a new one — rare but possible):
   ```
   ## Rubric version transition

   This iteration was scored against `anvil-installation-v2` (/44, ≥35); the prior iteration at `<thread>.{N-1}.review/` was scored against `anvil-installation-v1` (/40, ≥32). The score delta `<prior_total>/40 → <current_total>/44` is NOT directly comparable — the threshold pool, dimension count, and weighted contributions all changed. A downstream consumer reading the delta SHOULD treat the prior score as advisory only and re-anchor on the current iteration's `<current_total>/44` against the `≥35/44` threshold.
   ```

   When the prior rubric is legacy (no `rubric_id` stamped):
   ```
   ## Rubric version transition

   This iteration was scored against `anvil-installation-v2` (/44, ≥35); the prior iteration at `<thread>.{N-1}.review/` predates per-review rubric version stamping (issue #346) and was scored against `/40-legacy` — the rubric this skill shipped before the `/40 → /44` migration (likely `anvil-installation-v1`, /40, ≥32). The score delta `<prior_total>/40-legacy → <current_total>/44` is NOT directly comparable — the threshold pool, dimension count, and weighted contributions all changed. A downstream consumer reading the delta SHOULD treat the prior score as advisory only and re-anchor on the current iteration's `<current_total>/44` against the `≥35/44` threshold.
   ```

   When the prior rubric matches the current rubric (the steady-state case — no transition surfaced):
   ```
   (subsection omitted entirely)
   ```

   The subsection is **observational** — it does NOT affect the verdict, the critical-flag list, or the `advance` decision. It is purely audit-trail prose so the operator's mental model stays calibrated across a rubric migration. Backwards-compat: a legacy review sibling produced before this contract shipped does NOT need to be re-emitted.
10. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
11. **Report**: print the path to the review dir and a one-line status (e.g., `Reviewed quiet-place.1 → quiet-place.1.review/ (33/44, advance: false, 0 critical flags)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output. Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Notes for the reviewer agent

- **Be honest**, not encouraging. The skill is not "polish the proposal." It is "would this piece, as specified, actually stand up — conceptually, spatially, and as a built object?" If the answer is no, score accordingly.
- **Distinguish description from design.** A piece that *describes* an evocative space but never gives its geometry, circulation, or dimensions has not resolved Dimension 2. This is the most common reason for a low Spatial / architectural resolution score — the equivalent of a memo's "assertion dressed as research."
- **Consent and safety are design, not waivers.** For participatory work, a missing or hand-waved consent/safety section is a candidate critical flag, not a minor note.
- **Critical flags are not bonus points.** They are statements that the proposal has a defect serious enough that it cannot proceed as drawn. Use sparingly but use them when warranted.
- **Comments should be actionable.** "Make the space more compelling" is not useful. "Give the central chamber an interior diameter and a clearance for two seated visitors; the experience claim depends on dimensions you have not stated" is useful.

## `_progress.json` and `_meta.json` snippets (review sibling)

This command writes the critic-sibling shape documented in `anvil/lib/snippets/progress.md` (with `for_version` naming the version reviewed). Specifically:

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "review": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

And the companion `_meta.json` declaring the scorecard kind (see `anvil/lib/snippets/scorecard_kind.md`):

```json
{
  "critic": "review",
  "role": "installation-review.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict",
  "rubric_id": "anvil-installation-v2",
  "rubric_total": 44,
  "advance_threshold": 35
}
```

The three `rubric_*` / `advance_threshold` fields are required for new reviews (post-issue #346) and absent-tolerated for legacy reviews. They let downstream consumers compare scores apples-to-apples across rubric migrations without re-reading the skill's current `rubric.md`.

Merge rule (shallow): preserve fields not touched by this command. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
