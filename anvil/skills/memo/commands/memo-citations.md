---
name: memo-citations
description: Deterministic citation-coverage critic for the memo skill. Scans the body markdown of the latest <thread>.{N}/ version dir for unhooked load-bearing claims (numeric, named-author, quantitative summary, date-pinned events) and broken \cite{} / [@] keys; writes a typed _review.json to the <thread>.{N}.citations/ sibling for the critics aggregator. Optional, non-blocking, idempotent.
---

# memo-citations — Citation-coverage critic

**Role**: Deterministic tool-evidence critic (pre-flight detector, optional, non-blocking).
**Reads**: latest `<thread>.{N}/<thread>.md` + refs sources resolved by `anvil/skills/memo/lib/refs_resolver.py`.
**Writes**: `<thread>.{N}.citations/_review.json` (always), `<thread>.{N}.citations/_findings.json` (companion JSON).

This command is the memo-skill analog of `memo-render` for the citation-coverage Track B detector shipped under Epic #328 Phase 3 (issue #336). It runs a deterministic pass over the body markdown and emits a typed `Review` (`kind=tool_evidence`) that the standard `critics.aggregate` pipeline merges into the verdict alongside the standard `memo-review` judgment critic.

**Phase 3 of Epic #328 (reframed 2026-06-05)**. Track B mechanical detector — informed by but not blocking on Phase 1 (#333, judgment-side enrichment guidance) and runs in parallel with Phase 2 (#335, `hyperlink-resolver`). The two Track B critics share the same general shape (deterministic detector → `tool_evidence`-kind `_review.json` → sibling critic dir); convention coordination on the CLI entry-point shape and sibling-dir naming is documented inline below.

**State-machine status**: `memo-citations` is an **optional pre-review pass**, NOT a new state. It runs after `memo-draft` and before the LLM-side `memo-review`; the standard review aggregator picks up the `.citations/` sibling automatically via `anvil/lib/critics.py::discover_critics`. See SKILL.md §"Critic auto-discovery" for the surrounding contract.

**Composability**: independently re-runnable. The consumer can edit `refs.bib`, add a new refs/ file, fix a broken `\cite{}` key in the body markdown, and re-invoke `memo-citations <thread>` to re-emit the findings without going through draft / revise. Each invocation regenerates `_review.json` from the current body + current refs sources; `<thread>.{N}.citations/_review.json` is a **derived artifact** and MUST NEVER be hand-edited.

## Inputs

- **Thread slug** (positional argument): identifies the thread within the cwd portfolio.
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/<thread>.md` existing. If no such version exists, exit with a notice (no work to do).
- **Body markdown**: `<thread>.{N}/<thread>.md` per the post-#295 contract (body filename echoes the thread slug).
- **Refs keys**: collected via `anvil/skills/memo/lib/citation_coverage.py::collect_refs_keys`. The collector walks the per-thread `<thread>/refs/` plus the portfolio-level `<portfolio>/research/` (per `refs_resolver.resolve_refs_dirs`) and harvests bibtex entry keys from every `*.bib` file. Also picks up the version dir's own `refs.bib` (the working bibliography written by `anvil/lib/cite.py::cite`).

## Outputs

```
<thread>.{N}.citations/
  _review.json    Typed Review (kind=tool_evidence) per anvil/lib/review_schema.py.
  _findings.json  Structured payload from CoverageResult.to_json() (informational companion).
