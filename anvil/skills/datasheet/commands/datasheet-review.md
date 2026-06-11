---
name: datasheet-review
description: Reviewer command for the datasheet skill. Runs the deterministic pre-flight (render gate + pin-map + bus-width), scores the latest version against the 9-dimension /44 rubric (threshold 39), and writes a read-only review sibling. Runs in parallel with datasheet-audit; both are required to advance.
---

# datasheet-review — Reviewer

**Role**: reviewer (`kind: judgment`, with a deterministic `tool_evidence` pre-flight).
**Reads**: latest `<thread>/<thread>.{N}/` (specifically `datasheet.tex` and any `figures/`).
**Writes**: `<thread>/<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, `_gate.json`, `_meta.json`, and `_progress.json`. Bare `<thread>.{N}/` references below are shorthand for these nested paths.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

This is one of the **two REQUIRED critic siblings** for the datasheet skill (the other is `datasheet-audit`). Both must complete before a thread can leave `DRAFTED`. They run in parallel — this command makes NO attempt to coordinate with `datasheet-audit`; both read the same `<thread>.{N}/` and write to disjoint sibling paths.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/datasheet.tex` under the thread root.
- **`status`**: read from the thread-level brief frontmatter (default `preliminary`). Calibrates dims 4 and 8 per `rubric.md`.
- **Rubric**: `anvil/skills/datasheet/rubric.md` (`anvil-datasheet-v1`: 9 dimensions, /44, **≥39** threshold, five critical flags).
- **Optional consumer override**: `.anvil/skills/datasheet/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<thread>.{N}.review/
  verdict.md       Decision + total /44 + critical flags + pre-flight summary + top revision priorities
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to datasheet.tex sections or excerpts
  _gate.json       Render-gate payload + pin-map/bus-width check results
  _meta.json       { critic, scorecard_kind: "human-verdict", rubric_id: "anvil-datasheet-v1",
                     rubric_total: 44, advance_threshold: 39, started, finished, model, schema_version }
  _progress.json   Phase state for the reviewer (phase: review, for_version: N)
```

**Atomicity**: the review sibling is written atomically via `anvil/lib/sidecar.py::staged_sidecar`. The required files (`verdict.md`, `scoring.md`, `comments.md`, `_meta.json`, `_progress.json`) are staged under `.<thread>.{N}.review.tmp/`; on clean completion the staging dir is renamed (one atomic `Path.rename`) to `<thread>.{N}.review/`. The optional `_gate.json` is written inside the staging dir but is NOT in the required-files manifest. A mid-cycle interrupt leaves a staging dir the next invocation's `cleanup_one_staging(<thread>.{N}.review)` sweep removes.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/datasheet.tex`. Sweep a stale staging dir from a prior interrupt of THIS critic on THIS version via `anvil/lib/sidecar.py::cleanup_one_staging(<thread>.{N}.review)` — sibling critics' in-flight staging dirs are NOT touched. If `<thread>.{N}.review/` exists, the review is complete — exit early with a notice (idempotent).
2. **Open the staged sidecar**: `staged_sidecar(final_dir=<thread>.{N}.review, required_files=["verdict.md", "scoring.md", "comments.md", "_meta.json", "_progress.json"])`. Every file write below lands inside the yielded staging directory. Inside it, initialize `_progress.json` (`phases.review.state = in_progress`, `for_version = N`) and `_meta.json` with `scorecard_kind: "human-verdict"` plus the three **rubric version stamping fields** required since v0.4.0 (`anvil/lib/snippets/scorecard_kind.md`): `rubric_id: "anvil-datasheet-v1"`, `rubric_total: 44`, `advance_threshold: 39`.
3. **Read inputs**: load `<thread>.{N}/datasheet.tex`, enumerate `figures/`, read `status` from the brief, load `rubric.md` and any consumer override. Note (do not walk) the presence of spec-bundle materials in `<thread>/refs/` — the per-claim back-check is **audit-owned** (`datasheet-audit` steps 5–6); the reviewer's dim 1 justification acknowledges audit ownership when the bundle is present.
4. **Run the deterministic pre-flight** — three mechanical checks BEFORE the content review:
   - **4a. Render gate**: invoke `anvil/lib/render_gate.py::compile_and_gate(tex_path=<thread>.{N}/datasheet.tex, engine="xelatex", page_cap=None, overfull_threshold_pt=5.0)`. This is the first command in the lifecycle to invoke the LaTeX compiler. On engine-unavailable (`compile_status="unavailable"`), the gate degrades gracefully and the review proceeds without enforcement.
   - **4b. Pin-map check**: run `anvil/skills/datasheet/lib/pinmap_check.py::check_pinmap(<tex source>)`. Violations (double-assigned pin, unassigned pin, count mismatch) are **critical flag 2** candidates. `found=False` (no markers) is a dim 2 deduction on a skill-authored sheet (the sheet opted out of its own integrity checks), not a flag.
   - **4c. Bus-width check**: run `anvil/skills/datasheet/lib/buswidth_check.py::check_buswidths(<tex source>)`. A declaration whose `2^width` cannot cover its claimed `max`/`range`/`values` is a **critical flag 2** candidate.
   - Write the combined payload to `_gate.json` inside the staging dir: the `GateResult.to_json()` output under a `"render_gate"` key, plus `"pinmap"` and `"buswidth"` keys carrying each checker's result dict (`found`, `violations`, `passed`). On any gate failure, record one critical flag per failed dimension in `verdict.md` — the standard `compute_verdict` path treats critical flags as `BLOCK`.
