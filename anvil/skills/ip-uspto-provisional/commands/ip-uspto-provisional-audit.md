---
name: ip-uspto-provisional-audit
description: Final fact-check audit pass on a READY provisional application. Verifies inventor names, title/field-of-use, reference numerals, dates/citations, background admissions, and related-application term attribution across spec and drawings. Runs only after convergence (the provisional READY marker is present). Claims-optional — claim/abstract checks are dropped; a claim-seed, if present, is checked at major cap.
---

# ip-uspto-provisional-audit — Auditor

**Role**: auditor.
**Reads**: latest `<thread>.{N}/` (entire content) plus `<thread>/BRIEF.md` for ground-truth checks.
**Writes**: `<thread>.{N}.audit/` with `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`.

The audit sibling is **read-only once written**. A failed audit blocks `ip-uspto-provisional-finalize`.

## How the provisional audit differs from `ip-uspto-audit`

This command is templated on `anvil:ip-uspto`'s `ip-uspto-audit` but adapted to the claims-optional, no-inventorship-gate, no-abstract posture of a provisional (SKILL.md §"Claims-optional posture", §"Artifact contract"):

- **Discovery marker is `READY`, NOT `READY_FOR_AUDIT`.** The provisional reviser writes a `_revise-result.md` whose header is `READY` (see `ip-uspto-provisional-revise.md` Path A); there is no `READY_FOR_AUDIT` marker in this skill.
- **No abstract checks.** A provisional has no `abstract.txt` (SKILL.md:55) — the abstract-correctness check is dropped entirely.
- **No required-claims checks.** Claims are optional. The claim-spec-terminology and numerical-consistency-against-claims checks become *conditional*: they run only if a `claims.tex` claim-seed is present, and any finding inside a present seed caps at severity `major` (a seed claim is not a filed claim — SKILL.md §"Claims-optional posture"). The **absence** of a claim-seed is never a finding.
- **No inventorship-matrix check.** There is no `inventorship.md` gate in this skill (no per-claim attribution without required claims). The inventorship-matrix-currency check is dropped.
- **Inventor-name consistency carries over against `BRIEF.md` only** (the provisional has no `inventorship.md` intermediate to cross-check).
- Reference-numeral coherence, title/field-of-use, date/citation-vs-priority, background-admission, and drawing-stub checks all **carry over unchanged**.

The `anvil-uspto.cls` LaTeX class and spec scaffold are reused from `anvil:ip-uspto`'s `assets/` per the install-coupling contract (SKILL.md §"Install coupling"); this command adds no new assets.

## When this runs

The audit is a **post-convergence** phase. It runs only when:
1. The current version has `_revise-result.md` with header `READY`, AND
2. No audit sibling exists yet for this version.

The audit is NOT one of the parallel critics. It runs once per terminal version, after convergence. Its role is fact-checking, not scoring.

## Inputs

- **Thread slug** (positional argument).
- **READY version directory**: highest `N` with `<thread>.{N}/_revise-result.md` whose header is `READY` (NOT `READY_FOR_AUDIT`).
- **Ground-truth sources**:
  - `<thread>/BRIEF.md` — for inventor names, field of use, intended invention, and `priority_date_target`.
  - `<thread>/prior-art/**` — for verifying any prior-art citations or admissions in the spec.
  - `<thread>/refs/**` — the per-thread document input the draft command already enumerates; Check 9 reads the related application's text from here when a candidate document is present (see Check 9). No BRIEF key is involved.
- **Optional claim-seed**: `<thread>.{N}/claims.tex` — present only when the operator/drafter opted into one.

## Outputs

```
<thread>.{N}.audit/
  _summary.md       Pass/fail boolean + per-check status
  findings.md       Itemized findings (severity, location, rationale, suggested fix)
  _gate.json        Render-gate backstop result (issue #572) — GateResult.to_json() payload
                    from Check 8; consumed by ip-uspto-provisional-finalize's pre-finalize gate
  _meta.json        { critic: "audit", role: "ip-uspto-provisional-audit.md", started, finished, model,
                      schema_version, scorecard_kind: "machine-summary",
                      rubric_id: "anvil-ip-provisional-v1", rubric_total: 45, advance_threshold: 39 }
  _progress.json    Phase state for the audit
```

