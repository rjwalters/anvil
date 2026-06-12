---
name: ip-uspto-inventorship
description: Inventorship interview generator. Produces a per-independent-claim attribution matrix the human attorney countersigns. Run before first draft AND re-run before finalize once claims are stable. Opt-in --evidence mode mines repo git history into reduction-to-practice citations that pre-fill the matrix Notes column only.
---

# ip-uspto-inventorship — Inventorship interviewer

**Role**: inventorship interviewer.
**Reads**: `<thread>/BRIEF.md`. If a latest `<thread>.{N}/claims.tex` exists, also read it for per-claim attribution.
**Writes**: `<thread>/inventorship.md` — the inventorship matrix, with one row per independent claim and a column per named inventor.

**Why this matters**: 37 CFR 1.63 (the inventor's oath/declaration) requires correct inventorship. Mis-attributed inventorship is grounds for **unenforceability** of the issued patent — the issue can be raised during litigation and the patent invalidated. This is one of the highest-stakes correctness questions in the entire filing.

## Inputs

- **Thread slug** (positional argument).
- **`<thread>/BRIEF.md`**: required. Provides the named inventors and the inventive features.
- **`<thread>.{N}/claims.tex`** (optional): if a draft exists, the inventorship matrix attributes each independent claim's inventive concept(s) to named inventors. Without claims, the matrix attributes the inventive features from `BRIEF.md` §3.
- **`--evidence [<repo_path>]`** (optional flag, opt-in): additionally mine the git history of the implementation repository at `<repo_path>` (default: the git toplevel of the current working directory) into reduction-to-practice evidence artifacts, and pre-fill the matrix **Notes column only** with commit citations. See "Evidence mode" below. **Without this flag, behavior is byte-identical to the base command — no git access, no evidence artifacts.**
- **`--reseed`** (optional flag, only meaningful with `--evidence`): discard the cached `inventorship_map.json` and re-seed the element→paths map from scratch.

## Outputs

```
<thread>/
  inventorship.md   Inventorship interview prompts + attribution matrix + attestation block
  inventorship-evidence/        (--evidence mode only; thread-level, like the matrix)
    inventorship_map.json       Element/feature → repo-paths map (semi-manual seed; cached)
    evidence.jsonl              Append-only git evidence rows (reduction-to-practice citations)
```

The file has the following structure:

```markdown
---
thread: <slug>
inventors:
  - name: <Full Name>
    role: <e.g., "principal investigator", "lead engineer">
generated_against: BRIEF.md  # or "thread.3/claims.tex" once claims exist
generated_at: <ISO>
matrix_locked: false           # set to true once human attorney countersigns
---

# Inventorship matrix — <thread>

## Source basis

This matrix attributes inventive contribution either to:
- (A) **Inventive features** as enumerated in `BRIEF.md` §3 (used when no claims exist yet), OR
- (B) **Independent claims** as drafted in `<thread>.{N}/claims.tex` (used once claims are stable).

Current basis: <A or B with version reference>.

## Interview prompts (give these to each named inventor)

For each <feature | claim>, ask:

1. **Who conceived this <feature | claim limitation>?** (Conception = the formation in the mind of a definite and permanent idea of the complete and operative invention. The conceiver is an inventor.)
2. **Was this conceived in collaboration?** If yes, name every collaborator and describe each person's contribution to the conception.
3. **When was this first conceived?** (Date, even approximate.)
4. **Was conception communicated to anyone (orally, in writing, code commits) before reduction to practice?** Reduction to practice (a working implementation or constructive reduction via filing) is distinct from conception.
5. **Has anyone NOT named here contributed to the conception?** (Reduction to practice alone is NOT inventorship. Lab assistants who built but did not conceive are NOT inventors.)

## Matrix

| #  | Feature or claim                                                       | Inventor 1 | Inventor 2 | Inventor 3 | Notes |
|----|------------------------------------------------------------------------|------------|------------|------------|-------|
| F1 | <feature 1 from BRIEF §3, or claim 1 from claims.tex>                  | ●          |            |            |       |
| F2 | <feature 2, or claim N>                                                | ●          | ●          |            | Joint conception over a 2-week period |
| ...|                                                                        |            |            |            |       |

Mark `●` for each inventor who conceived (in whole or part) the feature or claim limitation.

## Attribution rules

- An inventor must conceive at least one limitation of at least one issued claim to qualify. If after the matrix is filled, a named inventor has no `●` against any claim, they should be **removed** from the inventor list. Conversely, if anyone is `●` who is NOT in the named inventor list, they must be **added** (37 CFR 1.48 covers correction post-filing, but the cleaner path is to fix before filing).
- Lab assistants, technicians, and engineers who built a working implementation without conceiving are NOT inventors. Include them in the spec acknowledgments if appropriate.
- A supervisor or PI who funded or directed the work but did not conceive is NOT an inventor.
- Joint conception requires actual collaboration on the inventive concept. Two people who independently arrived at the same idea are not joint inventors of that idea; only one can be the inventor of that limitation (the earlier in time, generally).

## Attestation block (for human attorney countersignature)

I have reviewed the matrix above and the underlying interviews. I confirm:

- [ ] All conceiving inventors are named.
- [ ] No non-conceiving contributors are named.
- [ ] The matrix is consistent with the current claim set (or, if drafted pre-claims, the inventive features in `BRIEF.md` §3).
- [ ] Each named inventor has separately agreed to sign the 37 CFR 1.63 declaration.

Attorney signature: ___________________________  Date: ___________
```

## Procedure

1. **Discover state**: check whether `<thread>/inventorship.md` already exists.
   - If yes AND `matrix_locked: true` in frontmatter AND it was generated against the same basis (BRIEF.md or the same `claims.tex` version), exit early with a notice (idempotent).
   - If yes AND it was generated against an OLDER basis (claims have advanced since), back it up to `inventorship.{N-1}.md` and proceed with a fresh generation.
   - If yes AND `matrix_locked: false` and the basis is current, exit with a notice: "matrix exists and is current basis; attorney signature pending."
2. **Read inputs**:
   - `<thread>/BRIEF.md` — extract named inventors from the frontmatter and inventive features from §3.
   - Latest `<thread>.{N}/claims.tex` — if present, extract independent claims (parse `\begin{claim}...\end{claim}` blocks numbered 1, M, ... that are not dependent on a prior claim).
3. **Pick basis**:
   - If `claims.tex` exists at any version, use **basis B (claims-based)** with the highest-N version.
   - If no claims yet, use **basis A (feature-based)** from `BRIEF.md` §3.
4. **Generate the matrix**:
   - Frontmatter: thread slug, named inventors (from BRIEF), basis identifier, `generated_at` timestamp, `matrix_locked: false`.
   - Interview prompts: the 5-question list above (copy verbatim — these are legally derived).
   - Matrix: one row per feature (basis A) or per independent claim (basis B). Pre-fill `●` entries based on:
     - (basis A) The inventor most likely associated with each feature based on `BRIEF.md` context. **If uncertain, leave the cell blank and add a note "ATTRIBUTION TBD — pending inventor interview".** Never guess at attribution.
     - (basis B) The features-to-claims mapping should be evident from the spec's reference numerals and the claim language. Again, only pre-fill where the attribution is unambiguous from the source material.
   - Attribution rules: copy verbatim (these are 37 CFR 1.45 and case law derived).
   - Attestation block: copy verbatim, leave all checkboxes unchecked and attorney signature blank.
5. **Report**: print the path written and a one-line summary (e.g., `Inventorship matrix generated: acme-widget/inventorship.md (basis: thread.3/claims.tex, 3 independent claims, 2 named inventors, 4 attribution cells pre-filled, 5 marked TBD)`).

## Evidence mode (`--evidence`) — v1, opt-in

`ip-uspto-inventorship <thread> --evidence [<repo_path>] [--reseed]`

Mines the implementation repository's git history into an evidentiary trail backing the matrix. For AI-assisted invention this trail is increasingly load-bearing: reduction-to-practice attribution backed by commits, not recollection.

**What evidence mode is — and is not (advisory-only contract):**

- Git history documents **reduction to practice** (who committed working implementation), NOT **conception** (the legal test for inventorship). Every git-derived annotation MUST carry the reduction-to-practice label and the conception caveat.
- Evidence **informs the attorney interview; it never adjudicates**. It never adds or removes named inventors, and it never marks or unmarks `●` cells — the `●` pre-fill rules in the Procedure above (including "Never guess at attribution") govern unchanged.
- Evidence pre-fills the matrix **Notes column only**.

### Step E1 — Path map (`inventorship_map.json`): seed, cache, reseed

The map associates each matrix row key (feature IDs under basis A, claim element labels under basis B — matching the basis selected in Procedure step 3) with the repo paths that implement it:

```json
{
  "thread": "acme-widget",
  "basis": "B:thread.3/claims.tex",
  "seeded_at": "2026-06-12T00:00:00Z",
  "vendored_prefixes": ["third_party/", "vendor/"],
  "elements": {
    "C1": {
      "label": "Independent claim 1 — adaptive widget controller",
      "paths": [
        {"path": "src/controller.py", "role": "primary", "manually_seeded": true, "seeded_at": "2026-06-12T00:00:00Z", "lines": [40, 120]}
      ]
    }
  }
}
```

- `role` is one of `primary` / `vendored-primary` / `diverged-copy` / `supporting`.
- **Seeding is semi-manual**: on first run the agent proposes the element→paths map (from the basis rows and its reading of the repo) and the **operator confirms it** before the map is written. Path attribution is never guessed silently.
- **Cache semantics**: on reruns the cached map is reused and re-validated. A mapped path that has moved or disappeared produces a `stale-path` finding that **prompts the operator** for the new location — the cached map is never silently updated. `--reseed` discards the cache and seeds fresh.
- `vendored_prefixes` is an optional operator-maintained list; any mapped path under a listed prefix (or with role `vendored-primary`) is **BLOCKED** for evidence purposes: local git history attributes the importer, not the author, so upstream history is required. BLOCKED paths surface in the matrix Notes and the command report — never silently skipped.

### Step E2 — Deterministic mining (`inventorship_evidence.py`)

Run the skill-local lib by direct file path (the skill dir is hyphenated, so there is no dotted `python -m` path; in an installed consumer repo the path is `.anvil/skills/ip-uspto/lib/inventorship_evidence.py`):

```bash
python3 anvil/skills/ip-uspto/lib/inventorship_evidence.py \
  <thread>/inventorship-evidence/inventorship_map.json \
  --repo <repo_path> \
  --write-evidence <thread>/inventorship-evidence/evidence.jsonl
```

JSON report to stdout. Exit codes per the tool-evidence convention: `0` = clean collection; `1` = findings (vendored/BLOCKED paths, `suspected-vendored` bulk-import heuristic hits, stale map paths, zero-history paths) — review each finding with the operator; `2` = invocation error (invalid map, git unavailable, not a git repository) — evidence mode degrades gracefully: report the error and continue with the matrix un-annotated.

`evidence.jsonl` is **append-only**, one JSON object per (path, sha): `{path, sha, author, email, date, subject, claim_element, classification, rationale}`. The miner emits `classification: "unclassified"`; rows already present (including rows the classification step has annotated) are never rewritten.

The miner also flags `suspected-vendored` when a path's add-commit touches more than 50 files AND its message matches the vendor heuristic (`vendor|import|port|migrat|consolidat`, case-insensitive) — prompt the operator before treating that history as authorship evidence.

### Step E3 — Classification (LLM step, in this command)

For each unclassified row, read the commit's **diff content** (via the lib's `commit_diff` helper, ~4000-char per-commit budget) and classify it as `conception` / `implementation` / `mixed` / `unclassified`, writing the classification and a one-line `rationale` back to the row. **Classify on diff content, never on the commit message alone** — commit messages are the #1 documented misclassification source. A commit whose diff introduces the inventive mechanism itself may evidence conception-adjacent activity; note it for the interview, but it still proves only reduction to practice.