```

The `_review.json` carries:

- One null-scored row on dimension `citation_coverage` so the schema validates while the aggregator treats this critic as null-everywhere (same pattern as `render_gate`'s null-scored row on dimension `render_gate`).
- One `Finding` per unhooked load-bearing claim (severity per the §"Severity ladder" below).
- One `Finding` per broken `\cite{}` / `[@]` key (severity `blocker`), with a closest-match suggestion in `Finding.suggested_fix` via `difflib.get_close_matches` when a near-key exists in the discovered refs source.
- One `CriticalFlag` of type `critical_unsourced_load_bearing_claim` when the threshold heuristic fires (see §"Critical-flag heuristic" below).

## Procedure

1. **Discover state**: enumerate `<thread>.{N}/` dirs; pick the highest `N` with `<thread>.md` present. If no such version exists, exit with a notice (`No memo version found; nothing to scan.`).
2. **Invoke the citation-coverage scan**: call

   ```python
   from anvil.skills.memo.lib.citation_coverage import scan_version_dir

   result = scan_version_dir(version_dir=<thread>.{N}/)
   ```

   The scanner owns the full pipeline: refs-key collection (per `collect_refs_keys`), the four claim-detector classes (numeric / named-author / quantitative summary / date-pinned events), the four false-positive disciplines (version-context, self-reference, hedge, quoted), and the broken-citation closest-match suggestion. See `anvil/skills/memo/lib/citation_coverage.py` module docstring for the detection contract.

3. **Emit `_review.json`**: write

   ```python
   review = result.to_review(version_dir=<version_dir>.name)
   (<version_dir>.citations / "_review.json").write_text(review.model_dump_json(indent=2))
   ```

   The review's `kind=tool_evidence` shape is what the aggregator routes on; `tool_calls=[]` is set on every finding to satisfy the schema requirement (the detector greps the body — no per-finding tool invocations to record).

4. **Emit `_findings.json` companion**: write the structured payload from `result.to_json()` alongside the typed review. The companion carries `refs_keys_scanned`, per-finding source spans, the `total_findings` count, and the `critical_flag_emitted` boolean — informational only; the load-bearing contract remains `_review.json`.

5. **Report**: print a one-line status reflecting the scan outcome:
   - Clean: `Scanned acme-seed.2/acme-seed.md (0 unhooked claims, 0 broken citations).`
   - Findings, no critical flag: `Scanned acme-seed.2/acme-seed.md (3 unhooked, 1 broken — see _review.json).`
   - Critical flag fired: `Scanned acme-seed.2/acme-seed.md (7 unhooked claims, 2 broken — CRITICAL: unsourced load-bearing claim threshold exceeded).`

## Detection classes

The detector recognizes four canonical load-bearing claim shapes:

| Class | Examples | Default severity | Notes |
|---|---|---|---|
| **Numeric** | `$2.3B`, `42 %`, `12 ms`, `Q3 2024` | `major` | Money, percent, unit-qualified, quarter-year. |
| **Named-author** | `Smith (2023) showed`, `Karpathy's 2024 talk` | `major` | Highest-confidence positive class. Treated as intrinsically load-bearing — any unhooked instance triggers the critical-flag heuristic. |
| **Quantitative summary** | `we found that…`, `the median was…`, `in the last 12 months` | `minor` | Lower confidence than the first two; fires only on the canonical summary frames. |
| **Date-pinned event** | `On March 5, 2025,` | `major` | High-confidence date anchor; the "On <Month> <Day>, <Year>," shape is the only one that fires (a bare year like "2024" does NOT fire). |

## False-positive discipline

Per the issue body §"False-positive discipline" the detector is **deliberately conservative**. Borderline cases default to NOT-emit so dim 3 reviewer headroom is preserved:

