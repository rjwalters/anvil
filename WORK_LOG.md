# Work Log

Chronological record of merged PRs and closed issues. Maintained by the Guide triage agent.

---

### 2026-05-30

- **PR #105**: feat(deck): silent Marp auto-shrink detector + Anvil's first `pyproject.toml` (closes #102)
- **PR #104**: feat(deck): `figure-italic-supporting-line-too-long` lint + word budget (closes #101)
- **PR #103**: docs(readme): update to reflect installable v0.0.1 with 8 shipped skills
- **PR #99**: feat(figures): per-glyph Unicode fallback + 4 semantic mermaid classDefs (closes #92)
- **PR #98**: docs(ip-uspto): normalize critic phase names to use critic tag (closes #88)
- **PR #97**: fix(install): error on bare `--skills=` (closes #82)
- **PR #96**: docs(ip-uspto): clarify Check 7 is string-presence, cross-ref Check 9 (closes #87)
- **PR #95**: fix(slides): pdfjam OPTIONAL + `.0.outline` orchestrator exemption (closes #85)
- **PR #94**: fix(report): reviewer enforces PDF existence + freshness for Dim 7 (closes #84)
- **PR #93**: fix(install): make `--dry-run` honest about what it did not do (closes #81)
- **PR #91**: fix(report): strengthen ack-file matching + flag unreachable citations as critical (closes #83)
- **PR #90**: fix(deck): reconcile slide-order across drafter, critics, archetypes (closes #86)
- **PR #89**: fix(install): remove `sh -c` indirection so quoted paths survive (closes #80)
- **Issue #100** (umbrella, closed): decomposed into #101 + #102 — two residual overflow modes in the post-#68 figure idiom surfaced by 13-deck canary re-render wave
- **Issue #21** (umbrella, closed): decomposed into 9 focused issues (#80–#88) — PR-wave follow-ups from #15–#20
- **Issue #106** (opened, follow-up to #105): declare `pydantic` in `pyproject.toml`; `anvil/lib/__init__.py` eagerly imports `cite` which requires it

### 2026-05-29

