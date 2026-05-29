---
name: proposal-audit
description: Auditor command for the proposal skill. Verifies BOM arithmetic, spec/link-budget consistency, cost sourceability, and internal consistency against the topology. Writes a read-only audit sibling directory. RUN BY DEFAULT — required to leave DRAFTED state.
---

# proposal-audit — Auditor

**Role**: auditor (`kind: tool_evidence`).
**Reads**: latest `<thread>.{N}/` (specifically `proposal.tex`, the priced BOM/labor/total tables, and the spec tables), and `<thread>/refs/**` (datasheets, vendor quotes, planning-range sources) for the sourceability check.
**Writes**: `<thread>.{N}.audit/` with `verdict.md`, `findings.md`, `evidence.md`, `_meta.json`, and `_progress.json`.

The audit sibling directory is **read-only once written**. Revisions consume it; they never modify it.

This is one of the **two REQUIRED critic siblings** for the proposal skill (the other is `proposal-review`). Both must complete before a thread can leave the `DRAFTED` state. They run in parallel.

**This command is run by default.** This is the substantive divergence from `anvil:installation` (which deferred audit per memo, because installation-art proposals make few externally-verifiable factual claims). Proposals are different: they make priced, sourceable cost claims and link-budget/throughput claims that are exactly the `kind: tool_evidence` class the audit phase exists for (per `anvil/lib/snippets/audit.md`, audit owns "numeric consistency — does the math check?"). Three of the rubric's four critical flags are audit-owned. The closest precedent is the post-commitment bookend `anvil:report`, which runs `report-audit` by default because a document someone relies on to move money has high correctness stakes. A proposal is the pre-commitment instance of the same.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/proposal.tex` existing.
- **Source references**: `<thread>/refs/**` — datasheets, vendor price lists, quotes. The auditor uses these as the sourceability basis for priced lines and spec claims. (A proposal without `refs/` is auditable on internal consistency and arithmetic alone; the auditor flags any price that has neither a `refs/` basis nor an inline planning-range basis.)
- **Rubric** (audit-side critical flags): `anvil/skills/proposal/rubric.md` (flags 2, 3, 4 are audit-owned).

## Outputs

```
<thread>.{N}.audit/
  verdict.md       Pass/fail + critical flags + coverage summary + top revision priorities
  findings.md      Per-claim audit log (every priced line + quantitative/spec claim + audit result)
  evidence.md      Source → dependent-claims traceability map (every source → which claims depend on it)
  _meta.json       { critic: "audit", scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state for the auditor (phase: audit)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/proposal.tex`. If `<thread>.{N}.audit/_progress.json.audit.state == done` and `verdict.md` exists, the audit is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed audit exists (`audit.state == in_progress` without `verdict.md`), delete the partial output and re-audit.