### Step E4 — Matrix pre-fill (Notes column ONLY)

For each matrix row with classified evidence, append citations to the **Notes** cell in this shape:

```
git evidence (RTP): abc1234 Alice Author, 2025-03-02 — adds adaptive threshold loop
```

- `(RTP)` — the reduction-to-practice label — is mandatory on every annotation.
- BLOCKED paths render as `BLOCKED — vendored path (upstream history required): third_party/blob/` in the row's Notes.
- Add this caveat once, directly beneath the matrix table:

> Git evidence above documents **reduction to practice only**. Conception — the legal test for inventorship — must be established through the inventor interviews. A commit author is not thereby an inventor; an inventor need not appear in the commit log.

- **Never touch any other column.** `●` cells, inventor columns, and TBD markers follow the base rules exactly as if `--evidence` were not passed.
- **Locked matrix**: if `matrix_locked: true`, the matrix file is never modified (same rule as the base command); evidence artifacts are still written/refreshed under `<thread>/inventorship-evidence/`, and the report notes that Notes pre-fill is pending the next unlocked regeneration.

### Evidence-mode report

Extend the step-5 report line with an evidence summary, e.g. `evidence: 14 rows mined (3 new), 11 classified, 2 findings (1 stale-path, 1 suspected-vendored), 1 BLOCKED vendored path`.