- **PR #79**: feat(lib): render-gate primitive + wire into 5 paginated skills (closes #64) — `anvil/lib/render_gate.py` (page-fit, overfull, compile, placeholder); wired into pub/report/installation/proposal/ip-uspto; memo OUT of scope per maintainer (markdown-first)
- **PR #78**: fix(slides): correct mermaid-PDF claim in `slides-revise.md` (closes #77)
- **PR #76**: fix(slides): wire `mmdc` preflight + strengthen smoke test (closes #70) — slides-side of the #32/PR #40 inline-mermaid regression
- **PR #75**: test(deck): add #50 white-on-white ask-table regression armor (closes #57)
- **PR #74**: feat(figures): ship `anvil/lib/figures/` shared brand-palette primitive (closes #69) — `palette.py` + `anvil.mplstyle` + `mermaid-theme.json` + CSS-drift guard test
- **PR #72**: fix(deck): make mmdc-rendered PNG the working diagram path; preflight + dep check (closes #65) — corrected #32's false inline-mermaid claim across deck + slides docs; added `mmdc` preflight; added `install-anvil.sh --check-deps`
- **PR #68**: fix(deck): replace overflow-prone figure+bullets and ask H1+H2 idioms in template (closes #24, #25)
- **PR #67**: docs(deck): add matplotlib `figure-conventions.md` and wire cross-references (closes #23)
- **PR #66**: docs(snippets,memo): fix phantom phase state and tighten `_meta.json` contract docs (closes #36) — contract bug in `progress.md` snippet
- **PR #63**: test: complete `__init__.py` package chain for deck/slides/proposal test dirs (closes #58)
- **PR #62**: feat(proposal): implement `anvil:proposal` skill (buildable-system proposals) (closes #60)
- **PR #61**: feat(installation): implement `anvil:installation` skill (experiential artwork) (closes #59)
- **Issue #51** (umbrella, closed): decomposed into #59 + #60 — new artifact classes for non-investment studio works
- **PR #56**: feat(ip-uspto): add `ip-uspto-vision` VLM critic for patent drawings (closes #48)
- **PR #55**: fix(deck): make ask-slide tables readable by defeating Marp default cell bg (closes #50)
- **PR #54**: feat(report): add `report-vision` VLM critic for rendered PDFs (closes #47)
- **PR #53**: feat(pub): add `pub-vision` VLM critic for rendered research papers (closes #46)
- **PR #52**: feat(slides): add `slides-vision` VLM critic command + tests (closes #45)
- **PR #49**: feat(lib): VLM critic primitive + `deck-vision` sibling (closes #30) — `anvil/lib/render.py` + `anvil/lib/vision.py` + first consumer
- **PR #44**: feat(pub): venue-pinned advisory rubric overlays alongside generic /40 (closes #33) — `anvil/lib/rubric.py` + neurips/nature/arxiv YAMLs
- **PR #43**: docs(lib): codify `.review/` vs `.audit/` as CRITIC judgment-vs-tool-evidence split (closes #29) — new `anvil/lib/snippets/audit.md`
- **PR #42**: feat(lib): add stable-score termination as secondary stop condition (closes #27) — `anvil/lib/convergence.py` with `STALLED` verdict
- **PR #41**: feat(lib): shared citation primitive `anvil/lib/cite.py` (closes #28) — DOI + arXiv resolvers, stdlib-only, idempotent `refs.bib`
- **PR #40**: feat(lib): document MathJax + `--html`/mermaid figure pipeline as canonical Marp config (closes #32) — *NOTE: this PR shipped the inline-mermaid-default design that turned out to be wrong; corrected by PR #72 a day later*
- **PR #39**: feat(lib): canonical `_review.json` schema, discovery + aggregation (closes #26) — `review_schema.py` + `critics.py` with legacy adapters
- **PR #38**: feat(deck,slides): wire `slide-content-overflow` lint into review phase (closes #31)
- **PR #37**: feat(ip-uspto): add `_outline.json` control surface for chunked drafting (closes #34)
- **PR #35**: feat(lib): extract `anvil/lib/snippets/` and migrate 6 skills (closes #10) — markdown-snippet convention layer

### Earlier (skills v0 implementation phase)

- **PR #20** → closed #4: implement `anvil:ip-uspto` skill
- **PR #19** → closed #6: implement `anvil:deck` skill (Marp)
- **PR #18** → closed #7: implement `anvil:slides` skill (Marp)
- **PR #17** → closed #8: implement `anvil:report` skill
- **PR #16** → closed #5: implement `anvil:pub` skill
- **PR #15** → closed #11: implement `scripts/install-anvil.sh`
- **PR #13** → closed #3: implement `anvil:memo` skill
- Initial commit + scaffolding

---

## Maintenance notes

- **PR #40 (canary-introduced regression)**: this PR shipped #32's inline-mermaid-as-default design. The studio canary's 12-deck render wave (resolved #65/#72) proved the claim false — inline mermaid leaks as raw code in the rendered PDF; `mmdc → PNG` is the only working diagram path. Both smoke tests at the time only checked "non-empty PDF + exit 0", which is why it slipped through review. Lesson recorded in #70: *"renders to a non-empty PDF" ≠ "renders correctly"*.
- **Decomposition pattern**: Three umbrellas were decomposed during this period (#21 → 9 issues; #51 → 2; #100 → 2). Decomposition is preferred over bundled umbrellas when items have different risk profiles or touch independent files.
- **Curator-skip pattern**: For one-line / mechanically-checkable fixes, we skipped the curator phase and built directly from the issue body (#77, #82, #87, #88). Same for direct-verify in lieu of a judge agent (#77, #87, #97, #98, #103). Reserve agent dispatch for substantive code review.
- **#105 introduced Anvil's first `pyproject.toml`**. The deps philosophy is documented in its top comment: subprocess-only by default; Python deps are optional extras with preflight + remediation.
