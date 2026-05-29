---
name: slides-rehearse
description: Rehearser command for the slides skill. Deterministic-first time-budget and density check. Counts words per slide, estimates spoken time, flags density violations and time-budget overruns.
---

# slides-rehearse — Rehearser

**Role**: rehearser (time-budget + density check).
**Reads**: latest `<thread>.{N}/deck.md` AND `<thread>.{N}/notes/*.md` AND `<thread>/BRIEF.md` (for `time_slot_minutes`).
**Writes**: `<thread>.{N}.rehearse/` with `timing.md`, `density.md`, and `_progress.json`.

This is the rehearsal critic — it does NOT produce a 1-40 rubric score (that's the reviewer's job). It produces two deterministic critical-flag verdicts (density flag and time flag) that the reviewer propagates.

## Why deterministic-first

Two of the three structural critical flags (density and time) are mechanical — word counts, bullet counts, and a spoken-time heuristic. The rehearser computes these deterministically (regex / wordcount / arithmetic) so the flag verdicts are reproducible. LLM judgment is reserved for one classification step: "is this figure trivial or non-trivial?" (which feeds the per-slide time estimate).

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md`.
- **Brief**: `<thread>/BRIEF.md` for `time_slot_minutes` frontmatter. If absent, defaults to 45 minutes and warns.
- **Per-thread overrides**: `<thread>/.anvil.json` may set `time_per_slide_seconds_base` to override the default 90s base.

## Outputs

```
<thread>.{N}.rehearse/
  timing.md        Per-slide and aggregate spoken-time estimates + time flag status
  density.md       Per-slide word/bullet counts + density flag status (listing every violation)
  _progress.json   Phase state with rehearse: done, for_version: <N>
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md`. If `<thread>.{N}.rehearse/_progress.json.rehearse.state == done` and both `timing.md` + `density.md` exist, exit early with a notice (idempotent).
2. **Resume check**: if `rehearse.state == in_progress` without complete output, delete partial files and re-run.
3. **Initialize `_progress.json`**: `phases.rehearse.state = in_progress`, `phases.rehearse.started = <ISO>`, `for_version: <N>`.
4. **Parse the deck**: split `deck.md` on `---` slide separators. Skip the Marp frontmatter block at the top (everything before the first slide-delimiting `---` that follows the frontmatter block). For each slide:
   - Slide number (1-indexed in slide order).
   - Slide title (first heading on the slide, or filename of paired notes file).
   - Body text (everything except the title, frontmatter, footer).
   - Bullet count (lines starting with `-`, `*`, or `1.`/`2.`/etc., at any nesting).
   - Word count of body (split on whitespace; exclude markdown syntax tokens like `**`, `*`, `[`, `]`, `(`, `)`).
   - Figure count (matches of `![...](figures/...)` or fenced ```mermaid blocks).
5. **Pair each slide with its notes file**: `notes/<NN>-*.md` where `<NN>` is the zero-padded slide number. Count notes words.
6. **Density check** (deterministic):
   - For each slide, check `body_word_count > 50` OR `bullet_count > 7`.
   - For each violation, record: slide number, title, word count, bullet count, the rule violated.
   - Set the **density flag** if any violation exists.
7. **Time estimate per slide** (heuristic — deterministic given a "trivial / non-trivial" figure classification):

   ```
   slide_seconds = base + (non_trivial_figures * 30) + (notes_words * 1.5)
   slide_seconds = min(slide_seconds, 180)  # cap at 3 minutes / slide
   ```

   Where:
   - `base = 90` (default; configurable via `<thread>/.anvil.json` `time_per_slide_seconds_base`).
   - `non_trivial_figures` = number of figures on the slide judged "non-trivial" (architecture diagrams, results plots, math derivations). The classification is an LLM call per slide; trivial figures (decorative images, simple title-slide elements) don't add time.
   - `notes_words` = word count of the paired `notes/<NN>-*.md` (the more the speaker plans to say, the longer the slide).
   - The 180-second cap reflects that even deep-dive technical slides rarely sustain attention beyond 3 minutes; if the heuristic suggests more, the slide should be split (which the density check usually catches independently).

