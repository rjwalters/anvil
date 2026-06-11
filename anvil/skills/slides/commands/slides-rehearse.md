---
name: slides-rehearse
description: Rehearser command for the slides skill. Deterministic-first time-budget and density check. Counts words per slide, estimates spoken time, flags density violations and time-budget overruns.
---

# slides-rehearse — Rehearser

**Role**: rehearser (time-budget + density check).
**Reads**: latest `<thread>/<thread>.{N}/deck.md` AND `<thread>/<thread>.{N}/notes/*.md` (the version dir is nested under the thread root per the artifact contract) AND `<thread>/BRIEF.md` (for `time_slot_minutes`).
**Writes**: `<thread>/<thread>.{N}.rehearse/` with `timing.md`, `density.md`, and `_progress.json`. Bare `<thread>.{N}/` / `<thread>.{N}.rehearse/` references below are shorthand for these nested paths.

This is the rehearsal critic — it does NOT produce a 1-40 rubric score (that's the reviewer's job). It produces two deterministic critical-flag verdicts (density flag and time flag) that the reviewer propagates.

## Why deterministic-first

Two of the three structural critical flags (density and time) are mechanical — word counts, bullet counts, and a spoken-time heuristic. The rehearser computes these deterministically (regex / wordcount / arithmetic) so the flag verdicts are reproducible. LLM judgment is reserved for one classification step: "is this figure trivial or non-trivial?" (which feeds the per-slide time estimate).

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md` under the thread root `<thread>/`.
- **Brief**: `<thread>/BRIEF.md` for `time_slot_minutes` frontmatter. If absent, defaults to 45 minutes and warns.
- **Per-thread overrides**: `<thread>/.anvil.json` may set `time_per_slide_seconds_base` to override the default 90s base.

## Outputs

Nested under the thread root `<thread>/`, as a sibling of the `<thread>.{N}/` version dir under rehearsal:

```
<thread>.{N}.rehearse/
  timing.md        Per-slide and aggregate spoken-time estimates + time flag status
  density.md       Per-slide word/bullet counts + density flag status (listing every violation)
  _progress.json   Phase state with rehearse: done, for_version: <N>
```

**Atomicity** (issue #350, #376): the rehearse sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The three files (`timing.md`, `density.md`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.rehearse.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.rehearse/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.rehearse.tmp/` dir on disk that the next invocation's `cleanup_one_staging(<thread>.{N}.rehearse)` per-critic sweep removes; the final-named dir never exists in partial form. Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md` under the thread root `<thread>/`. Then **sweep a stale staging dir from a prior interrupt of THIS critic on THIS version** by invoking `anvil/lib/sidecar.py::cleanup_one_staging(<thread>.{N}.rehearse)` (the per-critic, parallel-safe sweep — issue #376). This removes ONLY a leftover `.<thread>.{N}.rehearse.tmp/` from a previously-killed run of this same critic on THIS version. Sibling critics' in-flight staging dirs under the same thread root are NOT touched (issue #350, #376). If `<thread>.{N}.rehearse/` exists (the atomic-rename contract guarantees the dir only exists when complete), exit early with a notice (idempotent).
2. **Resume check**: per the staged-sidecar shape introduced in issue #350, a partial rehearse left behind by a mid-cycle interrupt manifests as a leading-dot `.<thread>.{N}.rehearse.tmp/` directory; the step 1 sweep has already removed it. Backwards-compat: if a legacy pre-#350 `<thread>.{N}.rehearse/` exists without complete output, delete and re-run.
3. **Open the staged sidecar** for the rehearse dir by invoking the context manager `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.rehearse, required_files=["timing.md", "density.md", "_progress.json"])`. Every file write below MUST land **inside the yielded staging directory** (the path of the shape `.<thread>.{N}.rehearse.tmp/`), NOT inside the final `<thread>.{N}.rehearse/` path. On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name (issue #350). Then, **inside the staging dir**, initialize `_progress.json`: `phases.rehearse.state = in_progress`, `phases.rehearse.started = <ISO>`, `for_version: <N>`.
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

12. **Update `_progress.json`** inside the staging dir: `phases.rehearse.state = done`, `phases.rehearse.completed = <ISO>`. This is the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires `_progress.json` to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies every name in the required-files manifest exists in the staging dir, then atomically renames `.<thread>.{N}.rehearse.tmp/` → `<thread>.{N}.rehearse/`. The final-named dir only ever exists in **complete** form.
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

## Git sync (opt-in, off by default)

If the consumer repo carries `.anvil/config.json` with `git.commit_per_phase: true`, end this phase per the per-phase git commit/sync hook documented in `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo): after the staged-sidecar atomic rename (issue #350) lands the final-named `<thread>.{N}.rehearse/`, stage ONLY this command's own `<thread>.{N}.rehearse/` sidecar (never sibling critics' dirs — the narrow scope keeps the hook safe under parallel critic fan-out), commit as `anvil(slides/rehearse): <thread>.{N} [<state>]` (the bracket carries the thread's derived state per SKILL.md §State machine — `REHEARSED` when the rehearsal lands on the latest AUDITED version), and push when `git.push` is also `true`. Git failures (not a git repo, commit failure, offline push) emit a one-line warning and continue — the rehearsal still reports its timing verdict unchanged; artifact-on-disk is the source of truth. When `.anvil/config.json` is absent or `git.commit_per_phase` is false/absent, skip this step entirely — behavior is byte-identical to a pre-#426 install (default off).
