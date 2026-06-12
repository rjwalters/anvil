---
name: ip-uspto-prior-art
description: Novelty / §102 / §103 positioning critic. Evaluates the application against operator-supplied prior art. Does NOT do its own patent search. Owns rubric dimension 5.
---

# ip-uspto-prior-art — Prior-art critic

**Role**: prior-art positioning critic.
**Reads**: latest `<thread>.{N}/spec.tex` + `<thread>.{N}/claims.tex` + `<thread>/prior-art/**` (operator-supplied).
**Writes**: `<thread>.{N}.priorart/` with `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`.

The priorart sibling is **read-only once written**. Critical flags short-circuit convergence.

## Scope and important non-scope

This critic evaluates the application against prior art the **operator has supplied** in `<thread>/prior-art/`. It does **not** perform its own patent search. Patent searching is a distinct discipline (USPTO classification, Boolean queries, Espacenet/Google Patents/PatBase, IPC/CPC classes) that requires dedicated tooling and time budget. A future skill (potentially `anvil:ip-search`) may address it.

If `<thread>/prior-art/` is empty or absent, this critic produces a `_summary.md` noting that no prior art was supplied and recommending operator supply some before re-running. It does NOT score Dimension 5 in that case (leaves score `null`).

## Rubric dimension owned

| # | Dimension | Weight |
|---|---|---|
| 5 | Novelty positioning vs. cited art (§102/§103) | 5 |

## Background — 35 U.S.C. § 102 / § 103

- **§102 (anticipation)**: a claim is anticipated if a single prior-art reference discloses every limitation of the claim. Anticipation is a complete bar to patentability of that claim.
- **§103 (obviousness)**: a claim is obvious if the differences between the claim and the prior art are such that the claimed invention as a whole would have been obvious to a PHOSITA at the time of the effective filing date, in light of one or more references that could be combined.
  - The Graham factors (Graham v. John Deere): scope and content of the prior art; differences between prior art and the claims; level of skill in the art; objective indicia of nonobviousness (commercial success, long-felt need, failure of others).
  - KSR motivation-to-combine: rejects the rigid "teaching, suggestion, motivation" test in favor of a flexible inquiry into whether a PHOSITA would have had reason to combine references.