### Out of scope for v1

Inventor-interview packet generation (`--interview`) and determination synthesis (`--synthesize`) are deliberately deferred to a follow-up issue — the evidence contracts above are designed so that pass is purely additive.

## Re-validation pre-finalize

After the claim set stabilizes (during AUDITED → FINALIZED transition), re-run this command to regenerate the matrix against the final `claims.tex`. The previous matrix is backed up. The human attorney must re-attest against the final matrix before `ip-uspto-finalize` will proceed.

## Idempotence

- A locked (`matrix_locked: true`) matrix generated against the current basis is never overwritten.
- An unlocked matrix against the current basis is preserved (a no-op with a notice).
- An out-of-date matrix is backed up before being replaced.
- The operator can force regeneration by deleting `inventorship.md`.

## Notes for the inventorship agent

- **Pre-fill conservatively.** It is far less harmful to leave a cell blank and let the human attorney fill it after interviews than to pre-fill incorrectly and have the attorney accept the bad attribution by inattention.
- **Never invent inventors.** Only the inventors named in `BRIEF.md` frontmatter may appear in the matrix.
- **Conception ≠ reduction to practice.** This distinction is the source of most inventorship errors. The matrix attribution rules document it; the matrix itself enforces it by only listing the conceiving step.
- **Re-validation is mandatory pre-finalize.** Claims often change during revision (a claim limitation gets added, removed, or shifted between independents and dependents). The matrix MUST track the final claims, not just the first-draft features.


