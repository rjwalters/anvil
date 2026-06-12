---
name: pub-review
description: Reviewer command for the pub skill. Scores the latest paper version against the 9-dimension /44 rubric and writes a read-only review sibling directory.
---

# pub-review — Reviewer

**Role**: reviewer.
**Reads**: latest `<thread>.{N}/` (specifically `main.tex`, `refs.bib`, and any `figures/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/main.tex` existing.
- **Rubric**: `anvil/skills/pub/rubric.md` (9 dimensions, /44, ≥35 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/pub/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).
- **Optional thread config**: `<thread>/.anvil.json`. The `venue` field, if set, triggers an additional advisory scoring pass against the matching venue rubric YAML (see `SKILL.md` § "Venue overlays").
- **Optional `web_search` knob** (issue #424): when the thread's `<thread>/BRIEF.md` frontmatter (or, in a post-#295 project layout, the thread's `documents:` entry in the project `BRIEF.md` — see `anvil/lib/project_brief.py`) sets `web_search: true`, the reviewer MAY run 3–5 targeted web searches while scoring **D4 (related-work positioning)** to check for close prior work missing from `refs.bib`. The reviewer remains **read-only with respect to citations**: it NEVER writes `.bib` entries, never runs `cite.resolve()`, and never adds anything to `refs.bib` or `candidates.bib`. Discovered identifiers (DOI / arXiv ID / URL as found) land in `comments.md` as `related-work`-tagged **leads** recommending a `pub-litsearch` re-run; the re-run performs the resolver verification (`anvil/lib/cite.py::resolve()` — the resolver-verified-or-dropped contract is centralized in `pub-litsearch`, matching the existing step 8 → litsearch re-run wiring). When the knob is absent or `false`, this behavior DOES NOT fire and the review path is byte-identical to the default no-web behavior — same contract as `--rescore-mode` below.
- **Optional `--rescore-mode <rescore-id>` flag** (issue #368): when set, the reviewer re-routes its staged_sidecar output from `<thread>.{N}.review/` to `<thread>.{N}.review.rescore-<rescore-id>/`, re-targets the prior-review lookup to `<thread>.{N}.review/` (NOT `<thread>.{N-1}.review/`) since the current version's legacy review IS the prior review for a rescore pass, and stamps `_meta.json` with `rescore_state: "completed"` + `rescore_id: "<rescore-id>"` (overwriting any placeholder `rescore_state: "scheduled"` left behind by `anvil:rubric-rebackport --rescore --apply`). When the flag is unset, behavior is byte-identical to the default review path. See step 3 for the full re-routing contract.

## Outputs

```
<thread>.{N}.review/
  verdict.md         Top-level decision + total /44 + critical flags + top revision priorities
  scoring.md         Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md        Line-level comments keyed to main.tex section headings or excerpts
  findings.md        Cross-section observations + rubric version transition subsection
                     (emitted on every review; transition section conditional per step 9b)
  _review.json       Canonical critic JSON (anvil/lib/review_schema.py) — generic /44 scorecard
                     with `rubric: "anvil-pub-v2"`. Drives the convergence gate.
  _review.venue.json (optional) Venue advisory overlay scorecard, when `<thread>/.anvil.json`
                     declared a `venue` that resolved to a matching YAML. Same `Review` schema,
                     with `rubric: "anvil-pub-<venue>-v1"`. ADVISORY ONLY: this file does NOT
                     change the convergence-gate decision; it surfaces venue-specific findings
                     for the reviser.
  _summary.md        JSON-in-markdown scorecard carrying the top-level `rubric` block + dimensions.
                     Sibling to `_review.json`; the `rubric` block lets aggregators compare scores
                     across rubric migrations without re-reading `rubric.md`.
  _meta.json         { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version, rubric_id, rubric_total, advance_threshold }
  _progress.json     Phase state for the reviewer (phase: review)
```

**Atomicity** (issue #350, #376): the review sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The required files (`verdict.md`, `scoring.md`, `comments.md`, `findings.md`, `_review.json`, `_summary.md`, `_meta.json`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.review.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.review/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.review.tmp/` dir on disk that the next invocation's `cleanup_one_staging(<thread>.{N}.review)` per-critic sweep removes; the final-named dir never exists in partial form. Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob. The optional `_review.venue.json` and `_gate.json` are also written inside the staging dir but are NOT in the required-files manifest (they are conditional outputs).

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/main.tex`. Then **sweep a stale staging dir from a prior interrupt of THIS critic on THIS version** by invoking `anvil/lib/sidecar.py::cleanup_one_staging(<thread>.{N}.review)` (the per-critic, parallel-safe sweep — issue #376). This removes ONLY a leftover `.<thread>.{N}.review.tmp/` from a previously-killed run of this same critic on THIS version. Sibling critics' in-flight staging dirs under the same portfolio root are NOT touched (issue #350, #376). The sweep is idempotent and logs at INFO level when it removes a dir. If `<thread>.{N}.review/` exists (the atomic-rename contract guarantees the dir only exists when complete), the review is complete — exit early with a notice (idempotent).
2. **Resume check**: per the staged-sidecar shape introduced in issue #350, a partial review left behind by a mid-cycle interrupt manifests as a leading-dot `.<thread>.{N}.review.tmp/` directory (NOT as a partially-filled `<thread>.{N}.review/`). The sweep in step 1 has already removed any such partial. Backwards-compat: if a legacy pre-#350 `<thread>.{N}.review/` exists WITHOUT `verdict.md`, delete the dir and re-review.
3. **Open the staged sidecar** for the review dir by invoking the context manager `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.review, required_files=["verdict.md", "scoring.md", "comments.md", "findings.md", "_review.json", "_summary.md", "_meta.json", "_progress.json"])`. Every file write from this step through the final `_progress.json` update MUST land **inside the yielded staging directory** (the path of the shape `.<thread>.{N}.review.tmp/`), NOT inside the final `<thread>.{N}.review/` path. On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name (issue #350). Then, **inside the staging dir**, initialize `_progress.json`: `phases.review.state = in_progress`, `phases.review.started = <ISO>` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict`, `rubric_id: "anvil-pub-v2"`, `rubric_total: 44`, and `advance_threshold: 35` (see `anvil/lib/snippets/scorecard_kind.md` §"The discriminator" — the three rubric-stamping fields are required for new reviews per issue #346; `"anvil-pub-v2"` is the pub skill's current /44 rubric identifier per `anvil/skills/pub/rubric.md` line 3). The rubric-stamping fields let downstream consumers compare scores apples-to-apples across the `/40 → /44` migration without re-reading the skill's current `rubric.md`. Also load the **prior review sibling** at `<thread>.{N-1}.review/_meta.json` when present and cache its `rubric_id` value as `prior_rubric_id` (or `None` when the prior sibling is absent — first iteration — or lacks the field — legacy pre-#346 review). The cached `prior_rubric_id` feeds the `_summary.md.rubric` block at step 10 + the `findings.md` rubric-transition subsection (step 10b) when the prior rubric differs from the current `"anvil-pub-v2"`.

   **When `--rescore-mode <rescore-id>` is set** (issue #368) — the rebackport reviewer-hook contract:
   - **Re-derive `final_dir`** from `<thread>.{N}.review` to `<thread>.{N}.review.rescore-<rescore-id>`. The staging directory derived by `anvil/lib/sidecar.py::staging_path_for(final_dir)` correspondingly becomes `.<thread>.{N}.review.rescore-<rescore-id>.tmp/` — no separate code path is needed; the same `staged_sidecar(final_dir=...)` call works with the rescore sidecar path.
   - **Re-target the prior-review lookup to `<thread>.{N}.review/_meta.json`** (NOT `<thread>.{N-1}.review/_meta.json`). Under rescore mode, the legacy review at `<thread>.{N}.review/` IS the prior review — the rescore is re-scoring the SAME version's body against an updated rubric, not advancing to a new version. Cache its `rubric_id` value as `prior_rubric_id` (or fall back to `--legacy-rubric` from the rebackport tool when the legacy review lacks the field — pre-#346).
   - **Stamp `_meta.json` with `rescore_state: "completed"` and `rescore_id: "<rescore-id>"`** in addition to the standard rubric-stamping fields. The placeholder `_meta.json` left behind by `anvil:rubric-rebackport --rescore --apply` carries `rescore_state: "scheduled"`; this reviewer overwrites it with `"completed"` once the full required-files manifest (including `_review.json` per the `Review` schema in `anvil/lib/review_schema.py`, with `rubric: "anvil-pub-v2"` and the rescore_id surfaced for downstream aggregators) has landed inside the staging dir. The `rescore_source: "anvil:rubric-rebackport"` field from the placeholder is preserved (or added if absent).
   - **All other behavior is unchanged** — same scoring, same verdict, same `findings.md` emission, same `_summary.md.rubric` block (now carrying the legacy review's rubric as `prior_rubric_id`). The legacy `<thread>.{N}.review/` dir is NEVER mutated — the rescore is a side-car write only.
   - **When `--rescore-mode` is unset**, the steps above DO NOT fire and the review path is byte-identical to the default behavior documented in the rest of this step.
4. **Read inputs**: load `<thread>.{N}/main.tex`, `<thread>.{N}/refs.bib`, enumerate `figures/`, load `rubric.md` and any consumer override. Also call `anvil.lib.rubric.discover_venue_rubric(<thread>, <skill_root>)`; this reads `<thread>/.anvil.json` for an optional `venue` field and returns the matching `Rubric` (or `None`).
   - If `<thread>/.anvil.json` declared a `venue` but `discover_venue_rubric` returned `None` (no matching YAML in any tier), print a one-line stdout warning (`pub-review: venue '<slug>' declared in .anvil.json but no matching rubric YAML found; proceeding with generic /44 only`) and continue. Do NOT fail the review — the generic gate is still in force.
4b. **Run render-gate (pre-flight)** — mirrors `deck-review.md` step 5b:
   - Invoke `anvil/lib/render_gate.py`'s `gate(...)` against the paper PDF. Mirror the `marp_lint.py` integration shape used in `deck-review.md` step 5b (a deterministic pre-flight that emits a typed `Review` with `kind=tool_evidence` plus a sibling `_gate.json` for CI inspection — see `anvil/lib/render_gate.py` module docstring).
   - **Inputs:**
     - `pdf_path`: `<thread>.{N}/paper.pdf` — produced by `pub-audit`'s `pdflatex && bibtex && pdflatex && pdflatex` cycle.
     - `log_path`: `<thread>.{N}.audit/compile-log.txt` — captured by `pub-audit` (see `commands/pub-audit.md`).
     - `source_paths`: `[<thread>.{N}/main.tex]` plus any `\input`/`\include` children.
     - `page_cap=None` — paper length is venue-dependent; the generic gate does not enforce a cap. (A consumer with a hard venue cap can override per-thread via `<thread>/.anvil.json: render_gate.page_cap`.)
     - `overfull_threshold_pt=5.0`, `placeholder_patterns=None` (use `DEFAULT_PLACEHOLDER_PATTERNS`).
   - **Audit-first ordering (fail-open)**: when `paper.pdf` and `compile-log.txt` are **absent** (i.e., this `pub-review` was invoked before `pub-audit`), the gate fails open with a clear stdout message (`pub-review: render-gate skipped — paper.pdf / compile-log.txt not present; run pub-audit first`). The review proceeds normally without gate enforcement. The strict "audit must run first" ordering is intentionally out of scope here (a separate state-machine change).
   - Write the `GateResult.to_json()` payload to `<thread>.{N}.review/_gate.json` for CI inspection.
   - Cache the `GateResult` for the `_summary.md` `render_gate` block and the critical-flag wiring in step 7.
   - When `GateResult.passed=False`, append one entry per failed gate dimension to `critical_flag_notes` in `_review.json` (type prefix: `render_gate_<dim>`), via `GateResult.to_review(...).critical_flags`. The aggregator then forces `Verdict.BLOCK` per the standard `anvil/lib/critics.py::compute_verdict` path; no schema change needed.

5. **Score each dimension** (1–9 per rubric):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (section heading, excerpt, figure, table) from the paper.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.

   Notes specific to paper review (in addition to the general guidance in `rubric.md`):
   - **Rigor (D1)** and **Evidence (D2)** are scored independently. A paper with a sound method but only one experiment scores high on D1 and low on D2.
   - **Clarity of contribution (D3)** is scored from the abstract and introduction. If the contribution is not extractable in one sentence per item from those two sections, score below full weight.
   - **Related-work positioning (D4)** requires the reviewer to read `\section{Related Work}` against `refs.bib`. If the closest prior work (per the reviewer's domain knowledge) is missing from `refs.bib`, set a critical flag (close prior work ignored) AND score D4 low. **When `web_search: true`** (issue #424; see Inputs), the reviewer may additionally run 3–5 targeted searches to ground this judgment in live results rather than training-data recall alone; any discovered prior work becomes a `related-work`-tagged lead in `comments.md` (step 8), NOT a citation — verification is `pub-litsearch`'s job on the re-run.
   - **Reproducibility (D5)**: check for explicit code/data/seed references and a methods section detailed enough to replicate. Pseudo-code without hyperparameters scores low.
   - **Figure & table quality (D6)**: the reviewer reads captions standalone. A caption that does not communicate the figure's point without the body text loses points.
   - **Citation hygiene (D8)**: at this stage the reviewer only checks (a) every `\cite{}` resolves to an entry in `refs.bib` (catches build failure early) and (b) bibliography entries have the standard fields. Whether cited papers actually support claims is `pub-audit`'s job.
   - **Rhetorical economy (D9)**: orthogonal to dim 7 *Prose & structural quality*. Dim 7 measures flow / hand-waving / tense / LaTeX hygiene; dim 9 asks "could the same argument land in fewer pages?" — paragraphs that restate the introduction, tables that duplicate prose claims, methods sections that ceremonially recap prior work without adding signal. A paper at the venue's page cap whose argument fits in 6 pages scores low on dim 9 regardless of its prose polish.
6. **Identify critical flags**: review the paper against the example flags in `rubric.md` (citation error, plagiarism risk, missing experiment for a claim, numerical inconsistency, close prior work ignored, build/compile failure) AND the open-ended "any dealbreaker a sophisticated reader would catch" instruction. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 35) AND (no critical flags)`.

   **Append `score_history` row with `rubric_id` (issue #346)**: the orchestrator (the command that drives review→revise iterations) appends one row to `<thread>.{N}/_progress.json.metadata.score_history` per finished review iteration. Per `anvil/lib/snippets/progress.md` §"Convergence fields → score_history", the canonical row shape is `{iteration, total, threshold, rubric_id}` — for the pub skill at /44, that's `{iteration: <N>, total: <computed-total>, threshold: 35, rubric_id: "anvil-pub-v2"}`. A thread that spans the `/40 → /44` migration records different `rubric_id` values across its rows (e.g., rows 1–2 may carry `"anvil-pub-v1"` from legacy reviews and rows 3+ carry `"anvil-pub-v2"` from post-migration reviews); readers tolerate rows missing `rubric_id` per the backwards-compat contract (treat as `"unknown/legacy"`). See `convergence.check_stable` for the precedent on `None`-tolerance.
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to paper sections — section heading + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`). For related-work concerns, tag with `related-work` so a re-run of `pub-litsearch` can pick them up specifically. **When `web_search: true`** (issue #424), each web-discovered prior-work candidate from the D4 searches is written here as a `related-work`-tagged lead carrying whatever the search surfaced (title / authors / year / identifier-or-URL as found) plus an explicit recommendation to re-run `pub-litsearch` — the reviewer writes NO citations and NO `.bib` entries; the litsearch re-run owns the `cite.resolve()` verification and decides candidate-vs-lead.
9. **Write `verdict.md`** in the format specified in `rubric.md`:
   - Total: `XX / 44`
   - Decision: `advance: true` or `advance: false`
   - Critical flags (if any)
   - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
   - Top 3 revision priorities (if `advance: false`)
10. **Write canonical `_review.json`** for the generic /44 scorecard. This is the canonical critic JSON shape documented in `anvil/lib/review_schema.py` (`Review` model). Fields:
    - `version_dir`: `"<thread>.{N}"`
    - `critic_id`: `"pub-review"`
    - `rubric`: `"anvil-pub-v2"`
    - `scores`: one entry per generic-rubric dimension (id matching `rubric.md` dimension numbering/naming), with `max` echoed from the rubric.
    - `findings`: optional, mirror of severity-tagged `comments.md` items.
    - `critical_flags`: mirror of any flags raised.
    - `total`, `threshold` (35), `verdict`.
    The convergence-gate decision (`advance`) is computed from THIS file only.

    **Also write `_summary.md` with the top-level `rubric` block (issue #346)**: emit a JSON-in-markdown `_summary.md` carrying at minimum the `rubric` block — the rubric the reviewer scored against, so a downstream consumer aggregating across versions does not need to walk back to `anvil/skills/pub/rubric.md` (which may have changed between v3 and v5 of a long thread that spanned the `/40 → /44` migration). Shape:

    ```markdown
    # Review summary

    ```json
    {
      "critic": "review",
      "for_version": <N>,
      "rubric": {
        "id": "anvil-pub-v2",
        "total": 44,
        "advance_threshold": 35,
        "dimensions": 9,
        "prior_rubric_id": "anvil-pub-v1"
      }
    }
    ```
    ```

    The `rubric` block fields:
    - `id` (`str`): the rubric identifier — `"anvil-pub-v2"` for the current /44 rubric. Mirrors `_meta.json.rubric_id`.
    - `total` (`int`): the rubric's declared `total` — `44`.
    - `advance_threshold` (`int`): the rubric's declared advance threshold — `35`.
    - `dimensions` (`int`): the count of weighted dimensions — `9`.
    - `prior_rubric_id` (`str | null`, conditional): present when the prior review sibling at `<thread>.{N-1}.review/` exists. Value is the prior `_meta.json.rubric_id` when present, or `null` when the prior sibling lacks the field (legacy pre-#346 review). **Omitted entirely** on the first iteration (no prior review sibling exists).
    - `prior_rubric_inferred` (`str`, conditional): present when `prior_rubric_id == null` AND a prior review sibling exists. Value is `"/40-legacy"` to signal "this thread's prior iteration was scored against the pre-#346 /40 rubric (whatever the skill shipped at the time)".

    The block is **observational only** — it does NOT affect verdict, critical flags, or `advance`. Backwards-compat: a legacy review sibling produced before issue #346 MAY omit `_summary.md` entirely; downstream consumers MUST tolerate the absence.

10b. **Emit rubric-version-transition subsection in `findings.md` when the prior rubric differs (issue #346)**: when the cached `prior_rubric_id` from step 3 is non-`None` AND differs from the current `"anvil-pub-v2"`, OR when `prior_rubric_id == None` AND a prior review sibling exists (legacy pre-#346 review), write a `## Rubric version transition` subsection into `findings.md`. The subsection's purpose is **operator visibility** — it surfaces, in plain prose, the fact that this iteration's score is NOT directly comparable to the prior iteration's score (the threshold pool changed, the dimension count changed, weighted contributions shifted) so an operator reading `verdict.md`'s score-delta numbers does not silently mis-judge. Three shapes:

    When the prior rubric is a different stamped id (e.g., post-#346 thread that started with one rubric and the skill ships a new one — rare but possible):
    ```
    ## Rubric version transition

    This iteration was scored against `anvil-pub-v2` (/44, ≥35); the prior iteration at `<thread>.{N-1}.review/` was scored against `anvil-pub-v1` (/40, ≥32). The score delta `<prior_total>/40 → <current_total>/44` is NOT directly comparable — the threshold pool, dimension count, and weighted contributions all changed. A downstream consumer reading the delta SHOULD treat the prior score as advisory only and re-anchor on the current iteration's `<current_total>/44` against the `≥35/44` threshold.
    ```

    When the prior rubric is legacy (no `rubric_id` stamped):
    ```
    ## Rubric version transition

    This iteration was scored against `anvil-pub-v2` (/44, ≥35); the prior iteration at `<thread>.{N-1}.review/` predates per-review rubric version stamping (issue #346) and was scored against `/40-legacy` — the rubric this skill shipped before the `/40 → /44` migration (likely `anvil-pub-v1`, /40, ≥32). The score delta `<prior_total>/40-legacy → <current_total>/44` is NOT directly comparable — the threshold pool, dimension count, and weighted contributions all changed. A downstream consumer reading the delta SHOULD treat the prior score as advisory only and re-anchor on the current iteration's `<current_total>/44` against the `≥35/44` threshold.
    ```

    When the prior rubric matches the current rubric (the steady-state case — no transition surfaced):
    ```
    (subsection omitted entirely)
    ```

    The subsection is **observational** — it does NOT affect the verdict, the critical-flag list, or the `advance` decision. It is purely audit-trail prose so the operator's mental model stays calibrated across a rubric migration. Backwards-compat: a legacy review sibling produced before this contract shipped does NOT need to be re-emitted.
11. **Venue overlay (conditional)**: if `discover_venue_rubric` returned a non-None `Rubric` in step 4, score the paper against the venue rubric in addition to the generic /44 — read each venue dimension's `description` and `calibration` from the YAML, assign integer scores in `[0, weight]`, set venue critical flags as warranted. Write the result to `<thread>.{N}.review/_review.venue.json` using the same `Review` schema:
    - `version_dir`: `"<thread>.{N}"`
    - `critic_id`: `"pub-review-venue"`
    - `rubric`: the venue rubric's `id` (e.g., `"anvil-pub-neurips-v1"`)
    - `scores`: one entry per venue-rubric dimension (id matching the YAML's `dimensions[].id`).
    - `total`: sum of venue dim scores (informational only — does NOT contribute to the convergence gate).
    - `threshold`: omit OR echo the YAML's threshold if declared. The aggregator filters by `rubric` id when computing the gate, so this file's threshold is informational.
    - `verdict`: omit (per-critic verdicts are ignored by the aggregator).
    The venue file's findings and critical_flags ARE consumed by the reviser for venue-specific signal — but a venue critical flag does NOT block the convergence gate (which only fires on flags carried in the generic `_review.json`). Mention the venue overlay in `verdict.md` (e.g., a one-paragraph note: `"Advisory venue overlay scored 12/16 against anvil-pub-neurips-v1; see _review.venue.json for findings."`).
12. **Update `_progress.json`** inside the staging dir: `phases.review.state = done`, `phases.review.completed = <ISO>`. This is the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires `_progress.json` to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies every name in the required-files manifest exists in the staging dir, then atomically renames `.<thread>.{N}.review.tmp/` → `<thread>.{N}.review/`. The final-named dir only ever exists in **complete** form.
13. **Report**: print the path to the (now-renamed) review dir and a one-line status (e.g., `Reviewed q3-method.1 → q3-method.1.review/ (32/44, advance: false, 1 critical flag) [+ venue overlay 12/16 vs anvil-pub-neurips-v1]`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output. Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Notes for the reviewer agent

- **Be honest, not encouraging.** The skill is not "polish the paper." It is "would a sophisticated program committee member at the target venue recommend acceptance?" If the answer is no, score accordingly.
- **Distinguish assertion from evidence.** A claim without an experiment, proof, or citation is a hypothesis. This is the most common reason for low Evidence Sufficiency scores.
- **Critical flags are not bonus points.** Use them when the paper has a defect serious enough that a sophisticated reader would stop reading. The audit phase (`pub-audit`) will catch many fact/citation issues — the reviewer should still flag what's visible at review time.
- **Comments should be actionable.** "Tighten this section" is not useful. "Replace the unsourced 87% accuracy claim in the abstract with a citation to Table 2, or remove the claim" is useful.
- **Defer fact-check to the auditor.** This phase scores citation hygiene (do entries exist and are they well-formed) but does not verify cited papers actually support claims. Save the per-citation claim-support pass for `pub-audit`.

## `_progress.json` and `_meta.json` snippets (review sibling)

This command writes the critic-sibling shape documented in `anvil/lib/snippets/progress.md` (with `for_version` naming the version reviewed), and a `_meta.json` declaring the scorecard kind per `anvil/lib/snippets/scorecard_kind.md`:

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

```json
{
  "critic": "review",
  "role": "pub-review.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict",
  "rubric_id": "anvil-pub-v2",
  "rubric_total": 44,
  "advance_threshold": 35
}
```

The three `rubric_*` / `advance_threshold` fields are required for new reviews (post-issue #346) and absent-tolerated for legacy reviews. They let downstream consumers compare scores apples-to-apples across rubric migrations without re-reading the skill's current `rubric.md`.

Merge rule (shallow): preserve fields not touched by this command. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.

## Git sync (opt-in, off by default)

If the consumer repo carries `.anvil/config.json` with `git.commit_per_phase: true`, end this phase per the per-phase git commit/sync hook documented in `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo): after the staged-sidecar atomic rename (issue #350) lands the final-named `<thread>.{N}.review/`, stage ONLY this command's own `<thread>.{N}.review/` sidecar (never sibling critics' dirs — the narrow scope keeps the hook safe under parallel critic fan-out), commit as `anvil(pub/review): <thread>.{N} [REVIEWED]`, and push when `git.push` is also `true`. Git failures (not a git repo, commit failure, offline push) emit a one-line warning and continue — the review still reports success; artifact-on-disk is the source of truth. When `.anvil/config.json` is absent or `git.commit_per_phase` is false/absent, skip this step entirely — behavior is byte-identical to a pre-#426 install (default off).
