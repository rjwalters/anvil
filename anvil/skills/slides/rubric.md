# Slides review rubric

The reviewer scores a talk deck against 8 weighted dimensions summing to **40**. The threshold to advance is **≥32/40**. Any of **three critical flags** short-circuits the verdict — the deck is blocked regardless of total score until the flagged issue is addressed.

The rubric is talk-tuned: **technical accuracy + pedagogical clarity + narrative arc + density (25/40 ≈ 62.5%)** dominate. A talk's primary job is to communicate true ideas clearly within a time budget. Visual polish matters but never outranks correctness or readability — an unreadable beautiful slide is worse than a plain readable one.

This weighting differs from `anvil:memo` (where thesis + evidence + risk dominate) and will differ from `anvil:deck` (where investability + persuasion + defensibility dominate). Same 8-dimension shape; different priorities.

## Dimensions

| # | Dimension | Weight | What it measures |
|---|---|---|---|
| 1 | **Technical accuracy** | 7 | Every claim — equation, statistic, attribution, mechanism — is correct and citable. Listeners cannot pause-and-verify. A single wrong equation in a recorded talk is a reputational tax that compounds. Highest weight by design; ties to the mandatory audit phase. |
| 2 | **Pedagogical clarity** | 6 | One idea per slide. Concept → example → implication scaffold where applicable. Jargon defined on first use. Talks teach; decks pitch. A listener who has not seen the material before should be able to follow the through-line. |
| 3 | **Narrative arc** | 6 | Hook → context → 2–4 substantive beats → takeaway → Q&A. A talk without a spine loses the audience by slide 8. Beat transitions are explicit (section dividers, recap slides). The final slide states the takeaway in plain language. |
| 4 | **Slide density / cognitive load** | 6 | Bullet-count caps respected. No "wall of text." 6×6 rule applied judiciously. Penalize density spikes (one outlier slide can break audience attention for the next three). Highest mechanical-reject reason. |
| 5 | **Visual quality** | 4 | Diagram clarity, consistent style, no chartjunk, sensible color choices. Lower weight than for `deck` (where polish is investability signal); a great talk on plain slides beats a polished talk on bad slides. |
| 6 | **Accessibility / readability at distance** | 4 | Minimum font size (24pt body / 18pt code), color-blind-safe palette, sufficient contrast, no critical info conveyed by color alone. Hard requirement for projected venues — a slide unreadable from row 20 is a slide nobody read. |
| 7 | **Presenter-notes completeness** | 4 | Every slide has speaker notes covering: what to say, transitions, anticipated questions, time-allocation. Critical for rehearsal AND for handoff (someone else may deliver the talk). |
| 8 | **Time-budget realism** | 3 | Slide count × estimated-time-per-slide fits the venue slot ±10%. Penalize "60 slides for a 45-minute slot" overruns. Rehearsal phase produces the empirical estimate; the reviewer scores the realism of the fit. |
| | **Total** | **40** | Advance threshold: ≥32 |

The four anchor dimensions (1–4) sum to **25/40 = 62.5%**, reflecting that the four pillars of a good talk are *true, clear, well-shaped, and digestible*. The presentation-craft dimensions (5–8) sum to 15/40 — necessary but never sufficient.

## Scoring guidance

For each dimension, the reviewer assigns an integer between 0 and the dimension's weight. A short justification accompanies each score (1–3 sentences pointing to specific evidence — slide number, excerpt, figure reference).

Suggested calibration:
- **Full weight** — meets the standard convincingly; a sophisticated reader would have no substantive objection.
- **~75% of weight** — meets the standard with a defensible gap or one specific weakness.
- **~50% of weight** — partial; multiple gaps or one significant weakness.
- **~25% of weight** — present but inadequate; major rework needed.
- **0** — absent or actively misleading.

## Advance threshold

- **≥32/40** AND no critical flag → advance to `READY` (or to next step in the lifecycle).
- **<32/40** → block; revise.
- **Any critical flag set** → block regardless of total. The next revision must address the flagged issue specifically; the reviewer (and auditor, for audit flags) must re-evaluate the flag before the threshold check applies.

## Critical flags

Three flag families are first-class for `slides`. Any one sets `advance: false` regardless of numeric score. The reviewer may additionally raise *ad hoc* flags for issues that meet the bar of "a sophisticated audience member would immediately stop taking the talk seriously" — these are starting points, not a closed set.

