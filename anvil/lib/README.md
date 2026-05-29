# anvil/lib/

Framework primitives shared across anvil skills. **Pure markdown** in v0;
no runtime, no Python, no install-time dependencies.

## Why markdown?

Skills themselves are markdown that an LLM consumes directly. The
duplication observed across the six v0 skills (`memo`, `pub`, `slides`,
`deck`, `report`, `ip-uspto`) is duplication of CONVENTION, not
duplication of executable code: every skill embeds a "minimal
read-merge-write snippet" for `_progress.json`, a "use ISO-8601 UTC
timestamps" expectation, a "discover `<thread>.{N}/` directories" recipe,
etc. The right primitive is a canonical text fragment the skill commands
**reference** rather than executable code they call.

Python is deferred until a non-LLM consumer exists. When a CLI
orchestrator, CI verifier, or daemon needs to inspect anvil artifacts
programmatically, those modules will land in this directory alongside
the snippets. For v0 the markdown snippets are the source of truth.

## Layout

```
anvil/lib/
  README.md                    This file.
  snippets/                    Canonical text fragments referenced by SKILL.md
                                and command files.
    progress.md                _progress.json schema, merge rule, crash recovery.
    timestamp.md               ISO-8601 UTC format convention.
    version_layout.md          <thread>.{N}/ + sibling naming rules.
    thread_state.md            Derive state-machine position from on-disk evidence.
    state_machine.md           Base state machine + canonical extension points.
    rubric.md                  8-dim /40 scoring shape + convergence logic.
    critics.md                 Sibling discovery + aggregation rules.
    scorecard_kind.md          human-verdict | machine-summary discriminator.
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
`<consumer>/.anvil/lib/` in stage 5 (`copy framework code`). The
snippets land at `<consumer>/.anvil/lib/snippets/*.md` and are
referenced from the installed `.anvil/skills/<skill>/SKILL.md` and
command files by the `.anvil/lib/snippets/<name>.md` relative path.

## Why these 8 snippets?

Each snippet corresponds to one source of duplication observed across
the six v0 skill implementations. The full reconciliation appears in
issue #10's curation comment; the short version per file:

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

## Deferred (NOT in v0)

The following are explicitly out of scope for the initial lib extraction
and are tracked as separate follow-up issues:

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
- **Python module bindings** — when a non-LLM consumer (CLI, daemon,
  CI verifier) needs to inspect anvil artifacts programmatically.

## See also

- `anvil/skills/*/SKILL.md` — each skill's authoritative definition,
  with cross-references back to the snippets.
- `anvil/skills/README.md` — skill layout convention.
- Repository `README.md` — anvil's overall design principles.
