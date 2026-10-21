# Work Log Archive — 2026-07

Sections moved byte-for-byte from [WORK_LOG.md](../WORK_LOG.md) by `loom-daemon work-docs archive`.

### 2026-07-31

- **PR #839**: fix(memo): fall back to project-root BRIEF.md for recommendation_target (closes #837)
- **PR #838**: fix(numeric-consistency): exclude season/fiscal-year labels from fraction parsing (closes #836)
- **PR #835**: fix(guide): exempt pure docs-maintenance PRs from WORK_LOG entries (closes #834) — breaks the self-referential docs-PR treadmill (#827→#833 chain); a PR whose diff touches only WORK_LOG/WORK_PLAN/README no longer gets its own WORK_LOG line (PR #833 is the last of that chain to be recorded)
- **PR #832**: docs: Guide document maintenance update (WORK_LOG entries for PR #830 and #831, which merged after generating themselves and so weren't recorded in their own runs)
- **PR #831**: docs: Guide document maintenance update (WORK_LOG entry for PR #830, which merged after generating itself and so wasn't recorded in its own run)
- **PR #830**: docs: Guide document maintenance update (WORK_LOG entry for PR #829, which merged after generating itself and so wasn't recorded in its own run)
- **PR #829**: docs: Guide document maintenance update (WORK_LOG entry for PR #828, which merged after generating itself and so wasn't recorded in its own run)
- **PR #828**: docs: Guide document maintenance update (WORK_LOG entry for PR #827, which merged after generating itself and so wasn't recorded in its own run)
- **PR #827**: docs: Guide document maintenance update (WORK_LOG entry for PR #826, which merged after generating itself and so wasn't recorded in its own run)
- **PR #826**: docs: Guide document maintenance update (WORK_LOG/WORK_PLAN refresh for #824/PR #825 closure)
- **PR #825**: fix: ignore .loom/.daemon.flags and .loom/runtimes/ in loom-managed gitignore block (closes #824)
- **PR #821**: fix(install): strip __pycache__/*.pyc/.DS_Store cruft from every tree-copy site (closes #818)

### 2026-07-30

- **PR #805**: fix(install): ship vocab_reminder default word list to installed lib mirror (closes #800)
- **PR #763**: fix(install): ship skill lib/ to the documented direct-invocation path (closes #743)
- **PR #761**: feat(memo): add cross-version drift check to memo-review (closes #746)
- **PR #814**: fix(curator): normalize unknown mergeable_state in blocked-pending-PR guard (closes #806)
- **PR #812**: fix(curator): make blocked-pending-PR guard's marker read REST-backed and fail-closed on read failure (closes #809)
- **PR #804**: docs(curator): add time-debounce to blocked-pending-PR guard to fix concurrent-dispatch race (closes #802)
- **PR #798**: fix(curator): stop claim/unclaim churn on blocked-pending-PR no-op re-checks (closes #796)
- **PR #773**: feat(memo): add evidence-grade rendering rule so grade tags stay out of reader prose (closes #751)
- **PR #786**: docs(curator): add idempotency guard for blocked-pending-PR re-checks (closes #785)
- **PR #787**: docs(champion): make size-limit rejection comment idempotent, not re-posted every tick (closes #784)
- **PR #791**: fix(champion): drop stray -r from LAST_MARKER `gh pr view` --jq call (closes #788)
- **PR #793**: fix(curator): repair idempotency-guard snippet (gh --jq --arg, zsh echo) (closes #789)
- **PR #794**: fix(champion): drop invalid --jq -r flag from 11 pre-existing gh call sites (closes #790)

### 2026-07-29

