---
name: deck-audit
description: Fact / number / citation auditor for the deck skill. Verifies every cited statistic, customer name, partner logo, and team credential traces to the brief or refs. Critical-flag eligible.
---

# deck-audit — Fact / citation auditor

**Role**: auditor.
**Reads**: latest `<thread>.{N}/` (specifically `deck.md`, `speaker-notes.md`, `figures/src/*.csv`), `<thread>/BRIEF.md`, `<thread>/refs/**`.
**Writes**: `<thread>.{N}.audit/` with `_summary.md`, `findings.md`, `audit-trail.md` (line-by-line evidence), `_meta.json`, `_progress.json`.

This auditor is sharper than the generic `audit` critic on other skills (e.g., `memo`): it specifically enforces the deck no-fabrication contract. A deck that ships to investors with a single unattested customer logo is a deck that loses the firm's credibility on first reference-check.

## Owned rubric dimensions

The auditor does **not own any rubric dimension directly** — it does not score the deck on a 0–5 scale. Its job is to verify factual accuracy and raise critical flags. Its `_summary.md` shows all dimensions as `null` but the `critical_flag` field is the audit's primary output.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md` (usually a version where `verdict.md` has `advance: true`; audit is typically run as the final pre-send gate).
- **Brief**: `<thread>/BRIEF.md` — canonical source of truth for traction numbers, team bios, assets.
- **Refs**: `<thread>/refs/**` — secondary sources the brief itself was derived from. Audit can drill through to refs when the brief cites them.

## Outputs

```
<thread>.{N}.audit/
  _summary.md       All dims null; critical_flag bool is the primary output
  findings.md       Itemized findings: severity, slide ref, claim quoted, attestation status
  audit-trail.md    Line-by-line evidence: every numeric/named claim on every slide, with its attestation source
  _meta.json
  _progress.json
```

## Procedure

1. **Discover state** + **resume check** (standard).
2. **Initialize `_progress.json`** + `_meta.json`.
3. **Enumerate claims**: walk every slide in `<thread>.{N}/deck.md` and extract:
   - **Numbers**: every number that appears in body text or in a chart (read from `figures/src/*.csv` if a chart is data-driven).
   - **Names**: every named person, company (competitor, customer, partner, investor), product, or institution.
   - **Logos / images**: every referenced asset (`![...](assets/...)` or `![...](figures/...)`).
   - **Quoted statements**: any quoted endorsement or claim attributed to a third party.
4. **Attest each claim**:
   - For each number: find it in `BRIEF.md`. If present → attested. If absent → drill to `refs/` and check whether brief should have included it. If absent from both → **`Fabricated traction` critical flag** (if traction-related), OR `[blocker]` finding (if non-traction numeric).
   - For each name: find it in `BRIEF.md` (team, competition, traction sections, prior raises). If absent → **`Fabricated team credentials` critical flag** (for bio claims) or **`Fabricated traction` critical flag** (for customer / partner logos).
   - For each logo / image: confirm the file exists in `<thread>/assets/` AND is listed in the brief's "Assets available" inventory. Missing from inventory → critical flag.
   - For each quoted statement: confirm it appears in a ref file or in the brief. Unattested quotes → `[blocker]` finding (potentially a fabrication flag depending on context).
5. **Cross-check chart data**:
   - For each chart in `figures/`, find the source CSV in `figures/src/`. Run any matplotlib script (`figures/src/*.py`) on the CSV and confirm the rendered chart matches.
   - If chart shows numbers the CSV doesn't support → **flag as numeric fabrication**.
6. **Cross-check market arithmetic**:
   - Recompute TAM/SAM/SOM from cited inputs (redundant with `deck-market`, but auditor double-checks at READY).
   - If `deck-market` raised a market-math flag and it was supposedly addressed in the latest revision, verify the fix.
