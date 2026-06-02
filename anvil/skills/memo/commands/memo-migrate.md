---
name: memo-migrate
description: One-shot LaTeX → anvil:memo thread converter. Reads a legacy memo.tex (the source body from a prior LaTeX-based memo pipeline) and produces a DRAFTED-state anvil:memo thread (BRIEF.md + .anvil.json + <thread>.1/ with memo.md + exhibits/ + _progress.json + changelog.md) that re-enters the standard memo lifecycle.
---

# memo-migrate — Legacy-LaTeX → anvil:memo migrator

**Role**: migrator (one-shot, idempotent on resume, NOT in the standard `draft → review → revise → figures` lifecycle).
**Reads**: a legacy `memo.tex` source file and any sibling `memo.pdf` / `figures/*.pdf`.
**Writes**: a new thread root containing `BRIEF.md` (stub), `.anvil.json`, `refs/prior-pipeline/v0/`, and `<thread>.1/` (memo.md, exhibits/, _progress.json with `draft.state == done`, changelog.md).

This command exists because Studio's 2026-06-01 portfolio review surfaced 14 legacy LaTeX threads that each required the same hand-rolled migration. The most consequential bug in the hand migrations was `\textasciitilde` getting silently dropped by pandoc — which turns hedged values (`~$50K`) into asserted values (`$50K`) in financial prose. This command codifies the migration pattern so the bug is impossible to ship.

**State-machine status**: `memo-migrate` is a **one-shot entry point**, NOT a lifecycle phase. It produces a thread in `DRAFTED` state (derived from `<thread>.1/_progress.json.phases.draft == done` per SKILL.md §"State machine") and then exits. The operator runs `memo-review <thread>` next, exactly as if `memo-draft` had produced the version. The output thread is indistinguishable from a freshly-drafted one — only `refs/prior-pipeline/v0/` and the `migrated_from` `_progress.json` metadata field distinguish a migrated thread from a clean one.

**Composability**: `memo-migrate` is **single-shot** — it is run once per legacy `.tex` source. There is no re-run case; if the migration produced a broken `memo.md`, the operator either (a) hand-edits `<thread>.1/memo.md` and proceeds normally, or (b) deletes the entire thread root and re-runs `memo-migrate`. The command does not attempt to merge into an existing thread.

## Inputs

- **Source LaTeX file** (positional argument): path to the legacy `memo.tex`. The thread's parent directory and any sibling `memo.pdf` are inferred from this path.
- **`--thread-slug=<slug>`** (optional): overrides the auto-derived slug. Default: the parent-dir name of the source `.tex` file. Use this when the source `.tex` lives in a directory named differently from the desired thread slug (e.g., `legacy/memo.tex` should produce thread `acme-seed/`, not `legacy/`).
- **`--target-length=words:<min>-<max>`** (optional): writes through to the generated `<thread>/.anvil.json` `target_length.words` field. Format: `words:<min>-<max>` (e.g., `words:1800-2400`). Matches the legacy flat shape documented in `anvil/skills/memo/SKILL.md` §"Length targets". When omitted the field is left unset (operator can add it later by editing `.anvil.json`).

## Outputs

Mirrors the migration-thread shape documented in `anvil/skills/memo/SKILL.md` §"Artifact contract" and `anvil/skills/memo/templates/BRIEF.migration.md.example`:

```
<thread>/
  BRIEF.md                  Stub brief seeded from migration context (clearly marked
                            TODO; operator MUST fill in before first revise pass).
  .anvil.json               { "max_iterations": 4, "target_length"?: {...} }
  refs/
    prior-pipeline/v0/
      memo.tex              Copy of the original .tex source (read-only reference)
      memo.pdf              Original rendered PDF (if found alongside .tex)
      figures/              Copy of the original figures/ directory (if present)
  <thread>.1/
    memo.md                 Converted markdown body (pandoc + LaTeX pattern handling)
    exhibits/               PDF → PNG converted figures (one PNG per source PDF)
    _progress.json          { phases.draft: { state: "done", ... },
                              metadata: { iteration: 1, max_iterations: 4 } }
    changelog.md            Single-line "migrated from <source>" record
```

The "v0 starts at `<thread>.1/`" convention matches `anvil/skills/memo/SKILL.md` §"State machine" — `DRAFTED` is derived from "latest `<thread>.{N}/` exists with `memo.md` and `_progress.json.draft == done`". The operator then runs `memo-review <thread>` against `<thread>.1/` normally — the migration produces a `DRAFTED`-state thread that re-enters the standard memo lifecycle.

## Procedure

