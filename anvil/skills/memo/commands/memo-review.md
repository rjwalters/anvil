---
name: memo-review
description: Reviewer command for the memo skill. Scores the latest memo version against the 8-dimension /40 rubric and writes a read-only review sibling directory.
---

# memo-review — Reviewer

**Role**: reviewer.
**Reads**: latest `<thread>.{N}/` (specifically `memo.md` and any `exhibits/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/memo.md` existing.
- **Rubric**: `anvil/skills/memo/rubric.md` (8 dimensions, /40, ≥32 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/memo/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<thread>.{N}.review/
  verdict.md       Top-level decision + total /40 + critical flags + top revision priorities
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to memo.md headings or excerpts
  _summary.md      Machine-readable scorecard + pre-flight lint block (see step 9)
  _meta.json       { critic, role, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state for the reviewer (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/memo.md`. If `<thread>.{N}.review/_progress.json.review.state == done` and `verdict.md` exists, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`** for the review dir: `phases.review.state = in_progress`, `phases.review.started = <ISO>` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`).
4. **Read inputs**: load `<thread>.{N}/memo.md`, enumerate `exhibits/`, load `rubric.md` and any consumer override. Also read `<thread>/.anvil.json` if present and extract the optional `target_length` field per the SKILL.md §Length targets contract. Normalize to a `(min_words, max_words)` pair: `words` taken directly, `pages` converted at 600 words/page, malformed/absent → no target (dim 7 falls back to the implicit "reasonable" judgment).
4b. **Run pre-flight image-reference lint (source-side)** — issue #146:
   - Invoke `anvil/skills/memo/lib/memo_image_refs.py`'s `lint_memo_image_refs(<thread>.{N}/)`. This is a Python-stdlib heuristic check (no third-party deps, no Marp / Pandoc invocation) that parses `memo.md` for both markdown `![alt](path)` syntax AND HTML `<img src="...">` syntax. For each ref it resolves the path relative to the version directory and verifies the file exists. URL refs (`http://`, `https://`, `mailto:`, `data:`, `ftp://`, `file://`) and absolute filesystem paths (`/abs/...`) are skipped — out of scope per the v0 contract.
   - The call returns a `LintResult` with `errors: list[Finding]`, `warnings: list[Finding]`, and `infos: list[Finding]`. Each `Finding` has `line` (1-based source line), `rule` (always `"memo_image_refs_exist"` for this lint), `severity`, `message`, `ref` (the raw reference string), and `resolved_path` (the absolute path the ref resolved to).
   - When a missing ref names a subdirectory (e.g., `exhibits/foo.png`) AND a file with the same basename exists at the version-dir root (e.g., `<version_dir>/foo.png`), the diagnostic surfaces the **`cp -r` footgun shape** explicitly — the canary failure mode documented in #146 (`cp -r .../old/exhibits .../new/` expanded to dump files into the version root because the destination did not exist as a directory).
   - **Escape hatch**: `<!-- anvil-lint-disable: memo_image_refs_exist -->` placed on the same line as a ref, or on the immediately preceding line, downgrades that finding from `error` to `info` so the lint records that the ref is intentionally absent (e.g., `memo-figures` will generate it later) without blocking advance.
   - The lint is **review-phase only** — the drafter and reviser do not invoke it. The drafter is intentionally allowed to produce a stale-path memo so the reviser sees the failure mode (precedent: deck-review step 5b, per the curator addendum on issue #31 / AC6).
   - Cache the `LintResult` for the `_summary.md` write below; cache `lint.errors > 0` as `lint_critical_flag` for the verdict logic at step 7.
5. **Score each dimension** (1–8 per rubric):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (heading, excerpt, exhibit) from the memo.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.
   - **Dim 7 (Scope discipline) length comparison**: compute the word count of `memo.md` (a simple `len(memo.md.split())` is sufficient; the reviewer may strip code-fence content and YAML frontmatter before counting if they meaningfully distort the body length). If `target_length` is set, compare the actual word count against the declared `[min, max]` range and apply the following calibration:
     - **In range** (`min <= actual <= max`): no length-driven deduction; score on the other scope-discipline criteria (no kitchen-sink appendices, no scope creep into adjacent deals).
     - **Modest deviation** (within ~15% of the nearest endpoint): note in the justification but do not flag — soft target.
     - **Meaningful deviation** (>~15% over `max` or under `min`): deduct on dim 7 and call out the deviation explicitly in the justification.
     The dim 7 justification MUST record **both the declared target and the actual count** (e.g., "Target 1800–2400 words; actual 2050 — in range" or "Target 1800–2400 words; actual 3400 — 42% over upper bound"). When `target_length` is unset, the dim 7 justification falls back to the implicit "reasonable for the decision being made" judgment as today, with no length numbers required.
6. **Identify critical flags**: review the memo against the 4 example flags in `rubric.md` AND the open-ended "any deal-breaker a sophisticated reader would catch" instruction. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 32) AND (no critical flags) AND (lint.errors == 0)`. When the pre-flight image-reference lint (step 4b) reports `errors > 0`, `advance` is forced `false` and the verdict lists `Memo image refs (lint)` under critical flags. The rubric total is reported honestly but does not save the verdict — a memo that references files that do not exist is not advance-eligible regardless of its prose quality.
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to memo sections — heading reference + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`).
9. **Write `_summary.md`** as a JSON-in-markdown scorecard. The `lint` block is populated from the cached `LintResult` returned by step 4b:
   ```markdown
   # Review summary

   ```json
   {
     "critic": "review",
     "for_version": <N>,
     "dimensions": { ... per-dim scores ... },
     "lint": {
       "memo_image_refs": {
         "ran": true,
         "errors": 1,
         "warnings": 0,
         "errors_by_path": [
           { "line": 41, "rule": "memo_image_refs_exist", "severity": "error", "message": "Image reference `exhibits/fig_cohort_valuation.png` does not exist at expected path `/abs/path/to/<thread>.{N}/exhibits/fig_cohort_valuation.png`, but a file with the same basename was found at the version-dir root...", "ref": "exhibits/fig_cohort_valuation.png", "resolved_path": "/abs/path/to/<thread>.{N}/exhibits/fig_cohort_valuation.png" }
         ],
         "warnings_by_path": []
       }
     },
     "critical_flag": true,
     "critical_flag_notes": [
       { "type": "memo_image_refs_lint", "ref_lines": [41], "justification": "Pre-flight image-reference lint flagged 1 missing ref. See lint.memo_image_refs.errors_by_path for the per-ref breakdown and suggested fixes." }
     ]
   }
   ```
   ```
   - When `lint.memo_image_refs.errors > 0`, set `critical_flag: true` and append a `critical_flag_notes` entry of type `memo_image_refs_lint` naming the affected source lines. This flag lives under the "fourth-category critical flag" bucket per `rubric.md`'s open-ended "any deal-breaker a sophisticated reader would catch" slot — a memo whose PDF renders with broken-image placeholders is not ship-ready regardless of its prose.
10. **Write `verdict.md`** in the format specified in `rubric.md`:
    - Total: `XX / 40`
    - Decision: `advance: true` or `advance: false`
    - Critical flags (if any) — include `Memo image refs (lint)` when `lint.memo_image_refs.errors > 0`
    - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
    - Top 3 revision priorities (if `advance: false`) — when the lint raised errors, the first priority MUST be "Fix the N missing image references (see `_summary.md` lint block)"
11. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
12. **Report**: print the path to the review dir and a one-line status (e.g., `Reviewed acme-seed.1 → acme-seed.1.review/ (28/40, advance: false, 0 critical flags)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output. Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Notes for the reviewer agent

- **Be honest**, not encouraging. The skill is not "polish the memo." It is "would I stake my professional reputation on this recommendation?" If the answer is no, score accordingly.
- **Distinguish assertion from research.** A claim without a source is a hypothesis. Most early-draft memos contain too many hypotheses dressed as facts; this is the most common reason for low Evidence Quality scores.
- **Critical flags are not bonus points.** They are statements that the memo has a defect serious enough that a sophisticated reader would stop reading. Use sparingly but use them when warranted.
- **Comments should be actionable.** "Tighten this section" is not useful. "Replace the unsourced TAM figure with a citation or remove the claim" is useful.

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

> Note: using `review` as the phase name here is the documented v0 status quo; new critics should use their own tag per `anvil/lib/snippets/progress.md` (phase-name normalization across skills is deferred under #21 item 11).

And the companion `_meta.json` declaring the scorecard kind (see `anvil/lib/snippets/scorecard_kind.md`):

```json
{
  "critic": "review",
  "role": "memo-review.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict"
}
```

Merge rule (shallow): preserve fields not touched by this command. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
