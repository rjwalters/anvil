---
name: proposal-review
description: Reviewer command for the proposal skill. Scores the latest proposal version against the 9-dimension /44 rubric and writes a read-only review sibling directory. Runs in parallel with proposal-audit; both are required to advance.
---

# proposal-review — Reviewer

**Role**: reviewer (`kind: judgment`).
**Reads**: latest `<thread>.{N}/` (specifically `proposal.tex` and any `figures/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, `_meta.json`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

This is one of the **two REQUIRED critic siblings** for the proposal skill (the other is `proposal-audit`). Both must complete before a thread can leave the `DRAFTED` state. They run in parallel — this command makes NO attempt to coordinate with `proposal-audit`; both read the same `<thread>.{N}/` and write to disjoint sibling paths.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/proposal.tex` existing.
- **`customer_kind`**: read from the brief frontmatter (or `<thread>/.anvil.json`); default `external`. Reframes how dimension 7 is read (see below).
- **Rubric**: `anvil/skills/proposal/rubric.md` (9 dimensions, /44, ≥35 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/proposal/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<thread>.{N}.review/
  verdict.md       Top-level decision + total /44 + critical flags + top revision priorities
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to proposal.tex sections or excerpts
  _summary.md      Top-level `rubric` block (rubric the reviewer scored against) + (optionally) other machine-readable scorecard fields — see step 9b
  _meta.json       { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version, rubric_id, rubric_total, advance_threshold }
  _progress.json   Phase state for the reviewer (phase: review)
```

**Atomicity** (issue #350): the review sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The required files (`verdict.md`, `scoring.md`, `comments.md`, `_summary.md`, `_meta.json`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.review.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.review/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.review.tmp/` dir on disk that the next invocation's `cleanup_stale_staging` sweep removes; the final-named dir never exists in partial form. Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob. The optional `_gate.json` is written inside the staging dir but is NOT in the required-files manifest.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/proposal.tex`. Then **sweep stale staging dirs from prior interrupts** by invoking `anvil/lib/sidecar.py::cleanup_stale_staging(<portfolio_root>)` where `<portfolio_root>` is the directory that contains `<thread>.{N}/`. This removes any leftover `.<thread>.<M>.review.tmp/` (and other `.<...>.tmp/`) shapes left behind by a previously-killed reviewer session (issue #350). If `<thread>.{N}.review/` exists (the atomic-rename contract guarantees the dir only exists when complete), the review is complete — exit early with a notice (idempotent).
2. **Resume check**: per the staged-sidecar shape introduced in issue #350, a partial review left behind by a mid-cycle interrupt manifests as a leading-dot `.<thread>.{N}.review.tmp/` directory; the step 1 sweep has already removed it. Backwards-compat: if a legacy pre-#350 `<thread>.{N}.review/` exists WITHOUT `verdict.md`, delete the dir and re-review.
3. **Open the staged sidecar** for the review dir by invoking the context manager `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.review, required_files=["verdict.md", "scoring.md", "comments.md", "_summary.md", "_meta.json", "_progress.json"])`. Every file write below MUST land **inside the yielded staging directory** (the path of the shape `.<thread>.{N}.review.tmp/`), NOT inside the final `<thread>.{N}.review/` path. On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name (issue #350). Then, **inside the staging dir**, initialize `_progress.json` for the review dir: `phases.review.state = in_progress`, `phases.review.started = <ISO>`, `for_version = N` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict`, `rubric_id: "anvil-proposal-v2"`, `rubric_total: 44`, and `advance_threshold: 35` (see `anvil/lib/snippets/scorecard_kind.md` §"The discriminator" — the three rubric-stamping fields are required for new reviews per issue #346; `"anvil-proposal-v2"` is the proposal skill's current /44 rubric identifier per `anvil/skills/proposal/rubric.md` line 3). The rubric-stamping fields let downstream consumers compare scores apples-to-apples across the `/40 → /44` migration without re-reading the skill's current `rubric.md`. Also load the **prior review sibling** at `<thread>.{N-1}.review/_meta.json` when present and cache its `rubric_id` value as `prior_rubric_id` (or `None` when the prior sibling is absent — first iteration — or lacks the field — legacy pre-#346 review). The cached `prior_rubric_id` feeds the new top-level `rubric` block in the review sibling's metadata and the rubric-transition surfacing in `findings.md` / `comments.md` when the prior rubric differs from the current `"anvil-proposal-v2"`.
4. **Read inputs**: load `<thread>.{N}/proposal.tex`, enumerate `figures/`, read `customer_kind`, load `rubric.md` and any consumer override. **Source-of-truth materials note (issue #166)**: enumerate `<thread>/refs/` and identify any **source-of-truth materials** present per SKILL.md §"Source-of-truth materials" (files named for their content — `quote-<vendor>.{pdf,md}`, `datasheet-<part>.pdf`, `sow-*.md`, `comparables/<project>.md`, `cv-<lead>.{pdf,md}`, `site-plan-*.pdf`). The reviewer's job here is to **note their presence**, not to walk them — the per-claim refs back-check is **audit-owned** and lives in `proposal-audit` step 7 (extended to non-cost claims per the same issue). The reviewer's dim 4 (Scope completeness) justification SHOULD acknowledge that audit handles the per-claim back-check when source-of-truth materials are present (e.g., "Scope completeness scored as written; refs/sow-bigcorp.md is on-disk for audit-side scope back-check per SKILL.md §'Source-of-truth materials'"). The reviewer MUST NOT duplicate the per-claim refs back-check on the review side — the deduction lives in the audit's dim 6 sub-rule per `rubric.md` §"Refs back-check (dim 6 + dim 4)". When `refs/` contains no source-of-truth materials (or is empty), this step is a no-op and the reviewer scores dim 4 as today.
4b. **Run render-gate (pre-flight)** — mirrors `deck-review.md` step 5b:
   - Invoke `anvil/lib/render_gate.py`'s `compile_and_gate(...)` against `<thread>.{N}/proposal.tex` with `engine="xelatex"`. Mirror the `marp_lint.py` integration shape used in `deck-review.md` step 5b (a deterministic pre-flight that emits a typed `Review` with `kind=tool_evidence` plus a sibling `_gate.json` for CI inspection — see `anvil/lib/render_gate.py` module docstring).
   - **Inputs:**
     - `tex_path`: `<thread>.{N}/proposal.tex`.
     - `engine`: `"xelatex"` (matches the `anvil-proposal.cls` fontspec setup).
     - `extra_source_paths`: any `\input`/`\include` children (none in the default skeleton, but consumer overrides may add them).
     - `page_cap=None` — proposal length is customer/sponsor-dependent (a short pitch may run 4 pages; a complex build spec 20+). The generic gate does not enforce a cap. Consumers can override per-thread via `<thread>/.anvil.json: render_gate.page_cap` if a venue / client / budget reviewer has a hard limit. A recommended 4–20 pages range is documented in `SKILL.md` as guidance only.
     - `overfull_threshold_pt=5.0`, `placeholder_patterns=None` (use `DEFAULT_PLACEHOLDER_PATTERNS`).
   - **First-compile semantics**: this is the *first* command in the proposal lifecycle to invoke the LaTeX compiler — `proposal-audit` reads the source but does not compile a PDF, and `proposal-figures` runs after `READY`. The gate triggers `xelatex` and gates the resulting PDF + log in one step (`compile_and_gate`). On engine-unavailable (xelatex not on PATH), the gate degrades gracefully with `compile_status="unavailable"`; the review proceeds without enforcement and the rest of the pipeline remains usable on stock CI without LaTeX installed.
   - Write the `GateResult.to_json()` payload to `<thread>.{N}.review/_gate.json` for CI inspection.
   - On failure, the gate's `to_review(...)` Review carries one `CriticalFlag` per failed gate dimension (type prefix: `render_gate_<dim>`); the aggregator (`anvil/lib/critics.py::compute_verdict`) treats this as `BLOCK` per the standard path. No schema change needed.

5. **Score each dimension** (1–9 per rubric):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (section heading, excerpt, figure) from the proposal.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.
   - **Dimension 7 (persuasiveness / value proposition) is read through `customer_kind`**: for `external`, score "does this give the client a reason to commit money?"; for `internal`, score "does this justify the budget allocation against the alternative?" Same weight (4), reframed prompt. Note the framing you used in the justification.
6. **Identify critical flags**: review the proposal against the rubric's four named flags AND the open-ended "any issue that means the proposal cannot proceed as specified" instruction. The reviewer **owns flag 1** (*misses a stated hard constraint*) and shares flag 3 (*not deliverable as resourced*) with the auditor; flags 2 (*cost not credible/sourceable*) and 4 (*internal inconsistency*) are primarily audit-owned but flag them here too if obvious from the text alone. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 35) AND (no critical flags)`.

   **Append `score_history` row with `rubric_id` (issue #346)**: the orchestrator (the command that drives review→revise iterations) appends one row to `<thread>.{N}/_progress.json.metadata.score_history` per finished review iteration. Per `anvil/lib/snippets/progress.md` §"Convergence fields → score_history", the canonical row shape is `{iteration, total, threshold, rubric_id}` — for the proposal skill at /44, that's `{iteration: <N>, total: <computed-total>, threshold: 35, rubric_id: "anvil-proposal-v2"}`. A thread that spans the `/40 → /44` migration records different `rubric_id` values across its rows; readers tolerate rows missing `rubric_id` per the backwards-compat contract (treat as `"unknown/legacy"`).
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to proposal sections — heading reference + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`).
9. **Write `verdict.md`** in the format specified in `rubric.md`:
   - Total: `XX / 44`
   - Decision: `advance: true` or `advance: false`
   - Critical flags (if any)
   - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
   - Top 3 revision priorities (if `advance: false`)
9b. **Write `_summary.md` with the top-level `rubric` block (issue #346)**: emit a JSON-in-markdown `_summary.md` carrying at minimum the `rubric` block — the rubric the reviewer scored against, so a downstream consumer aggregating across versions does not need to walk back to `anvil/skills/proposal/rubric.md` (which may have changed between v3 and v5 of a long thread that spanned the `/40 → /44` migration). Shape:

    ```markdown
    # Review summary

    ```json
    {
      "critic": "review",
      "for_version": <N>,
      "rubric": {
        "id": "anvil-proposal-v2",
        "total": 44,
        "advance_threshold": 35,
        "dimensions": 9,
        "prior_rubric_id": "anvil-proposal-v1"
      }
    }
    ```
    ```

    The `rubric` block fields:
    - `id` (`str`): the rubric identifier — `"anvil-proposal-v2"` for the current /44 rubric. Mirrors `_meta.json.rubric_id`.
    - `total` (`int`): the rubric's declared `total` — `44`.
    - `advance_threshold` (`int`): the rubric's declared advance threshold — `35`.
    - `dimensions` (`int`): the count of weighted dimensions — `9`.
    - `prior_rubric_id` (`str | null`, conditional): present when the prior review sibling at `<thread>.{N-1}.review/` exists. Value is the prior `_meta.json.rubric_id` when present, or `null` when the prior sibling lacks the field (legacy pre-#346 review). **Omitted entirely** on the first iteration (no prior review sibling exists).
    - `prior_rubric_inferred` (`str`, conditional): present when `prior_rubric_id == null` AND a prior review sibling exists. Value is `"/40-legacy"` to signal "this thread's prior iteration was scored against the pre-#346 /40 rubric (whatever the skill shipped at the time)".

    The block is **observational only** — it does NOT affect verdict, critical flags, or `advance`. Backwards-compat: a legacy review sibling produced before issue #346 MAY omit `_summary.md` entirely; downstream consumers MUST tolerate the absence.

    **Mixed-rubric thread surfacing in `comments.md` (or `findings.md` if emitted)**: when `prior_rubric_id` is present AND differs from `"anvil-proposal-v2"`, OR when `prior_rubric_id == null` AND a prior review sibling exists, the reviewer SHOULD append a `## Rubric version transition` subsection at the bottom of `comments.md` (or in a new `findings.md` if the reviewer chooses to emit one) noting the change, e.g.:

    > **Rubric version transition.** This iteration was scored against `anvil-proposal-v2` (/44, ≥35); the prior iteration at `<thread>.{N-1}.review/` was scored against `anvil-proposal-v1` (/40, ≥32) [or `/40-legacy` for unstamped legacy]. The score delta `<prior_total>/40 → <current_total>/44` is NOT directly comparable — the threshold pool, dimension count, and weighted contributions all changed. A downstream consumer reading the delta SHOULD treat the prior score as advisory only and re-anchor on the current iteration's `<current_total>/44` against the `≥35/44` threshold.

    The subsection is purely audit-trail prose so the operator's mental model stays calibrated across a rubric migration. When the prior rubric matches the current rubric (the steady-state case), the subsection is omitted entirely.
10. **Update `_progress.json`** inside the staging dir: `phases.review.state = done`, `phases.review.completed = <ISO>`. This is the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires `_progress.json` to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies every name in the required-files manifest exists in the staging dir, then atomically renames `.<thread>.{N}.review.tmp/` → `<thread>.{N}.review/`. The final-named dir only ever exists in **complete** form.
11. **Report**: print the path to the (now-renamed) review dir and a one-line status (e.g., `Reviewed gossamer-lan.1 → gossamer-lan.1.review/ (32/44, advance: false, 0 critical flags)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output. Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Notes for the reviewer agent

- **You are the judgment critic, not the auditor.** Your job is subjective quality a strong reader can score from the text alone — is the design sound, does it meet the stated hard constraints, is the scope complete, can it plausibly be delivered, is the pitch persuasive? The *arithmetic* of the BOM and the *spec consistency* (does the link budget close? does Qty × Unit = Total?) belong to `proposal-audit` — do not duplicate that work, but DO flag an obvious contradiction if you see one.
- **Constraint satisfaction is the proposal's spine.** A proposal that does not visibly thread each stated hard constraint through the design has not earned dimension 3. If the brief said "invisible, no conduit, 10 Gbps" and the design quietly proposes surface raceway, that is critical flag 1 — not a minor note.
- **Distinguish description from design.** A proposal that *describes* an architecture but never gives the topology, the part choices, or the install method has not resolved dimension 2. This is the most common reason for a low design-correctness score.
- **Deliverability is real, not aspirational.** The "we'll figure out staffing" answer scores low on dimension 5. The proposal must show a concrete path to the tools/skills/staff — the Gossamer "fiber workshop" is the model: own the splicer and the practice spool, not a contractor's phone number.
- **Comments should be actionable.** "Make the cost section stronger" is not useful. "The BOM lists 16 transceivers but the topology has 7 spokes — state the 14 + 2 uplink derivation so the count is checkable" is useful.

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

And the companion `_meta.json` declaring the scorecard kind and the rubric the reviewer scored against (see `anvil/lib/snippets/scorecard_kind.md` §"The discriminator"):

```json
{
  "critic": "review",
  "role": "proposal-review.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict",
  "rubric_id": "anvil-proposal-v2",
  "rubric_total": 44,
  "advance_threshold": 35
}
```

The three `rubric_*` / `advance_threshold` fields are required for new reviews (post-issue #346) and absent-tolerated for legacy reviews. They let downstream consumers compare scores apples-to-apples across rubric migrations without re-reading the skill's current `rubric.md`.

Merge rule (shallow): preserve fields not touched by this command. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
