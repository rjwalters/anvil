# Memo review rubric

The reviewer scores a memo against 8 weighted dimensions summing to **40**. The threshold to advance is **≥32/40**. Any **critical flag** short-circuits the verdict — the memo is blocked regardless of total score until the flagged issue is addressed.

The rubric is tuned so that **intellectual honesty and reasoning quality (thesis + evidence + risk = 17/40 = 42.5%)** dominate the score. A memo's primary job is to make a defensible recommendation; prose polish is necessary but not sufficient.

## Dimensions

| # | Dimension | Weight | What it measures |
|---|---|---|---|
| 1 | **Recommendation clarity** | 5 | A single unambiguous recommendation (invest / pass / conditional) with stated check size or scope. A reader should extract the ask in one sentence. |
| 2 | **Thesis coherence** | 6 | A falsifiable thesis (what must be true for this to work). Supporting claims are logically chained, not just listed. |
| 3 | **Evidence quality** | 6 | Claims backed by primary sources, data, or named references. Numbers are sourced. Assertion is distinguished from research. |
| 4 | **Risk honesty** | 6 | Top 3–5 risks are named explicitly with mitigations or acknowledged residual exposure. Pro-forma risk sections that list only weak risks score low. |
| 5 | **Market & competitive framing** | 4 | TAM/SAM/SOM (or equivalent), competitive landscape, and a credible "why now" — sized to the artifact, not boilerplate. |
| 6 | **Financial reasoning** | 5 | Unit economics, capital efficiency, scenario math. Early-stage: clear sensitivity to key assumptions. Later-stage: defensible model. |
| 7 | **Scope discipline** | 4 | The memo stays within its declared scope (no scope creep into adjacent deals, no kitchen-sink appendices that dilute the argument). Length is within the declared `target_length` if set (default: reasonable for the decision being made). |
| 8 | **Prose & structure** | 4 | Navigable headings, tight prose, no jargon-without-definition, exhibits referenced from body. Lowest weight by design — substance over style. |
| | **Total** | **40** | Advance threshold: ≥32 |

## Scoring guidance

For each dimension, the reviewer assigns an integer between 0 and the dimension's weight. A short justification accompanies each score (1–3 sentences pointing to specific evidence in the memo).

Suggested calibration:
- **Full weight** — meets the standard convincingly; a sophisticated reader would have no substantive objection on this dimension.
- **~75% of weight** — meets the standard with a defensible gap or one specific weakness noted.
- **~50% of weight** — partial; multiple gaps or one significant weakness.
- **~25% of weight** — present but inadequate; major rework needed.
- **0** — absent or actively misleading.

## Citation hooks (dim 3)

Per the `memo-draft` *Evidence* contract, every **named author-year citation** and every **load-bearing quantitative claim** (dollar amounts, percentages, dates, multipliers anchoring an argument) should carry one of three hooks: (a) an inline footnote naming the source, (b) a `<thread>/refs/<key>.md` stub (which MAY be as minimal as `# TODO: source for <claim>`), or (c) an explicit in-prose hedge ("reportedly", "estimated", "roughly", "~"). The reviewer applies a **per-instance deduction** on dim 3 *Evidence quality* for unhooked load-bearing claims.

- **One or two missing hooks** — single-point deduction.
- **Pervasive absence** — multiple anchor numbers across multiple sections with no `refs/` stubs, footnotes, or in-prose hedges — two-point deduction.
- **Hedged estimates** ("Hoffman ~$5.4K, rough order") — NOT deducted. The hedge itself is the contract.

The dim 3 justification MUST cite the specific missing hooks (e.g., "Unsourced: 'Levenson et al., 2006', Hoffman price-anchor table, Apple PCC dates — no refs/ stubs, no footnotes, no hedge — -2"). Vague "needs more sources" deductions without named instances are not actionable for the reviser and SHOULD be avoided.

The deduction is applied entirely via reviewer judgment reading this prose against the memo — there is no automated `refs/` enforcement in v0. The contract exists to give both drafter and reviewer a shared, named standard to score against.

