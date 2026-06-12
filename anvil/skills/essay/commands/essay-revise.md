---
name: essay-revise
description: Reviser for the essay skill. Consumes the review sibling + gate sidecars for the latest version and produces a single revised version, preserving flagged-as-working voice signatures. REVIEWED → REVISED transition (loops to review until ≥35/44 with zero critical flags, or the iteration cap).
---

# essay-revise — Reviser

**Role**: reviser (one reviser consumes N critic siblings).
**Reads**: latest `<thread>.{N}/<thread>.md` + `_progress.json`, `<thread>.{N}.review/` (all files incl. `_gate.json`), the `<thread>.{N}.numeric/` and `<thread>.{N}.hyperlinks/` gate sidecars, resolved `voice:` docs (when the tier is active), `<thread>/refs/` + shared `research/`, project `BRIEF.md`.
**Writes**: `<thread>.{N+1}/` with `<thread>.md`, `changelog.md`, `_progress.json` — or reports `READY` without writing when the verdict pre-check passes.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/<thread>.md`. Require a completed `<thread>.{N}.review/` (else exit pointing at `essay-review`). Require `<thread>.{N+1}/` to not exist (immutability — never revise in place).
2. **Verdict pre-check**: read `<thread>.{N}.review/verdict.md`. When it records `advance: true` AND zero unresolved critical flags, the thread is **`READY` — terminal**: report the publish-handoff summary (resolved body path, total /44, the three handoff guarantees per SKILL.md §Publish handoff contract) and exit WITHOUT writing a new version.
3. **Iteration-cap check**: default `max_iterations: 4` (worst-case terminal version `<thread>.5/`); project-BRIEF paired override (`max_iterations` + `iteration_cap_rationale`) per the #349 memo contract — the BLOCKED notice surfaces the rationale verbatim when an elevated cap is hit. At cap → report `BLOCKED — human review required` and exit.
4. **Read all critic input**: `verdict.md` (top revision priorities first), `scoring.md` (per-dim deductions), `comments.md` (severity + `scope` tags), `_gate.json` + the `.numeric/` and `.hyperlinks/` `_review.json` payloads (the mechanical findings carry exact lines and suggested fixes), and the "What's working" list.
5. **Load voice grounding (conditional)**: when the project BRIEF declares a `voice:` block, resolve the docs and read them alongside the critic feedback. **Preserve the voice signatures the reviewer flagged as working** — voice-grounded revision must not sand off the persona while chasing rubric points (`anvil/lib/snippets/voice_grounding.md` §Reviser contract). When the review carried the missing-voice-contract `major` finding, surface it in the report (the fix is operator-side BRIEF authoring, not body editing).
6. **Build the revision plan**, ordered: (1) critical flags — every flag MUST be addressed (an example-coherence flag usually means reframing or replacing the example, not polishing the prose around it; a numeric flag means fixing the arithmetic or naming the bridging number, not deleting all numbers); (2) blocking gate findings (broken links: fix the target or remove the dependent claim); (3) `blocker`/`major` comments; (4) the lowest-scoring dims' deductions, honoring `scope: reduce` items — at this length, cutting is usually the highest-leverage edit; (5) `minor`/`nit` only when they don't conflict with (1)–(4). Never touch the "What's working" list.
7. **Write `<thread>.{N+1}/<thread>.md`** (slug-echo per #295) applying the plan. Re-run the drafter's step-5 self-disciplines on the result (numeric re-derivation, example-needs-the-gate check, register, close) — the revision must not introduce a fresh instance of the failure mode it just fixed.
8. **Write `changelog.md`** mapping each consumed critic note to the change made (or to an explicit `declined — <reason>` entry; deductions may be argued against, critical flags may not).
9. **Initialize `_progress.json`** for the new version: `phases.revise.state = done` (LAST write), carry forward `metadata.voice_exemplars` (updated if different exemplars were consulted), and **append the `score_history` row** for the completed review iteration per `anvil/lib/snippets/progress.md` §Convergence fields: `{ "iteration": <N>, "total": <reviewed-total>, "threshold": 35, "rubric_id": "anvil-essay-v1" }`. Stable-score termination (`STALLED`) follows `anvil/lib/snippets/rubric.md` §"Termination resolution order" over this history.
10. **Report**: e.g., `Revised the-loop-is-the-unit.1 → the-loop-is-the-unit.2 (addressed 1 critical flag, 4 major comments; 2 declined with reasons). Next: essay-review the-loop-is-the-unit`.

## What essay-revise does NOT do

- **Never edits `<thread>.{N}/` or any critic sibling in place** — immutability is the audit trail.
- **Never advances state itself** — the next `essay-review` pass scores `<thread>.{N+1}/` on its own merits; there is no "the reviser fixed it" credit.
- **Never bypasses critical flags** — a changelog `declined` entry is legitimate for scoring deductions, never for flags or broken links.
- **Never sands off the persona** — rubric-point chasing that flattens flagged-as-working voice signatures is the named meta-failure mode.

## Git sync (opt-in, off by default)

If the consumer repo carries `.anvil/config.json` with `git.commit_per_phase: true`, end this phase per the per-phase git commit/sync hook documented in `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo): after the `_progress.json` `done` write lands, stage ONLY this command's own `<thread>.{N+1}/` version dir, commit as `anvil(essay/revise): <thread>.{N+1} [REVISED]`, and push when `git.push` is also `true`. On the no-write paths (READY / BLOCKED at step 2–3) there is nothing to commit and the hook is a silent no-op. Git failures (not a git repo, commit failure, offline push) emit a one-line warning and continue — the revision still reports success; artifact-on-disk is the source of truth. When `.anvil/config.json` is absent or `git.commit_per_phase` is false/absent, skip this step entirely — behavior is byte-identical (default off).