5. **Score each dimension** (1–9 per `rubric.md`): assign an integer between 0 and the dimension's weight with a 1–3 sentence justification citing specific evidence (section heading, table, excerpt). Record in `scoring.md` as a table with columns `# | Dimension | Weight | Score | Justification`. Calibration notes:
   - **Dim 2** incorporates the pre-flight results: mechanical violations from 4b/4c land here (plus the flag), and the reviewer ALSO scores the judgment half — cross-section agreement of repeated quantities (family table vs package section vs first-page header).
   - **Dim 4** is read through `status` per `rubric.md` §"Dim 4 — measured-vs-projected calibration"; note the status used in the justification.
   - **Dim 7** uses the pre-flight's render result where available (compiled PDF page breaks, overfull boxes) plus layout judgment (two-column first page present, fresh-page sections, footer consistency).
   - **Dim 9** penalizes prose that restates tables and marketing filler — a datasheet is a reference document.
6. **Identify critical flags**: review against the rubric's five named flags AND the open-ended "cannot go to a customer as specified" instruction. The reviewer co-owns **flag 4** (pre-silicon value presented as final — visible from the text alone) and raises flag 2 when the pre-flight found violations; flags 1, 3, and 5 are audit-owned but flag them here too if obvious from the text alone. One-paragraph justification per flag in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 39) AND (no critical flags)`. Append one row to `<thread>.{N}/_progress.json.metadata.score_history` per `anvil/lib/snippets/progress.md` §"Convergence fields": `{iteration: N, total: <total>, threshold: 39, rubric_id: "anvil-datasheet-v1"}`.
8. **Write line-level comments** in `comments.md`, keyed to sections — heading reference + short excerpt + comment, grouped by severity (`blocker` / `major` / `minor` / `nit`).
9. **Write `verdict.md`** in the format specified in `rubric.md` §"Verdict format": total, decision, critical flags, pre-flight summary (one line each for render gate / pin-map / bus-width), dimension summary table, top 3 revision priorities (if blocking).
10. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>` — the LAST write before the context manager exits. Exiting the `staged_sidecar` block verifies the manifest and atomically renames the staging dir to `<thread>.{N}.review/`.
11. **Report**: print the path and a one-line status (e.g., `Reviewed ax101-objdet.1 → ax101-objdet.1.review/ (37/44, advance: false, 1 critical flag [pinmap: pin 12 double-assigned])`).

## Idempotence and resumability

- A completed review (`<thread>.{N}.review/` exists — the atomic-rename contract guarantees completeness) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review leaves only a `.tmp` staging dir, removed by the step 1 sweep on the next run.

## Notes for the reviewer agent

- **You are the judgment critic, not the auditor.** Spec back-checking against `refs/` belongs to `datasheet-audit`; do not duplicate the per-claim walk — but DO flag an obvious internal contradiction (the family table says QFN48, the package section draws a QFN56) when you see one.
- **Run the mechanical checks first, always.** The pre-flight is cheap and catches the exact failures the canary hit by hand. A review that scores prose while the pinout double-assigns a power pin has failed at its job.
- **The threshold is 39, not 35.** A datasheet is the purest customer-facing artifact in anvil; "pretty good" is a blocked sheet.
- **Comments should be actionable.** "Tighten the description" is not useful. "§1 General Description ¶2 restates the Key Features list verbatim — cut it; the table is the reference" is useful.

## `_meta.json` snippet (review sibling)

```json
{
  "critic": "review",
  "role": "datasheet-review.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict",
  "rubric_id": "anvil-datasheet-v1",
  "rubric_total": 44,
  "advance_threshold": 39
}
```

The three `rubric_*` / `advance_threshold` fields are required for new reviews (v0.4.0 per-review version stamping contract). Merge rule (shallow): preserve fields not touched by this command. ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
