---
name: pub
description: Draft, review, revise, and audit research papers in LaTeX (compilable PDF) using the standard anvil lifecycle plus an optional read-only literature-search critic.
domain: pub
type: skill
user-invocable: false
---

# anvil:pub — Research papers (LaTeX)

The `pub` skill produces research papers as LaTeX sources that compile to a PDF at READY state. It follows the canonical anvil lifecycle — `draft → review → revise → audit → figures` — with one paper-specific addition: an optional pre-draft **literature-search** critic (`pub-litsearch`) that the drafter and the reviser can consume. Litsearch is a sibling critic, not a phase that gates the state machine.

Papers carry sharper expectations than memos around evidence and citation correctness, so the audit phase (`pub-audit`) is a first-class part of the lifecycle (not optional), and the rubric weights rigor / evidence / citation hygiene heavily.

## Artifact contract

A **paper thread** is a single research paper authored across one or more revisions, identified by a slug (e.g., `q3-method`, `acme-bench-2026`). Each thread occupies a portfolio directory:

```
<portfolio>/
  <thread>/                       Optional thread root with brief and reference material
    BRIEF.md                      Optional structured or freeform brief (frontmatter + prose)
    refs/                         Optional reference material (datasets, prior drafts, transcripts)
    refs.bib                      Optional starter bibliography supplied by the author
  <thread>.0.litsearch/           Optional pre-draft literature-search sibling (read-only)
    notes.md                      Annotated discussion of related work + positioning
    candidates.bib                Candidate BibTeX entries the drafter may merge into refs.bib
    _progress.json                Phase state (litsearch)
  <thread>.1/                     First drafted version (immutable once written)
    main.tex                      Paper body (LaTeX, uses anvil-paper.cls by default)
    refs.bib                      Bibliography (BibTeX)
    figures/                      Figure assets and source scripts
      src/                        Optional source scripts (e.g., Python plot scripts)
      *.pdf / *.png / *.svg / *.tex   Rendered figures (TikZ .tex or rasterized)
    _progress.json                Phase state for this version
    changelog.md                  (revisions only) Maps prior critic notes to changes
  <thread>.1.review/              Reviewer output for version 1 (read-only)
    verdict.md                    Top-level decision (advance / block) + total /40
    scoring.md                    Per-dimension scores against the paper rubric
    comments.md                   Line-level comments keyed to main.tex sections
  <thread>.1.audit/               Fact / citation auditor critic sibling (read-only)
    citation-audit.md             Per-\cite{} resolution + claim-support check
    numerical-audit.md            Numbers-in-text vs figures/tables consistency
    flags.md                      Critical flags (unsupported citations, numerical disagreement)
  <thread>.1.litsearch/           (optional) Re-run litsearch after reviewer flagged missing prior work
  <thread>.2/                     Revised version (after revise consumes v1 + all critic siblings)
  ...
  <thread>.{N}/                   Terminal version, marked READY in its _progress.json
```

Versioned dirs (`<thread>.{N}/`) and critic sibling dirs (`<thread>.{N}.<critic>/`) are **immutable once their `_progress.json` records the phase as `done`**. Revisions are produced as a new version dir, never by editing in place.

The litsearch sibling is intentionally allowed at `.0.litsearch/` (before any drafted version) AND at `.{N}.litsearch/` (after a reviewer points out missing prior work). Both follow the same "N parallel critics, one reviser" rule: when present at `<thread>.{N}.litsearch/`, the next `memo-revise`-equivalent pass (`pub-revise`) consumes it alongside `.review/` and `.audit/`.

## State machine

Per-thread state, derived from on-disk evidence (not flags):

```
EMPTY → DRAFTED → REVIEWED → REVISED → … → READY → AUDITED
        ↑
        (optional .0.litsearch/ may exist before DRAFTED; it does not gate the machine)
```

| State | Evidence |
|---|---|
| `EMPTY` | No `<thread>.{N}/` directories exist (a bare `<thread>.0.litsearch/` is still EMPTY for state purposes) |
| `DRAFTED` | Latest `<thread>.{N}/` exists with `main.tex` + `refs.bib` + `_progress.json.draft == done`; no sibling review at the same `N` |
| `REVIEWED` | `<thread>.{N}.review/verdict.md` exists for the latest `N` |
| `REVISED` | A `<thread>.{N+1}/` exists after a prior `<thread>.{N}.review/` |
| `READY` | Latest `<thread>.{N}.review/verdict.md` records `advance: true` AND no unresolved critical flag (in either `.review/` or `.audit/`) |
| `AUDITED` | `<thread>.{N}.audit/` exists alongside a `READY` version AND `audit/_progress.json.audit == done` AND `flags.md` records no unresolved critical flag |

