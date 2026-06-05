---
name: memo-draft
description: Drafter command for the memo skill. Produces a new memo version directory from a brief (or, on revise-from-feedback path, from a prior version + critic siblings).
---

# memo-draft — Drafter

**Role**: drafter.
**Reads**: `<thread>/BRIEF.md` (if present), the resolved refs-dir list returned by `anvil/skills/memo/lib/refs_resolver.py::resolve_refs_dirs(<thread_dir>)` — `<thread>/refs/**` for the legacy single-thread shape; plus `<portfolio>/research/**` for the portfolio-shared shape (issue #280) when a sibling `<portfolio>/research/` directory exists. For revise-from-feedback path: also the latest `<thread>.{N}/` and all `<thread>.{N}.*/` critic siblings.
**Writes**: `<thread>.{N+1}/` containing `<thread>.md`, optional `exhibits/`, and `_progress.json`.

## Inputs

- **Thread slug** (positional argument): identifies the thread within the cwd portfolio.
- **Brief** (`<thread>/BRIEF.md`): freeform prose, optionally with YAML frontmatter. Recognized frontmatter keys (all optional): `company`, `sector`, `stage`, `check_size`, `recommendation_target` (one of `invest`/`pass`/`conditional`/`undecided`). Unrecognized keys are passed through to the drafter as context. If no `BRIEF.md` is present, the user can scaffold one by copying `templates/BRIEF.fresh.md.example` (new-thread case) or `templates/BRIEF.migration.md.example` (migrate-from-prior-pipeline case) into `<thread>/BRIEF.md` and editing in place — this command does not write a brief on the user's behalf.
- **References** (resolved via `anvil/skills/memo/lib/refs_resolver.py::resolve_refs_dirs(<thread_dir>)`): the per-thread `<thread>/refs/**` AND, when the thread lives under a portfolio dir with a sibling `<portfolio>/research/` directory (issue #280), the portfolio-level `<portfolio>/research/**` evidence pool. Any supporting material (decks, transcripts, exported financials, comp matrices, vertical briefs, case studies). Treated as read-only context. Per-thread precedence on filename collision is the drafter's responsibility (pick-first when iterating by basename).
- **`<thread>.0.perspective/` or latest `<thread>.{N}.perspective/`** (optional, load-bearing if present): pre-draft external-substrate sibling produced by `memo-perspective`. When present, the drafter reads `notes.md` (narrative synthesis: comparable / market positioning + gaps) and `candidates.md` (structured comparables / cited research / market reports / customer evidence / regulatory entries with source URLs) and uses them as context for the Market & competitive framing, Evidence, Risks, and Financial reasoning sections. Per `anvil/lib/snippets/perspective.md` §"State-machine non-gating", absence does NOT block drafting — the drafter proceeds normally without a perspective sibling, exactly as memo threads have always done. The perspective sibling is opt-in input, not required output.
- **Prior version + critic siblings** (revise-from-feedback path only): in normal flow, revision is handled by `memo-revise`. `memo-draft` is the entry point for new threads. For threads where the user wants to start fresh from feedback (rare), this path is available — but `memo-revise` is preferred because it preserves the changelog mapping.

## Outputs

A new version directory:

```
<thread>.{N+1}/
  <thread>.md            Memo body (markdown)
  exhibits/          Inline tables, charts, source data referenced from <thread>.md (created as needed)
  _progress.json     Phase state with draft: done after successful write
```

For a new thread, `N+1 == 1` so the output is `<thread>.1/`.

## Procedure

1. **Discover thread state**: enumerate existing `<thread>.{N}/` dirs. Compute the next `N`.
2. **Resume check**: if `<thread>.{N+1}/_progress.json` exists with `draft.state == in_progress`, treat as a crashed prior run. Delete any partial `<thread>.md` and re-draft. If `draft.state == done`, the version is already drafted — exit early with a notice (this command is idempotent: it does not overwrite a completed draft).
3. **Read inputs**: load `BRIEF.md` (if present) and enumerate the **resolved refs-dir list** returned by `anvil/skills/memo/lib/refs_resolver.py::resolve_refs_dirs(<thread_dir>)` — `[<thread>/refs/]` for the legacy single-thread shape, OR `[<thread>/refs/, <portfolio>/research/]` for the portfolio-shared shape (issue #280) when a sibling `<portfolio>/research/` directory exists. **Read all text-readable files in the resolved list (markdown `.md`, plain text `.txt`, JSON `.json`) into context as source-of-truth for claims in their domain** (CVs for biographical claims, filings for sized public claims, papers for technical-claim citations, transcripts for quotation/tone, emails for traction claims, portfolio-level vertical briefs / comp matrices / case studies for cross-thread market context, strongman files for thesis / counter-argument substrate per the §"Strongman drafter contract" below). **Per-thread precedence on filename collision**: when the same basename exists in both `<thread>/refs/` and `<portfolio>/research/`, the per-thread copy wins (the resolver returns it first; the drafter picks the first match when iterating by basename — a thread that wants to override a portfolio-level fact with its own copy uses this hook). If a claim conflicts with the content of a source-of-truth document anywhere in the resolved list (per-thread `refs/` or portfolio-level `research/`), **the `refs/` document wins** — the same precedence rule as the pre-#280 contract, extended to apply to portfolio-level `research/` source-of-truth materials too — the drafter MUST either rewrite the claim to agree with the source or flag the conflict explicitly in prose.

   **Strongman drafter contract (issue #330)**: when `strongman-for.md` and/or `strongman-against.md` files are present anywhere in the resolved refs-dir list (per-thread `<thread>/refs/`, per-thread `<thread>/refs/<topic>/`, or portfolio-level `<portfolio>/research/<topic>-analysis/` — see SKILL.md §"Source-of-truth materials" §"Strongman scoping convention" for the scoping rules), the drafter:

   - Reads the file(s) as **authoritative load-bearing substrate**, with the same precedence rule as other source-of-truth materials (strongman content wins on contradiction with the brief or with the drafter's prior context — the drafter MUST rewrite the claim to agree with the strongman or flag the conflict explicitly).
   - For each `strongman-against.md` present, identifies the **named load-bearing objections** / counter-arguments inside it (the strongman author named them as numbered objections, headings, or bulleted lists — the file's structure is the contract; the drafter is NOT re-deriving them).
   - Ensures the produced draft either:
     - **Directly addresses each named objection** in prose with reasoning that engages the objection on its merits, OR
     - **Explicitly scopes the objection out of the memo's claim set** (e.g., "we acknowledge X as a risk but the memo focuses on Y", or "the FinFET mask cost is the subject of a separate analysis and is treated as out-of-scope here").
   - Does NOT simply ignore the file — the reviewer at `memo-review` step 4g will enumerate the named objections, classify the memo's treatment of each as `ADDRESSED` / `PARTIALLY_ADDRESSED` / `NOT_ADDRESSED`, and a `NOT_ADDRESSED` finding on a load-bearing objection is a critical-flag candidate that forces `advance: false`. Ignoring the file produces a predictable dim 3 deduction; addressing the objections (or scoping them out) is the load-bearing drafter contract.
   - For each `strongman-for.md` present, reads the file as **load-bearing context for the thesis statement** and ensures the memo's thesis aligns with the strongest version of its own argument (calibration substrate for dim 2 *Thesis coherence*). The reviewer at step 5 will note dim 2 alignment in its scoring justification; the drafter's job is to make the alignment hold (e.g., preserving load-bearing framings or named noun phrases from `strongman-for.md` through to the thesis statement and recommendation).

   The strongman files coexist with other source-of-truth materials in the same `refs/` (or `research/<topic>-analysis/`) directory; the drafter cites them inline as `[refs/strongman-against.md]` (per-thread) or `[research/<topic>-analysis/strongman-against.md]` (portfolio-level) when surfacing a counter-argument the memo addresses or scopes out, following the existing `[refs/<file>]` / `[research/<file>]` citation-token convention. Absence of strongman files is the legacy case: the drafter proceeds normally without strongman substrate, exactly as memo threads have always done (the contract is opt-in by file presence, byte-identical to pre-#330 behavior for threads without strongman files). For **PDF refs** (`.pdf`), call `anvil/skills/memo/lib/refs_pdf.py::check_pdftotext_available()`; when it returns `True`, also extract each PDF's text via `extract_pdf_text(<path>.pdf)` (the function takes any `Path`, so per-thread `<thread>/refs/*.pdf` AND portfolio-level `<portfolio>/research/*.pdf` are both in scope) and read the extracted text into context **as authoritative source-of-truth content** alongside the `.md` / `.txt` / `.json` path above. When `check_pdftotext_available()` returns `False` — or when extraction returns an empty string (image-based / scanned PDF) — the drafter falls back to the **v0 presence-only path** described next, **exactly** as if the PDF had been an image: this is the load-bearing graceful-degradation contract documented in `anvil/skills/memo/lib/refs_pdf.py` and SKILL.md §"Source-of-truth materials". For non-text files (images `.png` / `.jpg`, and PDFs when the optional extraction path above is unavailable), the drafter is informed of their presence by filename and respects the rule: "if you make a claim about the subject of `<file>`, you SHOULD NOT make it unless you can verify it against `BRIEF.md` content the operator has surfaced; otherwise add a `# TODO: verify against <refs-dir-basename>/<file>` note in prose." Cite source-of-truth files inline as `[refs/<file>]` for per-thread hits and `[research/<file>]` for portfolio-level hits (issue #280) so the reviewer can trace them and surface WHICH layer the evidence came from; this hook is honored as if it were an inline footnote (see step 6 *Evidence* below). The presence of citation-stub-shaped files (`<key>.md` carrying `# TODO: source for <claim>`) in the same directory is unaffected — both file-roles coexist per SKILL.md §"Source-of-truth materials". **Optional perspective context**: enumerate `<thread>.*.perspective/` siblings and, if any exist, load the latest one's `notes.md` and `candidates.md` as **load-bearing context** for the Market & competitive framing, Evidence, Risks, and Financial reasoning sections — anchor ids in `candidates.md` (e.g., `#acme-series-a-2024`) are stable references the drafter can cite in prose ("comparable framing from perspective `#acme-series-a-2024`") or surface to the reviewer via inline `[refs/<file>]`-shaped pointers when the candidate's source field names a refs document. The perspective sibling does NOT extend the no-fabrication contract — entries the drafter pulls into memo prose must still respect the brief-vs-refs precedence above (refs wins on contradiction); the perspective sibling is a verified-substrate aid that helps the drafter cite candidates the brief or refs already attest to. If no perspective sibling exists, proceed normally: drafting is non-gating on perspective per `anvil/lib/snippets/perspective.md` §"State-machine non-gating". If revising from feedback, also load the prior version's `<thread>.md` and concatenate all critic siblings' `verdict.md` + `scoring.md` + `comments.md`.
4. **Initialize `_progress.json`**: write `phases.draft.state = in_progress`, `phases.draft.started = <ISO timestamp>`, `metadata.iteration = N+1`, `metadata.max_iterations` (default 4). Also resolve and record `metadata.target_length_resolved` per step 5 — the resolution must happen before the prompt is built so the resolved range is in scope for both the prompt injection and the `_progress.json` provenance write.
5. **Resolve `target_length` for v{N+1}**: read the matching `documents:` entry from `<project>/BRIEF.md` (via `anvil/skills/memo/lib/project_brief.py::load_project_brief` + `ProjectBrief.document_for_slug(slug)`) per the SKILL.md §Length targets contract and apply the resolution order to the version about to be produced (`N+1`):
   1. If `target_length_overrides["<N+1>"]` is set and well-formed, use that range. Source: `"overrides.<N+1>"`.
   2. Else if the document's `target_length` is set and well-formed, use that range. Source: `"default"`.
   3. Else, no target. Source: `"none"`.

   Normalize the resolved range to a `(min_words, max_words)` pair:
   - `{ words: [W_min, W_max] }` → `(W_min, W_max)` directly.
   - `{ pages: [P_min, P_max] }` → `(P_min * 600, P_max * 600)` using the documented 600-words/page conversion.
   - Missing, malformed, both-keys-set, or `min > max` → no target (fall back to current implicit behavior).

   The BRIEF parser raises `ValueError` on a structurally invalid BRIEF; the drafter SHOULD propagate that error (the BRIEF schema is load-bearing). A missing BRIEF or a BRIEF that does not list this slug yields no target (source `"none"`, the resolver returns `None`).

   Write the resolved range and its source into `_progress.json.metadata.target_length_resolved` as part of step 4 — shape:

   ```json
   "target_length_resolved": {
     "min_words": 2000,
     "max_words": 2800,
     "source": "overrides.10"
   }
   ```

   When the source is `"none"`, write `{"source": "none"}` (omit `min_words`/`max_words`) or omit the field entirely; consumers tolerate both shapes.

   If a target is set, inject it into the drafting prompt as a soft target using the exact wording: **"Target length: <min>–<max> words (~<min_pages>–<max_pages> pages at 600 words/page). Treat as a soft budget — material that earns its space may exceed; pad-prose that fills space MUST be cut."** Where the absent `pages` form is set, derive the page approximation from the word range (`min_pages = round(min_words/600)`, `max_pages = round(max_words/600)`). Where no target is set, omit this line from the prompt entirely.
5b. **Resolve `render_engine` for v{N+1}** (issue #320, optional per-document HTML/PDF engine pin): from the same BRIEF document entry resolved in step 5, read `BriefDocument.render_engine`. When set (one of `"weasyprint"`, `"xelatex"`, `"wkhtmltopdf"` — the parser already validated the closed set), persist it into `_progress.json.metadata.render_engine_requested` as part of step 4. When `None` / absent on the BRIEF entry, omit the field from `_progress.json.metadata`. The render step (9.5) reads this field at render time and threads it through to `render_gate.gate(render_engine=...)`; the render-gate honors the request when the named binary is on PATH and gracefully falls through to auto-priority otherwise (silent-with-record in `render_gate.reasons`). The field is **idempotent across draft and revise** — once written by the drafter, the reviser should re-resolve from BRIEF.md at v{N+1} time (the BRIEF may have been edited between draft and revise), but the field is read-once at render time so mid-thread BRIEF edits propagate naturally.
6. **Draft the memo**: produce `<thread>.md` with:
   - **Header**: thread slug, date, iteration, author (model identifier).
   - **Executive summary** (3–5 sentences): the recommendation + the one-sentence ask.
   - **Thesis** (named, falsifiable): what must be true for the recommendation to hold.
   - **Evidence**: claims with sources. Inline citations are acceptable (footnote style or parenthetical); exhaustive reference list at the end is preferred for primary sources.

     **Citation-hook contract.** Every **named author-year citation** (e.g., "Levenson et al., 2006") and every **specific load-bearing quantitative claim** that anchors an argument (dollar amounts, percentages, dates, multipliers) MUST carry at least one of the following hooks:

     - **(a) Inline footnote** naming the source — sufficient on its own.
     - **(b) `<thread>/refs/<key>.md` stub** — created at the thread level (not the version level — see SKILL.md §Citation stubs). A stub MAY be as minimal as a single line `# TODO: source for <claim>`; the stub's *existence* is the contract, its *completeness* is not.
     - **(c) In-prose hedge** — order-of-magnitude or rough figures that the prose itself labels as estimates ("reportedly", "estimated", "roughly", "order of", "~") are exempt from the footnote/stub requirement but MUST be hedged in the prose itself.

     The reviewer treats absent hooks for load-bearing claims (no footnote, no `refs/` stub, no in-prose hedge) as a dim 3 *Evidence quality* deduction; see `rubric.md` §"Citation hooks (dim 3)" for the per-instance deduction rule. Hedged estimates do NOT carry a deduction.

     **Source-of-truth refs as authoritative hooks.** When the resolved refs-dir list (per-thread `<thread>/refs/` plus optional portfolio-level `<portfolio>/research/` per issue #280) contains an author-supplied **source-of-truth** material (e.g., `cv.pdf`, `filing-s1.pdf`, `transcript-foo.md`, `strongman-for.md`, `strongman-against.md` per-thread, or `00-intro.md`, `comps/silicon-comp-matrix.md`, `case-studies/acme.md`, `<topic>-analysis/strongman-against.md` portfolio-level — see SKILL.md §"Source-of-truth materials"), a claim that carries an inline `[refs/<file>]` (per-thread) or `[research/<file>]` (portfolio-level) pointer is honored by the reviewer **as if it had an inline footnote**. The reviewer will further back-check at least one claim per source-of-truth refs-document type against the underlying source (see `rubric.md` §"Refs back-check (dim 3)"). A claim backed by either pointer that the reviewer finds **contradicted** by the underlying source is a critical-flag candidate — the drafter should treat source-of-truth documents as authoritative when drafting and re-check before citing. **Per-thread precedence**: when a basename collision exists (e.g., per-thread `refs/cv.pdf` AND portfolio-level `research/cv.pdf`), use the `[refs/cv.pdf]` token to commit to the per-thread copy (the resolver's pick-first behavior makes this unambiguous); cite the portfolio-level copy explicitly via `[research/cv.pdf]` only when the basename is unique to the portfolio level.
   - **Risks**: top 3–5 risks with mitigations or acknowledged residual exposure.
   - **Market & competitive framing**: sized to the artifact, not boilerplate.
   - **Financial reasoning**: unit economics, scenario math, sensitivity. Tables go in `exhibits/` and are referenced from this section.
   - **Recommendation**: the explicit ask, restated, with check size or scope.
7. **Create exhibits** (inline only — full figure generation belongs to `memo-figures`): any tables or simple inline data structures referenced from the body should land in `exhibits/` as `.md` or `.csv` files. Image generation is deferred to `memo-figures`.
8. **Update `_progress.json`**: `phases.draft.state = done`, `phases.draft.completed = <ISO timestamp>`.
9. **Report**: print the path to the new version dir and a one-line status (e.g., `Drafted acme-seed.1/ (acme-seed.md: 1240 words, 2 exhibits)` — the body filename echoes the thread slug per #295). When `target_length` is set, also report whether the produced word count falls in-range (e.g., `... 1240 words, target 1800–2400 — under target`).
9.5. **Invoke `memo-render` (optional, non-blocking)**: after the draft is written and `phases.draft.state == done` is recorded (step 8), invoke `memo-render <thread>` to render `<thread>.md` → `<thread>.pdf` and write the render-gate findings into `_progress.json.phases.render` + `_progress.json.render_gate`. This step is the lifecycle wiring shipped by Epic #158 Phase 3 (issue #190).

   **Non-blocking by design.** A missing renderer (no pandoc on PATH, no HTML/PDF engine), a render-gate finding (placeholder hit, missing image ref, overflow warning, page-fit out of range), or even a hard pandoc failure does NOT abort `memo-draft`. The drafter still reports `Drafted <thread>.{N}/...` per step 9. The render outcome is recorded in `_progress.json.phases.render` and `_progress.json.render_gate` for the operator to surface and for the Phase 4 reviewer to read in `_summary.md.render_gate`.

   **What this preserves.** Render is a **sub-step of `DRAFTED`**, NOT a new state — SKILL.md §"State machine" still derives `DRAFTED` from `phases.draft == done`. A `<thread>.{N}/` with `phases.draft == done` but no `phases.render` block is a fully legal `DRAFTED` state (every memo version drafted before Epic #158 / Phase 3 has this shape). This step is additive and backwards-compat.

   **When to skip the call.** Two cases:
   - If `memo-render` is not on PATH (consumer hasn't installed Anvil's Phase 3 commands yet), the drafter silently skips this step — no failure, no info-level note, just no render. The drafter's contract is "produce a markdown memo"; rendering is an opt-in extension.
   - If the consumer has explicitly disabled rendering via a future BRIEF.md project-level knob (e.g., `render: skip` at the top of the frontmatter — NOT shipped in Phase 3), skip the call. This is a forward-compatibility note; no config-reading is required in Phase 3.

   See `commands/memo-render.md` §"Failure modes" for the full enumeration of non-blocking failure shapes and `commands/memo-render.md` §"Composability with `memo-draft` and `memo-revise`" for the design contract.

## Voice and style overrides

If `.anvil/skills/memo/voice.md` exists in the consumer repo, load it and apply its guidance during drafting. This is how a fund or author customizes voice without forking the skill.

## Idempotence and resumability

- A completed draft (`_progress.json.draft.state == done` AND `<thread>.md` exists) is never overwritten. Re-running `memo-draft <thread>` on a `DRAFTED` thread is a no-op with a notice.
- A crashed draft (`_progress.json.draft.state == in_progress` with no complete `<thread>.md`) is re-runnable after deleting any partial output.
- Validation is by file existence (does `<thread>.md` exist? is it non-empty?), not solely by the progress flag.

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

`metadata.target_length_resolved` is the resolved target this draft was authored against, with `source` provenance — see step 5 for the resolution rules and the three documented source values (`"overrides.<N>"`, `"default"`, `"none"`). The reviewer reads this field rather than re-resolving from `<project>/BRIEF.md`, preventing drift if BRIEF.md is edited between draft and review. The field is optional — its absence is tolerated for legacy version dirs (reviewer falls back to re-resolution).

Merge rule (shallow): read existing `_progress.json` if present, update only `phases.draft` and `metadata`, preserve all other fields. Use the read-merge-write recipe in `anvil/lib/snippets/progress.md`; use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
