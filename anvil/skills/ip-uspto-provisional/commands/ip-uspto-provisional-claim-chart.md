---
name: ip-uspto-provisional-claim-chart
description: Advisory claim-chart critic for the ip-uspto-provisional skill. Charts each independent claim seed against every arrangement the description itself calls built, measured, simulated, computed or preferred, in met / not met / not stated cells with quoted evidence, derives gap lists, and recomputes printed figures by script with per-miss source classification. ADVISORY ONLY — owns NO rubric dimension, sets NO critical flag, is never in the configured critic set, never edits the draft, never proposes claim language, never adds claim seeds, and never advances the state machine.
---

# ip-uspto-provisional-claim-chart — Advisory claim-chart critic

**Role**: advisory claim-chart critic (counsel aid — reads independent claim seeds against the described arrangements; a gap-finder, not a scorer).
**Reads**: latest `<thread>.{N}/spec.tex` (+ embedded claim-seed subsection, if any) + optional `<thread>.{N}/claims.tex` + `drawings/drawing-descriptions.md`; the figure-recompute step also reads whatever tables/values the spec prints. **Deliberately does NOT read `claims.tex` or the claim-seed subsection until step 3** (the arrangement list must be built claims-blind).
**Writes**: `<thread>.{N}.claimchart/` with `cover-note.md`, `counsel-note.md`, `chart.md`, `_meta.json`, `_progress.json` — and nothing else. The sibling is **read-only once written**.

## Advisory posture (load-bearing)

This command is **not a scoring critic**. It owns **no rubric dimension**, sets **no critical flag**, is **never in the configured critic set** (default or `.anvil.json` override — adding `claimchart` to a `critics` list is a configuration error this command does not honor), never gates revise / audit / finalize, and never advances the state machine. Its findings are for **counsel**, not for the convergence loop.

**Invisible to aggregation by construction.** The reviser and `anvil/lib/critics.py::discover_critics` discover a critic sibling by payload shape: a canonical `_review.json`, or the ip-uspto legacy triple (`_summary.md` + `findings.md` + `_meta.json`). This sibling deliberately writes **none of those filenames** — no `_review.json`, no `_summary.md`, no `findings.md` — so discovery skips it and the reviser never aggregates, sanity-checks, or waits on it. Do not rename this sibling's outputs to the critic shapes; the names `chart.md` / `counsel-note.md` / `cover-note.md` ARE the structural guarantee. `_meta.json` here carries `scorecard_kind: "advisory-note"` (deliberately outside the two scoring kinds — `human-verdict` / `machine-summary` — because this is not a scorecard) and **no** `rubric_id` / `rubric_total` / `advance_threshold` stamps: it owns no dimension to stamp.

## Why this chart (the trial)

The three configured critics (`review`, `s112`, `priorart`) never ask whether each independent claim seed reads on an arrangement the specification **itself** calls built, measured, simulated or preferred. In a consumer trial across several provisionals, a one-pass chart of claim limitations against described arrangements found such a gap **every time**, and in most cases no earlier critic or audit had stated it. A formal-proof encoding of the same question added nothing — the finding came from answering **yes or no for each limitation on each arrangement**.

Two trial failure modes shape this procedure:

- **An arrangement left off the list is never charted.** One run missed the single point every earlier critic had found, because that embodiment was not on its hand-built list. Hence the exhaustive claims-blind sweep in step 2.
- **Counting silence as "not met" overstates the result.** Where the text simply does not say which variant a simulation used, the right cell value is **`not stated`**. Hence the three-valued cells and the rule that `not stated` is never counted as `not met` anywhere.

A second, smaller trial piece ships here: recomputing every printed figure from its printed inputs. Nearly every figure that failed to reproduce was the source's own figure with a **rounded input** or an **unstated condition**, so the recompute is only useful with a source-check step attached (step 6 classifies every miss against its source before anything is reported).

## Outputs

