---
name: deck-narrative
description: Narrative-arc critic for the deck skill. Reads the deck end-to-end as a single argument and scores rubric dims 1 (narrative arc) and 7 (ask specificity).
---

# deck-narrative — Narrative-arc critic

**Role**: narrative-arc critic.
**Reads**: latest `<thread>.{N}/deck.md` (full read, in slide order) + `speaker-notes.md` + `<thread>/BRIEF.md`.
**Writes**: `<thread>.{N}.narrative/` with `_summary.md`, `findings.md`, `comments.md`, `_meta.json`, `_progress.json`.

This critic evaluates the deck as a **single story** rather than slide-by-slide. The other critics look at individual slides; this critic asks whether the slides cohere into an argument that ends in an ask.

## Owned rubric dimensions

- **1 — Narrative arc** (weight 6) — the deck flows from problem → solution → why-now → why-us → ask as a single argument.
- **7 — Ask specificity** (weight 5) — round size, use of funds, runway-to-milestone are concrete and follow from the setup.

Total ownership: 11/40 (the highest-leverage 11 points in the rubric).

Other rubric dimensions are scored by other critics and remain `null` in this critic's `_summary.md`.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md`.
- **Brief**: `<thread>/BRIEF.md` (to verify the deck's ask matches the brief's ask).
- **Optional rubric override**: `.anvil/skills/deck/rubric.overrides.md`.

## Outputs

```
<thread>.{N}.narrative/
  _summary.md       8-dim partial scorecard (dims 1 + 7 scored; others null) + critical-flag bool
  findings.md       Itemized findings (severity, slide ref or sequence ref, rationale, suggested fix)
  comments.md       Sequence-level commentary (transitions, missing bridges, slide-order issues)
  _meta.json        { "critic": "narrative", "role": "deck-narrative.md", ... }
  _progress.json    Phase state for this critic
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md`. If `<thread>.{N}.narrative/_progress.json.narrative.state == done` AND `_summary.md` parses, exit early (idempotent).
2. **Resume check**: delete partial output and re-run if a prior crash.
3. **Initialize `_progress.json`** and `_meta.json`.
4. **Read deck.md end-to-end** as one document. Read speaker-notes.md in parallel. Read BRIEF.md for the canonical ask.
5. **Evaluate narrative arc** (Dim 1, weight 6):
   - **Problem → Solution bridge**: Does the solution slide answer the problem slide? If the solution describes a different problem, score low.
   - **Solution → Why-now**: Why is now the right time? Is there a credible reason (technology unlock, regulatory change, behavior change)? "Why now" missing or weak = score ≤3.
   - **Why-now → Why-us**: Why is this team right for this moment? Is the founder–market fit explicit?
   - **Why-us → Traction/Proof**: Does the team's claim get backed by evidence? If team claims "we're the experts" but traction is thin, the arc breaks.
   - **Traction → Ask**: Does the ask follow from the setup? If the ask is "$3M to validate the problem" but the problem slide claimed product-market fit, the arc breaks.
   - **Slide order**: Are slides in an order that builds the argument? Out-of-order slides (e.g., team before problem) almost always score low.
   - **Slide count**: Target 10–15 for fundraising decks. Decks <8 slides usually feel thin; decks >18 usually feel padded. Flag deviation but don't auto-deduct — some stages legitimately need more (e.g., growth rounds with extensive financials).
6. **Evaluate ask specificity** (Dim 7, weight 5):
   - Round size present and specific? ("$3M", not "raising a round").
   - Use of funds broken down? (engineering / GTM / hires / runway, with rough percentages or dollar amounts).
   - Runway-to-milestone framing? ("$3M gets us to $5M ARR over 18 months", not just "$3M for 18 months runway").
   - Does the ask in deck.md match the ask in BRIEF.md? If not, flag — drafter or brief is out of sync.
   - **Critical flag — `Absent ask`**: trigger if any of round size / use of funds / runway-to-milestone is missing entirely, OR if the ask is so vague it gives the investor permission to say "interesting, keep me posted."