3. **Initialize `_progress.json`** for the audit dir: `phases.audit.state = in_progress`, `phases.audit.started = <ISO>`, `for_version = N` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`); proposal-audit ships task-specific `findings.md` and `evidence.md` alongside the scorecard-kind declaration. (Per the migration note in `audit.md`, this command emits the legacy prose triple today; the legacy adapter bridges it to the `kind: tool_evidence` contract.)
4. **Read inputs**: load `<thread>.{N}/proposal.tex`, parse the BOM / labor / project-total tables and the spec tables, enumerate `refs/`.
5. **Audit the BOM arithmetic** — the central check:
   - For **every priced line** in the multi-section BOM, verify `Qty × Unit = Total`. For ranges (`$15--20`), verify both endpoints (`Qty × low = Total_low`, `Qty × high = Total_high`).
   - Verify each **section subtotal** (if the BOM groups lines) and the bold **Materials subtotal** against the sum of its lines.
   - Verify the **Labor subtotal** (hours and cost) against the sum of the labor lines.
   - Verify the **Project total** = Materials subtotal + Labor subtotal.
   - Record each in `findings.md`.
6. **Audit spec / datasheet consistency** — the link-budget check:
   - For each claimed part number, rated distance, power budget, or link budget, check it against the stated demand. Examples: an SFP+ LR transceiver rated 10 km vs. palazzo runs of <500 m (passes — headroom); a 400 W PoE budget vs. the summed AP draw on that switch (must not exceed); a fiber bend radius vs. the routing the proposal calls for.
   - Where a `refs/` datasheet exists, verify the claimed spec matches it. Where none exists, flag the claim as `Verified? = n/a — no datasheet in refs/` and note whether the claim is plausible on its face.
7. **Audit sourceability** — the cost-credibility check:
   - For **every price**, confirm it has a basis: a planning range stated inline, a vendor list price, or a quote in `refs/`. A price that is internally arbitrary (a round number with no basis) or off by an order of magnitude is a finding.
   - Record the basis for each price in `evidence.md`.
8. **Audit internal consistency** — the cross-check:
   - **BOM quantities vs. topology**: derive expected quantities from the topology and compare. Example: 7 fiber spokes → 14 transceivers (two per spoke) + 2 for the gateway uplink = 16; if the BOM lists a different count, that is a finding.
   - **Coverage rule vs. count**: if the proposal states a coverage rule (one AP per major room) and a room count, the AP quantity in the BOM must follow from it.
   - Any two parts of the proposal that disagree on a verifiable fact is a finding.
9. **Build the claim inventory** in `findings.md` with columns:

   ```
   | # | Location | Claim | Basis | Verified? | Notes |
   |---|----------|-------|-------|-----------|-------|
   | 1 | §7 BOM   | "7 × $799 = $5,593" | arithmetic | yes | 7 × 799 = 5593 ✓ |
   | 2 | §7 BOM   | "SFP+ LR $15--20, qty 16, total $240--320" | arithmetic + planning range | yes | 16×15=240, 16×20=320 ✓; price is a planning range |
   | 3 | §5 Optics| "SFP+ LR rated 10 km vs. <500 m runs" | spec headroom | yes | 20× margin — consistent |
   | 4 | §7 BOM   | "16 transceivers" | topology (7 spokes) | yes | 7×2 + 2 uplink = 16 ✓ |
   | 5 | §7 total | "Materials + Labor = $13,494--17,599" | arithmetic | NO | $8,494+$5,000=$13,494 low ✓; $10,499+$7,100=$17,599 high ✓ — consistent |
   ```

   Every row gets a `Verified?` value of `yes`, `no`, `partial`, or `n/a`.
10. **Build the evidence map**: in `evidence.md`, invert the above — list every source (a `refs/` datasheet, a stated planning range, a vendor list price) and, for each, the priced lines / spec claims that depend on it. This surfaces unsourced prices (a price depending on nothing) and the single-source risk (everything depending on one quote).
11. **Identify audit-side critical flags** (see `rubric.md`):
    - **Cost estimate not credible / not sourceable** (flag 2) — any price with no basis, or off by an order of magnitude.
    - **Not deliverable as resourced** (flag 3, shared with review) — if the delivery-capability ("workshop") story implies tools/skills the BOM does not actually fund, or implies staffing the labor estimate does not account for.
    - **Internal inconsistency** (flag 4) — failed arithmetic, a subtotal that does not add up, a transceiver count that disagrees with the topology, or a spec that contradicts the demand (e.g. a link budget that does not close over the stated run length).
12. **Compute pass/fail**: `pass = (no critical flags) AND (all priced lines and quantitative claims verified, or partial-with-acceptable-rationale)`.
13. **Write `verdict.md`** in the format specified in `rubric.md`:
    - Pass: `pass: true` or `pass: false`
    - Coverage: how many BOM lines, subtotals, and spec/link-budget claims were audited (e.g. "audited 18/18 BOM lines, 3 subtotals, 4 spec claims; 23 verified, 2 partial").
    - Critical flags (if any) with justification pointing to a specific location and the specific evidence (or its absence).
    - Top revision priorities (if `pass: false`): the specific factual / arithmetic fixes required.
14. **Update `_progress.json`**: `phases.audit.state = done`, `phases.audit.completed = <ISO>`.
15. **Report**: print the path to the audit dir and a one-line status (e.g., `Audited gossamer-lan.1 → gossamer-lan.1.audit/ (pass: true, 0 critical flags, 18 BOM lines + 4 spec claims audited)`).

## Idempotence and resumability

- A completed audit (`audit.state == done` AND `verdict.md` exists with a parseable pass/fail) is never re-run. Re-invoking is a no-op with a notice.
- A crashed audit is re-runnable after deleting partial output.

## Parallel-with-review semantics

This command makes NO attempt to coordinate with `proposal-review`. Both commands read the same `<thread>.{N}/` version dir; they write to disjoint sibling paths; neither reads the other's output. The portfolio orchestrator (and `proposal-revise`) aggregates both critic outputs. The split is principled (see `anvil/lib/snippets/audit.md`): the reviewer owns subjective judgment (`kind: judgment`); the auditor owns externally-verifiable correctness (`kind: tool_evidence`) — the BOM arithmetic, the link budgets, the sourceability.

## Notes for the auditor agent

- **You are not a reviewer.** Stylistic and persuasiveness concerns are out of scope; defer them to the review sibling. Your job is to verify that the numbers are **internally consistent, arithmetically correct, sourceable, and physically plausible**.
- **Check every priced line.** A single wrong `Qty × Unit` or a subtotal that does not add up is critical flag 4 (internal inconsistency) — a proposal whose own math is wrong cannot be relied on to price the commitment.
- **A price with no basis is worse than an expensive one.** Flag 2 is about sourceability, not magnitude: a defensible $5,593 line beats an arbitrary $3,000 line. State the basis (planning range / list price / quote) for every price in `evidence.md`; flag any that has none.
- **The link budget is load-bearing.** A transceiver rated for less than the stated run length, or a power budget exceeded by the summed device draw, is a design that does not work as drawn — flag 4. Conversely, generous headroom (10 km optics over 500 m runs) is consistent, not a finding.
- **Derive counts from the topology.** Do not take the BOM's quantities on faith — re-derive them (spokes → transceivers, rooms → APs) and flag any mismatch. This is the most common internal inconsistency.
- **Quantify your coverage** in `verdict.md`. State exactly how many lines and claims you audited and the verified/partial/unverified split. If a claim cannot be verified because no datasheet is in `refs/`, flag it explicitly with `Verified? = n/a` and recommend the reviser add the source or soften the claim.

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

And the companion `_meta.json` declaring the scorecard kind:

```json
{
  "critic": "audit",
  "role": "proposal-audit.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict"
}
```

Merge rule (shallow): preserve fields not touched by this command. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
