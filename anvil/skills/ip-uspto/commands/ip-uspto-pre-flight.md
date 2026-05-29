---
name: ip-uspto-pre-flight
description: Mechanical USPTO formal-compliance scan. Runs after each revise, before the next review cycle. Deterministic-first (regex, counts, parser), LLM fallback only for ambiguous structural questions.
---

# ip-uspto-pre-flight — Pre-flight (mechanical compliance)

**Role**: pre-flight checker.
**Reads**: latest `<thread>.{N}/` (all of `spec.tex`, `claims.tex`, `abstract.txt`, `drawings/`).
**Writes**: `<thread>.{N}.preflight/` with `_summary.md`, `findings.md`, `_meta.json`.

This command catches mechanical formal-compliance issues (37 CFR 1.71–1.84 derived) that critics would otherwise spend their attention budget on. Deterministic checks run first; an LLM fallback handles only the genuinely ambiguous structural cases (e.g., "does this claim look like a multiple-dependent-on-multiple-dependent claim?").

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/spec.tex` AND `<thread>.{N}/claims.tex`.

## Outputs

```
<thread>.{N}.preflight/
  _summary.md        Pass/fail boolean + counts table + per-check status
  findings.md        Itemized findings for any failed check (severity, location, rationale, suggested fix)
  _meta.json         { critic: "preflight", role: "ip-uspto-pre-flight.md", started, finished, model, schema_version }
  _progress.json     Phase state for the pre-flight check
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/spec.tex` AND `<thread>.{N}/claims.tex`. If `<thread>.{N}.preflight/_progress.json.preflight.state == done` AND `_summary.md` exists, exit early (idempotent).
2. **Resume check**: if prior partial output exists from a crashed run, delete it.
3. **Initialize `_progress.json`** for the preflight dir.
4. **Run deterministic checks** (in order; collect findings, do not short-circuit):

   ### Check 1 — Paragraph numbering (`[0001]`, `[0002]`, …)
   - Scan `spec.tex` for `\anvilpara{...}` macro invocations (provided by `anvil-uspto.cls`).
   - Verify the resulting numbering is contiguous starting at `[0001]`. Gaps and duplicates are findings.
   - **Deterministic**: regex + counter.

   ### Check 2 — Abstract word count (≤150 words, 37 CFR 1.72(b))
   - Read `abstract.txt`. Count words (whitespace-separated tokens, exclude pure-punctuation tokens).
   - If count > 150 → finding with severity `blocker`.
   - If count < 50 → finding with severity `minor` (abstract is suspiciously short).
   - **Deterministic**: word count.

   ### Check 3 — Claim numbering (1..N contiguous, 37 CFR 1.126)
   - Parse `claims.tex` for `\begin{claim}...\end{claim}` blocks.
   - Verify each claim is numbered (via the class's auto-numbering, but the source must have one `\begin{claim}` per claim) starting at 1 and contiguous to N.
   - Find any duplicated numbers or gaps.
   - **Deterministic**: parser.

   ### Check 4 — Multiple-dependent claim rule (37 CFR 1.75(c))
   - For each dependent claim, extract its dependency list (e.g., `The widget of claim 1` or `The widget of any one of claims 1 to 3`).
   - **No multiple-dependent claim may depend on another multiple-dependent claim.**
   - **Deterministic** for the unambiguous cases (clear "any of" wording). **LLM fallback** when the dependency phrasing is unconventional (e.g., embedded in prose).
   - Findings: list each violating chain.

   ### Check 5 — Reference numeral coherence
   - Extract every numeric reference (`\refnum{42}` macro or bare `42` in figure captions) from `spec.tex` and `drawings/**`.
   - Verify each reference numeral that appears in `spec.tex` also appears in at least one drawing, and vice versa.
   - Findings: orphan numerals on either side.
   - **Deterministic**: set difference. (Owns Dimension 7 partially; full responsibility is the `review` critic.)

   ### Check 6 — Section heading presence (37 CFR 1.77(b))
   - Verify `spec.tex` contains, in order, the required heading commands provided by `anvil-uspto.cls`:
     - `\fieldoftheinvention`
     - `\background`
     - `\summary`
     - `\briefdescriptionofdrawings`
     - `\detaileddescription`
     - `\claims`
     - `\abstract`
   - Missing or out-of-order headings are findings with severity `blocker`.
   - **Deterministic**: regex.

   ### Check 7 — Page geometry sanity
   - Verify `spec.tex` uses `\documentclass{anvil-uspto}` (or a clearly identified consumer override).
   - The class enforces 1-inch margins, US Letter, 12pt, 1.5 spacing. If the class is not in use, raise a finding with severity `blocker`.
   - **Deterministic**: regex on documentclass line.

   ### Check 8 — Claim count thresholds
   - Count total claims and independent claims.
   - USPTO charges fees beyond 20 total claims and 3 independent claims (37 CFR 1.16(h)–(j)). NOT a compliance failure but a cost-budget signal.
   - Findings: severity `minor` if total > 20 or independents > 3 (informational).

5. **LLM fallback (only when triggered by Check 4)**: if any dependency phrasing was unparseable by the deterministic check, hand the dependent claim text to an LLM with the question: "Does this claim depend on a single antecedent claim, multiple antecedent claims (multiple-dependent), or is it ambiguous?" Use the answer to complete Check 4.
6. **Determine pass/fail**: pass iff no finding has severity `blocker`.
7. **Write `_summary.md`**:

   ```markdown
   ---
   critic: preflight
   for_version: <N>
   passed: <true|false>
   ---

   # Pre-flight summary — <thread>.<N>

   | Check | Result | Findings |
   |---|---|---|
   | 1. Paragraph numbering | pass | - |
   | 2. Abstract word count (≤150) | fail | 1 (count: 168) |
   | 3. Claim numbering contiguous | pass | - |
   | 4. Multiple-dependent claim rule | pass | - |
   | 5. Reference numeral coherence | pass (0 orphans) | - |
   | 6. Section headings | pass | - |
   | 7. Page geometry (anvil-uspto class) | pass | - |
   | 8. Claim count thresholds | informational | 22 total / 4 independent (fee impact) |

   **Overall**: <FAIL — 1 blocker | PASS — informational findings only>

   See `findings.md` for details.
   ```

8. **Write `findings.md`** in the same format as critic findings (severity, location, rationale, suggested fix).
9. **Write `_meta.json`** and finalize `_progress.json` to `done`.
10. **Report**: print the path and a one-line summary (e.g., `Pre-flight: acme-widget.2.preflight/ → FAIL (1 blocker: abstract 168 words)`).

## Gating behavior

The pre-flight result gates the loop edge `REVISED → REVIEWED`:
- If `passed: true`, the orchestrator may advance to running critics on this version.
- If `passed: false`, the operator (or orchestrating agent) must run `ip-uspto-revise` again (with the pre-flight findings included as input) before re-running critics. The orchestrator reports `PRE_FLIGHT_FAILED — revise required`.

## Idempotence

- A completed pre-flight (`_progress.json.preflight.state == done` AND `_summary.md` exists) is never re-run.
- A crashed run is re-runnable after deleting partial output.
- A pre-flight on version `N` is **never re-run** if `<thread>.{N+1}/` already exists — the result was already consumed by a subsequent revision.

## Notes for the pre-flight agent

- **Deterministic first.** Do not invoke the LLM for checks that have unambiguous deterministic implementations. Save the LLM budget for the genuinely ambiguous case (Check 4 fallback).
- **Reference numeral check is partial.** Full reference-numeral correspondence (e.g., "is reference 42 actually depicting the same component everywhere it appears?") is the `review` critic's job. Pre-flight only checks existence/presence.
- **The class file is the enforcement mechanism for geometry.** Pre-flight verifies the class is in use, not the geometry directly — if the class is loaded, geometry is correct by construction.
