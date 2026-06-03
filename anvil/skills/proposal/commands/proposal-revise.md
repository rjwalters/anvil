---
name: proposal-revise
description: Reviser command for the proposal skill. Reads the latest version + ALL critic siblings (both .review/ and .audit/ required) and produces the next version with a changelog mapping critic notes to changes.
---

# proposal-revise — Reviser

**Role**: reviser.
**Reads**: latest `<thread>.{N}/` and ALL `<thread>.{N}.*/` critic siblings (`.review/`, `.audit/`, and any optional `.critic/`).
**Writes**: `<thread>.{N+1}/` containing the revised proposal, the class file, figures, `_progress.json`, and a `changelog.md` mapping critic notes to the changes made.

This command is the canonical "N parallel critics, one reviser" pattern from anvil's design principles. It consumes any number of critic siblings at the current version and produces a single revised version that addresses them. For the proposal skill, **both `.review/` and `.audit/` are required** — the reviser refuses to run if either is missing.

## Inputs

- **Thread slug** (positional argument).
- **Latest version**: highest `N` with `<thread>.{N}/proposal.tex`.
- **Critic siblings**: ALL `<thread>.{N}.<critic>/` directories at that `N`. BOTH `<thread>.{N}.review/verdict.md` AND `<thread>.{N}.audit/verdict.md` are REQUIRED (the proposal skill runs both critics by default). Optional siblings (a domain specialist `.critic/`) contribute additional findings.

## Outputs

```
<thread>.{N+1}/
  proposal.tex          Revised proposal body
  anvil-proposal.cls    Carried over so the version dir compiles standalone
  figures/              Carried over and/or updated figures
  changelog.md          Maps each critic note (by sibling + section) to the change made in this revision
  _progress.json        Phase state with revise: done
```

## CLI flags

### `--scope <level>` (optional, default `important`)

Operator-controlled severity filter for which `comments.md` findings the reviser addresses. Valid levels are `critical-only`, `important`, and `all`. **Default is `important`** — this is a behavioral migration from the previous "address every finding regardless of severity" path (which is now opt-in via `--scope all`).

The flag honors the existing `comments.md` severity groupings already emitted by `proposal-review` step 8 (`blocker` / `major` / `minor` / `nit`) — no schema change. Critics continue to emit the four-bucket grouping; the reviser teaches the grouping as a filter, not just as presentation.

**Level semantics**:

- **`--scope critical-only`** — addresses ONLY audit-critical-flag and review-critical-flag findings. All `blocker`, `major`, `minor`, and `nit` `comments.md` entries are deferred. Use case: a hot-fix iteration that lands the must-fix arithmetic / hard-constraint failures while explicitly punting the rest to the next pass.
- **`--scope important`** (default) — addresses critical flags + `blocker` + `major`. `minor` and `nit` are deferred. This is the default because it is the canary-surfaced structural fix for the "additivity produces document bloat" pattern documented in anvil#241 — the reviser is not "skipping work," it is letting the next critic pass re-flag findings that survived a tier filter, and the rhetorical-economy dim (rubric.md dim 9, shipped via PR #254) penalizes denser-but-not-stronger v{N+1}'s.
- **`--scope all`** — addresses every finding regardless of severity. This is the pre-issue-#241 behavior; opt-in only.

**Critical invariants (apply at every `--scope` level)**:

- **Audit-critical-flag and review-critical-flag findings MUST always be addressed.** `--scope critical-only` does NOT skip critical-flag handling — it skips `blocker` / `major` / `minor` / `nit` while preserving the existing critical-flag-must-address rule (see step 8 sub-bullet under "Critical flags MUST be addressed").
- **Sub-threshold dimension lifts are independent of comment severity.** A rubric dimension scored below threshold (or carrying a critical flag) is always in the revision plan regardless of `--scope` — the rubric ≥35 threshold is a separate gate from the comment-severity filter.