**Snippet references**: See `anvil/lib/snippets/progress.md` for the `_progress.json` read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC timestamp convention. The merge is shallow: preserve fields and phases not touched by this command.

## Git sync (opt-in, off by default)

If the consumer repo carries `.anvil/config.json` with `git.commit_per_phase: true`, end this phase per the per-phase git commit/sync hook documented in `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo): after `<thread>/inventorship.md` is written, stage ONLY `<thread>/inventorship.md`, staged explicitly by path (a thread-level file per the snippet's staging rules), commit as `anvil(ip-uspto/inventorship): <thread> [<state>]` (a thread-level command with no version dir — the version token is the bare thread slug per `git_sync.md` §Commit-message shape → "Non-thread commit shapes"; the bracket is `INVENTORSHIP_DONE` on the pre-draft run, or the thread's current derived state on a pre-finalize re-validation), and push when `git.push` is also `true`. A preserved-matrix no-op run writes nothing, so the hook has nothing to commit and is a silent no-op. Git failures (not a git repo, commit failure, offline push) emit a one-line warning and continue — the command still reports success; artifact-on-disk is the source of truth. When `.anvil/config.json` is absent or `git.commit_per_phase` is false/absent, skip this step entirely — behavior is byte-identical to a pre-#426 install (default off). In `--evidence` mode, additionally stage `<thread>/inventorship-evidence/inventorship_map.json` and `<thread>/inventorship-evidence/evidence.jsonl` (explicitly by path) in the same commit when they were written or appended this run; default (no-flag) runs stage exactly what they staged before.
