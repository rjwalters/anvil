---
name: deck-review
description: General reviewer command for the deck skill. Scores rubric dimensions 2, 5, 6 (problem clarity, traction/proof, team credibility) and emits the full critic-sibling schema plus a verdict.md. The verdict aggregates sibling critic outputs against the /44 rubric (≥39 advance threshold).
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

Total ownership: 14/44. Other dimensions are scored by specialist critics (`deck-narrative` for 1+7+9, `deck-market` for 3+4, `deck-design` for 8) and are left `null` in `_summary.md`. Note: post-#357, `deck-narrative` owns dim 9 *Rhetorical economy* in addition to dims 1 and 7 — the arc/ask critic's natural turf includes "could a busy investor extract the ask in 90 seconds?".

The general reviewer is also responsible for writing the **aggregated `verdict.md`** — the canonical artifact the orchestrator reads to decide advance/block. The aggregation reads sibling critics if present at the same `<thread>.{N}.<tag>/` and combines per-dimension scores (mean of non-null) and critical flags (logical OR).

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md`.
- **Rubric**: `anvil/skills/deck/rubric.md` (9 dimensions, /44, ≥39 threshold, four critical flags).
- **Optional consumer override**: `.anvil/skills/deck/rubric.overrides.md`.
- **Sibling critics at same `N`** (read but not modified): `<thread>.{N}.narrative/_summary.md`, `<thread>.{N}.market/_summary.md`, `<thread>.{N}.design/_summary.md`. These contribute to the aggregated `verdict.md` if present.
- **Optional `--rescore-mode <rescore-id>` flag** (issue #368): when set, the reviewer re-routes its staged_sidecar output from `<thread>.{N}.review/` to `<thread>.{N}.review.rescore-<rescore-id>/`, re-targets the prior-review lookup to `<thread>.{N}.review/` (NOT `<thread>.{N-1}.review/`) since the current version's legacy review IS the prior review for a rescore pass, and stamps `_meta.json` with `rescore_state: "completed"` + `rescore_id: "<rescore-id>"` (overwriting any placeholder `rescore_state: "scheduled"` left behind by `anvil:rubric-rebackport --rescore --apply`). Specialist critics (`deck-narrative`, `deck-market`, `deck-design`, `deck-vision`) are NOT rescored by this flag in v0 — only the aggregator `deck-review` rescores; specialist rescoring is a separate follow-on per the deck-review split-init precedent in PR #363. When the flag is unset, behavior is byte-identical to the default review path. See steps 3 + 4 for the full re-routing contract.

## Outputs

```
<thread>.{N}.review/
  verdict.md         Aggregated decision + total /44 + critical flags + top revision priorities
                     (carries `## Rubric version transition` subsection when prior rubric differs)
  scoring.md         Per-dimension score (owned dims only) + 1–3 sentence justification each
  comments.md        Slide-level comments keyed to deck.md slides
  _summary.md        9-dim partial scorecard (owned dims scored; others null) + critical-flag bool
                     + top-level `rubric` block (id, total, advance_threshold, dimensions)
  findings.md        Itemized findings: severity, slide ref, rationale, suggested fix
                     + "Rubric version transition" subsection (conditional, when prior rubric differs)
  _meta.json         { "critic": "review", "role": "deck-review.md", "started": "<ISO>", "finished": "<ISO>", "model": "<id>",
                       "scorecard_kind": "human-verdict", "rubric_id": "anvil-deck-v2",
                       "rubric_total": 44, "advance_threshold": 39 }
  _progress.json     Phase state for the review (phase: review)
