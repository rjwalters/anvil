---
name: report-review
description: Reviewer command for the report skill. Scores the latest report version against the 9-dimension /44 rubric (≥39 advance threshold) and writes a read-only review sibling directory.
---

# report-review — Reviewer

**Role**: reviewer.
**Reads**: `<project>/_project.md`, latest `<project>/<thread>.{N}/` (specifically `report.md` and any `exhibits/`).
**Writes**: `<project>/<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

This command is one of the two REQUIRED critic siblings for the report skill. The other is `report-audit`. Both must complete before a thread can leave the `DRAFTED` state. They run in parallel (independent inputs to the version dir, disjoint outputs).

## Inputs

- **Project + thread path** (positional argument): `<project>/<thread>`.
- **Project context**: `<project>/_project.md` — recipient, engagement_id, voice_notes, confidentiality_class. The reviewer uses these to score tone & audience calibration (dimension 8) and to gauge appropriateness against the engagement scope.
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/report.md` existing.
- **Rubric**: `anvil/skills/report/rubric.md` (9 dimensions, /44, ≥39 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/report/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).
- **Optional `--rescore-mode <rescore-id>` flag** (issue #368): when set, the reviewer re-routes its staged_sidecar output from `<thread>.{N}.review/` to `<thread>.{N}.review.rescore-<rescore-id>/`, re-targets the prior-review lookup to `<thread>.{N}.review/` (NOT `<thread>.{N-1}.review/`) since the current version's legacy review IS the prior review for a rescore pass, and stamps `_meta.json` with `rescore_state: "completed"` + `rescore_id: "<rescore-id>"` (overwriting any placeholder `rescore_state: "scheduled"` left behind by `anvil:rubric-rebackport --rescore --apply`). When the flag is unset, behavior is byte-identical to the default review path. See step 3 for the full re-routing contract.

## Outputs

```
<project>/<thread>.{N}.review/
  verdict.md       Top-level decision + total /44 + critical flags + top revision priorities
                   (carries `## Rubric version transition` subsection when prior rubric differs)
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to report.md headings or excerpts
  _summary.md      JSON-in-markdown scorecard carrying the top-level `rubric` block + dimensions.
                   The `rubric` block lets aggregators compare scores across rubric migrations
                   without re-reading `rubric.md`.
  _meta.json       { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version, rubric_id, rubric_total, advance_threshold }
  _progress.json   Phase state for the reviewer (phase: review)
```

**Atomicity** (issue #350): the review sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The required files (`verdict.md`, `scoring.md`, `comments.md`, `_summary.md`, `_meta.json`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.review.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.review/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.review.tmp/` dir on disk that the next invocation's `cleanup_stale_staging` sweep removes; the final-named dir never exists in partial form. Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob. The optional `_gate.json` is written inside the staging dir but is NOT in the required-files manifest (it is a conditional output).

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/report.md`. Then **sweep stale staging dirs from prior interrupts** by invoking `anvil/lib/sidecar.py::cleanup_stale_staging(<portfolio_root>)` where `<portfolio_root>` is the directory that contains `<thread>.{N}/`. This removes any leftover `.<thread>.<M>.review.tmp/` (and other `.<...>.tmp/`) shapes left behind by a previously-killed reviewer session (issue #350). If `<thread>.{N}.review/` exists (the atomic-rename contract guarantees the dir only exists when complete), the review is complete — exit early with a notice (idempotent).
2. **Resume check**: per the staged-sidecar shape introduced in issue #350, a partial review left behind by a mid-cycle interrupt manifests as a leading-dot `.<thread>.{N}.review.tmp/` directory; the step 1 sweep has already removed it. Backwards-compat: if a legacy pre-#350 `<thread>.{N}.review/` exists WITHOUT `verdict.md`, delete the dir and re-review.
3. **Open the staged sidecar** for the review dir by invoking the context manager `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.review, required_files=["verdict.md", "scoring.md", "comments.md", "_summary.md", "_meta.json", "_progress.json"])`. Every file write from this step through the final `_progress.json` update MUST land **inside the yielded staging directory** (the path of the shape `.<thread>.{N}.review.tmp/`), NOT inside the final `<thread>.{N}.review/` path. On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name (issue #350). Then, **inside the staging dir**, initialize `_progress.json`: `phases.review.state = in_progress`, `phases.review.started = <ISO>`, `for_version = N` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict`, `rubric_id: "anvil-report-v2"`, `rubric_total: 44`, and `advance_threshold: 39` (see `anvil/lib/snippets/scorecard_kind.md` §"The discriminator" — the three rubric-stamping fields are required for new reviews per issue #346; `"anvil-report-v2"` is the report skill's current /44 rubric identifier per `anvil/skills/report/rubric.md` line 3). The rubric-stamping fields let downstream consumers compare scores apples-to-apples across the `/40 → /44` migration without re-reading the skill's current `rubric.md`. Also load the **prior review sibling** at `<thread>.{N-1}.review/_meta.json` when present and cache its `rubric_id` value as `prior_rubric_id` (or `None` when the prior sibling is absent — first iteration — or lacks the field — legacy pre-#346 review). The cached `prior_rubric_id` feeds the `_summary.md.rubric` block at step 9 + the `verdict.md` rubric-transition subsection (step 9b) when the prior rubric differs from the current `"anvil-report-v2"`.

   **When `--rescore-mode <rescore-id>` is set** (issue #368) — the rebackport reviewer-hook contract:
   - **Re-derive `final_dir`** from `<thread>.{N}.review` to `<thread>.{N}.review.rescore-<rescore-id>`. The staging directory derived by `anvil/lib/sidecar.py::staging_path_for(final_dir)` correspondingly becomes `.<thread>.{N}.review.rescore-<rescore-id>.tmp/` — no separate code path is needed; the same `staged_sidecar(final_dir=...)` call works with the rescore sidecar path.
   - **Re-target the prior-review lookup to `<thread>.{N}.review/_meta.json`** (NOT `<thread>.{N-1}.review/_meta.json`). Under rescore mode, the legacy review at `<thread>.{N}.review/` IS the prior review — the rescore is re-scoring the SAME version's body against an updated rubric, not advancing to a new version. Cache its `rubric_id` value as `prior_rubric_id` (or fall back to `--legacy-rubric` from the rebackport tool when the legacy review lacks the field — pre-#346).
   - **Stamp `_meta.json` with `rescore_state: "completed"` and `rescore_id: "<rescore-id>"`** in addition to the standard rubric-stamping fields. The placeholder `_meta.json` left behind by `anvil:rubric-rebackport --rescore --apply` carries `rescore_state: "scheduled"`; this reviewer overwrites it with `"completed"` once the full review (verdict.md / scoring.md / comments.md / _summary.md) has landed inside the staging dir. The `rescore_source: "anvil:rubric-rebackport"` field from the placeholder is preserved (or added if absent).
   - **All other behavior is unchanged** — same scoring, same verdict, same `verdict.md` transition subsection (step 9b — now carrying the legacy review's rubric as `prior_rubric_id`). The customer-facing ≥39/44 advance threshold is preserved verbatim; a rescore pass landing below threshold surfaces the gap the same way a default-mode review would, just inside the rescore sidecar. The legacy `<thread>.{N}.review/` dir is NEVER mutated — the rescore is a side-car write only.
   - **When `--rescore-mode` is unset**, the steps above DO NOT fire and the review path is byte-identical to the default behavior documented in the rest of this step.
4. **Read inputs**: load `<thread>.{N}/report.md`, enumerate `exhibits/`, load `_project.md` for recipient calibration context, load `rubric.md` and any consumer override. Also stat `<thread>.{N}/report.pdf` for the existence + freshness check in step 4c — the PDF is stat-only, its content is not read by this critic; see `report-vision` for rendered-content review.
4b. **Run render-gate (pre-flight)** — mirrors `deck-review.md` step 5b:
   - Invoke `anvil/lib/render_gate.py`'s `gate(...)` against `<thread>.{N}/report.pdf` (produced by `report-figures`; see `commands/report-figures.md`).
   - **Inputs:**
     - `pdf_path`: `<thread>.{N}/report.pdf`.
     - `log_path`: when `_project.md.delivery_format` is the LaTeX path, the compile log captured by `report-figures` at `<thread>.{N}/.report-build.log`; otherwise `None` (pandoc path produces no persistent log).
     - `source_paths`: `[<thread>.{N}/report.md]`.
     - `page_cap=None` — customer report length varies; the gate does not enforce. Consumers can override per-thread via `<thread>/.anvil.json: render_gate.page_cap`.
     - `overfull_threshold_pt=5.0`, `placeholder_patterns=None` (use `DEFAULT_PLACEHOLDER_PATTERNS`).
     - `engine`: `"pandoc"` when `_project.md.delivery_format` is the pandoc path, else the LaTeX engine name. **When `engine="pandoc"` the overfull-box check is skipped** (pandoc/CSS output has no `Overfull` semantics — the gate emits a documented note in `reasons`).
   - When `report.pdf` is absent (e.g., `report-figures` has not run), the gate fails open with a clear stdout message (`report-review: render-gate skipped — report.pdf not present; run report-figures first`). The review proceeds normally.
   - Write `GateResult.to_json()` to `<thread>.{N}.review/_gate.json` for CI inspection.
   - On failure, the gate's `to_review(...)` Review carries one `CriticalFlag` per failed gate dimension; the aggregator (`anvil/lib/critics.py`) treats this as `BLOCK` per the standard `compute_verdict` path. No schema change needed.
4c. **Verify deliverable existence + freshness** (lightweight stat-only check, complements 4b's render-gate):
   - **Why this is additive over 4b**: the render-gate from #64 (step 4b above) deliberately fails open on a missing `report.pdf` — line 50 explicitly states "the gate fails open with a clear stdout message ... The review proceeds normally." Separately, the render-gate has no concept of source/output mtime ordering — so a stale PDF (figurer ran on version N, then `report.md` was edited in-place without re-running figures) passes 4b cleanly. This check enforces existence + freshness so a report can't advance without the deliverable being built against the current source.
   - The check uses `anvil/skills/report/lib/pdf_freshness.py::check_pdf_freshness(version_dir)`. It is deterministic (file-stat only, no model call, no PDF parse).
   - **If `<thread>.{N}/report.pdf` does NOT exist**: append a Dimension 7 finding to `comments.md` with severity `major`, rationale `"Rendered deliverable not built — figurer has not run on this version (or its output was deleted). Run report-figures before review can score Dimension 7 substantively."`, evidence_span `"<thread>.{N}/report.pdf"`, suggested_fix `"Run report-figures <project>/<thread>"`. Cap Dimension 7's score at 2/4 for this version.
   - **Else if `<thread>.{N}/report.pdf` mtime is OLDER than `<thread>.{N}/report.md` mtime**: append a Dimension 7 finding with severity `major`, rationale `"Rendered deliverable is stale — report.md was modified after report.pdf was built. The PDF the recipient would see does not reflect the current source."`, evidence_span `"<thread>.{N}/report.pdf (mtime: <ISO>) older than <thread>.{N}/report.md (mtime: <ISO>)"`, suggested_fix `"Re-run report-figures to refresh the deliverable"`. Cap Dimension 7's score at 2/4.
   - **Else (PDF exists and is fresher than source)**: no finding. Dimension 7 scoring proceeds normally from the markdown source.
   - This check does NOT read PDF content — that is `report-vision`'s territory.
   - The check does NOT set a `critical_flag` — `major` severity at the rubric-cap level is the right calibration. A missing/stale PDF affects ADVANCE via the rubric total (capped Dim 7 ≤ 2/4 contributes ≤ 2 to the /40 total), not via critical-flag short-circuit. The reviewer can still substantively evaluate the markdown.

5. **Score each dimension** (1–9 per rubric, /44 total, customer-facing weights):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (heading, excerpt, exhibit) from the report.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.
   - **Dimension 7 cap from step 4c**: if step 4c emitted a finding (missing or stale `report.pdf`), Dimension 7's score is capped at 2/4 regardless of the markdown-source assessment. The justification must reference the step 4c finding.
   - **Rhetorical economy (D9)**: distinct from dim 1 *Executive summary clarity* (first-page clarity) and dim 7 *Format / presentation quality* (rendered polish). Dim 9 asks "is the WHOLE report load-bearing?" — sections that restate findings without adding evidence, appendices that quote interview transcripts verbatim where excerpts would land, recommendation lists padded with low-value items, methodology sections that pre-emptively defend against questions nobody is going to ask. Customer reports balloon under "more = more rigorous" pressure; dim 9 is the explicit countervailing pressure.
6. **Identify critical flags** (review-side; see `rubric.md` for the list and definitions):
   - Recommendation contradicts a finding
   - Named third party mischaracterized
   - Legal/compliance statement without disclaimer
   - Scope creep beyond engagement (compare report content against the scope declared in `_project.md` and any `BRIEF.md` scope field)

   AND the open-ended "any other issue that would cause a sophisticated recipient to lose confidence" instruction. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 39) AND (no critical flags)`.

   **Append `score_history` row with `rubric_id` (issue #346)**: the orchestrator (the command that drives review→revise iterations) appends one row to `<thread>.{N}/_progress.json.metadata.score_history` per finished review iteration. Per `anvil/lib/snippets/progress.md` §"Convergence fields → score_history", the canonical row shape is `{iteration, total, threshold, rubric_id}` — for the report skill at /44, that's `{iteration: <N>, total: <computed-total>, threshold: 39, rubric_id: "anvil-report-v2"}`. A thread that spans the `/40 → /44` migration records different `rubric_id` values across its rows; readers tolerate rows missing `rubric_id` per the backwards-compat contract (treat as `"unknown/legacy"`). See `convergence.check_stable` for the precedent on `None`-tolerance.
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to report sections — heading reference + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`).
9. **Write `verdict.md`** in the format specified in `rubric.md`:
   - Total: `XX / 44`
   - Decision: `advance: true` or `advance: false`
   - Critical flags (if any) with justification
   - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
   - Top 3 revision priorities (if `advance: false`)

   **Also write `_summary.md` with the top-level `rubric` block (issue #346)**: emit a JSON-in-markdown `_summary.md` carrying at minimum the `rubric` block — the rubric the reviewer scored against, so a downstream consumer aggregating across versions does not need to walk back to `anvil/skills/report/rubric.md` (which may have changed between v3 and v5 of a long thread that spanned the `/40 → /44` migration). Shape:

   ```markdown
   # Review summary

   ```json
   {
     "critic": "review",
     "for_version": <N>,
     "rubric": {
       "id": "anvil-report-v2",
       "total": 44,
       "advance_threshold": 39,
       "dimensions": 9,
       "prior_rubric_id": "anvil-report-v1"
     }
   }
   ```
   ```

   The `rubric` block fields:
   - `id` (`str`): the rubric identifier — `"anvil-report-v2"` for the current /44 rubric. Mirrors `_meta.json.rubric_id`.
   - `total` (`int`): the rubric's declared `total` — `44`.
   - `advance_threshold` (`int`): the rubric's declared advance threshold — `39`.
   - `dimensions` (`int`): the count of weighted dimensions — `9`.
   - `prior_rubric_id` (`str | null`, conditional): present when the prior review sibling at `<thread>.{N-1}.review/` exists. Value is the prior `_meta.json.rubric_id` when present, or `null` when the prior sibling lacks the field (legacy pre-#346 review). **Omitted entirely** on the first iteration (no prior review sibling exists).
   - `prior_rubric_inferred` (`str`, conditional): present when `prior_rubric_id == null` AND a prior review sibling exists. Value is `"/40-legacy"`.

   The block is **observational only** — it does NOT affect verdict, critical flags, or `advance`. Backwards-compat: a legacy review sibling produced before issue #346 MAY omit `_summary.md` entirely; downstream consumers MUST tolerate the absence.

9b. **Emit rubric-version-transition subsection in `verdict.md` when the prior rubric differs (issue #346)**: when the cached `prior_rubric_id` from step 3 is non-`None` AND differs from the current `"anvil-report-v2"`, OR when `prior_rubric_id == None` AND a prior review sibling exists (legacy pre-#346 review), append a `## Rubric version transition` subsection to `verdict.md` (the report skill does not emit a separate `findings.md`; the verdict file is the canonical home for cross-section observations per the curator's "smaller skills, less ceremony" decision). The subsection's purpose is **operator visibility** — it surfaces, in plain prose, the fact that this iteration's score is NOT directly comparable to the prior iteration's score (the threshold pool changed, the dimension count changed, weighted contributions shifted). Three shapes:

   When the prior rubric is a different stamped id:
   ```
   ## Rubric version transition

   This iteration was scored against `anvil-report-v2` (/44, ≥39); the prior iteration at `<thread>.{N-1}.review/` was scored against `anvil-report-v1` (/40, ≥35). The score delta `<prior_total>/40 → <current_total>/44` is NOT directly comparable — the threshold pool, dimension count, and weighted contributions all changed. A downstream consumer reading the delta SHOULD treat the prior score as advisory only and re-anchor on the current iteration's `<current_total>/44` against the `≥39/44` threshold.
   ```

   When the prior rubric is legacy (no `rubric_id` stamped):
   ```
   ## Rubric version transition

   This iteration was scored against `anvil-report-v2` (/44, ≥39); the prior iteration at `<thread>.{N-1}.review/` predates per-review rubric version stamping (issue #346) and was scored against `/40-legacy` — the rubric this skill shipped before the `/40 → /44` migration (likely `anvil-report-v1`, /40, ≥35). The score delta `<prior_total>/40-legacy → <current_total>/44` is NOT directly comparable — the threshold pool, dimension count, and weighted contributions all changed. A downstream consumer reading the delta SHOULD treat the prior score as advisory only and re-anchor on the current iteration's `<current_total>/44` against the `≥39/44` threshold.
   ```

   When the prior rubric matches the current rubric (the steady-state case — no transition surfaced):
   ```
   (subsection omitted entirely)
   ```

   The subsection is **observational** — it does NOT affect the verdict, the critical-flag list, or the `advance` decision. Backwards-compat: a legacy review sibling produced before this contract shipped does NOT need to be re-emitted.
10. **Update `_progress.json`** inside the staging dir: `phases.review.state = done`, `phases.review.completed = <ISO>`. This is the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires `_progress.json` to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies every name in the required-files manifest exists in the staging dir, then atomically renames `.<thread>.{N}.review.tmp/` → `<thread>.{N}.review/`. The final-named dir only ever exists in **complete** form.
11. **Report**: print the path to the (now-renamed) review dir and a one-line status (e.g., `Reviewed acme-q2/findings.1 → acme-q2/findings.1.review/ (36/44, advance: false, 0 critical flags)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output. Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Parallel-with-audit semantics

This command makes NO attempt to coordinate with `report-audit`. Both commands read the same `<thread>.{N}/` version dir; they write to disjoint sibling paths (`.review/` vs `.audit/`); neither reads the other's output. The portfolio orchestrator (and `report-revise`) is the component that aggregates both critic outputs.

This is the canonical "N parallel critics, one reviser" pattern — `report-review` is one of the N critics; `report-audit` is another.

## Notes for the reviewer agent

- **You are reviewing for the named recipient.** Load `_project.md` first. The recipient identity changes what "audience calibration" means — score dimension 8 against THAT recipient, not against a generic professional reader.
- **Be honest, not encouraging.** The skill is not "polish the report." The threshold is ≥39/44 — a tight tolerance for customer-facing material. Most first drafts of customer reports score in the low-to-mid /44 range; that is normal and informative, not a failure of the drafter.
- **Distinguish style from substance.** Stylistic improvements live in `comments.md` at severity `nit` or `minor`. They should NOT drive critical flags. Critical flags are for substantive defects (mischaracterizations, contradictions, scope violations, missing disclaimers).
- **Cross-reference with `_project.md`.** The reviewer's job is partly to confirm the report addresses the engagement scope declared in the project context. Scope creep is a critical flag.
- **Defer factual auditing to the auditor sibling.** This command does NOT walk citation chains or check numeric consistency — that is `report-audit`'s job. Note "possibly factual issue here, deferring to auditor" in comments rather than scoring it.

## `_progress.json` and `_meta.json` snippets (review sibling)

```json
{
  "version": 1,
  "thread": "<slug>",
  "project": "<project-slug>",
  "for_version": <N>,
  "phases": {
    "review": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

The review sibling's `_progress.json` includes a `for_version` field naming the version it reviews. The companion `_meta.json` declares the scorecard kind and the rubric the reviewer scored against (per `anvil/lib/snippets/scorecard_kind.md` §"The discriminator"):

```json
{
  "critic": "review",
  "role": "report-review.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict",
  "rubric_id": "anvil-report-v2",
  "rubric_total": 44,
  "advance_threshold": 39
}
```

The three `rubric_*` / `advance_threshold` fields are required for new reviews (post-issue #346) and absent-tolerated for legacy reviews. They let downstream consumers compare scores apples-to-apples across rubric migrations without re-reading the skill's current `rubric.md`.

Merge rule (shallow): preserve fields not touched by this command.