1. **Preflight: pandoc**. Check `anvil/skills/memo/lib/migrate.py::check_pandoc_available()`. When pandoc is absent, raise `MigrateError(PANDOC_REMEDIATION)` and exit non-zero. This is a **hard fail** — unlike `memo-render`, the migration cannot synthesize a markdown body without pandoc. The remediation message names the install paths (`brew install pandoc` / `apt-get install pandoc`).
2. **Preflight: pdftoppm** (soft). Check `check_pdftoppm_available()`. When pdftoppm is absent, log the `PDFTOPPM_REMEDIATION` note and continue: the `\includegraphics` refs in `memo.md` are still rewritten to `exhibits/<basename>.png`, but the PNGs are not produced (the operator can run pdftoppm by hand later or install poppler-utils and re-run figure conversion).
3. **Validate source**. Confirm the source `.tex` exists and is readable. Raise `MigrateError` if not. (Mirrors the precedent in `anvil/lib/render.py::render_pdf_to_pngs` which raises `FileNotFoundError` for a missing input PDF.)
4. **Resolve thread slug**. If `--thread-slug` is provided, use it; otherwise use the parent-directory name of the source `.tex`. Example: `legacy/acme-seed/memo.tex` → slug `acme-seed`.
5. **Resolve target_length**. Parse `--target-length=words:<min>-<max>` if provided. Validate `min <= max` and both are integers. When malformed or absent, no target is written (matches the SKILL.md §"Length targets" "no target — fall back to implicit behavior" branch).
6. **Read + preprocess the LaTeX source.** Three pre-pandoc transforms:
   - **Strip preamble**: drop everything before `\begin{document}` and after `\end{document}` (per the v0 must-have spec in issue #202). If neither delimiter is present (body-only fragment), the source is passed through unchanged.
   - **Substitute load-bearing patterns** (this is the 5c safeguard): replace `\textasciitilde` (with or without trailing `{}`) with an ASCII sentinel that pandoc is guaranteed not to touch. Replace `\EUR{X}` and `\EUR{}` with a sentinel + content pair (same rationale). The sentinels are post-substituted back to canonical markdown after pandoc runs.
7. **Invoke pandoc**. Subprocess: `pandoc -f latex -t markdown_strict`, source-in via stdin (no temp file round-trip). Capture stdout. Non-zero exit raises `MigrateError` with the captured stderr.
8. **Post-substitute sentinels.** Walk the pandoc output and replace the tilde sentinel with a literal `~` and the EUR sentinel with `€`. **This is the load-bearing step that fixes sub-issue 5c**: a fixture `memo.tex` containing `\textasciitilde\$50K` produces `memo.md` containing literal `~$50K` (the hedged value), not `$50K` (the asserted value pandoc would have produced by silently dropping `\textasciitilde`).
9. **Rewrite figure refs.** Walk the markdown for `![alt](path)` image refs. For each non-URL, non-absolute, non-`exhibits/` ref:
   - Strip the alt text (anvil:memo prefers empty alt with surrounding prose carrying the caption).
   - Strip the `figures/` prefix and switch the extension to `.png`: `figures/fig1.pdf` → `exhibits/fig1.png`.
   - Collect the `(source_pdf_relative_path, target_png_basename)` tuple for the figure-conversion step.
10. **Pair orphan footnotes** (sub-issue 5d). Find `[^N]` references that have no matching `[^N]: ...` definition. For each orphan, emit a placeholder `[^N]: TODO: migration recovered orphan footnote — verify text against refs/prior-pipeline/v0/memo.tex` definition at the end of the document. This keeps the markdown well-formed (no broken refs) and surfaces the orphan as a TODO for the operator's first revise pass.
11. **Write `memo.md`**. Persist the post-processed markdown body to `<thread>.1/memo.md`.
12. **Preserve refs** (acceptance criterion 6). Copy the original `memo.tex` and any sibling `memo.pdf` to `<thread>/refs/prior-pipeline/v0/`. Also copy the sibling `figures/` directory (if present) so the raw PDFs are archived alongside the source LaTeX for audit-trail purposes.
13. **Convert figures** (acceptance criterion 5; sub-issue 5a). When `pdftoppm` is available, for each collected `(source_pdf, basename)` tuple:
    - Resolve the source PDF by checking `<source.tex>/<path>`, `<source.tex>/figures/<basename>.pdf`, and the archived `<thread>/refs/prior-pipeline/v0/figures/<basename>.pdf` (so the conversion works even after the source moved).
    - Invoke `pdftoppm -r 150 -png <pdf> <exhibits_dir>/<basename>` (reuses the same flags as `anvil/lib/render.py::render_pdf_to_pngs`).
    - **5a single-page rename**: `pdftoppm` writes `<basename>-1.png` even for single-page PDFs. Rename `<basename>-1.png` to `<basename>.png` so the markdown ref resolves. For multi-page PDFs, keep page-1 as the canonical reference; later pages remain as `<basename>-2.png`, etc., for operator inspection.
14. **Write `BRIEF.md`** (acceptance criterion 7). Produce a clearly-marked stub with:
    - The token `TODO: migration-brief stub` at the top so operators can grep for unfinished briefs across a portfolio.
    - Explicit `TODO` placeholders for every author-judgment field (`company`, `sector`, `stage`, `check_size`, `recommendation_target`). The migration tool cannot infer these from the source LaTeX.
    - The shape of the canonical `BRIEF.migration.md.example` template appended below as a reference block — so the operator sees the section structure of a finished migration brief while editing.
15. **Write `.anvil.json`** (acceptance criterion 8). Emit the legacy flat shape: `{ "max_iterations": 4 }` (+ optional `"target_length": { "words": [min, max] }` when `--target-length` was provided). Matches the SKILL.md §"Length targets" "Flat shape (legacy)" documentation.
16. **Write `_progress.json`** (acceptance criterion 3). Initialize the version dir's `_progress.json` with `phases.draft = { state: "done", started: <ISO>, completed: <ISO> }`, `metadata.iteration = 1`, `metadata.max_iterations = 4`, and an additional `metadata.migrated_from = "<source.tex>"` field for provenance. This shape derives `DRAFTED` state per SKILL.md §"State machine".
17. **Write `changelog.md`**. Single-block record: "Migrated from `<source>` via `anvil:memo-migrate` on `<ISO>`" + a line naming where the refs were preserved + a line summarizing the figure-conversion outcome. This file is *informational* — it does not feed the rubric, it does not gate any state transition.
18. **Report**. Print a one-line summary identifying the produced thread and any soft-fail notes (e.g., `pdftoppm not on PATH — skipped figure conversion`).

## Failure modes

| Failure | Symptom | Outcome | Operator action |
|---|---|---|---|
| **Missing pandoc** | `check_pandoc_available()` returns False | `MigrateError(PANDOC_REMEDIATION)`, non-zero exit | Install pandoc per the install story; re-run. |
| **Missing pdftoppm** | `check_pdftoppm_available()` returns False | `_progress.json.phases.draft.state == done`, but `exhibits/` is empty; `changelog.md` records the skip; the report includes the `PDFTOPPM_REMEDIATION` install story | Install poppler-utils; re-run figure conversion by hand or delete the thread and re-run `memo-migrate`. |
| **pandoc non-zero exit** | source LaTeX rejected | `MigrateError` carrying captured stderr | Inspect the source `.tex` for syntax errors; fix and re-run. |
| **Source `.tex` missing** | path does not resolve | `MigrateError` with the resolved path | Confirm the path; re-run. |
| **`\textasciitilde` round-trip fails** | Should be impossible by design | If it happens, the sentinel substitution leaked through pandoc somehow | File an issue — this is the load-bearing 5c bug guard and any regression is critical. |

## Idempotence and resume semantics

`memo-migrate` is **not idempotent in the lifecycle sense** — re-running it against the same source `.tex` while the thread root already exists will **overwrite** `<thread>.1/memo.md`, `BRIEF.md` (clobbering operator edits!), and `.anvil.json`. The intended re-run path is: delete `<thread>/` entirely and re-run. This is the "single-shot entry point" contract — once the operator has started editing `BRIEF.md` or `<thread>.1/memo.md`, the canonical re-edit path is `memo-revise`, not `memo-migrate`.

This is a deliberate departure from the `draft → review → revise` commands' idempotent-on-resume contract: those commands assume the operator wants to continue from where the prior run left off. `memo-migrate` is a fresh-import operation — there is no "resume" semantic to preserve.

## Reference

- `anvil/skills/memo/lib/migrate.py` — implementation. The single public entrypoint is `migrate_thread(...)`.
- `anvil/skills/memo/templates/BRIEF.migration.md.example` — the canonical migration-brief template that BRIEF.md's reference block appends.
- `anvil/lib/render.py::check_pandoc_available` — the framework-side pandoc preflight that the skill-local `check_pandoc_available` mirrors (the skill-local mirror exists for consumer-install path safety per issue #199 / sibling `refs_pdf.py`).
- `anvil/lib/render.py::render_pdf_to_pngs` — the pdftoppm invocation precedent that the skill-local `_convert_pdf_to_png` mirrors.
- `anvil/skills/memo/SKILL.md` §"State machine" — how `DRAFTED` is derived from `_progress.json.phases.draft == done`.
- `anvil/skills/memo/SKILL.md` §"Length targets" — the `.anvil.json` `target_length` flat-shape contract.

## Notes for the agent

- **Pandoc is REQUIRED.** Unlike `memo-render` (non-blocking, soft-fail), `memo-migrate` cannot proceed without pandoc — it hard-fails with the install story.
- **`\textasciitilde` is load-bearing.** The sentinel round-trip is the single bug this command exists to prevent. Any regression in the post-substitute step is a critical issue.
- **BRIEF.md is a STUB.** The operator MUST fill in the `TODO` fields before the first `memo-revise` pass. The migration tool cannot infer company / sector / stage / check-size / recommendation-target from the source LaTeX.
- **The output thread re-enters the standard lifecycle.** `memo-review <thread>` works against the migrated `<thread>.1/` exactly as it does against a freshly-drafted thread; the migration provenance (`metadata.migrated_from`) is the only mark that distinguishes a migrated thread from a clean one.
- **Refs preservation is permanent.** Do NOT delete `<thread>/refs/prior-pipeline/v0/` — it is the canonical record of "what was the prior pipeline's output that this thread was migrated from?", and the BRIEF.md `Source material — read order` section cites into it.
