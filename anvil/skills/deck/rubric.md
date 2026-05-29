# Deck review rubric

Pitch decks are scored against 8 weighted dimensions summing to **40**. The threshold to advance is **≥35/40** — decks are customer-facing artifacts (the founder's pitch to external capital), held to the same standard as legal artifacts per `lib/README.md`'s convergence rule. Any **critical flag** short-circuits the verdict — the deck is blocked regardless of total score until the flagged issue is addressed.

The rubric is tuned for the way investors actually read decks: **narrative coherence + ask specificity + market credibility dominate (16/40 = 40%)**. A deck of strong individual slides without an arc fails. A deck with a clear arc but no specific ask fails. A deck with a credible problem and team but a fabricated market number fails on the critical flag regardless of total.

## Dimensions

| # | Dimension | Weight | What it measures | Owned by critic |
|---|---|---|---|---|
| 1 | **Narrative arc** | 6 | The deck reads as a single argument from problem → solution → why-now → why-us → ask. Slides flow; the order is the argument; the closing ask follows from the setup. A deck of strong individual slides with no arc fails this dimension hardest. **Highest weight.** | `deck-narrative` |
| 2 | **Problem clarity** | 5 | An investor reading the problem slide cold understands the problem in <30 seconds and why it is worth solving now. Vague problems ("workflows are inefficient"), self-evident problems ("people want better X"), or problems explained only via solution are the #1 deck-killer. | `deck-review` |
| 3 | **Market size credibility** | 5 | TAM/SAM/SOM with defensible bottom-up logic. Top-down framing ("$XB market × 1% = $XM") is a near-automatic disqualifier at most funds and scores low here. Comparables and competitor sizing as anchors are credit. Math must check out — see critical flags. | `deck-market` |
| 4 | **Solution differentiation** | 5 | What is uniquely yours; why competitors / incumbents can't or won't follow. Explicit moat language (network effects, switching costs, regulatory, technology lead, distribution). "Faster / cheaper / better" without mechanism scores low. | `deck-market` |
| 5 | **Traction / proof** | 5 | Whatever evidence the stage permits: revenue (with growth rate), users (with retention), LOIs (with names), pilots (with conversion path), technical milestones (with verifiable outputs), design partners (named). Honest framing of what is real vs. projected. Hockey-stick projections without a current point on the curve score 0. | `deck-review` |
| 6 | **Team credibility** | 4 | Founder–market fit, prior outcomes, key hires, advisors who actually advise. Stage-dependent emphasis: seed → team-heavy; growth → traction-heavy. Generic credentials ("ex-FAANG") without a thesis-relevant connection score low. | `deck-review` |
| 7 | **Ask specificity** | 5 | Round size, optionally valuation expectation, use of funds breakdown, milestones the raise unlocks, runway months. "Raising $X to do Y by Z" — no hand-waving. An absent or vague ask is a critical flag. | `deck-narrative` |
| 8 | **Design polish** | 5 | Visual hierarchy, slide density (≤6 bullets and ≤30 words per content slide is the working bar), chart legibility at projection scale, consistent typography/palette, no chartjunk, no walls of text. Decks are seen, not read — design is content. Critique runs against the **rendered PDF**, not the markdown source. | `deck-design` |
| | **Total** | **40** | Advance threshold: **≥35** | |

**Weight rationale**:
- Narrative + ask + market = **16/40 = 40%**. A pitch deck is fundamentally a persuasive document with a request.
- Differentiates from `pub` (rigor + evidence dominate; calibrated for academic credibility) and `memo` (clarity-of-recommendation dominates; calibrated for internal IC decision-making).

## Critic dimension ownership

Critics fill only the rubric dimensions they own. Other dimensions remain `null` in the critic's `_summary.md`. The reviser aggregates per-dimension as the **mean of non-null critic scores**.

| Critic | Owns dimensions | Notes |
|---|---|---|
| `deck-review` | 2, 5, 6 | General reviewer; can fill any dimension as a fallback if the specialist critic is skipped, but primary ownership is here. |
| `deck-narrative` | 1, 7 | Arc + ask — read the deck end to end as a single argument. |
| `deck-market` | 3, 4 | Market math + competitive differentiation — verify arithmetic, check framing. |
| `deck-design` | 8 (markdown-source density / hierarchy / consistency) | Visual quality — critique against the rendered PDF, not the source. |
| `deck-vision` | 8 (rendered-PDF density) + vision rubric v1–v6 | VLM critic over rendered PNGs; surfaces overflow, label cropping, axis legibility, palette adherence, mathtext artifacts, slide density. See `commands/deck-vision.md`. |

**Joint ownership of dim 8 (design polish)**: both `deck-design` and `deck-vision` contribute scores to dim 8 — `deck-design` evaluates source-side density and consistency signals (bullet counts, word density, mixed-typography heuristics), and `deck-vision` evaluates rendered-PDF density at projection scale (the VLM sees what the markdown source cannot expose, e.g. text that fits in the markdown but spills past the 16:9 safe area after Marp lays it out). The aggregator (`anvil/lib/critics.py::aggregate`) handles this cleanly via mean-of-non-null: when both critics score dim 8, the aggregated dim-8 score is the arithmetic mean of their two integer scores (rounded with banker's rounding). When only one critic runs, that critic's score stands alone. The two critics also contribute disjoint findings — `deck-design` flags source-side issues; `deck-vision` flags rendered-only defects.

In addition to dim 8, `deck-vision` owns six **vision-rubric dimensions** scored /5 each (vertical_overflow, label_cropping, axis_legibility, palette_adherence, mathtext_artifacts, slide_density). These six dims appear in the aggregated scorecard alongside the 8 main-rubric dimensions; the existing aggregator merges them via the same mean-of-non-null path with no schema or aggregation changes. See `anvil/lib/vision.py` and `commands/deck-vision.md` for the rubric definition.

If a critic sibling is missing at version `N` (e.g., operator skipped `design`), the reviser leaves that dimension's aggregate as `null` in `verdict.md` and notes the gap. A deck cannot reach `READY` with any main-rubric dimension still `null` — at minimum, the general `deck-review` must fill any dimensions no specialist owns. Vision-rubric dimensions (v1–v6) are gated separately: a deck without a `deck-vision` pass is not yet validated against rendered-only defects, and the reviser surfaces this as a gap in `_revision-log.md`.

## Scoring guidance

For each dimension, the critic assigns an integer between 0 and the dimension's weight. A short justification accompanies each score (1–3 sentences pointing to specific slides or evidence in the deck).

Suggested calibration:
- **Full weight** — meets the standard convincingly; a sophisticated investor would have no substantive objection on this dimension.
- **~75% of weight** — meets the standard with a defensible gap or one specific weakness noted.
- **~50% of weight** — partial; multiple gaps or one significant weakness.
- **~25% of weight** — present but inadequate; major rework needed.
- **0** — absent or actively misleading.

## Advance threshold

- **≥35/40** — advance to `READY` (or to next step in the lifecycle).
- **<35/40** — block; revise.
- **Any critical flag set** — block regardless of total. The next revision must address the flagged issue specifically and the relevant critic(s) must re-evaluate the flag before the threshold check applies.

## Critical flags

A critical flag is an issue severe enough that **a sophisticated investor would immediately disqualify the deck**, regardless of how well other dimensions score. The four standing critical flags for pitch decks are:

1. **Fabricated traction.** A traction number (revenue, ARR, users, retention, LOIs, pilots, design partners, customer logos) that does not appear in the brief or refs. This is the most credibility-destroying error a deck can contain: an investor who diligences and discovers a number was made up will not take a follow-up meeting. Raised by `deck-audit`, `deck-market`, or `deck-review`.
2. **Fabricated team credentials.** A bio claim (prior role, prior exit, degree, advisory board affiliation, named hire) that does not appear in the brief or refs. Same disqualification dynamic as fabricated traction. Raised by `deck-audit` or `deck-review`.
3. **Market-math error.** TAM/SAM/SOM arithmetic that does not check out (multiplication wrong, units inconsistent, double-counted segments), OR top-down-only sizing presented as defensible without bottom-up validation. Raised by `deck-market` or `deck-audit`.
4. **Absent ask.** No specific round size, OR no use-of-funds breakdown, OR no runway-to-milestone framing. A deck without a clear ask is a deck that gives the investor permission to say "interesting, keep me posted." Raised by `deck-narrative` or `deck-review`.

The critic should also raise a flag for any other issue that, in its judgment, meets the standard above — the four examples above are starting points, not a closed set. The aggregated critical flag in the reviser's `verdict.md` is the **logical OR** of all critic critical flags.

## Verdict format

The reviser (consuming all critic siblings at `<thread>.{N}/`) writes an aggregated `verdict.md` at the top of the next version's revision plan (or the general reviewer writes a per-critic verdict in `.review/`). The format:

1. **Total score**: `XX / 40` (mean-aggregated per dimension across non-null critic scores).
2. **Decision**: `advance: true` or `advance: false`. (`advance: true` requires both `total ≥ 35` AND `no unresolved critical flag from any critic`.)
3. **Critical flags** (if any): bullet list, each with one-paragraph justification and the critic that raised it.
4. **Dimension summary**: a markdown table of per-dimension aggregate scores, the critics contributing each, and any null dimensions.
5. **Top 3 revision priorities** (if `advance: false`): the highest-leverage changes for the reviser to focus on.

## Output layout (per critic sibling)

```
<thread>.{N}.<tag>/
  verdict.md       (deck-review only — full reviewer verdict; specialist critics emit _summary.md instead)
  scoring.md       Per-dimension score + justification for owned dimensions
  comments.md      Slide-level comments keyed to deck.md slides (by slide number and heading)
  _summary.md      8-dim partial scorecard (owned dims scored, others null) + critical flag bool
  findings.md      Itemized findings: severity, slide ref, rationale, suggested fix
  _meta.json       { critic, role, started, finished, model }
  _progress.json   Phase state for this critic
```

For `deck-design` only:
```
<thread>.{N}.design/
  slides/          Per-slide PNGs rendered from deck.pdf (the artifact this critic actually evaluates)
  ... (all of the above)
```

The critic dir is **read-only once written** (state: `done` in its own `_progress.json`). Revisions consume it without modifying it.
