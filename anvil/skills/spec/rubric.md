# Spec review rubric

Rubric id: **`anvil-spec-v1`**. The reviewer and auditor score a spec against 9 weighted dimensions summing to **44**. The threshold to advance is **≥39/44** (the audit-grade / legal band used by `report`/`ip-uspto`/`datasheet` — a normative specification is an audit-grade artifact an implementer reads as the source of truth, NOT general educational collateral). Any **critical flag** short-circuits the verdict — the spec is blocked regardless of total score until the flagged issue is addressed.

The rubric is tuned so that **normative correctness dominates**: dim 1 (*Normative correctness*) carries the highest weight (7) because the artifact class succeeds or fails on whether its claims are *true of the thing it describes* — the way `primer` tilts toward pedagogy (dim 1, weight 7) and `essay` toward voice. Behind it, **internal consistency** (dim 2) and **claim precision** (dim 3) are heavy (weight 6 each): a spec that contradicts itself section-to-section, or states a normative claim ambiguously, is a defect an implementer trips over. Dim 9 (*Rhetorical economy*) is **residual here rather than load-bearing** (unlike `essay`, where it is load-bearing) — a spec is expected to be exhaustive, so economy is guarded but not the point.

**Phase-1 scoping note.** The full spec↔implementation audit sweep (the mechanized `code_ref` cross-check) is **Phase 2 scope (#707)**, and the deterministic cross-table constant-consistency gate is **Phase 3 scope (#708)**. This Phase-1 `rubric.md` defines each dimension's *scoring rubric* (what a 7 vs a 3 looks like) so reviewers and auditors can score by manual judgment against `code_ref` today; the mechanized sweeps land later and slot in under the same dimensions without re-weighting.

## Dimensions

| # | Dimension | Weight | What it measures |
|---|---|---|---|
| 1 | **Normative correctness** | 7 | (dominant) Every normative claim — a constant, a struct/field layout, a formula, a validity predicate — either matches the `code_ref` implementation OR is explicitly marked target-state with the gap tracked. This is the dim the class lives or dies on. When `code_ref` is active, scored against the resolved implementation; when undeclared, scored on the spec alone AND a `major` finding recommends declaring it (see SKILL.md §Code-ref contract). Deductions quote the claim AND (when known) the contradicting implementation location. |
| 2 | **Internal consistency** | 6 | The same quantity, constant, or predicate stated in multiple sections agrees with itself (the datasheet dim-2 shape: a block-time floor stated as 3s in one section and 5s in another is the failure mode). Phase 1 scores this by judgment; Phase 3's deterministic constant-extraction gate (#708) mechanizes the cheap half later. Deductions quote both occurrences and their sections. |
| 3 | **Claim precision** | 6 | Every normative claim is unambiguous and falsifiable — an implementer can read it, implement exactly it, and test conformance against it. Weasel words, undefined terms used normatively, and "should/must/may" used loosely (RFC 2119 discipline) deduct. Report/datasheet-adjacent "spec accuracy" framing. |
| 4 | **Completeness** | 5 | The spec covers every component/message/state it claims to normatively govern; no dangling "TBD" in a load-bearing predicate, no message type referenced but never defined. A reader can implement the whole system from the spec without guessing. Undefined-but-referenced entities deduct. |
| 5 | **Technical accuracy** | 5 | Beyond correspondence to `code_ref`, the spec's internal logic holds: formulas are dimensionally sound, predicates are satisfiable, cited primitives are used correctly. (Audited — see the audit-side twin below.) A claim that is internally wrong (not merely code-mismatched) deducts here; a code-mismatch is dim 1 / the audit's consistency finding. |
| 6 | **Structure & navigation** | 4 | Audit-grade wayfinding: numbered sections, a definitions/notation section, a table of contents, "see §X" cross-references that resolve. A reader who can't locate the normative statement governing a behavior is the failure mode. |
| 7 | **Cross-reference & versioning discipline** | 4 | Internal cross-references (`§X`, equation/table references) resolve; the spec versions itself (revision history / change markers) so a reader knows which version they hold and what changed. Dangling references and unversioned normative changes deduct. |
| 8 | **Prose clarity** | 4 | Sentence/paragraph craft for an implementer audience: the reader is never re-reading a normative sentence to parse what it requires. |
| 9 | **Rhetorical economy** | 3 | Earns its length; no padding. **Residual here** (unlike `essay`, where it is load-bearing) — a spec is expected to be exhaustive, so this is guarded but not dominant. Wandering repetition and non-normative digressions deduct. |
| | **Total** | **44** | Advance threshold: ≥39 |

## Scoring guidance

Each dimension is scored as an **integer from 0 to its weight** (the weight is the per-dimension maximum; no half-points). A short justification accompanies each score (1–3 sentences citing specific evidence: a quoted passage with a location anchor).

Calibration (stated for dim 1 at weight 7; scale proportionally for other weights):

- **7 (full weight)** — every normative claim either matches the resolved `code_ref` implementation or is explicitly marked target-state with a tracked gap; an implementer reading the spec builds exactly what the code does (or exactly the marked target).
- **5–6** — mostly correct with one or two claims whose correspondence to the implementation is unverified or slightly stale (quote each).
- **3–4** — several normative claims have drifted from the implementation with no target-state marking; an implementer would build the wrong thing in places.
- **1–2** — the spec substantially contradicts the implementation and does not track the gaps; it is not a trustworthy source of truth.
- **0** — no correspondence to any implementation; the spec describes a system that does not exist as written.

**Quoted evidence.** Every justification embeds at least one **verbatim quote from the spec body** with a location anchor — `("the quoted span" — §2.1)` — per `anvil/lib/snippets/rubric.md` §"Dimension scoring guidance" rule 1, with the `no instance of <X> found` by-absence marker allowed at full weight only. A quote that does not appear verbatim in the body is fabricated evidence and the justification must be re-derived.

## Critical flags

Any single flag → BLOCK, regardless of total score. Each flag's justification in `verdict.md` (review-side) or `verdict.md`/`findings.md` (audit-side) quotes the offending passage and the contract it violates.

1. **Self-contradiction** (review-side — `spec-review`, judgment): the same normative quantity/predicate is stated two incompatible ways in the spec (the block-time-floor 3s-vs-5s shape). Quote both occurrences and their sections. This is a hard block because an implementer cannot satisfy a spec that contradicts itself. *(Phase 3's deterministic constant gate (#708) will mechanize the cheap half of detecting this; Phase 1 catches it by judgment.)*
2. **Undefined normative term** (review-side — `spec-review`, judgment): a term used in a `MUST`/`SHALL`/validity predicate is never defined, making the requirement unfalsifiable. Quote the normative use and confirm the absence of a definition.
3. **Implementation contradicts normative claim** (audit-side — `spec-audit`; conditional on an active, resolved `code_ref`): a spec claim disagrees with the resolved implementation. **PHASE 1 SCOPE NOTE — the full three-way verdict is deferred to Phase 2 (#707).** The fix direction (spec-wrong → revise spec; code-wrong → operator escalation, **never** silently rewrite the spec to match a vestigial code path; intentional target-state gap → record in the implementation-status register) is a *human decision* the Phase-1 skeleton does NOT adjudicate. **Phase 1 posture: an auditor who detects a suspected code/spec mismatch records it as a `major` finding** (quoting the spec claim AND the implementation location), surfaces the ambiguous direction to the operator in the verdict prose, and **never auto-rewrites the spec**. The three-way verdict logic + implementation-status register that promote this to a fully-adjudicated critical flag land in Phase 2. **Inactive (cannot fire) when `code_ref` is undeclared or unresolvable** — no implementation to check against; the missing/broken contract is a `major` finding instead.

**Absent-`code_ref` posture (flag 3 inactive).** When the `documents:` entry declares no `code_ref`, flag 3 **cannot fire** — no false critical flag, no crash. Instead, both `spec-review` and `spec-audit` record a **`major` finding recommending the operator declare `code_ref`**: a spec whose defining constraint ("every normative claim is true of the implementation, or marked target-state") is unenforceable is a defect to surface, not a blocker. A declared-but-unresolvable `code_ref` (bad path) is also a `major` finding (the tier activates but degrades gracefully), never a critical flag.

If no critical issues, the verdict says so explicitly: "Critical flags: none."

**Never a critical flag (Phase 1)**: a suspected code/spec mismatch (a `major` finding pending Phase 2's three-way verdict — never an auto-rewrite), an undeclared or unresolvable `code_ref` (a `major` finding), or length past an implicit envelope (dim 9 deduction).

## Advance threshold

- **Review total ≥39/44** AND no unresolved review critical flag AND a clean audit (no unresolved audit critical flag) → advance; the thread is `READY`/`AUDITED` (terminal — see SKILL.md §Publish handoff contract).
- **Review total <39/44** OR any unresolved critical flag (review-side or audit-side) → block; revise.
- Termination order (critical flag → threshold → iteration cap → stalled) per `anvil/lib/snippets/rubric.md`.

## Critic sidecar format

Both critics emit the **`human-verdict`** scorecard kind per `anvil/lib/snippets/scorecard_kind.md`.

```
<thread>.{N}.review/
  verdict.md       Advance / block + total /44 + critical-flag paragraphs + top revision priorities
  scoring.md       Per-dimension table: # | Dimension | Weight | Score | Justification
  comments.md      Line-level comments keyed to the body (severity + scope tags)
  _summary.md      Machine-readable blocks (rubric, code_ref echo, scope_distribution)
  _meta.json       Stamps (below)
  _progress.json   Phase state for the reviewer

<thread>.{N}.audit/
  verdict.md       Audit verdict + critical audit-flag paragraphs (factual + spec↔implementation)
  findings.md      Per-claim table: claim | kind (factual/implementation-consistency) | verified? | evidence
  comments.md      Line-level audit comments
  _summary.md      Machine-readable audit blocks (code_ref resolution, findings counts)
  _meta.json       Stamps (below)
  _progress.json   Phase state for the auditor
```

## `_meta.json` format

```json
{
  "critic": "review",
  "role": "spec-review.md",
  "started": "2026-07-14T15:00:00Z",
  "finished": "2026-07-14T15:18:00Z",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict",
  "rubric_id": "anvil-spec-v1",
  "rubric_total": 44,
  "advance_threshold": 39
}
```

The three rubric-stamping fields (`"rubric_id": "anvil-spec-v1"`, `"rubric_total": 44`, `"advance_threshold": 39`) are **mandatory** in every critic `_meta.json` this skill writes (per-review version stamping, issue #346) — the skill ships post-stamping, so there is no legacy-absence tolerance needed on the write side; readers still tolerate absence per the framework-wide backwards-compat contract. The critic sibling dir is **read-only once written**.

Consumers add domain-specific critical-flag examples via `.anvil/skills/spec/rubric.overrides.md` (additive only; cannot reduce the base rubric).
