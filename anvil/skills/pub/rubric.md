# Paper review rubric

The reviewer scores a paper against 8 weighted dimensions summing to **40**. The threshold to advance is **≥32/40**. Any **critical flag** short-circuits the verdict — the paper is blocked regardless of total score until the flagged issue is addressed.

The rubric is tuned so that **rigor + evidence + citation hygiene (6 + 6 + 5 = 17/40 ≈ 43%)** dominate the score. A paper's primary job is to defend a claim with evidence; prose polish is necessary but not sufficient. Compared to the memo rubric, this rubric demotes recommendation/decision clarity (papers do not recommend; they argue) and promotes positioning against prior work and reproducibility.

## Dimensions

| # | Dimension | Weight | What it measures |
|---|---|---|---|
| 1 | **Rigor of method / argument** | 6 | The methodology (experimental setup, proof structure, derivation) is sound and adequate to support the claims. The highest-weighted dimension. Distinct from evidence sufficiency: a method can be rigorous in structure but undersupported in results. |
| 2 | **Evidence sufficiency** | 6 | The experiments / proofs / data presented are adequate for the claims made. Sample sizes are justified, baselines are appropriate, ablations exist where claims rest on a specific design choice. Distinct from rigor: a rigorous method that produces only weak signal scores low here. |
| 3 | **Clarity of contribution** | 5 | What is new is unambiguous and stated in the abstract and introduction. A reviewer can extract the contribution(s) in one sentence per item. Failure mode: papers whose contribution is unclear are rejected even when results are strong. |
| 4 | **Related-work positioning** | 5 | Honest and accurate placement against prior art. Closest prior work is engaged on its actual merits. Failure mode: ignoring close prior work — often grounds for desk rejection. |
| 5 | **Reproducibility** | 5 | Code, data, seeds, hyperparameters, environment are referenced or supplied. Methods section is sufficient for an independent group to replicate. Increasingly a hard requirement at top venues. |
| 6 | **Figure & table quality** | 4 | Figures and tables are self-contained (caption tells the story), readable at print size, have axis labels with units, and avoid chartjunk. Tables have correct alignment and meaningful column headers. |
| 7 | **Prose & structural quality** | 4 | Abstract → introduction → methods → results → discussion flow is intact; prose is concise; no hand-waving; tense and voice are consistent. Includes LaTeX-specific concerns: no overfull hboxes in body sections, no broken cross-references (`Section ??`), no unused macros. |
| 8 | **Citation hygiene** | 5 | Every non-trivial claim has a citation; cited papers actually support the surrounding claim (audit phase verifies — this dimension catches the unsourced-claim half); bibliography entries are complete and consistent (author, title, venue, year all present). |
| | **Total** | **40** | Advance threshold: ≥32 |

## Scoring guidance

For each dimension, the reviewer assigns an integer between 0 and the dimension's weight. A short justification (1–3 sentences) accompanies each score, pointing to specific evidence in the paper.

Suggested calibration:
- **Full weight** — meets the standard convincingly; a sophisticated reader (a likely program committee member at a top venue) would have no substantive objection on this dimension.
- **~75% of weight** — meets the standard with a defensible gap or one specific weakness noted.
- **~50% of weight** — partial; multiple gaps or one significant weakness.
- **~25% of weight** — present but inadequate; major rework needed.
- **0** — absent or actively misleading.

## Advance threshold

- **≥32/40** — advance to `READY` (proceed to `pub-audit`).
- **<32/40** — block; revise.
- **Any critical flag set (from `.review/` OR `.audit/`)** — block regardless of total. The next revision must address the flagged issue specifically and the next reviewer pass must re-evaluate the flag before the threshold check applies.

## Critical flags

A critical flag is an issue severe enough that **a sophisticated reader would immediately stop taking the paper seriously**, regardless of how well other dimensions score. Set a flag whenever such an issue is identified — this list is illustrative, not exhaustive:

