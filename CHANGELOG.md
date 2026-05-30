# Changelog

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
