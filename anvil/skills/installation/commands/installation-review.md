---
name: installation-review
description: Reviewer command for the installation skill. Scores the latest proposal version against the 8-dimension /40 rubric and writes a read-only review sibling directory.
---

# installation-review — Reviewer

**Role**: reviewer.
**Reads**: latest `<thread>.{N}/` (specifically `installation.tex` and any `figures/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/installation.tex` existing.
- **Rubric**: `anvil/skills/installation/rubric.md` (8 dimensions, /40, ≥32 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/installation/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<thread>.{N}.review/
  verdict.md       Top-level decision + total /40 + critical flags + top revision priorities
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to installation.tex sections or excerpts
  _meta.json       { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state for the reviewer (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/installation.tex`. If `<thread>.{N}.review/_progress.json.review.state == done` and `verdict.md` exists, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`** for the review dir: `phases.review.state = in_progress`, `phases.review.started = <ISO>` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`).
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

5. **Score each dimension** (1–8 per rubric):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (section heading, excerpt, figure) from the proposal.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.
6. **Identify critical flags**: review the proposal against the 3 example flags in `rubric.md` (*unbuildable as specified* · *safety/consent hazard unaddressed* · *concept incoherent / premise not legible*) AND the open-ended "any issue that means the proposal cannot proceed as specified" instruction. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 32) AND (no critical flags)`.
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to proposal sections — heading reference + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`).
9. **Write `verdict.md`** in the format specified in `rubric.md`:
   - Total: `XX / 40`
   - Decision: `advance: true` or `advance: false`
   - Critical flags (if any)
   - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
   - Top 3 revision priorities (if `advance: false`)
10. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
11. **Report**: print the path to the review dir and a one-line status (e.g., `Reviewed quiet-place.1 → quiet-place.1.review/ (30/40, advance: false, 0 critical flags)`).

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
  "scorecard_kind": "human-verdict"
}
```

Merge rule (shallow): preserve fields not touched by this command. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
