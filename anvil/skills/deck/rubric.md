# Deck review rubric

Pitch decks are scored against 9 weighted dimensions summing to **44**. The threshold to advance is **≥39/44** — decks are customer-facing artifacts (the founder's pitch to external capital), held to the same standard as legal artifacts per `lib/README.md`'s convergence rule. The threshold is the proportional bump from the pre-#357 ≥35/40 (≈ 35×44/40 = 38.5, rounded). Any **critical flag** short-circuits the verdict — the deck is blocked regardless of total score until the flagged issue is addressed.

The rubric is tuned for the way investors actually read decks: **narrative coherence + ask specificity + market credibility dominate (16/44 ≈ 36.4%)**. A deck of strong individual slides without an arc fails. A deck with a clear arc but no specific ask fails. A deck with a credible problem and team but a fabricated market number fails on the critical flag regardless of total. The dim 9 *Rhetorical economy* addition (weight 4) provides explicit countervailing pressure against bloat — decks lose to bloat hardest of any skill (a 30-slide deck is fatal); dim 9 catches the failure mode where every other dim rewards adding more.

## Dimensions

| # | Dimension | Weight | What it measures | Owned by critic |
|---|---|---|---|---|
| 1 | **Narrative arc** | 6 | The deck reads as a single argument from problem → solution → why-now → why-us → ask. Slides flow; the order is the argument; the closing ask follows from the setup. A deck of strong individual slides with no arc fails this dimension hardest. **Highest weight.** | `deck-narrative` |
| 2 | **Problem clarity** | 5 | An investor reading the problem slide cold understands the problem in <30 seconds and why it is worth solving now. Vague problems ("workflows are inefficient"), self-evident problems ("people want better X"), or problems explained only via solution are the #1 deck-killer. | `deck-review` |
| 3 | **Market size credibility** | 5 | TAM/SAM/SOM with defensible bottom-up logic. Top-down framing ("$XB market × 1% = $XM") is a near-automatic disqualifier at most funds and scores low here. Comparables and competitor sizing as anchors are credit. Math must check out — see critical flags. | `deck-market` |
| 4 | **Solution differentiation** | 5 | What is uniquely yours; why competitors / incumbents can't or won't follow. Explicit moat language (network effects, switching costs, regulatory, technology lead, distribution). "Faster / cheaper / better" without mechanism scores low. Named competitors are cross-checked against the brief AND, if present, the perspective sibling's `candidates.md` (per `anvil/lib/snippets/perspective.md`); names appearing in neither surface as the **"unmatched competitor" warning** (severity: warning — the evidentiary base for the **Fabricated competitive claims** critical flag in `deck-market`). | `deck-market` |
| 5 | **Traction / proof** | 5 | Whatever evidence the stage permits: revenue (with growth rate), users (with retention), LOIs (with names), pilots (with conversion path), technical milestones (with verifiable outputs), design partners (named). Honest framing of what is real vs. projected. Hockey-stick projections without a current point on the curve score 0. | `deck-review` |
| 6 | **Team credibility** | 4 | Founder–market fit, prior outcomes, key hires, advisors who actually advise. Stage-dependent emphasis: seed → team-heavy; growth → traction-heavy. Generic credentials ("ex-FAANG") without a thesis-relevant connection score low. | `deck-review` |
| 7 | **Ask specificity** | 5 | Round size, optionally valuation expectation, use of funds breakdown, milestones the raise unlocks, runway months. "Raising $X to do Y by Z" — no hand-waving. An absent or vague ask is a critical flag. | `deck-narrative` |
| 8 | **Design polish** | 5 | Visual hierarchy, slide density (≤6 bullets and ≤30 words per content slide is the working bar), chart legibility at projection scale, consistent typography/palette, no chartjunk, no walls of text. Decks are seen, not read — design is content. Critique runs against the **rendered PDF**, not the markdown source. | `deck-design` |
| 9 | **Rhetorical economy** | 4 | Could a busy investor extract the ask in 90 seconds? Are slides 18+ load-bearing? Could the same arc reach the ask in fewer slides? Decks lose to bloat hardest of any skill — a 30-slide deck is fatal. Owned by `deck-narrative` (which owns the arc/ask pair); the arc critic's natural turf. | `deck-narrative` |
| | **Total** | **44** | Advance threshold: **≥39** | |

**Weight rationale**:
- Narrative + ask + market = **16/44 ≈ 36.4%**. A pitch deck is fundamentally a persuasive document with a request.
- Dim 9 *Rhetorical economy* (4/44) provides the explicit anti-bloat countervailing pressure — decks balloon under "more slides = more thorough" pressure, and a 30-slide deck is fatal regardless of per-slide quality.
- Differentiates from `pub` (rigor + evidence dominate; calibrated for academic credibility) and `memo` (clarity-of-recommendation dominates; calibrated for internal IC decision-making).

## Critic dimension ownership

Critics fill only the rubric dimensions they own. Other dimensions remain `null` in the critic's `_summary.md`. The reviser aggregates per-dimension as the **mean of non-null critic scores**.

| Critic | Owns dimensions | Notes |
|---|---|---|
| `deck-review` | 2, 5, 6 | General reviewer; can fill any dimension as a fallback if the specialist critic is skipped, but primary ownership is here. |
| `deck-narrative` | 1, 7, 9 | Arc + ask + rhetorical economy — read the deck end to end as a single argument. Dim 9 *Rhetorical economy* maps naturally to the arc/ask critic's turf: "could a busy investor extract the ask in 90 seconds?" is the same critic's question. |
| `deck-market` | 3, 4 | Market math + competitive differentiation — verify arithmetic, check framing. |
| `deck-design` | 8 (markdown-source density / hierarchy / consistency) | Visual quality — critique against the rendered PDF, not the source. |
| `deck-vision` | 8 (rendered-PDF density) + vision rubric v1–v6 | VLM critic over rendered PNGs; surfaces overflow, label cropping, axis legibility, palette adherence, mathtext artifacts, slide density. See `commands/deck-vision.md`. |

**Joint ownership of dim 8 (design polish)**: both `deck-design` and `deck-vision` contribute scores to dim 8 — `deck-design` evaluates source-side density and consistency signals (bullet counts, word density, mixed-typography heuristics), and `deck-vision` evaluates rendered-PDF density at projection scale (the VLM sees what the markdown source cannot expose, e.g. text that fits in the markdown but spills past the 16:9 safe area after Marp lays it out). The aggregator (`anvil/lib/critics.py::aggregate`) handles this cleanly via mean-of-non-null: when both critics score dim 8, the aggregated dim-8 score is the arithmetic mean of their two integer scores (rounded with banker's rounding). When only one critic runs, that critic's score stands alone. The two critics also contribute disjoint findings — `deck-design` flags source-side issues; `deck-vision` flags rendered-only defects.

In addition to dim 8, `deck-vision` owns six **vision-rubric dimensions** scored /5 each (vertical_overflow, label_cropping, axis_legibility, palette_adherence, mathtext_artifacts, slide_density). These six dims appear in the aggregated scorecard alongside the 8 main-rubric dimensions; the existing aggregator merges them via the same mean-of-non-null path with no schema or aggregation changes. See `anvil/lib/vision.py` and `commands/deck-vision.md` for the rubric definition.

If a critic sibling is missing at version `N` (e.g., operator skipped `design`), the reviser leaves that dimension's aggregate as `null` in `verdict.md` and notes the gap. A deck cannot reach `READY` with any main-rubric dimension still `null` — at minimum, the general `deck-review` must fill any dimensions no specialist owns. Vision-rubric dimensions (v1–v6) are gated separately: a deck without a `deck-vision` pass is not yet validated against rendered-only defects, and the reviser surfaces this as a gap in `_revision-log.md`.

## Perspective substrate (dims 3, 4)

Per `anvil/lib/snippets/rubric.md` §"Rubric–perspective interaction", a
perspective sibling (`<thread>.0.perspective/` or the latest
`<thread>.{N}.perspective/`) is **opportunistic substrate** for dims
3 (Market size credibility) and 4 (Solution differentiation): when
present and cited, scores at the **top of the calibrated range** become
defensibly reachable; when absent, **no new deduction is taken** —
the dimensions score against the legacy baseline.

The rule applies to two market-credibility-shaped failure modes the
canary surfaces:

- **Market size credibility (dim 3)** — bottom-up TAM/SAM/SOM logic
  becomes **harder to score at 4/5 or full weight without** a
  perspective sibling. A market-size claim that cites a perspective
  candidate (a vendor sizing report, a comparable company's last
  funding round, a regulator's published market data, a published
  analyst note) is treated as **substrate-backed** by `deck-market` —
  the candidate's `Source:` field is the inline-hook-equivalent for
  the sizing claim, and the dimension scores higher than it would for
  the same claim made without the source pointer. Conversely, a deck
  WITHOUT a perspective sibling that lands a credible bottom-up sizing
  case on the strength of brief + prior knowledge alone is NOT
  penalised — it scores against the pre-perspective baseline. Top-down
  framing remains a near-automatic disqualifier regardless of
  perspective presence (see the dimension definition).
- **Solution differentiation (dim 4)** — competitive-positioning
  claims (named competitors, moat language, "why they can't follow")
  become **easier to score higher** when the perspective sibling
  carries competitor candidates that the deck's differentiation
  language matches against. A named competitor that appears in
  `candidates.md` (with a source pointer to the competitor's product
  page, pricing page, customer case study, or public benchmark) is the
  substrate base `deck-market` reads to validate the differentiation
  framing. This is the **positive-evidence side** of the existing
  "unmatched competitor" warning documented in the dim 4 cell above:
  matched competitors score the dimension up; unmatched competitors
  fire the existing warning (no scoring change to this rule).

Per the framework contract, the rule is **opportunistic, not
punitive**:

- **With perspective + cited candidates**: dims 3 and 4 may score
  **higher** than the legacy baseline. The reviewer / critic SHOULD
  note in the justification that the higher score reflects
  substrate-backed claims (e.g., "Dim 3 = 5/5: sizing cites
  `candidates.md#mckinsey-fiber-2024` with bottom-up build-up;
  substrate-backed per perspective sibling").
- **Without perspective** (legacy threads): dims 3 and 4 score against
  the pre-perspective baseline. No new deduction is applied. Top-down
  TAM still scores low; unmatched competitors still fire the existing
  warning. The rubric is silent on perspective absence.
- **With perspective + a "known gap"**: when the perspective sibling's
  `notes.md` "Identified gaps" names a substrate area as un-covered
  AND `deck.md` makes a load-bearing claim about that area without
  hooking it (no candidate citation, no brief-attested data), the
  existing dim 3 / dim 4 weaknesses (top-down sizing without bottom-up
  validation, unhooked differentiation language) are applied to a
  more-clearly-established miss — the perspective sibling sharpens the
  diagnosis rather than introducing a new deduction.

The cross-check is **specialist-owned**: `deck-market` owns both
dim 3 and dim 4 per the dimension table above, so the perspective
interaction lives in that critic's hot path (see
`commands/deck-market.md` for the per-candidate validation steps).
`deck-review` is the fallback when `deck-market` is skipped.

**Backward compatibility.** Threads without a perspective sibling
(legacy decks; threads run with the pre-#149 deck skill) score dims 3
and 4 identically to the pre-perspective behaviour. The perspective
interaction is non-gating per `anvil/lib/snippets/perspective.md`; no
review can fail on perspective absence alone.

## Refs back-check (dims 5, 6)

`<thread>/refs/` is **also** the home for **author-supplied source-of-truth materials** (CV, founder bio, public filings, papers, transcripts, LOIs, customer quotes, images) — see SKILL.md §"Source-of-truth materials". When such materials are present, dim 5 (Traction / proof) and dim 6 (Team credibility) MUST each score a **per-instance refs back-check** in addition to the existing BRIEF cross-check the dimensions already run.

The back-check is **review-owned** (both dims live in `deck-review`'s ownership block per the dimension table above) and is **additive**: the brief precedence rule from SKILL.md §"Source-of-truth materials" is unchanged — only brief-attested claims may appear on a slide, but the reviewer back-checks brief-attested claims against the underlying `refs/` source-of-truth document when one is present.

The reviewer partitions `<thread>/refs/` into source-of-truth materials (named for their content — `cv.pdf`, `cv.md`, `founder-bio.md`, `transcript-foo.md`, `filing-s1.pdf`, `loi-bigcorp.md`, `quote-acme.md`) and generic reference material (decks, transcripts not named as a source-of-truth, financial spreadsheets used only as drafter context) per the SKILL.md disambiguation rule. Generic reference material is out of scope for this sub-rule. For each source-of-truth refs-document **type** present that is on-topic for dim 5 (traction-bearing — LOIs, quotes, customer letters, traction-cited filings) or dim 6 (team-bearing — CVs, founder bios, prior-outcome filings), the reviewer picks at least one load-bearing claim in `deck.md` whose evidentiary basis is the document's subject and back-checks it. The reviewer is **not** required to back-check every claim — the requirement is **at least one claim per source-of-truth refs-document type present**.

The reviewer records each back-check in `comments.md` with a four-valued verdict (`VERIFIED` / `UNVERIFIED` / `CONTRADICTED` / `NOT-IN-REFS`) and applies a **per-instance deduction** on the bound dim (5 for traction claims, 6 for team claims):

- **One `CONTRADICTED` claim** against a source-of-truth ref — **two-point** deduction on the bound dim AND a **critical-flag candidate**, escalating to one of the existing standing flags:
  - Traction-bearing CONTRADICTED → existing **critical flag 1 (Fabricated traction)** — the underlying source-of-truth document shows the traction figure is not what the slide says.
  - Team-bearing CONTRADICTED → existing **critical flag 2 (Fabricated team credentials)** — the underlying source-of-truth document shows the bio claim is not what the slide says.
  No new flag is needed; the existing flags 1 and 2 are the natural escalation path. The contradiction is the canary failure mode the contract exists to catch: a factual error in a load-bearing traction or bio claim (the Bessemer 15+ years founder bio error from issue #166's body) that propagates through versions because no reviewer back-checked against the underlying source.
- **One `UNVERIFIED` claim** against a source-of-truth ref (document is present and on-topic but does not contain the supporting passage) — **one-point** deduction on the bound dim. Not flag-eligible on its own; the gap is signaled but not deal-breaking.
- **`NOT-IN-REFS` claims** (deck makes a claim, no source-of-truth refs-document covers its subject) — **no deduction**. Informational only; records "where did this come from" visibility for the reviser.
- **`VERIFIED` claims** — no deduction; positively scored under the dim's full-weight calibration.

The dim 5 / dim 6 justification MUST cite the specific verdict and the refs-document path (e.g., "Back-checked Slide 10 'Founder: 15+ years at Bessemer Trust' against `refs/cv.pdf`: CONTRADICTED ('Bessemer Trust 2018-2023') — -2 on dim 6 + critical flag 2 (Fabricated team credentials)"). Vague "needs refs back-check" deductions without named instances are not actionable for the reviser and SHOULD be avoided.

**Backward compatibility.** When `<thread>/refs/` contains **no** source-of-truth materials (only generic reference material, or empty, or missing), this sub-rule is **inactive** and dims 5 / 6 fall back to BRIEF-only cross-check (the pre-#166 behavior). A deck thread that uses `refs/` only as drafter context (transcripts, prior decks the brief did not name as a source-of-truth) is unaffected. PDFs and images are treated as presence-only in v0 — the reviewer notes the file is on-disk and back-checks against a sibling `.md` companion (e.g., a `cv.md` next to `cv.pdf`) or `BRIEF.md`-surfaced content; PDF text extraction is deferred to issue #167.

The deduction is applied entirely via reviewer judgment — there is no automated `refs/` parsing in v0. See `commands/deck-review.md` §Procedure step 6 (dim 5 / dim 6 refs back-check sub-step) for the reviewer-side procedure and `commands/deck-draft.md` §Procedure step 5 for the drafter-side ingestion contract.

## Per-thread rubric overrides (calibrations + waivers)

A deck thread MAY carry a `rubric_overrides:` block on its matching `documents:` entry in the **project-level** `BRIEF.md` (the parent of the thread root, post-#382 nested model), parsed by `anvil/lib/project_brief.py::load_rubric_overrides_for_slug(<project_dir>, <slug>)`. Two key families apply to decks (issue #393, mirroring the memo #233 / #265 / #296 contract):

```yaml
# project BRIEF.md, documents: entry for the deck slug
- slug: series-a-deck
  artifact_type: deck
  rubric_overrides:
    dim_5_calibration: "pre-revenue pilot-stage deck — score traction on pilot conversion evidence, not revenue"
    dim_6_waiver: "Operator directive 2026-06-09: no team content in this deck; team story lives in team-thesis.latest."
```

**Calibration (`dim_N_calibration`)** — per-dimension scoring guidance. The value is prose the reviewer appends **verbatim** as a suffix to that dimension's `scoring.md` justification (`"calibration applied: <verbatim override text>"`, via `anvil/lib/rubric_overrides_suffix.py::apply_calibration_to_justification`). Calibrations tune HOW a dimension is judged; they do not change weights or the threshold.

**Waiver (`dim_N_waiver`)** — operator-directed dimension exclusion, **rationale-as-value**: the YAML value IS the mandatory rationale. Semantics (paired-rationale discipline, same as the iteration-cap override precedent in `SKILL.md` §"Per-thread override contract"):

- A waived dimension is removed from **both the numerator and the denominator** of the verdict. The advance threshold normalizes proportionally: `normalized_threshold = 39 × (44 − waived_weight) / 44`, compared as an **exact fraction** (no rounding). Example: dim 6 (weight 4) waived → remaining pool /40, threshold `39 × 40/44 = 390/11 ≈ 35.45` — a 36/40 deck advances; a 35/40 deck does not. Mechanical helpers: `normalized_advance_threshold` / `meets_normalized_threshold` in `anvil/lib/rubric_overrides_suffix.py`.
- A waiver **REQUIRES a non-empty rationale**; an unjustified waiver (missing / empty / whitespace-only value) is rejected at parse time. A dimension that is both waived and calibrated is rejected at parse time as contradictory (the error names both keys).
- The waiver is surfaced **verbatim** in the aggregated `verdict.md` (`## Waived dimensions` section + the normalized judgment stated explicitly in the header) and in the `_summary.md.rubric_overrides` audit block, so an investor-send reviewer sees what was excluded and why.
- **Critical flags are NOT waivable.** A waiver removes scoring weight only. If waived-dimension content appears on a slide anyway, the flag machinery applies in full — a dim-6 waiver does not suppress `Fabricated team credentials`.
- **`_meta.json` stamping stays nominal** (issue #346): reviews under a waiver still stamp `rubric_id: "anvil-deck-v2"`, `rubric_total: 44`, `advance_threshold: 39` — the stamp records the rubric version; waiver math happens at verdict time and is recorded in `_summary.md` / `verdict.md`.
- **Decks without `rubric_overrides` behave byte-identically** to pre-#393: no suffixes, nominal `≥39/44` verdict.

In v0 only the aggregator (`deck-review`) loads and applies overrides; specialist critics (`deck-narrative`, `deck-market`, `deck-design`, `deck-vision`) defer per the PR #363 split-init precedent. The aggregated `verdict.md` — the only verdict.md author — is the surfacing point. See `commands/deck-review.md` steps 5e, 8, 9, 12, and 13.

## Scoring guidance

For each dimension, the critic assigns an integer between 0 and the dimension's weight. A short justification accompanies each score (1–3 sentences pointing to specific slides or evidence in the deck).

Suggested calibration:
- **Full weight** — meets the standard convincingly; a sophisticated investor would have no substantive objection on this dimension.
- **~75% of weight** — meets the standard with a defensible gap or one specific weakness noted.
- **~50% of weight** — partial; multiple gaps or one significant weakness.
- **~25% of weight** — present but inadequate; major rework needed.
- **0** — absent or actively misleading.

## Advance threshold

- **≥39/44** — advance to `READY` (or to next step in the lifecycle).
- **<39/44** — block; revise.
- **Any critical flag set** — block regardless of total. The next revision must address the flagged issue specifically and the relevant critic(s) must re-evaluate the flag before the threshold check applies.

## Critical flags

A critical flag is an issue severe enough that **a sophisticated investor would immediately disqualify the deck**, regardless of how well other dimensions score. The four standing critical flags for pitch decks are:

1. **Fabricated traction.** A traction number (revenue, ARR, users, retention, LOIs, pilots, design partners, customer logos) that does not appear in the brief or refs. This is the most credibility-destroying error a deck can contain: an investor who diligences and discovers a number was made up will not take a follow-up meeting. Raised by `deck-audit`, `deck-market`, or `deck-review`.
2. **Fabricated team credentials.** A bio claim (prior role, prior exit, degree, advisory board affiliation, named hire) that does not appear in the brief or refs. Same disqualification dynamic as fabricated traction. Raised by `deck-audit` or `deck-review`.
3. **Market-math error.** TAM/SAM/SOM arithmetic that does not check out (multiplication wrong, units inconsistent, double-counted segments), OR top-down-only sizing presented as defensible without bottom-up validation. Raised by `deck-market` or `deck-audit`.
4. **Absent ask.** No specific round size, OR no use-of-funds breakdown, OR no runway-to-milestone framing. A deck without a clear ask is a deck that gives the investor permission to say "interesting, keep me posted." Raised by `deck-narrative` or `deck-review`.

The critic should also raise a flag for any other issue that, in its judgment, meets the standard above — the four examples above are starting points, not a closed set. The aggregated critical flag in the reviser's `verdict.md` is the **logical OR** of all critic critical flags.

**Fabricated competitive claims** is a critic-discretion critical flag raised by `deck-market` (see `commands/deck-market.md` step 6) when the deck makes a substantive factual claim (named customer wins, disclosed metrics, product specifics) about a competitor that lacks attestation in the brief OR in the perspective sibling's `candidates.md`. Its evidentiary base is the **"unmatched competitor" warning** (severity: warning, not critical on its own), which fires whenever a named competitor appears in `deck.md` but in neither the brief's Competition section nor (when present) the perspective candidates. The warning alone is a credit-reducer on dim 4 (Solution differentiation); escalation to the critical flag depends on whether the deck attaches a verifiable factual claim to the unmatched competitor. Perspective siblings are non-gating per `anvil/lib/snippets/perspective.md` — on threads without a perspective sibling, the cross-check falls back to brief-only (no error, no finding about the absence).

## Verdict format

The reviser (consuming all critic siblings at `<thread>.{N}/`) writes an aggregated `verdict.md` at the top of the next version's revision plan (or the general reviewer writes a per-critic verdict in `.review/`). The format:

1. **Total score**: `XX / 44` (mean-aggregated per dimension across non-null critic scores).
2. **Decision**: `advance: true` or `advance: false`. (`advance: true` requires both `total ≥ 39` AND `no unresolved critical flag from any critic`.)
3. **Critical flags** (if any): bullet list, each with one-paragraph justification and the critic that raised it.
4. **Dimension summary**: a markdown table of per-dimension aggregate scores, the critics contributing each, and any null dimensions.
5. **Top 3 revision priorities** (if `advance: false`): the highest-leverage changes for the reviser to focus on.

## Output layout (per critic sibling)

```
<thread>.{N}.<tag>/
  verdict.md       (deck-review only — full reviewer verdict; specialist critics emit _summary.md instead)
  scoring.md       Per-dimension score + justification for owned dimensions
  comments.md      Slide-level comments keyed to deck.md slides (by slide number and heading)
  _summary.md      8-dim partial scorecard (owned dims scored, others null) + critical flag bool
  findings.md      Itemized findings: severity, slide ref, rationale, suggested fix
  _meta.json       { critic, role, started, finished, model }
  _progress.json   Phase state for this critic
```

For `deck-design` only:
```
<thread>.{N}.design/
  slides/          Per-slide PNGs rendered from deck.pdf (the artifact this critic actually evaluates)
  ... (all of the above)
```

The critic dir is **read-only once written** (state: `done` in its own `_progress.json`). Revisions consume it without modifying it.