- **Issue #764** (closed): Tracker: retire local `.claude/commands/loom/sweep.md --claim-owned` patch when the Loom install is upgraded — closed manually (no PR); the tracked Loom v0.16.0 upgrade landed the trigger condition.
- **PR #765**: fix: bump Pillow floor to >=12.3.0, resolving 13 Dependabot alerts (closes #744)
- **PR #769**: feat(memo): add `memo-revise --reject "<reason>"` — lifecycle verb for operator rejection of an advancing version (closes #754)
- **PR #770**: feat(memo): add memo-comprehension cold-reader critic — atom-level plan-reconstruction verification decoupled from the drafter (closes #753)
- **PR #771**: feat(rhetoric_lint): add long-sentence-density default rule (closes #750)
- **PR #772**: feat(memo): add skeleton-first drafting so bodies expand an approved claim tree (closes #752)
- **PR #774**: fix(project-share): strip `__pycache__`, `*.pyc`, and `.DS_Store` from exports (closes #756)
- **PR #775**: feat(project-share): add report-only dangling-citation lint (closes #758)
- **PR #776**: feat(project-share): add `export.cover` / `cover_as` durable cover-note knob (closes #757)
- **PR #777**: config: enable autonomous work-finder in committed loom config
- **PR #778**: fix(config): merge duplicate autonomous blocks into one
- **PR #781**: test(memo): remove stale weasyprint on-PATH test superseded by #308/#311 (closes #779)
- **Guide note**: as of this pass, three issues remain open with fully-implemented, Judge-approved PRs pending human/Champion merge: #746↔PR #761, #743↔PR #763, #751↔PR #773. All three represent completed Builder work, not backlog needing new dispatch.
- **Guide note (later pass)**: applied `loom:blocked` to #746 and #743 (previously unblocked despite each having an open, Judge-approved, mergeable PR — #761 and #763 respectively) to prevent duplicate Builder dispatch, mirroring the existing #751/#773 pattern. All three open issues now carry `loom:blocked`; the `loom:urgent` queue is empty because there is no unbuilt ready work — the rate-limiting step is merging #761/#763/#773.

### 2026-07-28

- **PR #759**: docs(memo): add label-once-then-ledger convention to dim 3 citation hooks (closes #747)
- **PR #760**: feat(rhetoric_lint): add emphasis-density, meta-commentary, and warning-emoji default rules (closes #745)
- **PR #762**: feat(project_brief): accept slides as a third `target_length` unit (closes #742)
- **PR #766**: feat(memo): resolution modes (`removed`/`moved-to-exhibit`) + net-delta reporting for memo-revise (closes #748)
- **PR #767**: feat(memo,deck,proposal,report): require revisers to re-verify review-supplied citations before propagating them (closes #749)
- **PR #768**: feat(project-share): ship runnable `lib/cli.py` argparse entry point (closes #755)

### 2026-07-22

- **PR #733**: feat(paper): orchestrator recommends `paper-vision` for unchecked figures (closes #731)
- **PR #734**: fix(paper): load `voice.md` in `paper-revise`; add default AI-tell prose check (closes #732)
- **PR #736**: chore: update Loom 0.10.6→0.12.0 and Repo Skills 0.3.0→0.4.3
- **PR #737**: docs(paper): add natbib author-year cite-command rule to drafter and reviser (closes #735)
- **PR #739**: fix(vision): gitignore regenerable per-page PNGs from all four vision critics (closes #738)
- **PR #741**: feat(memoir): add `anvil:memoir` skill — chaptered narrative nonfiction reconstructed from a private evidentiary corpus (closes #740)

### 2026-07-15

- **PR #723**: feat(project-brief): accept a list of paths/globs for `code_ref`/`spec_ref` (closes #719)
- **PR #726**: docs(sidecar): make atomic-sidecar CLI invocations consumer-reachable + robuster manual-mv manifest check (closes #724)
- **PR #727**: feat(help): add `anvil:help` orientation utility skill (closes #725)
- **PR #729**: feat(install): always install `anvil:help` regardless of `--skills=` filter (closes #728)
- **PR #730**: feat(spec): vendor botho-bridge-spec AUDITED thread as worked example (closes #709) — real `code_ref` three-way audit + implementation-status register + live `% anvil-const:` constants, terminal `AUDITED`
- **Epic #697 closed (spec artifact class complete)**: all four phases merged — Phase 1 skeleton + `code_ref` resolver (#706), Phase 2 three-way audit verdict + implementation-status register (#707), Phase 3 deterministic constant-consistency gate (#708), Phase 4 vendored worked example (#709/PR #730). Canary dogfood against botho#902's bridge-spec found 3 real spec↔code divergences (fixed upstream) and surfaced follow-on framework friction, all resolved on anvil: findings.md write-guard default (#717), malformed `code_ref` surfacing (#718), `code_ref` list-form for multi-crate trees (#719/#723), sidecar CLI consumer-reachability (#724).

### 2026-07-14