7. **Identify additional findings**:
   - Missing logical bridges between slides (specific examples).
   - Slides that don't earn their place (could be cut without weakening the argument).
   - Slides that should be added (e.g., missing competitive-positioning slide makes the differentiation claim float).
   - Speaker-notes that contradict slide content (a sign the drafter is hedging).
   - Stubs and TODOs left over from the draft (e.g., `[TODO: traction number from brief]`).
8. **Write `_summary.md`**:
   ```markdown
   # Narrative critic summary

   ```json
   {
     "critic": "narrative",
     "for_version": <N>,
     "dimensions": {
       "1_narrative_arc":            { "score": 5, "weight": 6 },
       "2_problem_clarity":          null,
       "3_market_size_credibility":  null,
       "4_solution_differentiation": null,
       "5_traction_proof":           null,
       "6_team_credibility":         null,
       "7_ask_specificity":          { "score": 4, "weight": 5 },
       "8_design_polish":            null
     },
     "critical_flag": false,
     "critical_flag_notes": []
   }
   ```
   ```
9. **Write `findings.md`**:
   ```
   ## Findings (narrative)

   1. **[major]** Slide 4 → 5: Why-now claim ("AI agents are mature enough") not connected to the product. Suggested fix: add a sentence to Slide 5 explicitly using AI-agent capability that wouldn't have existed 18 months ago.
   2. **[minor]** Slide 7 (Competition) sits awkwardly between Market and Traction. Suggested fix: move to after Solution (Slide 4) so differentiation is established before market sizing.
   3. **[major]** Slide 12 (Ask): "Raising $3M" but no breakdown. Suggested fix: add use-of-funds bullet (40% eng / 30% GTM / 20% hires / 10% runway) and runway-to-milestone framing.
   ```
10. **Write `comments.md`** (sequence-level, not slide-level):
    ```
    ## Slide order

    Current: Title → Problem → Solution → Why-now → Product → Market → Competition → Traction → Business model → Team → Financials → Ask. The Competition slide is out of place (recommended order: Title → Problem → Why-now → Solution → Competition → Product → Market → Traction → Business model → Team → Financials → Ask).

    ## Transitions

    - Slide 2 → 3 (Problem → Solution): strong; solution directly answers the problem stated.
    - Slide 4 → 5 (Why-now → Product): weak; the why-now claim doesn't manifest in the product description. See finding #1.
    - Slide 10 → 11 (Team → Financials): abrupt; consider a transitional sentence.

    ## Slide count

    12 slides (within target range 10–15). Slide 13 appendix optional and not included; recommend adding 1-2 appendix slides with detailed unit economics for follow-up Q&A.
    ```
11. **Update `_progress.json`** and `_meta.json` (finished: <ISO>).
12. **Report**: one-line status (e.g., `Narrative critic on acme-seed.1 → acme-seed.1.narrative/ (dims 1+7: 9/11; 3 findings)`).

## Idempotence and resumability

Standard: completed = no-op; crashed = re-runnable after deleting partial output.

## Notes for the narrative-critic agent

- **Read the deck linearly, in one pass, like an investor scrolling through a PDF for the first time.** Then read it again, slower. The first pass catches arc problems; the second catches detail.
- **An arc breaks when the conclusion doesn't follow.** "We're raising $3M to build the product" is fine for pre-seed but breaks the arc of a deck that claimed product-market fit on Slide 5.
- **Don't critique design, market math, problem clarity, traction, or team here.** Other critics own those dimensions. Stay in the arc + ask lane. (If you spot a fabrication issue in passing, flag it in `comments.md` as an aside — but score only owned dimensions.)
- **The ask is the test.** A deck that doesn't have a concrete ask isn't a pitch deck; it's a company overview. Score harshly when the ask is missing or vague.
