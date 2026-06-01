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
- **Brief** (`<thread>/BRIEF.md`): freeform prose, optionally with YAML frontmatter. Recognized frontmatter keys (all optional): `company`, `sector`, `stage`, `check_size`, `recommendation_target` (one of `invest`/`pass`/`conditional`/`undecided`). Unrecognized keys are passed through to the drafter as context. If no `BRIEF.md` is present, the user can scaffold one by copying `templates/BRIEF.fresh.md.example` (new-thread case) or `templates/BRIEF.migration.md.example` (migrate-from-prior-pipeline case) into `<thread>/BRIEF.md` and editing in place — this command does not write a brief on the user's behalf.
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
3. **Read inputs**: load `BRIEF.md` (if present) and enumerate `refs/`. **Read all text-readable files in `<thread>/refs/` (markdown `.md`, plain text `.txt`, JSON `.json`) into context as source-of-truth for claims in their domain** (CVs for biographical claims, filings for sized public claims, papers for technical-claim citations, transcripts for quotation/tone, emails for traction claims). If a claim conflicts with the content of a `refs/` source-of-truth document, **the `refs/` document wins** — the drafter MUST either rewrite the claim to agree with the source or flag the conflict explicitly in prose. For non-text files (PDFs `.pdf`, images `.png` / `.jpg`), the drafter is informed of their presence by filename and respects the rule: "if you make a claim about the subject of `refs/<file>`, you SHOULD NOT make it unless you can verify it against `BRIEF.md` content the operator has surfaced; otherwise add a `# TODO: verify against refs/<file>` note in prose." (Automated PDF text extraction is out of scope for v0 — see SKILL.md §"Source-of-truth materials".) Cite `refs/` source-of-truth files inline as `[refs/<file>]` so the reviewer can trace them; this hook is honored as if it were an inline footnote (see step 6 *Evidence* below). The presence of citation-stub-shaped files (`<key>.md` carrying `# TODO: source for <claim>`) in the same directory is unaffected — both file-roles coexist per SKILL.md §"Source-of-truth materials". If revising from feedback, also load the prior version's `memo.md` and concatenate all critic siblings' `verdict.md` + `scoring.md` + `comments.md`.
4. **Initialize `_progress.json`**: write `phases.draft.state = in_progress`, `phases.draft.started = <ISO timestamp>`, `metadata.iteration = N+1`, `metadata.max_iterations` (inherit from `<thread>/.anvil.json` if set, else 4). Also resolve and record `metadata.target_length_resolved` per step 5 — the resolution must happen before the prompt is built so the resolved range is in scope for both the prompt injection and the `_progress.json` provenance write.
5. **Resolve `target_length` for v{N+1}**: if `<thread>/.anvil.json` exists, read the optional `target_length` field per the SKILL.md §Length targets contract and apply the resolution order to the version about to be produced (`N+1`):
   1. If `target_length.overrides.v{N+1}` is set and well-formed, use that range. Source: `"overrides.v{N+1}"`.
   2. Else if `target_length.default` is set and well-formed, use that range. Source: `"default"`.
   3. Else if the top-level `target_length` is the legacy flat shape (`words` or `pages` key directly), use that range. Source: `"legacy_flat"`.
   4. Else, no target. Source: `"none"`.

   Normalize the resolved range to a `(min_words, max_words)` pair:
   - `{ "words": [W_min, W_max] }` → `(W_min, W_max)` directly.
   - `{ "pages": [P_min, P_max] }` → `(P_min * 600, P_max * 600)` using the documented 600-words/page conversion.
   - Missing, malformed, both-keys-set, or `min > max` → no target (fall back to current implicit behavior). A `target_length` with both flat (`words`/`pages`) and extended (`default`/`overrides`) keys at the top level is malformed — source `"none"`, no target.

   Write the resolved range and its source into `_progress.json.metadata.target_length_resolved` as part of step 4 — shape:

   ```json
   "target_length_resolved": {
     "min_words": 2000,
     "max_words": 2800,
     "source": "overrides.v10"
   }
   ```

   When the source is `"none"`, write `{"source": "none"}` (omit `min_words`/`max_words`) or omit the field entirely; consumers tolerate both shapes.

   If a target is set, inject it into the drafting prompt as a soft target using the exact wording: **"Target length: <min>–<max> words (~<min_pages>–<max_pages> pages at 600 words/page). Treat as a soft budget — material that earns its space may exceed; pad-prose that fills space MUST be cut."** Where the absent `pages` form is set, derive the page approximation from the word range (`min_pages = round(min_words/600)`, `max_pages = round(max_words/600)`). Where no target is set, omit this line from the prompt entirely.
