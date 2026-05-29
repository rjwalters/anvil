# Proposal review rubric

The reviewer scores a buildable-system proposal against 8 weighted dimensions summing to **40**. The threshold to advance is **≥32/40**. Any **critical flag** — set by either `proposal-review` or `proposal-audit` — short-circuits the verdict regardless of total score until addressed.

A proposal must score BOTH "is this technically sound" AND "should the approver say yes / can we deliver". The weighting reflects this: the **engineering substance (dims 1–4 = 22/40 = 55%)** dominates, with deliverability + cost (10/40) and the pitch (4/40) as the proposal-specific additions. A proposal lives or dies on the customer's hard constraints, so constraint satisfaction is tied for the top weight with design correctness.

## Dimensions

| # | Dimension | Weight | What it measures |
|---|---|---|---|
| 1 | **Intent / requirements clarity** | 5 | What the system must do and the constraints it operates under — what the customer / sponsor needs. A reader should grasp the requirement and its non-negotiables from the Premise alone. |
| 2 | **Design correctness** | 6 | Topology + component choices are technically sound and internally consistent. The engineering core: a competent engineer would not object to the architecture as drawn. |
| 3 | **Constraint satisfaction** | 6 | The design explicitly meets the stated hard constraints (e.g. invisibility, no conduit, 10 Gbps). Tied for top weight — proposals live or die on the customer's hard constraints, and the proposal must show it threads each one. |
| 4 | **Scope completeness** | 5 | BOM, interfaces, coverage, inclusions / exclusions are fully enumerated; nothing load-bearing is left implicit. A reader can tell exactly what is and is not in the price. |
| 5 | **Deliverability** | 5 | The executor can actually build it — a real path to the staff / contractors / tools / skills needed to execute and maintain it (the Gossamer "fiber workshop" angle). The install method is real and sequenced. |
| 6 | **Cost credibility** | 5 | BOM + labor are priced, sourceable, and competitive. Figures have a basis (planning range, vendor list price, quote), not arbitrary numbers; the arithmetic holds. |
| 7 | **Persuasiveness / value proposition** | 4 | Why the approver should say yes — the pitch element. For `customer_kind: external`, read as "wins the client". For `customer_kind: internal`, read as "justifies the budget allocation" (same weight, reframed prompt). |
| 8 | **Open decisions** | 4 | Unresolved engineering choices are tracked honestly (the `anvil:memo` "assumptions to validate" analogue). A proposal that pretends every decision is settled scores low. |
| | **Total** | **40** | Advance threshold: ≥32 |

## `customer_kind` and dimension 7

The proposal's `customer_kind` frontmatter key (`external` | `internal`, default `external`) reframes how the reviewer reads dimension 7 — it does not change the weight:

- **`external`** (an external client): dim 7 is read as written — does the proposal give the client a reason to commit money? Is the value proposition legible and competitive?
- **`internal`** (an internal budget sponsor): dim 7 is read as "does this justify the budget allocation?" — is the spend defensible against the alternative of not building it, or building it differently? The pitch is to the budget, not to a client.

All other dimensions are scored identically regardless of `customer_kind`.

## Scoring guidance

For each dimension, the reviewer assigns an integer between 0 and the dimension's weight. A short justification accompanies each score (1–3 sentences pointing to specific evidence in `proposal.tex`).

Suggested calibration:
- **Full weight** — meets the standard convincingly; a sophisticated engineer or buyer would have no substantive objection on this dimension.
- **~75% of weight** — meets the standard with a defensible gap or one specific weakness noted.
- **~50% of weight** — partial; multiple gaps or one significant weakness.
- **~25% of weight** — present but inadequate; major rework needed.
- **0** — absent or actively incoherent.

## Advance threshold

- **≥32/40** — advance to `READY` (subject to also having `pass: true` in the audit sibling).
- **<32/40** — block; revise.
- **Any critical flag set** (in either `.review/` or `.audit/`) — block regardless of total. The next revision must address the flagged issue specifically and the relevant critic must re-evaluate the flag before the threshold check applies.

## Critical flags

A critical flag is an issue severe enough that **the proposal cannot proceed as specified**, regardless of how well other dimensions score. The four named flags below are the disqualifiers for a buildable-system proposal; three of the four are **audit-owned** (`kind: tool_evidence` — set by `proposal-audit` from externally-verifiable checks per `anvil/lib/snippets/audit.md`). This list is the baseline, not a closed set.