8. **Aggregate time estimate**: `total_seconds = sum(slide_seconds)`. Convert to minutes for reporting.
9. **Time flag check**: read `time_slot_minutes` from `<thread>/BRIEF.md` frontmatter. If `total_minutes > time_slot_minutes * 1.10`, set the **time flag**.
10. **Write `density.md`**:

    ```markdown
    # Density check for <thread>.<N>

    ## Summary
    - Total slides: <N>
    - Density violations: <N>
    - Density flag: <SET / NOT SET>

    ## Violations (if any)
    | Slide | Title              | Word count | Bullet count | Rule violated      |
    |-------|--------------------|------------|--------------|--------------------|
    | 7     | Architecture overview | 62      | 5            | >50 words          |
    | 14    | Results            | 38         | 9            | >7 bullets         |

    ## Per-slide counts (full table)
    | Slide | Title              | Word count | Bullet count |
    |-------|--------------------|------------|--------------|
    | 1     | Title              | 12         | 0            |
    | 2     | Hook               | 28         | 3            |
    | ...   | ...                | ...        | ...          |
    ```

11. **Write `timing.md`**:

    ```markdown
    # Time-budget check for <thread>.<N>

    ## Summary
    - Declared slot: <M> minutes (from BRIEF.md `time_slot_minutes`)
    - Estimated talk duration: <X> minutes (<X*60> seconds)
    - Fit: <Y>% of slot (target ≤100%, hard cap 110%)
    - Time flag: <SET / NOT SET>

    ## Per-slide time estimates
    | Slide | Title              | Base | Figures (non-trivial) | Notes words | Estimated seconds |
    |-------|--------------------|------|------------------------|-------------|-------------------|
    | 1     | Title              | 90   | 0                      | 18          | 117 (capped at 180) |
    | 2     | Hook               | 90   | 0                      | 42          | 153                 |
    | ...   | ...                | ...  | ...                    | ...         | ...                 |

    ## Heuristic
    slide_seconds = base + (non_trivial_figures * 30) + (notes_words * 1.5), capped at 180s.
    Base = 90s (overridable via .anvil.json `time_per_slide_seconds_base`).

    ## Recommended cuts (if time flag set)
    <Bulleted list of the lowest-density / lowest-priority slides as cut candidates, by slide number and title.>
    ```

12. **Update `_progress.json`**: `phases.rehearse.state = done`, `phases.rehearse.completed = <ISO>`.
13. **Report**: print a one-line status (e.g., `Rehearsed kdd-2026-keynote.1 → kdd-2026-keynote.1.rehearse/ (22 slides, 47 minutes for 45-min slot, density flag SET, time flag SET)`).

## Heuristic calibration note

The 90s-base + 30s-per-figure + 1.5s-per-notes-word formula is plausible but inherently rough — actual rehearsal with the speaker is the ground truth. The skill ships this heuristic as a default and exposes `time_per_slide_seconds_base` for tuning. A speaker who runs through their decks faster or slower than average should override the base after their first real rehearsal.

The heuristic is intentionally conservative on the high side (notes_words * 1.5 assumes a moderate-paced delivery; an animated speaker may run faster). Better to flag a deck as over-budget and have rehearsal show it fits, than to under-flag and have the talk overrun in front of a live audience.

## Idempotence and resumability

- A completed rehearse (`rehearse.state == done` AND both files exist) is never re-run. Re-invoking is a no-op with a notice.
- A crashed rehearse is re-runnable after deleting partial output.

## Notes for the rehearser agent

- **Be deterministic where possible.** Word counts, bullet counts, and the arithmetic are not judgment calls. Compute them precisely.
- **The one LLM call per slide** ("trivial / non-trivial figure?") is the only place judgment is exercised. Use a conservative bar: a one-slide-of-the-architecture diagram is non-trivial; a corporate logo on the title slide is trivial.
- **Don't double-count.** A figure embedded as a Mermaid code block AND referenced as an image is one figure, not two.
- **The recommended cuts list is generative, not deterministic.** If the time flag is set, suggest the lowest-priority slides for the reviser to consider cutting. The reviser ultimately decides.

## `_progress.json` snippet (rehearse sibling)

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "rehearse": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Merge rule (shallow): preserve fields not touched by this command. See `anvil/lib/snippets/progress.md` for the full read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC format. This sibling SHOULD declare `scorecard_kind: human-verdict` in `_meta.json` per `anvil/lib/snippets/scorecard_kind.md` (the reviewer and reviser consume these outputs as narrative, not as programmatic partial scorecards).