**Reason argument**: a CLI-supplied reason is NOT required (this differs from the `--polish` precedent in `memo-revise.md`'s CLI flags). The default-changing-from-`all`-to-`important` is a behavioral migration, not an operator-bypass affordance; an audit-trail field in `_progress.json.metadata.scope` is sufficient. Operators who want the deferred-tier behavior get it by default; operators who want every-finding behavior must opt in.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/proposal.tex` AND BOTH `<thread>.{N}.review/verdict.md` and `<thread>.{N}.audit/verdict.md`. If either critic sibling is missing, exit with an error ("both review and audit are required before revising; run the missing critic first").
2. **Resume check**: if `<thread>.{N+1}/_progress.json.revise.state == done` and `proposal.tex` + `changelog.md` exist, the revision is complete — exit early with a notice.
3. **Iteration cap check**: read `metadata.max_iterations` from `<thread>.{N}/_progress.json` (or `<thread>/.anvil.json` override; default 4). If `N + 1 > max_iterations`, exit with a `BLOCKED` notice — human review required.
4. **Combined-advance pre-check**: parse both verdicts. If `review.advance == true` (≥35) AND `audit.pass == true` AND there are no critical flags in either sibling, exit with a notice: the thread is `READY`/`AUDITED`, no revision needed. (Operator can force-run by deleting a verdict or bumping the iteration manually, but the default is to refuse to revise an already-passing version.)
5. **Initialize `_progress.json`**: write `phases.revise.state = in_progress`, `phases.revise.started = <ISO>`, `metadata.iteration = N+1`, `metadata.max_iterations`. Also record the resolved `--scope` level: write `metadata.scope` as one of `"critical-only"`, `"important"`, or `"all"`. The value stored is the *resolved* value at invocation time (the default `"important"` when the flag was absent, or the explicit operator-supplied value); the field participates in the shallow-merge rule per `anvil/lib/snippets/progress.md` and is preserved on subsequent writes by other commands. Absence of the field is tolerated by readers and treated as `"all"` for backwards-compat with pre-this-change version dirs.
6. **Read inputs**:
   - Prior version's `proposal.tex` and `figures/`.
   - `<thread>.{N}.review/verdict.md` + `scoring.md` + `comments.md`.
   - `<thread>.{N}.audit/verdict.md` + evidence file + **per-claim findings file (tolerant-read)**: the auditor's per-claim findings table normally lives at `<thread>.{N}.audit/findings.md`, but some execution contexts (notably subagent harnesses — see #135 for anvil's documented subagent-delegation workaround) block files literally named `findings.md`. To make this reviser robust against that block, try the three documented filenames in priority order and use the first one that exists:
     1. `<thread>.{N}.audit/findings.md` (canonical)
     2. `<thread>.{N}.audit/claim-log.md` (documented alias)
     3. `<thread>.{N}.audit/audit-findings.md` (documented alias)

     If none of the three exist, exit with an error naming all three candidates checked (e.g. `proposal-revise: no per-claim audit findings file found in <thread>.{N}.audit/ — checked findings.md, claim-log.md, audit-findings.md`). Do not introduce glob/regex matching — these three named candidates only. The canonical `findings.md` always wins when multiple files coincidentally exist (defensive-against-confusion property).
   - Every other `<thread>.{N}.<critic>/` sibling discovered on disk.
7. **Build a revision plan** — apply the `--scope` filter from step 5:
   - **Always include (no filter)**: audit-critical-flag and review-critical-flag findings. These are addressed regardless of `--scope` per the §"CLI flags" critical invariants.
   - **Always include (no filter)**: sub-threshold dimension lifts. For each rubric dimension that scored below threshold (or had a critical flag), enumerate the specific changes required to lift the score. The rubric ≥35 threshold is independent of comment severity — `--scope` filters comments, not dimensions.
   - **Always include (no filter)**: audit findings with `Verified? = no` or a critical flag — plan the specific factual / arithmetic fix (correct the BOM line, fix the subtotal, reconcile the transceiver count with the topology, source the unsourced price, or close the link budget). Audit findings are not severity-tagged in the same `blocker` / `major` / `minor` / `nit` shape; they are treated as critical-equivalent for filter purposes.
   - **Filter `comments.md` entries by severity per the resolved `--scope` level**:
     - `--scope critical-only` — include no `comments.md` entries (the critical-flag pathway above is sufficient).
     - `--scope important` (default) — include `comments.md` entries tagged `blocker` and `major`. Defer `minor` and `nit`.
     - `--scope all` — include `comments.md` entries at all four severities (`blocker`, `major`, `minor`, `nit`).
   - **Record deferred entries**: every `comments.md` entry filtered out by the scope level is recorded for the `Deferred to next iteration` table in `changelog.md` (see step 9). The deferred list is the operator's TODO signal — the next `proposal-review` pass MAY re-surface the same findings (which is correct behavior; it means the deferred items have re-aged and the operator can decide whether to lift them in the next revision).
   - Resolve conflicting feedback between critic siblings explicitly (e.g., reviewer says "cut the BOM detail to tighten the pitch," auditor says "the cut line was the one with the sourceable basis" — pick a synthesis and note it in the changelog). Conflict resolution applies to findings that survived the severity filter; conflicts among deferred findings are themselves deferred.
