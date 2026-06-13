---
name: slides-audit
description: Auditor command for the slides skill. MANDATORY technical fact-check. Enumerates every technical claim in deck.md and notes/, assigns a verdict (supported / unsupported / wrong / ambiguous), and sets the audit critical flag on any wrong claim.
---

# slides-audit — Auditor (MANDATORY)

**Role**: auditor (technical fact-check).
**Reads**: latest `<thread>/<thread>.{N}/deck.md` AND `<thread>/<thread>.{N}/notes/*.md` (the version dir is nested under the thread root per the artifact contract). Also reads `<thread>/refs/**` and any cited external sources where retrievable.
**Writes**: `<thread>/<thread>.{N}.audit/` with `verdict.md`, `claims.md`, and `_progress.json`. Bare `<thread>.{N}/` / `<thread>.{N}.audit/` references below are shorthand for these nested paths.

The audit sibling directory is **read-only once written**. The reviewer consumes its verdict to propagate the audit flag; revisions consume it to address `wrong` and `unsupported` claims.

## Why this command is mandatory

The audit phase is the load-bearing distinction between `anvil:slides` (talks) and `anvil:deck` (pitches). Talks live or die on technical accuracy — listeners cannot pause-and-verify, and a single wrong equation in a recorded talk is a reputational tax that compounds. The mandatory audit phase exists to make accuracy a first-class verdict, not a sub-score buried inside the general reviewer's rubric.