```
<thread>.{N}.claimchart/
  cover-note.md     ≤10-line paste-ready cover block for the counsel package: what was charted,
                     freeze stamp, headline derived-list results. The ONLY excerpt a human
                     needs to copy elsewhere; this command never writes into <thread>.counsel/.
  counsel-note.md   The ONE-PAGE counsel note (hard page budget): chart verdict summary, the
                     five derived lists, figure-recompute misses with their classes, limits.
  chart.md          The full backing chart: arrangement list (tagged, anchored), the
                     limitation × arrangement matrix with per-cell quoted evidence, arguable
                     readings reported both ways, and the figure-recompute table.
  _meta.json        { critic: "claimchart", role, started, finished, model, schema_version,
                      scorecard_kind: "advisory-note", findings_sha256, findings_frozen_at }
                    — NO rubric_id / rubric_total / advance_threshold (owns no dimension).
  _progress.json    Phase state for the claimchart sibling.
```

**Atomicity** (issues #350, #376): the sibling dir is written atomically via `anvil/lib/sidecar.py` — staged under `.<thread>.{N}.claimchart.tmp/`, atomic rename on completion; entry sweep via `cleanup_one_staging(<thread>.{N}.claimchart)`; sibling staging dirs untouched.

## Procedure

1. **Discover state, sweep, open sidecar**: highest `N` with `<thread>.{N}/spec.tex`; `cleanup_one_staging(<thread>.{N}.claimchart)`; if `<thread>.{N}.claimchart/` exists, exit early (idempotent — the atomic-rename contract guarantees completeness). Otherwise open `staged_sidecar(final_dir=<thread>.{N}.claimchart, required_files=["cover-note.md", "counsel-note.md", "chart.md", "_meta.json", "_progress.json"])`. **Non-Python-driver ordering** (issue #645): a session with no orchestrating Python driver uses the `python -m anvil.lib.sidecar` CLI shim (`uv run --project .anvil` prefix in a consumer install) — `stage` → write all five required files into the printed staging path → `commit … --required cover-note.md,counsel-note.md,chart.md,_meta.json,_progress.json`; the manual-`mv` tier-2 fallback stamps `_meta.json` with `"atomicity_fallback": "manual-mv"`, exactly as the sibling critics document. Do NOT create the final-named dir before the manifest is complete.

2. **Pass 1 — build the arrangement list (claims-blind).** Read the description sections of `spec.tex` (Detailed Description and every embodiment / example / variant paragraph, the Brief Description of Drawings, and `drawings/drawing-descriptions.md`) — and **do not open `claims.tex` or the spec's claim-seed subsection yet**. Enumerate **every distinct arrangement** the text describes: each entry carries (a) a name, (b) a **tag taken from the text's own words** — one of `built`, `measured`, `simulated`, `computed`, `proposed` (quote the sentence that earns the tag), (c) a **preferred marker** when the text calls it preferred/preferred-embodiment (again verbatim), and (d) the paragraph anchors. Completeness discipline: sweep the whole description — past the headline embodiment, into every "in another embodiment / alternatively / in a variant" paragraph. An arrangement left off this list is never charted (trial failure mode 1); when unsure whether a paragraph describes a distinct arrangement or restates one, list it separately and say so.

3. **Nothing-to-chart check (claims-optional, graceful).** Only now open the claim source: `<thread>.{N}/claims.tex` if present, else the claim-seed subsection inside `spec.tex`. If neither exists: write `cover-note.md` + `counsel-note.md` + `chart.md` recording `no claim seeds — nothing to chart (claims-optional: absence is never a finding)` plus the arrangement list (it is still useful to counsel), finalize `_meta.json` + `_progress.json`, commit, exit `done` — a legitimate state, not an error. Likewise, a spec whose description yields **no arrangements** charts nothing: record the empty list and say plainly that every independent reads on no described arrangement — still advisory, never a critical flag.

4. **Pass 2 — chart each limitation (re-read before refuting).** For each **independent** seed claim first, then each **dependent**: split it into limitations. For every limitation × arrangement, record exactly one cell:

   - **`met`** — the arrangement describes the limitation. Quote the decisive words verbatim and give the paragraph anchor.
   - **`not met`** — after **re-reading the arrangement's paragraphs in this pass**. Never record `not met` from memory: re-open the spec section and quote the words that ground the refusal (the absence must itself be evidenced by what the re-read does and does not contain).
   - **`not stated`** — the text is silent or ambiguous in a way that is not a refusal (e.g., it never says which variant a simulation used). Silence is never `not met` (trial failure mode 2).
   - **Arguable readings are named and reported both ways**: a cell whose verdict turns on a claim-term interpretation shows BOTH readings — `met (reading A: "…" — ¶[0041]) / not met (reading B: "…" — ¶[0041])` — and for every derived list below, an arguable cell counts the **conservative** way (as NOT reading on), so the derived lists err toward surfacing a question for counsel rather than hiding it.

5. **`not stated` is tracked separately everywhere.** In the matrix, in the derived lists, and in the counsel note, `not stated` cells are counted and reported as their own category — never folded into `not met`, never summed with it, never described as "limitations not met".

6. **Recompute printed figures by script.** Extract a figure ledger from the spec: every printed numeric figure that presents as a computed or sourced result (table rows, inline performance numbers), each with its printed value, its printed inputs, the derivation the text states (as an arithmetic expression), any condition the derivation needs that the text does not state, and its citable source when one exists. Then run the deterministic checker (skill-local lib; the source-check step the trial says makes the recompute useful):

   ```python
   from pathlib import Path
   from anvil.lib.skill_lib_loader import import_skill_lib_module

   figure_recompute = import_skill_lib_module(
       "ip-uspto-provisional",
       Path("anvil/skills/ip-uspto-provisional/lib"),  # .anvil/skills/ip-uspto-provisional/lib in a consumer install
       "figure_recompute",
   )
   report = figure_recompute.recompute_ledger(ledger)
   ```

   (CLI form for a Python-less session: `python anvil/skills/ip-uspto-provisional/lib/figure_recompute.py <ledger.json> [--json]` from the anvil source root — the module is stdlib-only and runs bare; in a consumer install the loader form above via `uv run --project .anvil` is the path.) **Every miss is classified by the script before anything is reported** — `text-omits-condition` (the text omits a condition or the input precision the derivation needs; includes the benign rounded-input case where the figure is faithful to its source), `figure-differs-from-source` (the printed figure disagrees with its stated derivation or its cited source), `no-source` (no derivation and no citable source — provenance not checkable). Fold the classified table into `chart.md` and the misses into the counsel note. Do not hand-override a script classification; if the ledger entry was extracted wrong, fix the ledger and re-run.

7. **Derive the five lists** (the counsel note's core; conservative counting per step 4):

   1. **Independents reading on no arrangement** — an independent reads on an arrangement iff every limitation is `met` (arguable cells and `not met` cells both count against; `not stated` cells are listed alongside as their own line, never merged).
   2. **Built / simulated / preferred arrangements read by no independent** — each arrangement with a `built`, `measured`, `simulated`, or `computed` tag, or a preferred marker, that no independent fully reads on.
   3. **Dependents without support along their parent chain** — a dependent whose parent independent reads on no arrangement, or whose own added limitations find no `met` cell on any arrangement the parent reads on.
   4. **Claim terms absent from the description** — a term used in a seed claim that appears nowhere in the description (the conversion will have no support for it).
   5. **Bounds that can exclude every described case** — a claim range or bound (e.g., "10–12 wt%") whose endpoints exclude all described values (e.g., every example sits at 8 or 15) — the bound carves away the described support.

8. **Write and freeze.** Write `chart.md`, `counsel-note.md` (respect the one-page budget — the chart backs it, the note does not reproduce it), and `cover-note.md` into the staging dir. Compute the freeze hash over the three frozen files in alphabetical order — `cat chart.md counsel-note.md cover-note.md | sha256sum` — and write `_meta.json` with `critic: "claimchart"`, `role: "ip-uspto-provisional-claim-chart.md"`, `started`, `finished`, `model`, `schema_version: 1`, `scorecard_kind: "advisory-note"`, **`findings_sha256`** (the hex digest) and **`findings_frozen_at`** (ISO-8601 UTC, per `anvil/lib/snippets/timestamp.md`). Finalize `_progress.json` LAST, then exit the sidecar context (manifest verified, atomic rename).

9. **Compare against other critics — only AFTER the freeze lands.** With the sibling committed, open the other critics' outputs at the same `N` (`.review/`, `.s112/`, `.priorart/`, and `.audit/` when present) and mark which chart findings are novel versus already stated. **The frozen files are never edited** — the comparison goes in the terminal report only: e.g., `claimchart: acme-widget-prov.3 → 2/4 independents read on no arrangement; 3 novel findings, 2 already stated by s112 (frozen sha256 abc… at 2026-11-17T19:34:02Z)`.

## Output surface — one page, two notes, nothing else

The command's entire durable output is the `cover-note.md` (≤10 lines) and the one-page `counsel-note.md` (plus the backing `chart.md` and bookkeeping `_meta.json` / `_progress.json`) inside its own sibling. It **never edits the draft**, **never proposes claim language**, **never adds claim seeds**, never writes into other critic siblings, and never writes into `<thread>.counsel/` (that package is finalize's and immutable once written — a human copying the cover note into the counsel package is the intended handoff). Findings do NOT flow to the reviser: there is no `findings.md`, and the reviser's discovery never sees this sibling.

## Limits (stated in every counsel note)

- **Completeness of the arrangement list is the chart's ceiling.** An arrangement the pass-1 sweep missed is never charted, and nothing downstream can notice (trial failure mode 1). The chart certifies only what the listed arrangements show.
- **This command cannot see operability defects** (whether a described arrangement would actually work), **physical-model defects** (whether the numbers are physically plausible), or **prior-art defects** (whether the read-on arrangement is novel). Those belong to `s112`, the audit, and `priorart` respectively; a clean chart is not any of those.
- It charts **seeds, not filed claims** (a provisional's claims are optional and unexamined); the chart is a conversion-readiness aid, never a §102/§103 adjudication.

## Idempotence and resumability

Standard. The sibling at `N` is immutable once written; a re-run on the same version exits early at step 1. New disclosure lands on the next version, and the chart is re-run there (the freeze hash of the old sibling makes stale-versus-current comparison mechanical).

## Notes for the claim-chart agent

- **Chart, don't argue.** The value is the yes/no/not-stated per cell with quoted evidence — not prose advocacy for either side of a reading.
- **Silence is `not stated`, not `not met`.** Overstating a `not met` from silence is the trial's second failure mode and the fastest way to make counsel discard the whole chart.
- **You are blind on purpose in pass 1.** The arrangement list is built before the claims are read so the claims cannot shape which arrangements get listed.
- **Never fix what you find.** A gap is surfaced for counsel and the inventors; proposing claim language or editing the draft is out of scope by contract.

## `_progress.json` snippet

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": { "claimchart": { "state": "done", "started": "<ISO>", "completed": "<ISO>" } }
}
```

## Git sync (opt-in, off by default)

Per `anvil/lib/snippets/git_sync.md`: if `.anvil/config.json` exists and `git.commit_per_phase` is `true`, end this phase: stage only the dirs this phase wrote, commit as `anvil(<skill>/<phase>): <thread>.{N} [<state>]`, push if `git.push` is `true`. Git failures warn and continue — never fail the phase. When the config or knob is absent, skip this step entirely (default off).

This phase's specifics:

- **Ordering**: after the staged-sidecar atomic rename (issue #350) lands the final-named `<thread>.{N}.claimchart/` — so only complete sidecars are ever committed.
- **Staging target**: ONLY this command's own `<thread>.{N}.claimchart/` sidecar (never sibling critics' dirs).
- **Commit**: `anvil(ip-uspto-provisional/claim-chart): <thread>.{N} [advisory]` — an advisory sibling that does not advance the state machine, so the bracket carries the advisory marker.
