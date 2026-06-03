# Changelog

## [Unreleased]

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
