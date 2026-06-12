---
name: essay-draft
description: Drafter for the essay skill. Produces the first version of a short-form voice-grounded essay (markdown body, 500–1500 words typical) from the project BRIEF, the voice docs, and any thread refs. EMPTY → DRAFTED transition.
---

# essay-draft — Drafter

**Role**: drafter.
**Reads**: project `BRIEF.md` (matching `documents:` entry + optional top-level `voice:` block), the resolved voice docs, `<thread>/refs/`, shared `research/` (when present); for re-drafts after a crashed pass, the partial `_progress.json`.
**Writes**: `<thread>.{N}/<thread>.md` + `_progress.json` (new version dir; immutable once `done`).

This is the `EMPTY → DRAFTED` transition. (Revisions go through `essay-revise`, which produces `<thread>.{N+1}/` from critic feedback — this command drafts v1, or a fresh v1 after an abandoned thread.)

## Procedure

1. **Discover state**: confirm no `<thread>.{N}/` exists yet (else exit with a pointer to `essay-review` / `essay-revise` per the state table in SKILL.md). Create `<thread>.1/` and initialize `_progress.json` (`phases.draft.state = in_progress`, per `anvil/lib/snippets/progress.md`).
2. **Read the project BRIEF**: locate the matching `documents:` entry (slug = thread dir name; `artifact_type: essay`). Read `target_length` when declared; default guidance is **500–1500 words** (the artifact-class envelope per SKILL.md), with 500–1000 as the sweet spot dim 9 scores against. Record the resolved target in `_progress.json.metadata.target_length_resolved` when declared.
3. **Load voice grounding (conditional — issue #461)**: invoke `anvil/lib/project_brief.py::resolve_voice_docs(<project_dir>)`.
   - **When active**: load the resolved docs in order — **values → style_guide → vocabulary → corpus exemplars** (values first: stances and standing constrain what may be said before register shapes how it is said). Choose **3–5 corpus exemplars** that are voice-matched AND topically adjacent to the piece being drafted — a handful read closely beats fifty skimmed. **Record the consulted exemplar paths in `_progress.json.metadata.voice_exemplars`** (a list of path strings) so the reviewer can verify grounding happened. Quote a corpus passage when justifying a register or mode choice in the self-check (step 6).
   - **When inactive** (no `voice:` block, empty block, or no BRIEF): omit `metadata.voice_exemplars` entirely and draft without persona calibration. Do NOT invent a voice contract. The reviewer will surface the missing contract as a `major` finding (SKILL.md §Voice grounding) — that is the correct surface, not a drafting blocker.
   - **Declared-but-missing files**: proceed with whatever resolved (`resolve_voice_docs` returns `missing: true` entries, never raises); the reviewer surfaces the broken declaration.
4. **Ingest evidence**: read `<thread>/refs/` text-readable materials and the shared `research/` pool (when present) as authoritative substrate. Claims whose evidentiary basis lives in a file should trace to that file; specific named external entities (papers, benchmarks, projects, organizations) the dinner-party reader would ask "where do I find that?" about get a markdown link at draft time — the review's link audit checks both halves (deterministic resolution + coverage judgment).
5. **Draft the body** to `<thread>.1/<thread>.md` (the filename **echoes the slug** per #295 — never `post.md`, never `essay.md`):
   - **Hook first**: open with a concrete moment, question, observation, or specific scene (rubric dim 1).
   - **Dinner-party register throughout**: sharing, not winning an argument — no hedges-to-forestall-pushback, no trailing summaries, no balanced point-counterpoint scaffolding, no moralizing (dim 6).
   - **Numbers are load-bearing or absent**: every number supports a specific claim, and the arithmetic among named numbers must survive a reader doing it in their head (the spread failure — SKILL.md §Failure-mode catalog). Before finishing, re-derive every spread/gap/percentage claim from the values the draft names.
   - **The central example must need the claim**: if the piece frames an abstract gate and illustrates it with a worked example, verify the example physically depends on that gate (the toaster failure).
   - **Land the close** — short declarative landing or honest reversal, not a recap.
6. **Self-check** into `_progress.json.metadata.self_check`: word count vs target, voice exemplars consulted (with one quoted register justification when the tier is active), the example-coherence one-liner (central claim restated + central example restated + "the example needs the gate because …"), and the numeric re-derivation note.
7. **Finalize**: set `phases.draft.state = done` (the `_progress.json` write is LAST so crash recovery per `anvil/lib/snippets/progress.md` sees an incomplete phase, not a half-blessed one).
8. **Report**: e.g., `Drafted the-loop-is-the-unit.1 (812 words; voice tier active, 4 exemplars consulted). Next: essay-review the-loop-is-the-unit`.

## What essay-draft does NOT do

- **No PDF render, no figures.** The artifact is markdown prose (SKILL.md §Artifact contract).
- **No review-side gates.** The numeric / hyperlink / rhetoric gates run in `essay-review`; the drafter's step-5 disciplines exist to pass them, not to replace them.
- **Never writes voice docs.** The `voice:` contract is operator-declared; an absent contract is surfaced by the reviewer, not silently filled in by the drafter.

## Git sync (opt-in, off by default)

If the consumer repo carries `.anvil/config.json` with `git.commit_per_phase: true`, end this phase per the per-phase git commit/sync hook documented in `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo): after the `_progress.json` `done` write lands, stage ONLY this command's own `<thread>.{N}/` version dir, commit as `anvil(essay/draft): <thread>.{N} [DRAFTED]`, and push when `git.push` is also `true`. Git failures (not a git repo, commit failure, offline push) emit a one-line warning and continue — the draft still reports success; artifact-on-disk is the source of truth. When `.anvil/config.json` is absent or `git.commit_per_phase` is false/absent, skip this step entirely — behavior is byte-identical (default off).
