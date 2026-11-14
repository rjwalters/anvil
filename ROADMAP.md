# Anvil Roadmap

**Mission**: Make iterative AI-assisted authoring of long-form artifacts as principled as software engineering is — versioned, reviewable, resumable, and audit-trailed.

**Status as of 2026-11-13, `main` @ `15440f27`** (VERSION `0.11.40`). This pass replaced the stale "Near-Term Themes" list with Now / Next / Later, and moved the per-skill and `anvil/lib/` tables to the files that own them ([README.md](README.md) § Skills, [anvil/lib/README.md](anvil/lib/README.md)); the "Core Challenges" table was dropped as a restatement of the README's design principles. What changed in substance is noted inline as *(corrected)*.

## Design Philosophy

1. **Skill identity = artifact identity.** One skill per standardized artifact type, not parameterized meta-skills with `--type` flags. When two skills share infrastructure (renderer, palette, scoring), the sharing lives in `anvil/lib/`, not by collapsing the skills.

2. **Filesystem as substrate.** Versioned directories are the unit of state; sibling directories are the unit of review output; `_progress.json` is the unit of resumability. No database, no forge dependency, no orchestration daemon.

3. **Deterministic gates before judgment.** Cheap mechanical checks (overflow lint, render-gate, page-fit, compile success, placeholder scan) fire *before* the expensive content review. Don't spend an 8-dimension web-fact-checking review on an artifact that doesn't even fit the page contract.

4. **Separation of concerns.** Review is read-only. Revision is separate. Audit is a distinct tool-augmented fact-check (`kind: tool_evidence`). Figure generation is its own role. Rendered-artifact review (`kind: vision`) is a fourth.

5. **Opinionated defaults, override liberally.** Anvil-shipped skills are starting points. Consumers extend them per-project via `.anvil/skills/<name>/` — voice, rubric overlays, templates, asset generators, custom critics.

6. **Subprocess-only by default; Python deps are always optional.** The core install requires no Python packages — renderers (`marp`, `mmdc`, `pdfjam`, `pdftoppm`, `xelatex`, `pandoc`) are subprocess calls. Advanced detectors that need a Python library are exposed as opt-in extras (`uv pip install -e .[auto_shrink]`).

