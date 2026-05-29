# anvil/lib/

Framework primitives consumed by Anvil skills.

This directory holds two complementary kinds of primitive:

1. **Markdown snippets** under `snippets/` — the canonical text fragments
   skill commands reference so the conventions ( `_progress.json` shape,
   timestamp format, version-dir naming, `scorecard_kind` discriminator,
   etc.) live in one place rather than duplicated across every skill.
   Skills themselves are markdown that an LLM reads directly, so
   referencing a snippet is the right primitive for LLM-side
   coordination. Landed by #10.
2. **Python types** for the critic-output contract: `review_schema.py`,
   `review_schema.json`, and `critics.py`. These are the machine-readable
   export of the same `scorecard_kind` discriminator the snippets
   describe, intended for non-LLM consumers (CLI orchestrators, CI
   verifiers, future TypeScript callers). Landed by #26.

The snippets are the source of truth for LLM-driven authoring; the
Python types are the source of truth for programmatic validation and
aggregation. They MUST agree. When they diverge, treat it as a bug.

## Layout

```
anvil/lib/
  README.md                    This file.
  snippets/                    Canonical markdown text fragments (#10).
    progress.md                _progress.json schema, merge rule, crash recovery.
    timestamp.md               ISO-8601 UTC format convention.
    version_layout.md          <thread>.{N}/ + sibling naming rules.
    thread_state.md            Derive state-machine position from on-disk evidence.
    state_machine.md           Base state machine + canonical extension points.
    rubric.md                  8-dim /40 scoring shape + convergence logic.
    critics.md                 Sibling discovery + aggregation rules.
    scorecard_kind.md          human-verdict | machine-summary discriminator.
  review_schema.py             Pydantic models for the unified `_review.json`
                                payload (the machine-readable canonicalization
                                of the markdown snippets above). (#26)
  review_schema.json           Auto-generated JSON Schema export of the
                                pydantic models. Regenerate with
                                `python3 -m anvil.lib.export_schema`. (#26)
  critics.py                   Discovery, loading, aggregation, verdict
                                computation, and a legacy adapter that reads
                                the memo prose triple and the ip-uspto
                                _summary/findings/_meta triple. (#26)
  export_schema.py             One-shot exporter for review_schema.json.
  examples/
    review-example.json        Fully-populated worked example fixture.
```

## How skills consume snippets

Skills reference snippets by path. The reference is resolvable at
read-time by an LLM (which can read the file directly when needed) and
is also a clear pointer for human readers.

In SKILL.md or a command file:

> The `_progress.json` schema and the read-merge-write convention live in
> `anvil/lib/snippets/progress.md` (or `.anvil/lib/snippets/progress.md`
> in an installed consumer repo). Every command in this skill follows
> that convention.

Skill commands MAY also embed short reminders of the convention inline
(e.g., the expected JSON shape) for ease of reading, but the canonical
definition lives in the snippet file. When the snippet and an inline
copy diverge, the snippet wins.

## Install-time copying

The install script (`scripts/install-anvil.sh`) copies `anvil/lib/` to
`<consumer>/.anvil/lib/` in stage 5 (`copy framework code`). Both the
markdown snippets and the Python modules land alongside each other; the
consumer repo's commands reference them by the `.anvil/lib/snippets/<name>.md`
relative path.

## Why these 8 snippets?

Each snippet corresponds to one source of duplication observed across
the six v0 skill implementations. The short version per file:

