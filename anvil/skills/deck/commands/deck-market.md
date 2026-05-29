---
name: deck-market
description: Market/TAM-credibility critic for the deck skill. Verifies TAM/SAM/SOM arithmetic, evaluates competitive framing, and scores rubric dims 3 (market size credibility) and 4 (solution differentiation).
---

# deck-market — Market / competitor critic

**Role**: market and competitor critic.
**Reads**: latest `<thread>.{N}/deck.md` (market and competition slides + any supporting figures and `figures/src/*.csv`); `<thread>/BRIEF.md`.
**Writes**: `<thread>.{N}.market/` with `_summary.md`, `findings.md`, `comments.md`, `_meta.json`, `_progress.json`.

This critic verifies the market case the deck makes. It computes TAM/SAM/SOM arithmetic, checks bottom-up vs top-down framing, and evaluates competitor positioning. Market-math errors and top-down-only sizing are high-frequency disqualifiers at investor diligence; this critic catches them before send.

## Owned rubric dimensions

- **3 — Market size credibility** (weight 5)
- **4 — Solution differentiation** (weight 5)

Total ownership: 10/40. Other dimensions are scored by other critics and remain `null` in this critic's `_summary.md`.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md`.
- **Brief**: `<thread>/BRIEF.md` (sections "Market" and "Competition" specifically; other sections for grounding).
- **Source data**: `<thread>.{N}/figures/src/*.csv` (if market sizing uses a chart, the source data lives here).
- **Optional override**: `.anvil/skills/deck/rubric.overrides.md`.

## Outputs

```
<thread>.{N}.market/
  _summary.md       8-dim partial scorecard (dims 3 + 4 scored; others null) + critical-flag bool
  findings.md       Itemized findings (severity, slide ref, rationale, suggested fix)
  comments.md       Slide-level commentary (market slide, competition slide)
  tam-recompute.md  (Optional) Independent recomputation of TAM/SAM/SOM showing the critic's working
  _meta.json
  _progress.json
```

## Procedure

1. **Discover state** + **resume check** (standard).
2. **Initialize `_progress.json`** + `_meta.json`.
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
   - **Cross-check against brief**: every named competitor on the slide should appear in the brief's competition section. Competitors named only on the slide → flag (drafter may have invented them).
6. **Identify critical flags**:
   - **Market-math error**: as above (recomputation diverges >10% OR top-down-only sizing presented as defensible).
   - **Fabricated competitive claims**: if the deck names a customer of a competitor (e.g., "We won three accounts from Competitor X") and that claim isn't attested in the brief, flag.
7. **Write `tam-recompute.md`** (optional but recommended):
   ```markdown
   # TAM/SAM/SOM independent recomputation

   ## Deck's claim (Slide 6)

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
       "8_design_polish":            null
     },
     "critical_flag": false,
     "critical_flag_notes": []
   }
   ```
   ```
9. **Write `findings.md`** and **`comments.md`** in the standard severity/slide-ref format.
10. **Update `_progress.json`** and `_meta.json`.
11. **Report**: one-line status (e.g., `Market critic on acme-seed.1 → acme-seed.1.market/ (dims 3+4: 7/10; 4 findings, 0 critical flags; TAM recomputation matches within rounding)`).

## Idempotence and resumability

Standard.

## Notes for the market-critic agent

- **Always recompute, never trust.** If the deck says "$20B TAM" do the multiplication yourself from the cited inputs. A math error in front of a sophisticated investor is a deal-killer.
- **Top-down is a flag, not a discussion.** "$300B market × 1%" is the most common form of pitch-deck market sizing, and it is the form most investors discount to zero. Score it accordingly.
- **Generic competitor framing is a credit-reducer.** "We're faster than legacy players" tells the investor nothing. "We're 10x cheaper than UiPath and 3x faster than Workato because our orchestrator is event-driven not poll-based" is specific.
- **Cross-check named competitors against the brief.** If the deck names a competitor not in the brief, that competitor may have been invented — surface as a finding.
- **Don't critique narrative, problem, traction, team, ask, or design here.** Other critics own those.
