# Fixtures: body_filename customization (issue #279)

Two end-to-end fixtures exercising the per-thread `body_filename`
customization shipped under issue #279.

## `backward_compat/`

A minimal portfolio with one thread (`demo-thread`) that has **no
`.anvil.json`**. The default `body_filename` resolution path applies:
the body markdown lives at `demo-thread.1/memo.md`, exactly as every
memo thread written before issue #279 shipped saw.

This fixture locks the **load-bearing backward-compat contract** (AC9
of issue #279): a thread with no `body_filename` declaration MUST
continue to use `memo.md` with zero behavioral change.

Layout:

```
backward_compat/                       Portfolio root
  demo-thread/                         Thread root (BRIEF.md, no .anvil.json)
    BRIEF.md                           Minimal investment-memo brief
  demo-thread.1/                       Version 1
    memo.md                            Body markdown — default filename
```

## `paper_shape/`

A minimal portfolio with one thread (`latency-wall`) that **declares
`body_filename: "paper.md"`** in `.anvil.json`. The override resolution
path applies: the body markdown lives at `latency-wall.1/paper.md`
(NOT `memo.md`).

The fixture demonstrates the canary use case: 2AM Logic Studio's
brains-for-robots venture runs five thread types under `anvil:memo`,
four of which (latency-wall paper, technical-vision, execution-plan,
team-thesis) benefit from a non-`memo.md` body filename for cosmetic
clarity.

The fixture also exercises the **coexistence** of `body_filename`
with `rubric_overrides` at the top level of `.anvil.json` — both
fields are sibling keys, neither nested inside the other.

Layout:

```
paper_shape/                           Portfolio root
  latency-wall/                        Thread root
    BRIEF.md                           Minimal position-paper brief
    .anvil.json                        Declares body_filename + rubric_overrides
  latency-wall.1/                      Version 1
    paper.md                           Body markdown — overridden filename
```

## What these fixtures do NOT do

Per the Phase A scope of issue #279, these fixtures are **shape-only**:
they assert the on-disk layout, not behavioral round-trips through the
six memo commands. The behavioral coverage lives in
`test_anvil_config_body_filename.py` (the reader contract) and the
existing command-test suite (the prose-level wiring). A future Phase B
issue MAY extend these fixtures with end-to-end command invocations
(e.g., `memo-draft` → `memo-review` → `memo-revise` against each
fixture) when the canary surfaces a specific behavioral regression.