- **PR #687**: feat(primer): add `anvil:primer` artifact class — long-form pedagogical explainer (closes #686)
- **PR #688**: fix(install): prune stale agent files on a `--skills=` narrowing (closes #685)
- **PR #689**: feat(install): detect + hint (opt-in fix) for pre-0.8.0 tracked `.anvil` artifacts (closes #684)
- **PR #695**: feat(primer): place figure references at draft time so exhibits are reachable (closes #690)
- **PR #698**: feat(primer): add `--polish` operator-directed revision path via shared snippet (closes #691)
- **PR #699**: feat(render): four deterministic PDF-render gates from the primer canary (closes #692)
- **PR #700**: docs(primer): vendor trimmed Botho worked example + BRIEF-parse regression test (closes #693)
- **PR #703**: test(memo): add `ArtifactType.PRIMER` to skill-identity pin expectations (closes #702)
- **PR #704**: fix(report): thread page-number CSS via `variables.header-includes` for pandoc 3.x (closes #701)
- **PR #705**: feat(cite): add DataCite fallback for DOIs unregistered with Crossref (closes #696)
- **PR #710**: feat(spec): Phase 1 skeleton — `anvil:spec` artifact class + `code_ref` resolver + `ArtifactType.SPEC` (closes #706)
- **PR #711**: feat(spec): Phase 2 — three-way audit verdict + implementation-status register (closes #707)
- **PR #712**: feat(spec): Phase 3 — deterministic cross-table constant-consistency gate (closes #708)
- **PR #713**: refactor: rename `anvil:pub` skill to `anvil:paper` (closes #694)
- **PR #715**: fix: regenerate `lib/*_schema.json` and add drift guard (closes #714)
- **PR #720**: fix(install): prune upstream-removed/renamed skills on full installs, Stage 7.6 (closes #716)
- **PR #721**: docs(audit): cross-reference `findings.md` harness-guard fallback in six audit commands (closes #717)
- **PR #722**: fix(project-brief): surface malformed `code_ref`/`spec_ref` as `missing=True`, not silent `None` (closes #718)

### 2026-07-13

- **PR #648**: chore(loom): Install Loom 0.10.6
- **PR #649**: docs(pub): reconcile rubric.md Output-layout with pub-review.md's 8-file manifest (closes #647)
- **PR #650**: docs(pub-review): document fail-open manual fallback for uv-gated checks (closes #646)
- **PR #651**: docs(critics): document orchestrator output-file guard collisions with required critic outputs (closes #644)
- **PR #652**: feat(sidecar): add `python -m anvil.lib.sidecar` CLI for driver-less atomic staging (closes #645)
- **PR #654**: feat(pub): make multi-file `\input`/`\include` threads first-class in review (closes #643)
- **PR #657**: docs(installation,proposal): wire review content-read to `tex_includes` resolver; datasheet documented-safe note (closes #653)
- **PR #658**: docs(skills): roll out the #645 two-tier non-Python-driver sidecar fallback clause to the remaining critic-writing docs (closes #655)
- **PR #659**: docs: fix stale sidecar count (45→58) and `scorecard_kind` cross-ref imprecision (closes #656)
- **PR #664**: docs: drop datasheet from findings.md hard-required skill list in critics.md (closes #660)
- **PR #665**: feat(pub): add external-artifact verification gate to pub-review (closes #663)
- **PR #666**: fix(install): scope Stage 7.5 agent copy by `--skills=` (closes #662)
- **PR #675**: fix: bring README status line under version.sh management, fill Skills table (closes #661)
- **PR #676**: docs(pub): fix render-gate input PDF name to `main.pdf` in pub-review/SKILL (closes #667)
- **PR #677**: fix(render_gate): dedupe overfull boxes by (line, amount, kind) on multi-pass logs (closes #668)
- **PR #678**: docs(pub): replace fixed compile pass count with latexmk-style convergence loop (closes #669)
- **PR #679**: feat(lib): add `--body` override to `numeric_consistency` and `evidence_check` body discovery (closes #670)
- **PR #680**: feat(pub): add numeric class option to `anvil-paper.cls` + first-class migration path docs (closes #671)
- **PR #681**: docs(pub): stage version-dir `main.pdf` in pub-audit git-sync scope (closes #672)
- **PR #682**: fix(lib): lazily re-export sidecar primitives to silence runpy RuntimeWarning (closes #673)
- **PR #683**: feat(install): ship self-contained `.anvil/.gitignore` for runtime artifacts (closes #674)

### 2026-07-07

