---
name: deck-market
description: Market/TAM-credibility critic for the deck skill. Verifies TAM/SAM/SOM arithmetic, evaluates competitive framing, and scores rubric dims 3 (market size credibility) and 4 (solution differentiation).
---

# deck-market — Market / competitor critic

**Role**: market and competitor critic.
**Reads**: latest `<thread>/<thread>.{N}/deck.md` (the version dir is nested under the thread root per the artifact contract; market and competition slides + any supporting figures and `figures/src/*.csv`); `<thread>/BRIEF.md`; optional `<thread>.{M}.perspective/candidates.md` for `M ≤ N` (the latest perspective sibling at or before the current version — see `anvil/lib/snippets/perspective.md`; gracefully absent on threads that have never run `deck-perspective`).
**Writes**: `<thread>/<thread>.{N}.market/` with `_summary.md`, `findings.md`, `comments.md`, `_meta.json`, `_progress.json`. Bare `<thread>.{N}/` / `<thread>.{N}.<critic>/` references below are shorthand for these nested paths.

This critic verifies the market case the deck makes. It computes TAM/SAM/SOM arithmetic, checks bottom-up vs top-down framing, and evaluates competitor positioning. Market-math errors and top-down-only sizing are high-frequency disqualifiers at investor diligence; this critic catches them before send.

## Owned rubric dimensions

- **3 — Market size credibility** (weight 5)
- **4 — Solution differentiation** (weight 5)

Total ownership: 10/44. Other dimensions are scored by other critics and remain `null` in this critic's `_summary.md`.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md` under the thread root `<thread>/`.
- **Brief**: `<thread>/BRIEF.md` (sections "Market" and "Competition" specifically; other sections for grounding).
- **Source data**: `<thread>.{N}/figures/src/*.csv` (if market sizing uses a chart, the source data lives here).
- **Optional perspective sibling**: `<thread>.{M}.perspective/candidates.md` for the highest `M ≤ N` (per `anvil/lib/snippets/perspective.md`). If present, widens the competitor cross-check substrate beyond the brief. Gracefully absent on threads with no perspective sibling — no error, no finding. See step 5 "Cross-check against perspective candidates" for the discovery rule.
- **Optional override**: `.anvil/skills/deck/rubric.overrides.md`.

## Outputs

Nested under the thread root `<thread>/`, as a sibling of the `<thread>.{N}/` version dir under critique:

```
<thread>.{N}.market/
  _summary.md       9-dim partial scorecard (dims 3 + 4 scored; others null) + critical-flag bool
  findings.md       Itemized findings (severity, slide ref, rationale, suggested fix)
  comments.md       Slide-level commentary (market slide, competition slide)
  tam-recompute.md  (Optional) Independent recomputation of TAM/SAM/SOM showing the critic's working
  _meta.json
  _progress.json
```