8. **Produce `proposal.tex`** at `<thread>.{N+1}/proposal.tex`:
   - Address each planned change.
   - Preserve sections that scored well — do not regress on dimensions that already met the standard.
   - Carry over `figures/` and the `anvil-proposal.cls` from the prior version; update or add figures as the revision plan requires.
   - **Critical flags MUST be addressed**: a *missed hard constraint* flag (1) requires the design to actually satisfy the constraint (no surface raceway if invisibility was required); a *cost not sourceable* flag (2) requires a basis for every price; a *not deliverable* flag (3) requires a concrete delivery-capability story the BOM/labor actually fund; an *internal inconsistency* flag (4) requires the arithmetic, counts, and link budgets to be made to agree.
9. **Write `changelog.md`**: a markdown table mapping each critic note to the change made.

   ```
   | Source                          | Note                                          | Resolution                                  |
   |---------------------------------|-----------------------------------------------|---------------------------------------------|
   | gossamer-lan.1.audit (critical) | Materials subtotal off by $200 (sum mismatch) | Recomputed the subtotal; was a missing line |
   | gossamer-lan.1.audit (major)    | Transceiver qty 14 but topology has 7 spokes  | Corrected to 16 (14 spoke + 2 uplink); added the derivation inline |
   | gossamer-lan.1.review (blocker) | Design proposes surface raceway — violates "no conduit" | Reworked routing to ceiling adhesion; restored constraint satisfaction |
   | gossamer-lan.1.review (major)   | Deliverability story is a contractor phone number | Added the fiber-workshop subsection (tools + practice spool) |
   ```

   For deliberate non-resolutions (e.g., a critic suggested a change the reviser disagrees with), include them with `Resolution: declined — <one-line reason>`. The next critic pass can override or accept the reviser's judgment.

   **Deferred section (any non-`all` scope).** Under `--scope critical-only` or `--scope important`, append a second table to `changelog.md` after the resolutions table, listing every `comments.md` entry filtered out by the scope level. Shape:

   ```
   ## Deferred to next iteration (scope: important)

   | Source                          | Severity | Note                                       |
   |---------------------------------|----------|--------------------------------------------|
   | gossamer-lan.1.review (minor)   | minor    | §5 channel-mix could add a worked example  |
   | gossamer-lan.1.review (nit)     | nit      | §2 footnote citation style inconsistency   |
   ```

   The scope level is named in the section header so downstream readers (next critic pass, human reviewer of the changelog) can see at a glance which tier filter was applied. Under `--scope all` the section is omitted entirely (every finding is addressed). Under `--scope critical-only` or `--scope important` the section is written even if zero entries were deferred — an empty `Deferred to next iteration (scope: ...)` table with a header row is the in-band signal that the filter was applied and nothing was caught by it.

   Deferred entries are NOT a `Resolution: declined — <reason>` — they are findings the reviser explicitly did not address this iteration because the scope filter punted them, not findings the reviser disagrees with. The next `proposal-review` pass MAY re-surface the same findings (which is correct behavior; deferred items have re-aged and the operator can lift them in the next revision).
