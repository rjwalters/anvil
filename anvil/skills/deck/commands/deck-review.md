---
name: deck-review
description: General reviewer command for the deck skill. Scores rubric dimensions 2, 5, 6 (problem clarity, traction/proof, team credibility) and emits the full critic-sibling schema plus a verdict.md.
---

# deck-review — General reviewer

**Role**: general reviewer.
**Reads**: latest `<thread>.{N}/` (specifically `deck.md`, `speaker-notes.md`, and `figures/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Owned rubric dimensions

The general reviewer owns dimensions:
- **2 — Problem clarity** (weight 5)
- **5 — Traction / proof** (weight 5)
- **6 — Team credibility** (weight 4)

Total ownership: 14/40. Other dimensions are scored by specialist critics (`deck-narrative` for 1+7, `deck-market` for 3+4, `deck-design` for 8) and are left `null` in `_summary.md`.

The general reviewer is also responsible for writing the **aggregated `verdict.md`** — the canonical artifact the orchestrator reads to decide advance/block. The aggregation reads sibling critics if present at the same `<thread>.{N}.<tag>/` and combines per-dimension scores (mean of non-null) and critical flags (logical OR).

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md`.
- **Rubric**: `anvil/skills/deck/rubric.md` (8 dimensions, /40, ≥35 threshold, four critical flags).
- **Optional consumer override**: `.anvil/skills/deck/rubric.overrides.md`.
- **Sibling critics at same `N`** (read but not modified): `<thread>.{N}.narrative/_summary.md`, `<thread>.{N}.market/_summary.md`, `<thread>.{N}.design/_summary.md`. These contribute to the aggregated `verdict.md` if present.

## Outputs

```
<thread>.{N}.review/
  verdict.md         Aggregated decision + total /40 + critical flags + top revision priorities
  scoring.md         Per-dimension score (owned dims only) + 1–3 sentence justification each
  comments.md        Slide-level comments keyed to deck.md slides
  _summary.md        8-dim partial scorecard (owned dims scored; others null) + critical-flag bool
  findings.md        Itemized findings: severity, slide ref, rationale, suggested fix
  _meta.json         { "critic": "review", "role": "deck-review.md", "started": "<ISO>", "finished": "<ISO>", "model": "<id>" }
  _progress.json     Phase state for the review (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md`. If `<thread>.{N}.review/_progress.json.review.state == done` AND `verdict.md` + `_summary.md` exist with parseable scores, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`**: `phases.review.state = in_progress`, `phases.review.started = <ISO>`.
4. **Initialize `_meta.json`** with `critic: "review"`, `role: "deck-review.md"`, `started: <ISO>`, `model: <id>`.
5. **Read inputs**:
   - `<thread>.{N}/deck.md` (slide source) + `speaker-notes.md`.
   - `<thread>/BRIEF.md` (to ground claims — every traction number on a slide should trace to the brief).
   - Optionally `<thread>.{N}/figures/` for sanity-checking diagrams.
   - Sibling critic `_summary.md` files at the same `N` (if they exist), for verdict aggregation.
5b. **Run pre-flight overflow lint (source-side)**:
   - Invoke `anvil/skills/deck/lib/marp_lint.py`'s `lint_deck(<thread>.{N}/deck.md)`. This is a Python-stdlib heuristic port of marp-vscode's `slide-content-overflow` diagnostic (see the module docstring for the upstream SHA pin and the per-slide `<!-- anvil-lint-disable: slide-content-overflow -->` escape hatch).
   - The call returns a `LintResult` with `errors: list[Finding]`, `warnings: list[Finding]`, and `infos: list[Finding]`. Each `Finding` has `slide` (1-based slide number), `line` (1-based source line), `rule`, `severity`, and `message`.
   - The lint is **review-phase only** — drafter, auditor, figurer, and the specialist critics (`deck-narrative`, `deck-market`, `deck-design`) do not invoke it. The drafter is intentionally allowed to produce an overflowing slide so the reviser sees the failure mode (issue #31, AC6).
   - Cache the `LintResult` for the `_summary.md` and `findings.md` writes below; cache `lint.errors > 0` as `lint_critical_flag` for the verdict logic.
5c. **Run silent-Marp-auto-shrink lint (post-render, optional)** — issue #102 / #100b:
   - Invoke `anvil/skills/deck/lib/auto_shrink_detector.py`'s `detect_auto_shrink(<thread>.{N}/deck.pdf, <thread>.{N}/deck.md)`. The detector reads the rendered PNGs (reuses `<thread>.{N}.vision/slides/` if the vision critic already populated it; otherwise renders fresh via `anvil/lib/render.py::render_pdf_to_pngs`), computes a per-page content bbox by sampling the background from corner patches and thresholding pixel diffs, classifies each slide by `<!-- _class: ... -->` directive (default `content`), and flags any page whose `bottom_margin_norm` exceeds BOTH `1.5 × class_median` AND `0.18`. Singleton-class slides (typically one `title`, one `ask`) are recorded as skipped with a reason — never flagged.
   - **Why a post-render check is necessary**: Marp's CSS `fit-to-frame` behaviour silently scales the entire `<section>` down to fit a slightly-over-budget page rather than clipping; the slide compiles clean, the PDF opens fine, and the reader sees a slide that reads small without any obvious failure mode. `marp_lint` (step 5b) catches *loud* overflow source-side; this detector catches the *silent* fit-to-scale post-render. `deck-vision` v1 `vertical_overflow` is the qualitative VLM companion (one API call per slide); this detector is deterministic and free.
   - The call returns an `AutoShrinkResult` with `findings: list[AutoShrinkFinding]`, `skipped: bool`, `reason: str | None`, `per_class_medians: dict[str, float]`, and `skipped_classes: dict[str, str]`. Each `AutoShrinkFinding` has `slide`, `class_name`, `bottom_margin_norm`, `median_bottom_margin_norm`, `ratio`, `rule="auto-shrink-fit-compression"`, `severity` (always `"error"`), and a human-readable `message` with an actionable fix hint.
   - **Graceful-skip on missing deps**: the detector needs `Pillow` and `numpy`, which are OPTIONAL Anvil extras (install via `uv pip install -e .[auto_shrink]`). The detector's first step calls `anvil.lib.render.check_auto_shrink_deps_available()`; if it returns `False`, the detector returns `AutoShrinkResult(skipped=True, reason=AUTO_SHRINK_REMEDIATION)` without raising. Record the skip as a `severity="info"` lint entry — the rest of `deck-review` proceeds normally. (Same pattern as the `mmdc` preflight #65 and the `pdfjam` preflight #85.)
   - **Graceful-skip on missing PDF**: if `deck.pdf` does not yet exist (the user hasn't run `deck-figures`), the detector returns `AutoShrinkResult(skipped=True, reason="deck.pdf not found at ...")`. Record as an info-level skip; do not block.
   - Cache the `AutoShrinkResult` for the `_summary.md` and `findings.md` writes below. Errors from this lint OR into `lint_critical_flag` alongside the `marp_lint` errors — `lint_critical_flag = (marp_lint.errors > 0) or (auto_shrink.errors > 0)`. Per the curator's design (#102 D3), the two checks are *complementary*: `marp_lint` catches the source-side overflow before render; this detector catches the post-render auto-shrink that source-side checks structurally can't see.
5d. **Run deck↔memo parity lint (Phase A, warning-only)** — issue #200:
   - Invoke `anvil/skills/deck/lib/parity_lint.py`'s `lint_deck_memo_parity(<thread>.{N}/, <sibling memo version dir or None>)`. This is a Python-stdlib heuristic check (no third-party deps) that extracts hard-claim tokens — money (`$XXK/M/B`, decimal prices), percentages (including en-dash ranges), quarters/FY tags, named months + year, ALL-CAPS acronyms (length 2-6), and unit-bearing integers — from both `deck.md` and the sibling `memo.md` body, then compares the two token sets and flags any token present in one body but absent from the other.
   - **Sibling-memo-version discovery is the caller's (this command's) responsibility in v0**. Convention: at the portfolio root that contains `<thread>.{N}/deck.md`, look for sibling memo version dirs matching `<thread>.{M}/memo.md` and pick the highest `M`. If no sibling memo version exists (single-pipeline thread — most non-Studio consumers, and Studio threads where only the deck has shipped), pass `memo_version_dir=None`. Centralizing the discovery in `anvil/lib/parity.py` is part of the promotion plan once the memo-side mirror lands.
   - **Graceful-skip when no memo sibling**: `lint_deck_memo_parity(deck_dir, None)` (or with a sibling dir that lacks `memo.md`) returns `LintResult(skipped=True, reason="no memo sibling found at portfolio root; parity check inactive", memo_sibling=None)` with zero findings. `deck-review` proceeds normally — the rest of the review/verdict logic is byte-identical to a thread without the parity lint enabled. The skip is RECORDED in `_summary.md.lint.deck_memo_parity` (`ran: false`, `memo_sibling: null`, `reason: "..."`) and as a single info-level entry in `findings.md` § Parity-lint findings, so the operator sees WHY the check did not fire — same skip-reason convention as `auto_shrink` (step 5c).
   - The call returns a `LintResult` with `warnings: list[Finding]`, `infos: list[Finding]`, `skipped: bool`, `reason: str | None`, and `memo_sibling: str | None`. Each `Finding` has `line` (1-based source line in whichever body the token appeared), `rule="deck_memo_parity"`, `severity="warning"` (or `"info"` if suppressed), `message` (a human-readable diagnostic naming the canary anchor), `token` (the normalized token surface form), and `side` (`"only_in_memo"` or `"only_in_deck"`).
   - **v0 ships at `warning` severity only** (Phase A). Parity findings do NOT contribute to `lint_critical_flag` and do NOT force `advance: false` — the `errors` list on the result is always empty in v0. Verdict aggregation (step 12) is byte-identical to a thread without this lint enabled. Phase B promotion to `error` severity (and therefore `advance: false`-gating) is a separate decision deferred 2–4 weeks after Phase A merge, based on canary consumption signal. This Phase A / Phase B contract mirrors the `_convictions.md` kill-switch precedent documented in `anvil/skills/memo/SKILL.md` §"Convictions ledger".
   - **Escape hatch**: `<!-- anvil-lint-disable: deck_memo_parity -->` placed on the same line as a deliberately-deck-only or deliberately-memo-only claim (or on the line directly above) downgrades that finding from `warning` to `info`. Use case: the memo says "we considered FTC enforcement" but the deck deliberately omits it for narrative density — the operator marks the claim and the lint stops complaining. Comma-separated rule lists (`<!-- anvil-lint-disable: deck_memo_parity, slide-content-overflow -->`) are honored.
   - **Canary anchor**: the load-bearing failure mode this lint catches is Citation Clear memo.4 ↔ deck.3, where the reviser introduced an insurer benchmark "~50–60% completion" into memo.4 that deck.3 lacked and no anvil primitive detected the drift (issue #200). The lint's first warning on the citation-clear thread on Phase A ship is the regression anchor.
   - Cache the `LintResult` for the `_summary.md` and `findings.md` writes below. **Do NOT OR this lint's findings into `lint_critical_flag`** — Phase A is observational only.
6. **Score owned dimensions**:
   - **Dim 2 — Problem clarity** (0–5): Does the problem slide convey what hurts, for whom, how much, in <30 seconds? Cite specific slide language. Vague problems, self-evident problems, or problems explained only via solution score low.
   - **Dim 5 — Traction / proof** (0–5): Does the traction slide show real evidence at the stage's level? Are projections clearly labeled as projections? Cross-check every number against `BRIEF.md` — any number on the slide not in the brief is a `Fabricated traction` critical flag.
   - **Dim 6 — Team credibility** (0–4): Are bios specific (named prior roles, named outcomes)? Is founder–market fit explicit? Cross-check every bio against `BRIEF.md` — any bio claim not in the brief is a `Fabricated team credentials` critical flag.
   - **Dim 5 + Dim 6 refs back-check sub-step** (issue #166): enumerate `<thread>/refs/` and identify the **source-of-truth materials** present per SKILL.md §"Source-of-truth materials" (files named for their content — `cv.pdf`, `cv.md`, `founder-bio.md`, `transcript-*.md`, `filing-*.pdf`, `paper-*.pdf`, `email-loi-*.md` / `loi-*.md`, `quote-*.md`, `image-*.{png,jpg}`). The back-check applies to source-of-truth materials only; generic reference material (decks, transcripts the brief did not name as a source-of-truth, financial spreadsheets used only as drafter context) is out of scope for this sub-step and stays under the existing BRIEF-only cross-check. For each source-of-truth refs-document **type** present that is on-topic for dim 5 (traction-bearing files: LOIs, quotes, customer letters, traction-cited filings) or dim 6 (team-bearing files: CVs, founder bios, prior-outcome filings), pick at least one load-bearing claim in `deck.md` whose evidentiary basis is the document's subject and write a `comments.md` entry of the form:
     ```
     claim: "<excerpt from deck.md slide N>"
       -> refs/<file>
       -> verdict: <VERIFIED | UNVERIFIED | CONTRADICTED | NOT-IN-REFS>
       -> <one-line justification, citing the line/passage in refs/<file> when CONTRADICTED or VERIFIED>
     ```
     Verdict tags + per-instance deduction schedule (binds to dim 5 for traction-bearing claims, dim 6 for team-bearing claims):
     - **`VERIFIED`** — claim matches the source-of-truth document; no deduction.
     - **`UNVERIFIED`** — refs/ document is present and on-topic but does not contain the supporting passage (claim is unsupported but not contradicted); **1-point deduction** on the relevant dim (5 or 6).
     - **`CONTRADICTED`** — refs/ document contains a passage that **directly contradicts** the claim (e.g., Slide 10 says "Founder: 15+ years at Bessemer Trust" but `refs/cv.pdf` shows "Bessemer Trust 2018-2023" — five years, not fifteen); **2-point deduction** on the relevant dim AND a **critical-flag candidate**. For traction-bearing claims (dim 5), a CONTRADICTED verdict in a load-bearing context escalates to the existing **critical flag 1 (Fabricated traction)** — the underlying source-of-truth document shows the traction figure is not what the slide says. For team-bearing claims (dim 6), a CONTRADICTED verdict escalates to the existing **critical flag 2 (Fabricated team credentials)** — same canary failure mode the existing flag exists to catch (Bessemer 15+ years founder bio error from issue #166's body propagated through TWO deck versions because no reviewer back-checked against the CV). No new flag is needed; the existing flags 1 and 2 are the natural escalation path.
     - **`NOT-IN-REFS`** — the deck makes a claim, but no source-of-truth refs-document on-disk covers the claim's subject. Informational only (no deduction); records "where did this come from" visibility.
     The reviewer is **not required to back-check every claim** — that would re-litigate the whole deck — but is required to back-check **at least one claim per source-of-truth refs-document type present**. When `refs/` contains no source-of-truth materials (only generic reference material, or empty), this sub-step is **inactive** and dims 5 / 6 fall back to BRIEF-only cross-check (backward-compat with the pre-#166 behavior). PDFs and images are treated as presence-only in v0 — the reviewer notes the file is on-disk and the deck's claim about its subject is `UNVERIFIED` unless the operator has surfaced the relevant passage in `BRIEF.md` or a sibling `.md` companion (e.g., a `cv.md` next to `cv.pdf`). PDF text extraction is deferred to issue #167.
7. **Identify critical flags**:
   - `Fabricated traction`: any traction number or customer logo on a slide not attested in `BRIEF.md`.
   - `Fabricated team credentials`: any bio claim not attested in `BRIEF.md`.
   - Open-ended: "any other issue a sophisticated investor would catch and disqualify on." Raise as the fourth-category flag with a one-paragraph justification.
8. **Write `scoring.md`** as a markdown table for owned dimensions (others omitted or shown as N/A):
   ```
   | # | Dimension          | Weight | Score | Justification |
   |---|--------------------|--------|-------|---------------|
   | 2 | Problem clarity    | 5      | 4     | Slide 2 clearly identifies mid-market manufacturers and quantifies (250k plants, $200k/yr engineer cost). One gap: doesn't quantify how much profit is left on the table. |
   | 5 | Traction / proof   | 5      | 3     | Slide 8 lists 8 paying customers and 3 LOIs (all verified in brief). Missing: retention/cohort data and revenue cadence. |
   | 6 | Team credibility   | 4      | 3     | Founder bios are specific (prior roles named). Gap: no advisors slide; brief lists 2 advisors. |
   ```
9. **Write `_summary.md`** as a JSON-in-markdown scorecard. The `lint` block is populated from the cached `LintResult` returned by step 5b:
   ```markdown
   # Review summary

   ```json
   {
     "critic": "review",
     "for_version": <N>,
     "dimensions": {
       "1_narrative_arc":            null,
       "2_problem_clarity":          { "score": 4, "weight": 5 },
       "3_market_size_credibility":  null,
       "4_solution_differentiation": null,
       "5_traction_proof":           { "score": 3, "weight": 5 },
       "6_team_credibility":         { "score": 3, "weight": 4 },
       "7_ask_specificity":          null,
       "8_design_polish":            null
     },
     "lint": {
       "ran": true,
       "errors": 2,
       "warnings": 3,
       "errors_by_slide": [
         { "slide": 4, "line": 27, "rule": "slide-content-overflow", "severity": "error", "message": "Slide exceeds estimated vertical capacity by ~2.0 line-units..." },
         { "slide": 7, "line": 51, "rule": "slide-content-overflow", "severity": "error", "message": "..." }
       ],
       "warnings_by_slide": [
         { "slide": 5, "line": 36, "rule": "slide-content-overflow", "severity": "warning", "message": "..." }
       ],
       "auto_shrink": {
         "ran": true,
         "skipped": false,
         "reason": null,
         "errors": 1,
         "warnings": 0,
         "infos": 0,
         "findings": [
           { "slide": 9, "class_name": "content", "bottom_margin_norm": 0.34, "median_bottom_margin_norm": 0.12, "ratio": 2.83, "rule": "auto-shrink-fit-compression", "severity": "error", "message": "Slide 9 (class 'content') has bottom margin 34.0% of slide height; class median is 12.0% (2.83x). Marp likely fit-to-frame-scaled this page — trim 10–20 words from the densest element or move one bullet to a peer slide so the content fits without auto-shrink." }
         ],
         "per_class_medians": { "content": 0.12 },
         "skipped_classes": { "title": "only 1 page(s) in class 'title' — minimum 3 required for a peer-median comparison.", "ask": "only 1 page(s) in class 'ask' — minimum 3 required for a peer-median comparison." }
       },
       "deck_memo_parity": {
         "ran": true,
         "memo_sibling": "/abs/path/to/citation-clear.4",
         "reason": null,
         "warnings": 1,
         "infos": 0,
         "only_in_memo": ["50-60%"],
         "only_in_deck": [],
         "warnings_by_token": [
           { "line": 7, "rule": "deck_memo_parity", "severity": "warning", "message": "Hard claim `50-60%` appears in memo (line 7) but not in the sibling deck...", "token": "50-60%", "side": "only_in_memo" }
         ],
         "infos_by_token": []
       }
     },
     "critical_flag": false,
     "critical_flag_notes": []
   }
   ```
   ```
   - The `deck_memo_parity` block is populated from the cached `LintResult` returned by step 5d. When the lint skipped (no memo sibling discoverable), the block shape is `{ "ran": false, "memo_sibling": null, "reason": "no memo sibling found at portfolio root; parity check inactive", "warnings": 0, "infos": 0, "only_in_memo": [], "only_in_deck": [], "warnings_by_token": [], "infos_by_token": [] }`. The `ran: false` skip path MUST be recorded — the operator should see WHY the parity check did not fire (same skip-reason convention as `auto_shrink`).
   - **`deck_memo_parity` findings do NOT contribute to `critical_flag` in v0** (Phase A ships warning-only). The block is observational: it surfaces drift in `findings.md` and the operator's revision priorities, but the `critical_flag` boolean is computed exactly as before (`marp_lint.errors > 0` OR `auto_shrink.errors > 0`). Phase B promotion to error severity (and therefore `advance: false`-gating) is a separate decision deferred per issue #200's Phase A / Phase B contract.
   - When `lint.errors > 0` (sum of source-side `errors` AND `auto_shrink.errors`), set `critical_flag: true` and append entries to `critical_flag_notes`:
     - source-side overflow: `{ "type": "slide_overflow_lint", "slide_refs": ["Slide 4", "Slide 7"], "justification": "Pre-flight overflow lint flagged N slides..." }`.
     - auto-shrink: `{ "type": "auto_shrink_fit_compression", "slide_refs": ["Slide 9"], "justification": "Marp silent auto-shrink detected on N slide(s) — rendered PNG bbox shows slide content occupies <50% of peer-class median height. See lint.auto_shrink.findings for the per-slide breakdown." }`.
     Both flag categories live under the "fourth-category critical flag" bucket (per `rubric.md`'s open-ended slot for "any other issue a sophisticated investor would catch and disqualify on") — a deck whose slides visibly read smaller than peer slides reads as unfinished.
   - If a non-lint critical flag is also raised, populate `critical_flag_notes` with one object per flag: `{ "type": "fabricated_traction", "slide_ref": "Slide 8", "justification": "..." }`.
10. **Write slide-level `comments.md`**: list specific feedback keyed to slide number + heading. Group by severity (`blocker` / `major` / `minor` / `nit`). Example:
    ```
    ## Slide 8 — Traction

    - **major**: ARR figure ($420k) appears here but brief lists $380k ARR. Discrepancy must be resolved before send.
    - **minor**: Add MoM growth rate — investor will ask.

    ## Slide 11 — Financials

    - **blocker**: "Projected $5M ARR by end of year" — current ARR is $380k, no current data point on the curve. Either provide intermediate milestones or drop the projection.
    ```
11. **Write `findings.md`** as itemized findings (deck-specific format the reviser uses for aggregation):
    ```
    ## Findings

    1. **[major]** Slide 8: ARR discrepancy ($420k on slide vs $380k in brief). Suggested fix: use $380k or explain the delta in speaker notes with citation.
    2. **[blocker]** Slide 11: Hockey-stick projection with no intermediate milestones. Suggested fix: replace with month-by-month build to a $5M ARR target, or scope projection to next 12 months only.
    ...

    ## Lint findings

    Each entry comes from the pre-flight `slide-content-overflow` lint (step 5b). Errors block advance; warnings are recorded for the reviser but do not block.

    1. **[error]** Slide 4 (line 27): Slide exceeds estimated vertical capacity by ~2.0 line-units (estimated 15.6u vs. capacity 13.0u). Top costs: image=7.0u, h2=2.0u, bullet=1.1u. Suggested fix: collapse the trailing 4 bullets into a single italic supporting line under the figure, or move the figure to a two-column block.
    2. **[error]** Slide 7 (line 51): Slide exceeds estimated vertical capacity by ~2.7 line-units. Top costs: h1=3.2u, h1+h2-anti-pattern=1.5u. Suggested fix: drop the H2 slide tag — the `_class: ask` dark background already signals "the ask"; use a single H2 headline.
    3. **[warning]** Slide 5 (line 36): Slide borderline (estimated 14.0u vs. capacity 13.0u). Suggested fix (non-blocking): consider trimming one bullet.
    ```
    Each finding: severity, slide reference (with source line), rationale (1–2 sentences), suggested fix (1 sentence). The "Lint findings" section is present even if empty (write `_No lint findings._`).

    A second post-render lint block (issue #102) sits under its own subsection. When `auto_shrink.skipped == true` (deps missing or PDF absent), record the skip reason as a single info-severity entry rather than omitting the section — the reviser should see WHY the check didn't run:

    ```
    ## Auto-shrink lint findings (post-render, optional)

    Each entry comes from the `auto-shrink-fit-compression` detector (step 5c). Errors block advance via the lint critical flag — Marp silently scaled the slide down to fit, which reads as "unfinished" next to peer slides.

    1. **[error]** Slide 9 (class 'content', bm=34% vs class median 12%, ratio 2.83x): Marp likely fit-to-frame-scaled this page. Suggested fix: trim 10–20 words from the densest element, or move one bullet to a peer slide so the content fits without auto-shrink.
    ```

    Or, when the detector was skipped:

    ```
    ## Auto-shrink lint findings (post-render, optional)

    _Skipped: <reason from AutoShrinkResult.reason>._

    Per-class medians: { content: 0.12 }
    Skipped classes (too few peers): { title: "only 1 page", ask: "only 1 page" }
    ```

    A third lint block (issue #200, Phase A) sits under its own subsection. The parity lint is **always present** (subsection emitted even when the lint skipped) so the operator sees WHY the check did or did not fire. v0 ships warning-only — entries surface drift but do NOT block advance:

    ```
    ## Parity-lint findings (deck↔memo, optional)

    Each entry comes from the deck↔memo parity lint (step 5d). v0 (Phase A) ships at **warning severity** — entries surface drift in shared hard claims (money, percentages, dates / quarters / FY, named months + year, ALL-CAPS acronyms, unit-bearing integers) but do NOT contribute to `lint_critical_flag` and do NOT block advance. Phase B promotion to error severity is a separate decision after 2–4 weeks of canary consumption signal.

    1. **[warning]** only_in_memo (memo line 7): Hard claim `50-60%` appears in memo but not in the sibling deck. Either reconcile on next `deck-revise`, document the deliberate omission with `<!-- anvil-lint-disable: deck_memo_parity -->`, or accept the divergence (warning only in v0). Canary: Citation Clear memo.4 introduced a `~50–60% completion` insurer benchmark absent from deck.3 — exactly this shape.
    ```

    Or, when the parity check was skipped (no memo sibling discoverable at the portfolio root):

    ```
    ## Parity-lint findings (deck↔memo, optional)

    _Skipped: no memo sibling found at portfolio root; parity check inactive._

    Memo sibling discovered: null
    ```

    Or, when the parity check ran cleanly (no divergences):

    ```
    ## Parity-lint findings (deck↔memo, optional)

    _No parity-lint findings._

    Memo sibling discovered: /abs/path/to/<thread>.{M}/
    ```
12. **Aggregate verdict** (this reviewer is the canonical verdict author):
    - **The `deck_memo_parity` lint (step 5d) does NOT participate in this aggregation in v0.** Parity findings ship at `warning` severity (Phase A); they surface in `findings.md` § Parity-lint findings and MAY appear under "Top revision priorities" in `verdict.md`, but they are NOT counted in `lint_critical_flag` and they do NOT force `advance: false`. Phase B promotion to error severity (and therefore inclusion in the critical-flag aggregation) is a separate decision deferred per issue #200's Phase A / Phase B contract. The aggregation logic below is byte-identical to a thread with the parity lint disabled.
    - Glob `<thread>.{N}.*/_summary.md` (siblings + self). Parse each.
    - For each rubric dimension, compute the aggregate score as the mean of non-null critic scores. Round to one decimal for display; sum for total.
    - For critical flag, take logical OR of all critic flags **including both pre-flight lints** (source-side `marp_lint` from step 5b AND post-render `auto_shrink_detector` from step 5c). If this `_summary.md`'s own `lint.errors > 0` OR `lint.auto_shrink.errors > 0`, the aggregated critical flag is true regardless of any other critic.
    - Decision: `advance = (total >= 35) AND (no critical flag)`. When `lint.errors > 0`, `advance` is forced `false` and the verdict lists `Slide overflow (lint)` under critical flags; when `lint.auto_shrink.errors > 0`, the verdict additionally lists `Slide auto-shrink (lint)`. The rubric total is reported honestly but does not save the verdict.
13. **Write `verdict.md`**:
    ```markdown
    # Verdict — <thread> v<N>

    **Total**: 32.5 / 40
    **Decision**: `advance: false`
    **Critical flags**: 1 (from deck-market)

    ## Dimension summary

    | # | Dimension | Weight | Score | Critics contributing |
    |---|-----------|--------|-------|---------------------|
    | 1 | Narrative arc            | 6 | 5.0 | narrative |
    | 2 | Problem clarity          | 5 | 4.0 | review |
    | 3 | Market size credibility  | 5 | 3.0 | market |
    | 4 | Solution differentiation | 5 | 4.0 | market |
    | 5 | Traction / proof         | 5 | 3.0 | review |
    | 6 | Team credibility         | 4 | 3.0 | review |
    | 7 | Ask specificity          | 5 | 5.0 | narrative |
    | 8 | Design polish            | 5 | 5.5 | design |

    ## Critical flags

    - **Market-math error** (raised by deck-market): TAM calculation on Slide 7 multiplies units wrong — claimed $50B but inputs yield $5B. Reviser must recompute.
    - **Slide overflow (lint)** (raised by deck-review pre-flight, 2 errors): Slides 4 and 7 exceed estimated vertical capacity per the `slide-content-overflow` heuristic. See `findings.md` § Lint findings for the per-slide breakdown and suggested fixes.

    ## Top revision priorities

    1. Fix Slide 7 TAM calculation (critical flag).
    2. Resolve the 2 overflow-lint errors on slides 4 and 7 (critical flag — blocks advance).
    3. Slide 11 projection — replace hockey stick with month-by-month build.
    4. Slide 8 ARR discrepancy ($420k vs brief $380k).
    ```
14. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
15. **Update `_meta.json`**: `finished: <ISO>`.
16. **Report**: print one-line status (e.g., `Reviewed acme-seed.1 → acme-seed.1.review/ (review owns 14/40; aggregated total 32.5/40, advance: false, 1 critical flag)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` + `_summary.md` exist and parse) is never re-run.
- A crashed review is re-runnable after deleting partial output.
- If sibling critics produce updated `_summary.md` files **after** this reviewer ran, re-running the reviewer is appropriate — the aggregation in `verdict.md` will pick up the new scores. (The orchestrator should re-run `deck-review` last in any parallel critic batch.)

## Notes for the reviewer agent

- **Be honest, not encouraging.** The skill is not "polish the deck." It is "would I take a meeting based on this?" If the answer is no, score accordingly.
- **Cross-check against the brief.** Every traction number on a slide must trace to the brief. Every bio must trace to the brief. This is the single highest-value check the reviewer performs.
- **Critical flags are not bonus points.** Use sparingly but use them when warranted. A fabrication critical flag in a fundraising deck is a deal-killer.
- **Slide-level comments are actionable.** "Tighten this slide" is not useful. "Slide 8 ARR figure conflicts with brief — use $380k or document the delta in speaker notes" is useful.

## `_progress.json` snippet (review sibling)

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "review": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Merge rule: shallow merge; preserve fields not touched by this command.


**Scorecard kind declaration**: This critic's `_meta.json` SHOULD include `"scorecard_kind": "human-verdict"` per `anvil/lib/snippets/scorecard_kind.md`. This is the deck aggregator critic, which emits BOTH the `human-verdict` shape (verdict.md, scoring.md, comments.md) and the `machine-summary` shape (_summary.md, findings.md); the primary kind is `human-verdict` because the aggregated `verdict.md` is the primary deliverable for the orchestrator.
