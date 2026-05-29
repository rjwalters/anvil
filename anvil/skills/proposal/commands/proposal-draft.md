---
name: proposal-draft
description: Drafter command for the proposal skill. Produces a new proposal version directory from a brief by filling the proposal.tex.j2 template.
---

# proposal-draft — Drafter

**Role**: drafter.
**Reads**: `<thread>/BRIEF.md` (if present), `<thread>/refs/**` (if present), and the `templates/proposal.tex.j2` + `templates/anvil-proposal.cls` shipped with this skill. For revise-from-feedback path: also the latest `<thread>.{N}/` and all `<thread>.{N}.*/` critic siblings.
**Writes**: `<thread>.{N+1}/` containing `proposal.tex`, the class file, an optional `figures/`, and `_progress.json`.

## Inputs

- **Thread slug** (positional argument): identifies the thread within the cwd portfolio.
- **Brief** (`<thread>/BRIEF.md`): freeform prose, optionally with YAML frontmatter. Recognized frontmatter keys (all optional): `title`, `subtitle`, `studio`, `date`, `stage`, `signature_color` (hex, no `#`; default `4A6FA5`), `hero` (path to a hero render under `figures/`), `customer_kind` (`external`/`internal`; default `external`). Unrecognized keys are passed through to the drafter as context.
- **References** (`<thread>/refs/**`): any supporting material (site plans, datasheets, vendor quotes). Treated as read-only context — and as the sourceability basis the auditor will later check the BOM against.
- **Prior version + critic siblings** (revise-from-feedback path only): in normal flow, revision is handled by `proposal-revise`. `proposal-draft` is the entry point for new threads. For threads where the user wants to start fresh from feedback (rare), this path is available — but `proposal-revise` is preferred because it preserves the changelog mapping.

## Outputs

A new version directory:

```
<thread>.{N+1}/
  proposal.tex          Proposal body (XeLaTeX), produced by filling proposal.tex.j2
  anvil-proposal.cls    Copied alongside proposal.tex so the version dir compiles standalone
  figures/              Topology diagrams, site/routing plans (created as needed; figures deferred to proposal-figures)
  _progress.json        Phase state with draft: done after successful write
```

For a new thread, `N+1 == 1` so the output is `<thread>.1/`.

## Procedure

1. **Discover thread state**: enumerate existing `<thread>.{N}/` dirs. Compute the next `N`.
2. **Resume check**: if `<thread>.{N+1}/_progress.json` exists with `draft.state == in_progress`, treat as a crashed prior run. Delete any partial `proposal.tex` and re-draft. If `draft.state == done`, the version is already drafted — exit early with a notice (this command is idempotent: it does not overwrite a completed draft).
3. **Read inputs**: load `BRIEF.md` (if present) and enumerate `refs/`. If revising from feedback, also load the prior version's `proposal.tex` and concatenate all critic siblings' verdict/scoring/comments (review) and verdict/findings/evidence (audit).
4. **Initialize `_progress.json`**: write `phases.draft.state = in_progress`, `phases.draft.started = <ISO timestamp>`, `metadata.iteration = N+1`, `metadata.max_iterations` (inherit from `<thread>/.anvil.json` if set, else 4).
5. **Fill the template** to produce `proposal.tex` from `templates/proposal.tex.j2`. The template provides the 10-section skeleton; the drafter elaborates each section into prose, tables, and figure references. Thread the customer's **hard constraints** (from the Premise) through every section — the reviewer scores constraint satisfaction (dim 3) on exactly this:
   1. **Premise** — `\begin{callout}[title=Premise]` one-paragraph thesis threading the hard constraints (e.g. invisibility, no conduit, 10 Gbps). Legible without further reading.
   2. **The Idea** — why this approach; the problem the conventional answer fails to solve; the value proposition (anchors the pitch element, dim 7).
   3. **Topology** — the system architecture with a `metricbox` diagram/table of the structure (hub-and-spoke, mesh, pipeline). The design must be technically sound (dim 2).
   4. **The Core Subsystem** — the central engineered element, with `\subsection`s. Generalize the section title from "The Core Subsystem" to the piece's actual core (Gossamer: "The Fiber"). **The delivery-capability subsection is the deliverability anchor (dim 5)** — the "we deliver by acquiring the tools/skills/staff to execute and maintain it" angle (Gossamer: "the fiber workshop").
   5. **The Interfaces** — the secondary engineered layer (Gossamer: "The Optics") with a spec `metricbox` table. Match components at both ends; the auditor cross-checks rated specs against run lengths / capacity.
   6. **Coverage / Capacity** — how the system covers its full required scope and the design rule that guarantees it (dims 3, 4).
   7. **Bill of Materials** — the central proposal artifact: a multi-section priced `tabularx` BOM + a **labor estimate** subsection + a **project total** subsection (materials + labor → total). Anchors scope completeness (dim 4) and cost credibility (dim 6). See "Priced tables" below.
   8. **Installation / Operating Notes** — a `description` list of sequenced execution and operating guidance (dim 5).
   9. **References / Compliance** — OPTIONAL `tabularx` of standards/spec sheets cited (Gossamer: ITU-T G.652D/G.657). Omit the whole section if the piece cites nothing — the template gates it on the `references` key being defined and non-empty.
   10. **Open Decisions** — an `enumerate` of unresolved engineering choices (dim 8). Plus the `\coda{...}` closing line.