| Snippet | Why |
|---|---|
| `progress.md` | Every command embedded `_progress.json` read-merge-write inline; consumer agents invented divergent JSON shapes. |
| `timestamp.md` | Each command picked its own timestamp format. |
| `version_layout.md` | `<thread>.{N}/` and sibling rules were redocumented per skill. |
| `thread_state.md` | Drafter, reviser, and orchestrator each reimplemented thread enumeration. |
| `state_machine.md` | Base state machine + extension points (pre-draft, mid-loop, post-AUDITED terminal) were rewritten per skill. |
| `rubric.md` | 8-dim /40 shape + convergence logic was rewritten per skill, with subtle divergences. |
| `critics.md` | Glob discovery + per-dim mean aggregation was rewritten per skill. |
| `scorecard_kind.md` | The 5+ critic schema shapes collapse to 2 canonical kinds via a discriminator field; this is the load-bearing primitive that unifies the others. |

## The canonical `_review.json` contract (Python types)

The Python schema in `review_schema.py` is a **single typed JSON shape**
that captures the machine-readable subset of the markdown snippets:

- It folds `_meta.json` (ip-uspto), `verdict.md` (memo) and
  `_summary.md` (ip-uspto / deck) into one payload, removing the
  per-skill divergence in disk layout.
- It pins the `kind` field reserved values (`judgment`,
  `tool_evidence`, `vision`) so #29 and #30 can ship without a
  schema-version bump.
- It pins the `verdict` enum (`ADVANCE`, `REVISE`, `BLOCK`, `STALLED`)
  to match the snippet `rubric.md` decision rule, reserving `STALLED`
  for #27's stable-score termination.

Writing `_review.json` is optional in v1: shipped skills continue to
emit the prose triples documented in `snippets/scorecard_kind.md`, and
the legacy adapter in `critics.py` bridges them. New skills SHOULD write
`_review.json` directly; migrations of the six shipped skills happen as
separate per-skill PRs.

### Field reference

#### `Review` (per-critic payload)

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | `"1"` literal | yes | Pinned. Bumps require a schema-version-rolling PR; additive fields do not. |
| `kind` | `"judgment" \| "tool_evidence" \| "vision"` | yes (default `judgment`) | Reserves space for #29 (tool-evidence) and #30 (vision) without a schema bump. v1 actively uses only `judgment`. |
| `version_dir` | string | yes | Name of the version dir under review, e.g. `"acme-seed.3"`. Lets the file travel out of its sibling dir and remain locatable. |
| `critic_id` | string | yes | Stable identifier for this critic (`"memo-review"`, `"deck-market"`, `"ip-uspto-s112"`). |
| `model` | string | no | Model identifier (`"claude-opus-4-7"`). Strongly recommended for reproducibility. |
| `rubric` | string | no | Rubric identifier (`"anvil-memo-v1"`). The aggregator uses this only to surface mismatched-rubric warnings. |
| `scores` | `Score[]` | yes (non-empty) | One row per rubric dimension, including dimensions this critic doesn't own (`score: null`). |
| `findings` | `Finding[]` | no | Itemized critique items beyond the scorecard. Empty is valid (clean review). |
| `critical_flags` | `CriticalFlag[]` | no | Top-level critical flags. Any non-empty list forces `Verdict.BLOCK`. |
| `total` | int | no | This critic's own sum-of-non-null. Informational on a per-critic basis; the aggregator recomputes. |
| `threshold` | int | no | Echoed from the rubric. Required on `AggregatedReview`. |
| `verdict` | `Verdict` enum | no | Per-critic verdict, optional and ignored by the aggregator (the aggregator recomputes from the merged scorecard). |
| `rendered_artifact` | string | conditional | Required when `kind == "vision"`; path of the rendered artifact (relative to `version_dir`). |

#### `Score` (one rubric dimension)

