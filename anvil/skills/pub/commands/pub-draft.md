---
name: pub-draft
description: Drafter command for the pub skill. Produces a new paper version directory from a brief and any pre-draft litsearch sibling. Output is LaTeX (main.tex + refs.bib + figures/).
---

# pub-draft — Drafter

**Role**: drafter.
**Reads**: `<thread>/BRIEF.md`, `<thread>/refs/`, `<thread>/refs.bib` (if present), AND any `<thread>.0.litsearch/` sibling. For revise-from-feedback fallback path: also the latest `<thread>.{N}/` and all `<thread>.{N}.*/` critic siblings (but the canonical revise path is `pub-revise`).
**Writes**: `<thread>.{N+1}/` containing `main.tex`, `refs.bib`, `figures/`, and `_progress.json`.

## Inputs

- **Thread slug** (positional argument).
- **Brief** (`<thread>/BRIEF.md`): freeform prose with optional YAML frontmatter. Recognized frontmatter keys (all optional):
  - `title` — paper title
  - `author` / `authors` — author list (single string or list)
  - `affiliation` — author affiliation(s)
  - `venue` — target venue (e.g., `NeurIPS-2026`, `arXiv`, `IEEE-TPAMI`)
  - `documentclass` — override the default `anvil-paper` class (e.g., `neurips_2024`, supplied by the consumer repo via `.anvil/skills/pub/templates/`)
  - `anonymous` — boolean; if `true`, drafter renders author block as `Author Name(s) Withheld` and uses the class's anonymous mode
  - `claim` — one-sentence statement of the paper's main contribution
  - `keywords` — list of keywords
- **References** (`<thread>/refs/**`): any supporting material (datasets, prior drafts, transcripts, supplied source PDFs). Treated as read-only context.
- **Author-supplied bibliography** (`<thread>/refs.bib`): copied into the version dir as the starting `refs.bib`. Additional entries from the litsearch sibling are merged.
- **Litsearch sibling** (`<thread>.0.litsearch/`): if present, the drafter consumes `notes.md` (for positioning) and `candidates.bib` (entries available to cite).

## Outputs

```
<thread>.{N+1}/
  main.tex                 Paper body (LaTeX, uses templates/anvil-paper.cls or overridden documentclass)
  refs.bib                 Bibliography (BibTeX; merged from <thread>/refs.bib and litsearch candidates.bib as needed)
  figures/                 Figure assets and source scripts (created as needed)
    src/                   Optional source scripts (e.g., Python plot scripts)
    *.tex / *.pdf / ...    Rendered figures (TikZ .tex or rasterized; pub-figures fills these)
  _progress.json           Phase state with draft: done after successful write
```

For a new thread, `N+1 == 1` so the output is `<thread>.1/`. (Note: a `<thread>.0.litsearch/` may exist as a pre-draft sibling, but `<thread>.0/` is **not** a version dir.)

## Procedure

