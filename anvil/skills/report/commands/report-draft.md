---
name: report-draft
description: Drafter command for the report skill. Produces a new report version directory from a project context + brief (or, on revise-from-feedback path, from a prior version + critic siblings).
---

# report-draft — Drafter

**Role**: drafter.
**Reads**: `<project>/_project.md`, `<project>/<thread>/BRIEF.md` (if present), `<project>/<thread>/refs/**` (if present). For revise-from-feedback path: also the latest `<thread>.{N}/` and all `<thread>.{N}.*/` critic siblings.
**Writes**: `<project>/<thread>.{N+1}/` containing `report.md`, optional `exhibits/`, and `_progress.json`.

## Inputs

- **Project + thread path** (positional argument): `<project>/<thread>` identifies the report. The project must already have `_project.md` at its root; if absent, the command exits with an error directing the operator to create it from `_project.md.example`.
- **Project context** (`<project>/_project.md`): REQUIRED. Provides recipient identity, engagement_id, delivery format, confidentiality class, prior reports list, and voice notes. The drafter loads this first and treats it as authoritative for all recipient-facing decisions.
- **Brief** (`<project>/<thread>/BRIEF.md`): freeform prose, optionally with YAML frontmatter. Recognized frontmatter keys (all optional): `title`, `report_type` (one of `findings`/`assessment`/`advisory`/`final`), `scope`, `due_date`. Unrecognized keys are passed through to the drafter as context.
- **References** (`<project>/<thread>/refs/**`): any supporting material (interviews, measurements, source documents). Treated as read-only context.
- **Prior version + critic siblings** (revise-from-feedback path only): in normal flow, revision is handled by `report-revise`. `report-draft` is the entry point for new threads; for threads where the user wants to start fresh from feedback (rare), this path is available — but `report-revise` is preferred because it preserves the changelog mapping.

## Outputs

A new version directory:

```
<project>/<thread>.{N+1}/
  report.md          Report body (markdown)
  exhibits/          Inline tables, charts, source data referenced from report.md (created as needed)
  _progress.json     Phase state with draft: done after successful write
```

For a new thread, `N+1 == 1` so the output is `<project>/<thread>.1/`.

## Procedure

1. **Validate project context**: confirm `<project>/_project.md` exists and parses. Extract recipient, engagement_id, delivery_format, confidentiality_class, prior_reports, voice_notes. If `_project.md` is missing, exit with an error directing the operator to `templates/_project.template.md` (or `templates/_project.md.example`).
2. **Discover thread state**: enumerate existing `<project>/<thread>.{N}/` dirs. Compute the next `N`.
3. **Resume check**: if `<project>/<thread>.{N+1}/_progress.json` exists with `draft.state == in_progress`, treat as a crashed prior run. Delete any partial `report.md` and re-draft. If `draft.state == done`, the version is already drafted — exit early with a notice (this command is idempotent: it does not overwrite a completed draft).
4. **Read inputs**: load `BRIEF.md` (if present), enumerate `refs/`, and absorb the project context. If revising from feedback, also load the prior version's `report.md` and concatenate all critic siblings' verdicts + scoring + comments + findings + evidence.
5. **Initialize `_progress.json`**: write `phases.draft.state = in_progress`, `phases.draft.started = <ISO timestamp>`, `project = <project-slug>`, `metadata.iteration = N+1`, `metadata.max_iterations` (inherit from `<thread>/.anvil.json` if set, else 4).
6. **Draft the report** following the default template (`templates/report.template.md`, or a consumer override at `.anvil/skills/report/templates/report.template.md`). Sections (in order):
   - **Cover** — report title, recipient (from `_project.md`), engagement_id, version, date, confidentiality class. Generated from `templates/cover.template.md`.
   - **Executive summary** — single page maximum: top findings, top recommendations, scope and caveats. Generated from `templates/exec-summary.template.md`. This page must stand alone.
   - **Scope & method** — what was assessed, what was not, how the assessment was conducted, sample size, data sources, time window.
   - **Findings** — numbered findings, each with a heading, narrative, and explicit evidence citation. Reference exhibits inline.
   - **Recommendations** — numbered recommendations, each cross-referenced to one or more findings, each with owner / scope / "what done looks like."
   - **Risks & limitations** — scope boundaries, sample limits, assumptions stated explicitly. What this report does NOT cover and why.
   - **Appendices** — supplementary material; optional.
   - **Evidence index** — bibliography / citation list, each entry traceable to a primary source (interview, document, dataset, measurement).
7. **Apply recipient calibration**: use `voice_notes` and `confidentiality_class` from `_project.md` to set jargon level, tone, and any redaction posture. A `restricted` confidentiality class triggers a placeholder warning at the top of the cover page (`[RESTRICTED — DO NOT REDISTRIBUTE]`); the skill does NOT enforce write-location restrictions in v0 (see SKILL.md open question on confidentiality handling).
8. **Apply prior-reports awareness** (for engagements with prior delivered reports): the drafter reads `prior_reports[]` from `_project.md` and references prior findings where relevant to avoid contradiction and to maintain a coherent engagement narrative. The auditor sibling will later cross-check for contradictions.
9. **Create exhibits** (inline only — full figure generation belongs to `report-figures`): any tables or simple inline data structures referenced from the body should land in `exhibits/` as `.md` or `.csv` files. Image generation is deferred to `report-figures`.
10. **Update `_progress.json`**: `phases.draft.state = done`, `phases.draft.completed = <ISO timestamp>`.
11. **Report**: print the path to the new version dir and a one-line status (e.g., `Drafted acme-q2/findings.1/ (report.md: 2840 words, 4 exhibits, recipient: Acme Corp)`).

## Voice and style overrides

If `.anvil/skills/report/voice.md` exists in the consumer repo, load it and apply its guidance during drafting (overrides the skill default). Additionally, `_project.md`'s `voice_notes` field is per-project and ALWAYS applied on top of the resolved voice file. Resolution order:

1. Skill-default voice (if any) — base.
2. Consumer override `.anvil/skills/report/voice.md` — replaces base.
3. Project-specific `_project.md` `voice_notes` field — layered on top.

## Idempotence and resumability

- A completed draft (`_progress.json.draft.state == done` AND `report.md` exists) is never overwritten. Re-running `report-draft <project>/<thread>` on a `DRAFTED` thread is a no-op with a notice.
- A crashed draft (`_progress.json.draft.state == in_progress` with no complete `report.md`) is re-runnable after deleting any partial output.
- Validation is by file existence (does `report.md` exist? is it non-empty? does the cover page reference the recipient from `_project.md`?), not solely by the progress flag.

## `_progress.json` snippet

Minimum schema this command writes (matches `SKILL.md`):

```json
{
  "version": 1,
  "thread": "<slug>",
  "project": "<project-slug>",
  "phases": {
    "draft": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  },
  "metadata": {
    "iteration": <N>,
    "max_iterations": 4
  }
}
```

Merge rule: read existing `_progress.json` if present, update only `phases.draft` and `metadata`, preserve all other fields. Until `anvil/lib/progress.py` lands (see #10), each command embeds this minimal read-merge-write inline.