| Field | Type | Required | Notes |
|---|---|---|---|
| `dimension` | string | yes | Dimension identifier. Skills choose convention (memo: `"evidence_quality"`; deck: `"2_problem_clarity"`). Opaque to the lib. |
| `score` | int or null | yes | Integer in `[0, max]`, or `null` if this critic doesn't own this dim. Use `null` (not `0`) for unowned dims. |
| `max` | int (>= 1) | yes | Per-dim weight from the rubric. Echoed here so a stand-alone `_review.json` is self-contained. |
| `critical` | bool | yes (default `false`) | True when this dim has a critical-flag-worthy defect. Aggregation is logical OR. |
| `evidence_span` | string | no | Pointer to source location. Format: `"<path>:L<start>-L<end>"` for text; `"<path>:slide=<N>"` for deck/slides. |
| `fix` | string | no | One-sentence actionable revision instruction. The reviser reads this. |
| `justification` | string | no | 1–3 sentence rationale. When `score is None`, use this to point at the owning critic (`"n/a — see deck-market"`). |

#### `Finding` (one actionable critique item)

| Field | Type | Required | Notes |
|---|---|---|---|
| `severity` | `"blocker" \| "major" \| "minor" \| "nit"` | yes | `blocker` implies critical. |
| `dimension` | string | no | Dim this finding contributes to. Optional — cross-cutting findings (e.g. "fix all citations") need not name one. |
| `evidence_span` | string | no | Same format as `Score.evidence_span`. |
| `rationale` | string | yes | 1–2 sentences explaining the defect. |
| `suggested_fix` | string | yes | One sentence: what the reviser should do. |
| `tool_calls` | `ToolCall[]` | conditional | Required when parent `Review.kind == "tool_evidence"`. |

#### `CriticalFlag` (verdict-blocking flag)

| Field | Type | Required | Notes |
|---|---|---|---|
| `type` | string | yes | Short tag (`"fabricated_traction"`, `"factual_error"`). Skill-defined. |
| `justification` | string | yes | One paragraph: why this is a critical flag. |
| `evidence_span` | string | no | Pointer to the source location. |

### `evidence_span` format

The reviser uses spans to locate text for revision without re-reading the
whole artifact. v1 documents two conventions but does NOT enforce them via
regex — skills disagree on path prefixes.

| Artifact type | Format | Example |
|---|---|---|
| Text (memo, pub, report, ip-uspto spec) | `<path>:L<start>-L<end>` | `"memo.3/memo.md:L42-L58"` |
| Deck / slides | `<path>:slide=<N>` | `"deck.1/deck.md:slide=4"` |
| Drawings / figures (ip-uspto) | `<path>:fig=<N>` (suggested) | `"acme-widget.2/drawings/fig-3.svg:fig=3"` |

### `kind` field

