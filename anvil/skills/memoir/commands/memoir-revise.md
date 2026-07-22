---
name: memoir-revise
description: Reviser for the memoir skill. Consumes ALL critic siblings for the latest version — review, general audit, and (when the corpus tier is active) corpus-audit — and produces a single revised version, never fabricating a provenance.md source-line mapping. REVIEWED+AUDITED → REVISED transition (loops until ≥39/44 with zero critical flags across all active critics, or the iteration cap).
---

# memoir-revise — Reviser

**Role**: reviser (one reviser consumes N critic siblings — here review +
general audit, plus corpus-audit when the corpus tier is active; the
`report`/`primer`/`spec` shape extended to a third conditional sibling).
**Reads**: latest `<thread>.{N}/<thread>.tex` + `_progress.json`,
`<thread>.{N}.review/` (all files), `<thread>.{N}.audit/` (all files),
`<thread>.{N}.corpus-audit/` (all files, when present), `<thread>.{N}/provenance.md`
(when the corpus tier is active), `<thread>/refs/` + shared `research/`,
project `BRIEF.md`.
**Writes**: `<thread>.{N+1}/` with `<thread>.tex`, `provenance.md`
(carried forward + updated, when active), `changelog.md`,
`_progress.json` — or reports `AUDITED` without writing when the
combined verdict pre-check passes.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/<thread>.tex`.
   Require BOTH a completed `<thread>.{N}.review/` AND a completed
   `<thread>.{N}.audit/` (else exit pointing at the missing critic —
   `REVIEWED-PARTIAL`/`AUDITED-PARTIAL` are not advance-eligible per
   SKILL.md). Require `<thread>.{N+1}/` to not exist (immutability —
   never revise in place).
2. **Combined verdict pre-check**: re-resolve
   `anvil/lib/project_brief.py::resolve_corpus_dirs(<project_dir>)` to
   determine whether the corpus tier is currently active (the same
   check `memoir-audit` used when it ran). Read
   `<thread>.{N}.review/verdict.md` and `<thread>.{N}.audit/verdict.md`,
   and — **only when the corpus tier is active** —
   `<thread>.{N}.corpus-audit/verdict.md` (require it to exist when the
   tier is active; its absence at this step means `memoir-audit` has not
   finished the exhaustive sweep yet — treat identically to
   `AUDITED-PARTIAL`, do not proceed).

   The thread is **`AUDITED` — terminal** iff:
   - the review records `advance: true` (total >=39/44, zero unresolved
     review critical flags), AND
   - the general audit records `audit_clean: true`, AND
   - when the corpus tier is active, the corpus-audit sibling ALSO
     records `audit_clean: true` (zero unresolved fabrication-class
     critical flags).

   When all applicable conditions hold: report the publish-handoff
   summary (resolved body path, review total /44, clean audit(s), a
   pointer to `/anvil:project-book` for assembly) and exit WITHOUT
   writing a new version. Otherwise proceed to step 3.
3. **Iteration-cap check**: default `max_iterations: 4` (worst-case
   terminal version `<thread>.5/`); project-BRIEF paired override
   (`max_iterations` + `iteration_cap_rationale`) per the #349 memo
   contract. At cap → report `BLOCKED — human review required` and
   exit.
4. **Read all critic input**: from the review — `verdict.md` (top
   revision priorities first), `scoring.md` (per-dim deductions; dim 1
   sourcing gaps lead), `comments.md`, and the "What's working" list.
   From the general audit — `verdict.md` (critical audit flags first),
   `findings.md` (factual/narrative-consistency findings),
   `comments.md`. From the corpus-audit (when present) —
   `verdict.md` (fabrication-class critical flags first), `findings.md`
   (per-provenance-row classification), `comments.md`. **A critical
   flag from ANY of the three critics blocks** — all must be addressed.
5. **Re-resolve the corpus + voice tiers**: re-invoke
   `resolve_corpus_dirs`, `resolve_voice_docs`, and
   `resolve_subject_voice_docs` against the project `BRIEF.md` and read
   the resolved docs alongside the critic feedback so the revision stays
   consistent with all active tiers. When any critic carried a
   missing/unresolvable-tier `major` finding, surface it in the report
   (the fix is operator-side BRIEF authoring or path correction, not
   body editing).
6. **Build the revision plan**, ordered: (1) critical flags — every flag
   from ANY critic MUST be addressed:
   - **Fabrication-class flags** (`fabricated_quote`,
     `fabricated_fact`, `misattribution_of_substance`, `anachronism`,
     `unattributed_paraphrase` — corpus-audit-side): cut or correct the
     offending claim so it is either removed, or replaced with a claim
     the corpus actually supports (with an updated `provenance.md` row).
     **Never invent a new source-line mapping to paper over the
     finding** — a MISMATCH/NOT_FOUND/FABRICATED classification is
     resolved by changing the CLAIM to match the evidence, never by
     changing the CITATION to match the claim.
   - **`misattribution`** (voice-identity, review-side): rewrite the
     dialogue line in the correctly-attributed speaker's own cadence, or
     re-attribute it to the speaker whose corpus actually supports it.
   - (3) `blocker`/`major` comments from any critic; (4) the
     lowest-scoring dims' deductions; (5) `minor`/`nit` only when they
     don't conflict with (1)-(4). Never touch the "What's working" list.
7. **Write `<thread>.{N+1}/<thread>.tex`** (slug-echo per #295) applying
   the plan. Re-run the drafter's step-7 self-disciplines
   (sourcing-traces-to-provenance check, narrator/subject voice
   interleaving check, scene-craft pass) — the revision must not
   introduce a fresh instance of the failure mode it just fixed.
   - **Carry forward and update `provenance.md`** (when the corpus tier
     is active): every retained claim keeps its row; every changed claim
     gets a re-derived row (a real corpus passage, or an explicit
     `NOT_FOUND` note); every cut claim's row is removed. **Fabricating a
     source-line mapping remains prohibited on revision exactly as on
     first draft.**
   - **Preserve photo-placement macro references**: carry forward
     `\famphoto{...}`/`\fullphoto{...}`/`\marginphoto{...}` calls unless
     a critic specifically flagged a caption/placement problem;
     `memoir-figures` re-resolves them against the manifest.
8. **Write `changelog.md`** mapping each consumed critic note (from
   review, general audit, and corpus-audit) to the change made (or to an
   explicit `declined — <reason>` entry; scoring deductions may be
   argued against, critical flags — from ANY critic — may not).
9. **Initialize `_progress.json`** for the new version:
   `phases.revise.state = done` (LAST write), carry forward
   `metadata.corpus_dirs_resolved` / `metadata.voice_exemplars` /
   `metadata.subject_voice_exemplars` (when active), and **append the
   `score_history` row** for the completed review iteration per
   `anvil/lib/snippets/progress.md` §Convergence fields: `{ "iteration":
   <N>, "total": <reviewed-total>, "threshold": 39, "rubric_id":
   "anvil-memoir-v1" }`. Stable-score termination (`STALLED`) follows
   `anvil/lib/snippets/rubric.md` §"Termination resolution order" over
   this history.
10. **Report**: e.g., `Revised 00-introduction.1 → 00-introduction.2
    (addressed 1 corpus-audit critical flag [NOT_FOUND -> claim cut] + 2
    major comments; 1 declined with reason). Next: memoir-review +
    memoir-audit 00-introduction`.

## What memoir-revise does NOT do

- **Never edits `<thread>.{N}/` or any critic sibling in place** —
  immutability is the audit trail.
- **Never advances state itself** — the next `memoir-review` +
  `memoir-audit` pass scores `<thread>.{N+1}/` on its own merits; there
  is no "the reviser fixed it" credit.
- **Never bypasses a critical flag from any critic** — a changelog
  `declined` entry is legitimate for scoring deductions, never for a
  critical flag.
- **Never fabricates a `provenance.md` source-line mapping to resolve a
  fabrication-class finding** — the fix is always to the CLAIM, never a
  reverse-engineered CITATION.
- **Never proceeds to `AUDITED` when the corpus tier is active but
  `<thread>.{N}.corpus-audit/` has not yet been written** — treated
  identically to `AUDITED-PARTIAL`.

## Git sync (opt-in, off by default)

Per `anvil/lib/snippets/git_sync.md`: if `.anvil/config.json` exists and
`git.commit_per_phase` is `true`, end this phase: stage only the dirs
this phase wrote, commit as `anvil(<skill>/<phase>): <thread>.{N}
[<state>]`, push if `git.push` is `true`. Git failures warn and
continue. Default off.

This phase's specifics:

- **Ordering**: after the `_progress.json` `done` write lands. On the
  no-write paths (AUDITED / BLOCKED at step 2-3) there is nothing to
  commit and the hook is a silent no-op.
- **Staging target**: ONLY this command's own `<thread>.{N+1}/` version
  dir.
- **Commit**: `anvil(memoir/revise): <thread>.{N+1} [REVISED]`.