### 1. Audit flag (set by `slides-audit`, surfaced in reviewer's verdict)

The auditor enumerates every technical claim in `deck.md` and `notes/*.md` and assigns one of `supported` / `unsupported` / `wrong` / `ambiguous`. The audit flag fires when **any claim is verdicted `wrong`**. The reviewer reads `<thread>.{N}.audit/verdict.md` and propagates the flag into the review's `verdict.md`.

Examples:
- An equation with a wrong constant or sign.
- A cited statistic that doesn't match the cited source.
- An attribution to the wrong author / paper / year.
- A mechanism described in a way that contradicts established consensus (where established consensus exists).

The auditor's `unsupported` verdicts (claim is plausible but uncited) do **not** set the flag — they go into Dimension 1 (Technical accuracy) as a score reduction, not a block.

### 2. Density flag (set by `slides-rehearse`, surfaced in reviewer's verdict)

Any slide that violates the hard density caps:
- **>50 words** on the slide body (excluding title, footer, and presenter notes).
- **>7 bullets** at any level.

These caps are tight by design — a 50-word slide is already at the limit of what an audience can read while listening. Above the cap, attention fragments and the talk effectively pauses while listeners catch up.

Resolution: split the slide. The reviser distributes the content across 2+ slides, possibly inserting a "section divider" slide if the split reveals a beat boundary.

### 3. Time flag (set by `slides-rehearse`, surfaced in reviewer's verdict)

Projected total spoken time exceeds **110% of the venue slot** (declared in `BRIEF.md` frontmatter as `time_slot_minutes`).

Examples:
- 45-minute slot, deck projects to 52 minutes → flag fires (115%).
- 30-minute slot, deck projects to 32 minutes → no flag (107%).

Resolution: cut. The reviser identifies the lowest-priority beat (or a sub-point within a beat) and removes it, then re-runs `slides-rehearse` to confirm. A talk that overruns by 10%+ is materially worse than a talk that runs 10% short — overrun cuts into Q&A, the next speaker's slot, or the audience's break.

### Ad hoc flags

In addition to the three structural flags above, the reviewer should raise a flag for any other issue meeting the bar in their judgment. Common candidates:

- **Pedagogical regression** — a slide assumes background the brief said the audience does not have.
- **Live-demo dependency on flaky infrastructure** — a slide depends on a network call, external API, or unverified runtime that is likely to fail in the venue.
- **Unattributed quotation** — a quote on a slide without a speaker attribution.
- **PII / confidential data** — slide content includes information not cleared for the audience.

## Verdict format

The reviewer writes a `verdict.md` at the top of the review sibling dir with:

1. **Total score**: `XX / 40`.
2. **Decision**: `advance: true` or `advance: false`. (`advance: true` requires both `total >= 32` AND `no unresolved critical flag` — including the audit, density, and time flags pulled in from sibling critic dirs.)
3. **Critical flags** (if any): bullet list, each with one-paragraph justification. Pulled flags from `slides-audit` and `slides-rehearse` are labeled with their source.
4. **Dimension summary**: a markdown table of per-dimension scores (full detail lives in `scoring.md`).
5. **Top 3 revision priorities** (if `advance: false`): the highest-leverage changes the reviser should focus on.

## Output layout

```
<thread>.{N}.review/
  verdict.md       Top-level decision (see above)
  scoring.md       Per-dimension score + justification
  comments.md      Slide-level comments keyed to slide numbers (and to notes/<NN>-*.md filenames)
  _progress.json   { phases.review.state == done, for_version: <N> }
```

The reviewer dir is **read-only once written**. Revisions consume it without modifying it.

## Notes for the reviewer agent

- **Be honest, not encouraging.** The skill is not "polish the deck." It is "would this talk hold up in front of the declared audience for the declared time slot?" If the answer is no, score accordingly.
- **Trust the auditor and rehearser.** The audit flag, density flag, and time flag are upstream of the reviewer's judgment — pull them in from sibling dirs and propagate. Do not re-litigate them.
- **Pedagogy beats polish.** A clear plain slide beats a beautiful confusing one. Score Dimension 2 (Pedagogical clarity) before scoring Dimension 5 (Visual quality).
- **Notes matter for talks.** A slide without notes is a slide the speaker has not thought through. Penalize Dimension 7 hard for missing or perfunctory notes.
- **Time-budget realism is a real dimension, not a tiebreaker.** Score Dimension 8 from the rehearser's `timing.md` — do not eyeball.
