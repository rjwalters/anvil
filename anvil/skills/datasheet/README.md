# anvil:datasheet

Customer-facing IC / component datasheets — the spec-bearing document a customer designs against. Produced via the canonical anvil lifecycle with a **mandatory audit pass** (`draft → review + audit → revise → … → READY → AUDITED → figures`), tuned for the way a datasheet actually fails: numbers that read fine in isolation but contradict the design source, pins assigned twice, bus fields that cannot represent their claimed range, silent spec changes, pre-silicon values presented as final, and sibling SKUs whose shared-die specs drift apart. All six failure modes were hit hand-authoring two real preliminary datasheets at the studio canary (issue #418); this skill encodes the cleanup.

## Quick orientation

| File | What it is |
|---|---|
| `SKILL.md` | Frontmatter + artifact contract + state machine (incl. `REVIEWED+AUDITED`) + the six canary failure modes. Read this first. |
| `rubric.md` | 9-dimension /44 scorecard (`anvil-datasheet-v1`). **≥39 advances** (customer-facing tier). Five critical-flag conditions (four audit-owned). |
| `commands/datasheet.md` | Portfolio orchestrator. Run from a project root to see per-thread/per-SKU state. |
| `commands/datasheet-draft.md` | Drafter. Brief + `refs/` spec bundle → `datasheet.tex` (XeLaTeX), emitting pin-map + bus-width integrity markers. |
| `commands/datasheet-review.md` | Reviewer. Deterministic pre-flight (render gate + pin-map + bus-width) then scores the 9 dims → `.review/` sibling. |
| `commands/datasheet-audit.md` | Auditor (REQUIRED by default). Spec source-of-truth cross-check (`VERIFIED`/`UNVERIFIED`/`CONTRADICTED`/`NOT-IN-REFS`) + mechanical checks + revision-history READY-gate + shared-die SKU coherence → `.audit/` sibling. |
| `commands/datasheet-revise.md` | Reviser. Aggregates `.review/` + `.audit/` → next version + `changelog.md`, bumping rev + revision-history row when specs changed. |
| `commands/datasheet-figures.md` | Figurer. Renders deterministic TikZ/data figures; stub-by-default for author artwork (package drawings, characterization plots). |
| `templates/anvil-datasheet.cls` | LaTeX class (XeLaTeX): navy `#1F4E7A` accent, part-vendor title block, consistent rev/footer, `featurecolumns` two-column first page, `\est{}`/`\simval{}`/`\meas{}` provenance macros, `\preliminarynotice`. |
| `templates/datasheet.tex.j2` | Section skeleton (Key Features \| Applications → Ordering → Specs → Performance → Pinout → Application → Package → Revision History → Legal) with the integrity markers pre-wired. |
| `templates/BRIEF.md.example` | Reference brief shape (frontmatter + prose). |
| `lib/pinmap_check.py` | Mechanical pin-map integrity checker (`% anvil-pinmap-begin/end` markers; every pin assigned exactly once). |
| `lib/buswidth_check.py` | Mechanical bus-width sanity checker (`% anvil-bus:` markers; `2^W` must cover the claimed set). |
| `tests/` | Structural skeleton test + checker unit tests + template/class compile smoke test (skips without `xelatex`). |

## Reference skills

- **`anvil:proposal`** — the **structural + audit-by-default** reference: LaTeX/XeLaTeX skill with both `.review/` and `.audit/` REQUIRED to leave `DRAFTED` (`REVIEWED+AUDITED`), refs back-check with the four-valued verdict schedule, staged-sidecar atomic critic writes, render-gate pre-flight in the reviewer.
- **`anvil:report`** — the customer-facing-stakes reference (audit by default; the ≥39 tier).
- **`anvil:memo`** — the lifecycle / rubric-format reference.

## What is new in this skill

1. **Spec source-of-truth cross-check** — `refs/` holds the *spec bundle* (model/quant/RTL exports, foundry quotes, package drawings); the audit resolves every numeric claim against it. The spec bundle **outranks the brief** for numbers — the inverse of proposal's brief-is-the-contract rule, because a datasheet's numbers ARE the design's numbers.
2. **Mechanical integrity checkers** — `lib/pinmap_check.py` + `lib/buswidth_check.py`, driven by machine-readable marker comments the drafter is required to emit. Run in both review (pre-flight, `_gate.json`) and audit (findings). Violations are critical flag 2.
3. **Revision-history READY-gate** — spec-bearing changes vs the prior version without a rev bump + history row are critical flag 3; the audit diffs `N-1` vs `N`.
4. **Measured-vs-projected provenance** — `\est{}`/`\simval{}`/`\meas{}` macros + the `status` knob; bare pre-silicon values presented as final are critical flag 4.
5. **Shared-die SKU coherence** — the audit reads sibling SKU threads' latest sheets in the same project and compares the shared-die spec blocks; divergence is critical flag 5.

## Out of scope (v1)

- **Mechanical spec-diff checker** for the revision-history gate (v1 is auditor judgment over a real diff) — natural Phase-2 follow-on.
- **Automated byte-diff of marked shared blocks** across sibling SKU threads (v1 is documented audit judgment) — Phase-3 follow-up.
- **Worked example thread** — the canary's cleaned-up reference sheets, sanitized, can land as a follow-up (issue #418 notes the artifacts are available).
- **PDF text extraction** for spec-bundle PDFs (presence-only in v1, per issue #167).
- **No `anvil/lib/` changes.** The skill consumes `render_gate.py`, `sidecar.py`, `critics.py`, `latest_resolution.py`, and the snippets contracts as-is; critic siblings keep `scorecard_kind: "human-verdict"` with the v0.4.0 `rubric_id`/`rubric_total`/`advance_threshold` stamping.
