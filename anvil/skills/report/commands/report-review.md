---
name: report-review
description: Reviewer command for the report skill. Scores the latest report version against the 8-dimension /40 rubric (≥35 advance threshold) and writes a read-only review sibling directory.
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
- **Rubric**: `anvil/skills/report/rubric.md` (8 dimensions, /40, ≥35 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/report/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<project>/<thread>.{N}.review/
  verdict.md       Top-level decision + total /40 + critical flags + top revision priorities
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to report.md headings or excerpts
  _meta.json       { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state for the reviewer (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/report.md`. If `<thread>.{N}.review/_progress.json.review.state == done` and `verdict.md` exists, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`** for the review dir: `phases.review.state = in_progress`, `phases.review.started = <ISO>`, `for_version = N` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`).
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

5. **Score each dimension** (1–8 per rubric, /40 total, customer-facing weights):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (heading, excerpt, exhibit) from the report.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.
   - **Dimension 7 cap from step 4c**: if step 4c emitted a finding (missing or stale `report.pdf`), Dimension 7's score is capped at 2/4 regardless of the markdown-source assessment. The justification must reference the step 4c finding.
6. **Identify critical flags** (review-side; see `rubric.md` for the list and definitions):
   - Recommendation contradicts a finding
   - Named third party mischaracterized
   - Legal/compliance statement without disclaimer
   - Scope creep beyond engagement (compare report content against the scope declared in `_project.md` and any `BRIEF.md` scope field)

   AND the open-ended "any other issue that would cause a sophisticated recipient to lose confidence" instruction. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 35) AND (no critical flags)`.
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to report sections — heading reference + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`).
9. **Write `verdict.md`** in the format specified in `rubric.md`:
   - Total: `XX / 40`
   - Decision: `advance: true` or `advance: false`
   - Critical flags (if any) with justification
   - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
   - Top 3 revision priorities (if `advance: false`)
10. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
11. **Report**: print the path to the review dir and a one-line status (e.g., `Reviewed acme-q2/findings.1 → acme-q2/findings.1.review/ (33/40, advance: false, 0 critical flags)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output. Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Parallel-with-audit semantics

This command makes NO attempt to coordinate with `report-audit`. Both commands read the same `<thread>.{N}/` version dir; they write to disjoint sibling paths (`.review/` vs `.audit/`); neither reads the other's output. The portfolio orchestrator (and `report-revise`) is the component that aggregates both critic outputs.

This is the canonical "N parallel critics, one reviser" pattern — `report-review` is one of the N critics; `report-audit` is another.

## Notes for the reviewer agent

- **You are reviewing for the named recipient.** Load `_project.md` first. The recipient identity changes what "audience calibration" means — score dimension 8 against THAT recipient, not against a generic professional reader.
- **Be honest, not encouraging.** The skill is not "polish the report." The threshold is ≥35/40 — a tight tolerance for customer-facing material. Most first drafts of customer reports score 28–33; that is normal and informative, not a failure of the drafter.
- **Distinguish style from substance.** Stylistic improvements live in `comments.md` at severity `nit` or `minor`. They should NOT drive critical flags. Critical flags are for substantive defects (mischaracterizations, contradictions, scope violations, missing disclaimers).
- **Cross-reference with `_project.md`.** The reviewer's job is partly to confirm the report addresses the engagement scope declared in the project context. Scope creep is a critical flag.
- **Defer factual auditing to the auditor sibling.** This command does NOT walk citation chains or check numeric consistency — that is `report-audit`'s job. Note "possibly factual issue here, deferring to auditor" in comments rather than scoring it.

## `_progress.json` snippet (review sibling)

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

The review sibling's `_progress.json` includes a `for_version` field naming the version it reviews. Merge rule (shallow): preserve fields not touched by this command.