```

**Atomicity** (issue #350, #376): the review sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The required files (`verdict.md`, `scoring.md`, `comments.md`, `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.review.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.review/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.review.tmp/` dir on disk that the next invocation's `cleanup_one_staging(<thread>.{N}.review)` per-critic sweep removes; the final-named dir never exists in partial form. Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md`. Then **sweep a stale staging dir from a prior interrupt of THIS critic on THIS version** by invoking `anvil/lib/sidecar.py::cleanup_one_staging(<thread>.{N}.review)` (the per-critic, parallel-safe sweep — issue #376). This removes ONLY a leftover `.<thread>.{N}.review.tmp/` from a previously-killed run of this same critic on THIS version. Sibling critics' in-flight staging dirs under the same portfolio root are NOT touched (issue #350, #376). The sweep is idempotent and logs at INFO level when it removes a dir. If `<thread>.{N}.review/` exists (the atomic-rename contract guarantees the dir only exists when complete), the review is complete — exit early with a notice (idempotent).
2. **Resume check**: per the staged-sidecar shape introduced in issue #350, a partial review left behind by a mid-cycle interrupt manifests as a leading-dot `.<thread>.{N}.review.tmp/` directory (NOT as a partially-filled `<thread>.{N}.review/`). The sweep in step 1 has already removed any such partial. Backwards-compat: if a legacy pre-#350 `<thread>.{N}.review/` exists WITHOUT `verdict.md`, delete the dir and re-review.
3. **Open the staged sidecar** for the review dir by invoking the context manager `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.review, required_files=["verdict.md", "scoring.md", "comments.md", "_summary.md", "findings.md", "_meta.json", "_progress.json"])`. Every file write from this step through the final `_progress.json` / `_meta.json` updates MUST land **inside the yielded staging directory** (the path of the shape `.<thread>.{N}.review.tmp/`), NOT inside the final `<thread>.{N}.review/` path. On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name (issue #350). Then, **inside the staging dir**, initialize `_progress.json`: `phases.review.state = in_progress`, `phases.review.started = <ISO>`.
4. **Initialize `_meta.json`** with `critic: "review"`, `role: "deck-review.md"`, `started: <ISO>`, `model: <id>`, `scorecard_kind: "human-verdict"`, `rubric_id: "anvil-deck-v2"`, `rubric_total: 44`, and `advance_threshold: 39` (per `anvil/lib/snippets/scorecard_kind.md` §"The discriminator" — the three rubric-stamping fields are required for new reviews per issue #346; `"anvil-deck-v2"` is the deck skill's current /44 rubric identifier per `anvil/skills/deck/rubric.md` line 3). The rubric-stamping fields let downstream consumers compare scores apples-to-apples across the `/40 → /44` migration without re-reading the skill's current `rubric.md`. Also load the **prior review sibling** at `<thread>.{N-1}.review/_meta.json` when present and cache its `rubric_id` value as `prior_rubric_id` (or `None` when the prior sibling is absent — first iteration — or lacks the field — legacy pre-#346 review). The cached `prior_rubric_id` feeds the `_summary.md.rubric` block at step 9 + the `findings.md` rubric-transition subsection (step 11b) when the prior rubric differs from the current `"anvil-deck-v2"`. Specialist critics (`deck-narrative`, `deck-market`, `deck-design`, `deck-vision`) inherit the same `rubric_id` via their own `_meta.json` if they ship updated `<critic>-review.md`s in follow-up issues; in this PR only `deck-review` (the aggregator) stamps. The aggregator at step 12 reads sibling scores and stamps the aggregated verdict, which is sufficient for the canary failure mode this contract exists to close.

   **When `--rescore-mode <rescore-id>` is set** (issue #368) — the rebackport reviewer-hook contract:
   - **Re-derive `final_dir`** (from step 3) from `<thread>.{N}.review` to `<thread>.{N}.review.rescore-<rescore-id>`. The staging directory derived by `anvil/lib/sidecar.py::staging_path_for(final_dir)` correspondingly becomes `.<thread>.{N}.review.rescore-<rescore-id>.tmp/` — no separate code path is needed; the same `staged_sidecar(final_dir=...)` call works with the rescore sidecar path. The deck-review aggregator's split-init shape (step 3 = staged_sidecar + `_progress.json`; step 4 = `_meta.json`) is preserved verbatim — only the path target changes.
   - **Re-target the prior-review lookup to `<thread>.{N}.review/_meta.json`** (NOT `<thread>.{N-1}.review/_meta.json`). Under rescore mode, the legacy review at `<thread>.{N}.review/` IS the prior review — the rescore is re-scoring the SAME version's body against an updated rubric, not advancing to a new version. Cache its `rubric_id` value as `prior_rubric_id` (or fall back to `--legacy-rubric` from the rebackport tool when the legacy review lacks the field — pre-#346).
   - **Stamp `_meta.json` with `rescore_state: "completed"` and `rescore_id: "<rescore-id>"`** in addition to the standard rubric-stamping fields. The placeholder `_meta.json` left behind by `anvil:rubric-rebackport --rescore --apply` carries `rescore_state: "scheduled"`; this reviewer overwrites it with `"completed"` once the full review (verdict.md / scoring.md / comments.md / _summary.md / findings.md) has landed inside the staging dir. The `rescore_source: "anvil:rubric-rebackport"` field from the placeholder is preserved (or added if absent).
   - **All other behavior is unchanged** — same scoring, same aggregated verdict, same `findings.md` emission, same `_summary.md.rubric` block (now carrying the legacy review's rubric as `prior_rubric_id`). The specialist critic siblings (`<thread>.{N}.narrative/`, `<thread>.{N}.market/`, `<thread>.{N}.design/`, `<thread>.{N}.vision/`) are read for aggregation but are NOT rescored in v0 — only this aggregator rescores. Specialist rescoring is a separate follow-on. The legacy `<thread>.{N}.review/` dir is NEVER mutated — the rescore is a side-car write only.
   - **When `--rescore-mode` is unset**, the steps above DO NOT fire and the review path is byte-identical to the default behavior documented in the rest of this step and step 3.
5. **Read inputs**:
   - `<thread>.{N}/deck.md` (slide source) + `speaker-notes.md`.
   - `<thread>/BRIEF.md` (to ground claims — every traction number on a slide should trace to the brief).
   - Optionally `<thread>.{N}/figures/` for sanity-checking diagrams.
   - Sibling critic `_summary.md` files at the same `N` (if they exist), for verdict aggregation.
5b. **Run pre-flight overflow lint (source-side)**:
   - Invoke `anvil.lib.marp_lint`'s `lint_deck(<thread>.{N}/deck.md)` as a Python import — NOT as a filesystem path. The canonical consumer invocation is:
     ```bash
     uv run --project .anvil python -c "from anvil.lib.marp_lint import lint_deck; print(lint_deck('<thread>.{N}/deck.md'))"
     ```
     The module resolves through the importable `anvil/` package mirror at `.anvil/anvil/lib/marp_lint.py` (post-#230); the legacy `.anvil/lib/` filesystem path no longer exists. This is a Python-stdlib heuristic port of marp-vscode's `slide-content-overflow` diagnostic (see the module docstring for the upstream SHA pin and the per-slide `<!-- anvil-lint-disable: slide-content-overflow -->` escape hatch).
   - The call returns a `LintResult` with `errors: list[Finding]`, `warnings: list[Finding]`, and `infos: list[Finding]`. Each `Finding` has `slide` (1-based slide number), `line` (1-based source line), `rule`, `severity`, and `message`.
   - The lint is **review-phase only** — drafter, auditor, figurer, and the specialist critics (`deck-narrative`, `deck-market`, `deck-design`) do not invoke it. The drafter is intentionally allowed to produce an overflowing slide so the reviser sees the failure mode (issue #31, AC6).
   - **On `ImportError` / `ModuleNotFoundError`** (the module is not importable — e.g., a broken consumer install where `.anvil/anvil/lib/marp_lint.py` is missing or `uv sync` was never run): the reviewer MUST NOT silently skip. Record a single info-level entry in `findings.md` § Lint findings of the form `lint=unavailable (module not importable: <ImportError message>)` and set `lint.ran = false` + `lint.reason = "<ImportError message>"` in the `_summary.md.lint` block. The verdict proceeds without the lint contributing to `lint_critical_flag` — but the operator sees WHY the check did not fire, instead of a silent drop (issue #375).
   - Cache the `LintResult` for the `_summary.md` and `findings.md` writes below; cache `lint.errors > 0` as `lint_critical_flag` for the verdict logic.
5c. **Run silent-Marp-auto-shrink lint (post-render, optional)** — issue #102 / #100b:
   - Invoke `anvil.skills.deck.lib.auto_shrink_detector`'s `detect_auto_shrink(<thread>.{N}/deck.pdf, <thread>.{N}/deck.md)` as a Python import — NOT as a filesystem path. The canonical consumer invocation is `uv run --project .anvil python -c "from anvil.skills.deck.lib.auto_shrink_detector import detect_auto_shrink; ..."`. The module resolves through the importable mirror at `.anvil/anvil/skills/deck/lib/auto_shrink_detector.py` (post-#230). The detector reads the rendered PNGs (reuses `<thread>.{N}.vision/slides/` if the vision critic already populated it; otherwise renders fresh via `anvil.lib.render.render_pdf_to_pngs`), computes a per-page content bbox by sampling the background from corner patches and thresholding pixel diffs, classifies each slide by `<!-- _class: ... -->` directive (default `content`), and flags any page whose `bottom_margin_norm` exceeds BOTH `1.5 × class_median` AND `0.18`. Singleton-class slides (typically one `title`, one `ask`) are recorded as skipped with a reason — never flagged.
   - **Why a post-render check is necessary**: Marp's CSS `fit-to-frame` behaviour silently scales the entire `<section>` down to fit a slightly-over-budget page rather than clipping; the slide compiles clean, the PDF opens fine, and the reader sees a slide that reads small without any obvious failure mode. `marp_lint` (step 5b) catches *loud* overflow source-side; this detector catches the *silent* fit-to-scale post-render. `deck-vision` v1 `vertical_overflow` is the qualitative VLM companion (one API call per slide); this detector is deterministic and free.
   - The call returns an `AutoShrinkResult` with `findings: list[AutoShrinkFinding]`, `skipped: bool`, `reason: str | None`, `per_class_medians: dict[str, float]`, and `skipped_classes: dict[str, str]`. Each `AutoShrinkFinding` has `slide`, `class_name`, `bottom_margin_norm`, `median_bottom_margin_norm`, `ratio`, `rule="auto-shrink-fit-compression"`, `severity` (always `"error"`), and a human-readable `message` with an actionable fix hint.
   - **Graceful-skip on missing deps**: the detector needs `Pillow` and `numpy`, which are OPTIONAL Anvil extras (install via `uv pip install -e .[auto_shrink]`). The detector's first step calls `anvil.lib.render.check_auto_shrink_deps_available()`; if it returns `False`, the detector returns `AutoShrinkResult(skipped=True, reason=AUTO_SHRINK_REMEDIATION)` without raising. Record the skip as a `severity="info"` lint entry — the rest of `deck-review` proceeds normally. (Same pattern as the `mmdc` preflight #65 and the `pdfjam` preflight #85.)
   - **Graceful-skip on missing PDF**: if `deck.pdf` does not yet exist (the user hasn't run `deck-figures`), the detector returns `AutoShrinkResult(skipped=True, reason="deck.pdf not found at ...")`. Record as an info-level skip; do not block.
   - **On `ImportError` / `ModuleNotFoundError`** (the `anvil.skills.deck.lib.auto_shrink_detector` module itself is not importable — distinct from the optional-deps skip above, which is a `False` return from `check_auto_shrink_deps_available()`): the reviewer MUST NOT silently skip. Record a single info-level entry in `findings.md` § Auto-shrink lint findings of the form `lint=unavailable (module not importable: <ImportError message>)` and set the `_summary.md.lint.auto_shrink` block to `{"ran": false, "skipped": true, "reason": "module not importable: <ImportError message>", ...}` with empty `findings`. The verdict proceeds without auto-shrink contributing to `lint_critical_flag` — but the operator sees WHY the check did not fire (issue #375).
   - Cache the `AutoShrinkResult` for the `_summary.md` and `findings.md` writes below. Errors from this lint OR into `lint_critical_flag` alongside the `marp_lint` errors — `lint_critical_flag = (marp_lint.errors > 0) or (auto_shrink.errors > 0)`. Per the curator's design (#102 D3), the two checks are *complementary*: `marp_lint` catches the source-side overflow before render; this detector catches the post-render auto-shrink that source-side checks structurally can't see.
5d. **Run deck↔memo parity lint (Phase A, warning-only)** — issue #200:
   - Invoke `anvil.skills.deck.lib.parity_lint`'s `lint_deck_memo_parity(<thread>.{N}/, <sibling memo version dir or None>)` as a Python import — NOT as a filesystem path. The canonical consumer invocation is `uv run --project .anvil python -c "from anvil.skills.deck.lib.parity_lint import lint_deck_memo_parity; ..."`. The module re-exports from `anvil.lib.parity` and resolves through the importable mirror at `.anvil/anvil/skills/deck/lib/parity_lint.py` (post-#230). This is a Python-stdlib heuristic check (no third-party deps) that extracts hard-claim tokens — money (`$XXK/M/B`, decimal prices), percentages (including en-dash ranges), quarters/FY tags, named months + year, ALL-CAPS acronyms (length 2-6), and unit-bearing integers — from both `deck.md` and the sibling `memo.md` body, then compares the two token sets and flags any token present in one body but absent from the other.
   - **Sibling-memo-version discovery is the caller's (this command's) responsibility in v0**. Convention: at the portfolio root that contains `<thread>.{N}/deck.md`, look for sibling memo version dirs matching `<thread>.{M}/memo.md` and pick the highest `M`. If no sibling memo version exists (single-pipeline thread — most non-Studio consumers, and Studio threads where only the deck has shipped), pass `memo_version_dir=None`. Centralizing the discovery in `anvil/lib/parity.py` is part of the promotion plan once the memo-side mirror lands.
   - **Graceful-skip when no memo sibling**: `lint_deck_memo_parity(deck_dir, None)` (or with a sibling dir that lacks `memo.md`) returns `LintResult(skipped=True, reason="no memo sibling found at portfolio root; parity check inactive", memo_sibling=None)` with zero findings. `deck-review` proceeds normally — the rest of the review/verdict logic is byte-identical to a thread without the parity lint enabled. The skip is RECORDED in `_summary.md.lint.deck_memo_parity` (`ran: false`, `memo_sibling: null`, `reason: "..."`) and as a single info-level entry in `findings.md` § Parity-lint findings, so the operator sees WHY the check did not fire — same skip-reason convention as `auto_shrink` (step 5c).
   - **On `ImportError` / `ModuleNotFoundError`** (the `anvil.skills.deck.lib.parity_lint` module itself is not importable — distinct from the no-memo-sibling skip above, which is a runtime return value): the reviewer MUST NOT silently skip. Record a single info-level entry in `findings.md` § Parity-lint findings of the form `lint=unavailable (module not importable: <ImportError message>)` and set the `_summary.md.lint.deck_memo_parity` block to `{"ran": false, "memo_sibling": null, "reason": "module not importable: <ImportError message>", "warnings": 0, "infos": 0, "only_in_memo": [], "only_in_deck": [], "warnings_by_token": [], "infos_by_token": []}`. The verdict proceeds; parity is observational-only in v0 (Phase A) so this never contributes to `lint_critical_flag` regardless — but the operator sees WHY the check did not fire (issue #375).
   - The call returns a `LintResult` with `warnings: list[Finding]`, `infos: list[Finding]`, `skipped: bool`, `reason: str | None`, and `memo_sibling: str | None`. Each `Finding` has `line` (1-based source line in whichever body the token appeared), `rule="deck_memo_parity"`, `severity="warning"` (or `"info"` if suppressed), `message` (a human-readable diagnostic naming the canary anchor), `token` (the normalized token surface form), and `side` (`"only_in_memo"` or `"only_in_deck"`).
   - **v0 ships at `warning` severity only** (Phase A). Parity findings do NOT contribute to `lint_critical_flag` and do NOT force `advance: false` — the `errors` list on the result is always empty in v0. Verdict aggregation (step 12) is byte-identical to a thread without this lint enabled. Phase B promotion to `error` severity (and therefore `advance: false`-gating) is a separate decision deferred 2–4 weeks after Phase A merge, based on canary consumption signal. This Phase A / Phase B ship-with-falsifiability pattern (single named consumer + bounded observation window + explicit kill-switch criterion) is the same shape used by the kill-switch precedent recorded in `WORK_LOG.md` 2026-06-02 (issue #227).
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
9. **Write `_summary.md`** as a JSON-in-markdown scorecard with a top-level `rubric` block (issue #346) sibling to `lint`. The `lint` block is populated from the cached `LintResult` returned by step 5b; the `rubric` block carries the rubric the reviewer scored against so a downstream consumer aggregating across versions does not need to walk back to `anvil/skills/deck/rubric.md` (which may have changed between v3 and v5 of a long thread that spanned the `/40 → /44` migration):
   ```markdown
   # Review summary

   ```json
   {
     "critic": "review",
     "for_version": <N>,
     "rubric": {
       "id": "anvil-deck-v2",
       "total": 44,
       "advance_threshold": 39,
       "dimensions": 9,
       "prior_rubric_id": "anvil-deck-v1"
     },
     "dimensions": {
       "1_narrative_arc":            null,
       "2_problem_clarity":          { "score": 4, "weight": 5 },
       "3_market_size_credibility":  null,
       "4_solution_differentiation": null,
       "5_traction_proof":           { "score": 3, "weight": 5 },
       "6_team_credibility":         { "score": 3, "weight": 4 },
       "7_ask_specificity":          null,
       "8_design_polish":            null,
       "9_rhetorical_economy":       null
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
   - The `rubric` block fields (issue #346): `id` is the rubric identifier (`"anvil-deck-v2"`), `total` is the declared total (`44`), `advance_threshold` is the gate (`39`), `dimensions` is the count of weighted dimensions (`9`). The `prior_rubric_id` (conditional) is present when the prior review sibling exists; it is the prior `_meta.json.rubric_id` value (or `null` when the prior sibling lacks the field — legacy pre-#346 review). The `prior_rubric_inferred` (conditional) is present when `prior_rubric_id == null` AND a prior review sibling exists; its value is `"/40-legacy"` to signal "this thread's prior iteration was scored against the pre-#346 /40 rubric (whatever the skill shipped at the time)". Both fields are **omitted entirely** on the first iteration (no prior review sibling exists). The block is **observational only** — it does NOT affect verdict, critical flags, or `advance`.
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
    - Decision: `advance = (total >= 39) AND (no critical flag)`. When `lint.errors > 0`, `advance` is forced `false` and the verdict lists `Slide overflow (lint)` under critical flags; when `lint.auto_shrink.errors > 0`, the verdict additionally lists `Slide auto-shrink (lint)`. The rubric total is reported honestly but does not save the verdict.

    **Append `score_history` row with `rubric_id` (issue #346)**: the orchestrator (the command that drives review→revise iterations) appends one row to `<thread>.{N}/_progress.json.metadata.score_history` per finished review iteration. Per `anvil/lib/snippets/progress.md` §"Convergence fields → score_history", the canonical row shape is `{iteration, total, threshold, rubric_id}` — for the deck skill at /44, that's `{iteration: <N>, total: <aggregated-total>, threshold: 39, rubric_id: "anvil-deck-v2"}`. A thread that spans the `/40 → /44` migration records different `rubric_id` values across its rows; readers tolerate rows missing `rubric_id` per the backwards-compat contract (treat as `"unknown/legacy"`).
12b. **Emit rubric-version-transition subsection in `findings.md` when the prior rubric differs (issue #346)**: when the cached `prior_rubric_id` from step 4 is non-`None` AND differs from the current `"anvil-deck-v2"`, OR when `prior_rubric_id == None` AND a prior review sibling exists (legacy pre-#346 review), append a `## Rubric version transition` subsection to `findings.md` (sibling to the existing `## Findings`, `## Lint findings`, `## Auto-shrink lint findings`, and `## Parity-lint findings` subsections). Three shapes:

    When the prior rubric is a different stamped id:
    ```
    ## Rubric version transition

    This iteration was scored against `anvil-deck-v2` (/44, ≥39); the prior iteration at `<thread>.{N-1}.review/` was scored against `anvil-deck-v1` (/40, ≥35). The score delta `<prior_total>/40 → <current_total>/44` is NOT directly comparable — the threshold pool, dimension count, and weighted contributions all changed. A downstream consumer reading the delta SHOULD treat the prior score as advisory only and re-anchor on the current iteration's `<current_total>/44` against the `≥39/44` threshold.
    ```

    When the prior rubric is legacy (no `rubric_id` stamped):
    ```
    ## Rubric version transition

    This iteration was scored against `anvil-deck-v2` (/44, ≥39); the prior iteration at `<thread>.{N-1}.review/` predates per-review rubric version stamping (issue #346) and was scored against `/40-legacy` — the rubric this skill shipped before the `/40 → /44` migration (likely `anvil-deck-v1`, /40, ≥35). The score delta `<prior_total>/40-legacy → <current_total>/44` is NOT directly comparable — the threshold pool, dimension count, and weighted contributions all changed. A downstream consumer reading the delta SHOULD treat the prior score as advisory only and re-anchor on the current iteration's `<current_total>/44` against the `≥39/44` threshold.
    ```

    When the prior rubric matches the current rubric (the steady-state case — no transition surfaced):
    ```
    (subsection omitted entirely)
    ```

    The subsection is **observational** — it does NOT affect the verdict, the critical-flag list, or the `advance` decision. Backwards-compat: a legacy review sibling produced before this contract shipped does NOT need to be re-emitted.
13. **Write `verdict.md`**:
    ```markdown
    # Verdict — <thread> v<N>

    **Total**: 36.5 / 44
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
    | 9 | Rhetorical economy       | 4 | 4.0 | narrative |

    ## Critical flags

    - **Market-math error** (raised by deck-market): TAM calculation on Slide 7 multiplies units wrong — claimed $50B but inputs yield $5B. Reviser must recompute.
    - **Slide overflow (lint)** (raised by deck-review pre-flight, 2 errors): Slides 4 and 7 exceed estimated vertical capacity per the `slide-content-overflow` heuristic. See `findings.md` § Lint findings for the per-slide breakdown and suggested fixes.

    ## Top revision priorities

    1. Fix Slide 7 TAM calculation (critical flag).
    2. Resolve the 2 overflow-lint errors on slides 4 and 7 (critical flag — blocks advance).
    3. Slide 11 projection — replace hockey stick with month-by-month build.
    4. Slide 8 ARR discrepancy ($420k vs brief $380k).
    ```
14. **Update `_meta.json`** inside the staging dir: `finished: <ISO>`.
15. **Update `_progress.json`** inside the staging dir: `phases.review.state = done`, `phases.review.completed = <ISO>`. This is the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires `_progress.json` to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies every name in the required-files manifest exists in the staging dir, then atomically renames `.<thread>.{N}.review.tmp/` → `<thread>.{N}.review/`. The final-named dir only ever exists in **complete** form.
16. **Report**: print one-line status (e.g., `Reviewed acme-seed.1 → acme-seed.1.review/ (review owns 14/44; aggregated total 36.5/44, advance: false, 1 critical flag)`).

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