**Perspective sibling as substrate evidence.** When a `<thread>.0.perspective/` (or latest `<thread>.{N}.perspective/`) sibling exists, the reviewer treats its presence as **positive evidence that the drafter had verified external substrate available** when authoring the memo. Specifically: a load-bearing claim that cites a candidate from `candidates.md` (by anchor id, e.g., `#acme-series-a-2024`, or by the underlying `refs/<file>` pointer the candidate names) is treated as carrying an inline-footnote-equivalent hook — i.e., the citation-hook deduction does NOT apply to that claim. The perspective candidate's source pointer (URL, refs file, citation pointer) is the load-bearing artifact; the candidate's structured `Source:` field is the hook. Conversely, an unhooked load-bearing claim about a substrate area the perspective sibling's `notes.md` "Identified gaps" explicitly flagged as un-covered is a **stronger** signal of a real deduction — the drafter was told the substrate was missing and made the claim anyway. The reviewer also reads `_meta.json.search_params.stubs_filled` to identify which `refs/<key>.md` stubs the perspective role resolved (per `commands/memo-perspective.md` §"Side-effect: filling refs/ citation stubs"); a stub the perspective sibling filled is no longer a "needs hook" instance. Absence of a perspective sibling is the legacy case — the reviewer applies the citation-hook rule above unchanged (perspective is non-gating per `anvil/lib/snippets/perspective.md`, so no deduction is taken for its absence). See `commands/memo-perspective.md` for the substrate-gathering contract and `SKILL.md` §"State machine" for the optional-sibling framing.

## Perspective substrate (dim 3)

Per `anvil/lib/snippets/rubric.md` §"Rubric–perspective interaction",
the perspective sibling participates in dim 3 *Evidence quality*
scoring as **opportunistic substrate**, sibling to the §"Citation
hooks (dim 3)" and §"Refs back-check (dim 3)" sub-rules above and
below. This subsection codifies the perspective interaction as a
**named, first-class sub-rule** distinct from the citation-hook
extension paragraph in the §"Citation hooks (dim 3)" subsection
(which the perspective interaction is integrated into); the two
treatments are coherent and additive — this subsection states the
framework-anchored contract, the §"Citation hooks" paragraph encodes
the per-instance hook-equivalence rule.

The rule:

