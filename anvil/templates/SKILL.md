---
name: anvil:<type>
description: <one-line description of what this skill produces>
domain: <domain — e.g. "investment", "ip", "research", "marketing">
type: <artifact type — e.g. "memo", "patent", "paper", "deck">
user-invocable: true
---

# anvil:<type> — <Skill display name>

> Template scaffold. Replace every `<type>` and the placeholder content
> below with skill-specific text. Delete this blockquote when done.

This skill produces **<artifact type>** in Anvil's standard
version-dir + sibling-critic layout, with a rigorous review/revise loop
driven by an 8-dimension /40 rubric.

## Lifecycle commands

Every Anvil skill ships at minimum:

| Command | Purpose | Reads | Writes |
|---|---|---|---|
| `<type>-draft` | Produce the first version. | Brief or upstream artifact. | `<thread>.1/` |
| `<type>-review` | Score the latest version. | `<thread>.{N}/` | `<thread>.{N}.review/` |
| `<type>-revise` | Apply the review's `fix` field. | `<thread>.{N}/`, `<thread>.{N}.review/` | `<thread>.{N+1}/` |
| `<type>-audit` | Tool-evidence verification (optional or mandatory per skill). See `anvil/lib/snippets/audit.md` for the `.review/` vs `.audit/` distinction and the per-finding `tool_calls[]` contract. | Latest READY version. | `<thread>.{N}.audit/` with `_review.json` `kind: tool_evidence`. |

Some skills add `<type>-figures` (for skills with assets / diagrams) or
specialist critic commands (`<type>-narrative`, `<type>-market`, etc.).

## State machine

```
EMPTY → DRAFTED → REVIEWED → REVISED → REVIEWED → … → READY → AUDITED
```

The version dir's `_progress.json` carries the state; the reviser
short-circuits if the latest review's verdict is `ADVANCE`, otherwise it
produces `<thread>.{N+1}/`.

## Critic output: the canonical `_review.json` contract

Every `<type>-review` command (and any specialist critic command) MUST
write a single `_review.json` file in its sibling dir. This is the
load-bearing contract consumed by the reviser. The schema is defined in
`anvil/lib/review_schema.py` and exported as JSON Schema at
`anvil/lib/review_schema.json`. See `anvil/lib/README.md` for the
field-by-field reference.

**Minimum required fields** in every `_review.json`:

```json
{
  "schema_version": "1",
  "kind": "judgment",
  "version_dir": "<thread>.{N}",
  "critic_id": "<type>-review",
  "scores": [
    {
      "dimension": "<dim_1>",
      "score": 4,
      "max": 5,
      "critical": false,
      "fix": "<one-sentence revision instruction>"
    },
    ...
  ]
}
```

For specialist critics that own a subset of dimensions, set `score: null`
on unowned dimensions and use `justification` to point at the owning
critic (e.g. `"n/a — see <type>-market"`). The aggregator computes
mean-of-non-null per dimension.

**Prose siblings** (`verdict.md`, `comments.md`, `findings.md`) are
optional human-readable artifacts. They are NOT load-bearing — the
reviser ignores them. New skills MAY skip them entirely.

**Critical flags** that should short-circuit the verdict go in the
top-level `critical_flags` array, not in per-dimension `critical` flags.
(Per-dim `critical` is for dim-scoped critical defects; top-level flags
are for cross-cutting "stop reading" defects.)

**Computing the verdict** is the *aggregator's* job, not any single
critic's. Per-critic `verdict` fields are accepted but ignored — set them
only as a per-critic sanity check, not as the source of truth.

### Audit-class critics: `kind: tool_evidence`

Audit-class critics (typically `<type>-audit`) MUST set
`kind: "tool_evidence"` on their `_review.json` payload, and every entry
in `findings[]` MUST carry a non-empty `tool_calls` array recording the
tool invocations that produced the evidence. The schema validator at
`anvil/lib/review_schema.py::Review._validate_kind_required_fields`
rejects any `tool_evidence` review whose findings omit `tool_calls`. See
`anvil/lib/snippets/audit.md` for the principled `.review/` vs `.audit/`
split and the per-skill mapping table.

Minimal `_review.json` example for an audit critic:

```json
{
  "schema_version": "1",
  "kind": "tool_evidence",
  "version_dir": "<thread>.{N}",
  "critic_id": "<type>-audit",
  "scores": [
    {
      "dimension": "<dim_1>",
      "score": 4,
      "max": 5,
      "critical": false,
      "justification": "Citation resolution check passed."
    }
  ],
  "findings": [
    {
      "severity": "major",
      "dimension": "<dim_1>",
      "rationale": "Cited paper does not support the surrounding claim.",
      "suggested_fix": "Drop the citation or replace with a supporting source.",
      "tool_calls": [
        {
          "tool": "grep",
          "args": { "pattern": "\\\\cite\\{smith2024\\}", "path": "main.tex" },
          "result_summary": "1 occurrence at line 142"
        },
        {
          "tool": "read_pdf",
          "args": { "path": "refs/smith2024.pdf" },
          "result_summary": "Section 3 discusses unrelated topic"
        }
      ]
    }
  ]
}
```

## Directory layout

```
<thread>.1/                     # first draft
  <artifact-files>              # e.g. memo.md, spec.tex, deck.md
  _progress.json

<thread>.1.review/              # general reviewer's output
  _review.json                  # ← canonical contract
  _progress.json
  verdict.md                    # optional, human-only
  comments.md                   # optional, human-only

<thread>.1.<specialist>/        # optional specialist critics
  _review.json                  # owns a subset of dimensions

<thread>.2/                     # next revision (after revise)
  ...

<thread>.2.review/              # ...and its review
  ...
```

The version dir name is `<thread>.{N}`. The sibling critic dirs are
`<thread>.{N}.<tag>` for some tag (`review`, `audit`, `narrative`,
`market`, `s112`, `design`, etc.). The lib's `discover_critics()`
enumerates these.

## Rubric

Each skill defines its rubric in `anvil/skills/<type>/rubric.md` with:

- 8 dimensions summing to 40 (or skill-specific total).
- Advance threshold (typically `>= 32` for general work, `>= 35` for
  legal/customer-facing work).
- 3–5 example critical flags.
- Calibration guidance per dimension.

The rubric is what reviewers consult; the `_review.json` schema is
rubric-agnostic (the lib doesn't know your dimension names).

## Consumer overrides

Skills should accept an optional consumer-side override at
`.anvil/skills/<type>/rubric.overrides.md` that can ADD critical-flag
examples or tighten the threshold. The base rubric is never relaxed by
the override — overrides are additive.

## `_progress.json` contract

Each version dir and each critic sibling dir carries its own
`_progress.json` tracking phase state. The canonical fields:

```json
{
  "version": 1,
  "thread": "<slug>",
  "phases": {
    "<phase>": {
      "state": "pending|in_progress|done|failed",
      "started": "<ISO-8601>",
      "completed": "<ISO-8601>"
    }
  }
}
```

Critic siblings additionally carry `for_version: <N>` naming the version
they review. `_progress.json` is **distinct from** `_review.json`: the
former tracks phase state for resume; the latter is the critique payload.

## Idempotence

Every command MUST be idempotent on re-invocation:

- A completed phase (`done` AND the file existence check passes) is never
  re-run; re-invoking prints a notice and exits.
- A crashed phase (`in_progress` without the expected output files) is
  re-runnable after deleting partial output. Validation is by file
  existence, not solely by flag.

## Reading the rubric

```python
# In your <type>-review command, do not hand-roll rubric parsing.
# Load the rubric from the skill dir; emit one Score row per dim
# regardless of whether you own that dim.

from anvil.lib.review_schema import Review, Score

scores = [
    Score(dimension="<dim_1>", score=4, max=5, critical=False, fix="..."),
    Score(dimension="<dim_2>", score=None, max=6, critical=False,
          justification="n/a — see <type>-market"),
    # ...one row per rubric dimension, owned or not.
]

review = Review(
    schema_version="1",
    kind="judgment",
    version_dir="<thread>.{N}",
    critic_id="<type>-review",
    scores=scores,
)

# Write to disk:
(critic_dir / "_review.json").write_text(review.model_dump_json(indent=2))
```

## Aggregating across critics

The reviser (or the orchestrator) consumes the lib directly:

```python
from anvil.lib.critics import (
    discover_critics, load_review, aggregate, compute_verdict,
)

siblings = discover_critics(version_dir)
reviews = [load_review(d) for d in siblings]
agg = aggregate(reviews)
verdict = compute_verdict(agg)

if verdict == "ADVANCE":
    # Promote to READY.
    ...
elif verdict == "BLOCK":
    # Surface critical flags; do not proceed to revise.
    ...
else:  # REVISE
    # Apply agg.scores[*].fix and agg.findings[*].suggested_fix
    # in <thread>.{N+1}/.
    ...
```

## See also

- `anvil/lib/README.md` — full schema reference and aggregation rules.
- `anvil/lib/examples/review-example.json` — fully-populated example.
- `CLAUDE.md` (repo root) — Anvil pattern overview.
- `anvil/skills/memo/` — reference implementation (memo).
