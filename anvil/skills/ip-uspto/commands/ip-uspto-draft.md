---
name: ip-uspto-draft
description: Drafter command for the ip-uspto skill. Produces a new patent application version directory from the brief + inventorship matrix (and prior-art context if supplied), or revises from a prior version + critic siblings.
---

# ip-uspto-draft — Drafter

**Role**: drafter.
**Reads**:
- New thread: `<thread>/BRIEF.md`, `<thread>/inventorship.md`, `<thread>/refs/**`, `<thread>/prior-art/**` (for §102/§103 awareness during drafting).
- Revise-from-feedback path (rare; reviser is preferred): also the latest `<thread>.{N}/` and all `<thread>.{N}.*/` critic siblings.

**Writes**: `<thread>.{N+1}/` containing `spec.tex`, `claims.tex`, `abstract.txt`, `drawings/`, and `_progress.json`.

## Inputs

- **Thread slug** (positional argument).
- **`<thread>/BRIEF.md`** (required): structured brief produced by `ip-uspto-intake` or hand-authored to the same shape.
- **`<thread>/inventorship.md`** (recommended): the inventorship matrix. Drafter does not consume attribution per se but uses the named-inventor list for the spec front matter. Drafting can proceed without it (with a warning); `finalize` will refuse to proceed if the matrix is missing or stale.
- **`<thread>/prior-art/`** (optional): operator-supplied prior art. Drafter uses this for §102/§103 awareness — distinguishing language should be present in the spec from draft 1 so the `priorart` critic has something to evaluate.
- **`<thread>/refs/`** (optional): additional reference material.

## Outputs

A new version directory:

```
<thread>.{N+1}/
  spec.tex            Specification (LaTeX, \documentclass{anvil-uspto})
  claims.tex          Claims block (\begin{claim}...\end{claim} per claim)
  abstract.txt        Abstract (plain text, ≤150 words)
  drawings/
    drawing-descriptions.md  Stub descriptions for human illustrator (default v0 figures path)
    (or fig-1.tex, fig-1.svg, etc., when figures phase has been run)
  _progress.json      Phase state with draft: done after successful write
```

For a new thread, `N+1 == 1` so the output is `<thread>.1/`.

## Procedure

1. **Discover thread state**: enumerate existing `<thread>.{N}/` dirs. Compute the next `N`.
2. **Resume check**: if `<thread>.{N+1}/_progress.json` exists with `draft.state == in_progress`, treat as a crashed prior run. Delete any partial output and re-draft. If `draft.state == done`, the version is already drafted — exit early (idempotent).
3. **Read inputs**: load `BRIEF.md` (required — error if missing), `inventorship.md` (warn if missing), enumerate `refs/` and `prior-art/`. If revising from feedback, also load the prior version's full content and concatenate all critic siblings' `_summary.md` + `findings.md`.
4. **Initialize `_progress.json`**: `phases.draft.state = in_progress`, `phases.draft.started = <ISO>`, `metadata.iteration = N+1`, `metadata.max_iterations` (inherit from `<thread>/.anvil.json` if set, else 5).
5. **Draft the application** in this order:

   ### 5a. Spec skeleton from template
   Load `anvil/skills/ip-uspto/assets/template-spec.tex.j2`. Fill in:
   - `\documentclass{anvil-uspto}` preamble.
   - Title (from `BRIEF.md` frontmatter `title`).
   - Inventors (from `BRIEF.md` frontmatter `inventors`).
   - Field of use (from `BRIEF.md` frontmatter `field_of_use`).

   ### 5b. FIELD OF THE INVENTION (§ heading via `\fieldoftheinvention`)
   One paragraph naming the technical field, sized for a USPTO examiner classifier.

   ### 5c. BACKGROUND OF THE INVENTION (§ heading via `\background`)
   Two to four paragraphs. Describe the problem (from `BRIEF.md` §1) and the prior approaches (from `BRIEF.md` §2). **Do NOT admit any reference as prior art** — discuss approaches in terms of what was generally done in the field, citing only when the inventor has confirmed publication dates. Distinguishing language goes here (it will be refined by the `priorart` critic later).

   ### 5d. SUMMARY OF THE INVENTION (§ heading via `\summary`)
   One to two paragraphs per inventive feature (`BRIEF.md` §3). State each inventive feature plainly and the benefit it provides. The SUMMARY should mirror the independent claims at a higher level — a reader of the summary should be able to anticipate roughly what the independent claims will cover.

   ### 5e. BRIEF DESCRIPTION OF THE DRAWINGS (§ heading via `\briefdescriptionofdrawings`)
   One line per figure: `FIG. <N>. <one-line description>.` In v0, drawings are stubs (see `drawings/drawing-descriptions.md`); the brief description should still list every planned figure so the reviewer can check correspondence.

   ### 5f. DETAILED DESCRIPTION OF EMBODIMENTS (§ heading via `\detaileddescription`)
   The bulk of the spec. For each inventive feature in `BRIEF.md` §3:
   - Describe at least one embodiment from `BRIEF.md` §4 in concrete detail. Use reference numerals (`\refnum{<N>}` macro from the class) consistently — each component referenced in spec must appear in a drawing.
   - For each numeric parameter, state the working range from `BRIEF.md` §5 ("the operating frequency may range from 5 GHz to 80 GHz, preferably between 20 GHz and 60 GHz, most preferably about 40 GHz").
   - For each categorical parameter, list the alternatives from `BRIEF.md` §5 ("the substrate material may be silicon, germanium, or a III-V semiconductor including gallium arsenide and indium phosphide").
   - Acknowledge edge cases from `BRIEF.md` §6 without overstating the limitations.
   - **Use `\anvilpara{...}` for each numbered paragraph** so the class produces `[0001]`, `[0002]`, … numbering automatically.

   ### 5g. CLAIMS (separate `claims.tex` file, included from spec.tex)
   Produce `claims.tex` with:
   - **3 independent claims maximum** by default (USPTO charges fees beyond 3 independents). Layer them: a broad apparatus claim, a method claim, a system-level claim — chosen based on the inventive features.
   - **Dependent claim ladder**: for each independent claim, write 3–6 dependent claims that progressively narrow. Each dependent should add a specific limitation drawn from an embodiment or alternative in `BRIEF.md` §4 or §5.
   - **20 claims total maximum** by default (USPTO charges fees beyond 20). If the inventive material justifies more, raise it but flag the cost in the operator notes.
   - **No multiple-dependent-on-multiple-dependent** claims (37 CFR 1.75(c)). Multi-dependent ("any of claims 1 to 3") is permitted but its parents must themselves be single-dependent.
   - **Antecedent basis discipline**: every claim term introduced as `a widget` must be referenced subsequently as `the widget`, never as `said widget` (modern USPTO style preference).
   - Use `\begin{claim}...\end{claim}` for each claim; the class handles numbering.

   ### 5h. ABSTRACT (separate `abstract.txt`, plain text)
   ≤150 words, single paragraph. State what the invention is and the principal use. The abstract is for searchability; it does NOT limit claim scope and should not contain unnecessary detail.

   ### 5i. Drawings stubs (default v0 path)
   Write `drawings/drawing-descriptions.md`:

   ```markdown
   # Drawing descriptions — <thread>.<N>

   Each entry below is a stub for a human illustrator. Follow 37 CFR 1.84 (black ink, numbered FIG. N, lead lines, reference numerals shared with spec).

   ## FIG. 1 — <one-line caption>
   - **Type**: <block diagram | flowchart | cross-section | perspective | schematic>
   - **Components shown** (reference numerals): 10 (housing), 12 (input port), 14 (processor), 16 (output port).
   - **Spatial relationships**: <one paragraph describing relative position and connection>.
   - **Annotations/lead lines**: each numeric reference is connected to its component with a lead line.

   ## FIG. 2 — <one-line caption>
   ...
   ```

   The figurer phase (`ip-uspto-figures`) can later replace these stubs with TikZ or rendered images.