7. **Write `audit-trail.md`** — the line-by-line evidence file:
   ```markdown
   # Audit trail — acme-seed.2

   ## Slide 1 (Title)

   - "Acme Robotics" — attested in BRIEF.md frontmatter (company: "Acme Robotics") ✓
   - "Industrial automation for mid-market manufacturers" — paraphrase of BRIEF.md Solution section ✓
   - "Founder Name" — attested in BRIEF.md Team section ✓
   - Date "Series Seed · 2026-Q3" — attested in BRIEF.md frontmatter (target_close: "2026-Q3") ✓

   ## Slide 7 (Market)

   - "$5B SAM" — verified by independent recomputation: 250,000 plants × 28% addressable × $80,000 ACV = $5.6B (within rounding) ✓
   - "250,000 US plants" — BRIEF.md Market section cites NAM 2024 census; ref file `refs/nam-census-2024.pdf` page 47 confirms ✓
   - "$80,000 ACV" — BRIEF.md Traction section cites current customer cohort; ref `refs/cohort-summary.xlsx` confirms median ACV $78k (within rounding) ✓

   ## Slide 8 (Traction)

   - "$380k ARR" — BRIEF.md Traction section, confirmed ✓
   - "8 paying customers" — BRIEF.md Traction section, confirmed ✓
   - "Customer logo: Boeing" — **NOT FOUND** in BRIEF.md "Assets available" inventory; `assets/` does not contain `boeing-logo.png`. **Critical flag: Fabricated traction.**
   - "94% net retention" — BRIEF.md Traction section says retention "TBD pending cohort analysis". **NOT ATTESTED. Critical flag: Fabricated traction.**

   ## Slide 10 (Team)

   - "Founder Name — ex-VP Engineering, Boeing" — BRIEF.md Team section confirms ex-Boeing VP Engineering ✓
   - "Cofounder Name — ex-Founder of WidgetCo (acquired by Acme for $40M)" — BRIEF.md Team section confirms WidgetCo founding and acquisition; ref `refs/widgetco-press-release.pdf` confirms acquisition price $40M ✓
   - "Advisor: Famous Investor Name" — BRIEF.md mentions advisor name BUT brief notes "not yet public; founder pending permission". **Premature. Major finding.**

   ## Slide 12 (Ask)

   - "$3M round" — BRIEF.md Ask section confirms ✓
   - "45% engineering / 30% GTM / 15% hires / 10% reserve" — BRIEF.md Ask section confirms ✓
   - "18 months runway to $1.5M ARR" — BRIEF.md Ask section confirms ✓
   ```
8. **Write `findings.md`** summarizing critical / blocker / major / minor:
   ```
   ## Findings (audit)

   ### Critical flags

   1. **Fabricated traction** — Slide 8: "Customer logo: Boeing" appears on slide but Boeing is not in BRIEF.md Assets inventory and `assets/boeing-logo.png` does not exist. This is a credibility-destroying claim — Boeing reference-checks would expose immediately. Resolution: remove the logo OR add to brief Assets inventory only if founder confirms Boeing is a customer with logo permission.
   2. **Fabricated traction** — Slide 8: "94% net retention" appears on slide but BRIEF.md Traction section says retention is "TBD pending cohort analysis". Resolution: remove the number OR populate retention in brief from real cohort data before re-asserting.

   ### Major

   1. Slide 10: Advisor name listed publicly but brief notes "pending permission". Suggested fix: remove from slide until founder confirms permission, OR add note in speaker notes.

   ### Minor

   (none)
   ```
9. **Write `_summary.md`**:
   ```markdown
   # Audit summary

   ```json
   {
     "critic": "audit",
     "for_version": <N>,
     "dimensions": {
       "1_narrative_arc":            null,
       "2_problem_clarity":          null,
       "3_market_size_credibility":  null,
       "4_solution_differentiation": null,
       "5_traction_proof":           null,
       "6_team_credibility":         null,
       "7_ask_specificity":          null,
       "8_design_polish":            null
     },
     "critical_flag": true,
     "critical_flag_notes": [
       { "type": "fabricated_traction", "slide_ref": "Slide 8", "justification": "Boeing customer logo on slide; not in brief Assets inventory; asset file does not exist" },
       { "type": "fabricated_traction", "slide_ref": "Slide 8", "justification": "94% net retention asserted on slide; brief says TBD pending cohort analysis" }
     ]
   }
   ```
   ```
10. **Update `_progress.json`** and `_meta.json`.
11. **Report**: one-line status (e.g., `Audit on acme-seed.2 → acme-seed.2.audit/ (CRITICAL: 2 fabrication flags; 1 major; deck cannot ship until addressed)`).

## When to run

- **Recommended**: after the deck reaches `READY` (aggregated verdict `advance: true`), as a final pre-send gate. An audit at `READY` that raises critical flags forces another revise iteration — better caught here than by an investor.
- **Optional but useful**: at any iteration where the operator suspects fabrication risk (e.g., the drafter produced a slide with a number the operator doesn't recognize).
- **Always**: before sending to first external investor, for any commercial fundraise.

## Idempotence and resumability

Standard.

## Notes for the audit agent

- **Trust nothing, verify everything.** Even claims that "look right" must be traced to brief or refs.
- **The brief is the closed set of facts.** A claim attested only in a ref but not in the brief should be raised as a finding (drafter should not have used a ref-only fact without surfacing through brief).
- **Critical flags here block READY.** A `READY` verdict from the reviewer becomes `not READY` if audit raises a critical flag. The audit's critical-flag output trumps the aggregated review verdict.
- **Don't critique style, design, narrative, ask, or market structure.** Audit is purely factual. Other critics own those dimensions.
- **Do walk the chart data.** A chart that doesn't match its source CSV is the easiest fabrication to miss because it's "rendered". Diff the rendered chart against `python figures/src/<chart>.py` output.

**Scorecard kind declaration**: This critic's `_meta.json` SHOULD include `"scorecard_kind": "human-verdict"` per `anvil/lib/snippets/scorecard_kind.md`. deck-audit is an auditor critic — the audit findings are meant for human consumption (or for the reviser to address narratively), not for programmatic per-dimension aggregation.
