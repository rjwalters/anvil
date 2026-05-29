# Memo review rubric

The reviewer scores a memo against 8 weighted dimensions summing to **40**. The threshold to advance is **≥32/40**. Any **critical flag** short-circuits the verdict — the memo is blocked regardless of total score until the flagged issue is addressed.

The rubric is tuned so that **intellectual honesty and reasoning quality (thesis + evidence + risk = 17/40 = 42.5%)** dominate the score. A memo's primary job is to make a defensible recommendation; prose polish is necessary but not sufficient.

## Dimensions

| # | Dimension | Weight | What it measures |
|---|---|---|---|
| 1 | **Recommendation clarity** | 5 | A single unambiguous recommendation (invest / pass / conditional) with stated check size or scope. A reader should extract the ask in one sentence. |
| 2 | **Thesis coherence** | 6 | A falsifiable thesis (what must be true for this to work). Supporting claims are logically chained, not just listed. |
| 3 | **Evidence quality** | 6 | Claims backed by primary sources, data, or named references. Numbers are sourced. Assertion is distinguished from research. |
| 4 | **Risk honesty** | 6 | Top 3–5 risks are named explicitly with mitigations or acknowledged residual exposure. Pro-forma risk sections that list only weak risks score low. |
| 5 | **Market & competitive framing** | 4 | TAM/SAM/SOM (or equivalent), competitive landscape, and a credible "why now" — sized to the artifact, not boilerplate. |
| 6 | **Financial reasoning** | 5 | Unit economics, capital efficiency, scenario math. Early-stage: clear sensitivity to key assumptions. Later-stage: defensible model. |
| 7 | **Scope discipline** | 4 | The memo stays within its declared scope (no scope creep into adjacent deals, no kitchen-sink appendices that dilute the argument). Length is reasonable for the decision being made. |
| 8 | **Prose & structure** | 4 | Navigable headings, tight prose, no jargon-without-definition, exhibits referenced from body. Lowest weight by design — substance over style. |
| | **Total** | **40** | Advance threshold: ≥32 |

## Scoring guidance

For each dimension, the reviewer assigns an integer between 0 and the dimension's weight. A short justification accompanies each score (1–3 sentences pointing to specific evidence in the memo).

Suggested calibration:
- **Full weight** — meets the standard convincingly; a sophisticated reader would have no substantive objection on this dimension.
- **~75% of weight** — meets the standard with a defensible gap or one specific weakness noted.
- **~50% of weight** — partial; multiple gaps or one significant weakness.
- **~25% of weight** — present but inadequate; major rework needed.
- **0** — absent or actively misleading.

## Advance threshold

- **≥32/40** — advance to `READY` (or to next step in the lifecycle).
- **<32/40** — block; revise.
- **Any critical flag set** — block regardless of total. The next revision must address the flagged issue specifically and the reviewer must re-evaluate the flag before the threshold check applies.

## Critical flags

A critical flag is an issue severe enough that **a sophisticated reader would immediately stop taking the memo seriously**, regardless of how well other dimensions score. Set a flag whenever such an issue is identified — this list is illustrative, not exhaustive:

- **Conflict of interest** — Material undisclosed conflict (author or fund relationship) that affects the recommendation.
- **Factual error in cited financials** — A number, ratio, or attribution that does not match the cited source. Distinct from a contested interpretation; this is a verifiable error.
- **Recommendation contradicts thesis** — Memo recommends invest while the thesis it presents is unsupported (or recommends pass while the thesis is strongly supported and unrebutted).
- **Risks section omits a known dealbreaker** — A risk the reviewer can identify from the memo's own evidence is absent from the risks section.

The reviewer should also raise a flag for any other issue that, in their judgment, meets the standard above — the four examples are starting points, not a closed set.

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
  verdict.md       Top-level decision (see above)
  scoring.md       Per-dimension score + justification
  comments.md      Line-level comments keyed to memo.md
```

The reviewer dir is **read-only once written** (state: `done` in its own `_progress.json`). Revisions consume it without modifying it.