- **PR #625**: fix: resolve `anvil/lib/*` consumer paths to `.anvil/anvil/lib/` in command specs (closes #624)
- **PR #626**: feat(parity): suppress figure-carried economic false-promotions via figures/src CSV corpus (closes #623)
- **PR #627**: fix(marp_lint): make slide-overflow charge aspect- and CSS-flex-aware (closes #622)
- **PR #628**: fix(figures): force dark edge-label text in mermaid theme for v11 legibility (closes #619)
- **PR #629**: fix(render): pass `--no-stdin` so marp never blocks on stdin in non-TTY contexts (closes #620)
- **PR #630**: fix(deck): tolerate unknown per-entry fields in prompt journal reader (closes #621)
- **PR #631**: test(lib): cross-file rubric-threshold consistency lint (closes #618)
- **PR #632**: feat(install): scaffold voice-grounding docs under `.anvil/voice/`, not repo root (closes #617)
- **PR #635**: feat(install): record per-skill `skill_versions` to report skipped-override staleness (closes #633)
- **PR #636**: fix(install,render): resolve marp/figures assets under `.anvil/anvil/lib/` consumer path (closes #634)
- **PR #640**: docs(deck): drop the `.anvil/lib/` overlay layout from deck-imagegen-onboarding (closes #637)
- **PR #641**: fix(scripts): stage CHANGELOG.md in version.sh `--tag` release commits (closes #638)
- **PR #642**: docs: finish `.anvil/lib/` → `.anvil/anvil/lib/` consumer-path migration and widen doc-pin guard to memo/ + .tex (closes #639)

### 2026-07-03

- **PR #610**: docs: backfill post-0.6.0 record (WORK_LOG, CHANGELOG [Unreleased], WORK_PLAN, CLAUDE.md corrections)
- **PR #614**: feat(essay): adopt local-corpus claim-provenance contract in command files (closes #611)
- **PR #615**: feat(pub): adopt local-corpus claim-provenance contract in command files (closes #612)
- **PR #616**: feat(pub,report): adopt the subject voice tier in drafter/reviewer commands (closes #613)


### 2026-07-02

- **PR #609**: feat(templates): add Substrate / Forming positions / Voice modes sections to `VALUES.template.md` + Standing reference-scaffolding prompt (closes #600) — closes the schema gap where essay rubric dims 2/5 and `voice_grounding.md` referenced concepts the template gave authors no place to declare; `REQUIRED_SECTIONS` test tuple 6 → 9
- **PR #608**: feat(rhetoric_lint): document-positional rule scope (`scope: "first-line"`) + `no-opening-emdash` default rule (closes #601) — new `_first_prose_lineno` helper (front-matter/heading stripping); rule count 27 → 28; density-tightening recipe (5/1000 id-collision replacement) documented in the voice README
- **PR #607**: feat(install): Stage 7.9 scaffolds the starter word list as `VOCABULARY.words.txt` (fourth voice-grounding pair, closes #602) — sibling-resolution convention now visible at install time; hint block names `python -m anvil.lib.vocab_reminder`
- **PR #606**: feat(project-book): NEW UTILITY SKILL `anvil:project-book` — multi-thread book assembly (closes #596). Stages `.latest`-resolved chapter threads into a consumer-owned master LaTeX doc (skill-local `build:` BRIEF block), two-pass compile via `compile_and_gate`, per-thread `BOOK_REPORT.md`; build-does-not-block-on-quality (placeholder chapters for EMPTY threads, warn-never-block). Catalog 16 → 17 skills
- **PR #605**: feat(lib): local-corpus claim provenance contract (closes #597) — top-level `corpus:` BRIEF field + `ResolvedCorpusDir`/`resolve_corpus_dirs` (dir-gated, project-first/consumer-fallback) + new `anvil/lib/snippets/provenance.md` (per-version claim→source map, five-way VERIFIED/PARAPHRASE_OK/MISMATCH/NOT_FOUND/FABRICATED classification, five fabrication-class critical flags, `<thread>.{N}.corpus-audit/` sibling). Skill adoption (pub/essay) tracked as follow-ons
- **PR #604**: feat(lib): subject voice tier for the voice-grounding contract (closes #598) — `voice.subjects[]` (per-subject spoken corpus + voice_doc), independently activated from the author tier (`is_empty` untouched), `resolve_subject_voice_docs` mirror resolver, essay pilot wiring with conditional Misattribution critical flag 8. Scope boundary vs #597: this tier owns voice/cadence fidelity; substance verification is the corpus-provenance contract's
- **Sweep note**: #596–#602 (the example-memoir memoir enablement wave + blog-parity batch) ran through two `/loom:sweep` sessions — 7 issues, 7 PRs (#603–#609), 0 doctor cycles; suite 6,531 → 6,708 passing

### 2026-07-01

- **PR #603**: feat(project-photos): NEW UTILITY SKILL `anvil:project-photos` — read-only scanned-photo provenance manifest (closes #599). Human-authored numbering doc → deterministic `manifest.json` (capture → stable name + archive IDs + rotation hint + `multi_item`, `missing_captures` list); byte-identical re-runs, SHA-256-verified zero image mutation; image manipulation stays consumer-native per curation. Catalog 15 → 16 skills

