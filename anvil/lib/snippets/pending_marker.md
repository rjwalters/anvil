# Pending-measurement placeholder convention

This snippet codifies a first-class convention for drafting an artifact
whose load-bearing number does not yet exist — a training run still
running, a benchmark queued, a vendor quote not returned. Without a
supported convention, correct behavior depends on ad-hoc per-thread
prompt discipline hand-written into `BRIEF.md`, and critics have no way
to distinguish "this number is missing because it's genuinely pending"
from "this number is missing because the drafter was sloppy" — or,
worse, from a drafter who fabricates a plausible-looking number rather
than admit the gap. This snippet promotes the framework-level
`anvil/lib/pending_marker.py` primitive so any skill can adopt the
convention without reinventing it.

## The marker syntax

A drafter marks a genuinely-outstanding value with a bracketed
placeholder naming its source:

```
The model reaches [PENDING benchmark-run-2024-11] accuracy on the
held-out set.

Component cost is [PENDING: vendor-quote-acme] per unit at the quoted
minimum order quantity.
```

**Well-formed shape**: `[PENDING <source>]` or `[PENDING: <source>]` —
the literal, **case-sensitive** keyword `PENDING` immediately after the
opening bracket, a colon and/or whitespace separator, then a non-empty
`<source>` label naming *what* is pending (a benchmark run id, a
vendor name, "Q3 earnings call", a training-run identifier), then the
closing bracket.

