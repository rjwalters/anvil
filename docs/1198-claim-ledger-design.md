# Cross-version claim ledger — design decision record (#1198)

Design-decision record (docs only, no code) for issue #1198, per the
issue's "Revision 2026-09-14 (operator lane)" section. Champion approved
this issue for `loom:issue` **scoped to this record alone** (2026-09-15,
"APPROVED (scoped to PR 1)"): the two open design questions below now
have stated recommended defaults, and this PR's job is to make the call
explicit and durable, not to implement the ledger. The implementation
(the issue's "PR 2") is separate follow-on work, re-evaluated once this
record lands — see "Status of the implementation" at the bottom.

## Problem recap

Issue #888's **Failure 3**: a review pass had no record of what it (or a
prior pass) had already verified, so effort went to *re-deriving*
unchanged claims (a record count, a campaign count, a set of issue
states — all independently re-derived across five review rounds) while
*never-checked* claims sat untouched. #888's two original critical flags
both landed on clauses "carried untouched since `.1` that no pass had
ever verified," surfaced only at iterations 4 and 5 — findings that
could have been caught in one batched pass instead trickled across
several small revisions (`.5` was a restructure plus four corrections;
`.6` was three more hunks). Field evidence from a live canary
(`rjwalters/walters-family-tree`, 2026-08-10/13) showed naming the
failure mode in briefs suppresses it for a couple of revisions and then
it recurs in the same shape — "the prompt fixes it does not generalise
to the class, even when the class is named alongside the instance." The
fix has to be structural: a persisted record of what has been verified,
against what, and when.

## Decision 1 — Placement: skill-local

**The ledger primitive lands under `anvil/skills/essay/lib/`, not
`anvil/lib/`.**

Rationale:

- CLAUDE.md's "Working on this repo" convention is explicit: "New
  primitives ship under `anvil/skills/<skill>/lib/` until duplication is
  observed across skills... 'wait for the second consumer before
  generalizing.'" `anvil:essay` is the only reported consumer of this
  failure mode today (#888's field evidence, #1197's sibling split, and
  this issue are all essay-scoped).
- #888's own framing ("review loop", not "essay specifically") is real
  signal that the *problem* is framework-wide, but that is exactly what
  the skill-local-first rule is designed to defer, not skip — a second
  concrete consumer (`paper`, `report`, `memoir`, or another
  claim-heavy skill hitting the same trickling-findings shape) is the
  trigger to promote, not an abstract argument that the problem
  generalizes.
