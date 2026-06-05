---
name: slides-review
description: Reviewer command for the slides skill. Scores the latest slides version against the 8-dimension /40 rubric, pulls in critical flags from audit and rehearse siblings, and writes a read-only review sibling directory.
---

# slides-review — Reviewer

**Role**: reviewer.
**Reads**: latest `<thread>.{N}/` (specifically `deck.md`, all `notes/*.md`, and any `figures/`). Also reads `<thread>.{N}.audit/verdict.md` and `<thread>.{N}.rehearse/timing.md` and `density.md` if present, to propagate critical flags.
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/deck.md` existing.
- **Rubric**: `anvil/skills/slides/rubric.md` (8 dimensions, /40, ≥32 threshold, three critical-flag rules).
- **Sibling critic outputs** (if present at the same `N`):
  - `<thread>.{N}.audit/verdict.md` — for the audit flag.
  - `<thread>.{N}.rehearse/timing.md` + `density.md` — for the time and density flags.
- **Optional consumer override**: `.anvil/skills/slides/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<thread>.{N}.review/
  verdict.md       Top-level decision + total /40 + critical flags (own + propagated) + top revision priorities
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Slide-level comments keyed to slide numbers and notes/<NN>-*.md filenames
  _summary.md      8-dim scorecard + lint block (pre-flight overflow lint output)
  findings.md      Itemized findings (severity, slide ref, rationale, suggested fix) + "Lint findings" section
  _meta.json       { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state for the reviewer (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md`. If `<thread>.{N}.review/_progress.json.review.state == done` and `verdict.md` exists, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`** for the review dir: `phases.review.state = in_progress`, `phases.review.started = <ISO>`, `for_version: <N>` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`).
4. **Read inputs**: load `<thread>.{N}/deck.md`, enumerate `notes/*.md` and `figures/`, load `rubric.md` and any consumer override.
4b. **Run pre-flight overflow lint**:
   - Invoke `anvil/lib/marp_lint.py`'s `lint_deck(<thread>.{N}/deck.md)`. This is a Python-stdlib heuristic port of marp-vscode's `slide-content-overflow` diagnostic (see the module docstring for the upstream SHA pin and the per-slide `<!-- anvil-lint-disable: slide-content-overflow -->` escape hatch).
   - The call returns a `LintResult` with `errors: list[Finding]`, `warnings: list[Finding]`, and `infos: list[Finding]`. Each `Finding` has `slide` (1-based slide number), `line` (1-based source line), `rule`, `severity`, and `message`.
   - The lint is **review-phase only** — `slides-draft`, `slides-audit`, `slides-figures`, and `slides-rehearse` do not invoke it. The drafter is intentionally allowed to produce an overflowing slide so the reviser sees the failure mode (issue #31, AC6).
   - Cache the `LintResult` for the `_summary.md` and `findings.md` writes below; cache `lint.errors > 0` as `lint_critical_flag` for the verdict logic.
5. **Read sibling critic outputs** (if present):
   - `<thread>.{N}.audit/verdict.md` — extract any `wrong` claims (these set the audit flag).
   - `<thread>.{N}.rehearse/density.md` — extract any slides exceeding 50 words or 7 bullets (these set the density flag).
   - `<thread>.{N}.rehearse/timing.md` — extract the projected total duration; if >110% of `time_slot_minutes` (from the brief), set the time flag.
6. **Parse the deck**: split `deck.md` on `---` slide separators. For each slide, record: slide number, title, body word count, bullet count, math/diagram presence, figure references. Pair each slide with its `notes/<NN>-*.md` file.
7. **Score each dimension** (1–8 per rubric):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (slide number, excerpt, figure reference, notes file).
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.
8. **Identify own critical flags**: review the deck against the ad-hoc flag examples in `rubric.md` (pedagogical regression, live-demo dependency, unattributed quotation, PII) AND the open-ended "any deal-breaker a sophisticated audience member would catch" instruction. For each flag set, write a one-paragraph justification in `verdict.md`.
9. **Pull in sibling flags**: propagate any audit / density / time flags from sibling critic dirs into the verdict, clearly labeled with their source (e.g., `audit flag — slides-audit verdicted 2 claims wrong`). Do not re-litigate these flags; the auditor and rehearser are authoritative on their respective dimensions.
10. **Compute total**: sum all dimension scores. `advance = (total >= 32) AND (no critical flags from any source)`. The pre-flight lint counts as a critical-flag source: when `lint.errors > 0`, `advance` is forced `false` and the verdict lists `Slide overflow (lint)` under critical flags — the rubric total is reported honestly but does not save the verdict.
11. **Write slide-level comments**: in `comments.md`, list specific feedback keyed to slide numbers (e.g., `### Slide 7: Architecture overview`) — heading reference + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`). Reference notes files where note quality is the issue (e.g., `notes/14-results.md is empty`).
11b. **Write `_summary.md`** as a JSON-in-markdown scorecard. The `lint` block is populated from the cached `LintResult` returned by step 4b:
    ```markdown
    # Review summary

    ```json
    {
      "critic": "review",
      "for_version": <N>,
      "dimensions": { /* 8-dim scorecard per rubric.md */ },
      "lint": {
        "ran": true,
        "errors": 1,
        "warnings": 0,
        "errors_by_slide": [
          { "slide": 7, "line": 51, "rule": "slide-content-overflow", "severity": "error", "message": "Slide exceeds estimated vertical capacity..." }
        ],
        "warnings_by_slide": []
      },
      "critical_flag": true,
      "critical_flag_notes": [
        { "type": "slide_overflow_lint", "slide_refs": ["Slide 7"], "justification": "Pre-flight overflow lint flagged 1 slide as exceeding estimated vertical capacity." }
      ]
    }
    ```
    ```
    When `lint.errors > 0`, set `critical_flag: true` and append a `{ "type": "slide_overflow_lint", ... }` entry to `critical_flag_notes` — the lint is treated as a critical-flag source on par with the audit / density / time flags.