This critic evaluates each independent claim against each supplied prior-art reference (and combinations) and reports anticipation/obviousness risk.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/claims.tex`.
- **Prior art**: `<thread>/prior-art/**`. Accepted formats:
  - Markdown files describing the reference (preferred): one file per reference, frontmatter with `title`, `inventors`, `publication_date`, `kind` (patent | publication | product), `summary`, `claim_text` (if a patent).
  - PDFs: usable but the critic can only excerpt-and-summarize; for high-stakes references, prefer a markdown summary.
  - Subdirectories per reference are accepted (e.g., `<thread>/prior-art/smith-2019/{summary.md,full.pdf}`).

## Outputs

```
<thread>.{N}.priorart/
  _summary.md       Critic tag priorart, critical flag, dim 5 score, per-reference per-claim risk table
  findings.md       Per-claim per-reference detailed analysis
  _meta.json        { critic, role, started, finished, model, schema_version, scorecard_kind: "machine-summary" }
  _progress.json    Phase state for the priorart critic
```

**Atomicity** (issue #350, #376): the priorart sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The four files (`_summary.md`, `findings.md`, `_meta.json`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.priorart.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.priorart/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.priorart.tmp/` dir on disk that the next invocation's `cleanup_one_staging(<thread>.{N}.priorart)` per-critic sweep removes; the final-named dir never exists in partial form. Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob.

## Procedure

1. **Discover state, resume, init `_progress.json`** (standard). At command entry, **sweep a stale staging dir from a prior interrupt of THIS critic on THIS version** by invoking `anvil/lib/sidecar.py::cleanup_one_staging(<thread>.{N}.priorart)` (the per-critic, parallel-safe sweep — issue #376). Idempotence: if `<thread>.{N}.priorart/` exists (the atomic-rename contract guarantees the dir only exists when complete — issue #350), exit early. Otherwise **open the staged sidecar** for the priorart dir by invoking `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.priorart, required_files=["_summary.md", "findings.md", "_meta.json", "_progress.json"])`. Every file write below MUST land inside the yielded staging directory (the path of the shape `.<thread>.{N}.priorart.tmp/`). On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name. Then, inside the staging dir, initialize `_progress.json`.
2. **Check prior art supply**: enumerate `<thread>/prior-art/**`. If empty, write a `_summary.md` noting "no prior art supplied; Dim 5 unscored" plus `findings.md`, `_meta.json`, and `_progress.json` (all four required-files inside the staging dir), then exit the staged_sidecar context (which atomically renames the staging dir to its final name — this is a `done` state, not an error — operator may legitimately have no prior art at hand for the first review pass).
3. **Read inputs**: parse each prior-art reference into a structured form (title, date, summary, claim text if applicable). Read all claims from `claims.tex`.

### Anticipation analysis (§102)

4. For each prior-art reference, for each independent claim:
   - Map each claim limitation to whether the reference discloses it (yes / partial / no / unknown).
   - If a single reference discloses every limitation → the claim is **anticipated** under §102 → **critical flag**.
   - If a reference discloses most but not all limitations → the claim is at obviousness risk under §103; proceed to step 5.

### Obviousness analysis (§103)

5. For each independent claim not anticipated by a single reference, check combinations:
   - Identify which limitations are missing from each reference.
   - For each subset of references that together disclose all limitations, ask: would a PHOSITA have reason to combine these references? (KSR motivation: explicit teaching, market pressure, design-need-with-finite-solutions, predictable result.)
   - If yes → mark the claim as having **§103 obviousness risk** from that combination. Severity depends on the strength of the combination motivation.
   - If no → the claim survives obviousness against that combination. Note it for the record.
6. Look for **objective indicia of non-obviousness** the spec could (and should) be calling out: unexpected results, commercial success, long-felt unmet need, failure of others. These are not in the spec but should be noted as recommended additions if the analysis hinges on a close obviousness call.

### Dependent claim analysis

7. Dependents inherit their parent's status: if the parent is anticipated, the dependent is anticipated UNLESS it adds a limitation that overcomes the anticipation. The critic should explicitly flag any dependent that overcomes anticipation — these become candidates for elevation to independent status during revision.

### Score Dimension 5 (0–5)

8. Calibration:
   - All independents survive §102 and §103 against the supplied art; spec calls out distinguishing features cleanly; dependent ladder picks up §103 fallback positions: **5**.
   - All independents survive but distinguishing language in spec is thin; ladder is adequate but missing one or two fallbacks: **4**.
   - All independents survive §102 but one is at moderate §103 risk; spec distinguishing language needs strengthening: **3**.
   - One independent is at high §103 risk with weak distinguishing language: **2**.
   - One or more independents anticipated under §102 OR obvious under §103 with overwhelming motivation: **0–1** (critical flag).

### Identify critical flags

9. Set `flagged: true` if any of:
    - An independent claim is anticipated by a single reference in `<thread>/prior-art/`.
    - An independent claim is obvious under §103 over a 2-reference combination with strong KSR motivation, with no dependent claim that overcomes the obviousness.
    - The spec admits a reference as prior art that, on this critic's review, anticipates a claim (admission is binding).

### Write outputs

10. **Write `_summary.md`** with the standard 8-row scorecard (only Dim 5 scored, or `null` if no prior art supplied). Include a per-reference per-claim risk table:

    ```markdown
    ## Risk matrix

    | Claim | Smith-2019 | Jones-2021 | Patel-2023 | Worst case |
    |-------|------------|------------|------------|------------|
    | 1 (independent) | §102 anticipated | not relevant | §103 with Jones | **§102 anticipated** |
    | 9 (independent) | not relevant | partial | §103 risk | §103 moderate |
    | 14 (independent) | not relevant | not relevant | not relevant | clean |
    ```

11. **Write `findings.md`** with one section per (independent claim × relevant reference) pair plus combinations. For anticipated claims, include the limitation-by-limitation map.
12. **Write `_meta.json`** and finalize `_progress.json` inside the staging dir. The `_progress.json` write MUST be the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires it to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies the manifest, then atomically renames `.<thread>.{N}.priorart.tmp/` → `<thread>.{N}.priorart/`. The final-named dir only ever exists in **complete** form.
13. **Report**: e.g., `priorart: acme-widget.2.priorart/ → D5=1, FLAGGED (claim 1 anticipated by smith-2019)`.

## Idempotence and resumability

Standard. Note that re-running this critic after the operator adds more prior art is expected — the critic should re-evaluate against the expanded set.

## Notes for the priorart agent

- **No prior art supplied is a legitimate state.** Score `null`, write the "operator supply more" message, return `done`. Do not invent prior art.
- **Anticipation is binary, obviousness is judgment.** Be precise about which one you are alleging. Calling something "obvious" when it is actually a §102 issue (or vice versa) is a category error that confuses the reviser.
- **The spec's Background section often admits prior art.** Re-read the Background to see what the application itself characterizes as known. Admissions there bind the application.
- **Encourage objective indicia.** If a §103 analysis is close, the spec can sometimes be strengthened by adding objective-indicia language ("the disclosed approach achieves [N]× the performance of prior approaches and addresses a long-standing need in the field"). Note this in findings, not as a flag.
- **Combinations require motivation.** Per KSR, you cannot combine arbitrary references just because together they cover the claim. There must be a reason a PHOSITA would combine them. Be explicit about the motivation in findings.

## `_progress.json` snippet

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "priorart": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```


## Scorecard kind

This critic emits the `machine-summary` scorecard kind per `anvil/lib/snippets/scorecard_kind.md`. The `_meta.json` MUST include `"scorecard_kind": "machine-summary"` so the `ip-uspto-revise` aggregator can correctly discriminate this sibling from any `human-verdict` siblings (e.g., consumer-added narrative critics).

## Git sync (opt-in, off by default)

If the consumer repo carries `.anvil/config.json` with `git.commit_per_phase: true`, end this phase per the per-phase git commit/sync hook documented in `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo): after the staged-sidecar atomic rename (issue #350) lands the final-named `<thread>.{N}.priorart/`, stage ONLY this command's own `<thread>.{N}.priorart/` sidecar (never sibling critics' dirs — the narrow scope keeps the hook safe under parallel critic fan-out), commit as `anvil(ip-uspto/prior-art): <thread>.{N} [<state>]` (the bracket carries the thread's current derived state per SKILL.md §State machine — specialist critics do not advance the state machine on their own), and push when `git.push` is also `true`. Git failures (not a git repo, commit failure, offline push) emit a one-line warning and continue — the phase still reports success; artifact-on-disk is the source of truth. When `.anvil/config.json` is absent or `git.commit_per_phase` is false/absent, skip this step entirely — behavior is byte-identical to a pre-#426 install (default off).