6. **Draft the memo**: produce `memo.md` with:
   - **Header**: thread slug, date, iteration, author (model identifier).
   - **Executive summary** (3–5 sentences): the recommendation + the one-sentence ask.
   - **Thesis** (named, falsifiable): what must be true for the recommendation to hold.
   - **Evidence**: claims with sources. Inline citations are acceptable (footnote style or parenthetical); exhaustive reference list at the end is preferred for primary sources.

     **Citation-hook contract.** Every **named author-year citation** (e.g., "Levenson et al., 2006") and every **specific load-bearing quantitative claim** that anchors an argument (dollar amounts, percentages, dates, multipliers) MUST carry at least one of the following hooks:

     - **(a) Inline footnote** naming the source — sufficient on its own.
     - **(b) `<thread>/refs/<key>.md` stub** — created at the thread level (not the version level — see SKILL.md §Citation stubs). A stub MAY be as minimal as a single line `# TODO: source for <claim>`; the stub's *existence* is the contract, its *completeness* is not.
     - **(c) In-prose hedge** — order-of-magnitude or rough figures that the prose itself labels as estimates ("reportedly", "estimated", "roughly", "order of", "~") are exempt from the footnote/stub requirement but MUST be hedged in the prose itself.

     The reviewer treats absent hooks for load-bearing claims (no footnote, no `refs/` stub, no in-prose hedge) as a dim 3 *Evidence quality* deduction; see `rubric.md` §"Citation hooks (dim 3)" for the per-instance deduction rule. Hedged estimates do NOT carry a deduction.

     **Source-of-truth refs as authoritative hooks.** When `<thread>/refs/` contains an author-supplied **source-of-truth** material (e.g., `cv.pdf`, `filing-s1.pdf`, `transcript-foo.md` — see SKILL.md §"Source-of-truth materials"), a claim that carries an inline `[refs/<file>]` pointer is honored by the reviewer **as if it had an inline footnote**. The reviewer will further back-check at least one claim per source-of-truth refs-document type against the underlying source (see `rubric.md` §"Refs back-check (dim 3)"). A claim backed by `[refs/<file>]` that the reviewer finds **contradicted** by the underlying source is a critical-flag candidate — the drafter should treat `refs/` documents as authoritative when drafting and re-check before citing.
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
    "max_iterations": 4,
    "target_length_resolved": {
      "min_words": 1800,
      "max_words": 2400,
      "source": "default"
    }
  }
}
```

`metadata.target_length_resolved` is the resolved target this draft was authored against, with `source` provenance — see step 5 for the resolution rules and the four documented source values (`"overrides.v{N}"`, `"default"`, `"legacy_flat"`, `"none"`). The reviewer reads this field rather than re-resolving from `<thread>/.anvil.json`, preventing drift if the JSON is edited between draft and review. The field is optional — its absence is tolerated for legacy version dirs (reviewer falls back to re-resolution).

Merge rule (shallow): read existing `_progress.json` if present, update only `phases.draft` and `metadata`, preserve all other fields. Use the read-merge-write recipe in `anvil/lib/snippets/progress.md`; use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