11c. **Write `findings.md`** with both review findings and a "Lint findings" subsection. The "Lint findings" section is present even if empty (write `_No lint findings._`):
    ```
    ## Findings

    1. **[major]** Slide 7: Architecture diagram unlabeled. Suggested fix: add boxed labels for each block before submission.
    ...

    ## Lint findings

    1. **[error]** Slide 7 (line 51): Slide exceeds estimated vertical capacity by ~2.0 line-units. Top costs: image=7.0u, h2=2.0u. Suggested fix: replace the trailing 4 bullets with a single italic supporting line under the figure.
    ```
12. **Write `verdict.md`** in the format specified in `rubric.md`:
    - Total: `XX / 40`
    - Decision: `advance: true` or `advance: false`
    - Critical flags (if any), labeled by source. When `lint.errors > 0`, include `Slide overflow (lint)` as one of the labeled flag entries.
    - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
    - Top 3 revision priorities (if `advance: false`)
13. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
14. **Report**: print the path to the review dir and a one-line status (e.g., `Reviewed kdd-2026-keynote.1 → kdd-2026-keynote.1.review/ (28/40, advance: false, 1 audit flag, 2 density flags)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output.
- Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Re-running on revision

When a new `<thread>.{N+1}/` is produced by `slides-revise`, the orchestrator runs all three critics (`slides-review`, `slides-audit`, `slides-rehearse`) against the new version. The reviewer for `<thread>.{N+1}/` is a fresh invocation writing to `<thread>.{N+1}.review/`; it does NOT consult the prior version's review (the changelog in `<thread>.{N+1}/changelog.md` is the audit trail for what was addressed).

## Notes for the reviewer agent

- **Be honest, not encouraging.** The skill is not "polish the deck." It is "would this talk hold up in front of the declared audience for the declared time slot?" Score accordingly.
- **Trust the auditor and rehearser.** Pull their flags in verbatim; do not re-score the dimensions they own. The reviewer scores all 8 dimensions, but the audit/density/time flags themselves are upstream — propagate them.
- **Pedagogy beats polish.** A clear plain slide beats a beautiful confusing one. Score Dimension 2 before Dimension 5.
- **Notes matter for talks.** Every slide needs a notes file with substantive content; perfunctory or empty notes are a Dimension 7 failure.
- **Comments should be actionable.** "Tighten this slide" is not useful. "Slide 7 has 8 bullets — split into two slides at the architecture / data-flow boundary" is useful.

## `_progress.json` snippet (review sibling)

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

Merge rule (shallow): preserve fields not touched by this command.