Thresholds: **≥32/40** advances. **<32/40** requires revision. Any critical flag (from `.review/` OR `.audit/`) short-circuits regardless of total — block until addressed.

Iteration cap: default `max_iterations: 4` (so worst-case terminal version is `<thread>.5/`). The cap is configurable per-thread by writing `{ "max_iterations": <N> }` to `<thread>/.anvil.json` in the thread root. Exceeding the cap marks the thread `BLOCKED` (in the portfolio orchestrator's report) and requires human review.

**READY vs AUDITED distinction.** Unlike memo (where `AUDITED` is rarely reached), `pub-audit` is part of the normal lifecycle. A paper is **not done** until it reaches `AUDITED`: the auditor's job is to verify every `\cite{}` resolves and every cited claim is actually supported. The PDF compile check (see Acceptance criteria) lives in the auditor's responsibility because it requires the bibliography to be valid.

## Command dispatch

| Command | Role | Reads | Writes |
|---|---|---|---|
| `pub` | portfolio orchestrator | all `<thread>.*` dirs under cwd | (none; reports state per thread + recommends next command) |
| `pub-litsearch <thread>` | literature-search critic | `<thread>/BRIEF.md` (+ `<thread>/refs/`); for re-run, the latest `<thread>.{N}/main.tex` and any `.review/` notes about missing prior work | `<thread>.0.litsearch/` (initial) or `<thread>.{N}.litsearch/` (re-run) |
| `pub-draft <thread>` | drafter | `<thread>/BRIEF.md`, `<thread>/refs.bib` (if present), `<thread>/refs/`, AND any `<thread>.0.litsearch/` sibling | `<thread>.1/` with `main.tex` + `refs.bib` + `figures/` |
| `pub-review <thread>` | reviewer | latest `<thread>.{N}/` | `<thread>.{N}.review/` |
| `pub-revise <thread>` | reviser | latest `<thread>.{N}/` + all `<thread>.{N}.*/` critic siblings | `<thread>.{N+1}/` with `changelog.md` |
| `pub-audit <thread>` | fact / citation auditor | latest `<thread>.{N}/` (after reaching `READY`) | `<thread>.{N}.audit/` |
| `pub-figures <thread>` | figurer | latest `<thread>.{N}/main.tex` and `figures/src/` | figures into `<thread>.{N}/figures/` |

The portfolio orchestrator (`pub`) is the user-facing entry point for status; the six lifecycle commands are dispatched from it (or invoked directly by the orchestrating agent).

## Progress tracking

Each version dir and critic sibling dir contains `_progress.json`. Schema (matches memo skill, with paper-relevant phases):

```json
{
  "version": 1,
  "thread": "<thread>",
  "phases": {
    "draft":   { "state": "done",        "started": "<ISO>", "completed": "<ISO>" },
    "figures": { "state": "in_progress", "started": "<ISO>" }
  },
  "metadata": {
    "iteration": 1,
    "max_iterations": 4
  }
}
```

Phase states: `pending`, `in_progress`, `done`, `failed`. Validation is **by file existence** (does `main.tex` exist? does each `\includegraphics{figures/fig-1.pdf}` resolve to a file?), not by flag — `_progress.json` is a resume hint, not a source of truth. A phase that crashed mid-write should be re-runnable from `pending` after deleting any partial output.

Until `anvil/lib/progress.py` lands (issue #10), each command reads and writes `_progress.json` directly with a minimal JSON read-merge-write snippet. The merge is shallow: a command updates one phase, preserves all others.

## Rubric

See `rubric.md` for the 8-dimension /40 scoring schema (paper-tuned weights, rigor + evidence + citation hygiene = 17/40 ≈ 43%), the ≥32 advance threshold, and the critical-flag short-circuit policy.

## Skill-specific phases

**`pub-litsearch` (optional, read-only critic).** Pure-LLM literature search is prone to hallucinating citations. This role MUST refuse to invent BibTeX entries. Instead, it produces:
- `notes.md` — discussion of how the paper positions against the related work the author already supplied, plus a list of **gaps** (named missing topics or specific known papers the brief mentioned but did not supply BibTeX for).
- `candidates.bib` — entries that come from author-supplied refs (re-formatted for consistency) or that the role is **explicitly told** about in the brief. Entries from "I think there's a 2023 paper about X by someone named Smith" are forbidden — the role surfaces such gaps in `notes.md` for the author to fill manually (e.g., by pasting a Semantic Scholar export into `<thread>/refs/`).

**`pub-audit` (mandatory at READY).** Sharper than the generic auditor:
1. Verify every `\cite{}` in `main.tex` resolves to a real entry in `refs.bib`.
2. Spot-check that cited papers actually support the surrounding claim (the auditor reads `<thread>/refs/` for any author-supplied source PDFs / notes; for citations whose source is not on disk, the auditor flags them as "claim-support unverified — source not on disk" rather than fabricating a verification).
3. Flag claims that should have a citation but do not.
4. Flag numerical values in the text (Tables, Sec. results) that disagree with figures/tables.
5. Verify the LaTeX compiles: run `pdflatex main && bibtex main && pdflatex main && pdflatex main` (or equivalent) and capture the log. A non-zero exit OR any unresolved `??` citation in the rendered PDF is a critical flag.

**`pub-figures`.** Writes into the current `<thread>.{N}/figures/` directory (not a sibling — figures are part of the artifact). The figurer SHOULD NOT invent data. Source scripts go in `figures/src/`; rendered outputs go in `figures/`. Conventions:
- **TikZ / PGFPlots** (`.tex` files in `figures/`) — for diagrams and small plots; vector-native in the compiled PDF, included via `\input{figures/diagram-1.tex}`.
- **Matplotlib** (Python in `figures/src/*.py`) — for data plots from real datasets; saved as `.pdf`, included via `\includegraphics{figures/fig-1.pdf}`.
- **External assets** (`.png` / `.svg` dropped into `figures/`) — allowed; the figurer leaves them alone.

The auditor (`pub-audit`) may re-run scripts in `figures/src/` to verify rendered outputs are current; this verification policy is documented in `pub-audit.md`.

## Templates / assets

- **Default LaTeX class**: `templates/anvil-paper.cls` — minimal generic single-column class with `\title`, `\author`, `\abstract`, standard sectioning, and `\bibliographystyle{plainnat}` baked in. Compiles cleanly with `pdflatex` + `bibtex` from a fresh checkout, no venue-specific assumptions. Supports an `anonymous` option (`\documentclass[anonymous]{anvil-paper}`) that suppresses author/affiliation rendering for double-blind submission.
- **Bibliography**: BibTeX (`.bib`) is the primary format, with `natbib` for citation commands (`\citep{}`, `\citet{}`). Most venues accept either BibTeX or biblatex; BibTeX has wider tooling compatibility.
- **Venue overrides**: NeurIPS, IEEE, ACM, arXiv, etc. are handled by the standard anvil override mechanism — the consumer drops `neurips_2024.sty` (or equivalent) into `.anvil/skills/pub/templates/` in their own repo and the brief instructs the drafter to switch the documentclass line (e.g., `\documentclass{neurips_2024}`). This skill ships **no venue style files** (licensing + staleness concerns).
- **Entry-point template**: `templates/main.tex.j2` — Jinja2-style placeholder document with frontmatter hooks (`{{title}}`, `{{author}}`, `{{abstract}}`) and section skeletons (`\section{Introduction}`, etc.). The drafter substitutes from the brief and elaborates.
- **Starter bibliography**: `templates/refs.bib.j2` — empty `.bib` with a comment header explaining that entries come from either author-supplied `<thread>/refs.bib` or the litsearch sibling's `candidates.bib`.
- **Smoke test brief**: `assets/example-brief.md` — a one-page paper brief the drafter can turn into a compilable 2–4 page paper with one figure and a handful of citations. Used by the acceptance test.

## Defaults and overrides

This skill ships opinionated defaults. Consumers are expected to override liberally via `.anvil/skills/pub/` in their own repo:

- `voice.md` (optional) — Author or lab voice/style guidance the drafter reads in addition to its base prompt.
- `rubric.overrides.md` (optional) — Add domain-specific critical-flag examples or adjust the open-ended "any dealbreaker a sophisticated reader would catch" instruction.
- `templates/<venue>.cls` or `templates/<venue>.sty` — Venue-specific style files. The brief tells the drafter to use them.
- `BRIEF.md.example` — Reference brief shape; freeform prose with optional YAML frontmatter is accepted.

## Anonymous / double-blind submission

When the brief sets `anonymous: true`, the drafter:
1. Uses `\documentclass[anonymous]{anvil-paper}` (or the venue override's equivalent option).
2. Replaces author names and affiliations with `Author Name(s) Withheld` and `Affiliation Withheld`.
3. Scrubs identifying language in acknowledgements and self-citations (`\citet{ourpriorwork}` becomes `\citet{anonprior}` with a note in `changelog.md`).

Venue overrides handle their own anonymization on top of this.