1. **Misses a stated hard constraint** *(review-owned)* — the design violates a constraint the customer declared non-negotiable (e.g. visible conduit when invisibility was required; sub-spec bandwidth when 10 Gbps was the floor). The proposal fails its own brief.
2. **Cost estimate not credible / not sourceable** *(audit-owned)* — BOM or labor figures are unsourceable, internally arbitrary, or off by an order of magnitude. The auditor walks every priced line for a basis (planning range, vendor list price, quote) and flags any that has none or is implausible.
3. **Not deliverable as resourced** *(audit/review-owned)* — there is no real path to the staff / contractors / tools / skills needed to build and maintain the system as proposed. The "workshop" / delivery-capability story is absent or hand-waved, so the proposal cannot be executed by the party it is pitched to.
4. **Internal inconsistency** *(audit-owned)* — the proposal contradicts itself on a verifiable fact: optics link budget vs. stated run length; BOM quantities vs. topology (e.g. 7 spokes should imply 14 + 2 uplink = 16 transceivers); section subtotals or the project total that do not add up.

The reviewer and auditor should each raise a flag for any other issue that, in their judgment, meets the "cannot proceed as specified" bar above — these four are starting points, not a closed set.

## Verdict format

### Review verdict (`<thread>.{N}.review/verdict.md`)

1. **Total score**: `XX / 40`.
2. **Decision**: `advance: true` or `advance: false`. (`advance: true` requires `total ≥ 32` AND `no unresolved critical flag`.)
3. **Critical flags** (if any): bullet list, each with one-paragraph justification.
4. **Dimension summary**: a markdown table of per-dimension scores (full detail lives in `scoring.md`).
5. **Top 3 revision priorities** (if `advance: false`): the highest-leverage changes the reviser should focus on.

### Audit verdict (`<thread>.{N}.audit/verdict.md`)

1. **Pass**: `pass: true` or `pass: false`.
2. **Coverage**: how many priced lines and quantitative claims were audited (e.g. "audited 18/18 BOM lines, 3 subtotals, 4 link-budget/spec claims").
3. **Critical flags** (if any): bullet list, each with one-paragraph justification pointing to a specific location in `proposal.tex` and the specific evidence (or absence thereof). The audit owns flags 2, 3, and 4 above.
4. **Top revision priorities** (if `pass: false`): the specific factual / arithmetic fixes required.

The auditor's `findings.md` contains the per-claim audit log (claim, location, basis, verified?). The auditor's `evidence.md` contains the source → dependent-claims traceability map. Both are required outputs.

## Combined advance gate

For the thread to reach the `AUDITED` state (this skill's terminal state):

```
advance = review.advance == true       (total ≥ 32)
       AND audit.pass == true
       AND no unresolved critical flags in either sibling
```

If either sibling blocks, the thread stays in `REVIEWED+AUDITED` (with both verdicts written) and the operator runs `proposal-revise` to produce `<thread>.{N+1}/`, which is then re-reviewed and re-audited.

## Output layout

```
<thread>.{N}.review/
  verdict.md       Top-level decision (see above)
  scoring.md       Per-dimension score + justification
  comments.md      Line-level comments keyed to proposal.tex
  _meta.json       { critic, scorecard_kind: "human-verdict", ... }
  _progress.json   { phases.review.state == done }

<thread>.{N}.audit/
  verdict.md       Pass/fail + critical flags + coverage
  findings.md      Per-claim audit log (BOM arithmetic, spec/link-budget, sourceability)
  evidence.md      Source → dependent-claims traceability map
  _meta.json       { critic: "audit", scorecard_kind: "human-verdict", ... }
  _progress.json   { phases.audit.state == done }
```

Both critic sibling dirs are **read-only once written** (state: `done` in their own `_progress.json`). Revisions consume them without modifying them. Critic siblings use `scorecard_kind: "human-verdict"` and emit the `verdict.md` (+ `scoring.md`/`comments.md` for review, + `findings.md`/`evidence.md` for audit) shape — the same shape `anvil/lib/critics.py` reads via its `LEGACY_MEMO_FILES` adapter. No `anvil/lib/` schema changes are introduced.
