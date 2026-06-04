# Changelog

## [Unreleased]

### Added — `anvil:project-migrate` skill (issue #297, bridge for the three-part model lock)

- NEW skill `anvil/skills/project-migrate/` — one-shot bridge tool that migrates existing studio projects to the post-#295 / post-#296 canonical model (project root + `BRIEF.md` absorbing all anvil config + `<slug>.md` body filename + `<project>/<slug>/<slug>.<N>/` shape). Closes the third leg of the three-part model lock (#295 + #296 + #297).
- **Commands**: `/anvil:project-migrate <project-dir>` (dry-run, NO mutations), `/anvil:project-migrate <project-dir> --apply` (execute), `/anvil:project-migrate <project-dir> --report` (markdown report only).
- **Three recognized current shapes**: pre-#283 classic (`<stem>.N/` sibling version dirs, no project BRIEF), post-#283 with `.anvil.json` (project BRIEF + per-thread `.anvil.json`), fully-migrated (target shape — no-op).
- **Per-project steps**: detect → plan → (optional) apply → verify. Each `DocumentPlan` is independently applyable; rollback is per-doc via a `<project>/.anvil-migrate-rollback/<slug>/` snapshot.
- **Cross-thread reference rewriting**: planner walks each body markdown for old-stem tokens (e.g., `memo.7`) and emits a `ContentRewrite` that updates them to the new slug-shaped reference (`<slug>.7`) after the directory renames land.
- **Git integration**: `git mv` is preferred when the project is under git so history follows; falls back to plain `shutil.move` otherwise.
- **Opinionated**: no back-compat flags. The skill converges existing projects onto one shape; it does not preserve the legacy shape under any option.
- **Idempotent**: re-running `--apply` on a fully-migrated project is byte-identical zero-diff.
- **rubric.md OMITTED**: migration output is mechanical; no /40 dimension to score.
- **`anvil:memo-migrate` carve-out**: the LaTeX bootstrap path continues to write a legacy `.anvil.json`; `project-migrate` runs as the documented post-step that consolidates it into the project BRIEF.
- Touched: NEW `anvil/skills/project-migrate/SKILL.md`, NEW `anvil/skills/project-migrate/commands/project-migrate.md`, NEW `anvil/skills/project-migrate/lib/` (`__init__.py`, `detect.py`, `plan.py`, `apply.py`, `verify.py`, `orchestrate.py`), NEW `anvil/skills/project-migrate/tests/` (six `test_project_migrate_*.py` files + `_fixtures.py` programmatic fixture builders + `conftest.py`), MODIFIED `anvil/skills/README.md` (skill index), MODIFIED `CLAUDE.md` (skill count 8 → 9).

## [0.2.0] — 2026-06-03

**Canary-driven iteration since 0.1.0.** Seventy-eight PRs landed in five days as the framework absorbed friction from the 2AM Logic Studio canary running multi-thread investment memos and proposals against rolling deadlines. The shape of this release: a new dim 9 *Rhetorical economy* rubric dimension (rubrics → /44, threshold ≥35), an `anvil:proposal` synthesis-sibling pipeline that consolidates cross-critic findings before revise, an `anvil:memo` `--plan` / `--apply` two-phase reviser, a `rubric_overrides` mechanism for non-investment-memo shapes (synthesis-brief, feedback-memo), a bulk `memo-migrate` LaTeX→markdown migration tool with 9 detector clusters, a framework-wide `<thread>.{N}.perspective/` sibling role, and an installer pivoted to `uv`-runnable consumer layouts. See `WORK_LOG.md` for the chronological merge record.

### Added — `anvil:memo` critic-side scope tagging on review comments (#242)