- Keeping the row shape (Decision 2) identical to what `anvil/lib/`
  would need makes a future promotion a mechanical move of one file plus
  its call sites, not a format migration — the same promotion shape
  already used for `anvil/lib/provenance_anchor.py` (#868), which
  started as a #597-adjacent essay/memoir concern and reused
  `anvil/lib/snippets/provenance.md`'s existing column contract rather
  than inventing a new one.

## Decision 2 — Relationship to the corpus-provenance ledger: extend, don't parallel

**The claim ledger is `provenance.md` itself, extended with a claim-kind
column and a verification stamp — not a second, parallel ledger file.**

The existing local-corpus claim-provenance contract
(`anvil/lib/snippets/provenance.md`, #597, anchor-drift extended by #868)
is already a persistent, cross-version claim→source map with a reviewer
back-check and a reviser copy-forward discipline. Its scope today is
narrower than #888's problem: it only covers claims attributed to a
declared `corpus:` directory. #888's broader claim (a record count
derived from a linked repo, a campaign count read off a `refs/` file, a
prose-logic conclusion a prior review already checked by argument rather
than by opening a source file) is not corpus-attributed and gets
silently re-derived or never checked under the current contract.

Extending the existing table over adding a second file:

- **One ledger, two `Kind`s.** Add a `Kind` column (`corpus` / `derived`)
  to the existing `provenance.md` table, plus two new columns —
  `Verified against` (what check last validated the row) and
  `Verified at` (the version number `N` that check ran at). `corpus`
  rows are exactly today's #597 rows, unchanged, with anchor-drift
  detection delegated to `anvil/lib/provenance_anchor.py` as it is today
  — **reused directly, not reimplemented** (the issue's own hint to
  treat #868 as "a structural model worth reusing" is read here as
  literal code reuse for the corpus tier, not merely a design analogy).
  `derived` rows are the new case: `Source file` holds a free-text
  reference (a `refs/` path, a repo + commit, or a pointer such as
  `"essay-review v2, comments.md"`) instead of a corpus-resolvable path;
  `anvil/lib/provenance_anchor.py` never runs against them, since there
  is no corpus root to resolve a free-text reference against.
- **Why not a second parallel ledger.** A second file duplicates the
  parsing, the reviewer back-check step, and the reviser copy-forward
  step that `provenance.md` already has, for no structural reason — the
  two claim kinds need the *same* lifecycle (write once, copy forward,
  get checked, get stamped), just a different verification mechanism per
  kind. A parallel file also reopens exactly the "which file does this
  claim belong in" ambiguity the corpus-tier boundary section in
  `provenance.md` already had to draw carefully once (§"Scope boundary
  vs. voice fidelity", §"Scope boundary vs. the AI-authorship byline") —
  adding a third boundary to adjudicate is worse than widening one
  existing, well-understood table.
- **Activation stays exactly as it is for the `corpus:` tier.** This
  decision does not touch `provenance.md` Section 1's activation rule
  (`corpus:` BRIEF key → tier active; absent → byte-identical inactive
  behavior). What changes is that `provenance.md` may now also exist, or
  carry additional `derived`-kind rows, when there is at least one
  checkable claim to track even though `corpus:` is inactive — the
  corpus tier's byte-identical-when-inactive guarantee is preserved
  because a thread with zero checkable claims of either kind still
  writes nothing.
- **The review pass's job changes shape, not scope.** A review pass's
  provenance/claim step becomes "check rows with no `Verified at`, or a
  `corpus` row whose anchor drifted" first, batched into the current
  pass — not "re-derive every claim from scratch every time." This is
  the direct mechanism for #888's fix: an inherited, never-verified
  `derived` row is visible by the same query a `corpus` row's
  anchor-drift check already used, so it cannot silently survive
  multiple rounds the way it did in #888's original two critical flags.

## What the killed `_convictions.md` primitive (#142/#225/#226/#227/#228) got wrong

A prior attempt at a related but distinct primitive — a
freestanding, reviser-owned "settled convictions" ledger — shipped
(#142/#147, PR #155) and was reverted two days later (#227, PR merging
the revert) after a canary observation window found two structural
defects (#225, #226). Both are read here as design constraints this
ledger must satisfy by construction, not by discipline, since "name the
failure mode in the brief" already failed once in the #888 field
evidence for a closely related problem:

- **#225 — write-only by construction.** `_convictions.md`'s named
  consumer was "the next reviser at version N+1," but the next reviser
  only runs when the current version does *not* advance
  (`verdict.advance == false` or a critical flag). A cleanly-advancing
  version — the modal, intended outcome — produced a convictions file
  with no reader, ever; the one canary instance that got written
  (`citation-clear/memo.4/_convictions.md`) hit 40/40 advance and was
  permanently dead-letter.
- **#226 — wrong trigger.** The write trigger was `Resolution: declined`
  rows in `changelog.md` (a critic-challenged-and-held position). In
  practice the load-bearing convictions in mature threads lived in
  `Resolution: addressed` rows, where the *judgment in how to address*
  was itself the held position — the trigger vocabulary selected against
  the primitive's own most valuable case.

**Why this design does not reopen either defect:**

- **No coupling to `verdict.advance` (closes #225's gap).** `Verified
  at` is stamped on a claim row *whenever a review pass actually checks
  it* — every reviewed version gets its claims checked against the
  ledger, independent of whether that version's verdict advances. The
  consumer is "the next `essay-review` pass," which the state machine
  runs on every reviewed version; whether a version advances only
  decides whether `essay-revise` produces a next version at all
  (`essay-revise.md`'s existing READY short-circuit already handles
  that branch), never whether the *current* version's claims get
  checked. There is no "only fires when revise runs" branch to reopen.
- **The trigger is claim-shaped, not changelog-shaped (closes #226's
  gap).** `Verified at` is read directly off the claim row itself
  (unset, or a stale `corpus` anchor per #868's existing drift check) —
  never inferred from a `changelog.md` resolution tag. #226's defect was
  specific to the `declined`-vs-`addressed` vocabulary; this ledger has
  no dependency on that vocabulary at all, so the same misclassification
  cannot recur by construction, not by a differently-tuned trigger that
  could still miss a case the way #226's did.
- **Extends an already-consumed primitive instead of introducing a new
  one.** `provenance.md` already has a real, exercised reviewer
  back-check step (`provenance.md` §3) and reviser copy-forward step
  (§2) wired into `essay-review.md` / `essay-revise.md` today — this is
  not a freestanding file hoping to find a reader for the first time,
  the way `_convictions.md` was. The extension inherits an existing,
  canary-exercised read/write cadence rather than inventing one.

## Framework module integration (non-changes, stated explicitly)

Per the issue's own hedge ("implementation guidance — unverified, not
traced against current code; verify before building"), the following is
this record's read of how the ledger composes with the three named
framework modules, to be confirmed (or corrected) by whoever implements
PR 2:

- **`anvil/lib/critics.py`** — expected to need **no changes**. An
  unverified or drift-detected row becomes an ordinary
  `major`/`blocker` finding in the reviewer's `comments.md`
  (`kind: judgment`, `evidence_span` pointing at the ledger row), routed
  through the existing `compute_verdict` aggregation unmodified — the
  same pattern `provenance.md`'s reviewer back-check (§3) and audit
  critic (§4) already use today. A fabrication caught via the ledger
  still raises the existing `provenance.md` §6 critical-flag vocabulary
  (`fabricated_fact`, `misattribution_of_substance`, etc.); no new
  `Finding` field or critical-flag type is needed for the ledger
  mechanism itself.
- **`anvil/lib/convergence.py`** — expected to need **no changes**. This
  primitive changes *what a review pass covers* each iteration (batch
  the never-verified and stale rows, don't trickle), not *when the
  review/revise loop terminates*. A thread that would otherwise converge
  with an unverified-claim backlog is still caught by the existing
  machinery, because an unverified/stale row surfaces as a
  `major`/`blocker` finding like any other — it depresses the rubric
  total or raises a critical flag exactly as a hand-found defect would.
  `decide_termination`'s resolution order (`THRESHOLD_MET` / `STALLED` /
  `MAX_ITERATIONS` / critical-flag short-circuit) needs no new branch.
- **`anvil/lib/sidecar.py`** — **does not apply the way the issue's
  "Affected Files" list implies.** `staged_sidecar`'s atomic
  stage-then-rename is the write discipline for **critic sibling
  directories** (`<thread>.{N}.review/`, `<thread>.{N}.corpus-audit/`,
  etc.) — a fan-in of several files into one new immutable directory.
  `provenance.md` (and this extension of it) is not a critic sibling; it
  is a single file written directly into `<thread>.{N}/` alongside the
  body, exactly like `<thread>.md` and `_progress.json` today (see
  `essay-draft.md` step 3c, `essay-revise.md` step 5). The correct
  atomic-write primitive for a single-file update is
  `anvil/lib/atomic_write.py` (`atomic_write_text`), which
  `anvil/lib/provenance_anchor.py`'s own `repoint` command already uses
  for exactly this file. PR 2 should confirm this rather than reaching
  for `staged_sidecar` on a target it was not built for.
- **`_progress.json` checkpointing** — expected to gain a summary field
  (e.g. `metadata.claim_ledger_summary`), mirroring the existing
  `metadata.provenance_summary` convention (`provenance.md` §7): a
  read-only roll-up for a human/orchestrator scanning progress state,
  never a second source of truth for verification status (the ledger
  file itself stays that). This composes with checkpointing without
  duplicating it, per the issue's own guidance.

## Row shape sketch (non-binding — PR 2's to finalize)

```
| Claim | Kind | Source file | Line range | Anchor | Verified against | Verified at | Notes |
```

`Kind` is blank/unrecognized on any pre-#1198 row → treated as unset,
never a defect (the same "unknown is honest" posture
`anvil/lib/provenance_anchor.py`'s `STATUS_NO_ANCHOR` already
established for the `Anchor` column's own backward-compatibility case).
`Claim` / `Source file` / `Line range` / `Anchor` / `Notes` keep their
existing #597/#868 contract unchanged; `Verified against` / `Verified
at` are the two new columns this record proposes.

## Status of the implementation (PR 2)

This record is deliberately docs-only, per Champion's approval scope. A
complete, tested draft implementation resolving both decisions above —
`anvil/skills/essay/lib/claim_ledger.py`, the `essay-review.md` /
`essay-revise.md` procedure updates, and
`anvil/skills/essay/tests/test_essay_claim_ledger.py` — already exists
and is preserved on the `archive/issue-1198-claim-ledger-draft` branch
(commit `11d45040b5be9efa290c9d672b6d4ae2e4f96366`) for whoever picks up
PR 2. It was written before this record was promoted to a standalone PR
and independently reaches the same two decisions documented above, so it
should need at most reconciliation with this record's exact wording, not
a redesign. Per Champion's 2026-09-15 approval comment on #1198, PR 2 is
separate follow-on work to be re-evaluated once this record merges — it
is not part of this PR's diff.

## References

- #888 — parent issue, Failure 3 + general claim-ledger problem statement
- #1197 — sibling Failure-1 split (predicted downstream effects), deliberately scoped to not require this ledger
- #597 / `anvil/lib/snippets/provenance.md` — the existing corpus-provenance contract this record extends
- #868 / `anvil/lib/provenance_anchor.py` — the content-addressed anchor pattern reused for the `corpus` kind
- #142 / #147 / PR #155 — the killed `_convictions.md` primitive's architect proposal + Phase A ship
- #225 / #226 — the two structural defects the canary observation found
- #227 / #228 — the kill-switch execution + the architect placeholder left open for a future redesign (this record is that redesign, scoped to a different, narrower failure mode)