**Atomicity** (issue #350, #376): the audit sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The four files (`_summary.md`, `findings.md`, `_meta.json`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.audit.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.audit/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.audit.tmp/` dir on disk that the next invocation's `cleanup_one_staging(<thread>.{N}.audit)` per-critic sweep removes; the final-named dir never exists in partial form. Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/_revise-result.md` whose header is `READY` (NOT `READY_FOR_AUDIT` — that marker does not exist in this skill). If no such version exists, exit with an error: "no version is READY; complete the revise cycle first." Then **sweep a stale staging dir from a prior interrupt of THIS critic on THIS version** by invoking `anvil/lib/sidecar.py::cleanup_one_staging(<thread>.{N}.audit)` (the per-critic, parallel-safe sweep — issue #376). This removes ONLY a leftover `.<thread>.{N}.audit.tmp/` from a previously-killed run of this same critic on THIS version. Sibling critics' in-flight staging dirs under the same portfolio root are NOT touched (issue #350, #376).
2. **Idempotence check**: if `<thread>.{N}.audit/` exists (the atomic-rename contract guarantees the dir only exists when complete), exit early.
3. **Resume check**: per the staged-sidecar shape introduced in issue #350, a partial audit left behind by a mid-cycle interrupt manifests as a leading-dot `.<thread>.{N}.audit.tmp/` directory; the step 1 sweep has already removed it. Backwards-compat: if a legacy pre-#350 `<thread>.{N}.audit/` exists without `_summary.md`, delete and re-audit.
4. **Open the staged sidecar** for the audit dir by invoking the context manager `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.audit, required_files=["_summary.md", "findings.md", "_gate.json", "_meta.json", "_progress.json"])`. Every file write below MUST land **inside the yielded staging directory** (the path of the shape `.<thread>.{N}.audit.tmp/`), NOT inside the final `<thread>.{N}.audit/` path. On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name (issue #350). Then, **inside the staging dir**, initialize `_progress.json`. The `_gate.json` file is written by Check 8 (render-gate backstop, issue #572) and is part of the required-files manifest — a Check 8 skip due to engine-unavailable still writes an `_gate.json` payload with `compile_status="unavailable"` so the manifest is satisfied.

   **Non-Python-driver ordering (fail-open, manual fallback)** — issue #645: `staged_sidecar` is a Python context manager. A manual/agent session with **no orchestrating Python driver** cannot hold its `with` block open across the file writes below (it writes files with its own editing tool between discrete steps), so it MUST use the equivalent CLI shim rather than writing straight into the final `<thread>.{N}.audit/` dir (which silently reopens the #350 partial-write defect this primitive exists to close). Two tiers, in preference order:

   1. **Primary — `python -m anvil.lib.sidecar` CLI shim** (the common case). In an installed consumer repo (anvil vendored under `.anvil/`, not on `sys.path`), prefix every invocation below with `uv run --project .anvil` (the `.anvil/pyproject.toml` + `uv sync --project .anvil` shipped by the installer since #230 make the module resolvable from the consumer root — the same shape the other `anvil.lib.*` critics already use); in the anvil source repo the bare `python -m anvil.lib.sidecar` form works as-is. This wraps the *exact same* `staged_sidecar` code, so the manifest check + single atomic `Path.rename` are enforced by code, not agent discipline:
      - `uv run --project .anvil python -m anvil.lib.sidecar stage <thread>.{N}.audit` → prints the staging path (`.<thread>.{N}.audit.tmp/`). (Refuses with a nonzero exit if `<thread>.{N}.audit/` already exists — matching `staged_sidecar`'s `FileExistsError` refuse-to-overwrite guard.)
      - Write **all** required files (`_summary.md`, `findings.md`, `_gate.json`, `_meta.json`, `_progress.json`) into that printed staging path — never into the final `<thread>.{N}.audit/` name.
      - `uv run --project .anvil python -m anvil.lib.sidecar commit <thread>.{N}.audit --required _summary.md,findings.md,_gate.json,_meta.json,_progress.json` → verifies the manifest, then atomically renames staging → final. **Nonzero exit (1) leaves the staging dir in place with no partial final dir** if any required file is missing — the `SidecarIncompleteError` analog; fix the gap and re-`commit`.
      - The stale-staging sweep of step 1 has an exact CLI analog: `uv run --project .anvil python -m anvil.lib.sidecar cleanup <thread>.{N}.audit` (the parallel-safe per-critic sweep, issue #376).
   2. **Last resort — manual `mv`-based staging** when even `python`/`uv` is unavailable. Reproduce the staging contract by hand: (a) at entry, sweep any leftover `rm -rf .<thread>.{N}.audit.tmp/` (the `cleanup_one_staging` analog); (b) `mkdir .<thread>.{N}.audit.tmp/` and write **every** required file into it — writing `_progress.json` **last**, so a mid-write interrupt is caught by the missing-manifest check rather than producing a final-named partial; (c) confirm the staging dir holds the full required set — use a count check (`[ "$(ls -1 .<staging-dir> | wc -l)" -eq <N> ]`) or an `ls`-based presence check rather than per-file `[ -f ]`, which can false-negative under a restricted-`stat` sandbox — **then** `mv .<thread>.{N}.audit.tmp <thread>.{N}.audit` as the **last** step (POSIX `mv` on a same-filesystem dir-to-dir rename is atomic, matching `Path.rename`). Do NOT create `<thread>.{N}.audit/` before all files are staged. **Record the fallback durably** so a reader can tell atomicity was reproduced by hand rather than tool-verified: stamp `_meta.json` with `"atomicity_fallback": "manual-mv"` (e.g. `sidecar: staged_sidecar CLI unavailable (uv/python not on PATH); atomicity reproduced via manual mv this pass`). Absent this note the manual staging is indistinguishable from an unsafe direct write.

   The two tiers land a byte-identical on-disk result to the `staged_sidecar` context-manager path; they exist only to give a Python-less session a code-enforced (tier 1) or contract-faithful (tier 2) route to the same atomicity guarantee. When an orchestrating Python driver IS present, use `staged_sidecar` directly as documented above — the CLI shim is not needed. (If your agent harness pattern-matches and rejects the `findings.md` filename on a `Write`, a Bash-heredoc write into the staging dir is an accepted fallback — see `anvil/lib/snippets/critics.md` §"Orchestrator output-file guard collisions".)

5. **Run audit checks** (collect findings; do not short-circuit):

   ### Check 1 — Inventor name consistency
   - Inventors in `spec.tex` front matter MUST match exactly (spelling, ordering, affiliation) the inventors in `<thread>/BRIEF.md` frontmatter. (The provisional has no `inventorship.md` intermediate — `BRIEF.md` is the single source of truth.)
   - Any mismatch → severity `blocker`.

   ### Check 2 — Title and field-of-use consistency
   - `spec.tex` title must match `BRIEF.md` frontmatter `title` (or be a clearly equivalent restatement).
   - Field of use stated in `spec.tex` FIELD section must match `BRIEF.md` frontmatter `field_of_use`.
   - Mismatch → severity `major`.

   ### Check 3 — Reference numeral coherence (full)
   - For every reference numeral appearing in `spec.tex`, the same numeral must appear in at least one figure (or figure stub description) referring to the same component.
   - For every reference numeral in any drawing or stub, the numeral must appear in `spec.tex`.
   - The component name associated with a numeral must be **consistent** across spec and drawings (e.g., `12` cannot mean "input port" in spec and "housing" in fig-2).
   - **Mechanical first pass (issue #1500)**: before the manual pass, run the deterministic name-consistency script over the version dir (invoked by **file path** — the hyphenated skill dir is not importable; in an installed consumer repo the path is `.anvil/skills/ip-uspto-provisional/lib/numeral_names.py`):

     ```
     python3 anvil/skills/ip-uspto-provisional/lib/numeral_names.py <thread>.{N}          # text findings
     python3 anvil/skills/ip-uspto-provisional/lib/numeral_names.py <thread>.{N} --json   # machine-readable
     ```

     The script collects, for every reference numeral, the element name used with it in the brief descriptions, the detailed description, any numeral index and the drawing descriptions (whitespace-normalised after LaTeX-comment stripping, so a name split across two source lines is still found) and lists numerals carrying more than one name, with each differing name, the `\anvilpara` paragraph number `[000N]`, and the section.
   - Each reported numeral is a **candidate** for this check, not an automatic finding: the extraction is heuristic (a legitimate short form "bridge 10" vs "sense bridge 10" is expected non-noise), so the auditor confirms each candidate in context. A **confirmed** rename mismatch keeps this check's existing `blocker` severity; a short-form/shared-head variant the script already de-duplicates needs no action.
   - Each kind of inconsistency → severity `blocker`.

   ### Check 4 — Date and citation verification
   - For every cited reference (in Background or elsewhere), check that the publication date precedes the inventor's stated priority date (`BRIEF.md` frontmatter `priority_date_target`). A reference cited as prior art with a date *after* priority cannot be prior art — flag as either a date error or an inadvertent admission.
   - For citations to `<thread>/prior-art/` references, verify the citation text matches the reference's stated `title` / `inventors` / `publication_date`.
   - Mismatch → severity `blocker` if it affects the priority/patentability story, `major` otherwise.

   ### Check 5 — Background admissions audit
   - Re-read the BACKGROUND section. Identify any sentence that could be construed as admitting a particular reference or product is prior art under §103.
   - In US practice, applicant's own admissions in the spec are binding and carry forward to the eventual non-provisional. Flag any unintentional admissions for the reviser/attorney to consider rewording.
   - Severity `major`.

   ### Check 6 — Claim-seed coherence (CONDITIONAL — only if `claims.tex` exists)
   - **If no `claims.tex` is present, this check is SKIPPED and produces NO finding.** The absence of a claim-seed is never a finding (SKILL.md §"Claims-optional posture").
   - If a claim-seed IS present:
     - Terms introduced in the seed (`the widget`, `the processor configured to`) must appear in the spec with consistent meaning. A seed term with NO support in the spec is a real finding (it would pollute the conversion) — but caps at severity `major` (a seed claim is not a filed claim).
     - For every numeric value or range in the spec that also appears in the seed (e.g., "between 5 GHz and 10 GHz"), verify exact agreement. A contradiction caps at severity `major`.
   - Where a seed defect evidences a *disclosure gap* (a seed limitation the spec does not enable), the finding belongs to the disclosure story and may carry whatever severity the gap warrants — record it as such and cross-reference the s112 dimension.

   ### Check 7 — Drawing-stub completeness (v0 specific)
   - In v0, drawings are typically stubs (`drawings/drawing-descriptions.md`). Verify each stub has all four required fields (Type, Components shown, Spatial relationships, Annotations/lead lines).
   - If figures have been rendered (TikZ or external), spot-check that each renders cleanly under the build pipeline.
   - Severity `minor` (informational; figures are typically completed by a human illustrator).

   ### Check 8 — Render-gate backstop (compile + overfull + placeholders, issue #572)
   - **Scratch-directory confinement**: create a fresh private subdirectory (e.g. `mktemp -d`) for ALL scratch/build/render work and run every compile inside it. Never move, rename, delete, or overwrite anything already present in a scratch/temp directory, and never build in a directory that existed before the run; clean up only what you created.
   - Invoke `anvil/lib/render_gate/`'s `compile_and_gate(...)` against `<thread>.{N}/spec.tex` with `engine="pdflatex"`, `page_cap=None`, AND `overfull_threshold_pt=2.0` (the ip-skill legal-artifact calibration override — same value the pre-flight Check 9 uses).
   - **Why this is a check at audit (NOT a duplicate of pre-flight)**: the pre-flight runs at the `REVISED → REVIEWED` loop edge. A late-revise edit AFTER the last pre-flight pass can introduce a new overfull box that reaches the audit unchallenged. This was the load-bearing gap that let the sphere canary's 83.6pt overfull reach a *filed* provisional (issue #572). The audit-time gate is the **backstop**: if the pre-flight was run AND nothing changed after it, this check is a no-op (the same compile is clean). If something DID change, the gate catches the new overfull before `ip-uspto-provisional-finalize` can package it into the COUNSEL-READY filing.
   - **Mechanical / pass-fail** — does NOT score a rubric dimension. Findings with severity `blocker` are added to the audit findings stream, which step 6's pass/fail rule already short-circuits on. On engine-unavailable (`pdflatex` not on PATH), the gate degrades gracefully (`compile_status="unavailable"`) and emits a `minor` finding (not a blocker) — audit still passes on CI without LaTeX.
   - Source-side placeholder patterns are the same set the pre-flight uses (defaults plus the ip-skill-specific `\refnum{??}` / `\anvilpara{}`); duplicate placeholder findings at audit time are not expected (the pre-flight already cleared them) and any hits indicate a post-pre-flight regression.
   - Write the `GateResult.to_json()` payload to the audit staging dir's `_gate.json` for `ip-uspto-provisional-finalize`'s pre-finalize read (see `ip-uspto-provisional-finalize.md` step 4b). The finalize gate refuses to assemble `<thread>.counsel/` when any audit-time overfull finding is present.

   ### Check 9 — Related-application term attribution (ADDED, issue #1500)
   - Scan `spec.tex` for every statement that a related or incorporated application uses a given term — phrasings like "there called X", "a term of the related application(s)", "the related application calls …", "referred to therein as X". This SCAN is LLM/procedure-driven (attribution phrasing is too varied for a regex); the verification it feeds is mechanical.
   - **Input surface (issue #1506)**: the related application's text is read from `<thread>/refs/**` — the existing per-thread document input, where a consumer naturally drops an incorporated application's text. There is **no new config key** (nothing in `BRIEF.md` records a related-application path, and this check does not look there).
   - **Identify the candidate**: a `refs/` file is the related-application text when (a) the spec's incorporation paragraph (the "incorporated herein by reference" statement naming the related application, by title or application number) names it, or (b) it is the single unambiguous match — exactly one document under `refs/**` whose content is a patent application. Do not guess among several.
   - **Skip-when-absent-or-ambiguous**: this check runs ONLY when exactly one candidate is identified. When `refs/` is empty or missing, holds no candidate, or holds several candidates the incorporation paragraph does not disambiguate (ambiguous), record the summary row as `n/a (related-application text not supplied)` — a skip, **NEVER a finding** (the absence of the text is a normal posture, exactly like the claims-optional one; an ambiguous `refs/` is treated the same as an empty one, never as a defect in the spec).
   - When the text IS supplied: open it and confirm each attributed term occurs — **whitespace-normalised, case-insensitive** (the grep for the term itself is mechanical). A term that does not occur → severity `major`: the described behaviour was accurate but the attributed name was not — exactly the canary defect (issue #1500) that cost a full NOT-READY audit cycle because only the auditor happened to look.
   - Report each finding with the term, the `[000N]` paragraph numbers of the attributing statements in `spec.tex`, and where the term was searched (the `refs/` path of the identified related-application document).

6. **Determine pass/fail**:
   - Pass iff no finding has severity `blocker`.
   - `major` findings do not block but should be addressed where feasible. (Per the claims-optional cap, every claim-seed finding is at most `major` unless it evidences a disclosure gap — so a present-but-imperfect claim-seed never, by itself, blocks the audit.)
7. **Write `_summary.md`**:

   ```markdown
   ---
   critic: audit
   for_version: <N>
   passed: <true|false>
   ---

   # Audit summary — <thread>.<N>

   | Check | Result | Findings |
   |---|---|---|
   | 1. Inventor name consistency | pass | - |
   | 2. Title / field-of-use consistency | pass | - |
   | 3. Reference numeral coherence (full) | fail | 2 (orphans on reference 22 and 34) |
   | 4. Date / citation verification | pass | - |
   | 5. Background admissions | major | 1 (Background ¶[0008] could be construed as admitting Smith-2019 as prior art) |
   | 6. Claim-seed coherence | n/a (no claim-seed) | - |
   | 7. Drawing-stub completeness | pass | - |
   | 8. Render-gate backstop (compile/overfull/placeholder) | pass | - |
   | 9. Related-application term attribution | n/a (related-application text not supplied) | - |

   **Overall**: <PASS | FAIL — 2 blockers>

   See `findings.md` for details.
   ```

   When no `claims.tex` exists, row 6 records `n/a (no claim-seed)` — the absence is explicit, not a silent gap. When the related-application text was not supplied (no `refs/` candidate, or an ambiguous one), row 9 records `n/a (related-application text not supplied)` — likewise explicit, likewise never a finding.

8. **Write `findings.md`** in the standard format.
9. **Write `_meta.json`** and finalize `_progress.json` inside the staging dir. `_meta.json` MUST stamp all three rubric-version fields per the per-review version stamping contract (issue #346; SKILL.md §"Uniform critic output schema"): `rubric_id: anvil-ip-provisional-v1`, `rubric_total: 45`, `advance_threshold: 39`, alongside `scorecard_kind: "machine-summary"`. The `_progress.json` write MUST be the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires it to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies every name in the required-files manifest exists in the staging dir, then atomically renames `.<thread>.{N}.audit.tmp/` → `<thread>.{N}.audit/`. The final-named dir only ever exists in **complete** form.
10. **Report**: e.g., `Audit: acme-widget-prov.3.audit/ → FAIL (2 blockers: ref-numeral orphans). Next: address blockers via ip-uspto-provisional-revise.` On pass: `Audit: acme-widget-prov.3.audit/ → PASS. Next: ip-uspto-provisional-finalize to assemble the counsel package.`

## Failure handling

A failed audit (any `blocker` finding) blocks `ip-uspto-provisional-finalize`. The operator should:
- Address blockers via `ip-uspto-provisional-revise <thread>` (this creates a new version; the cycle re-runs critics + re-audit). The aggregate score check still applies — addressing audit blockers doesn't bypass the rubric.

## Idempotence and resumability

- Completed audit on a version is never re-run (it's tied to a specific version that's immutable).
- A new version requires a new audit cycle.
- Crashed audit is re-runnable after deleting partial output (the step 1 sweep handles the leading-dot staging shape automatically).

## Notes for the auditor agent

- **The audit catches what the critics let through.** Critics evaluate against the rubric; the audit catches mechanical and factual issues that don't fit the rubric (inventor name typos, date errors, reference-numeral orphans).
- **Run the Check 3 script, then judge its candidates.** The numeral-name script (issue #1500) makes the stale-name defect — including one wrapped across source lines — mechanically visible; your confirmation pass is what separates a genuine rename mismatch (`blocker`) from a benign short form (no action).
- **Check 9 verifies attributed terms against the actual related-application text when supplied.** The text comes from `<thread>/refs/**` (a file the spec's incorporation paragraph names, or the single unambiguous candidate) — no config key is involved. The canary cost an audit cycle on a term an incorporated application does not contain; when the text is present, the term-occurrence grep is cheap and mechanical — never skip it. When it is absent or ambiguous, record the `n/a` row and move on; the absence is never a finding.
- **Spec admissions are binding — and they carry into conversion.** Background section re-read is high-leverage. An inadvertent admission in a provisional binds the eventual non-provisional.
- **Claims are optional — never invent a claim-seed finding.** If no `claims.tex` exists, Check 6 is `n/a`. The whole point of the provisional posture is that the absence of claims is normal and correct.
- **Severity discipline.** Blocker = the disclosure's priority story is compromised. Major = should be fixed but won't sink the filing decision. Minor = quality of life.

## `_progress.json` snippet (audit sibling)

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "audit": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```


## Scorecard kind

This critic emits the `machine-summary` scorecard kind per `anvil/lib/snippets/scorecard_kind.md`. The `_meta.json` MUST include `"scorecard_kind": "machine-summary"` so any downstream aggregator can correctly discriminate this sibling from any `human-verdict` siblings (e.g., consumer-added narrative critics).

## Git sync (opt-in, off by default)

Per `anvil/lib/snippets/git_sync.md` (`.anvil/anvil/lib/snippets/git_sync.md` in an installed consumer repo): if `.anvil/config.json` exists and `git.commit_per_phase` is `true`, end this phase: stage only the dirs this phase wrote, commit as `anvil(<skill>/<phase>): <thread>.{N} [<state>]`, push if `git.push` is `true`. Git failures warn and continue — never fail the phase. When the config or knob is absent, skip this step entirely (default off).

This phase's specifics:

- **Ordering**: after the staged-sidecar atomic rename (issue #350) lands the final-named `<thread>.{N}.audit/` — so only complete sidecars are ever committed.
- **Staging target**: ONLY this command's own `<thread>.{N}.audit/` sidecar (never sibling critics' dirs — the narrow scope keeps the hook safe under parallel critic fan-out).
- **Commit**: `anvil(ip-uspto-provisional/audit): <thread>.{N} [<state>]` — the bracket carries the thread's derived state per SKILL.md §State machine after the audit lands (`AUDITED` when `_summary.md` records `passed: true` alongside a `READY` version).