A thread cannot reach `READY` (the terminal-for-rubric state) without an `AUDITED` sibling. The portfolio orchestrator (`slides`) enforces this by recommending `slides-audit` immediately after any `REVIEWED` state where the audit sibling is missing.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md` existing under the thread root `<thread>/`.
- **Brief and refs**: `<thread>/BRIEF.md` and `<thread>/refs/**` provide the canonical sources for what the talk should be saying. Citations on slides should resolve to refs where possible.
- **External sources**: where a claim cites an external paper, statistic, or attribution, the auditor SHOULD attempt to verify it. Where verification is not possible (offline, paywalled, citation absent), the verdict is `ambiguous` rather than `wrong` or `supported`.

## Outputs

Nested under the thread root `<thread>/`, as a sibling of the `<thread>.{N}/` version dir under audit:

```
<thread>.{N}.audit/
  verdict.md       Top-level audit verdict + flag status + summary table
  claims.md        Every technical claim enumerated with verdict and citation
  _meta.json       { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state with audit: done, for_version: <N>
```

**Atomicity** (issue #350, #376): the audit sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The four files (`verdict.md`, `claims.md`, `_meta.json`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.audit.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.audit/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.audit.tmp/` dir on disk that the next invocation's `cleanup_one_staging(<thread>.{N}.audit)` per-critic sweep removes; the final-named dir never exists in partial form. Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md` under the thread root `<thread>/`. Then **sweep a stale staging dir from a prior interrupt of THIS critic on THIS version** by invoking `anvil/lib/sidecar.py::cleanup_one_staging(<thread>.{N}.audit)` (the per-critic, parallel-safe sweep — issue #376). This removes ONLY a leftover `.<thread>.{N}.audit.tmp/` from a previously-killed run of this same critic on THIS version. Sibling critics' in-flight staging dirs under the same thread root are NOT touched (issue #350, #376). If `<thread>.{N}.audit/` exists (the atomic-rename contract guarantees the dir only exists when complete), the audit is complete — exit early with a notice (idempotent).
2. **Resume check**: per the staged-sidecar shape introduced in issue #350, a partial audit left behind by a mid-cycle interrupt manifests as a leading-dot `.<thread>.{N}.audit.tmp/` directory; the step 1 sweep has already removed it. Backwards-compat: if a legacy pre-#350 `<thread>.{N}.audit/` exists WITHOUT `verdict.md`, delete the dir and re-audit.
3. **Open the staged sidecar** for the audit dir by invoking the context manager `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.audit, required_files=["verdict.md", "claims.md", "_meta.json", "_progress.json"])`. Every file write below MUST land **inside the yielded staging directory** (the path of the shape `.<thread>.{N}.audit.tmp/`), NOT inside the final `<thread>.{N}.audit/` path. On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name (issue #350). Then, **inside the staging dir**, initialize `_progress.json`: `phases.audit.state = in_progress`, `phases.audit.started = <ISO>`, `for_version: <N>` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`); slides-audit ships task-specific `claims.md` alongside the scorecard-kind declaration.
4. **Enumerate claims**: scan `deck.md` AND every `notes/*.md` file. A *technical claim* is any statement that:
   - asserts a numerical value, ratio, or statistic;
   - asserts an attribution (author, paper, year, institution);
   - states an equation or formula;
   - describes a mechanism, algorithm, or causal relationship;
   - asserts the state of established consensus in a field.

   Non-claims (do not enumerate): rhetorical questions, hypotheticals, opinions, slide titles, transition phrases, audience-engagement prompts.

5. **For each claim**, assign one of four verdicts:
   - **`supported`** — the claim is backed by a primary source (in refs/ or a verifiable external citation) AND the cited source matches the claim.
   - **`unsupported`** — the claim is plausible but no citation is provided AND no ref-folder source covers it. Does NOT set the audit flag (contributes to Dimension 1 score reduction by the reviewer).
   - **`wrong`** — the claim contradicts a primary source, contains a verifiable error (wrong constant in an equation, wrong year for an attribution, statistic that doesn't match the cited source), or asserts something contradicting established consensus where consensus exists. **Sets the audit critical flag.**
   - **`ambiguous`** — the claim cannot be verified or refuted from available material (paywalled source, missing citation, claim too vague to evaluate). Does NOT set the audit flag, but the reviewer should be aware that an ambiguous claim is one a hostile questioner could exploit.

6. **Write `claims.md`** — a markdown table:

   ```
   | # | Location               | Claim (excerpt)                                  | Verdict     | Citation / Note |
   |---|------------------------|--------------------------------------------------|-------------|-----------------|
   | 1 | slide 5                | "Transformers were introduced in 2017"           | supported   | Vaswani et al., NeurIPS 2017 (refs/vaswani-2017.pdf) |
   | 2 | slide 7, notes/07-*.md | "Self-attention is O(n^2) in sequence length"    | supported   | standard result; refs/vaswani-2017.pdf §3.2 |
   | 3 | slide 12               | "FlashAttention reduces this to O(n)"            | wrong       | FlashAttention is O(n^2) in FLOPs but O(n) in memory (Dao 2022); slide conflates the two |
   | 4 | slide 14               | "Most production LLMs use this technique"        | ambiguous   | "Most" is unquantified; no citation; could be defensible if narrowed |
   | 5 | notes/16-*.md          | "GPT-4 has 1.7T parameters"                      | unsupported | widely speculated, never confirmed by OpenAI |
   ```

   Group rows by slide number for navigability. Use the same numbering and slide-location convention as `slides-review`'s `comments.md` so the reviser can cross-reference.

7. **Write `verdict.md`**:

   ```markdown
   # Audit verdict for <thread>.<N>

   ## Summary
   - Total claims enumerated: <N>
   - Supported: <N>
   - Unsupported: <N> (NOT flagged; reviewer reduces Dimension 1 score)
   - Wrong: <N> (CRITICAL FLAG if N >= 1)
   - Ambiguous: <N>

   ## Audit flag: <SET / NOT SET>
   <If set: bulleted list of every `wrong` claim with one-paragraph justification per claim, naming the primary source the claim contradicts.>

   ## Notes
   <Any meta-observations: patterns of unsourced claims, citations that don't match the bibliography, etc.>
   ```

8. **Update `_progress.json`** inside the staging dir: `phases.audit.state = done`, `phases.audit.completed = <ISO>`. This is the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires `_progress.json` to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies every name in the required-files manifest exists in the staging dir, then atomically renames `.<thread>.{N}.audit.tmp/` → `<thread>.{N}.audit/`. The final-named dir only ever exists in **complete** form.
9. **Report**: print the path to the (now-renamed) audit dir and a one-line status (e.g., `Audited kdd-2026-keynote.1 → kdd-2026-keynote.1.audit/ (37 claims: 28 supported, 4 unsupported, 2 wrong, 3 ambiguous; AUDIT FLAG SET)`).

## Notes for the auditor agent

- **Sharper posture than the general reviewer.** The auditor's job is citation-correspondence. Where the reviewer asks "is this claim well-argued?", the auditor asks "is this claim *true* and *attributable*?". Be precise.
- **The notes/ matter.** Speakers often make claims in spoken commentary that don't appear on the slide. The auditor reads notes/*.md exhaustively because that's where the highest-density-of-spoken-claims lives.
- **`wrong` is a high bar.** It requires either (a) a primary source that contradicts the claim, or (b) consensus in the field that contradicts it. A claim being controversial is not `wrong`; a claim being unsupported is not `wrong`; only verifiable error or contradiction-of-consensus is `wrong`.
- **`unsupported` is a real signal.** A plausible claim without a source is a hostile-question vector. Flag generously here (it doesn't block the deck; it reduces Dimension 1 score in the reviewer's pass).
- **`ambiguous` is the auditor's hedge.** Use it when you genuinely can't tell. Paywalled papers, unverifiable industry statistics, vague quantifiers ("most", "many", "often") without bounds — all reasons to verdict `ambiguous` rather than guessing.
- **Figures are claims too.** A chart that purports to show data from a source must be verified the same way as a textual statistic. The figurer's job is to produce charts from sourced data; the auditor verifies that the produced chart matches the source.

## Idempotence and resumability

- A completed audit (`audit.state == done` AND `verdict.md` + `claims.md` exist) is never re-run. Re-invoking is a no-op with a notice.
- A crashed audit is re-runnable after deleting partial output.
- Validation is by file existence.

## Re-running on revision

When a new `<thread>.{N+1}/` is produced, the orchestrator runs `slides-audit` against it as a fresh invocation, writing to `<thread>.{N+1}.audit/`. The auditor does NOT carry forward verdicts from the prior version — every claim is re-evaluated against the current `deck.md` and `notes/*.md`.

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

## Git sync (opt-in, off by default)

Per `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo): if `.anvil/config.json` exists and `git.commit_per_phase` is `true`, end this phase: stage only the dirs this phase wrote, commit as `anvil(<skill>/<phase>): <thread>.{N} [<state>]`, push if `git.push` is `true`. Git failures warn and continue — never fail the phase. When the config or knob is absent, skip this step entirely (default off).

This phase's specifics:

- **Ordering**: after the staged-sidecar atomic rename (issue #350) lands the final-named `<thread>.{N}.audit/` — so only complete sidecars are ever committed.
- **Staging target**: ONLY this command's own `<thread>.{N}.audit/` sidecar (never sibling critics' dirs — the narrow scope keeps the hook safe under parallel critic fan-out).
- **Commit**: `anvil(slides/audit): <thread>.{N} [<state>]` — the bracket carries the thread's derived state per SKILL.md §State machine after the audit lands (`AUDITED` when the audit sits alongside a `READY` version with no unresolved `wrong` claims).
