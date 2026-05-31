---
name: memo-draft
description: Drafter command for the memo skill. Produces a new memo version directory from a brief (or, on revise-from-feedback path, from a prior version + critic siblings).
---

# memo-draft — Drafter

**Role**: drafter.
**Reads**: `<thread>/BRIEF.md` (if present), `<thread>/refs/**` (if present). For revise-from-feedback path: also the latest `<thread>.{N}/` and all `<thread>.{N}.*/` critic siblings.
**Writes**: `<thread>.{N+1}/` containing `memo.md`, optional `exhibits/`, and `_progress.json`.

## Inputs

- **Thread slug** (positional argument): identifies the thread within the cwd portfolio.
- **Brief** (`<thread>/BRIEF.md`): freeform prose, optionally with YAML frontmatter. Recognized frontmatter keys (all optional): `company`, `sector`, `stage`, `check_size`, `recommendation_target` (one of `invest`/`pass`/`conditional`/`undecided`). Unrecognized keys are passed through to the drafter as context.
- **References** (`<thread>/refs/**`): any supporting material (decks, transcripts, exported financials). Treated as read-only context.
- **Prior version + critic siblings** (revise-from-feedback path only): in normal flow, revision is handled by `memo-revise`. `memo-draft` is the entry point for new threads. For threads where the user wants to start fresh from feedback (rare), this path is available — but `memo-revise` is preferred because it preserves the changelog mapping.

## Outputs

A new version directory:

```
<thread>.{N+1}/
  memo.md            Memo body (markdown)
  exhibits/          Inline tables, charts, source data referenced from memo.md (created as needed)
  _progress.json     Phase state with draft: done after successful write
```

For a new thread, `N+1 == 1` so the output is `<thread>.1/`.

## Procedure

1. **Discover thread state**: enumerate existing `<thread>.{N}/` dirs. Compute the next `N`.
2. **Resume check**: if `<thread>.{N+1}/_progress.json` exists with `draft.state == in_progress`, treat as a crashed prior run. Delete any partial `memo.md` and re-draft. If `draft.state == done`, the version is already drafted — exit early with a notice (this command is idempotent: it does not overwrite a completed draft).
3. **Read inputs**: load `BRIEF.md` (if present) and enumerate `refs/`. If revising from feedback, also load the prior version's `memo.md` and concatenate all critic siblings' `verdict.md` + `scoring.md` + `comments.md`.
4. **Initialize `_progress.json`**: write `phases.draft.state = in_progress`, `phases.draft.started = <ISO timestamp>`, `metadata.iteration = N+1`, `metadata.max_iterations` (inherit from `<thread>/.anvil.json` if set, else 4).
5. **Read `target_length`**: if `<thread>/.anvil.json` exists, read the optional `target_length` field per the SKILL.md §Length targets contract. Normalize to a `(min_words, max_words)` pair:
   - `{ "words": [W_min, W_max] }` → `(W_min, W_max)` directly.
   - `{ "pages": [P_min, P_max] }` → `(P_min * 600, P_max * 600)` using the documented 600-words/page conversion.
   - Missing, malformed, or both-keys-set → no target (fall back to current implicit behavior).
   If a target is set, inject it into the drafting prompt as a soft target using the exact wording: **"Target length: <min>–<max> words (~<min_pages>–<max_pages> pages at 600 words/page). Treat as a soft budget — material that earns its space may exceed; pad-prose that fills space MUST be cut."** Where the absent `pages` form is set, derive the page approximation from the word range (`min_pages = round(min_words/600)`, `max_pages = round(max_words/600)`). Where no target is set, omit this line from the prompt entirely.
6. **Draft the memo**: produce `memo.md` with:
   - **Header**: thread slug, date, iteration, author (model identifier).
   - **Executive summary** (3–5 sentences): the recommendation + the one-sentence ask.
   - **Thesis** (named, falsifiable): what must be true for the recommendation to hold.
   - **Evidence**: claims with sources. Inline citations are acceptable (footnote style or parenthetical); exhaustive reference list at the end is preferred for primary sources.
   - **Risks**: top 3–5 risks with mitigations or acknowledged residual exposure.
   - **Market & competitive framing**: sized to the artifact, not boilerplate.
   - **Financial reasoning**: unit economics, scenario math, sensitivity. Tables go in `exhibits/` and are referenced from this section.
   - **Recommendation**: the explicit ask, restated, with check size or scope.
7. **Create exhibits** (inline only — full figure generation belongs to `memo-figures`): any tables or simple inline data structures referenced from the body should land in `exhibits/` as `.md` or `.csv` files. Image generation is deferred to `memo-figures`.
8. **Update `_progress.json`**: `phases.draft.state = done`, `phases.draft.completed = <ISO timestamp>`.
9. **Report**: print the path to the new version dir and a one-line status (e.g., `Drafted acme-seed.1/ (memo.md: 1240 words, 2 exhibits)`). When `target_length` is set, also report whether the produced word count falls in-range (e.g., `... 1240 words, target 1800–2400 — under target`).

## Voice and style overrides

If `.anvil/skills/memo/voice.md` exists in the consumer repo, load it and apply its guidance during drafting. This is how a fund or author customizes voice without forking the skill.

## Idempotence and resumability

- A completed draft (`_progress.json.draft.state == done` AND `memo.md` exists) is never overwritten. Re-running `memo-draft <thread>` on a `DRAFTED` thread is a no-op with a notice.
- A crashed draft (`_progress.json.draft.state == in_progress` with no complete `memo.md`) is re-runnable after deleting any partial output.
- Validation is by file existence (does `memo.md` exist? is it non-empty?), not solely by the progress flag.

## `_progress.json` snippet

This command writes the version-dir shape documented in `anvil/lib/snippets/progress.md` (`.anvil/lib/snippets/progress.md` in an installed consumer repo). Specifically, after a successful draft:

```json
{
  "version": 1,
  "thread": "<slug>",
  "phases": {
    "draft": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  },
  "metadata": {
    "iteration": <N>,
    "max_iterations": 4
  }
}
```

Merge rule (shallow): read existing `_progress.json` if present, update only `phases.draft` and `metadata`, preserve all other fields. Use the read-merge-write recipe in `anvil/lib/snippets/progress.md`; use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