**Atomicity** (issue #350, #376): the market sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The five required files (`_summary.md`, `findings.md`, `comments.md`, `_meta.json`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.market.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.market/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.market.tmp/` dir on disk that the next invocation's `cleanup_one_staging(<thread>.{N}.market)` per-critic sweep removes; the final-named dir never exists in partial form. The optional `tam-recompute.md` is written inside the staging dir but is NOT in the required-files manifest (it is a conditional output). Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob.

## Procedure

1. **Discover state** + **resume check** (standard). Then **sweep a stale staging dir from a prior interrupt of THIS critic on THIS version** by invoking `anvil/lib/sidecar.py::cleanup_one_staging(<thread>.{N}.market)` (the per-critic, parallel-safe sweep — issue #376). This removes ONLY a leftover `.<thread>.{N}.market.tmp/` from a previously-killed run of this same critic on THIS version. Sibling critics' in-flight staging dirs under the same thread root are NOT touched (issue #350, #376). The "completed" check is satisfied when the final-named `<thread>.{N}.market/` exists — the atomic-rename contract guarantees the dir only exists when complete.
2. **Open the staged sidecar** for the market dir by invoking the context manager `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.market, required_files=["_summary.md", "findings.md", "comments.md", "_meta.json", "_progress.json"])`. Every file write below MUST land **inside the yielded staging directory** (the path of the shape `.<thread>.{N}.market.tmp/`), NOT inside the final `<thread>.{N}.market/` path. On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name (issue #350). Then, **inside the staging dir**, initialize `_progress.json` + `_meta.json`.
3. **Read inputs**: load `deck.md`, identify market slide(s) and competition slide(s). Load `BRIEF.md` market and competition sections. Load any market-chart source data from `figures/src/*.csv`.
4. **Evaluate market size credibility** (Dim 3, weight 5):
   - **Identify the sizing approach**: bottom-up, top-down, or hybrid?
     - **Bottom-up** (e.g., "250k US plants × $80k average annual contract = $20B TAM"): credit for transparent inputs; verify the inputs are plausible.
     - **Top-down** (e.g., "$300B industrial automation market × 1% capture = $3B SAM"): low credit by default — this framing is a near-automatic disqualifier at most funds. Score ≤2/5 if top-down-only.
     - **Hybrid**: full credit possible if bottom-up backs up a top-down anchor.
   - **Recompute the arithmetic independently**: take the inputs the deck cites, compute the result, compare to what the deck claims. Write the recomputation to `tam-recompute.md` showing your working.
     - If recomputation matches within rounding → no flag.
     - If recomputation diverges by >10% → **Market-math error critical flag**. Document in `findings.md` with both numbers and the discrepancy.
   - **Verify inputs**: are the input numbers (plant count, average contract size, market size) themselves sourced? Cite where they come from in BRIEF.md or refs. Unsourced inputs reduce score even if arithmetic is correct.
   - **Comparables**: are recent comparable transactions cited (named companies, disclosed valuations)? Comparables anchor the market story; absence is a credit-reducer but not a flag.
5. **Evaluate solution differentiation** (Dim 4, weight 5):
   - **Competitive landscape framing**: is the competition slide a 2x2 (axes labeled), a feature matrix, or a narrative? Any is acceptable if it shows where the company sits and where competitors sit.
   - **Named competitors**: are competitors named specifically (not "legacy players" or "various startups")? Generic competition framing is a credit-reducer.
   - **Moat language**: is differentiation explained by mechanism (network effects, switching costs, regulatory moat, technology lead, distribution lock-in) or by adjective ("faster", "cheaper", "better")? Mechanism > adjective.
   - **Incumbent risk**: does the deck address how it survives an incumbent decision to enter? Most decks omit this; flag absence as a minor finding rather than score deduction unless the incumbent risk is the obvious objection.
   - **Cross-check named competitors against brief and perspective**: every named competitor on the slide should appear in the brief's competition section. If a **perspective sibling** is present at `<thread>.{N}.perspective/candidates.md` (per `anvil/lib/snippets/perspective.md`), the cross-check expands to the union of brief-named entities AND perspective candidates. Competitors named only on the slide — appearing in neither the brief nor (when present) the perspective candidates — surface as the **"unmatched competitor" finding** (severity: warning; see "Cross-check against perspective candidates" below). This warning is the evidentiary base for the **Fabricated competitive claims** critical flag (step 6): a critic that finds an unmatched competitor SHOULD also consider whether the deck makes verifiable factual claims about that competitor (named customers, disclosed revenue, specific product features) — if so, escalate to the critical flag.

   ### Cross-check against perspective candidates

   **Behavior when perspective sibling is present.** If `<thread>.{N}.perspective/candidates.md` exists (the perspective candidate list documented in `anvil/lib/snippets/perspective.md`), deck-market loads the candidate list and uses it to widen the cross-check substrate beyond the brief. The reference set becomes:

   ```
   reference_set = (entities named in BRIEF.md "Competition" section)
                 ∪ (named entities in <thread>.{N}.perspective/candidates.md)
   ```

   For each named competitor in the deck's competition slide(s), check whether the name (case-insensitively, allowing common shorthand variants like "UiPath" vs "UI Path") appears in the `reference_set`. If a competitor name appears in NEITHER set, emit the unmatched-competitor finding.

   **Behavior when perspective sibling is absent — graceful skip.** If no `<thread>.{N}.perspective/candidates.md` (or any older `<thread>.{M}.perspective/candidates.md` for `M ≤ N`) is on disk, deck-market gracefully skips the perspective half of the cross-check. The brief-only cross-check still runs unchanged — this is the v0 behavior preserved for backwards compatibility. **The absence of a perspective sibling is NEVER an error**: perspective is a non-gating, opt-in input (per `anvil/lib/snippets/perspective.md` "State-machine non-gating"). deck-market silently proceeds without surfacing the absence as a finding. Decks running on threads that have never run `deck-perspective` see no behavioral change from this cross-check beyond the pre-existing brief-only path.

   **Discovery rule for the perspective sibling.** Walk back from the current version `N` to find the latest perspective sibling at or before `N`:

   1. If `<thread>.{N}.perspective/candidates.md` exists, use it.
   2. Else, walk back through `<thread>.{N-1}.perspective/`, `<thread>.{N-2}.perspective/`, …, `<thread>.0.perspective/` and use the highest `M ≤ N` whose `candidates.md` exists.
   3. If none exist, perspective cross-check is skipped (graceful — no error, no finding).

   This mirrors the standard sibling re-run pattern from `version_layout.md` — the latest perspective sibling at or before the current version is the canonical substrate; nothing aggregates across perspective re-runs.

   **New finding type — "unmatched competitor"**:

   - **Trigger**: a competitor name appears in `deck.md`'s competition slide(s) but appears in neither the brief's Competition section nor the perspective candidates (when present).
   - **Severity**: **warning** (not critical). The standing critical flag is **Fabricated competitive claims** in step 6 — that flag fires when the deck makes a substantive factual claim about a competitor (named customer wins, disclosed metrics, product specifics) that lacks brief or perspective attestation. The unmatched-competitor warning is the **evidentiary base** that makes the critical flag triggerable: when a name appears without any external substrate, the critic should examine the surrounding claim language and decide whether to escalate.
   - **Suggested fix**: either add the competitor to the brief / re-run `deck-perspective` to capture it, or remove the name from the deck if it was speculatively introduced.

   Example finding entry for `findings.md`:

   ```markdown
   ### [WARNING] Unmatched competitor: "Acme Robotics"

   - **Slide**: Slide 9 — Competition
   - **Rationale**: "Acme Robotics" appears in the competition 2x2 (lower-left
     quadrant: "legacy / on-prem") but does not appear in BRIEF.md's
     Competition section, and acme-seed.1.perspective/candidates.md does not
     list it among the named competitor candidates. The drafter may have
     introduced this name speculatively.
   - **Severity**: warning (evidentiary base — escalate to "Fabricated
     competitive claims" critical flag if the deck makes verifiable factual
     claims about Acme Robotics such as named customers or disclosed
     revenue).
   - **Suggested fix**: either (a) add "Acme Robotics" to the brief's
     Competition section with a source pointer and re-run deck-market, (b)
     re-run deck-perspective to capture the candidate, or (c) remove the
     name from the deck if it was speculative.
   ```
6. **Identify critical flags**:
   - **Market-math error**: as above (recomputation diverges >10% OR top-down-only sizing presented as defensible).
   - **Fabricated competitive claims**: if the deck names a customer of a competitor (e.g., "We won three accounts from Competitor X") and that claim isn't attested in the brief OR in the perspective sibling's `candidates.md` (when present), flag. An unmatched-competitor warning (from step 5's cross-check) accompanied by a verifiable factual claim about that competitor is the canonical trigger pattern; without perspective substrate, the brief is the only attestation source and the same logic applies. See "Cross-check against perspective candidates" in step 5 for the substrate-discovery rule.
7. **Write `tam-recompute.md`** (optional but recommended):
   ```markdown
   # TAM/SAM/SOM independent recomputation

   ## Deck's claim (Slide 7)

   - TAM: $20B (claimed)
   - SAM: $5B (claimed)
   - SOM: $50M Year-3 (claimed)

   ## Critic's recomputation from cited inputs

   Inputs cited:
   - 250,000 US mid-market plants (source: NAM 2024 census, cited)
   - Average annual contract value: $80k (source: brief, founder estimate from current customer cohort)

   TAM = 250,000 × $80,000 = **$20.0B** ✓ matches deck

   SAM (cited as "addressable segment with budget for automation"):
   - Deck claim: $5B (= 25% of TAM)
   - 25% multiplier is unsourced — flag as a minor finding
   - Arithmetic: 250,000 × 25% × $80,000 = $5.0B ✓ arithmetic correct

   SOM (Year-3 capture):
   - Deck claim: $50M (= 1% of SAM)
   - 1% Year-3 capture is plausible for a seed-stage company with current 8 paying customers
   - At $80k ACV, $50M SOM ≈ 625 customers in Year 3 (from 8 today → 78x growth in 3 years)
   - Plausible but aggressive; recommend speaker-note framing as "capture target" not "projection"

   ## Verdict

   Math checks out within rounding. SAM multiplier (25%) needs sourcing — minor finding. SOM growth implied is aggressive — minor finding (not a critical flag, since the number itself is internally consistent).
   ```
8. **Write `_summary.md`**:
   ```markdown
   # Market critic summary

   ```json
   {
     "critic": "market",
     "for_version": <N>,
     "dimensions": {
       "1_narrative_arc":            null,
       "2_problem_clarity":          null,
       "3_market_size_credibility":  { "score": 4, "weight": 5 },
       "4_solution_differentiation": { "score": 3, "weight": 5 },
       "5_traction_proof":           null,
       "6_team_credibility":         null,
       "7_ask_specificity":          null,
       "8_design_polish":            null,
       "9_rhetorical_economy":       null
     },
     "critical_flag": false,
     "critical_flag_notes": []
   }
   ```
   ```
9. **Write `findings.md`** and **`comments.md`** in the standard severity/slide-ref format.
10. **Update `_progress.json`** and `_meta.json` inside the staging dir. The `_progress.json` write MUST be the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires it to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies every name in the required-files manifest exists in the staging dir, then atomically renames `.<thread>.{N}.market.tmp/` → `<thread>.{N}.market/`. The final-named dir only ever exists in **complete** form.
11. **Report**: one-line status (e.g., `Market critic on acme-seed.1 → acme-seed.1.market/ (dims 3+4: 7/10; 4 findings, 0 critical flags; TAM recomputation matches within rounding)`).

## Idempotence and resumability

Standard.

## Notes for the market-critic agent

- **Always recompute, never trust.** If the deck says "$20B TAM" do the multiplication yourself from the cited inputs. A math error in front of a sophisticated investor is a deal-killer.
- **Top-down is a flag, not a discussion.** "$300B market × 1%" is the most common form of pitch-deck market sizing, and it is the form most investors discount to zero. Score it accordingly.
- **Generic competitor framing is a credit-reducer.** "We're faster than legacy players" tells the investor nothing. "We're 10x cheaper than UiPath and 3x faster than Workato because our orchestrator is event-driven not poll-based" is specific.
- **Cross-check named competitors against the brief AND the perspective sibling.** If the deck names a competitor that appears in neither the brief nor the perspective sibling's `candidates.md` (when present), that competitor may have been invented — surface as the "unmatched competitor" warning (severity: warning, NOT critical by default). The Fabricated competitive claims **critical** flag fires only when the deck also makes a substantive factual claim (named customer win, disclosed metric, product specifics) about an unmatched competitor. The unmatched-competitor warning is the evidentiary base; the critical flag is the escalation. Perspective is gracefully absent on threads that have never run `deck-perspective` — fall back to brief-only cross-check in that case (no error, no finding about the absence).
- **Don't critique narrative, problem, traction, team, ask, or design here.** Other critics own those.


**Scorecard kind declaration**: This critic's `_meta.json` SHOULD include `"scorecard_kind": "machine-summary"` per `anvil/lib/snippets/scorecard_kind.md`. This is a deck specialist critic — `machine-summary` shape (`_summary.md` + `findings.md`), partial scorecard with non-owned dimensions set to `null`. The deck-review aggregator reads this sibling's `_summary.md` and combines its scores into the composite verdict.