- **Citation error** — A `\cite{}` resolves to a paper that does not support the surrounding claim, OR a `\cite{}` points to a `refs.bib` entry that does not exist (resolves to `[??]` in the rendered PDF).
- **Plagiarism risk** — Passages that closely mirror prior work without attribution. Includes the author's own prior work (self-plagiarism is a flag in venues that require novelty).
- **Missing experiment for a claim** — The paper claims a property (robustness, generality, efficiency) without the experiment that would substantiate it. A claim of "robust to noise" with no noise-sweep experiment is a flag.
- **Numerical inconsistency** — A number reported in the text disagrees with the corresponding figure or table. Examples: text says 87.3 accuracy, Table 2 says 87.1; abstract claims 5x speedup, results show 3x.
- **Close prior work ignored** — A paper exists in the literature that is so close to the claimed contribution that ignoring it constitutes a misrepresentation of novelty. This is harder to call than the first three — use only when the omitted paper is clearly known to a serious reviewer in the area.
- **Build / compile failure** — `pdflatex` + `bibtex` cycle does not complete cleanly, OR the rendered PDF contains unresolved citations or references. Caught by `pub-audit`; if surfaced by the reviewer (e.g., from a build log shared in the version dir), set a flag.

The reviewer should also raise a flag for any other issue that, in their judgment, meets the standard above — these examples are starting points, not a closed set. **Critical flags from `pub-audit` carry equal weight** to those from `pub-review` and block advancement to `AUDITED` (i.e., the paper is not done) until addressed.

## Verdict format

The reviewer writes a `verdict.md` at the top of the review sibling dir with:

1. **Total score**: `XX / 40`.
2. **Decision**: `advance: true` or `advance: false`. (`advance: true` requires both `total ≥ 32` AND `no unresolved critical flag`.)
3. **Critical flags** (if any): bullet list, each with one-paragraph justification.
4. **Dimension summary**: a markdown table of per-dimension scores (full detail lives in `scoring.md`).
5. **Top 3 revision priorities** (if `advance: false`): the highest-leverage changes the reviser should focus on.

## Output layout

```
<thread>.{N}.review/
  verdict.md           Top-level decision (see above)
  scoring.md           Per-dimension score + justification
  comments.md          Line-level comments keyed to main.tex sections
  _review.json         Generic /40 scorecard (canonical critic JSON; see anvil/lib/review_schema.py).
  _review.venue.json   (optional) Venue advisory overlay scorecard, written
                       when <thread>/.anvil.json sets a `venue` field that
                       resolves to a known venue YAML. Same JSON schema as
                       _review.json; informational only.
```

The reviewer dir is **read-only once written** (state: `done` in its own `_progress.json`). Revisions consume it without modifying it.

## Venue-pinned advisory overlay rubrics

A paper thread may declare a target venue in `<thread>/.anvil.json`:

```json
{
  "max_iterations": 4,
  "venue": "neurips"
}
```

When set and a matching YAML is found, the reviewer also scores the paper against a **venue-pinned advisory rubric** (NeurIPS reviewer form, Nature broad-significance bar, arXiv reader norms, etc.) and writes a second `_review.venue.json` alongside the generic `_review.json`. The venue file uses the same `Review` schema in `anvil/lib/review_schema.py` (no new on-disk shape).

**Critical: the venue overlay is ADVISORY ONLY. It does NOT change the /40 convergence gate.** The generic 8-dimension rubric above (with its ≥32/40 threshold and the critical-flag short-circuit) remains the sole driver of the `advance` decision. The venue overlay produces additional findings the reviser consumes for venue-specific signal; it does NOT contribute points to the gate-deciding total. This preserves the framework-wide "/40 means the same thing across skills" invariant documented in `anvil/lib/snippets/rubric.md`.

Shipped venues:

| Venue YAML | Total | Notes |
|---|---|---|
| `rubrics/neurips.yaml` | /16 | Soundness, presentation, contribution, novelty, reproducibility. Sources NeurIPS reviewer form. |
| `rubrics/nature.yaml` | /15 | Broad significance, accessibility, evidence strength, novelty. Sources Nature reviewer instructions. |
| `rubrics/arxiv.yaml` | /10 | Citation completeness, reproducibility, clarity of contribution, scope classification. De-facto reader bar + arXiv moderation. |

Each YAML cites its public source in a header comment so it can be updated as venue guidelines change. The schema for these YAMLs is `anvil/lib/rubric.py::Rubric` with `advisory: true`; the loader skips the sum-to-/40 invariant for advisory rubrics. The venue discovery search order (per-thread → consumer-installed → skill-shipped) and the consumer override pattern are documented in `SKILL.md`.

When `venue` is set but no matching YAML is found, the reviewer emits a stdout warning and proceeds with the generic rubric only. The thread's review is not blocked by the missing venue — the generic gate continues to apply.