- **With perspective + cited candidates**: a load-bearing claim that
  cites a candidate from `candidates.md` (by anchor id or by the
  underlying `refs/<file>` pointer the candidate names) is treated as
  **substrate-backed**. The candidate's structured `Source:` field
  (URL, refs file path, citation pointer) is the
  inline-footnote-equivalent hook for the surrounding claim, so the
  §"Citation hooks (dim 3)" per-instance deduction does NOT apply to
  that claim, and the dimension may score at the **top of the
  calibrated range** (full weight or ~75%) on the evidence of
  substrate-grounded reasoning. The reviewer notes the substrate
  backing in the dim 3 justification (e.g., "Dim 3 = 6/6: financial
  thesis cites `candidates.md#hoffman-2024-press-release` with bottom-
  up unit-economics build-up; substrate-backed per perspective
  sibling").
- **Without perspective** (legacy memo threads): dim 3 scores against
  the legacy baseline alone — §"Citation hooks (dim 3)" and §"Refs
  back-check (dim 3)" apply unchanged. **No new deduction** is taken
  for perspective absence. A memo authored before the perspective
  primitive landed continues to score on the pre-perspective rules.
- **With perspective + a "known gap"**: when the perspective sibling's
  `notes.md` "Identified gaps" names a substrate area as un-covered
  AND `memo.md` makes a load-bearing claim about that area without
  one of the three hooks (footnote, `refs/<key>.md` stub, in-prose
  hedge), the existing §"Citation hooks (dim 3)" per-instance
  deduction is the natural escalation path — the perspective sibling
  sharpens an existing deduction rather than introducing a new one.
  The reviewer cites both signals in the justification (e.g.,
  "Unsourced: 'Levenson et al., 2006' — no refs/ stub, no footnote,
  no hedge AND perspective sibling's notes.md flagged the literature
  area as a substrate gap — -2").
- **Stub-filling side-effect**: the reviewer reads
  `_meta.json.search_params.stubs_filled` to identify which
  `refs/<key>.md` citation stubs the perspective role resolved (per
  `commands/memo-perspective.md` §"Side-effect: filling refs/
  citation stubs"); a stub the perspective sibling filled is no
  longer a "needs hook" instance under §"Citation hooks (dim 3)".

The rule is **opportunistic, not punitive** per the framework
contract: perspective can move dim 3 **up**, never **down**. Removing
a perspective citation from an otherwise-identical memo holds or
lowers the score; it never raises it. Perspective is non-gating per
`anvil/lib/snippets/perspective.md`, so no memo can fail dim 3
solely on perspective absence.

See `commands/memo-perspective.md` for the substrate-gathering
contract and `SKILL.md` §"State machine" for the optional-sibling
framing.

## Refs back-check (dim 3)

`<thread>/refs/` is **also** the home for **author-supplied source-of-truth materials** (CV, public filings, papers, transcripts, emails, images) — see SKILL.md §"Source-of-truth materials". When such materials are present, dim 3 *Evidence quality* MUST also score a **per-instance refs back-check** in addition to the §"Citation hooks (dim 3)" rule above. The two sub-rules are **independent** and **additive**: a memo can lose points on both the citation-hook rule (unhooked load-bearing claim) and the refs back-check (claim contradicted by an on-disk source).

The reviewer partitions `<thread>/refs/` into source-of-truth materials (named for their content — `cv.pdf`, `transcript-foo.md`, `filing-s1.pdf`) and citation stubs (named for citation keys, carrying `# TODO: source for <claim>`) per the SKILL.md disambiguation rule. Citation stubs are out of scope for this sub-rule. For each source-of-truth refs-document **type** present (one CV, one filing, one transcript, etc.), the reviewer picks at least one biographical or factual claim in `memo.md` whose evidentiary basis is the document's subject and back-checks it. The reviewer is **not** required to back-check every claim — the requirement is **at least one claim per refs-document type present**.

The reviewer records each back-check in `comments.md` with a four-valued verdict (`VERIFIED` / `UNVERIFIED` / `CONTRADICTED` / `NOT-IN-REFS`) and applies a **per-instance deduction**:

- **One `CONTRADICTED` claim** against a source-of-truth ref — **two-point** dim 3 deduction AND a **critical-flag candidate**. The contradiction is the canary failure mode the contract exists to catch: a factual error in a load-bearing claim (team bio, traction figure, filing-cited number) that propagates through versions because no reviewer back-checked against the underlying source. Reviewers SHOULD raise the critical flag for any CONTRADICTED claim in a load-bearing section (team, financials, traction, technical thesis) — see §"Critical flags" below.
- **One `UNVERIFIED` claim** against a source-of-truth ref (document is present and on-topic but does not contain the supporting passage) — **one-point** dim 3 deduction. Not flag-eligible on its own; the gap is signaled but not deal-breaking.
- **`NOT-IN-REFS` claims** (memo makes a claim, no source-of-truth refs-document covers its subject) — **no deduction**. Informational only; records "where did this come from" visibility for the reviser.
- **`VERIFIED` claims** — no deduction; positively scored under dim 3's full-weight calibration.

The dim 3 justification MUST cite the specific verdict and the refs-document path (e.g., "Back-checked 'Robb Walters: 15+ year Sphere Staff Scientist tenure' against `refs/cv.pdf`: CONTRADICTED ('Sphere Semi, Palo Alto CA, 2026-current') — -2 + critical flag"). Vague "needs refs back-check" deductions without named instances are not actionable for the reviser and SHOULD be avoided — same standard as §"Citation hooks (dim 3)".

**Backward compatibility.** When `<thread>/refs/` contains **no** source-of-truth materials (only citation stubs, or empty, or missing), this sub-rule is **inactive** and dim 3 falls back to the §"Citation hooks (dim 3)" behavior alone. This preserves the PR #140 semantic: a thread that only uses `refs/` for drafter-written citation stubs is unaffected. PDFs and images are treated as presence-only in v0 — the reviewer notes the file is on-disk and back-checks against a sibling `.md` companion (e.g., a `cv.md` next to `cv.pdf`) or `BRIEF.md`-surfaced content; PDF text extraction is deferred.

The deduction is applied entirely via reviewer judgment — there is no automated `refs/` parsing in v0. See `commands/memo-review.md` §Procedure step 5 (dim 3 refs back-check sub-step) for the reviewer-side procedure and `commands/memo-draft.md` §Procedure step 3 for the drafter-side ingestion contract.

## Length targets (dim 7)

When `<thread>/.anvil.json` declares a `target_length` (see `SKILL.md` §Length targets), dim 7 *Scope discipline* compares the produced memo's word count against the declared range rather than judging length against an implicit default.

- **Spec form**: `target_length: { "words": [min, max] }` is primary. `target_length: { "pages": [min, max] }` is accepted and converted at **600 words/page** (so `pages: [3, 4]` ≡ `words: [1800, 2400]`). The reviewer always compares on word count — `anvil:memo` is markdown-first and rendering is not in the review hot path.
- **Counting**: a simple whitespace tokenization of `memo.md` is sufficient. The reviewer may strip code-fence content and YAML frontmatter before counting if they meaningfully distort the body length.
- **Calibration**:
  - **In range** (`min <= actual <= max`): no length-driven deduction.
  - **Modest deviation** (within ~15% of the nearest endpoint): note in the justification, no deduction.
  - **Meaningful deviation** (>~15% over `max` or under `min`): deduct on dim 7; call out the deviation in the justification.
- **Justification format**: when `target_length` is set, the dim 7 justification MUST record both the declared target and the actual count (e.g., "Target 1800–2400 words; actual 2050 — in range"). When the resolved source is `"overrides.v{N}"`, the provenance is appended to the declared-target clause so the reader can see which override fired (e.g., "Target 2000–2800 words (from overrides.v10); actual 2389 — in range"). When the source is `"default"` or `"legacy_flat"`, the provenance parenthetical MAY be omitted. When unset, dim 7 falls back to the implicit "reasonable for the decision being made" judgment with no length numbers required.

The author primitive this enables is the deliberate **expand → tighten** cadence (load new content with breathing room in one revision, then tighten editorial pressure on the next). Two cadence shapes are supported:

- **Single thread-level target**: declare a flat `target_length: { words: [min, max] }` and edit it between revise calls when the cadence shifts. This is the PR #122 shape and continues to work unchanged.
- **Per-version overrides (declarative)**: declare `target_length.default` for the baseline and `target_length.overrides.v{N}` for the versions that need a different range. The drafter and reviser apply the resolution order `overrides.v{N+1}` → `default` → no target when producing v{N+1}; the reviewer reads the resolved range from `_progress.json.metadata.target_length_resolved` so dim 7 scores against the same range the artifact was authored against. See `SKILL.md` §"Length targets" for the schema, resolution order, and backward-compatibility contract.

## Advance threshold

- **≥32/40** — advance to `READY` (or to next step in the lifecycle).
- **<32/40** — block; revise.
- **Any critical flag set** — block regardless of total. The next revision must address the flagged issue specifically and the reviewer must re-evaluate the flag before the threshold check applies.

## Critical flags

A critical flag is an issue severe enough that **a sophisticated reader would immediately stop taking the memo seriously**, regardless of how well other dimensions score. Set a flag whenever such an issue is identified — this list is illustrative, not exhaustive:

- **Conflict of interest** — Material undisclosed conflict (author or fund relationship) that affects the recommendation.
- **Factual error in cited financials** — A number, ratio, or attribution that does not match the cited source. Distinct from a contested interpretation; this is a verifiable error.
- **Recommendation contradicts thesis** — Memo recommends invest while the thesis it presents is unsupported (or recommends pass while the thesis is strongly supported and unrebutted).
- **Risks section omits a known dealbreaker** — A risk the reviewer can identify from the memo's own evidence is absent from the risks section.

The reviewer should also raise a flag for any other issue that, in their judgment, meets the standard above — the four examples are starting points, not a closed set.

## Verdict format

The reviewer writes a `verdict.md` at the top of the review sibling dir with:

1. **Total score**: `XX / 40`.
2. **Decision**: `advance: true` or `advance: false`. (`advance: true` requires both `total ≥ 32` AND `no unresolved critical flag`.)
3. **Critical flags** (if any): bullet list, each with one-paragraph justification.
4. **Dimension summary**: a markdown table of per-dimension scores (full detail lives in `scoring.md`).
5. **Top 3 revision priorities** (if `advance: false`): the highest-leverage changes the reviser should focus on.

## Output layout

```
<thread>.{N}.review/
  verdict.md       Top-level decision (see above)
  scoring.md       Per-dimension score + justification
  comments.md      Line-level comments keyed to memo.md
```

The reviewer dir is **read-only once written** (state: `done` in its own `_progress.json`). Revisions consume it without modifying it.
