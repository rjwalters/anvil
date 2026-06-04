---
name: memo-review
description: Reviewer command for the memo skill. Scores the latest memo version against the 9-dimension /44 rubric and writes a read-only review sibling directory.
---

# memo-review — Reviewer

**Role**: reviewer.
**Reads**: latest `<thread>.{N}/` (specifically `memo.md` and any `exhibits/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/memo.md` existing.
- **Rubric**: `anvil/skills/memo/rubric.md` (9 dimensions, /44, ≥35 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/memo/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).
- **Optional per-thread rubric overrides** (issue #233 / #265): `<thread>/.anvil.json`'s `rubric_overrides` block, parsed via `anvil/skills/memo/lib/anvil_config.py::load_rubric_overrides`. When present, per-dimension `dim_N_calibration` strings are appended as verbatim suffixes to each affected dimension's `scoring.md` justification (see step 4g + the §"Rubric overrides (rubric_overrides) — calibration suffixes" subsection below).

## Reader dispatch order: `.anvil.json` vs `BRIEF.md` "Critical reviewer guidance"

A thread MAY surface non-investment-memo calibration guidance in two places:

1. **Structured config** at `<thread>/.anvil.json` under the `rubric_overrides` block (the primary, machine-readable path shipped under issue #233). The reader is `anvil/skills/memo/lib/anvil_config.py::load_rubric_overrides`; per-dimension calibrations attach as verbatim suffixes to `scoring.md` justifications per step 4g.
2. **Author-side prose** in `BRIEF.md` (the legacy convention surfaced by the Studio canary's 2 READY-at-39/40 threads, the workaround that motivated #233 in the first place). The "Critical reviewer guidance" section is freeform prose telling the reviewer how to interpret specific dimensions for the non-standard shape.

**Precedence — structured config wins.** When BOTH sources are present, the reviewer reads `.anvil.json` first and applies per-dimension calibrations to `scoring.md` justifications via the suffix mechanism. The `BRIEF.md` "Critical reviewer guidance" section is then treated as **documented fallback / context** — the reviewer reads it for additional context (especially for `memo_subtype`-level orientation that does not map cleanly to a per-dim calibration) but does NOT re-apply its prose as a suffix (that would double-count the calibration in the audit trail). When ONLY `BRIEF.md` carries the guidance (no `rubric_overrides` block in `.anvil.json`, or no `.anvil.json` at all), the reviewer reads the BRIEF.md guidance and respects it inline in its `scoring.md` justifications — the pre-#233 status quo for the two canary threads. When ONLY `.anvil.json` carries the guidance (the recommended steady-state for new threads going forward), the suffix mechanism is the entire calibration surface.

**Why structured-config-wins.** The `.anvil.json` shape is the schema-of-record contract — it is parseable, validated by the typed loader, surfaces malformed inputs as warnings, and produces a deterministic audit trail (`scoring.md` carries the verbatim suffix). The `BRIEF.md` prose is author-discretion and can phrase the same intent in 20 different ways; making it the secondary source decouples the reviewer's mechanical behavior from author wording. Consumers migrating off the BRIEF.md convention should move their guidance into `.anvil.json` over the next 2-3 revisions; the BRIEF.md fallback ships indefinitely as backwards-compat.

## Outputs

```
<thread>.{N}.review/
  verdict.md       Top-level decision + total /44 + critical flags + top revision priorities
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to memo.md headings or excerpts
  _summary.md      Machine-readable scorecard + pre-flight lint block + render-gate block (see step 9)
  _meta.json       { critic, role, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state for the reviewer (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/memo.md`. If `<thread>.{N}.review/_progress.json.review.state == done` and `verdict.md` exists, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`** for the review dir: `phases.review.state = in_progress`, `phases.review.started = <ISO>` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`).
4. **Read inputs**: load `<thread>.{N}/memo.md`, enumerate `exhibits/`, load `rubric.md` and any consumer override. Resolve the declared `target_length` for v{N} by reading it from `<thread>.{N}/_progress.json.metadata.target_length_resolved` (the field the drafter or reviser wrote when producing v{N}). The field carries the resolved `(min_words, max_words)` pair plus a `source` provenance string (`"overrides.v{N}"`, `"default"`, `"legacy_flat"`, or `"none"`). Reading this field — rather than re-resolving from `<thread>/.anvil.json` here — is the load-bearing behavior: it pins the reviewer's dim 7 anchor to the same range the drafter/reviser authored against and prevents drift if `<thread>/.anvil.json` is edited between draft and review.

   If `target_length_resolved` is absent (legacy v{N} from before this field shipped, or a hand-built version dir), fall back to re-resolving from `<thread>/.anvil.json` per the SKILL.md §Length targets contract using `N` as the version number: `target_length.overrides.v{N}` → `target_length.default` → legacy flat `target_length` → no target. Normalize: `words` taken directly, `pages` converted at 600 words/page, malformed/absent → no target (dim 7 falls back to the implicit "reasonable" judgment).
4b. **Run pre-flight image-reference lint (source-side)** — issue #146:
   - Invoke `anvil/skills/memo/lib/memo_image_refs.py`'s `lint_memo_image_refs(<thread>.{N}/)`. This is a Python-stdlib heuristic check (no third-party deps, no Marp / Pandoc invocation) that parses `memo.md` for both markdown `![alt](path)` syntax AND HTML `<img src="...">` syntax. For each ref it resolves the path relative to the version directory and verifies the file exists. URL refs (`http://`, `https://`, `mailto:`, `data:`, `ftp://`, `file://`) and absolute filesystem paths (`/abs/...`) are skipped — out of scope per the v0 contract.
   - The call returns a `LintResult` with `errors: list[Finding]`, `warnings: list[Finding]`, and `infos: list[Finding]`. Each `Finding` has `line` (1-based source line), `rule` (always `"memo_image_refs_exist"` for this lint), `severity`, `message`, `ref` (the raw reference string), and `resolved_path` (the absolute path the ref resolved to).
   - When a missing ref names a subdirectory (e.g., `exhibits/foo.png`) AND a file with the same basename exists at the version-dir root (e.g., `<version_dir>/foo.png`), the diagnostic surfaces the **`cp -r` footgun shape** explicitly — the canary failure mode documented in #146 (`cp -r .../old/exhibits .../new/` expanded to dump files into the version root because the destination did not exist as a directory).
   - **Escape hatch**: `<!-- anvil-lint-disable: memo_image_refs_exist -->` placed on the same line as a ref, or on the immediately preceding line, downgrades that finding from `error` to `info` so the lint records that the ref is intentionally absent (e.g., `memo-figures` will generate it later) without blocking advance.
   - The lint is **review-phase only** — the drafter and reviser do not invoke it. The drafter is intentionally allowed to produce a stale-path memo so the reviser sees the failure mode (precedent: deck-review step 5b, per the curator addendum on issue #31 / AC6).
   - Cache the `LintResult` for the `_summary.md` write below; cache `lint.errors > 0` as `lint_critical_flag` for the verdict logic at step 7.
4c. **Read render-gate findings (non-blocking, graceful-degrade)** — Epic #158 Phase 4 / issue #196:
   - Read `<thread>.{N}/_progress.json.render_gate` (the top-level block written by `memo-render` per `commands/memo-render.md` step 6 + the `GateResult.to_json()` shape from `anvil/lib/render_gate.py`). The block carries `{gate, pdf_path, log_path, pages, page_cap, overfull_boxes, compile, placeholders, findings, pass, reasons}`. Each entry in `findings` is `{gate, severity, message, location}` where `gate` is one of `memo_compile_success` / `memo_page_fit` / `memo_overfull_check` / `memo_image_refs_exist` / `memo_placeholder_scan`.
   - **Graceful-degrade when absent**: if `_progress.json` is missing entirely, or `_progress.json.render_gate` is missing (the memo was never rendered — legal pre-Phase-3 state, every memo version drafted before Epic #158 has this shape, AND the current state when `memo-render` is unavailable on PATH or the consumer has not installed Anvil's Phase 3 commands), record a single info-level note in the cached `render_gate_block` (`{"ran": false, "reason": "no render_gate block in _progress.json"}`) and skip silently. The reviewer's dim 7 judgment falls back to word-count-only per `rubric.md` §"Length targets" — same behavior as before this phase shipped. This is the load-bearing backwards-compat contract.
   - **Non-blocking**: render-gate findings DO NOT abort the review, DO NOT set the verdict's `lint_critical_flag`, and DO NOT force `advance: false`. They are surfaced in `_summary.md.render_gate` for the operator to see and for the dim 7 justification to reference, but the verdict at step 7 is driven by the rubric total + the four critical-flag categories + the source-side `memo_image_refs_exist` lint (step 4b). Per `rubric.md` §"Length targets" §"Word count is primary; rendered page count is second-layer advisory": word count remains the primary measure; the rendered page count is a second-layer advisory the reviewer reads alongside it.
   - **Severity model surfaced verbatim**: the render gate classifies `memo_page_fit` findings as `error` when the operator declared `target_length.pages` (an explicit page-range contract) and `warning` when they declared `target_length.words` (the page-range is derived via the 600-words-per-page proxy; dim 7 word-count is authoritative). The reviewer does NOT re-derive the severity; the gate's classification is the contract. The `_summary.md.render_gate.findings_by_dimension` block surfaces the severities verbatim from `render_gate.findings`.
   - **Mirror of the deck-side shape**: this step mirrors the deck-side `_summary.md.lint` block that `deck-review` already produces (see `commands/deck-review.md` step 5b + step 9 — pre-flight `marp_lint` findings surfaced in `_summary.md.lint.errors_by_slide` + `lint.warnings_by_slide`). The memo block is named `render_gate` (not `lint`) so it stays distinct from the existing memo-side `lint` block (`memo_image_refs` + `refs_pdf_extraction`) that step 4b owns.
   - Cache the parsed block as `render_gate_block` for the `_summary.md` write at step 9. The dim 7 scoring at step 5 SHOULD read `render_gate_block.pages` (when present and non-null) for the rendered-page-count second-layer signal documented in `rubric.md` §"Length targets" §"Word count is primary; rendered page count is second-layer advisory".
4d. **Run memo↔deck parity lint (Phase A, warning-only)** — issue #215 (memo-side mirror of deck-review step 5d / PR #205 / issue #200):
   - Invoke `anvil/skills/memo/lib/parity_lint.py`'s `lint_memo_deck_parity(<thread>.{N}/, <sibling deck version dir or None>)`. This is a Python-stdlib heuristic check (no third-party deps, no Marp / Pandoc invocation) that extracts hard-claim tokens — money (`$XXK/M/B`, decimal prices), percentages (including en-dash ranges), quarters/FY tags, named months + year, ALL-CAPS acronyms (length 2-6), and unit-bearing integers — from both `memo.md` and the sibling `deck.md` body, then compares the two token sets and flags any token present in one body but absent from the other. The module is a **near-byte-identical mirror** of `anvil/skills/deck/lib/parity_lint.py` (PR #205) with the "primary artifact" framing flipped — `lint_source(memo_source, deck_source)` takes memo first, the rule label is `memo_deck_parity`, the escape-hatch directive is `<!-- anvil-lint-disable: memo_deck_parity -->`, and `LintResult.deck_sibling` mirrors the deck-side `memo_sibling`. The `Finding.side` values (`"only_in_memo"` / `"only_in_deck"`) are preserved verbatim — they describe *which body the token came from*, independent of which side is "primary".
   - **Sibling-deck-version discovery is the caller's (this command's) responsibility in v0**. Convention: at the portfolio root that contains `<thread>.{N}/memo.md`, look for sibling deck version dirs matching `<thread>.{M}/deck.md` and pick the highest `M`. If no sibling deck version exists (single-pipeline thread — most non-Studio consumers, and Studio threads where only the memo has shipped), pass `deck_version_dir=None`. Mirrors the deck-side's portfolio-root convention exactly. Centralizing the discovery in `anvil/lib/parity.py` is part of the now-fired second-consumer promotion plan — see the WORK_LOG entry for #215.
   - **Graceful-skip when no deck sibling**: `lint_memo_deck_parity(memo_dir, None)` (or with a sibling dir that lacks `deck.md`) returns `LintResult(skipped=True, reason="no deck sibling found at portfolio root; parity check inactive", deck_sibling=None)` with zero findings. `memo-review` proceeds normally — the rest of the review/verdict logic is byte-identical to a thread without the parity lint enabled. The skip is RECORDED in `_summary.md.lint.memo_deck_parity` (`ran: false`, `deck_sibling: null`, `reason: "..."`) and as a single info-level entry in `findings.md` § Parity-lint findings, so the operator sees WHY the check did not fire — same skip-reason convention as `lint.refs_pdf_extraction` (step 5) and the deck-side's `lint.deck_memo_parity` (deck-review step 5d).
   - The call returns a `LintResult` with `warnings: list[Finding]`, `infos: list[Finding]`, `skipped: bool`, `reason: str | None`, and `deck_sibling: str | None`. Each `Finding` has `line` (1-based source line in whichever body the token appeared), `rule="memo_deck_parity"`, `severity="warning"` (or `"info"` if suppressed), `message` (a human-readable diagnostic naming the canary anchor), `token` (the normalized token surface form), and `side` (`"only_in_memo"` or `"only_in_deck"`).
   - **v0 ships at `warning` severity only** (Phase A). Parity findings do NOT contribute to `lint_critical_flag` and do NOT force `advance: false` — the `errors` list on the result is always empty in v0. Verdict aggregation (step 7) is byte-identical to a thread without this lint enabled. Phase B promotion to `error` severity (and therefore `advance: false`-gating) is a separate decision deferred 2–4 weeks after Phase A merge, based on canary consumption signal. This Phase A / Phase B ship-with-falsifiability pattern (single named consumer + bounded observation window + explicit kill-switch criterion) is the same shape used by the kill-switch precedent recorded in `WORK_LOG.md` 2026-06-02 (issue #227) and is carried verbatim from the deck-side step 5d.
   - **Escape hatch**: `<!-- anvil-lint-disable: memo_deck_parity -->` placed on the same line as a deliberately-memo-only or deliberately-deck-only claim (or on the line directly above) downgrades that finding from `warning` to `info`. Use case: the deck says "we considered FTC enforcement" but the memo deliberately omits it for prose density — the operator marks the claim and the lint stops complaining. Comma-separated rule lists (`<!-- anvil-lint-disable: memo_deck_parity, memo_image_refs_exist -->`) are honored.
   - **Canary anchor**: the load-bearing failure mode this lint catches (from the memo-side POV) is the symmetric direction of Citation Clear memo.4 ↔ deck.3 — a deck pulling ahead of the memo on a load-bearing hard claim (e.g., the reviser tightens an insurer benchmark to "~50–60% completion" in deck.4 that memo.4 lacked) that no anvil primitive would otherwise detect. The deck-side step 5d catches the inverse drift direction (memo.4 introducing a claim deck.3 lacked); together the two checks cover both directions and are symmetric / idempotent — running deck-review and memo-review on the same `<thread>.{N}` produces the same warning set with the same tokens, just with rule names `deck_memo_parity` vs `memo_deck_parity`.
   - Cache the `LintResult` for the `_summary.md` write at step 9 and the `findings.md` write at step 10 (advisory only — `verdict.md` MAY reference under "Top revision priorities" but is NOT required). **Do NOT OR this lint's findings into `lint_critical_flag`** — Phase A is observational only.
4e. **Run summary-detail consistency back-check (Phase A, reviewer-judgment)** — issue #245:
   - This is a **reviewer-prose-only** sub-step in Phase A — no Python module is invoked. Following the §"Refs back-check (dim 3)" precedent (`commands/memo-review.md` step 5, fully reviewer-judgment with no automated `refs/` parsing in v0), the reviewer enumerates load-bearing summary claims, locates their detail elaboration, classifies any mismatch by verdict tag + severity, and emits a structured `summary_detail_consistency` block + a `findings.md` subsection. An automated detector at `anvil/skills/memo/lib/summary_detail.py` is a Phase B follow-on, gated on canary signal.
   - **Procedure (three phases)** — mirrors the issue body's "Proposed shape" list and `rubric.md` §"Summary-detail consistency":
     1. **Enumerate summary claims** — scan the callout block(s), abstract / TL;DR block, thesis block (first 1-3 paragraphs depending on memo shape), and any "what we believe" frontmatter for load-bearing assertions per `rubric.md` §"Summary-detail consistency" §"What counts as a load-bearing summary claim". Count each as a numbered claim (claim 1, claim 2, …). Record the source `summary_location` for each claim (e.g., `"callout bullet 1 (page 1)"`, `"§1 thesis paragraph 1"`). If the memo has no callout / abstract / thesis block to scan (short memos), record `ran: false` with `reason: "no callout / abstract / thesis block identified in memo.md"` and skip the rest of this step — the reviewer is required to explicitly emit `ran: false` rather than omit the block (same convention as `lint.refs_pdf_extraction` and `lint.memo_deck_parity`).
     2. **Locate the detailed elaboration** — for each summary claim, find the section(s) where it is elaborated. Use explicit `§N` references when present in the claim itself; fall back to topic / load-bearing-noun-phrase matching when absent. Record the `detail_location` (e.g., `"§2.2 (Pericles.2)"`) or `"(absent)"` when no detail section elaborates the claim.
     3. **Classify the mismatch** — for each (summary claim, detail section) pair, apply the verdict tag and severity from `rubric.md` §"Summary-detail consistency" §"Verdict tags" + §"Severity ladder":
        - **`MATCH`** — no finding emitted.
        - **`ABSENT`** — severity `important` typically; `critical` when the claim is the memo's thesis or a load-bearing recommendation justification.
        - **`CONTRADICTED`** — severity **always `critical`** (the canary failure mode).
        - **`DIVERGENT`** — severity `suggestion` typically; `important` when the framing change shifts the recommendation.
   - **Cache the structured block** for the `_summary.md` write at step 9 and the `findings.md` write at step 10. Specifically, cache `summary_detail_block` as:
     - `ran: bool` — `true` when summary blocks were identified and scanned; `false` (with `reason` populated) when no summary block was found.
     - `summary_blocks_scanned: list[str]` — descriptive labels for each scanned block (e.g., `["callout (page 1)", "§1 thesis paragraph 1"]`).
     - `claims_enumerated: int` — total count of load-bearing summary claims identified.
     - `findings_count: int` — total count of non-`MATCH` findings.
     - `findings_by_severity: {critical, important, suggestion}` — count of findings per severity bucket.
     - `findings: list[dict]` — one entry per non-`MATCH` finding with `claim_id`, `claim_excerpt`, `summary_location`, `detail_location`, `verdict`, `severity`, `message`, `suggested_fix`, and (when `severity == "critical"`) `load_bearing_justification`. Full shape and field semantics: see step 9 below.
     - `critical_flag_candidate: bool` — convenience flag for step 7 verdict aggregation. MUST equal `any(f.severity == "critical" and f.verdict == "CONTRADICTED" for f in findings)`. Implementer convention; not duplicated state.
   - **Cache `summary_detail_critical_flag = summary_detail_block.critical_flag_candidate`** for the verdict logic at step 7. A `CONTRADICTED` finding at `critical` severity surfaces as a `Summary-detail consistency: CONTRADICTED` critical flag in `verdict.md` (see step 10) and forces `advance: false` via the existing critical-flag pathway. `ABSENT` and `DIVERGENT` findings at `important` / `suggestion` severity are observational only and do NOT force `advance: false`.
   - **Related (back-check triangle)**: this is the *intra-memo* back-check (memo A summary ↔ memo A detail). The §"Refs back-check (dim 3)" sub-step at step 5 below covers memo A claim ↔ memo A `refs/`. The #236 cross-thread analog (step 4f below) covers memo A claim ↔ memo B `§N`. Together the three legs cover the back-check triangle. See `rubric.md` §"Summary-detail consistency" §"Related" for the composition contract.
4f. **Run cross-thread citation back-check (Phase A, reviewer-judgment)** — issue #236:
   - This is a **reviewer-prose-only** sub-step in Phase A — no Python module is invoked. Following the §"Refs back-check (dim 3)" precedent (`commands/memo-review.md` step 5, fully reviewer-judgment with no automated `refs/` parsing in v0) and the §"Summary-detail consistency" precedent (step 4e above, issue #245 / PR #250), the reviewer enumerates cross-thread citations in `memo.md`, resolves each to `(thread_slug, latest_version_dir, section_anchor)`, classifies any mismatch by verdict tag + severity, and emits a structured `cross_thread_cite_consistency` block + a `findings.md` subsection. An automated detector at `anvil/skills/memo/lib/cross_thread_cite.py` (skill-local first per CLAUDE.md §"Skill-local first, lib promotion later") is a Phase B follow-on, gated on canary signal.
   - **Procedure (three phases)** — mirrors the issue body's "Cite patterns to detect" + "Proposed shapes" lists and `rubric.md` §"Cross-thread citation back-check (dim 3)":
     1. **Enumerate cross-thread cites** — scan `memo.md` for citation-shaped patterns referencing other anvil threads per `rubric.md` §"Cross-thread citation back-check (dim 3)" §"What counts as a cross-thread citation". Catch all four shapes permissively:
        - **Literal-path**: `<thread-slug>/memo.<N>/memo.md` (e.g., `brasidas-synthesis/memo.2/memo.md`).
        - **Short-form**: `<thread-slug> §X` or `<thread-slug>/memo §X` (e.g., `brasidas-synthesis §3.1`).
        - **Relative-path** (studio convention): `output/<thread-slug>/...` (e.g., `output/brasidas-synthesis/memo.2/memo.md`).
        - **Backtick-wrapped**: `` `<thread-slug>/memo.<N>/memo.md` §<X> `` (e.g., `` `brasidas-synthesis/memo.2/memo.md` §5.2 ``).
        Count each as a numbered cite (cite 1, cite 2, …). Record the source `summary_location` for each cite (e.g., `"§2 paragraph 3 (memo.md line 47)"`). If `memo.md` contains no cross-thread cites, record `ran: false` with `reason: "no cross-thread citations identified in memo.md"` and skip the rest of this step — the reviewer is required to explicitly emit `ran: false` rather than omit the block (same convention as `lint.refs_pdf_extraction`, `lint.memo_deck_parity`, and `summary_detail_consistency` at step 4e).
     2. **Resolve each cite** — for each enumerated cite, resolve to `(thread_slug, latest_version_dir, section_anchor)`:
        - The **cited thread** resolves to the latest `<thread-slug>.{N}/` directory under the portfolio root (highest `N`) — cross-thread cites point at a **moving target** by default. **Pinning to a specific cited version** (e.g., `brasidas-synthesis.2`) is a **stronger contract** the reviewer notes positively in the dim 3 justification (NOT a deduction).
        - The **section anchor** is the `§N` or section-header reference in the cite text. Scan the cited `memo.md` for a matching header.
        - Record the `resolved_path` (e.g., `"<portfolio_root>/brasidas-synthesis.2/memo.md"`) and `section_anchor` (e.g., `"§3.1"`) for each cite.
     3. **Classify by verdict tag** — for each (cite, resolved location) tuple, apply the verdict tag and severity from `rubric.md` §"Cross-thread citation back-check (dim 3)" §"Verdict tags" + §"Severity ladder":
        - **`ANCHOR-FOUND`** — no finding emitted (silent). Cited thread + version + anchor all resolved cleanly.
        - **`ANCHOR-MISSING-BUT-THREAD-PRESENT`** — severity `important`; **-1 dim 3 deduction**. Cited thread exists but §N anchor not found in latest version. The canary failure mode.
        - **`ANCHOR-CONTRADICTED`** — severity **always `critical`**; **-2 dim 3 deduction AND critical-flag candidate**. §N exists at the cited location but its content materially contradicts the claim the citing memo attributes to it.
        - **`THREAD-NOT-FOUND`** — severity `important`; **-1 dim 3 deduction**. Cited thread slug does not resolve to any directory under the portfolio root.
   - **Cache the structured block** for the `_summary.md` write at step 9 and the `findings.md` write at step 10. Specifically, cache `cross_thread_cite_block` as:
     - `ran: bool` — `true` when at least one cross-thread cite was identified and resolved; `false` (with `reason` populated) when no cross-thread cites were found.
     - `cites_enumerated: int` — total count of cross-thread cites identified.
     - `findings_count: int` — total count of non-`ANCHOR-FOUND` findings.
     - `findings: list[dict]` — one entry per non-`ANCHOR-FOUND` finding with `cite_text`, `summary_location`, `resolved_path`, `section_anchor`, `verdict`, `severity`, `justification`. Full shape and field semantics: see step 9 below.
     - `critical_flag_candidate: bool` — convenience flag for step 7 verdict aggregation. MUST equal `any(f.severity == "critical" and f.verdict == "ANCHOR-CONTRADICTED" for f in findings)`. Implementer convention; not duplicated state.
   - **Cache `cross_thread_cite_critical_flag = cross_thread_cite_block.critical_flag_candidate`** for the verdict logic at step 7. An `ANCHOR-CONTRADICTED` finding at `critical` severity surfaces as a `Cross-thread cite: ANCHOR-CONTRADICTED` critical flag in `verdict.md` (see step 10) and forces `advance: false` via the existing critical-flag pathway. `ANCHOR-MISSING-BUT-THREAD-PRESENT` and `THREAD-NOT-FOUND` findings at `important` severity are observational only and do NOT force `advance: false` (the per-instance dim 3 deduction is the natural surface).
   - **Related (back-check triangle)**: this is the *cross-thread* back-check (memo A claim ↔ memo B `§N`). Step 4e above covers the intra-memo back-check (memo A summary ↔ memo A detail, #245 / PR #250). The §"Refs back-check (dim 3)" sub-step at step 5 below covers memo A claim ↔ memo A `refs/` (#144 / PR #140 / PR #162). Together the three legs cover the **back-check triangle** — see `rubric.md` §"Cross-thread citation back-check (dim 3)" §"Related (back-check triangle composition)" for the composition contract. The three legs share the structural shape (explicit-skip convention, top-level `_summary.md` block, critical-flag-candidate pathway, `findings.md` subsection, fixture-anchored Phase B) but preserve divergent verdict-tag vocabularies — each leg's vocabulary is canon for that leg.
4g. **Load `rubric_overrides` from `<thread>/.anvil.json`** — issue #233 / #265:
   - Invoke `anvil/skills/memo/lib/anvil_config.py::load_rubric_overrides(<thread_dir>)`. The thread dir is the **portfolio-root parent** of `<thread>.{N}/memo.md` (the directory that contains `BRIEF.md` and `.anvil.json`, NOT a version subdirectory). The loader returns a `RubricOverrides` instance per the schema documented in `anvil_config.py`'s module docstring.
   - The returned object carries:
     - `memo_subtype: Optional[str]` — free-string label naming the shape (e.g., `"synthesis-brief"`, `"feedback-memo"`, `"decision-framework"`). Opaque to the reviewer logic; recorded in the `_summary.md.rubric_overrides` block for audit-trail visibility (see step 9).
     - `calibrations: List[CalibrationOverride]` — per-dimension calibration entries (the load-bearing data: each entry is `(dimension: int 1-9, text: str)`).
     - `target_length: Optional[TargetLengthRange]` — optional per-thread override of the existing `target_length` field. **NOT consumed by `memo-review`** — the reviewer's dim 7 anchor is `<thread>.{N}/_progress.json.metadata.target_length_resolved` per step 4, written by the drafter / reviser. The `rubric_overrides.target_length` field is the **drafter / reviser** consumer surface (sub-issue 2's deferred half: `memo-draft` and `memo-revise` will honor it when they next ship a target-length-resolution update). This separation matches the schema decision noted in `anvil_config.py`'s docstring §"Relationship to existing schema": `rubric_overrides.target_length` is the *subtype calibration* surface, not the per-version surface.
     - `unknown_keys: Dict[str, Any]` — forward-compat passthrough (any key the loader didn't recognize). Surfaced via `warnings.warn` from the loader; surfaced in `_summary.md.rubric_overrides.unknown_keys` for operator visibility.
   - **Graceful-degrade when absent**: the loader returns an empty `RubricOverrides` (every field `None` / empty) for any of: missing `.anvil.json`, malformed JSON, missing `rubric_overrides` block, non-dict `rubric_overrides`. The lenient form is the production contract — a consumer typo in `.anvil.json` never breaks the lifecycle. The reviewer's behavior on an empty `RubricOverrides` is **byte-identical** to the pre-#233 status quo: no suffixes attached, no `_summary.md.rubric_overrides` block emitted (or emitted with `ran: false`).
   - **Cache the `RubricOverrides` instance** for the scoring write at step 5 and the `_summary.md` write at step 9. The instance is read-only from this point — no mutation.
4h. **Load artifact-type rubric overlay (issue #286, sub-deliverable 3 of #283; absorbs closed #278)**:
   - Invoke `anvil/skills/memo/lib/rubric_overlays.py::select_overlay_for_thread(<thread_dir>)`. The function walks up to find a project-level `BRIEF.md` (the portfolio-as-thread-root layout shipped via #284), locates the thread's slug in the BRIEF's `documents:` list, reads its declared `artifact_type` (one of `investment-memo`, `position-paper`, `tactical-plan`, `vision-document`, `descriptive-thesis`), and loads the matching overlay JSON from `anvil/skills/memo/rubric_overlays/<artifact-type>.json`.
   - The returned `RubricOverlay` carries:
     - `artifact_type: ArtifactType` — the registered enum value.
     - `weight_adjustments: dict[str, int]` — sparse dict of `dim_N` → integer delta applied to the base rubric weight. The reviewer applies the delta when scoring each affected dimension and clamps to non-negative integers (no shipped overlay drives any dim below 0). The verbatim adjustments are recorded in `_summary.md.rubric_overlay.weight_adjustments` for audit-trail visibility.
     - `calibration_prose: dict[str, str]` — sparse dict of `dim_N` → prose string. For each affected dimension, the reviewer appends the prose verbatim to its `scoring.md` justification as a calibration suffix, mirroring the per-thread `rubric_overrides.dim_N_calibration` mechanism (issue #233). Composition order is overlay-first then per-thread: `<base justification>` + ` [overlay: <overlay prose>]` + ` [thread: <per-thread prose>]`. When both surfaces target the same dim, both suffixes appear so the audit trail records which surface contributed which calibration.
   - **Graceful-degrade when absent**: `select_overlay_for_thread` returns `None` for any of: classic-layout thread (no project BRIEF on the walk-upward path — the v0 status quo for non-portfolio threads), thread slug not listed in the BRIEF's `documents:` block, or a BRIEF that fails to parse. In all of these cases the reviewer behaves byte-identically to the pre-#286 status quo — no weight adjustments, no overlay suffix, no `_summary.md.rubric_overlay` block (or emitted with `ran: false`).
   - **Identity overlay**: the `investment-memo` overlay is identity (zero weight adjustments, empty calibration prose) so a thread with `artifact_type: investment-memo` in the project BRIEF behaves byte-identically to a thread with no project BRIEF at all. The verdict comment surfaces `Applying rubric overlay: investment-memo (identity)` for transparency; the reviewer's scoring logic is unaffected.
   - **Cache the `RubricOverlay`** (or `None`) for the scoring write at step 5 and the `_summary.md` write at step 9. The instance is read-only from this point — no mutation.
5. **Score each dimension** (1–9 per rubric):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (heading, excerpt, exhibit) from the memo.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.
   - **Dim 9 (Rhetorical economy) `scope: reduce` echo sub-step (issue #242)**: when dim 9 scores below full weight (4/4), the rubric requires the reviewer to cite specific anti-pattern instances in the dim 9 justification (multi-paragraph hedges, oversized footnotes, restated subsections, redundant tables, reformulated open-decisions entries, restated bullet lists — per `rubric.md` §"Dim 9 — rhetorical economy"). For every cited instance, the reviewer MUST ALSO surface that instance as a `scope: reduce` entry in `comments.md` (see step 8) — the two surfaces stay coherent: `scoring.md` says "-2 on §4.2's three-paragraph hedge"; `comments.md` echoes the same §4.2 instance as a `scope: reduce` comment with the suggested trim. This is the **mechanical surfacing path** from rubric-side anti-pattern citation to operator-visible comment stream: without the echo, the reviser sees the dim 9 deduction in `scoring.md` but has no `comments.md` entry to act on, and the named instances stay locked in score-justification prose the reviser may not parse. The echo is **per-instance**: each named anti-pattern instance becomes one `scope: reduce` comment, severity matching the load-bearing-ness of the instance (typically `major` for thesis-block bloat, `minor` for tangential bloat). When dim 9 scores 4/4 (full weight) the echo is inactive — there are no instances to surface.
   - **Dim 3 (Evidence quality) refs back-check sub-step**: enumerate the **resolved refs-dir list** returned by `anvil/skills/memo/lib/refs_resolver.py::resolve_refs_dirs(<thread_dir>)` — `[<thread>/refs/]` for the legacy single-thread shape, OR `[<thread>/refs/, <portfolio>/research/]` for the portfolio-shared shape (issue #280) when a sibling `<portfolio>/research/` directory exists. Iterate ALL resolved directories (not just `<thread>/refs/`) and partition the union of entries into (a) **source-of-truth materials** — files named for their content (`cv.pdf`, `cv.md`, `transcript-*.md`, `filing-*.pdf`, `paper-*.pdf`, `email-*.md`, `image-*.{png,jpg}`, `prior/<vN>.{pdf,md}`, portfolio-level files like `comps/silicon-comp-matrix.md` and `00-*.md` vertical briefs) per SKILL.md §"Source-of-truth materials" — and (b) **citation stubs** — files matching the `<key>.md` shape with `# TODO: source for <claim>` content per SKILL.md §"Citation stubs". The back-check applies ONLY to source-of-truth materials; citation stubs are out of scope for this sub-step (they are scored under §"Citation hooks (dim 3)" per the existing per-instance deduction). **Per-thread precedence on filename collision**: when the same basename exists in both `<thread>/refs/` and `<portfolio>/research/`, the per-thread copy wins (the resolver returns it first; the reviewer picks the first match when iterating). The verdict-tag prose surfaces which layer the evidence came from via the `-> <refs-dir-basename>/<file>` shape (see below). For each source-of-truth refs-document **type** present in the union (one CV, one filing, one transcript, one comp-matrix, etc.), pick at least one biographical or factual claim in `memo.md` whose evidentiary basis is the document's subject, and write a `comments.md` entry of the form:
     ```
     claim: "<excerpt from memo.md>"
       -> <refs-dir-basename>/<file>      # `refs/<file>` for per-thread hits; `research/<file>` for portfolio-level hits (issue #280)
       -> verdict: <VERIFIED | UNVERIFIED | CONTRADICTED | NOT-IN-REFS>
       -> <one-line justification, citing the line/passage in <refs-dir-basename>/<file> when CONTRADICTED or VERIFIED>
     ```
     Verdict tags:
     - **`VERIFIED`** — claim matches the source-of-truth document; no deduction.
     - **`UNVERIFIED`** — refs/ document is present and on-topic but does not contain the supporting passage (claim is unsupported but not contradicted); 1-point dim 3 deduction.
     - **`CONTRADICTED`** — refs/ document contains a passage that **directly contradicts** the claim (e.g., memo says "Sphere Staff Scientist tenure 15+ years" but `refs/cv.pdf` shows "Sphere Semi, Palo Alto CA, 2026-current"); 2-point dim 3 deduction AND a **critical-flag candidate** per the rubric's open-ended "any deal-breaker a sophisticated reader would catch" instruction. Reviewers SHOULD set the critical flag for any CONTRADICTED claim in a load-bearing section (team, financials, traction, technical thesis).
     - **`NOT-IN-REFS`** — the memo makes a claim, but no source-of-truth refs-document on-disk covers the claim's subject. Informational only (no deduction); records "where did this come from" visibility.
     The reviewer is **not required to back-check every claim** — that would re-litigate the whole memo — but is required to back-check **at least one claim per refs-document type present**. When `refs/` contains no source-of-truth materials (only citation stubs, or empty), this sub-step is **inactive** and dim 3 falls back to the citation-hooks behavior alone (backward-compat with PR #140).

     **PDF refs back-check (opt-in via `pdftotext`, issue #167)**: call `anvil/skills/memo/lib/refs_pdf.py::check_pdftotext_available()`. When it returns `True`, extract each `*.pdf` file in the resolved refs-dir list (per-thread `<thread>/refs/*.pdf` AND portfolio-level `<portfolio>/research/*.pdf` and any subdirectory `*.pdf` therein — issue #280) to text via `extract_pdf_text(...)` and apply the same `VERIFIED` / `UNVERIFIED` / `CONTRADICTED` / `NOT-IN-REFS` verdict-tag rubric above against the extracted text directly — PDFs become first-class back-check sources, no sibling `.md` companion required. When extraction returns an empty string (image-based / scanned PDF), log an info-level note (`refs/<file>.pdf` produced no extractable text — likely image-based; would need OCR for back-check) and fall back to presence-only handling for that specific file — no deduction either way; this is an operator-facing visibility note. When `check_pdftotext_available()` returns `False`, PDFs and images are treated as **presence-only** (the v0 fallback shipped in PR #162) — the reviewer notes the file is on-disk and the memo's claim about its subject is `UNVERIFIED` unless the operator has surfaced the relevant passage in `BRIEF.md` or a sibling `.md` companion (e.g., a `cv.md` next to `cv.pdf`). In the `check_pdftotext_available() == False` path, the reviewer additionally records an info-level lint entry in `_summary.md.lint.refs_pdf_extraction` (see step 9) carrying the remediation install story from `refs_pdf.PDFTOTEXT_REMEDIATION` so the consumer sees how to enable the back-check on the next run. Images (`.png` / `.jpg`) remain presence-only in all paths in v0 (OCR / vision back-check is deferred per the issue body).

     **Cross-thread reference validation (issue #287 — sub-deliverable 4 of #283)**: scan `<thread>.{N}/memo.md` for cross-thread references of the form `[[../<other-slug>/<other-slug>.latest]]` and `[[../<other-slug>/<other-slug>.N]]` (with optional `/memo.md` or `/exhibits/<file>` suffix) via `anvil/skills/memo/lib/cross_thread_refs.py::find_cross_thread_refs(memo_text)` and resolve each one against the portfolio root (`<thread_dir>.parent`) via `resolve_cross_thread_ref(ref, portfolio_root)` (or use the convenience batch helper `resolve_cross_thread_refs(memo_text, portfolio_root)`). The resolver tolerates `.latest` as either a symlink, a real directory, OR (when neither exists) a walk-to-highest fallback that picks the highest-numbered `<other-slug>.<N>/` sibling — this works today regardless of sub-deliverable 5 (#288)'s `.latest` symlink convention. For each unresolved cross-thread ref (`reason` of `"thread not found"`, `"version not found"`, `"file not found"`, or `"latest unresolvable"`), record a `comments.md` entry of the form:

     ```
     claim: "<excerpt from memo.md including the unresolved [[../...]] ref>"
       -> <other-slug>/<file>        # citation-token vocabulary for cross-thread refs (recommended)
       -> verdict: UNRESOLVED (<reason>)
       -> <one-line justification — name the resolution failure and the on-disk gap>
     ```

     The citation-token vocabulary `[<other-slug>/<file>]` matches the existing `[refs/<file>]` (per-thread) and `[research/<file>]` (portfolio) patterns from issue #280 — one less special case for the reviser and downstream tooling to learn. Apply a **per-instance dim 3 deduction proportional to the unresolved count** — `-1` per unresolved ref, matching the `UNVERIFIED` precedent for the `refs/` back-check above. The deduction is cumulative across multiple unresolved refs (a memo with three unresolved cross-thread refs takes `-3` on dim 3). Resolved cross-thread refs are observed silently (no comment, no deduction); their successful resolution is the positive signal under dim 3's full-weight calibration.

     The dim 3 justification MUST cite the unresolved ref(s) and the resolution failure (e.g., "Unresolved cross-thread ref `[[../brasidas-synthesis/brasidas-synthesis.99]]` (memo.md line 47): version not found — brasidas-synthesis only has versions .1 and .2 on disk; -1"). Vague "cross-thread refs broken" deductions without named refs are not actionable for the reviser and SHOULD be avoided — same standard as the rest of dim 3's sub-rules. **Backward compatibility**: when `find_cross_thread_refs(memo_text)` returns an empty list (the common case — many threads do not cite siblings), this sub-step is **inactive** and dim 3 falls back to the citation-hooks + refs back-check behavior alone. Byte-identical pre-#287 behavior for any memo without cross-thread refs.
   - **Dim 7 (Scope discipline) length comparison**: compute the word count of `memo.md` (a simple `len(memo.md.split())` is sufficient; the reviewer may strip code-fence content and YAML frontmatter before counting if they meaningfully distort the body length). If `target_length` is set, compare the actual word count against the declared `[min, max]` range and apply the following calibration:
     - **In range** (`min <= actual <= max`): no length-driven deduction; score on the other scope-discipline criteria (no kitchen-sink appendices, no scope creep into adjacent deals).
     - **Modest deviation** (within ~15% of the nearest endpoint): note in the justification but do not flag — soft target.
     - **Meaningful deviation** (>~15% over `max` or under `min`): deduct on dim 7 and call out the deviation explicitly in the justification.
     The dim 7 justification MUST record **both the declared target and the actual count** (e.g., "Target 1800–2400 words; actual 2050 — in range" or "Target 1800–2400 words; actual 3400 — 42% over upper bound"). When the resolved source is `"overrides.v{N}"`, append the provenance to the declared-target clause so the reader can see which override fired (e.g., "Target 2000–2800 words (from overrides.v10); actual 2389 — in range"). When the source is `"default"` or `"legacy_flat"`, the provenance parenthetical MAY be omitted — those sources match the implicit "thread-level default" reading and adding the tag adds noise without information. When `target_length` is unset (source `"none"`), the dim 7 justification falls back to the implicit "reasonable for the decision being made" judgment as today, with no length numbers required.

     **Rendered page count as second-layer advisory** (Phase 4 / issue #196): when `render_gate_block` (cached at step 4c) is present AND `render_gate_block.pages` is non-null, append the rendered page count to the dim 7 justification alongside the word count (e.g., "Target 1800–2400 words; actual 2050 (3 rendered pages) — in range"). Per `rubric.md` §"Length targets" §"Word count is primary; rendered page count is second-layer advisory", the word count is the primary measure and the rendered page count is a second-layer advisory signal — the two MAY disagree, and when they do the reviewer judges which is binding (word count wins for the typical markdown-first memo; rendered page count is binding only when the operator declared `target_length.pages` explicitly). When the word count is in range but the rendered page count is out of range (e.g., 2050 words within `[1800, 2400]` but 5 rendered pages because of an oversized figure), record both numbers and note the rendered overflow as advisory in the dim 7 justification (e.g., "Target 1800–2400 words; actual 2050 (5 rendered pages — second-layer advisory, see `_summary.md.render_gate`) — in range on the primary signal"). When `render_gate_block.ran == false` (no render_gate block on disk — legal pre-Phase-3 or pre-render state), the rendered-page parenthetical is omitted and dim 7 falls back to word-count-only judgment.

   **Rubric overrides (rubric_overrides) — calibration suffixes** (issue #233 / #265): for each dimension N with a `dim_N_calibration` declared in the cached `RubricOverrides` (step 4g), append the verbatim calibration text as a suffix to that dimension's justification BEFORE writing it to `scoring.md`. The contract:

   - **Suffix shape (verbatim)**: `"<reviewer-prose-justification> calibration applied: <override text>"`. A single space separates the reviewer prose from the suffix; the prefix `"calibration applied: "` (with trailing space) is the load-bearing anchor a downstream consumer greps for. The override text is reproduced **byte-for-byte verbatim** — no rewording, no truncation, no whitespace normalization. The author's exact wording is the audit trail.
   - **Empty justification handling**: when the reviewer wrote no justification body for a dimension (e.g., full-weight score without prose), the suffix becomes the entire justification: `"calibration applied: <override text>"`. The calibration MUST still appear in the audit trail even when the reviewer's own prose is absent.
   - **Per-dimension dispatch**: ONLY dimensions with `dim_N_calibration` declared carry the suffix. Dimensions without a calibration are byte-identical to their pre-#233 form. A reviewer that sets calibrations for dims 1, 5, 6, 7 (the brasidas-synthesis canary) sees suffixes on those four; dims 2, 3, 4, 8, 9 are unchanged.
   - **Mechanical helper**: `anvil/skills/memo/lib/rubric_overrides_suffix.py::apply_calibration_to_justification(justification, overrides, dimension)` (single dim) or `apply_calibrations_to_scores(scores, overrides)` (batch) implements the suffix shape. The reviewer agent SHOULD invoke the helper rather than reproducing the suffix format by hand — the helper is the schema-of-record for the format. Calling sites: at the end of the per-dim scoring loop (step 5), after the reviewer has written its own prose justification, run the cached `RubricOverrides` through the helper and use the returned suffix-appended string as the `scoring.md` table cell.
   - **Zero-impact when `rubric_overrides` is absent** (AC3 of #265): the helper returns the input justification byte-for-byte unchanged when `overrides` is `None` OR `overrides.is_empty == True`. The reviewer's per-dim scoring write path is byte-identical to its pre-#233 behavior for legacy threads. This is the load-bearing backwards-compat contract for the ~90% of threads that do not declare `rubric_overrides`.
   - **Dim 7 interaction**: when `target_length` is declared inside `rubric_overrides`, the reviewer's dim 7 anchor is STILL the resolved range cached at step 4 (from `_progress.json.metadata.target_length_resolved` or the `.anvil.json` top-level fallback). The `rubric_overrides.target_length` field is consumed by `memo-draft` and `memo-revise` (the drafter / reviser) — they write the resolved range into `_progress.json.metadata.target_length_resolved` for the next version, and `memo-review` reads that resolved field per step 4. So `rubric_overrides.target_length` participates indirectly via the existing pinning mechanism. A `dim_7_calibration` (separate from `target_length`) attaches as a suffix per the rules above.

   **Worked example** — brasidas-synthesis canary (`memo_subtype: "synthesis-brief"`, the worked example from issue #233):

   On-disk `<thread>/.anvil.json`:
   ```json
   {
     "max_iterations": 8,
     "rubric_overrides": {
       "memo_subtype": "synthesis-brief",
       "dim_1_calibration": "decision-framework — score on framework clarity + sub-recommendation sharpness, not on single ranked recommendation",
       "dim_5_calibration": "defers to underlying market models — score on integration quality not on fresh sizing",
       "dim_6_calibration": "defers to underlying market models — score on whether financial framing supports positioning",
       "dim_7_calibration": "target length 9000-13000 words; score against declared target",
       "target_length": { "words": [9000, 13000] }
     }
   }
   ```

   Resulting `scoring.md` table rows (only the affected dims shown):
   ```
   | # | Dimension                 | Weight | Score | Justification                                                                                                                                                                                                                                                  |
   |---|---------------------------|--------|-------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
   | 1 | Recommendation clarity    | 5      | 5     | Brief commits to 5 sharp sub-recommendations and explicitly defers portfolio-shape choice to the CEO; the framework itself is unambiguous. calibration applied: decision-framework — score on framework clarity + sub-recommendation sharpness, not on single ranked recommendation |
   | 5 | Market & competitive framing | 4   | 4     | Synthesis correctly integrates per-vertical market models without re-doing the sizing work — references all 5 verticals with appropriate weight. calibration applied: defers to underlying market models — score on integration quality not on fresh sizing |
   | 6 | Financial reasoning       | 5      | 5     | Financial framing supports the recommendation framework without re-modeling; defers to the underlying per-vertical scenario math. calibration applied: defers to underlying market models — score on whether financial framing supports positioning |
   | 7 | Scope discipline          | 4      | 4     | Target 9000-13000 words; actual 11,247 — in range. Synthesis stays within scope of the analytical bundle. calibration applied: target length 9000-13000 words; score against declared target |
   ```

   Dims 2, 3, 4, 8, 9 carry their normal reviewer-prose justifications with NO suffix attached (no calibration declared for those dims). The verdict + advance logic at step 7 is unchanged — the suffix is audit-trail commentary, not a score modifier.
6. **Identify critical flags**: review the memo against the 4 example flags in `rubric.md` AND the open-ended "any deal-breaker a sophisticated reader would catch" instruction. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 35) AND (no critical flags) AND (lint.errors == 0)`. When the pre-flight image-reference lint (step 4b) reports `errors > 0`, `advance` is forced `false` and the verdict lists `Memo image refs (lint)` under critical flags. The rubric total is reported honestly but does not save the verdict — a memo that references files that do not exist is not advance-eligible regardless of its prose quality.

   **Summary-detail consistency critical flag (issue #245)**: when the cached `summary_detail_critical_flag` from step 4e is `true` (i.e., the back-check identified at least one `CONTRADICTED` finding at `critical` severity), append a critical flag named `Summary-detail consistency: CONTRADICTED` to the verdict's critical-flag list with the claim excerpt + the contradicting detail location as the one-paragraph justification. This flag is set via the existing critical-flag-candidate pathway, NOT via a new gate — the existing `advance` aggregation (`(total >= 35) AND (no critical flags) AND (lint.errors == 0)`) is unchanged; the back-check plugs into the "no critical flags" clause exactly like the §"Refs back-check" `CONTRADICTED` precedent. `ABSENT` and `DIVERGENT` findings at `important` / `suggestion` severity are observational only — they do NOT contribute to the critical-flag list and do NOT force `advance: false` on their own.

   **Cross-thread cite back-check critical flag (issue #236)**: when the cached `cross_thread_cite_critical_flag` from step 4f is `true` (i.e., the back-check identified at least one `ANCHOR-CONTRADICTED` finding at `critical` severity), append a critical flag named `Cross-thread cite: ANCHOR-CONTRADICTED` to the verdict's critical-flag list with the cite text + the contradicting cited-section location as the one-paragraph justification. This flag is set via the existing critical-flag-candidate pathway, NOT via a new gate — the existing `advance` aggregation (`(total >= 35) AND (no critical flags) AND (lint.errors == 0)`) is unchanged; the back-check plugs into the "no critical flags" clause exactly like the §"Refs back-check" `CONTRADICTED` precedent and the §"Summary-detail consistency" `CONTRADICTED` precedent. `ANCHOR-MISSING-BUT-THREAD-PRESENT` and `THREAD-NOT-FOUND` findings at `important` severity are observational only — they do NOT contribute to the critical-flag list and do NOT force `advance: false` on their own (the per-instance dim 3 deduction is the natural surface).
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to memo sections — heading reference + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`).

   **Scope tagging (issue #242, Phase A — reviewer-prose-only)**: every comment carries a `scope: preserve | expand | reduce` label alongside its severity grouping. The label appears in the comment heading directly so the operator can scan/filter at a glance and the reviser at #241 can read scope + severity together. See `rubric.md` §"Scope tagging (comments.md)" for the three-valued vocabulary, the dim 9 echo rule, the expand-trim-candidate rule, and the backwards-compat fallback. Shape:

   ```
   ### §4.2 (line 187) — scope: reduce, major
   Excerpt: "Three-paragraph hedge on PAM4/FEC tradeoffs..."
   Comment: Could land in one sentence per dim 9 §"Multi-paragraph hedges where one sentence carries the load."
   ```

   The three values:

   - **`scope: preserve`** — the comment proposes a change that neither adds nor removes content (e.g., reword for clarity, fix a typo, swap a noun for a sharper noun, reorder paragraphs without compression). Default when the comment does not propose adding or removing content.
   - **`scope: expand`** — the comment proposes ADDING content (a new paragraph, a new subsection, a new exhibit, a new risk entry, a new financial-scenario row, a new citation expansion).
   - **`scope: reduce`** — the comment proposes REMOVING or COMPRESSING content (collapse a three-paragraph hedge to one sentence, drop a redundant subsection, trim a restated bullet list, replace a worked-example table with a one-line rule statement, fold an oversized footnote into a parenthetical).

   **Required `scope: reduce` echoes from dim 9 (issue #242 AC 2)**: every dim 9 anti-pattern instance cited in `scoring.md` (per step 5's echo sub-step) MUST appear as a `scope: reduce` `comments.md` entry. The two surfaces stay coherent: when dim 9 scored less than 4/4, the `scope: reduce` subset of `comments.md` is **non-empty** AND each entry cites a specific instance with a suggested trim. Severity matches the load-bearing-ness of the instance (typically `major` for thesis-block bloat, `minor` for tangential bloat).

   **`scope: expand` trim-candidate rule (issue #242 AC 3)**: any `scope: expand` comment that proposes adding **≥1 paragraph** or **≥1 subsection** MUST identify what could be trimmed to fund the addition. Two acceptable forms:

   1. Name an existing paragraph / subsection to compress, OR
   2. Explicitly acknowledge that the addition fits within dim 9's budget without compression cost (e.g., "The risk section currently runs short — adding this risk fits without trimming elsewhere.").

   Comments lacking the trim-candidate clause are **automatically downgraded from `major` to `minor`** — the bar for unconditional expansion at `major` severity is "the dim 9 budget can absorb it." A `scope: expand` comment at `minor` severity does NOT carry the trim-candidate requirement (the additive cost is small enough that the budget is implicit). A `scope: expand` comment at `nit` severity (single-word / single-clause additions like a missing definition or a one-line clarification) is also exempt.

   **Heading shape**: the `scope` label appears in the comment heading after the severity, separated by a comma:

   ```
   ### <heading reference> (<location>) — scope: <preserve|expand|reduce>, <blocker|major|minor|nit>
   Excerpt: "<short excerpt>"
   Comment: <comment text>
   ```

   The comment groupings by severity (`blocker` / `major` / `minor` / `nit`) MAY remain as top-level `## Severity: <severity>` subsections; the scope label is per-comment inside those groupings. Alternatively the reviewer MAY group by scope at the top level (`## Scope: reduce` / `## Scope: expand` / `## Scope: preserve`) with severity per-comment — the choice is reviewer judgment and not load-bearing for the contract; the requirement is that BOTH scope and severity appear on every comment.

   **Backwards-compat (issue #242 AC 6)**: a review sibling produced **before** this contract shipped does NOT need to be re-emitted and remains a legal historical record. The reviser at #241 reads `scope` when present and falls back to severity-only when absent (mirrors the perspective-sibling backwards-compat pattern in `rubric.md` §"Perspective substrate (dim 3)" §"Without perspective"). New reviews produced after this contract ships MUST carry scope labels per the rules above.
9. **Write `_summary.md`** as a JSON-in-markdown scorecard. The `lint` block is populated from the cached `LintResult` returned by step 4b, the `refs_pdf_extraction` block reflects the PDF refs back-check path (step 5, issue #167), and the `render_gate` block reflects the cached `render_gate_block` from step 4c (Phase 4 / issue #196):
   ```markdown
   # Review summary

   ```json
   {
     "critic": "review",
     "for_version": <N>,
     "dimensions": { ... per-dim scores ... },
     "lint": {
       "memo_image_refs": {
         "ran": true,
         "errors": 1,
         "warnings": 0,
         "errors_by_path": [
           { "line": 41, "rule": "memo_image_refs_exist", "severity": "error", "message": "Image reference `exhibits/fig_cohort_valuation.png` does not exist at expected path `/abs/path/to/<thread>.{N}/exhibits/fig_cohort_valuation.png`, but a file with the same basename was found at the version-dir root...", "ref": "exhibits/fig_cohort_valuation.png", "resolved_path": "/abs/path/to/<thread>.{N}/exhibits/fig_cohort_valuation.png" }
         ],
         "warnings_by_path": []
       },
       "refs_pdf_extraction": {
         "ran": false,
         "reason": "pdftotext not available",
         "remediation": "pdftotext (poppler-utils) not found on PATH — required only for the optional `anvil:memo` PDF refs back-check (issue #167). Install via `brew install poppler` (macOS) or `apt-get install poppler-utils` (Debian/Ubuntu). ..."
       },
       "memo_deck_parity": {
         "ran": true,
         "deck_sibling": "/abs/path/to/citation-clear.3",
         "reason": null,
         "warnings": 1,
         "infos": 0,
         "only_in_memo": [],
         "only_in_deck": ["50-60%"],
         "warnings_by_token": [
           { "line": 31, "rule": "memo_deck_parity", "severity": "warning", "message": "Hard claim `50-60%` appears in deck (line 31) but not in the sibling memo...", "token": "50-60%", "side": "only_in_deck" }
         ],
         "infos_by_token": []
       }
     },
     "render_gate": {
       "ran": true,
       "pages": 5,
       "page_cap": null,
       "compile_status": "ok",
       "pass": false,
       "errors": 0,
       "warnings": 1,
       "infos": 0,
       "findings_by_dimension": {
         "memo_compile_success": [],
         "memo_page_fit": [
           { "severity": "warning", "message": "rendered 5 pages outside derived range [3, 4] (from target_length.words=[1800, 2400] @ 600 wpp). Word-count proxy in dim 7 remains authoritative; this is an advisory second-layer warning.", "location": "/abs/path/to/<thread>.{N}/memo.pdf:pages=5" }
         ],
         "memo_overfull_check": [],
         "memo_image_refs_exist": [],
         "memo_placeholder_scan": []
       },
       "reasons": [
         "memo_compile_success: pandoc exited 0; PDF produced.",
         "memo_page_fit: rendered 5 pages outside derived range [3, 4] (from target_length.words=[1800, 2400] @ 600 wpp). Word-count proxy in dim 7 remains authoritative; this is an advisory second-layer warning.",
         "memo_overfull_check: overflow check ran with no stderr warnings detected."
       ]
     },
     "summary_detail_consistency": {
       "ran": true,
       "summary_blocks_scanned": ["callout (page 1)", "§1 thesis paragraph 1"],
       "claims_enumerated": 4,
       "findings_count": 2,
       "findings_by_severity": {
         "critical": 1,
         "important": 1,
         "suggestion": 0
       },
       "findings": [
         {
           "claim_id": 1,
           "claim_excerpt": "Gen 2: those workloads migrate.",
           "summary_location": "callout bullet 1 (page 1)",
           "detail_location": "§2.2 (Pericles.2)",
           "verdict": "CONTRADICTED",
           "severity": "critical",
           "message": "Callout assigns Pericles.3's workload-migration behavior to Pericles.2 (Gen 2). §2.2 describes Pericles.2 as the 9HP analog FE respin family with mission-tuned variants — no DSP/workload migration. §2.3 describes the 12LP+ bridge die (Pericles.3) absorbing stable DSP blocks. The migration belongs to Gen 3, not Gen 2.",
           "suggested_fix": "Either rewrite the callout bullet to say 'Gen 3: workloads migrate into 12LP+' (matching §2.3), or rewrite §2.2/§2.3 to put workload migration in Gen 2 (matching the callout). The detail-side framing is the load-bearing one — recommend correcting the callout.",
           "load_bearing_justification": "The callout is the page-1 reader-anchor; the Gen-1/Gen-2/Gen-3 generation taxonomy IS the strategic thesis. A reader who stops after the callout has the wrong mental model of the platform. Critical."
         },
         {
           "claim_id": 3,
           "claim_excerpt": "the FPGA is the measurement instrument",
           "summary_location": "callout bullet 1 (page 1)",
           "detail_location": "(absent)",
           "verdict": "ABSENT",
           "severity": "important",
           "message": "Callout asserts the FPGA's role as 'measurement instrument that tells us which compute should move into the 12LP+ chiplet ASIC' — no detailed section elaborates on the measurement methodology or what 'tells us' means operationally. Reader has no way to evaluate the claim.",
           "suggested_fix": "Either add a §2.x subsection elaborating the FPGA-as-measurement-instrument methodology, or soften the callout to remove the operational claim (e.g., 'Gen 1 platform' without the instrument framing)."
         }
       ],
       "critical_flag_candidate": true
     },
     "scope_distribution": {
       "preserve": 0,
       "expand": 4,
       "reduce": 3
     },
     "cross_thread_cite_consistency": {
       "ran": true,
       "cites_enumerated": 3,
       "findings_count": 1,
       "findings": [
         {
           "cite_text": "brasidas-synthesis/memo.2 §3.1",
           "summary_location": "§2 paragraph 3 (memo.md line 47)",
           "resolved_path": "/abs/path/to/portfolio/brasidas-synthesis.2/memo.md",
           "section_anchor": "§3.1",
           "verdict": "ANCHOR-MISSING-BUT-THREAD-PRESENT",
           "severity": "important",
           "justification": "Cited thread brasidas-synthesis resolves to brasidas-synthesis.2/ (latest version), but §3.1 anchor is not present in brasidas-synthesis.2/memo.md. The data-center disagreement framing this cite attributes to §3.1 now lives at §5.2 (likely renumbered in the brasidas-synthesis memo.1 → memo.2 revision). -1 dim 3 deduction; reviser should re-cite to §5.2."
         }
       ],
       "critical_flag_candidate": false
     },
     "rubric_overrides": {
       "ran": true,
       "memo_subtype": "synthesis-brief",
       "calibrations_applied": [
         { "dimension": 1, "text": "decision-framework — score on framework clarity + sub-recommendation sharpness, not on single ranked recommendation" },
         { "dimension": 5, "text": "defers to underlying market models — score on integration quality not on fresh sizing" },
         { "dimension": 6, "text": "defers to underlying market models — score on whether financial framing supports positioning" },
         { "dimension": 7, "text": "target length 9000-13000 words; score against declared target" }
       ],
       "target_length_present": true,
       "unknown_keys": []
     },
     "critical_flag": true,
     "critical_flag_notes": [
       { "type": "memo_image_refs_lint", "ref_lines": [41], "justification": "Pre-flight image-reference lint flagged 1 missing ref. See lint.memo_image_refs.errors_by_path for the per-ref breakdown and suggested fixes." },
       { "type": "summary_detail_consistency", "claim_id": 1, "justification": "Summary-detail consistency back-check identified a CONTRADICTED finding at critical severity: callout assigns Gen-3 behavior to Gen-2. See summary_detail_consistency.findings for details." }
     ]
   }
   ```
   ```
   - The top-level `rubric_overrides` block (issue #233 / #265) is populated from the cached `RubricOverrides` from step 4g. The block lives at the **top level** of `_summary.md` (sibling to `lint`, `render_gate`, `summary_detail_consistency`, `cross_thread_cite_consistency`, and `scope_distribution`), NOT nested under `lint` — rationale: the existing `lint` namespace is reserved for deterministic mechanical checks; `rubric_overrides` is **per-thread reviewer configuration**, not a check result. The block exists so the operator and downstream consumers can see at a glance *which* calibrations the reviewer applied to which dimensions, with the verbatim override text recorded for the audit trail (mirroring the suffix text written into `scoring.md`). Shape:
     - `ran` (`bool`): whether any rubric override was loaded. `true` when the loader returned a non-empty `RubricOverrides` (any of `memo_subtype`, `calibrations`, `target_length`, or `unknown_keys` populated); `false` when the loader returned an empty instance (no `.anvil.json`, no `rubric_overrides` block, or malformed block — see the loader's lenient-form contract).
     - `reason` (`str`, only when `ran: false`): short tag — `"no rubric_overrides block in .anvil.json"`.
     - `memo_subtype` (`str | null`, only when `ran: true`): the verbatim `memo_subtype` string from the loader, or `null` when not declared. Opaque to the reviewer logic; surfaced for operator-side audit and for future-shipped tooling (e.g., a CI hook that asserts "all synthesis-brief threads carry dim_1_calibration").
     - `calibrations_applied` (`list[dict]`, only when `ran: true`): one entry per dimension with a `dim_N_calibration` declared. Each entry is `{dimension: int (1-9), text: str}`. The `text` field is **verbatim** from the loader — the same string that was appended as a suffix to `scoring.md`. Order is by dimension number ascending (the loader's sort order). When no calibrations are declared, the list is `[]`.
     - `target_length_present` (`bool`, only when `ran: true`): `true` when the loader parsed a `rubric_overrides.target_length` block. The reviewer does NOT consume this field for dim 7 scoring (the resolved range from `_progress.json.metadata.target_length_resolved` is the dim 7 anchor per step 4); this flag is surfaced so the operator can see WHAT the loader saw. Drafter / reviser are the consumers of `rubric_overrides.target_length`; the reviewer's `_summary.md` just records its presence.
     - `unknown_keys` (`list[str]`, only when `ran: true`): forward-compat passthrough — the keys the loader did not recognize (preserved verbatim by the loader under `RubricOverrides.unknown_keys`). Surfaced here so the operator sees WHICH unrecognized keys were present without having to re-read `.anvil.json`. When all keys are recognized, the list is `[]`.
   - **The `rubric_overrides` block does NOT participate in `critical_flag`.** This is by design: calibration overrides are reviewer-configuration metadata, not a check result. The block is observational only — the load-bearing surfacing of the calibrations themselves is the `scoring.md` suffix (per step 5's calibration-suffix rules). The `_summary.md` block is the structured shadow / audit trail.
   - **Backwards-compat**: a legacy review sibling produced before this block shipped MAY omit `rubric_overrides` entirely. Downstream consumers (test suites, tooling) MUST tolerate the absence by treating it as `{ran: false, reason: "block predates issue #265"}`. New reviews produced after this contract ships SHOULD emit the block (`ran: false` with reason when no overrides; `ran: true` with the full shape when overrides are present).
   - The top-level `scope_distribution` block (issue #242, Phase A) is a count of `comments.md` entries per `scope` value. Shape:
     - `preserve` (`int`): count of `scope: preserve` comments.
     - `expand` (`int`): count of `scope: expand` comments.
     - `reduce` (`int`): count of `scope: reduce` comments.
   - The block lives at the **top level** of `_summary.md` (sibling to `lint` and `render_gate`), NOT nested under `lint` — the scope label is **reviewer-judgment metadata on each comment**, not a mechanical lint result. Same placement rationale as the `summary_detail_consistency` top-level block (issue #245): the existing `lint` namespace is reserved for deterministic mechanical checks.
   - The `scope_distribution` block is the operator-visible signal that the critic is actually surfacing both directions, not just additions. The canary's "7-of-8-additions diagnostic" (the friction case from the issue body: a strategic critic that produced 7 `scope: expand` comments and 1 `scope: reduce` comment) becomes mechanical: a review with `scope_distribution.reduce == 0` AND `dimensions.9 < 4` is **malformed** per AC 2; the reviewer SHOULD re-run.
   - **The `scope_distribution` block does NOT participate in `critical_flag` in v0** (Phase A). The block is observational: it surfaces the comment-stream balance for the operator and the reviser, but `critical_flag` continues to be driven by the existing pathway (lint errors + summary-detail consistency CONTRADICTED) only. Phase B promotion to gating behavior is a separate decision after canary consumption signal.
   - **Backwards-compat**: a legacy review sibling produced before this block shipped MAY omit `scope_distribution` entirely; downstream consumers (the reviser at #241) MUST tolerate the absence and fall back to severity-only ordering (mirrors the perspective-sibling backwards-compat pattern). New reviews produced after this contract ships MUST emit the block.
   - When `lint.memo_image_refs.errors > 0`, set `critical_flag: true` and append a `critical_flag_notes` entry of type `memo_image_refs_lint` naming the affected source lines. This flag lives under the "fourth-category critical flag" bucket per `rubric.md`'s open-ended "any deal-breaker a sophisticated reader would catch" slot — a memo whose PDF renders with broken-image placeholders is not ship-ready regardless of its prose.
   - The `lint.refs_pdf_extraction` block mirrors the `lint.memo_image_refs` shape and records the PDF refs back-check path's per-run outcome (issue #167). Shape:
     - `ran` (`bool`): whether the PDF text extraction path ran. `True` when `refs_pdf.check_pdftotext_available()` returned `True` AND at least one `<thread>/refs/*.pdf` was present; `False` otherwise (binary absent OR no PDF refs).
     - `reason` (`str`, only when `ran: false`): short tag — `"pdftotext not available"` when the binary is absent, or `"no PDF refs"` when the binary IS available but `<thread>/refs/` contains no `.pdf` files.
     - `remediation` (`str`, only when `ran: false` AND `reason == "pdftotext not available"`): the verbatim `refs_pdf.PDFTOTEXT_REMEDIATION` install-story string, so the consumer sees how to enable the back-check on the next run.
     - `per_file` (`list[dict]`, only when `ran: true`): one entry per `.pdf` ref with `path` (relative to `<thread>/refs/`), `extracted_chars` (length of the extracted text, `0` for image-based / scanned PDFs), and an optional `note` (e.g., `"image-based — likely scanned; would need OCR for back-check"`).
   - **The `refs_pdf_extraction` block is info-level only.** It NEVER sets `critical_flag` — a missing optional binary is not a deal-breaker, and an image-only PDF is also not a deal-breaker (the deduction logic, if any, lives in the `comments.md` verdict-tag entries under dim 3, not here).
   - The top-level `render_gate` block (Phase 4 / issue #196) mirrors the deck-side `_summary.md.lint` block shape (`commands/deck-review.md` step 9 — pre-flight `marp_lint` findings surfaced for the reviser). The memo block is the post-render analog: each finding is one entry of the `GateResult.findings` list emitted by `render_gate.gate(kind="memo")` from PR #185, written to `_progress.json.render_gate` by `memo-render` (PR #193) and read here at step 4c. Shape:
     - `ran` (`bool`): whether `_progress.json.render_gate` was present and parseable. `True` when the memo was rendered by `memo-render`; `False` otherwise (legal pre-Phase-3 state, or `memo-render` not on PATH, or `memo-render` skipped via consumer config).
     - `reason` (`str`, only when `ran: false`): short tag — `"no render_gate block in _progress.json"` (the common pre-Phase-3 / unrendered case).
     - `pages` (`int | null`, only when `ran: true`): the rendered PDF page count from `pdfinfo`. `null` when `pdfinfo` was absent on PATH and the gate could not introspect; otherwise the integer page count of `memo.pdf`.
     - `page_cap` (`int | null`, only when `ran: true`): the page cap passed to the gate (memo gate uses target_length-derived range, not page_cap — typically `null`).
     - `compile_status` (`str`, only when `ran: true`): one of `"ok"` / `"failed"` / `"unavailable"` / `"skipped"` per `anvil/lib/render_gate.py`'s `COMPILE_*` constants.
     - `pass` (`bool`, only when `ran: true`): the gate's overall pass/fail signal. `False` when any of the five memo dimensions has an error finding.
     - `errors` / `warnings` / `infos` (`int`, only when `ran: true`): counts of findings by severity, aggregated across all five memo gate dimensions.
     - `findings_by_dimension` (`dict[str, list[dict]]`, only when `ran: true`): findings keyed by gate dimension name (`memo_compile_success` / `memo_page_fit` / `memo_overfull_check` / `memo_image_refs_exist` / `memo_placeholder_scan`). Each entry is `{severity, message, location}` per `GateFinding.to_dict()`. The severities are surfaced verbatim from the gate; the reviewer does NOT re-derive them (the gate's classification — `memo_page_fit` error when `target_length.pages` is declared, warning when `target_length.words` is declared — is the contract per step 4c).
     - `reasons` (`list[str]`, only when `ran: true`): the verbatim `reasons` list from `GateResult.to_json()`, one informational reason per gate dimension that ran.
   - **The `render_gate` block is non-blocking and info-level for the verdict.** It NEVER sets `critical_flag` and NEVER forces `advance: false`. Render-gate findings surface for the operator and inform the dim 7 justification per `rubric.md` §"Length targets" §"Word count is primary; rendered page count is second-layer advisory", but the verdict logic at step 7 (`advance = (total >= 35) AND (no critical flags) AND (lint.errors == 0)`) does NOT consume render-gate findings. A memo that scores ≥35 with no critical flags is advance-eligible even when `render_gate.pass == false` — word count remains the primary length signal and the rendered page count is advisory.
   - **The `memo_image_refs_exist` finding in `render_gate.findings_by_dimension`** is the post-render catch (refs that exist on disk but pandoc's resolver flagged, or symlink / case edge cases), distinct from the source-side `lint.memo_image_refs` block at step 4b. Both blocks are emitted (one per-step). When the source-side lint at step 4b already flagged a broken ref (the common case), the post-render gate's finding for the same ref is informational redundancy — the operator already has the actionable signal from `lint.memo_image_refs.errors_by_path`. The post-render block's purpose is the edge-case catch (pandoc resolver disagreed with the heuristic).
   - The `lint.memo_deck_parity` block (issue #215, Phase A) is populated from the cached `LintResult` returned by step 4d. When the lint skipped (no deck sibling discoverable), the block shape is `{ "ran": false, "deck_sibling": null, "reason": "no deck sibling found at portfolio root; parity check inactive", "warnings": 0, "infos": 0, "only_in_memo": [], "only_in_deck": [], "warnings_by_token": [], "infos_by_token": [] }`. The `ran: false` skip path MUST be recorded — the operator should see WHY the parity check did not fire (same skip-reason convention as `refs_pdf_extraction` and the deck-side's `lint.deck_memo_parity`).
   - **The `lint.memo_deck_parity` block does NOT participate in `critical_flag` in v0** (Phase A ships warning-only). The block is observational: it surfaces drift in `findings.md` and the operator's revision priorities, but `critical_flag` continues to be driven by `lint.memo_image_refs.errors > 0` only (per the verdict logic at step 7, which is byte-identical to a thread without the parity lint enabled). Phase B promotion to error severity (and therefore `advance: false`-gating) is a separate decision deferred per the issue body's Phase A / Phase B contract.
   - **Findings subsection (always emitted)**: write a `## Parity-lint findings (memo↔deck, optional)` subsection into `findings.md` (the review sibling's findings document, sibling to `comments.md`). The subsection is **always present** (subsection emitted even when the lint skipped) so the operator sees WHY the check did or did not fire. v0 ships warning-only — entries surface drift but do NOT block advance. Three shapes:

     ```
     ## Parity-lint findings (memo↔deck, optional)

     Each entry comes from the memo↔deck parity lint (step 4d). v0 (Phase A) ships at **warning severity** — entries surface drift in shared hard claims (money, percentages, dates / quarters / FY, named months + year, ALL-CAPS acronyms, unit-bearing integers) but do NOT contribute to `lint_critical_flag` and do NOT block advance. Phase B promotion to error severity is a separate decision after 2–4 weeks of canary consumption signal.

     1. **[warning]** only_in_deck (deck line 31): Hard claim `50-60%` appears in deck but not in the sibling memo. Either reconcile on next `memo-revise`, document the deliberate divergence with `<!-- anvil-lint-disable: memo_deck_parity -->`, or accept the divergence (warning only in v0).
     ```

     Or, when the parity check was skipped (no deck sibling discoverable at the portfolio root):

     ```
     ## Parity-lint findings (memo↔deck, optional)

     _Skipped: no deck sibling found at portfolio root; parity check inactive._

     Deck sibling discovered: null
     ```

     Or, when the parity check ran cleanly (no divergences):

     ```
     ## Parity-lint findings (memo↔deck, optional)

     _No parity-lint findings._

     Deck sibling discovered: /abs/path/to/<thread>.{M}/
     ```
   - The top-level `summary_detail_consistency` block (issue #245, Phase A) is populated from the cached `summary_detail_block` returned by step 4e. The block lives at the **top level** of `_summary.md` (sibling to the existing `lint` and `render_gate` top-level blocks), **NOT nested under `lint`** — rationale: the existing `lint` namespace is reserved for **deterministic mechanical checks** (`memo_image_refs`, `refs_pdf_extraction`, `memo_deck_parity`); the summary-detail back-check is **reviewer judgment**, not a mechanical lint, and naming it `lint.summary_detail_consistency` would misrepresent its character. The top-level placement matches the §"Schema notes" framing in the issue #245 curation. Shape:
     - `ran` (`bool`): whether the back-check ran. `True` when the reviewer identified at least one summary block (callout / abstract / TL;DR / thesis block / "what we believe" frontmatter) to scan; `False` when no summary block was present (short memos without callouts/abstracts).
     - `reason` (`str`, only when `ran: false`): short tag — `"no callout / abstract / thesis block identified in memo.md"`. The reviewer is required to record `ran: false` explicitly rather than omitting the block (same convention as `lint.refs_pdf_extraction` and `lint.memo_deck_parity`).
     - `summary_blocks_scanned` (`list[str]`, only when `ran: true`): descriptive labels for each scanned block (e.g., `["callout (page 1)", "§1 thesis paragraph 1"]`).
     - `claims_enumerated` (`int`, only when `ran: true`): total count of load-bearing summary claims identified per `rubric.md` §"Summary-detail consistency" §"What counts as a load-bearing summary claim".
     - `findings_count` (`int`, only when `ran: true`): total count of non-`MATCH` findings emitted.
     - `findings_by_severity` (`dict[str, int]`, only when `ran: true`): count of findings per severity bucket, keyed by `"critical"` / `"important"` / `"suggestion"`. The vocabulary deliberately diverges from the existing `lint.*` severity vocabulary (`error` / `warning` / `info`) — see `rubric.md` §"Summary-detail consistency" §"Severity ladder" — to signal the different character of the check (judgment vs. mechanical). Implementers SHOULD NOT normalize across vocabularies.
     - `findings` (`list[dict]`, only when `ran: true`): one entry per non-`MATCH` finding. Per-finding fields:
       - `claim_id` (`int`): the 1-based index of the load-bearing summary claim.
       - `claim_excerpt` (`str`): a short excerpt of the summary claim text (e.g., `"Gen 2: those workloads migrate."`).
       - `summary_location` (`str`): where the claim was found (e.g., `"callout bullet 1 (page 1)"`, `"§1 thesis paragraph 1"`).
       - `detail_location` (`str`): the section path where the elaboration was found, or `"(absent)"` when no detail section elaborates the claim.
       - `verdict` (`str`): one of `"ABSENT"` / `"CONTRADICTED"` / `"DIVERGENT"`. (`"MATCH"` is never emitted — matches are observed silently.)
       - `severity` (`str`): one of `"critical"` / `"important"` / `"suggestion"` per the rubric severity ladder.
       - `message` (`str`): a human-readable diagnostic describing the mismatch and naming the load-bearing nouns / numbers / actors involved.
       - `suggested_fix` (`str`): a concrete reviser-actionable fix — typically "rewrite the callout to match §N" OR "rewrite §N to match the callout" with a justification for which framing is load-bearing.
       - `load_bearing_justification` (`str`, only when `severity == "critical"`): a one- or two-sentence justification for why the finding rises to critical severity (e.g., "The callout is the page-1 reader-anchor; a reader who stops after the callout has the wrong mental model.").
     - `critical_flag_candidate` (`bool`, only when `ran: true`): convenience flag. MUST equal `any(f.severity == "critical" and f.verdict == "CONTRADICTED" for f in findings)`. Implementer convention; not duplicated state — the verdict aggregator at step 7 cheaply reads this field to test whether any finding requires a critical-flag entry.
   - **The `summary_detail_consistency` block plugs into `critical_flag` via the existing critical-flag-candidate pathway** (issue #245, Phase A). When `summary_detail_consistency.critical_flag_candidate == true`, the top-level `critical_flag` is set to `true` AND a `critical_flag_notes` entry of type `summary_detail_consistency` is appended with the claim excerpt + contradicting detail location as the justification (mirrors the `memo_image_refs_lint` type at step 4b). `ABSENT` and `DIVERGENT` findings at `important` / `suggestion` severity are observational only — they surface in `findings.md` and the verdict's revision priorities but do NOT contribute to `critical_flag`.
   - **Findings subsection (always emitted)**: write a `## Summary-detail consistency findings` subsection into `findings.md` (sibling to the existing `## Parity-lint findings (memo↔deck, optional)` subsection). The subsection is **always present** (emitted even when the back-check was skipped via `ran: false`) so the operator sees WHY the check did or did not fire. Three shapes:

     When findings are present:

     ```
     ## Summary-detail consistency findings

     Each entry comes from the summary-detail consistency back-check (step 4e). The check is reviewer-judgment (Phase A: no Python detector); see `rubric.md` §"Summary-detail consistency" for the verdict-tag rubric (`ABSENT` / `CONTRADICTED` / `DIVERGENT`) and severity ladder (`critical` / `important` / `suggestion`). A `CONTRADICTED` finding at `critical` severity contributes to `verdict.md`'s critical-flag list; `ABSENT` and `DIVERGENT` findings at `important` / `suggestion` severity are observational.

     Summary blocks scanned: callout (page 1), §1 thesis paragraph 1
     Claims enumerated: 4

     1. **[critical]** CONTRADICTED — claim 1 (callout bullet 1, page 1) ↔ §2.2 (Pericles.2): "Gen 2: those workloads migrate." Callout assigns Pericles.3's workload-migration behavior to Pericles.2 (Gen 2). §2.2 describes Pericles.2 as the 9HP analog FE respin family with mission-tuned variants — no DSP/workload migration. §2.3 describes the 12LP+ bridge die (Pericles.3) absorbing stable DSP blocks. The migration belongs to Gen 3, not Gen 2.
        Suggested fix: Either rewrite the callout bullet to say 'Gen 3: workloads migrate into 12LP+' (matching §2.3), or rewrite §2.2/§2.3 to put workload migration in Gen 2 (matching the callout). The detail-side framing is the load-bearing one — recommend correcting the callout.

     2. **[important]** ABSENT — claim 3 (callout bullet 1, page 1) ↔ (absent): "the FPGA is the measurement instrument" Callout asserts the FPGA's role as 'measurement instrument that tells us which compute should move into the 12LP+ chiplet ASIC' — no detailed section elaborates on the measurement methodology or what 'tells us' means operationally. Reader has no way to evaluate the claim.
        Suggested fix: Either add a §2.x subsection elaborating the FPGA-as-measurement-instrument methodology, or soften the callout to remove the operational claim (e.g., 'Gen 1 platform' without the instrument framing).
     ```

     Or, when the back-check was skipped (no summary block to scan):

     ```
     ## Summary-detail consistency findings

     _Skipped: no callout / abstract / thesis block identified in memo.md; summary-detail consistency check inactive._
     ```

     Or, when the back-check ran cleanly (no findings, all `MATCH`):

     ```
     ## Summary-detail consistency findings

     _No summary-detail consistency findings._

     Summary blocks scanned: callout (page 1), §1 thesis paragraph 1
     Claims enumerated: 4
     ```
   - The top-level `cross_thread_cite_consistency` block (issue #236, Phase A) is populated from the cached `cross_thread_cite_block` returned by step 4f. The block lives at the **top level** of `_summary.md` (sibling to the existing `lint`, `render_gate`, `summary_detail_consistency`, and `scope_distribution` top-level blocks), **NOT nested under `lint`** — rationale: the existing `lint` namespace is reserved for **deterministic mechanical checks** (`memo_image_refs`, `refs_pdf_extraction`, `memo_deck_parity`); the cross-thread cite back-check is **reviewer judgment**, not a mechanical lint, and naming it `lint.cross_thread_cite_consistency` would misrepresent its character. The top-level placement matches the §"Summary-detail consistency" §"Schema notes" framing (issue #245) and the back-check triangle composition contract (`rubric.md` §"Cross-thread citation back-check (dim 3)" §"Related"). Shape:
     - `ran` (`bool`): whether the back-check ran. `True` when at least one cross-thread cite was identified in `memo.md`; `False` when no cross-thread cites were found (the memo did not reference any other anvil threads).
     - `reason` (`str`, only when `ran: false`): short tag — `"no cross-thread citations identified in memo.md"`. The reviewer is required to record `ran: false` explicitly rather than omitting the block (same convention as `lint.refs_pdf_extraction`, `lint.memo_deck_parity`, and `summary_detail_consistency`).
     - `cites_enumerated` (`int`, only when `ran: true`): total count of cross-thread cites identified per `rubric.md` §"Cross-thread citation back-check (dim 3)" §"What counts as a cross-thread citation" (four cite shapes — literal-path / short-form / relative-path / backtick-wrapped).
     - `findings_count` (`int`, only when `ran: true`): total count of non-`ANCHOR-FOUND` findings emitted.
     - `findings` (`list[dict]`, only when `ran: true`): one entry per non-`ANCHOR-FOUND` finding. Per-finding fields:
       - `cite_text` (`str`): the verbatim cite text as it appears in `memo.md` (e.g., `"brasidas-synthesis/memo.2 §3.1"`).
       - `summary_location` (`str`): where the cite was found in `memo.md` (e.g., `"§2 paragraph 3 (memo.md line 47)"`).
       - `resolved_path` (`str`): the absolute path the cite resolves to (e.g., `"<portfolio_root>/brasidas-synthesis.2/memo.md"`), or a short tag like `"(thread not found)"` when the cited thread does not resolve.
       - `section_anchor` (`str`): the section anchor referenced by the cite (e.g., `"§3.1"`).
       - `verdict` (`str`): one of `"ANCHOR-FOUND"` / `"ANCHOR-MISSING-BUT-THREAD-PRESENT"` / `"ANCHOR-CONTRADICTED"` / `"THREAD-NOT-FOUND"`. (`"ANCHOR-FOUND"` is never emitted in `findings` — successful resolutions are observed silently; only non-`ANCHOR-FOUND` findings appear in the list.)
       - `severity` (`str`): one of `"critical"` / `"important"` / `"suggestion"` per the rubric severity ladder.
       - `justification` (`str`): a human-readable diagnostic naming the cited thread, the resolution outcome, the dim 3 deduction, and the reviser-actionable next step.
     - `critical_flag_candidate` (`bool`, only when `ran: true`): convenience flag. MUST equal `any(f.severity == "critical" and f.verdict == "ANCHOR-CONTRADICTED" for f in findings)`. Implementer convention; not duplicated state — the verdict aggregator at step 7 cheaply reads this field to test whether any finding requires a critical-flag entry.
   - **The `cross_thread_cite_consistency` block plugs into `critical_flag` via the existing critical-flag-candidate pathway** (issue #236, Phase A). When `cross_thread_cite_consistency.critical_flag_candidate == true`, the top-level `critical_flag` is set to `true` AND a `critical_flag_notes` entry of type `cross_thread_cite_consistency` is appended with the cite text + contradicting cited-section location as the justification (mirrors the `memo_image_refs_lint` type at step 4b and the `summary_detail_consistency` type at step 4e). `ANCHOR-MISSING-BUT-THREAD-PRESENT` and `THREAD-NOT-FOUND` findings at `important` severity are observational only — they surface in `findings.md` and the verdict's revision priorities but do NOT contribute to `critical_flag`.
   - **Findings subsection (always emitted)**: write a `## Cross-thread cite consistency findings` subsection into `findings.md` (sibling to the existing `## Parity-lint findings (memo↔deck, optional)` and `## Summary-detail consistency findings` subsections). The subsection is **always present** (emitted even when the back-check was skipped via `ran: false`) so the operator sees WHY the check did or did not fire. Three shapes:

     When findings are present:

     ```
     ## Cross-thread cite consistency findings

     Each entry comes from the cross-thread cite consistency back-check (step 4f). The check is reviewer-judgment (Phase A: no Python detector); see `rubric.md` §"Cross-thread citation back-check (dim 3)" for the verdict-tag rubric (`ANCHOR-FOUND` / `ANCHOR-MISSING-BUT-THREAD-PRESENT` / `ANCHOR-CONTRADICTED` / `THREAD-NOT-FOUND`) and severity ladder (`critical` / `important` / `suggestion`). An `ANCHOR-CONTRADICTED` finding at `critical` severity contributes to `verdict.md`'s critical-flag list; `ANCHOR-MISSING-BUT-THREAD-PRESENT` and `THREAD-NOT-FOUND` findings at `important` severity are observational (per-instance dim 3 deduction is the natural surface).

     Cites enumerated: 3

     1. **[important]** ANCHOR-MISSING-BUT-THREAD-PRESENT — `brasidas-synthesis/memo.2 §3.1` (memo.md §2 paragraph 3, line 47) ↔ `/abs/path/to/portfolio/brasidas-synthesis.2/memo.md`: cited thread brasidas-synthesis resolves to brasidas-synthesis.2/ (latest version), but §3.1 anchor is not present in brasidas-synthesis.2/memo.md. The data-center disagreement framing this cite attributes to §3.1 now lives at §5.2 (likely renumbered in the brasidas-synthesis memo.1 → memo.2 revision). -1 dim 3 deduction; reviser should re-cite to §5.2.
     ```

     Or, when the back-check was skipped (no cross-thread cites in the memo):

     ```
     ## Cross-thread cite consistency findings

     _Skipped: no cross-thread citations identified in memo.md; cross-thread cite consistency check inactive._
     ```

     Or, when the back-check ran cleanly (no findings, all `ANCHOR-FOUND`):

     ```
     ## Cross-thread cite consistency findings

     _No cross-thread cite consistency findings._

     Cites enumerated: 3
     ```
10. **Write `verdict.md`** in the format specified in `rubric.md`:
    - Total: `XX / 44`
    - Decision: `advance: true` or `advance: false`
    - Critical flags (if any) — include `Memo image refs (lint)` when `lint.memo_image_refs.errors > 0`; include `Summary-detail consistency: CONTRADICTED` when `summary_detail_consistency.critical_flag_candidate == true` (issue #245), with the claim excerpt + contradicting detail location as the one-paragraph justification; include `Cross-thread cite: ANCHOR-CONTRADICTED` when `cross_thread_cite_consistency.critical_flag_candidate == true` (issue #236), with the cite text + contradicting cited-section location as the one-paragraph justification.
    - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
    - Top 3 revision priorities (if `advance: false`) — when the lint raised errors, the first priority MUST be "Fix the N missing image references (see `_summary.md` lint block)". When the summary-detail consistency back-check raised a `CONTRADICTED` / `critical` finding (issue #245), the top-3 revision priorities MUST include "Reconcile callout/abstract with detailed sections (see `_summary.md.summary_detail_consistency.findings[critical=true]`)" as priority #1 — the contradicting summary is the page-1 reader-anchor and fixing it precedes other prose work. When the cross-thread cite back-check raised an `ANCHOR-CONTRADICTED` / `critical` finding (issue #236), the top-3 revision priorities MUST include "Reconcile cross-thread citation against cited thread's latest version (see `_summary.md.cross_thread_cite_consistency.findings[critical=true]`)" — a cite that materially contradicts the cited thread's content propagates the factual error and must be fixed before the memo advances.
    - **`scope: reduce` first-priority rule (issue #242 AC 4)**: when **dim 9 scored below full weight (< 4/4)**, the top-3 revision priorities MUST include at least one `scope: reduce` priority citing the specific dim 9 anti-pattern instance the reviser should act on first (e.g., "Collapse §4.2's three-paragraph hedge on PAM4/FEC into one sentence — see `comments.md` § scope: reduce"). This mirrors the existing critical-flag-driven "fix the N missing image references" first-priority precedent and the summary-detail-consistency CONTRADICTED first-priority precedent: when a structural countervailing pressure has fired (dim 9 deduction here, lint error in the precedent, CONTRADICTED finding in the #245 precedent), the verdict's revision priorities explicitly surface it so the reviser does not drown the trim directive in `scope: expand` noise. The `scope: reduce` priority is independent of and additive to the lint / summary-detail-consistency priorities: when multiple fire on the same review, all of them appear in the top-3 (the rubric's "Top 3 revision priorities" cap is the budget, not the count). When dim 9 scored 4/4 (full weight) the `scope: reduce` priority is inactive — the rubric judged the rhetorical economy already converged.
11. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
12. **Report**: print the path to the review dir and a one-line status (e.g., `Reviewed acme-seed.1 → acme-seed.1.review/ (30/44, advance: false, 0 critical flags)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output. Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Notes for the reviewer agent

- **Be honest**, not encouraging. The skill is not "polish the memo." It is "would I stake my professional reputation on this recommendation?" If the answer is no, score accordingly.
- **Distinguish assertion from research.** A claim without a source is a hypothesis. Most early-draft memos contain too many hypotheses dressed as facts; this is the most common reason for low Evidence Quality scores.
- **Critical flags are not bonus points.** They are statements that the memo has a defect serious enough that a sophisticated reader would stop reading. Use sparingly but use them when warranted.
- **Comments should be actionable.** "Tighten this section" is not useful. "Replace the unsourced TAM figure with a citation or remove the claim" is useful.

## `_progress.json` and `_meta.json` snippets (review sibling)

This command writes the critic-sibling shape documented in `anvil/lib/snippets/progress.md` (with `for_version` naming the version reviewed). Specifically:

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

> Note: using `review` as the phase name here is the documented v0 status quo; new critics should use their own tag per `anvil/lib/snippets/progress.md` (phase-name normalization across skills is deferred under #21 item 11).

And the companion `_meta.json` declaring the scorecard kind (see `anvil/lib/snippets/scorecard_kind.md`):

```json
{
  "critic": "review",
  "role": "memo-review.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict"
}
```

Merge rule (shallow): preserve fields not touched by this command. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