6. **`customer_kind` handling**: the brief's `customer_kind` (default `external`) drives the title-block `\proposalstage` default — `DESIGN PROPOSAL --- CONCEPT STAGE` (external) vs. `INTERNAL BUILD SPEC` (internal). It does NOT add or remove sections. An explicit `stage:` in the brief overrides the default. For an internal build spec, frame the value proposition (section 2 / dim 7) as a budget justification rather than a client pitch.
7. **Priced tables** (critical for this skill): Section 7 is where the proposal lives or dies on cost credibility. Pre-wire all three tables — the multi-section BOM (`\multicolumn{4}{@{}l}{\textbf{...}}` section headers, `\addlinespace` between groups, `Item | Qty | Unit | Total` columns, `\toprule`/`\midrule`/`\bottomrule`, a bold **Materials subtotal** row), the **Labor estimate** (`Task | Hours | Cost`, bold subtotal), and the **Project total** (Materials + Labor → bold Total). Every priced line must have a sourceable basis (planning range, vendor list price, quote) — the auditor walks every line for arithmetic and sourceability. See `assets/figure-conventions.md` for the priced-table conventions.
8. **Copy the class**: copy `templates/anvil-proposal.cls` into the version dir alongside `proposal.tex` so the version dir compiles standalone with `xelatex proposal.tex`.
9. **Figures**: this command does NOT render figures. It writes the `\herofigure{...}` and `\includegraphics{figures/...}` references the brief implies and leaves figure production to `proposal-figures`. Create an empty `figures/` dir.
10. **Update `_progress.json`**: `phases.draft.state = done`, `phases.draft.completed = <ISO timestamp>`.
11. **Report**: print the path to the new version dir and a one-line status (e.g., `Drafted gossamer-lan.1/ (proposal.tex: 10 sections, 3 priced tables, customer_kind: external)`).

## Voice and style overrides

If `.anvil/skills/proposal/voice.md` exists in the consumer repo, load it and apply its guidance during drafting. This is how a studio or sales-engineering team customizes voice without forking the skill.

## Idempotence and resumability

- A completed draft (`_progress.json.draft.state == done` AND `proposal.tex` exists) is never overwritten. Re-running `proposal-draft <thread>` on a `DRAFTED` thread is a no-op with a notice.
- A crashed draft (`_progress.json.draft.state == in_progress` with no complete `proposal.tex`) is re-runnable after deleting any partial output.
- Validation is by file existence (does `proposal.tex` exist? is it non-empty?), not solely by the progress flag.

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