- **Version numbers in technical context** never fire: `version 3 of the API`, `Python 3.12 deprecated…`, `Node.js 22.0.0`. Detection runs at line level — any line that matches the `_VERSION_CONTEXT_RE` token list suppresses numeric claims on that line. Named-author and date-pinned claims still fire (hedges modify quantities, not authorship).
- **Self-referencing numbers** never fire: `see Figure 3`, `Section 4 reports`, `page 12`, `Table 2 shows`. Detection runs per-match — a numeric match that lies inside a structural-reference span (e.g. the `3` in `Figure 3`) is dropped.
- **Hedged claims** default to NOT-emit: `roughly 30 customers`, `around half of`, `an estimated $1B market`. Hedge markers (`roughly`, `approximately`, `around`, `about`, `estimated`, `close to`, …) suppress numeric and summary claims on the line. Named-author and date-pinned still fire because hedges modify quantities, not authorship/dates.
- **Quoted material** never fires: blockquote lines (`>` prefix), lines inside fenced code blocks (` ``` ` or `~~~`), and inline-backtick spans (`` `like this` ``) — the inner content is stripped before claim detection.

## Severity ladder

| Class | Severity | Critical-flag candidate? |
|---|---|---|
| Broken `\cite{key}` / `[@key]` | `blocker` | No (per-key blocker; the reviser MUST fix each occurrence) |
| Unhooked named-author claim | `major` | **Yes** — any unhooked named-author claim fires the critical flag |
| Unhooked numeric claim | `major` | Only via the >5-total threshold |
| Unhooked date-pinned event | `major` | Only via the >5-total threshold |
| Unhooked quantitative summary | `minor` | Only via the >5-total threshold |

## Critical-flag heuristic

The critic emits a top-level `critical_unsourced_load_bearing_claim` `CriticalFlag` when EITHER:

- More than `CRITICAL_UNHOOKED_THRESHOLD` (= **5**) total unhooked claims surface across the body, OR
- Any single **named-author** claim is unhooked.

The threshold (`>5`) is chosen so the rubric's dim 3 reviewer keeps its headroom for the borderline (1–5 unhooked) case while a citation-light memo (>5) trips the critical pathway. The named-author short-circuit reflects that named-author claims are the highest-confidence positive class — an unhooked one is a fabrication risk.

When the critical flag fires, the standard `critics.aggregate` pipeline forces `Verdict.BLOCK` regardless of total score. The reviser at the next pass MUST address every named-author finding plus enough numeric / summary findings to drop the count to ≤5 (or, equivalently, hook the claims via refs entries + `\cite{}` / `[@]` markers).

## Auto-discovery contract

`<thread>.{N}.citations/` follows the standard sibling-critic naming convention recognized by `anvil/lib/critics.py::discover_critics`. The `_review.json` file in the sibling is the load-bearing contract; `_findings.json` is informational and not parsed by the aggregator.

No aggregator change is required to wire this critic in. The first invocation of the standard `memo-review` post `memo-citations` automatically picks up the `.citations/` sibling and merges its findings + critical flag into the verdict. The aggregator already treats null-scored dimensions as "this critic does not own this dim" — the `citation_coverage` row contributes 0 to the total score; the load-bearing artifacts are the findings and the critical flag.

## CLI entry point

```bash
python -m anvil.skills.memo.lib.citation_coverage <version_dir> [--body-filename <name>]
```

The `<version_dir>` is the memo version directory (e.g. `acme-seed/acme-seed.2/`). The runner writes `<version_dir>.citations/_review.json` and `<version_dir>.citations/_findings.json`.

**Coordination with Phase 2 (`hyperlink_resolver`, #335)**: until Phase 2 lands and a sibling convention is documented, the `python -m anvil.skills.memo.lib.<module> <version_dir>` shape is the default. If Phase 2 lands first with a different runner shape (e.g. an `argparse` subcommand or a different output layout), the `_cli_main` function in `citation_coverage.py` is the one place to mirror it.

## Failure modes

All failure modes are **non-blocking** by design. Each is enumerated here so the operator can route on the specific failure:

| Failure | Symptom | Operator action |
|---|---|---|
| **Missing version dir** | `version_dir does not exist` | Run `memo-draft` first to create the latest version. |
| **Missing body markdown** | `<version_dir>/<thread>.md` not found | The scan returns an empty `CoverageResult` (no findings, no critical flag). The reviewer's standard back-checks will catch the missing body separately. |
| **Empty refs source** | No `refs.bib` anywhere reachable | The scan still runs; every `\cite{}` / `[@]` marker fires as broken. This is intentional — a memo with citation markers but no refs source is a content-integrity failure. |
| **Malformed `refs.bib`** | Entry keys cannot be parsed | The collector silently skips the unparseable lines and continues. The unparsed entries' keys are absent from the refs-keys set, so any `\cite{}` referencing them surfaces as broken. The fix is to repair the `.bib` file. |

## Re-run pattern

`memo-citations` is **idempotent + cheaply re-runnable**. The intended re-run scenarios are:

- **Operator added a refs entry**: a prior scan flagged `\cite{ghost-key}` as broken. The operator runs `cite ghost-doi <version_dir>` (per `anvil/lib/cite.py::cite`) to append the entry to `refs.bib`. They re-invoke `memo-citations <thread>` and the broken-citation finding clears. The `_review.json` is regenerated.
- **Operator hooked a numeric claim**: a prior scan flagged `$2.3B` as unhooked. The operator edits the body markdown to add `\cite{some-source}` on the same line. Re-invoke `memo-citations <thread>` and the unhooked-claim finding clears.
- **Operator hedged a claim**: a prior scan flagged `42% of customers` as unhooked. The operator decides the precise figure is not load-bearing and softens it to `roughly 42% of customers`. Re-invoke and the finding clears (hedges suppress numeric claims).

What `memo-citations` does NOT do:

- **Never edit `<thread>.md`.** The body is the source-of-truth; the critic only reads.
- **Never edit `refs.bib`.** Refs management is owned by `anvil/lib/cite.py::cite` and the operator.
- **Never produce a new version directory.** The critic operates on the existing `<thread>.{N}/`; version advancement is owned by `memo-draft` / `memo-revise`.

## Composability with the standard memo lifecycle

The lifecycle wiring (per Epic #328 Phase 3):

- **`memo-citations`** can run any time after `memo-draft` writes `<thread>.md`. It is independent of `memo-render` and `memo-review` — operators may run all three in any order.
- **`memo-review`** picks up the `.citations/` sibling automatically via `critics.discover_critics`. The aggregator merges the `tool_evidence`-kind review into the verdict alongside the standard judgment-kind review.
- **`memo-revise`** consumes findings from the aggregated review (which includes the `.citations/` findings) and rewrites the body markdown to address them.

There is no required order between `memo-citations` and the LLM-side `memo-review`. The standard pattern is: `memo-draft` → `memo-citations` → `memo-review` → `memo-revise`, but operators may invoke the critic on demand to validate a refs-management edit without re-running the full review.