- Critic-side `scope: preserve | expand | reduce` tagging on every `<thread>.{N}.review/comments.md` entry, mechanically tied to dim 9 *Rhetorical economy* (#244 / PR #254). Phase A reviewer-prose-only (no `anvil/lib/` schema changes); composes with reviser-side severity filtering (#241).
- `anvil/skills/memo/rubric.md` — extended §"Dim 9 — rhetorical economy" with a "Surfacing to `comments.md`" subsection codifying the dim 9 → `scope: reduce` echo rule; added a §"Scope tagging (comments.md)" top-level subsection defining the three-valued vocabulary, the dim 9 echo rule, the `scope: expand` trim-candidate rule (major→minor downgrade when no trim candidate named), the `verdict.md` `scope: reduce` first-priority rule (when dim 9 < 4/4), the `_summary.md.scope_distribution` block, and the backwards-compat fallback for legacy reviews.
- `anvil/skills/memo/commands/memo-review.md` — extended step 5 (per-dim scoring) with the dim 9 `scope: reduce` echo sub-step; extended step 8 (line-level comments) with the `scope` label requirement, the dim 9 echo, and the `scope: expand` trim-candidate downgrade rule; extended step 9 (`_summary.md` write) with the top-level `scope_distribution` block (sibling to `lint` and `render_gate`); extended step 10 (`verdict.md` write) with the `scope: reduce` first-priority rule when dim 9 < 4/4.
- `anvil/skills/memo/SKILL.md` — added a short "Critics → reviser: scope tagging on `comments.md`" framing subsection pointing at the rubric and command-spec contract.
- `tests/skills/memo/test_memo_review_scope_tagging_doc.py` — new doc-AC test asserting the rubric and command spec carry the scope-tag contract surface (mirrors the existing `test_memo_review_render_gate_wiring_doc.py` doc-AC pattern). Distinct filename per the #58 packaging convention.

The asymmetry the canary diagnosed (critics propose adding content, never trimming): dim 9 (#244) closed the scoring-side hole; this issue closes the comments-stream-side hole. Without the echo, the reviser sees the dim 9 deduction in `scoring.md` but has no `comments.md` entry to act on. With it, every dim 9 anti-pattern instance mechanically becomes a `scope: reduce` comment, every `scope: expand` comment proposing a paragraph or subsection names a trim candidate, and `_summary.md.scope_distribution` carries the operator-visible signal that the critic is surfacing both directions. Memo-only this round; proposal-side mirror deferred per the precedent that #245's deck-side mirror followed (ship the rubric-side primitive on the canary-surface skill first; mirror to siblings after one consumption cycle).

### Added — `anvil:memo-revise` plan-then-apply mode (issue #243, Phase A)

- **`--plan` / `--apply` CLI flags on `memo-revise`** — opt-in two-phase invocation that materializes a `plan.md` change-set preview between scope choice and edit application. The shape mirrors `terraform plan` / `terraform apply` (or `git rebase -i`): `memo-revise <thread> --plan` writes a per-item planned-edit table at `<thread>.{N+1}.plan/plan.md` (a critic-sibling-shaped artifact, NOT a version dir) and exits without producing `<thread>.{N+1}/memo.md`; operators edit `plan.md` in place to decline items (three accepted shapes: same-line `<!-- declined: <reason> -->`, row deletion, or `Priority: declined` + bracketed `[declined: <reason>]`); `memo-revise <thread> --apply` then reads the (optionally edited) plan, validates freshness, and produces `<thread>.{N+1}/memo.md` + `changelog.md` per the existing reviser contract.
- **Plan validity contract.** `--apply` refuses stale plans across five cases: no matching plan exists, source review `verdict.md` mtime is newer than `plan.md` (re-reviewed since plan written), a new critic sibling was added since plan time, plan is older than `plan_max_age_days` (default 7, configurable via `<thread>/.anvil.json`), or `<thread>.{N+1}/` already exists. Each rejection points at remediation (typically: re-run `--plan` to refresh). Plan-sibling shape: `_meta.json` declares `scorecard_kind: "planner"`; `_progress.json.metadata.critic_siblings_at_plan_time` snapshots the critic set so apply-side detection of new siblings is exact.
- **Composition with `--polish`.** `memo-revise <thread> --polish "<reason>" --plan` writes a polish-pass plan; the verbatim operator reason flows from the plan header through to the produced version dir's `_progress.json.metadata.revise_force_reason` (operator does NOT re-pass `--polish` on `--apply` — the plan IS the audit trail). New composed `revision_mode` values: `"plan_then_apply"` and `"polish_plan_then_apply"`. Both are additive and audit-trail-only — not scored, not gating, no state-machine impact. `--plan` and `--apply` are mutually exclusive.
- **State-machine impact: none.** Plan siblings (`<thread>.{N+1}.plan/`) do NOT advance the thread to `REVISED`. The state-machine derivation in `SKILL.md` continues to use `<thread>.{N+1}/memo.md` presence as the `REVISED` evidence; plan siblings are invisible to it. This preserves the immutability contract (a half-built version dir without a `memo.md` is never `REVISED`).
- **Default no-flag path unchanged** (load-bearing regression contract). `memo-revise <thread>` with no flags continues to produce `<thread>.{N+1}/` directly per the existing 11-step procedure. The new dispatch steps 0a (--plan) and 0b (--apply) fire FIRST in the Procedure block; absence of either falls through to the unchanged 11-step procedure. Every existing consumer (the canary today, the 8 shipped skills' integration tests, the install-script regression tests) continues to work without modification.
- **Phase A scope**: reviewer-prose-only — no Python detector module. The plan-parsing logic is small enough to live inline in the command spec; extraction to `anvil/skills/memo/lib/plan.py` is a follow-on once a second consumer adopts the two-phase pattern (per CLAUDE.md "skill-local first, lib promotion later"). The shipped change touches `anvil/skills/memo/commands/memo-revise.md` (primary spec — new §"Plan-then-apply mode" + dispatch steps 0a/0b), `anvil/skills/memo/SKILL.md` (new §"Operator-confirmable change-set preview" sibling to §"Operator-initiated polish passes" + plan-sibling row in the artifact-contract diagram + state-machine non-gating note + command-dispatch-table flag update), `anvil/skills/memo/templates/plan.md.template` (canonical plan-artifact shape), `anvil/skills/memo/tests/test_memo_revise_plan.py` (44 tests across 8 test classes — doc-coverage + fixture-shape + AC10 inventory), and six fixtures under `anvil/skills/memo/tests/fixtures/memo_revise_plan/` (`clean_plan_apply`, `stale_verdict_rejected`, `declined_items_decay`, `target_length_exceeded`, `polish_plan_compose`, `no_flag_regression`).

This addresses the studio canary friction documented in issue #243 (`raytheon-pitch-strategy` thread, 2026-06-02): memo.3 → memo.4 produced a defensible higher-scoring version that the operator deleted and reverted on read because each addition was defensible in isolation but the aggregate drifted away from "clean and forceful presentation." A `plan.md` preview at the `--plan` step would have surfaced the per-item summaries and allowed line-level rejection before any edit was committed.

### Added — `anvil:proposal` synthesis-sibling schema + command spec (sub-issue 1 of issue #246)

- `anvil/skills/proposal/lib/synthesis_schema.py` — NEW pydantic models for the `<thread>.{N}.synthesis/gaps.json` contract. `GapList` carries `schema_version: "1"`, `for_version`, optional `thread`, and the two cross-sibling consolidation primitives: `Gap` (clustered findings — at least one `ContributingFinding` per gap, plus `root_concern` / `recommended_response` / severity ∈ {`critical`, `blocker`, `should-fix`, `nice-to-have`} / optional `rubric_dimensions`) and `Singleton` (findings that did NOT cluster). Mirrors `anvil/lib/review_schema.py` shape and discipline (`extra="forbid"`, pinned schema version, optional fields default to safe empties). Skill-local first per CLAUDE.md "Skill-local first, lib promotion later" — lives under the proposal skill until a second skill adopts synthesis.
- `anvil/skills/proposal/lib/synthesis_schema.json` — companion JSON Schema document (Draft 2020-12) auto-generated from the pydantic model so non-Python callers validate `gaps.json` against the same contract.
- `anvil/skills/proposal/commands/proposal-synthesize.md` — NEW command spec for the synthesizer lifecycle role inserted between parallel critics and the single reviser. Documents the on-disk shape (`<thread>.{N}.synthesis/` with `verdict.md`, `synthesis.md`, `gaps.json`, `_meta.json`, `_progress.json`), the resume / crash-recovery contract, the clustering procedure (deterministic pre-filter + LLM cluster step + conservative "leave as singleton when uncertain" fallback), the severity ladder (max-across-contributors), the aggregator-skip rule (`role: "synthesizer"` in `_meta.json` — no per-dimension scores means the existing aggregator's null-fall-through handles it without code change), the state-machine integration (new `SYNTHESIZED` transient state between `REVIEWED+AUDITED` and `REVISED`), and the reviser-side backward-compatibility fallback (when `gaps.json` is absent, `proposal-revise` reads per-sibling findings directly — preserved as the rollout safety net).
- `anvil/skills/proposal/tests/test_synthesis_schema.py` — schema-only tests: round-trip on the 12LP+ canary fixture from the issue body, default-fields safety, schema-rejects-invalid coverage (empty contributing-findings → rejected; unknown severity → rejected; missing required fields → rejected; extra fields → rejected; `for_version < 1` → rejected), full severity vocabulary acceptance, JSON Schema document presence + drift detection between model and on-disk JSON, command frontmatter parse. Distinct filename per the #58 packaging convention.

This is **sub-issue 1 of 4** from the curator's decomposition of issue #246. It establishes the load-bearing contract on which sub-issues 2 (reviser-side consumption), 3 (orchestrator + state-machine integration), and 4 (Studio reproducer integration test) depend. Reviser code, orchestrator wiring, and SKILL.md state-machine updates are deliberately out of scope for this PR — sub-issues 2 and 3 will land in parallel once the contract is fixed; sub-issue 4 lands last.

### Changed — `anvil:memo` and `anvil:proposal` rubric shape

- **New dim 9 *Rhetorical economy* (weight 4)** added to both `anvil:memo` and `anvil:proposal` rubrics. Both rubrics now score against **9 weighted dimensions summing to 44** (was 8 dims / 40). The advance threshold rises to **≥35/44** (was ≥32/40) — the ~80% bar is preserved (35/44 = 79.5%; 32/40 = 80%). Dim 9 polices whether every paragraph is load-bearing — could the same argument land in fewer words? Are the most important claims surfaced early? Is hedging proportional to genuine uncertainty? Could a busy reader extract the recommendation in 90 seconds? It is the countervailing pressure against the bloat failure mode the existing 8 dims structurally rewarded (every other dim rewards adding more). Six named anti-patterns (multi-paragraph hedges, oversized footnotes, redundant subsections, restating tables, reformulated open-decisions entries, restating bullet lists) make the dim actionable for the reviser. The justification MUST cite specific instances — same anchoring discipline as the existing dim 3 citation-hooks rule. Closes #244 (canary surface: 2AM Logic Studio's `raytheon-pitch-strategy` v1→v2 produced a "less compelling" v2 despite a higher /40 score; dim 9 is the missing countervailing pressure).
- **Cross-skill divergence**: the other six anvil-shipped skills (`anvil:pub`, `anvil:report`, `anvil:deck`, `anvil:slides`, `anvil:ip-uspto`, `anvil:installation`) continue on the 8-dim /40 rubric. Dim 9 ships first on the two skills where canary friction surfaced it; broader propagation is a separate decision driven by per-skill calibration evidence. The framework no longer has a single "8-dim /40" default — per-skill rubric shape is now the explicit reality.
- **Backward compatibility**: existing on-disk `<thread>.{N}.review/verdict.md` written against the old /40 rubric remains a legal historical record and will not be retroactively re-scored. The first revise pass after upgrade produces a v{N+1} whose subsequent review scores against the new /44 rubric. No `anvil/lib/` schema changes; critic siblings continue to emit the `human-verdict` scorecard kind via the existing `LEGACY_MEMO_FILES` adapter in `anvil/lib/critics.py`.
- **Deferred — Option C (genre-flag knob)**: the long-term shape is a `genre: buildable-system | strategic` frontmatter knob that activates dim 9 only for strategic-positioning artifacts. Option C depends on the per-genre rubric-override mechanism in #233 and ships as a companion issue once #233 lands. The dim 9 prose shipping here is reusable across both shapes.

### Added — `anvil:proposal` synthesis pipeline (issue #246, four-PR decomposition)

- **Sub-issue 2 — reviser consumes `gaps.json`** (#270). `proposal-revise.md` steps 6/7/9 updated to prefer `<thread>.{N}.synthesis/gaps.json` as the revision-plan source when present (validated against the pinned `GapList` pydantic model), with the per-sibling reading path preserved verbatim as the rollout-safety fallback. Step 7 walks `gaps` + `singletons` with `critical → blocker → should-fix → nice-to-have` ordering, planning one coordinated response per gap. Step 9 introduces the canonical `synthesis <gap-id> (<sibling>.<ref>, ...)` row format while preserving the `<thread>.<N>.<sibling> (<severity>)` shape on the fallback. 26 new structural tests pin the contract.
- **Sub-issue 3 — orchestrator + state-machine integration** (#271). `commands/proposal.md` state inference (step 3) recognizes `SYNTHESIZED` as a transient state when `<thread>.{N}.synthesis/verdict.md` + `gaps.json` exist. Dispatch table (step 4) gains rows for `REVIEWED+AUDITED → proposal-synthesize` and `SYNTHESIZED → proposal-revise`, plus the parallel at-cap → BLOCKED rows. Anomaly detection extended for stalled-no-synthesis, crashed-synthesis, and orphan-synthesis cases. `SKILL.md` state-machine ASCII diagram now includes `SYNTHESIZED` between `REVIEWED+AUDITED` and `REVISED`; evidence table and command-dispatch table updated to match. 32 new tests across 9 classes pin the contract.
- **Sub-issue 4 — Studio reproducer integration test** (#272). Fixture-and-clustering regression test for the 12LP+ FinFET mask cost canary (three siblings → one gap with three contributing findings). Ships an `anvil/skills/proposal/lib/synthesizer.py` clustering primitive with callback-injection seam (mirrors `anvil/lib/vision.py::VisionCritic`): default path raises `NotImplementedError`; consumers pass a callback for the LLM clustering step. Skill-local per CLAUDE.md "skill-local first, lib promotion later." 25 new tests pin clustering shape + post-processing pipeline (severity ladder defensive-override, dim-list union, schema validation).
- **Tolerant findings filename + alias contract** (#255 / `proposal-synthesize.md`). The synthesizer's input contract documents that critic siblings may emit `findings.md`, `Findings.md`, or `findings.json`; the synthesizer reads whichever exists. Matches the existing audit-side tolerance pattern.

Sub-issue 1 of #246 (schema + command spec, #253) is documented above under "Added — `anvil:proposal` synthesis-sibling schema + command spec". With all four sub-issues landed, the `EMPTY → DRAFTED → REVIEWED+AUDITED → SYNTHESIZED → REVISED → … → READY → AUDITED` proposal lifecycle is fully wired end-to-end.

### Added — `anvil:memo` rubric_overrides for non-investment-memo shapes (issue #233)

- **Sub-issue 1 — typed loader** (#267 / `anvil/skills/memo/lib/anvil_config.py`). Pydantic loader for the `rubric_overrides` block in `<thread>/.anvil.json`. Supports per-dimension calibration strings (`dim_N_calibration`), optional `target_length` inside the override, and a `memo_subtype` discriminator (`synthesis-brief`, `feedback-memo`, etc.). `extra="forbid"` on the inner block; unknown keys surface as `unknown_keys` for forward-compat visibility without hard-failing the load.
- **Sub-issue 2 — reviewer integration** (#273 / `anvil/skills/memo/lib/rubric_overrides_suffix.py`). `memo-review` reads `rubric_overrides` via the typed loader and appends `\"calibration applied: <override text>\"` as a verbatim suffix to each scored dimension's justification in `_review.json` + `scoring.md`. New top-level §"Reader dispatch order: `.anvil.json` vs `BRIEF.md` 'Critical reviewer guidance'" documents the precedence (structured config wins; BRIEF.md is documented Option-A fallback). Zero-impact when `rubric_overrides` is absent; documented in 27 tests covering suffix attached / suffix absent / per-dim dispatch / zero-impact / verbatim contract / loader-integration pipeline.
- **Sub-issue 3 — docs + worked-example templates** (#274). `SKILL.md` gains a "Rubric overrides and non-investment-memo shapes" section with worked examples for both canary subtypes and the `BRIEF.md` Option-A fallback. `rubric.md` carries one-sentence pointers near the most-commonly-recalibrated dims (1, 5, 6, 7). Two `.anvil.json` example templates ship under `anvil/skills/memo/templates/`: `.anvil.json.synthesis-brief.example` (brasidas-synthesis canary, [9000, 13000] words, calibrates dims 1/5/6/7) and `.anvil.json.feedback-memo.example` (raytheon-pitch-strategy canary, [4000, 6000] words, calibrates dims 1/4/5/6/7). 19 round-trip tests pin loader compatibility + cross-template consistency. Deferred: `memo-draft` / `memo-revise` consumption of `rubric_overrides.target_length` (the reviewer surfaces `target_length_present` for audit visibility but doesn't act on the value; drafter/reviser wiring is a follow-on).

### Added — `anvil:memo-migrate` (bulk LaTeX → markdown migration)

A new `anvil:memo-migrate` command and supporting library for converting a portfolio of legacy LaTeX memo threads to the markdown convention in bulk. Ships across nine PRs:

- **Command + base migration** (#207). `anvil:memo-migrate <source.tex> <portfolio>` runs `pandoc` over the source, lays down the version-dir layout, and emits a structured `_progress.json` report.
- **Refs/ seeding from BRIEF.md Sources** (#208). `anvil:memo-migrate-refs` extracts Sources references from BRIEF.md and seeds `refs/` for later reviewer back-check consumption.
- **Detector clusters** (#217–#222). Five detector clusters in `anvil/skills/memo/lib/migrate.py` flag layouts the canary corpus surfaces but pandoc loses: orphan figures in source `figures/` (#217), packed single-cell tabularx layouts (#218), 4-column key/value metricbox tables (#219), empty `figures/` directories (#221), and `figure_policy` classification for zero-figures intent (#222). Each emits a structured finding into the migration report.
- **Source brief ingestion** (#220). Earliest-brief-wins rule: when multiple version directories carry a `brief.md`, the migration ingests the root-level (or oldest) brief and records provenance in `_progress.json.metadata.source_brief_path`.
- **Detector cluster reference** (#223). `commands/memo-migrate.md` documents the detector cluster catalog with one-paragraph framing per cluster, anchoring the reviewer-side surface to the source-side detectors.
- **Memo parity lint mirror** (#224). Memo-side `<thread>.{N}.review/lint.json` mirror of the existing `anvil:deck` parity lint shape (warning-only, Phase A). Surfaces missing-from-BRIEF and missing-from-memo discrepancies without gating advance.

### Added — Framework `<thread>.{N}.perspective/` sibling role (Epic #143)

A new perspective-aware critic sibling that surfaces strong-form alternatives to the artifact's central claim before the reviewer scores it. Lands across five PRs as a framework-level addition rather than a per-skill one.

- **Snippet convention + perspective discipline** (#154). `anvil/lib/snippets/perspective.md` introduces the perspective sibling convention to the snippet-library substrate every skill reads.
- **`anvil:memo` perspective sibling** (#183). `memo-perspective` command surfaces alternative candidate threads from the portfolio; output lands at `<thread>.{N}.perspective/candidates.md` for reviewer consumption.
- **`anvil:proposal` perspective sibling** (#184). `proposal-perspective` mirrors the memo shape against the proposal lifecycle; new audit-wiring lines surface perspective evidence in the audit's `findings.md`.
- **Deck market perspective cross-check** (#156, #157). `deck-perspective` command + market-side cross-check.
- **Perspective-aware dimension calibration** (#194). `anvil/lib/rubric.py` extension that lets venue-pinned rubric overlays opt into perspective-aware calibration prose per scored dimension.

### Added — `anvil:memo` reviewer & reviser convergence machinery

- **`memo-revise --polish` operator-initiated polish-pass entry point** (#206). Operators can force a polish-pass revision with a verbatim free-text reason that flows into `_progress.json.metadata.revise_force_reason` for audit. Composes with `--scope` and `--plan` (see below).
- **`--scope severity filter` on revisers** (#257, memo + proposal). Default `important`; operators may pass `--scope all` to fold in `nice-to-have`-severity findings or `--scope blocker` to limit to blocker-severity only. Filter is applied to per-sibling findings (or to gap severity under synthesis).
- **Per-revision directive convention** (#260). Formalizes the operator-supplied `<thread>.{N+1}.directives.md` shape as the pre-revise directive surface — separate from BRIEF.md's per-thread directives.
- **Summary-detail consistency back-check** (#245, PR #250). Phase A reviewer-prose-only back-check that surfaces verdict-summary vs per-dim-detail mismatches in `<thread>.{N}.review/comments.md`.
- **Cross-thread citation back-check** (#236, PR #262). Phase A reviewer-prose-only back-check that flags citations referenced in a thread's body but absent from its `refs.bib`, walking sibling threads in the same portfolio.

### Added — Rendering, layout, and ergonomics

- **`anvil:memo-render` command + state-machine integration** (Epic #158 / PR #193). New explicit render lifecycle phase, replacing the implicit rendering that previously hid inside `memo-revise`. State-machine snippets updated to document the new phase.
- **`anvil:memo` lib substrate + renderer detection** (Epic #158 Phase 1 / PR #172). New `anvil/skills/memo/lib/` with renderer-detection helpers (`weasyprint`, `pandoc`, fallbacks).
- **Memo PDF render-gate (kind="memo")** (#185). `anvil/lib/render_gate.py` gains a `kind="memo"` mode for the markdown→PDF pipeline; matches the LaTeX-side gate's shape (page-fit, overfull boxes, compile success, placeholder scan).
- **Render-gate findings wired into reviewer + word-count-primacy rubric prose** (Epic #158 Phase 4 / PR #198). Render-gate output flows into reviewer prose for the dim 7 length-pinning calculation.
- **`@page` size US-Letter pinning for weasyprint** (#232, PR #263). Fixes a regression where weasyprint defaulted to A4 because the `@page` size was unspecified.
- **Per-thread `words_per_page` override for `memo_page_fit`** (#264). `<thread>/.anvil.json: words_per_page` lets operators tune the page-fit gate's word/page coefficient when the canary corpus drifts from the default.
- **Booktabs-class CSS for markdown tables** (#238, PR #259). Brings the markdown table render closer to the LaTeX booktabs aesthetic; opt-in via `class="booktabs"`.
- **`orientation: landscape` frontmatter knob for table-dense proposals** (#248). Per-version landscape rendering for proposals whose table widths exceed portrait.
- **Pre-flight image-reference lint (`memo_image_refs_exist`)** (#160). Detects markdown image links that resolve to missing files in `figures/`.
- **Per-version `target_length` overrides + provenance** (#161). Operators may pin `target_length` on a per-version basis via `<thread>.{N}/_progress.json.metadata.target_length` for dim 7 anchoring.
- **`refs/` source-of-truth materials + reviewer back-check** (#162). Reviewers verify every body-of-memo citation against the materials in `refs/`; mismatches surface as dim 3 findings.
- **Configurable `target_length` in `.anvil.json`** (#122). Top-level `target_length` in `.anvil.json` defines the resolved range that flows into dim 7 scoring. (Carried forward to the rubric_overrides mechanism above.)
- **Per-skill installer content-hash detection** (#163). Installer records a per-skill content hash for modified-vs-pristine detection at upgrade time.
- **Surface new-skill availability on upgrade** (#239, PR #261). Installer prints which skills are NEW at upgrade time, with copy-and-paste invocation lines.

### Added — `anvil:deck` and `anvil:slides` extensions

- **`anvil:deck-imagegen` orchestration runtime + command spec** (Epic #130 Phase 2 / PRs #169, #170, #171, #182, #186, #191, #192, #197). Brings generative-imagery into deck via a backend-agnostic preset library, an `imagery_policy` BRIEF.md frontmatter field, an `imagegen` orchestration runtime with prompt-journal schema and read/write primitive, three new audit findings (fabrication-attribution, generative-imagery findings gated on `imagery_policy`), and a consolidated `imagegen_phrases.py` for stock phrasing.
- **`deck↔memo` parity pre-flight lint** (#205). Warning-only Phase A check that flags structural mismatches between a deck and its companion memo (used by the canary's deck-from-memo pipeline).
- **Deck `.row` + `.split` stock layout classes** (#174). Reusable layout-only utility classes in `anvil-deck.css`.
- **Slides `marp_lint` re-export** (#164, PR #173). `anvil:slides` pins re-export of the deck-side `inline-display-style-dropped` rule; the underlying primitive lives in `marp_lint`.
- **Inline `display:grid` / `display:flex` lint** (#134). Source-side warning for inline display styles that Marp's foreignObject SVG render silently drops.
- **Deck iteration-cap rationale paired with `max_iterations` override** (#141). When a deck override raises `max_iterations`, an `iteration_cap_rationale` line is mandatory and the orchestrator surfaces a BLOCKED notice for missing-rationale cases.

### Added — Framework substrate

- **`palette.json` sibling for bare-python3 consumption** (#126). Anvil's brand palette is now also available as a JSON sibling alongside `palette.py` for tooling that can't import the Python module.
- **Optional `.latest` symlink convention** (#120, PR #123). Documented convention for the optional `<thread>.latest` symlink that resolves to the highest version dir.
- **Filetype-first vs project-first portfolio placement** (#127). Snippet-level documentation of the two portfolio-layout shapes.
- **Drafter-side citation-hook contract** (#140). Documented contract for the drafter-emitted citation-hook lines that the reviewer back-check consumes.
- **`anvil:memo` BRIEF.md fresh + migration templates** (#139). Two new BRIEF.md templates: a fresh-thread template and a migration-target template.
- **Optional pdftotext PDF refs back-check** (#175). Path A: subprocess `pdftotext` extracts the rendered PDF's text and back-checks refs against the source markdown.
- **Refs back-check rolled out to deck + proposal** (#176). Same back-check primitive consumed by both sibling skills.
- **`revise_consistency` stale-token sweep + deck-revise wiring** (#114). New `anvil/lib/revise_consistency.py` primitive sweeps for stale tokens between drafter output and reviser input; wired into `deck-revise`.

### Changed — Dependencies

- **`pyyaml>=6.0` declared as a base `[project]` dep** (#231, PR #268). `anvil/lib/rubric.py` does a top-level `import yaml`; `anvil/lib/__init__.py` re-exports `Rubric` / `load_rubric` / `discover_venue_rubric`, so any `from anvil.lib import ...` (and downstream `anvil.lib.render_gate`) transitively requires yaml at import time. This matches the same load-bearing-for-import-chain shape as the existing `pydantic` base-dep exception; `pyproject.toml`'s header comment is updated to document the second exception. Without this, a fresh `uv sync` produced a build that failed on first import.
- **Installer pivots to uv-runnable consumer layout** (#230, PR #269). The shipped install layout is now a directly-`uv sync`-runnable shape; consumers no longer need a separate `pip install` invocation. Drift-detection note added to the installer to flag layouts that predate the new shape.

### Removed

- **`_convictions.md` advisory contract** (PR #229, retiring PR #155). The Epic #142 Phase A `_convictions.md` advisory primitive shipped in #155 was removed after Phase B verdict surfaced no canary signal to justify it. Kill-switch removes the snippet, command-doc references, and tests. The same surface area is being re-explored under a different (in-progress) design.
- **`anvil:memo` per-skill `--polish` BRIEF.md scaffolding** (rolled into the new `--polish` flag landed in #206 above; pre-#206 partial scaffolding removed in the same PR).

### Fixed

- **`memo-migrate` `RenderError` inline for consumer-install layout** (#199, PR #204). Inlined `RenderError` in `refs_pdf.py` so consumer installs don't carry a dangling import.
- **Installer Claude shim depth-1 placement** (#138). Shims must land at depth 1 of `.claude/commands/` so `/anvil-*:*` commands actually register; the installer was previously placing them too deep.
- **`anvil:deck` auto-shrink tests gated on `[auto_shrink]` extra** (#115, PR #116). Without the gate, the auto-shrink tests fail when the optional `[auto_shrink]` extra isn't installed.
- **`matplotlib parse_math` anti-pattern guidance** (#125). Docs note steering away from `parse_math=True` in figure-side matplotlib code.
- **CLAUDE.md refresh post-0.1.0** (#112). Refresh of stale sections after the first installable release.

## [0.1.0] — 2026-05-30

**First installable release.** Anvil moves from skeleton to a working framework with 8 shipped skills, a maturing `anvil/lib/` substrate, and active use by the [2AM Logic Studio canary](https://2amlogic.com). 30+ PRs landed in two days of canary-driven development. See `WORK_LOG.md` for the chronological merge record.

### Added — Skills (8)

- `anvil:memo` — investment memos, internal documents (Markdown).
- `anvil:pub` — research papers with venue-pinned rubrics (NeurIPS / Nature / arXiv overlays).
- `anvil:report` — customer-facing technical reports (Markdown / LaTeX → PDF) with mandatory audit + `CUSTOMER-READY` promotion gate.
- `anvil:deck` — investor pitch decks (Marp Markdown → PDF).
- `anvil:slides` — talk / conference slides with speaker notes (Marp Markdown → PDF + handouts).
- `anvil:ip-uspto` — USPTO non-provisional utility patent applications (LaTeX → PDF) with 9-check pre-flight including render-gate.
- `anvil:installation` — experiential / installation artwork concept proposals (LaTeX → PDF).
- `anvil:proposal` — buildable-system proposals (pre-contract bookend to `anvil:report`); collapses the "internal build spec" case via `customer_kind: internal`.

Each skill ships a complete `draft → review → revise → (audit) → figures` lifecycle, an 8-dimension /40 rubric, opinionated templates, a worked example thread, and tests.

### Added — `anvil/lib/` framework substrate

- `snippets/` (10 markdown files) — pure-markdown conventions every skill reads (progress, timestamp, version_layout, thread_state, state_machine, rubric, critics, scorecard_kind, audit, cite).
- `review_schema.py` + `.json` — typed `_review.json` contract with `kind ∈ {judgment, tool_evidence, vision}` discriminator; JSON Schema export.
- `critics.py` — sibling-critic discovery, aggregation, verdict computation; legacy-shape adapters for the memo prose triple and ip-uspto hybrid.
- `convergence.py` — `check_stable` + `decide_termination`; `STALLED` verdict for plateaued threads.
- `cite.py` — DOI + arXiv resolver, BibTeX writer, idempotent `refs.bib`; stdlib only.
- `rubric.py` + `rubric_schema.json` — pydantic models + venue-pinned overlay discovery (`<thread>/.anvil.json: venue` → optional advisory rubric).
- `render.py` — Marp → PDF, PDF → PNGs, pandoc → PDF, matplotlib figure walker; `check_*_available()` preflight helpers for `mmdc` / `pdfjam` / auto-shrink dep set.
- `vision.py` — `VisionCritic` + `VisionRubric`; injectable callback for offline/CI use.
- `render_gate.py` — deterministic gate over compiled PDFs (page-fit + overfull boxes + compile success + placeholder scan); LaTeX-skill analog of `marp_lint`.
- `figures/palette.py` + `anvil.mplstyle` + `mermaid-theme.json` — shared brand-palette substrate with 6 named tokens (navy / ink / muted / rule / bg-section / bg) + 4 semantic mermaid classDefs (`anvil-accent` / `anvil-muted` / `anvil-warning` / `anvil-success`) + per-glyph Unicode fallback for matplotlib.
- `marp/config.yml` — pinned Marp config (MathJax + html; `mmdc → PNG` is the documented working diagram path).

### Added — Per-skill rendered-artifact (vision) critics

- `deck-vision`, `slides-vision`, `pub-vision`, `report-vision`, `ip-uspto-vision` — VLM critique of rendered PDFs / drawings. Each composes a skill-appropriate `VisionRubric` (e.g. `ip-uspto-vision` covers USPTO drawing requirements: reference numeral legibility, line weight / contrast, label placement, figure-number visibility, cross-reference accuracy).

### Added — Deterministic source-side lint

- `marp_lint` (deck + slides) with 5 named rules: source-side overflow detection (`slide-content-overflow`), figure-bullet stack detection, ask-slide H1+H2 detection, italic-supporting-line word-budget (`figure-italic-supporting-line-too-long`), and the suppression directive `<!-- anvil-lint-disable: <rule> -->`.

### Added — Installer + ergonomics

- `scripts/install-anvil.sh` with `--skills=` filter, `--dry-run`, `--check-deps` (covers `marp`, `mmdc`, `pdfjam`, `pdftoppm`, `xelatex`, `pandoc`); quoted-path safety (removed all 7 `sh -c` indirection sites); honest dry-run output.
- `pyproject.toml` — Anvil's first declared Python dep file, uv-shaped. Base dep: `pydantic>=2.0` (load-bearing for the schema layer). Optional extras: `[auto_shrink]` (Pillow + numpy for the Marp auto-shrink detector). Documented dep philosophy: subprocess-only by default; Python deps for genuinely-better-than-subprocess detection only.

### Added — Repo management

- `AGENTS.md` — Loom agent-archetype reference for ongoing development.
- `ROADMAP.md` — mission, design philosophy, current state, near-term themes.
- `WORK_LOG.md` — chronological record of merged PRs and closed issues.
- `WORK_PLAN.md` — prioritized backlog generated from current label state.
- `.claude/commands/loom/release.md` adapted from Loom for anvil's actual structure (2 version-bearing files, no build workflow).

### Added — Tests

- `tests/lib/` — full coverage for schema, critics, convergence, cite, rubric, render, vision, render_gate, figures.
- `tests/scripts/` — install-script regression armor (quoted-path safety, dry-run honesty, `--skills=` validation, version drift, `version.sh set` round-trip).
- Per-skill tests under `anvil/skills/<skill>/tests/` — skill-local lint, vision-critic, and template-correctness tests.
- CSS-drift guard test enforces palette tokens stay in sync between `palette.py` and `anvil-deck.css :root`.
- Version-drift guard test enforces `CLAUDE.md` and `pyproject.toml` stay in sync.

### Fixed

- Mermaid diagram silently rendered as raw code in Marp PDFs (regression introduced by inline-mermaid-as-default design); switched to `mmdc → PNG` as the documented working path with proactive preflight.
- White-on-white table rendering on `_class: ask` slides (Marp default-theme cell-bg leak).
- Deck draft and narrative critic recommended conflicting slide orders.
- Install script broke on target paths containing `'` (single-quote injection via `sh -c`).
- Install `--dry-run` emitted misleading `ok: ...` confirmations of actions that didn't happen.
- Bare `--skills=` silently fell through to install-all-skills (argument-validation gap).
- Phantom `completed` phase state introduced by a malformed Markdown table in `lib/snippets/progress.md`.
- Report ack-file substring matching was too lenient (now requires a structured YAML token + sha256 verification).
- Report auditor allowed unreachable external citations to pass (now a `critical_flag`).
- Report reviewer didn't check whether `report.pdf` existed despite the figurer claiming Dim 7 scored its existence.
- IP-USPTO critic phase names in `_progress.json` snippets used generic `"review"` instead of the critic's own tag (s101 / s112 / claims / priorart).
- Cross-skill pytest filename collision (deck vs slides `test_marp_*.py`) — completed `__init__.py` package chain across all skill test directories.
- Slide-archetypes "ONE italic supporting line" guidance was line-counting; replaced with explicit word/character budget (≤18 words / ≤108 chars) + lint detection of overlong supporting lines under figure refs.

### Changed

- `release.md` skill adapted for anvil's actual version-bearing files (was inherited verbatim from Loom with 5 wrong file paths).
- `scripts/version.sh` now tracks both `CLAUDE.md` and `pyproject.toml` with `check` reporting drift.
- README rewritten from "Alpha. Skeleton only" to a real installation + repository-layout + working-with-anvil guide.
- Deck `_class: ask` slide template no longer uses H1+H2 stack (overflowed 16:9); single H2 + inline use-of-funds paragraph.
- Deck figure-bullets idiom replaced with figure + one supporting line (Market / Traction / Financials templates updated; lint enforces word budget).
- Marp config pinned at framework level: MathJax not KaTeX; `html: true` for inline content; `--config-file anvil/lib/marp/config.yml`.

### Status

v0.1.0 is the first installable release. Anvil works on a single laptop with no GitHub account; renderer dependencies (marp / mmdc / pdfjam / pdftoppm / xelatex / pandoc) are checked by `install-anvil.sh --check-deps`. Active development continues against canary friction — see `WORK_PLAN.md` and the open-issues backlog for what's next.

### Next

- Per-skill audit-command migrations to emit typed `_review.json` (pre-date the #29 codification).
- Markdown-appropriate length-proxy gate for `anvil:memo` if canary friction emerges (memo is markdown-first; no PDF page-fit contract).
- Per-skill `lib/` extraction to `anvil/lib/` once duplication patterns are observed across skills (e.g. `marp_lint`, `auto_shrink_detector`, report's `pdf_freshness`).

---

## [0.0.1] — 2026-05-28

### Added
- Initial repository skeleton.
- Vision, design principles, and planned v0 skill catalog in README.
- MIT license.
- Project-level `CLAUDE.md` for AI session context.
- Directory structure for `anvil/{skills,lib,templates,roles}` and `scripts/`.
- Minimal `scripts/version.sh` (manages `CLAUDE.md` version string only; will grow as more version-bearing files appear).

### Status
- Alpha. No installable functionality. No skills yet implemented.

### Next
- Implement v0 skills per the catalog in README.
- Extract framework `lib/` from observed duplication after the first few skill implementations land.
- Implement `scripts/install-anvil.sh`.
