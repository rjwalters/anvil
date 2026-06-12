---
name: pub-audit
description: Fact and citation auditor for the pub skill. Verifies every cite resolves, spot-checks claim support, flags numerical inconsistencies, and verifies the LaTeX compiles to a clean PDF. Critical for paper credibility.
---

# pub-audit — Fact / citation auditor

**Role**: auditor (sibling critic, read-only).
**Reads**: latest `<thread>.{N}/main.tex`, `<thread>.{N}/refs.bib`, `<thread>.{N}/figures/`, AND `<thread>/refs/` for any author-supplied source PDFs / notes used to verify claim support.
**Writes**: `<thread>.{N}.audit/` with `citation-audit.md`, `numerical-audit.md`, `flags.md`, `compile-log.txt`, and `_progress.json`.

This is the **mandatory final-quality phase** for papers. Unlike memo (where auditor is optional), no paper reaches `AUDITED` without `pub-audit`. The auditor's findings carry equal weight to the reviewer's critical flags and block advancement until resolved.

## Why this exists as a distinct phase

The reviewer's job is to score a paper against the rubric (rigor, evidence, clarity, ...). The auditor's job is **fact-check**: every `\cite{}` resolves, cited papers actually support the surrounding claim, numerical values are consistent across text/figures/tables, and the paper compiles cleanly. These are mechanical or near-mechanical checks that benefit from a separate pass without the reviewer's scoring overhead.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/main.tex`. The auditor runs after the reviewer marks `advance: true` (i.e., the paper has reached `READY`). It is acceptable (and sometimes useful) to run the auditor earlier — e.g., on a draft that has not yet been reviewed — to surface fact issues before review effort is spent.
- **Author-supplied sources** (`<thread>/refs/**`): any PDFs, notes, or transcripts the author supplied. Used to verify claim support. **Citations whose source is not on disk are flagged "claim-support unverified — source not on disk" rather than fabricating a verification.**
- **Build toolchain**: `pdflatex`, `bibtex` (or `biber` if the consumer's documentclass uses biblatex). The auditor verifies the LaTeX compiles cleanly.

## Outputs

```
<thread>.{N}.audit/
  citation-audit.md    Per-cite{} resolution check + claim-support spot-check results
  numerical-audit.md   Numbers-in-text vs figures/tables consistency check
  flags.md             Critical flags (unresolved cites, claim-support failure, numerical inconsistency, build failure)
  compile-log.txt      Captured stdout/stderr from the pdflatex + bibtex compile cycle
  _meta.json           { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json       Phase state (phase: audit)
```

**Atomicity** (issue #350, #376): the audit sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The six files (`citation-audit.md`, `numerical-audit.md`, `flags.md`, `compile-log.txt`, `_meta.json`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.audit.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.audit/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.audit.tmp/` dir on disk that the next invocation's `cleanup_one_staging(<thread>.{N}.audit)` per-critic sweep removes; the final-named dir never exists in partial form. Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/main.tex`. Then **sweep a stale staging dir from a prior interrupt of THIS critic on THIS version** by invoking `anvil/lib/sidecar.py::cleanup_one_staging(<thread>.{N}.audit)` (the per-critic, parallel-safe sweep — issue #376). This removes ONLY a leftover `.<thread>.{N}.audit.tmp/` from a previously-killed run of this same critic on THIS version. Sibling critics' in-flight staging dirs under the same portfolio root are NOT touched (issue #350, #376). The sweep is idempotent and logs at INFO level when it removes a dir. If `<thread>.{N}.audit/` exists (the atomic-rename contract guarantees the dir only exists when complete), exit early with a notice (idempotent).
2. **Resume check**: per the staged-sidecar shape introduced in issue #350, a partial audit left behind by a mid-cycle interrupt manifests as a leading-dot `.<thread>.{N}.audit.tmp/` directory (NOT as a partially-filled `<thread>.{N}.audit/`). The sweep in step 1 has already removed any such partial. Backwards-compat: if a legacy pre-#350 `<thread>.{N}.audit/` exists WITHOUT `flags.md`, delete the dir and re-audit.
3. **Open the staged sidecar** for the audit dir by invoking the context manager `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.audit, required_files=["citation-audit.md", "numerical-audit.md", "flags.md", "compile-log.txt", "_meta.json", "_progress.json"])`. Every file write below MUST land **inside the yielded staging directory** (the path of the shape `.<thread>.{N}.audit.tmp/`), NOT inside the final `<thread>.{N}.audit/` path. On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name (issue #350). Then, **inside the staging dir**, initialize `_progress.json`: `phases.audit.state = in_progress`, `phases.audit.started = <ISO>`, `for_version = N` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`); pub-audit ships task-specific files (`citation-audit.md`, `numerical-audit.md`, `compile-log.txt`, `flags.md`) alongside the scorecard-kind declaration.
4. **Compile the paper** (build verification):
   - Run `pdflatex -interaction=nonstopmode main.tex` in `<thread>.{N}/`.
   - Run `bibtex main` (or `biber main` if biblatex is in use).
   - Run `pdflatex -interaction=nonstopmode main.tex` twice more to resolve cross-references and citations.
   - Capture all stdout and stderr to `<thread>.{N}.audit/compile-log.txt`.
   - Inspect the resulting `main.pdf` (or compile log) for unresolved citations (`[??]`) and unresolved cross-references (`Section ??`, `Figure ??`).
   - If the toolchain is not available in the environment, write a `compile-log.txt` entry: `SKIPPED — pdflatex not available in environment` and set a NON-critical note (rather than a critical flag) in `flags.md`. The acceptance test environment IS expected to have the toolchain.
   - A non-zero exit from any pdflatex/bibtex invocation, OR any `[??]` in the final PDF, sets a **critical flag** in `flags.md`.
5. **Citation audit** (`citation-audit.md`):
   - Enumerate every `\cite{key}`, `\citep{key}`, `\citet{key}` (and any other natbib cite commands) in `main.tex`.
   - For each `key`, verify it has a matching `@type{key, ...}` in `refs.bib`. List unresolved keys in `citation-audit.md` and add a critical flag for each.
   - For each resolved citation, attempt **claim-support spot-check**:
     - Extract the surrounding sentence(s) — the claim the citation backs.
     - If the cited paper has source material in `<thread>/refs/` (a PDF or notes file whose name or content references the BibTeX key), read it and assess: does the cited paper support the surrounding claim? Record a verdict per citation: `supports`, `does-not-support`, `partial`, `unverified — source not on disk`.
     - For `does-not-support`, set a critical flag (citation error).
     - For `unverified`, record but do NOT flag (this is a known limitation of LLM-based audit; the human author is responsible for off-disk verification).
   - Format `citation-audit.md` as a markdown table: `| Key | Resolved | Surrounding claim | Verdict | Notes |`.
6. **Numerical audit** (`numerical-audit.md`):
   - Enumerate numerical values in the abstract, results section, conclusion, and any explicit comparisons (e.g., "5x speedup", "87.3% accuracy").
   - For each, find the corresponding figure or table (typically referenced by `\ref{tab:results}`, `\ref{fig:scaling}`) and verify the text matches.
   - Record discrepancies in `numerical-audit.md` as a table: `| Text claim | Source (Tab/Fig) | Source value | Match | Notes |`.
   - For each mismatch, set a critical flag in `flags.md` (numerical inconsistency).
7. **Figure source-of-truth check** (informational — does not flag unless explicitly stale):
   - For each `\includegraphics{figures/<name>.pdf}` reference, check whether `figures/src/<name>.py` (or analogous source) exists.
   - If a source script exists and its mtime is newer than the rendered figure, note in `numerical-audit.md` as "figure may be stale — script newer than render". This is informational; the reviser or figurer is responsible for re-rendering. Set a non-critical note in `flags.md` if any stale figures are detected.
8. **Write `flags.md`**: a markdown list of critical flags, each with one-paragraph justification and the specific evidence (line numbers, table references, log excerpts) needed for the reviser to act.

   ```markdown
   # Audit flags for <thread>.{N}

   ## Critical flags (block advancement to AUDITED)

   - **Unresolved citation** (`\cite{smith2024}`): no matching entry in refs.bib. Surrounding claim: "...".
   - **Claim-support failure** (`\cite{jones2023}`): paper does not support the surrounding claim. Evidence: <excerpt from refs/jones2023.pdf or notes>.
   - **Numerical inconsistency** (Sec. 5 vs Table 2): text says 87.3%, table says 87.1%.
   - **Build failure**: bibtex main exited non-zero. See compile-log.txt lines 142–158.

   ## Non-critical notes

   - **Stale figure**: figures/scaling.pdf is older than figures/src/scaling.py — re-render recommended.
   - **Unverified citations** (4): claim-support could not be verified because source PDFs are not in <thread>/refs/. Author should verify off-disk.
   ```
9. **Update `_progress.json`** inside the staging dir: `phases.audit.state = done`, `phases.audit.completed = <ISO>`. Record summary counts in metadata: `metadata.audit_summary = { critical_flags: <N>, unverified_citations: <M>, ... }`. This is the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires `_progress.json` to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies every name in the required-files manifest exists in the staging dir, then atomically renames `.<thread>.{N}.audit.tmp/` → `<thread>.{N}.audit/`. The final-named dir only ever exists in **complete** form.
10. **Report**: print the path to the (now-renamed) audit dir and a one-line status (e.g., `Audited q3-method.2 → q3-method.2.audit/ (0 critical flags, 3 unverified citations, build OK)`).

## State machine impact

- If `flags.md` records **zero critical flags** AND the paper was already `READY`, the thread is now `AUDITED` (terminal).
- If `flags.md` records any **critical flag**, the thread remains `READY-WITH-AUDIT-FLAGS` (not terminal). The orchestrator recommends `pub-revise`, which consumes the audit sibling alongside the review sibling to produce the next version.
- A version that reaches `AUDITED` is the deliverable. There is no `READY` → `AUDITED` re-review loop unless the reviser produces a new version.

## Idempotence and resumability

- A completed audit (`audit.state == done` AND `flags.md` exists) is never re-run automatically. A new `<thread>.{N+1}.audit/` is created only after a new version dir exists.
- A crashed audit is re-runnable after deleting partial output.

## Notes for the auditor agent

- **Do not fabricate verifications.** If a cited paper's source material is not in `<thread>/refs/`, mark the citation `unverified` and move on. A `supports` verdict that is actually a hallucination is worse than an honest `unverified`.
- **Build failures are critical.** A paper that does not compile is not a paper. Even a single unresolved `??` citation in the rendered PDF is a critical flag — the reader will see it.
- **Numerical audit is mechanical.** When the abstract claims 87.3% and Table 2 shows 87.1%, flag it. Do not try to figure out which is "really" right — the reviser will fix the inconsistency. Both `87.3` and `87.1` cannot be the same number.
- **Stale figures are advisory, not critical.** A rendered figure older than its source script may or may not be stale (the script may not have changed in a meaningful way). Surface as a non-critical note for the reviser to investigate; do not block.

## `_progress.json` snippet (audit sibling)

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "audit": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  },
  "metadata": {
    "audit_summary": {
      "critical_flags": 0,
      "unresolved_citations": 0,
      "claim_support_failures": 0,
      "numerical_inconsistencies": 0,
      "unverified_citations": 3,
      "stale_figures": 1,
      "build_status": "ok"
    }
  }
}
```

## Git sync (opt-in, off by default)

If the consumer repo carries `.anvil/config.json` with `git.commit_per_phase: true`, end this phase per the per-phase git commit/sync hook documented in `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo): after the staged-sidecar atomic rename (issue #350) lands the final-named `<thread>.{N}.audit/`, stage ONLY this command's own `<thread>.{N}.audit/` sidecar (never sibling critics' dirs — the narrow scope keeps the hook safe under parallel critic fan-out), commit as `anvil(pub/audit): <thread>.{N} [<state>]` (the bracket carries the thread's derived state per SKILL.md §State machine after the audit lands — `AUDITED` when the audit passes alongside a `READY` version), and push when `git.push` is also `true`. Git failures (not a git repo, commit failure, offline push) emit a one-line warning and continue — the audit still reports its own verdict unchanged; artifact-on-disk is the source of truth. When `.anvil/config.json` is absent or `git.commit_per_phase` is false/absent, skip this step entirely — behavior is byte-identical to a pre-#426 install (default off).