7. **Canary-driven development.** Anvil is sharpened by being used. The [2AM Logic Studio canary](https://2amlogic.com) runs the framework against real authoring work; the friction it surfaces drives the prioritization. Issues labeled `tier:goal-supporting` are canary-surfaced production signal; `tier:maintenance` is technical debt and editorial cleanup.

---

## Where it stands

- **Twenty-four skills ship** under `anvil/skills/`: fourteen artifact classes (`memo`, `paper`, `report`, `deck`, `slides`, `ip-uspto`, `ip-uspto-provisional`, `installation`, `proposal`, `datasheet`, `essay`, `primer`, `spec`, `memoir`) and ten bridge / utility skills (`project-migrate`, `rubric-rebackport`, `project-share`, `project-scout`, `project-photos`, `project-book`, `help`, `deslop`, `diff`, `ip-search`). Each artifact class carries a draft → review → revise → (audit) → figures lifecycle with skill-specific variations, a scored rubric (9 dimensions / 44; the two `ip-uspto` skills / 45; `deck` 10 dimensions / 49), templates and a worked example.
- **Shared primitives live in `anvil/lib/`** and are indexed in `anvil/lib/README.md`: typed `_review.json` (`review_schema.py`), critic aggregation (`critics.py`), convergence, crash-safe sidecar writes (`sidecar.py`), `render_gate/`, and the deterministic pre-flight checks (`marp_lint.py`, `numeric_consistency.py`, `rhetoric_lint.py`, and others).
- **Reader-flow work for `paper` (#1396) is shipped but not accepted.** The lens subagent and its deterministic companions merged (#1397–#1401: `reader_flow_lint.py`, `float_proximity.py`, `numeral_multiset.py`, quoted-number variants), and the follow-ups from the first acceptance run closed (#1417–#1420, #1432, #1437). Acceptance clause 1 (recall against external findings) is recorded as met; clause 2 (fewer recurring findings on flow-revised versions) is **not met** — see [`docs/research/readerflow-acceptance-20261031.md`](docs/research/readerflow-acceptance-20261031.md).
- **Slides gained an import path and operator-directed revision** (#1368, #1369, #1373); deck re-review and dim-10 overrides were fixed (#1449, #1450, PRs #1451, #1453).
- **Codex registration and the essay claim ledger are shipped** (#1000, #1198; docs marked in PR #1473).
- **Tests:** a full local run of `pytest` at this sha gave 10753 passed, 20 skipped, **1 failed** (`tests/scripts/test_install_uv_runnable.py::test_install_produces_consumer_pyproject_toml`). The only GitHub Actions workflow is `version-bump-gate.yml`; no workflow runs the test suite on pull requests, which is how this failure and the similar #1466 reached `main`.
- *(corrected)* The old theme "cross-skill lint sharing" is done: `marp_lint` was promoted to `anvil/lib/marp_lint.py` (#318), and the deck and slides copies are 26-line re-exports.
- **Tracker:** seven open issues, none ready for a Builder (five pre-existing, plus #1480 and #1481 filed by this pass as `loom:triage`); one open PR (#1360). [WORK_PLAN.md](WORK_PLAN.md) was last regenerated 2026-10-27 and still lists #1396 as proposed; it is blocked.

## Now

Can start today; one PR each. Both are now filed as `loom:triage` — #1480 (item 1) and #1481 (item 2) — and neither is dispatchable until a human promotes it.

1. **Mirror the `setuptools>=84.2.1` floor into the consumer pyproject.** PR #1475 raised `[build-system].requires` in `pyproject.toml`; the heredoc in `scripts/install-anvil.sh` (`write_consumer_pyproject()`) still writes `setuptools>=84.0.0`. *Done when* the failing test above passes and the full suite is green. Installed surface, so the PR carries a VERSION bump and a CHANGELOG entry. Blocked by: nothing.
2. **Close the index gaps and guard them.** `anvil/lib/README.md` does not list `float_proximity.py` or `numeral_multiset.py`; `docs/README.md` does not list `research/readerflow-acceptance-20261031.md`. *Done when* all three are listed and a test fails if a `anvil/lib/*.py` module or a `docs/**/*.md` file is missing from its index. Blocked by: nothing.

## Next

3. **Run the test suite on pull requests.** *Done when* a workflow runs `pytest` on `pull_request` and is green on `main`. Unblocked once item 1 lands (the suite must be green first); needs a maintainer decision on where the roughly eight-minute suite runs.
4. **Settle reader-flow acceptance clause 2 (#1396).** Unblocked by the ruling on #1441. If the ruling is "multi-read union per side": extend `anvil/skills/paper/lib/readerflow_recurrence.py`, re-measure the three papers, and update the results record and its fixtures. *Done when* the record states pass or fail under the ruled measure and #1396 closes or is re-scoped.
5. **Finish live verification of `slides-import` (#1381).** Part A (skip-gated real-poppler test) merged in #1382. Part B needs `pdftotext`, `pdftoppm` and Marp on the machine that runs it. *Done when* the three checks in #1381 are posted with results, or the issue is closed under its ruling.

## Later

Direction only; each waits on the question stated.

- **Typed output for the older audit commands.** Eight of the eleven `*-audit` commands write prose plus a `scorecard_kind` declaration and no `_review.json`: `deck-audit`, `slides-audit`, `ip-uspto-audit`, `ip-uspto-provisional-audit`, `primer-audit`, `spec-audit`, and — already declaring `kind: tool_evidence` without emitting it — `datasheet-audit` and `memoir-audit`. Only `paper-audit`, `report-audit` and `proposal-audit` emit it. `anvil/lib/README.md` still lists the migration to `kind: tool_evidence` as a follow-up, and still names the five pre-migration commands. *Question:* is prose plus `scorecard_kind` the intended end state, or does each audit emit `_review.json` with `tool_calls[]`? *(corrected: the old text named five commands and predates `scorecard_kind`; eight lack `_review.json` at this sha — the two that already declare the typed kind are the sharpest case for the question.)*
- **Per-skill `lib/` extraction → `anvil/lib/`.** Report's `ack.py`, `audit_flags.py` and `pdf_freshness.py` and deck's `auto_shrink_detector.py` remain skill-local. *Question:* has a second skill needed one? Trigger is observed duplication, not anticipated need.
- **Memo-side gates.** `anvil:memo` is markdown-first (maintainer decision, #64). *Question:* has consumer friction shown the need for a markdown length proxy and clean-output gate?
- **Render-gate override ergonomics.** Per-thread `.anvil.json` overrides (`page_cap`, etc.) are part of the contract. *Question:* what friction do consumers report when setting them?
- **Reference-skill category.** Floated as #9 and deferred (a knowledge base violates load-bearing primitives). *Question:* does a real use case appear?
- **Portfolio orchestrators.** Each skill is single-thread; portfolio-level commands (the slides gap detector, #85) are nascent. *Question:* do the patterns repeat across skills?

### Candidate artifact classes (ideation)

Ideation only — **none of these is committed work.** Per design principle 7, "Canary-driven development," a new artifact class ships when a live downstream consumer produces the genre and hits friction none of the current classes fit (the way botho drove `primer` #686 and `spec` #697). This list records the candidates worth reaching for *when* that signal appears; it is not a build queue.

The bar a candidate must clear (what separated `primer`/`spec` from being `report` variants): (a) a **dominant success metric** that is a genuinely new axis, not one of an existing skill's dimensions; (b) real genre conventions a rubric can encode; (c) ideally a **companion input feeding a consistency audit** — the `spec_ref`/`code_ref` pattern is now reusable infrastructure and is anvil's differentiator over a generic "write me a doc" prompt; (d) deterministic pre-flight gates are possible.

Strongest candidates, each mapped to the pattern:

| Candidate | Dominant metric (new axis) | Companion input / audit | Notes |
|---|---|---|---|
| `app-note` (application note) | Design-in reproducibility — an engineer following it reaches a working circuit | `datasheet_ref` → does the note contradict the part's actual limits? (reuses the `code_ref` audit shape) | **Highest-signal candidate**: neighbor to the shipped `datasheet`. "Tutorial, for hardware." |
| `api-reference` | Accuracy + completeness against the API surface | `code_ref` / OpenAPI doc → every public symbol documented, no documented symbol that doesn't exist | Nearly falls out of `spec` for free; add a deterministic completeness gate. |
| `runbook` | Executable safety — every step unambiguous, ordered, verifiable, reversible | reference to the scripts/infra it drives | Distinct from `installation` (one-time setup) and `spec` (normative description). Natural gates: every step has a verification + a rollback. |
| `tutorial` / `how-to` | Task-completion success — reader reaches a working end state | the tool/API being taught | The task-completion sibling to `primer`'s concept-explanation. Clear boundary against `primer`. |
| `threat-model` | Attack-surface coverage + severity calibration | system architecture / code | Audit-grade like `spec`/`report`; distinctive and increasingly in demand. |

Explicitly **not** their own class (fold into an existing skill — recorded so the line is documented):

- ADR → a `memo` variant (decision record with a thesis).
- case-study, market / competitive analysis → `report` variants.
- RFP response → a `proposal` variant.
- literature review → already inside `paper` (litsearch).
- thesis, course, multi-lesson curriculum → `project-book` assembly, not a new class.
- release-notes → likely a *utility* (generated against a git range), not an authored artifact class — cf. the deferred "Reference-skill category" item above.


## Blocked and waiting

**Nothing in the tracker is dispatchable today**; the two Now items above are the only startable work and neither is filed.

- **#1441** (`loom:operator`): how to handle reader-flow clause 2, given that cross-version recurrence is not separable from the same-version noise floor. Blocks #1396 (`loom:blocked`).
- **#1381** (`loom:operator`): how Part B of the `slides-import` verification is run.
- **PR #1360** (Renovate, opened 2026-10-12, now conflicting) and **#1355** (Dependency Dashboard, `loom:blocked`): the repo has no Renovate config and takes updates through `.github/dependabot.yml` (PRs #1447, #1475). Waiting on a maintainer decision to close both.
- **#1224** (Champion merge-risk hold digest, `loom:blocked`): a standing tracker issue, not work.

---

## Not planned (what Anvil is not)

To keep scope honest:

- **Anvil is not a document generator.** It orchestrates *iterative authoring* — drafter, reviewer, reviser, auditor. The drafter is an LLM agent following a skill's command spec; Anvil doesn't generate the content itself.
- **Anvil is not a renderer.** It shells out to `marp`, `pandoc`, `xelatex`, `mmdc`, `pdftoppm`. The renderer choices are pinned (e.g. Marp for slides, MathJax not KaTeX) but the rendering itself happens in subprocess.
- **Anvil is not a forge.** No GitHub-style PR workflow for the artifacts. The version history is the audit trail; collaboration happens via shared filesystem + (optionally) git.
- **Anvil is not opinionated about voice.** Each skill ships defaults; consumers override via `.anvil/skills/<name>/voice.md` and other extension points.
- **Anvil is not yet** broadly distributed. The framework hardens through real use, not speculative design — v0.11.x is driven by several live canary consumers (2AM Logic Studio; botho, which drove `primer` and `spec`; `walters-family-tree`, which drove `memoir`; geode-fem and the Tractatus Lean-4 project on `paper`) rather than one.

## Release Cadence

We don't ship on a fixed cadence. Releases are cut when a coherent batch of canary-surfaced friction has been addressed and the codebase is at a clean point. See `scripts/version.sh` for the version-file list and the release skill (`/loom:release` if installed locally) for the cut process.

See [CHANGELOG.md](CHANGELOG.md) for the version history.
