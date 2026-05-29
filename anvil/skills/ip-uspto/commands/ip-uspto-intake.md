---
name: ip-uspto-intake
description: Intake command for the ip-uspto skill. Converts a raw inventor disclosure (transcript, brain dump, sketch annotations) into a structured BRIEF.md the drafter can consume reliably.
---

# ip-uspto-intake — Intake

**Role**: intake interviewer.
**Reads**: `<thread>/refs/**` (raw disclosure materials: transcripts, notes, sketches, prior emails).
**Writes**: `<thread>/BRIEF.md` (structured brief with frontmatter + prose sections).

Without a structured brief, the drafter hallucinates. This command is a one-shot per thread that converts whatever the inventor handed over into a clean brief that names the inventive features, embodiments, edge cases, and out-of-scope adjacents explicitly.

## Inputs

- **Thread slug** (positional argument): identifies the thread within the cwd portfolio.
- **`<thread>/refs/`**: any combination of:
  - Inventor interview transcripts (markdown, text).
  - Brain-dump notes (markdown, text).
  - Sketch annotations (text descriptions of figures the inventor drew).
  - Prior internal emails or design docs.
  - Reference papers or existing internal IP the inventor cited.
- **`<thread>/prior-art/`** (optional, separate): operator-supplied prior art for the `priorart` critic; NOT consumed by intake.

## Outputs

```
<thread>/
  BRIEF.md            Structured brief: frontmatter + 8 named sections
```

The brief has the following structure (see `assets/BRIEF.md.example` for a reference):

```markdown
---
thread: <slug>
title: <one-line title of the invention>
inventors:
  - name: <Full Name>
    affiliation: <Org>
  - name: <Full Name>
    affiliation: <Org>
priority_date_target: <YYYY-MM-DD or "asap">
field_of_use: <one-line technical field>
intake_date: <ISO date>
---

## 1. Problem statement
One-paragraph framing of the problem the invention solves. Concrete enough that a patent attorney can identify the field and roughly the prior approaches.

## 2. Prior approaches
What people did before this invention. Identified by name (commercial products, academic methods) where possible. This is NOT prior-art search; it is the inventor's understanding of the prior state of the art.

## 3. Key inventive features
Bullet list of the 3–7 features the inventor claims are inventive. Each bullet is one sentence + a one-sentence "why it matters". These become the seeds for independent claims.

## 4. Embodiments
For each inventive feature, list at least one embodiment (specific implementation) the inventor has built, simulated, or fully designed. Embodiments are the lifeblood of the spec.

## 5. Ranges and alternatives
For numeric parameters: ranges the invention is known to work over (e.g., "operates between 5 GHz and 80 GHz"). For categorical parameters: alternatives the inventor would accept (e.g., "X may be silicon, germanium, or III-V"). This material directly populates §112(a) written description.

## 6. Edge cases and failure modes
Conditions under which the invention degrades or fails. Useful for both spec breadth and for anticipating §112(b) definiteness questions.

## 7. Out of scope
Adjacent ideas the inventor has but is NOT claiming. Critical for scope discipline — prevents the drafter from over-claiming and the s101 critic from rejecting on preemption grounds.

## 8. Open questions for inventor
Questions the intake could not answer from the supplied disclosure and that the human attorney must resolve with the inventor before final filing. These do NOT block draft — they block finalize.
```

## Procedure

1. **Discover state**: check whether `<thread>/BRIEF.md` already exists. If yes and it parses (has the frontmatter and 8 sections), exit early with a notice (idempotent). If it exists but is unstructured (looks like the raw disclosure was pasted in), back it up to `<thread>/BRIEF.unstructured.md` and proceed.
2. **Read inputs**: enumerate `<thread>/refs/**`. If empty or absent, exit with an error: "no disclosure materials found in `<thread>/refs/`; place inventor disclosure there first."
3. **Extract structured content**: for each of the 8 sections, scan the disclosure materials for relevant content:
   - **Problem statement**: usually in the first few paragraphs of the disclosure or interview opener.
   - **Prior approaches**: look for explicit references to commercial products, papers, prior internal work.
   - **Key inventive features**: look for "what's new", "the key insight", "our contribution" phrasing. Be ruthless about pruning to 3–7; if the inventor lists 15 features, group and consolidate to the most defensible 3–7.
   - **Embodiments**: anything the inventor said "we built" or "we simulated" or "we have a prototype that".
   - **Ranges and alternatives**: numeric ranges, materials lists, alternative geometries.
   - **Edge cases**: anything the inventor said "doesn't work when" or "breaks down at" or "we haven't tried beyond".
   - **Out of scope**: anything the inventor explicitly excluded ("we're not claiming X"), or that is clearly outside the named field of use.
   - **Open questions**: anything the disclosure could not resolve unambiguously.
4. **Synthesize**: write `<thread>/BRIEF.md` with the frontmatter + 8 sections. Use the inventor's language where possible — the brief should read like the inventor wrote it, cleaned up.
5. **Flag gaps**: if any section has fewer than 2 substantive bullets / sentences, list it explicitly in `## 8. Open questions for inventor` rather than padding with speculation. A thin section is a flag, not a failure.
6. **Report**: print the path to the written brief and a one-line summary (e.g., `Intake done: acme-widget/BRIEF.md (5 inventive features, 3 open questions for inventor)`).

## Idempotence

- A well-formed `BRIEF.md` is never overwritten. Re-running is a no-op with a notice.
- A malformed `BRIEF.md` is backed up to `BRIEF.unstructured.md` before being replaced.
- If the operator wants to re-intake from scratch, delete `BRIEF.md` first.

## Notes for the intake agent

- **Do not invent.** If the disclosure doesn't say something, put a question in §8, don't make it up. Hallucinated brief content poisons the entire downstream pipeline.
- **Inventor language is valuable.** The inventor's phrasing often captures distinctions that matter for claim drafting (e.g., the inventor said "modulator" not "switch" — keep that). Don't over-paraphrase.
- **3–7 inventive features is a hard target.** Fewer than 3 suggests the invention isn't substantial enough to file; flag in §8. More than 7 suggests poor scoping; consolidate.
- **§7 (out of scope) is load-bearing.** Out-of-scope material here protects against the §101 critic later. An inventor who refuses to name out-of-scope material likely has a §101 problem brewing.

## `_progress.json`

This command does NOT write a `_progress.json` — intake operates on the thread root (`<thread>/`), not a version directory. The existence and well-formedness of `BRIEF.md` is the state signal the orchestrator uses to determine `INTAKE_DONE`.


**Snippet references**: See `anvil/lib/snippets/progress.md` for the `_progress.json` read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC timestamp convention. The merge is shallow: preserve fields and phases not touched by this command.