1. **Discover thread state**: enumerate existing `<thread>.{N}/` dirs. Compute the next `N`.
2. **Resume check**: if `<thread>.{N+1}/_progress.json.draft.state == done` AND `main.tex` + `refs.bib` exist, the version is already drafted — exit early with a notice (idempotent). If `draft.state == in_progress` with no complete `main.tex`, treat as a crashed prior run: delete any partial output and re-draft.
3. **Read inputs**: load `BRIEF.md` (or fail with a helpful message if missing — papers need at least a one-line claim and a target venue), enumerate `<thread>/refs/`, load `<thread>/refs.bib` if present, load `<thread>.0.litsearch/notes.md` and `candidates.bib` if present.
4. **Initialize `_progress.json`**: write `phases.draft.state = in_progress`, `phases.draft.started = <ISO timestamp>`, `metadata.iteration = N+1`, `metadata.max_iterations` (inherit from `<thread>/.anvil.json` if set, else 4).
5. **Choose documentclass**:
   - If brief frontmatter sets `documentclass`, use that (e.g., `\documentclass{neurips_2024}`). The consumer is responsible for dropping the matching `.cls` / `.sty` into `.anvil/skills/pub/templates/` in their repo.
   - Otherwise, use `\documentclass{anvil-paper}` (which is shipped at `anvil/skills/pub/templates/anvil-paper.cls`).
   - If `anonymous: true` in the brief, append the `anonymous` option: `\documentclass[anonymous]{anvil-paper}` (or pass through to the venue override's anonymous mechanism if known).
6. **Build `main.tex`**: instantiate `templates/main.tex.j2` with the brief's frontmatter, then write the paper body:
   - `\title{}`, `\author{}` (or `Author Name(s) Withheld`), `\date{}`.
   - `\begin{abstract} ... \end{abstract}` — 100–200 words; restates the claim, the method in one sentence, the key result, the contribution.
   - `\section{Introduction}` — motivates the problem, states the contribution explicitly (bullet list of named contributions is preferred over a single muddled paragraph), forward-references the experimental setup.
   - `\section{Related Work}` — positions against prior work as informed by the litsearch sibling's `notes.md`. Cites only entries that are in `refs.bib`. Honest engagement with the closest 1–3 papers per cluster; do not pad with weakly related work.
   - `\section{Method}` (or domain-appropriate equivalent: `\section{Approach}`, `\section{Theory}`, etc.) — describes the method with enough detail for an independent group to replicate (reproducibility dimension). Algorithms in `algorithm` environment where appropriate.
   - `\section{Experiments}` (or `\section{Results}`) — describes the experimental setup, then the results. Tables and figures are referenced from the body; the actual rendering is handled by `pub-figures` (figurer creates `figures/*.pdf` from `figures/src/*.py` or TikZ).
   - `\section{Discussion}` — interprets the results, names limitations honestly, discusses threats to validity.
   - `\section{Conclusion}` — restates the contribution and named results; no new arguments.
   - `\bibliographystyle{plainnat}` and `\bibliography{refs}` at the end (or whatever the venue override expects).
7. **Build `refs.bib`**:
   - Start with `<thread>/refs.bib` if present.
   - Merge entries from `<thread>.0.litsearch/candidates.bib` that the drafter actually cites in `main.tex`. Uncited entries stay in the litsearch sibling only — do not bloat `refs.bib` with unused entries.
   - Every `\cite{key}` in `main.tex` must have a matching `@type{key, ...}` in `refs.bib`. The drafter verifies this before marking `draft.state = done`.
8. **Create `figures/` skeleton**: `mkdir -p figures/src/`. Insert `\includegraphics{figures/<name>}` or `\input{figures/<name>.tex}` placeholders in the body where the brief or the structure calls for a figure. Actual figure generation is `pub-figures`'s job. If the brief supplies a `figures/src/` directory of scripts, copy them into the version dir's `figures/src/` so the figurer can pick them up.
9. **Update `_progress.json`**: `phases.draft.state = done`, `phases.draft.completed = <ISO timestamp>`.
10. **Report**: print the path to the new version dir and a one-line status (e.g., `Drafted q3-method.1/ (main.tex: 4200 words, refs.bib: 18 entries, 3 figure placeholders)`).

## Voice and style overrides

If `.anvil/skills/pub/voice.md` exists in the consumer repo, load it and apply its guidance during drafting. This is how a lab or author customizes voice without forking the skill.

## Documentclass overrides

The skill ships `templates/anvil-paper.cls`, a generic single-column class that compiles cleanly with `pdflatex` + `bibtex`. Venue-specific styles (NeurIPS, IEEE, ACM, arXiv) are NOT vendored — licensing and staleness make that fragile. To use a venue style:

1. The consumer drops the venue style file into `.anvil/skills/pub/templates/` in their own repo (e.g., `.anvil/skills/pub/templates/neurips_2024.sty`).
2. The brief sets `documentclass: neurips_2024` (or the appropriate value).
3. The drafter emits `\documentclass{neurips_2024}` (with options as needed) and the venue style is found by `pdflatex` because it lives in the consumer's `.anvil/` overlay.

This is the standard anvil override pattern — see `SKILL.md` "Defaults and overrides" and the consumer's `.anvil/skills/pub/` layout.

## Idempotence and resumability

- A completed draft (`_progress.json.draft.state == done` AND `main.tex` + `refs.bib` exist) is never overwritten. Re-running `pub-draft <thread>` on a `DRAFTED` thread is a no-op with a notice.
- A crashed draft (`_progress.json.draft.state == in_progress` with no complete `main.tex`) is re-runnable after deleting any partial output.
- Validation is by file existence (does `main.tex` exist? does `refs.bib` parse?), not solely by the progress flag.

## `_progress.json` snippet

Minimum schema this command writes (matches `SKILL.md`):

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

Merge rule: read existing `_progress.json` if present, update only `phases.draft` and `metadata`, preserve all other fields. Until `anvil/lib/progress.py` lands (see issue #10), each command embeds this minimal read-merge-write inline.
