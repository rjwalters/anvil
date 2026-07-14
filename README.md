# Anvil

**AI-powered artifact creation using filesystem versioning as the coordination layer.**

Anvil orchestrates iterative drafting, review, and revision of long-form artifacts — investment memos, patent applications, research papers, pitch decks, technical reports, art installations, customer proposals, short-form essays. Each artifact lives in an immutable versioned directory; review passes write to read-only sibling directories; revisions consume both and produce the next version. The version history *is* the audit trail.

**Status:** v0.8.0. Installable — see the Skills table below for the current list. Actively developed against a real-world canary consumer ([2AM Logic Studio](https://2amlogic.com)) — the framework is sharpened by being used, not by being designed in isolation.

**Sibling project:** [Loom](https://github.com/rjwalters/loom) does this for code (issues, PRs, forge coordination). Anvil does this for prose-and-graphics artifacts (filesystem coordination, no forge required). Both can be installed in the same repository.

## Skills

| Skill | Artifact type | Output |
|---|---|---|
| `anvil:memo` | Investment memos, internal documents | Markdown |
| `anvil:pub` | Research papers | LaTeX → PDF |
| `anvil:report` | Customer-facing technical reports (engagement findings, audits, advisories) | Markdown → PDF |
| `anvil:deck` | Investor pitch decks | Marp Markdown → PDF |
| `anvil:slides` | Talk / conference slides | Marp Markdown → PDF + speaker notes |
| `anvil:ip-uspto` | USPTO non-provisional utility patent applications | LaTeX → PDF |
| `anvil:ip-uspto-provisional` | USPTO provisional patent applications (claims-optional, enablement-depth-first; conversion seed for `anvil:ip-uspto`) | LaTeX → PDF |
| `anvil:installation` | Experiential / installation artwork (concept proposals) | LaTeX → PDF |
| `anvil:proposal` | Buildable-system proposals (pre-contract pitch to a customer or budget sponsor; pre-contract bookend to `anvil:report`) | LaTeX → PDF |
| `anvil:datasheet` | Customer-facing IC / component datasheets (mandatory spec source-of-truth audit, pin-map/bus-width integrity pre-flight, revision-history gate, shared-die SKU coherence) | LaTeX → PDF |
| `anvil:essay` | Short-form voice-grounded essays / blog posts (voice fidelity as the owned rubric dim, convergence-blocking numeric/link gates, READY-terminal publish handoff — site deploys stay consumer-native) | Markdown |
| `anvil:primer` | Long-form pedagogical explainers (teach-from-intuition companion to a formal spec; pedagogical scaffolding as the owned dominant rubric dim, an optional `spec_ref` companion input feeding a spec-consistency audit, AUDITED-terminal publish handoff) | Markdown (+ optional PDF) |
| `anvil:project-migrate` | One-shot bridge tool: migrates pre-#283 / post-#283 studio projects to the post-#295 / post-#296 model (project root + `BRIEF.md` + `<slug>.md` body filename) | Filesystem migration |
| `anvil:rubric-rebackport` | One-shot bridge tool: stamps or rescores legacy /40 reviews under the per-review rubric version stamping contract (`rubric_id` / `rubric_total` / `advance_threshold`) | In-place `_meta.json` stamping / rescore sidecars |
| `anvil:project-share` | Recurring packaging tool: collects each thread's `.latest`-resolved source + PDF + assets + refs and the shared research pool into one shareable, provenance-stamped folder | `SHARE/` export (+ optional zip) |
| `anvil:project-scout` | Strictly read-only discovery tool: walks a repo tree and classifies anvil-adoptable document clusters (already-migrated / legacy-migratable / bare threads / loose documents / foreign grammar), naming the recommended next command per cluster | Markdown adoption report (+ optional JSON sidecar) |
| `anvil:project-photos` | Strictly read-only provenance tool: reads a human-authored numbering doc for a scanned-photo archive and emits a deterministic manifest map (original capture → stable name + archive item IDs + rotation hint + multi-item flag, plus a missing-captures list) — byte-identical re-runs, image manipulation stays consumer-native | `manifest.json` provenance map |
| `anvil:project-book` | Recurring assembly tool: stages the `.latest`-resolved version of every chapter thread into a consumer-owned master LaTeX document, two-pass compiles it into one book, and writes a per-thread convergence report (state / score / audit + next command) | `book.tex` → PDF + per-thread `BOOK_REPORT.md` |

Each skill ships a complete lifecycle (`draft → review → revise → audit → figures`, with some variants), a tunable 8-dimension scoring rubric, opinionated templates, and a worked example thread. Consumers extend them per-project via `.anvil/skills/<name>/` in the consumer repo.

## Installation

Anvil installs into a target repository (the consumer repo) where you do the authoring work. The installer copies the framework + selected skills, writes thin Claude Code skill registrations, generates a consumer-side `pyproject.toml`, and appends an Anvil section to the target's `CLAUDE.md`.

```bash
# Install everything into the current directory
./scripts/install-anvil.sh .

# Install only specific skills
./scripts/install-anvil.sh --skills=memo,deck /path/to/target-repo

# Preview without writing
./scripts/install-anvil.sh --dry-run /path/to/target-repo

# Skip the post-install `uv sync` step (offline or no-uv installs)
./scripts/install-anvil.sh --no-sync /path/to/target-repo

# Check renderer dependencies (marp, mmdc, pdfjam, poppler/pdftoppm)
./scripts/install-anvil.sh --check-deps
```

After installation you invoke the skills from Claude Code in the consumer repo — e.g. `anvil:memo my-thesis` to draft a memo, then `memo-review my-thesis` to score it.

### Installing into an existing monorepo

The installer is designed to coexist with whatever already lives at the consumer root. Its full write footprint is:

- `.anvil/` — the framework + skills, self-contained, with its own `pyproject.toml`. `uv sync --project .anvil` resolves against that file only, so the anvil venv stays independent of the monorepo's own uv project (root `pyproject.toml` / `uv.lock` are never read or written). It also ships a self-contained `.anvil/.gitignore` (patterns `__pycache__/`, `*.py[cod]`, `.venv/`) so the Python bytecode caches and the uv venv the framework generates never dirty `git status`; that file is written once (skip-if-exists) and your root `.gitignore` is never touched.
- `.claude/skills/anvil-<skill>/` and `.claude/agents/anvil-*.md` — per-skill directories and per-file copies, namespaced so pre-existing skills and agents (e.g. `loom-*` entries from a sibling [Loom](https://github.com/rjwalters/loom) install) are untouched.
- `CLAUDE.md` — the only root-level file the installer writes. It appends one marker-bounded block (`<!-- BEGIN ANVIL --> … <!-- END ANVIL -->`) after your existing content; re-installs replace that block in place rather than appending a duplicate. Everything outside the markers — including a Loom section — passes through verbatim. (One nuance: if your CLAUDE.md ends in multiple blank lines, the first install normalizes that trailing run to a single blank line before the block.)

Root `pyproject.toml`, `uv.lock`, `package.json`, `Makefile`, `.loom/`, etc. are never modified. This contract is pinned by `tests/scripts/test_install_monorepo_coexistence.py`.

### Running anvil Python from a consumer (issue #230)

Some skill commands (memo-render, render-gate consumers, etc.) call `from anvil.lib.render_gate import gate` directly. The installer ships an uv-runnable `<consumer>/.anvil/` layout so this works without cloning the anvil source repo on the consumer machine:

```bash
# Default install runs `uv sync --project .anvil` for you at Stage 10.5.
# If you used --no-sync, materialize the consumer venv manually:
uv sync --project .anvil

# Then invoke framework Python from the consumer root:
uv run --project .anvil python -c "from anvil.lib.render_gate import gate; print(gate.__module__)"
```

The generated `.anvil/pyproject.toml` declares the framework's base runtime deps (`pydantic`, `pyyaml`); no manual `uv add` is required. The importable `anvil/` package mirror lives at `<consumer>/.anvil/anvil/`, fully self-contained — the install-time `anvil_source` recorded in `install-metadata.json` is provenance metadata only and is not consulted at runtime. The pre-#230 install layout (`.anvil/lib/` for framework Python) is detected on upgrade and surfaced with a one-line migration warning; no auto-deletion (hand-edited override files there are preserved for the operator to port).

### Running critics from multiple git worktrees

If your orchestration dispatches critics into sibling git worktrees of the same repo (e.g. a [Loom](https://github.com/rjwalters/loom) builder/critic layout where each issue gets its own worktree), two extra setup steps keep the anvil Python path clean:

- **Pre-sync each worktree.** A git worktree has its own checkout of `.anvil/`, so its `.anvil/.venv` starts empty. The first `uv run --project .anvil ...` in a fresh worktree triggers a cold `uv sync` — fine serially, but two critics dispatched into the *same* fresh worktree can race that first sync. Run `uv sync --project .anvil` as an explicit per-worktree setup step (e.g. from your dispatch/setup hook, before invoking any anvil command) rather than relying on lazy first-`uv run` sync:

  ```bash
  # In each fresh worktree, before dispatching critics:
  uv sync --project .anvil
  ```

- **`UV_LINK_MODE=copy` for cross-filesystem worktrees.** When a worktree lives on a different filesystem/volume from the uv cache (e.g. a `worktree.root` pointed at a separate mount), every `uv sync`/`uv run` prints `Failed to hardlink files; falling back to full copy`. Set `UV_LINK_MODE=copy` to make the copy fallback explicit and silence the warning:

  ```bash
  export UV_LINK_MODE=copy          # env var, per shell/dispatch hook
  # — or pin it in .anvil/uv.toml / .anvil/pyproject.toml:
  #   [tool.uv]
  #   link-mode = "copy"
  ```

The `.anvil/.gitignore` shipped by the installer already covers the `__pycache__/` and `.venv/` artifacts each worktree generates, so a pre-synced worktree stays clean in `git status`.

### Memo styling: the starter theme

The framework's memo stylesheet is deliberately minimal (black-on-white, no accents) — branding belongs to the consumer, not the framework default. So an install that includes `memo` also scaffolds a consumer-owned **starter theme** at `.anvil/themes/starter/` (navy-accented headings and table rules over the same functional baseline). The scaffold is skip-if-exists: the installer never overwrites anything under `.anvil/themes/`, so your edits survive every re-install and `--force` upgrade.

The theme is inert until a project opts in. Enable it by declaring the theme in the project `BRIEF.md` frontmatter:

```yaml
theme: starter
```

The durable override path for memo styling is `.anvil/themes/<theme>/memo/styles.css`. Editing the installed framework copy at `.anvil/anvil/lib/memo/styles.css` also works but is overwritten on every re-install/upgrade — prefer the theme tier.

### Renderer dependencies

The skills shell out to language-appropriate renderers. None are required by the install itself; each is needed only by the skills that use it.

| Tool | Used by | Install |
|---|---|---|
| `marp` (Marp CLI) | `deck`, `slides` | `npm install -g @marp-team/marp-cli` |
| `mmdc` (Mermaid CLI) | `deck`, `slides` (for diagrams) | `npm install -g @mermaid-js/mermaid-cli` |
| `pdfjam` (TeX Live) | `slides --4-up` / `--2-up` handouts only | `apt install texlive-extra-utils` (Linux) / `brew install --cask mactex-no-gui` (macOS) |
| `pdftoppm` (poppler) | Rendered-artifact critics | `apt install poppler-utils` / `brew install poppler` |
| `xelatex` / `pdflatex` | `pub`, `ip-uspto`, `ip-uspto-provisional`, `installation`, `proposal` | TeX Live / MacTeX |
| `pandoc` | `report` | `apt install pandoc` / `brew install pandoc` |

Run `./scripts/install-anvil.sh --check-deps` to see which are present on your system with remediation hints.

## Design principles

1. **Filesystem as substrate.** Versioned directories (`{thread}.{N}/`) are immutable. Sibling directories (`{thread}.{N}.review/`, `.audit/`, `.<critic>/`) hold read-only critic output. Revisions read both and write `{N+1}/`.
2. **Scored review rubric.** 8 weighted dimensions, /40 total, ≥32 to advance (≥35 for legal / customer-facing artifacts). Critical-flag short-circuit.
3. **Checkpointing.** `_progress.json` per version directory tracks phase state; long phases skip on resume; validation is by file existence, not flag.
4. **State machine.** `EMPTY → DRAFTED → REVIEWED → REVISED → … → READY → AUDITED` (with skill-specific extensions like `CUSTOMER-READY` for `report` and `FINALIZED` for `ip-uspto`).
5. **Separation of concerns.** Review is read-only. Revision is separate. Audit is a distinct tool-augmented fact-check. Figure generation is its own role.
6. **N parallel critics, one reviser.** Multiple critic siblings (`.review/`, `.audit/`, `.vision/`, `.s101/`, ...) feed a single reviser pass — first-class primitive, not a special case.
7. **Deterministic pre-flight where possible.** Rendered artifacts get cheap mechanical gates (overflow lint, render-gate, page-fit, compile success, placeholder scan) *before* the expensive content review fires.
8. **Forge-optional.** Anvil works on a single laptop with no GitHub account. A forge can be added for collaboration but is not required.
9. **Opinionated defaults, override liberally.** Anvil-shipped skills are starting points. Consumers extend them with project-specific voice, rubrics, templates, and asset generators via `.anvil/skills/<name>/`.
10. **Skill identity = artifact identity.** One skill per standardized artifact type, not parameterized meta-skills with `--type` flags. When two skills share infrastructure (renderer, palette, scoring primitive), the sharing lives in `anvil/lib/`, not by collapsing the skills.

**Optional Python extras.** Anvil's core ships subprocess-only (no Python deps). Advanced detectors that need a third-party library are exposed as opt-in extras:

```bash
uv pip install -e .[auto_shrink]   # enables the anvil:deck silent-Marp-auto-shrink lint (#102)
```

When an extra isn't installed, the corresponding check gracefully skips and the surrounding command (e.g. `deck-review`) proceeds normally with a clear remediation message in its output.

## Repository layout

```
anvil/
  skills/        Per-artifact-type skills (memo, pub, report, deck, slides,
                 ip-uspto, ip-uspto-provisional, installation, proposal,
                 datasheet, essay). Each has SKILL.md +
                 commands/ + rubric.md + (optional) templates/, assets/,
                 examples/, tests/, lib/.
  lib/           Shared framework primitives.
    snippets/    Pure-markdown conventions every skill reads (progress,
                 timestamp, version_layout, thread_state, state_machine,
                 rubric, critics, scorecard_kind, audit, cite,
                 perspective).
    review_schema.py   Typed _review.json contract (kind: judgment |
                       tool_evidence | vision) + JSON Schema export.
    critics.py         Sibling-critic discovery, aggregation, verdict
                       computation; legacy-shape adapters.
    convergence.py     check_stable + decide_termination (multi-iteration
                       termination — STALLED verdict).
    cite.py            DOI / arXiv resolver, BibTeX writer, idempotent
                       refs.bib.
    rubric.py          Rubric models + venue-pinned overlay discovery
                       (.anvil.json venue → optional advisory rubric).
    render.py          Marp → PDF, PDF → PNGs, pandoc → PDF, matplotlib
                       walker, mmdc/pdfjam preflight helpers.
    render_gate.py     Deterministic gate over compiled PDFs (page-fit,
                       overfull boxes, compile success, placeholder scan).
                       LaTeX-skill analog of marp_lint.
    vision.py          VisionCritic + VisionRubric (vision-model review
                       of rendered artifacts).
    figures/           Shared figure-theming primitive (matplotlib
                       mplstyle, palette tokens, mermaid theme).
    marp/              Pinned Marp config (MathJax + html, mmdc-required
                       diagram path).
  templates/     SKILL.md scaffolds.
  roles/         Generic role definitions (planned).

scripts/
  install-anvil.sh   Install anvil into a target repo.
  version.sh         Version management.

tests/
  lib/           Framework-level tests (review_schema, critics, cite,
                 convergence, rubric, render, vision, render_gate, figures).
  scripts/       Install-script tests (quoting, dry-run honesty,
                 --skills= validation).
```

## Working with Anvil (overview)

A typical authoring loop for any skill looks like:

1. **`<skill>-draft <thread>`** — drafter produces `<thread>.1/` with the artifact body, exhibits, and `_progress.json`.
2. **`<skill>-review <thread>`** — reviewer (and any specialist critics) score against the rubric; output lands in `<thread>.1.review/`. Optional deterministic pre-flight (render-gate / marp_lint / mmdc preflight) runs first.
3. **`<skill>-revise <thread>`** — reviser reads the prior version + all critic siblings and writes `<thread>.2/` with a `changelog.md` mapping critic notes to changes.
4. Loop until rubric threshold met (default ≥32 / 40) or stable-score termination.
5. **`<skill>-audit <thread>`** *(skills with audit phase)* — tool-augmented fact-check against external sources (citation resolution, BOM arithmetic, prior-art search, etc.). Emits `kind: tool_evidence` findings.
6. **`<skill>-figures <thread>`** — rendered deliverable (PDF, slides, drawings) using the shared figure-theming substrate (navy palette by default, override-able).
7. **State transitions to `READY` / `AUDITED` / `CUSTOMER-READY`** per skill state machine.

Every phase is idempotent and resumable; a crashed run picks up where it left off by re-reading `_progress.json` and inspecting the filesystem.

### Running under an external orchestrator

Anvil commands never touch git by default. If you run anvil under an external orchestrator that requires a clean working tree after every phase (e.g., a sync daemon that commits and pushes between agent turns), opt in to the per-phase git commit hook: commit a repo-level `.anvil/config.json` with `{"version": 1, "git": {"commit_per_phase": true, "push": true}}`. Each write-bearing phase then ends by staging only the dirs it wrote and committing as `anvil(<skill>/<phase>): <thread>.{N} [<state>]` (pushing when `git.push` is true); git failures warn and continue — the artifact on disk is always the source of truth. The full contract lives in `.anvil/anvil/lib/snippets/git_sync.md` after install (`anvil/lib/snippets/git_sync.md` in this repo). Default off: with no `.anvil/config.json`, behavior is unchanged. Note this is distinct from `.anvil/install-metadata.json`, which remains provenance-only. (The memo skill adopts the hook today; remaining skills follow in a tracked rollout.)

## Project status

Anvil is past the bootstrap phase. The eight v0 skills are merged and used in production by the [studio canary consumer](https://2amlogic.com). Active work is on follow-up polish surfaced by real authoring use — see [open issues](https://github.com/rjwalters/anvil/issues) for the live punch list. Issues labeled `tier:goal-supporting` are higher-value canary friction; `tier:maintenance` is technical debt and editorial cleanup.

## License

MIT