| Value | Meaning | Schema requires |
|---|---|---|
| `judgment` | Standard rubric-scored review (v1 default). | Nothing extra. |
| `tool_evidence` | Review backed by tool calls (#29). | `tool_calls` array per finding. |
| `vision` | Vision-model review of a rendered artifact (#30). | `rendered_artifact`. |

v1 actively uses only `judgment`. The other values are accepted by the
parser so #29 and #30 do not need a schema-version bump when they ship.

### `verdict` enum

| Value | Meaning |
|---|---|
| `ADVANCE` | `total >= threshold` AND no critical flag. |
| `REVISE` | `total < threshold` AND no critical flag. |
| `BLOCK` | Any critical flag is set (regardless of total). |
| `STALLED` | Reserved for #27 — stable-score termination when successive revisions stop improving. v1 does not produce this value. |

The decision rule is implemented in `critics.py::compute_verdict` and is
a pure function over the aggregated scorecard. Per-critic `verdict`
values are ignored by the aggregator — only the merged total + flags
decide. This matches the canonical decision rule documented in
`snippets/rubric.md`.

## The discovery and aggregation API

```python
from pathlib import Path
from anvil.lib.critics import (
    discover_critics,
    load_review,
    aggregate,
    compute_verdict,
)

# 1. Walk for sibling critic dirs at this version.
sibling_dirs = discover_critics(Path("acme-seed.3"))
# -> [Path('acme-seed.3.review'), Path('acme-seed.3.market'), Path('acme-seed.3.narrative')]

# 2. Parse each sibling's _review.json (or legacy triple via the adapter).
reviews = [load_review(d) for d in sibling_dirs]

# 3. Aggregate. Pure function; no filesystem access.
agg = aggregate(reviews)

# 4. Verdict. Pure function; uses agg.threshold by default.
verdict = compute_verdict(agg)
```

### Aggregation rules

For each rubric dimension across the N per-critic `Review` objects:

- **`score`**: mean of non-null per-critic scores, rounded to nearest int
  with banker's rounding (Python `round`). The float mean is preserved on
  `AggregatedReview.score_means[dim]` so reporting doesn't lose precision.
  When no critic scored a dimension, the aggregated score is `None` and
  contributes 0 to the total.
- **`critical`**: logical OR across critics for that dim.
- **`fix`**: deduplicated union of non-null per-critic `fix` strings,
  joined with `"; "` for human readability.
- **`evidence_span`**: first non-null span in critic order.
- **`justification`**: first non-null justification in critic order.
- **`max`**: required consistent across critics for a given dim; a
  mismatch raises `ValueError`.

`findings` and `critical_flags` are deduplicated by exact-string equality
on `(severity, dimension, rationale, suggested_fix)` and
`(type, justification)` respectively. Two critics emitting *almost* the
same finding will both surface — by design, so the reviser sees both
phrasings.

These rules match the aggregation pseudocode in `snippets/critics.md` and
`snippets/scorecard_kind.md`.

### Worked example — three critics, partial ownership

Suppose three deck critics with overlapping ownership:

| Dim | deck-review (general) | deck-narrative | deck-market | mean | aggregated |
|---|---|---|---|---|---|
| 1_recommendation | 4/5 | 5/5 (owned) | null | 4.5 | 4 (banker's) |
| 2_problem_clarity | 3/6 (owned) | 4/6 | null | 3.5 | 4 (banker's) |
| 3_market_framing | null | null | 4/4 (owned, with critical=true) | 4 | 4, critical=true |
| 4_thesis | 5/6 (owned) | null | null | 5 | 5 |
| 5_evidence | 4/6 (owned) | null | null | 4 | 4 |
| 6_competitive | null | null | 3/5 (owned) | 3 | 3 |
| 7_design | 3/4 (owned) | null | null | 3 | 3 |
| 8_polish | 3/4 (owned) | null | null | 3 | 3 |
| | | | | **total** | **30** |

Banker's rounding (Python `round`): 4.5 → 4 and 3.5 → 4 (round-half-to-even).

If the threshold is `28`, the aggregated total is `30 >= 28` so the
score-based decision is ADVANCE. But dim 3 has `critical=true`, so
`compute_verdict` returns **BLOCK**. The critical flag short-circuits
regardless of total.

If dim 3's critical flag is dropped, the verdict becomes ADVANCE. If the
threshold were `32` instead of `28`, total `30 < 32` so the verdict would
be REVISE.

## Legacy adapter and migration path

The lib reads three on-disk shapes today:

1. **Canonical** — `_review.json` (this contract). Preferred.
2. **Memo prose triple** — `verdict.md` + `scoring.md` + `comments.md`.
   This is the `human-verdict` shape per `snippets/scorecard_kind.md`,
   used by memo, report, pub.
3. **ip-uspto hybrid** — `_summary.md` + `findings.md` + `_meta.json`.
   This is the `machine-summary` shape per `snippets/scorecard_kind.md`,
   used by ip-uspto and the deck specialists.

When a critic sibling contains both `_review.json` and a legacy triple,
the canonical JSON wins and the legacy files are treated as stale (with a
`DeprecationWarning`). When only a legacy triple exists, the adapter
parses it into a `Review` and emits a `DeprecationWarning` per call so the
migration backlog is visible.

The adapter is a **bridge**, not a permanent home. Each shipped skill
should migrate its `<skill>-review` command to write `_review.json` in a
separate PR; the adapter exists so this issue can land without a six-skill
coordinated rewrite.

### Migration path for shipped skills

The skill migrations are out of scope for the issue that landed the
Python lib (#26). They are tracked as separate per-skill follow-up
issues. The expected sequence per skill:

1. Update `<skill>-review.md` (the review-command spec) to require writing
   `_review.json` in the canonical schema, in addition to the existing
   prose siblings.
2. (Optionally) Stop writing the prose siblings, once the reviser is
   verified to ignore them entirely.
3. Update `<skill>-revise.md` to consume `_review.json` via
   `anvil.lib.critics.load_review` instead of parsing prose.
4. Update the skill's `SKILL.md` to document the JSON contract.
5. Add an `anvil/skills/<skill>/examples/_review.example.json` for that
   skill's specific rubric.

The lib's API surface is stable from the moment #26 lands; skill
migrations can land in any order.

## Re-exporting the JSON Schema

After any change to `review_schema.py`, regenerate the JSON Schema:

```bash
python3 -m anvil.lib.export_schema
```

This rewrites `anvil/lib/review_schema.json`. The export is deterministic
(sorted keys, fixed indent) so the diff is reviewable.

## Tests

Unit tests live in `tests/lib/`:

- `tests/lib/test_review_schema.py` — schema validation, partial scorecard
  round-trip, schema rejection on missing fields and out-of-bounds scores.
- `tests/lib/test_critics.py` — discovery, loading, aggregation across
  multi-critic fixtures, verdict at threshold boundary, legacy adapter for
  both memo and ip-uspto shapes.

Run with `pytest tests/lib/` from the repo root.

## Citations: `cite.py`

The citation primitive lives in `anvil/lib/cite.py`. It is the
machine-side companion to the markdown convention documented in
`snippets/cite.md`. Public API:

```python
from pathlib import Path
from anvil.lib.cite import (
    cite,
    resolve,
    parse_identifier,
    bib_key,
    Identifier,
    BibRecord,
    IdentifierKind,
    CiteResolutionError,
    UnsupportedIdentifierError,
)

# 1. Top-level convenience: parse, resolve, write, return @key.
key = cite("10.1038/nature12373", Path("acme-seed.3"))
# -> "@kucsko2013nanometre"
# refs.bib has gained one entry; calling again is a no-op (idempotent).

# 2. Lower-level: parse + resolve separately.
identifier = parse_identifier("https://arxiv.org/abs/1706.03762")
record = resolve(identifier)
# record is a BibRecord with entry_type="misc", eprint="1706.03762", ...

# 3. Generate a bib key without writing.
plain_key = bib_key(record)             # 'vaswani2017attention'
collision_safe = bib_key(record, refs_bib=Path("acme-seed.3/refs.bib"))
```

### Supported identifier kinds (v0)

| Kind | Status | Resolver |
|---|---|---|
| `DOI` | supported | Crossref (`https://api.crossref.org/works/{doi}`) |
| `ARXIV` | supported | arXiv API (`https://export.arxiv.org/api/query?id_list=...`) |
| `PMID` | parses, raises `UnsupportedIdentifierError` on `resolve()` | follow-up |
| `URL` | parses, raises `UnsupportedIdentifierError` on `resolve()` | follow-up |

`parse_identifier` returns `IdentifierKind.URL` for any well-formed
`http(s)://` URL it does not recognize as a DOI or arXiv ID. The
`UnsupportedIdentifierError` then comes from `resolve()` so callers can
distinguish "garbage input" (raises `ValueError` at parse) from "valid
URL but no scraper in v0" (raises `UnsupportedIdentifierError` at
resolve).

### Cache

Resolved records cache to `~/.cache/anvil/cite/<kind>/<urlquoted-value>.json`.
Atomic writes (`.tmp` then `os.rename`); directory mode is `0700`. No
TTL — bibliographic records are stable. Set `CITE_CACHE_BYPASS=1` to
disable both read and write (useful when debugging the live resolver
against test cassettes).

### BibTeX shape

The writer emits BibTeX 0.99 entries with a fixed field order
(`author`, `title`, `journal`, `year`, `volume`, `number`, `pages`,
`doi`, `eprint`, `eprinttype`, `url`). Empty fields are omitted
entirely. Multi-author lists use ` and ` as the separator. One blank
line between entries.

`@article` is used for Crossref journal articles; `@misc` for arXiv
preprints (with `eprint` + `eprinttype=arxiv`). `inproceedings` and
`book` are reserved in the `BibRecord.entry_type` literal so a future
resolver can populate them without a schema bump.

### Citation-quality rubric dimensions

Skills that produce sourced artifacts opt in to two canonical rubric
dimensions:

- **`citation_recall`** — claims-with-citations / total-claims.
- **`citation_precision`** — claims-supported-by-cited-source /
  claims-with-citations.

These are first-class dimensions, not sub-fields of any other dim,
because the `Score` model enforces one integer score per dimension.
Adding them is **per-consumer rubric work**, not lib work — the lib
documents the naming convention but does not split any existing skill
rubric. See `snippets/rubric.md` for the migration pattern (split an
existing citation-related dimension to preserve the /40 envelope).

### The CSL boundary

**`cite.py` produces BibTeX. CSL is per-skill.** The lib ships zero
CSL files and zero CSL knowledge. Consumer skills that want
CSL-rendered citations (e.g. `anvil:pub`, `anvil:report`) ship an
`apa-7.csl` or similar under their own `assets/` directory and the
skill's render command picks it up.

`anvil:ip-uspto` uses a custom BibTeX style (USPTO formal-requirements
formatting); the lib does not need to know about that either.

### Tests

Unit tests live in `tests/lib/test_cite.py`. Cassettes
(hand-curated Crossref JSON + arXiv Atom XML) are committed under
`tests/lib/cassettes/cite/`. `urllib.request.urlopen` is patched at
test time to return cassette content; no live network calls happen in
CI. A single `@pytest.mark.network` test against a live DOI is
provided for smoke testing and is skipped by default.

To record additional cassettes:

```bash
curl -H "User-Agent: anvil-cite/0.0.1 (https://github.com/rjwalters/anvil)" \
  "https://api.crossref.org/works/10.xxx/xxx" \
  > tests/lib/cassettes/cite/crossref-10.xxx_xxx.json

curl -H "User-Agent: anvil-cite/0.0.1 (https://github.com/rjwalters/anvil)" \
  "https://export.arxiv.org/api/query?id_list=YYMM.NNNNN" \
  > tests/lib/cassettes/cite/arxiv-YYMM.NNNNN.xml
```

## Deferred (NOT in v0)

The following are explicitly out of scope and are tracked as separate
follow-up issues:

- **`presentation_renderer`** — shared Marp pipeline for deck + slides.
  Will land when both skills have stabilized their render-time
  requirements.
- **`citation_lint`** — deterministic count of unsourced numeric
  claims. Skill-specific (memo/pub care; deck/slides much less).
- **`voice_lint`** — ban LLM tics ("available on request",
  "reference TBD"). Skill-agnostic but better implemented per-skill
  first to establish the pattern.
- **Two-stage terminal-state runtime hook** — the
  `AUDITED → CUSTOMER-READY` (report) and `AUDITED → FINALIZED`
  (ip-uspto) pattern is currently inline per-skill. Will be promoted
  to a first-class lib primitive when a third skill needs it.

## See also

- `anvil/skills/*/SKILL.md` — each skill's authoritative definition,
  with cross-references back to the snippets.
- `anvil/skills/README.md` — skill layout convention.
- `anvil/lib/examples/review-example.json` — fully-populated example
  of the `_review.json` contract.
- Repository `README.md` — anvil's overall design principles.