6. **Validate before declaring done**:
   - `spec.tex` exists and is non-empty.
   - `claims.tex` exists and contains at least one `\begin{claim}` block.
   - `abstract.txt` exists, is non-empty, and is ≤150 words.
   - `drawings/drawing-descriptions.md` exists with at least one figure entry.
7. **Update `_progress.json`**: `phases.draft.state = done`, `phases.draft.completed = <ISO>`.
8. **Report**: print the path to the new version dir and a one-line status (e.g., `Drafted acme-widget.1/ (spec: 4200 words / 45 paragraphs, 3 independent + 14 dependent claims, abstract 138 words, 4 drawing stubs)`).

## Voice and style overrides

If `.anvil/skills/ip-uspto/voice.md` exists in the consumer repo, load it and apply during drafting. This is how a firm customizes its house drafting style (e.g., preferred claim format conventions, sentence-length preferences) without forking the skill.

## Idempotence and resumability

- A completed draft (`_progress.json.draft.state == done` AND all four required artifacts exist) is never overwritten. Re-running is a no-op with a notice.
- A crashed draft is re-runnable after deleting partial output. Validation is by file existence + content non-emptiness, not solely by the progress flag.

## `_progress.json` snippet

Minimum schema this command writes (matches `SKILL.md`):

```json
{
  "version": 1,
  "thread": "<slug>",
  "phases": {
    "draft": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  },
  "metadata": {
    "iteration": <N>,
    "max_iterations": 5
  }
}
```

Merge rule: read existing `_progress.json` if present, update only `phases.draft` and `metadata`, preserve all other fields.

## Notes for the drafter agent

- **Antecedent basis is checked by the `s112` critic.** Do not be sloppy — every "the X" must have a prior "a X" or "an X" in the same claim chain.
- **Independent claims are the legal product.** A great spec with a bad independent claim is a worthless patent. Draft the independent claims with the most care.
- **Never copy claim language from cited prior art.** If `<thread>/prior-art/` contains a reference, distinguish from it — do not echo it. The `priorart` critic will catch this.
- **The class macros do work for you** (`\anvilpara`, `\refnum`, claim environment). Use them — manual paragraph numbering is error-prone and will fail pre-flight.
- **3 independents / 20 total claims is a soft cap.** Exceed it when the invention justifies, but note the additional USPTO fees in the operator's report.


**Snippet references**: See `anvil/lib/snippets/progress.md` for the `_progress.json` read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC timestamp convention. The merge is shallow: preserve fields and phases not touched by this command.