The uppercase keyword is deliberate — it mirrors the `TODO`/`FIXME`
code-comment convention so a genuine marker is visually and
mechanically unambiguous. It also means ordinary prose that happens to
use the word "pending" (*"results are pending"*, *"a decision is
PENDING review"*) is never mistaken for a marker: the detector matches
only the bracketed, uppercase, source-bearing shape.

**A source-less marker (`[PENDING]`, `[PENDING ]`) is malformed and is
NOT detected as a marker at all** — it degrades to an unexplained
bracket for both a human reader and the detector. Always name the
source; a marker without one defeats the purpose (a reader — or
critic — has no way to know what's being waited on, or when it will
resolve).

## No-fabrication discipline

This convention exists for the same reason `perspective.md`'s
no-fabrication rule exists (see that snippet's "No-fabrication rule"):
an LLM drafter under pressure to produce a complete-looking artifact
will otherwise either (a) silently invent a plausible number to fill
the gap, or (b) leave vague hand-wavy language ("results are
promising") that reads as evasive rather than honest. **Neither is
acceptable.** The pending marker is the third option: name the gap
explicitly, name what's needed to close it, and let the deterministic
gate (below) keep the artifact from shipping with the gap still open.

A drafter facing a genuinely-unresolved number MUST use a well-formed
pending marker rather than fabricate a value or hand-wave around the
gap. This rule is as load-bearing as `perspective.md`'s citation
discipline — the difference between "honest about what's not done yet"
and "fabricated to look done" is exactly the failure mode this
convention closes.

## Not a defect — but not silently ignored either

A well-formed pending marker gets two, deliberately different,
treatments from a consuming skill's critics:

1. **No dimension score penalty.** A reviewer scoring the artifact
   against its rubric MUST NOT deduct points on any dimension *because*
   a well-formed marker is present (e.g. an evidence-sufficiency or
   reproducibility dimension should not mark down for "missing data"
   when the data is honestly declared as pending). The marker is a
   disclosure, not a defect.
2. **Blocks `READY`/`AUDITED` until resolved.** An artifact with any
   unresolved pending marker cannot reach a terminal state. Resolving a
   marker means replacing its bracketed text with the real value — at
   that point the next detector pass finds nothing and the gate
   clears. This is enforced via the standard critical-flag short-circuit
   mechanism (see `critics.md` and the consuming skill's `rubric.md`),
   not by asking a reviewer to remember to check.

Combining these two rules matters: double-penalizing (a low dimension
score **and** a blocked verdict) punishes the honest disclosure the
convention exists to encourage, which pushes drafters right back
toward fabrication or hand-waving. The critical flag alone communicates
"not done yet"; the dimension scores should reflect the argument's
soundness *assuming* the pending value resolves as described.

## The deterministic gate

Unlike a nuanced judgment call (e.g. "does this citation actually
support this claim?"), whether a well-formed marker is still present
in the body is a binary, mechanical fact — there's no ambiguity to
adjudicate. `anvil/lib/pending_marker.py` is therefore a **judgment-free
deterministic gate**: it emits a `CriticalFlag` directly
(`to_review(blocking=True)`) when any unresolved marker remains,
rather than relying on an LLM reviewer to notice the marker text and
decide, on its own initiative, to write a flag. This is the direct fix
for the "ad-hoc per-thread prompt discipline" problem the convention
exists to close — the gate does not depend on anyone remembering to
check.

The same module also always emits an advisory `Finding` at the lowest
schema severity (`"nit"`) per marker — a "known-incomplete, outstanding
dependency" note for `verdict.md`/`findings.md`, independent of whether
the consuming command runs the check in blocking mode.

See the `anvil/lib/pending_marker.py` module docstring for the full
detection/masking/severity contract, and `anvil/lib/numeric_consistency.py`
for the sibling deterministic-checks-family precedent this module
follows (masking, sidecar shape, `blocking=True` posture).

## Sidecar shape

`anvil/lib/pending_marker.py::write_review_dir` writes
`<thread>.{N}.pending/_review.json` via the standard staged-sidecar
atomicity primitive (`anvil/lib/sidecar.py`). The `.pending` tag is a
single path segment, so `anvil/lib/critics.py::discover_critics` picks
it up automatically — no aggregator change is needed to wire a new
consumer skill in. Because the check is deterministic and cheaply
re-runnable, a later pass (e.g. a blocking audit-time run) freely
overwrites an earlier pass's sidecar (e.g. an advisory review-time
run) for the same version dir — the same deterministic-regeneration
carve-out `numeric_consistency.py` documents for its own sidecar.

## Optional `BRIEF.md` frontmatter: `pending_sources`

A thread MAY declare the pending sources it expects to resolve over its
lifetime in `<thread>/BRIEF.md` YAML frontmatter:

```yaml
---
pending_sources:
  - benchmark-run-2024-11
  - vendor-quote-acme
---
```

`anvil/lib/pending_marker.py::load_expected_pending_sources` reads this
list. It is **purely a reporting aid** — declaring a source here has NO
effect on gating: an undeclared marker still blocks advancement, and a
declared-but-never-written source is not itself a defect. What it
enables is a critic reporting, e.g., *"3 of 5 declared pending sources
resolved; 2 outstanding: vendor-quote-acme, benchmark-run-2024-11"* —
visibility into which of the anticipated gaps are still open, without
requiring the reviewer to scroll the whole body looking for brackets.

## Adopting the convention in a skill

To wire this convention into a skill's review/audit lifecycle:

1. In the skill's `<skill>-review` command, invoke
   `python -m anvil.lib.pending_marker <thread>.{N}/ --write-review --blocking`
   (or the `check_pending_markers` / `write_review_dir` Python API
   directly). This is an unconditional step — no per-thread opt-in
   needed, mirroring `numeric_consistency`'s always-on posture. Because
   the check is judgment-free, run it in **blocking mode directly** at
   review time (unlike the numeric-consistency arithmetic check, which
   stays advisory and folds into the reviewer's own judgment) — see
   "The deterministic gate" above for why.
2. Fold `result.outstanding_sources` / `result.resolved_sources` into
   the reviewer's `verdict.md`/`findings.md` as an explicit "Outstanding
   dependencies" note — this is the human-legible half of the
   acceptance criteria; the deterministic flag alone is not enough for
   an operator to know *what* is still pending.
3. Add a critical-flag bullet to the skill's `rubric.md` documenting
   the flag class (mirror the existing critical-flag list format —
   e.g. `paper/rubric.md`'s "Build / compile failure" entry, which
   documents the analogous `artifact_verify` deterministic gate from
   issue #663).
4. Add a scoring-guidance note that a well-formed marker does not incur
   a dimension penalty (see "Not a defect — but not silently ignored
   either" above) — this is the rule an LLM reviewer is most likely to
   get wrong by default (the instinct to mark down for "missing data"
   is strong), so it needs to be explicit in the rubric, not merely
   implied by this snippet.
5. Optionally, re-run the check at the skill's terminal-gate/audit
   phase too (defense in depth — useful when an operator runs the
   audit phase before the review loop reaches `READY`, which several
   skills' audit commands explicitly permit).

No framework changes are required beyond these skill-local wiring
steps — the discovery glob in `critics.md` picks up the new
`.pending/` sidecar automatically.

## See also

- `anvil/lib/pending_marker.py` — the detector/emitter module this
  snippet documents.
- `anvil/lib/numeric_consistency.py` — the sibling deterministic-checks
  primitive whose masking/sidecar/CLI shape this module mirrors.
- `perspective.md` — the no-fabrication framing this snippet's
  discipline section is adapted from.
- `critics.md` — sidecar discovery, aggregation, and the critical-flag
  short-circuit mechanism this convention routes through.
- `rubric.md` — the general "Dimension scoring guidance" contract a
  consuming skill's own `rubric.md` extends with the pending-marker
  critical-flag entry.