10. **Update `_progress.json`**: `phases.revise.state = done`, `phases.revise.completed = <ISO>`.
11. **Report**: print the path to the new version dir and a one-line status. The status line MUST include the scope level and the deferred count alongside the existing addressed / declined counts — e.g., `Revised gossamer-lan.1 → gossamer-lan.2/ (scope: important; addressed 4 notes incl. 1 audit-critical, deferred 6 to next iteration, declined 1)`. The scope tag is the cheap operator signal that the run took a tiered filter; the deferred count is the cheap signal of how many findings were punted. Under `--scope all` the deferred count is zero and the line MAY omit the `deferred N to next iteration` clause (or print `deferred 0 to next iteration` — readers tolerate both shapes).

## Idempotence and resumability

- A completed revision (`revise.state == done` AND `proposal.tex` + `changelog.md` exist) is never re-run.
- A crashed revision is re-runnable after deleting partial output.

## Convergence

After this command produces `<thread>.{N+1}/`, the orchestrator should run BOTH `proposal-review <thread>` AND `proposal-audit <thread>` on the new version (in parallel). The cycle continues until:
- BOTH `verdict.md`s clear (`review.advance: true` ≥35 AND `audit.pass: true`, no critical flags) — thread reaches `READY`/`AUDITED`, OR
- `N+1 > max_iterations` (thread is `BLOCKED` for human review).

## Notes for the reviser agent

- **Do not regress.** If a section scored 5/6 in the prior review, the next version should keep it at ≥5/6. The `changelog.md` is the audit trail proving you did not lose ground while addressing other dimensions.
- **Audit-critical flags trump everything.** A failed BOM subtotal or a link budget that does not close is a worse outcome than declining a stylistic suggestion. Fix the math first.
- **Reconcile the two critics, don't average them.** The reviewer and auditor own different defect classes; a note from one is not softened by a good score from the other. Address both.
- **Declined notes are a feature, not a bug.** Sometimes a critic is wrong. Document the disagreement in `changelog.md` so the next pass can re-evaluate with full context.
- **Audit findings filename is tolerant by design.** The per-claim findings file from `proposal-audit` ships canonically as `findings.md`, but step 6 above accepts `claim-log.md` and `audit-findings.md` as documented aliases for subagent-harness-blocked execution contexts (see `proposal-audit.md` §"Alias contract" for the writer-side convention). If you find the audit sibling used an alias, treat it as the canonical findings file — no other handling is required.
- **Tier findings by severity.** The default `--scope important` addresses `blocker` + `major` + critical flags; `minor` and `nit` findings are deferred and recorded in `changelog.md`'s `Deferred to next iteration` section. This is the structural fix for the additivity-produces-bloat pattern documented in anvil#241 — the reviser is not "skipping work," it is letting the next critic pass re-flag findings that survived the tier filter, and the rhetorical-economy dim (rubric.md dim 9) penalizes denser-but-not-stronger v{N+1}'s. Critical flags MUST be addressed regardless of scope; deferred findings are NOT `Resolution: declined` (which means "the reviser disagrees with this finding") but a separate "punted by scope filter" category. Operators who want the pre-#241 every-finding behavior opt in via `--scope all`.

## `_progress.json` snippet (revised version dir)

This command writes the version-dir shape documented in `anvil/lib/snippets/progress.md`. The reviser adds a `metadata.revised_from` field naming the parent version (preserved by the shallow-merge rule on subsequent writes):

```json
{
  "version": 1,
  "thread": "<slug>",
  "phases": {
    "revise": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  },
  "metadata": {
    "iteration": <N+1>,
    "max_iterations": 4,
    "revised_from": <N>,
    "scope": "important"
  }
}
```

`metadata.revised_from` helps the orchestrator's anomaly detection catch gaps in the version chain. `metadata.scope` is the resolved `--scope` level for this revision (`"critical-only"`, `"important"` (default), or `"all"`) — see §"CLI flags" for the level semantics and step 7 for the filter logic. The field is a skill-specific extension to the `_progress.json` schema and is preserved by the shallow-merge rule per `anvil/lib/snippets/progress.md`. Absence of the field is tolerated by readers and treated as `"all"` for backwards-compat with pre-this-change version dirs. **This field is audit-trail only — not scored, not gating, not state-machine input.** Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
