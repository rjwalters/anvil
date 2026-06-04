# project_brief fixture (issue #284)

This fixture pins the dual-layout thread-root discovery contract
shipped under issue #284 (sub-deliverable 1 of #283). It carries three
on-disk shapes that exercise the layout-precedence rule:

1. **`brains-for-robots/`** — the canary's intended five-document
   project-as-thread-root shape. A single project-level `BRIEF.md`
   with a non-empty `documents:` frontmatter list naming five slugs;
   each slug has its own subdirectory carrying version dirs
   (`<slug>.N/`).
2. **`classic-portfolio/`** — the classic siblings-under-portfolio
   layout. No project BRIEF; each thread is a standalone directory
   with its own per-thread `BRIEF.md` and version dirs.
3. **`empty-documents-project/`** — edge case: a directory with a
   `BRIEF.md` whose `documents:` list is empty. Discovery must NOT
   treat this as a project root; the layout falls back to classic.

## Shape

```
project_brief/
  brains-for-robots/            (project-brief layout)
    BRIEF.md                    (frontmatter has non-empty documents: list)
    investment-memo/
      investment-memo.1/
        memo.md                 (placeholder body)
    latency-wall/
      latency-wall.1/
        memo.md
    technical-vision/
      technical-vision.1/
        memo.md
    execution-plan/
      execution-plan.1/
        memo.md
    team-thesis/
      team-thesis.1/
        memo.md

  classic-portfolio/            (classic layout, no project BRIEF)
    standalone-memo/
      BRIEF.md                  (per-thread BRIEF, no documents: key)
      standalone-memo.1/
        memo.md

  empty-documents-project/      (edge case, falls back to classic)
    BRIEF.md                    (frontmatter has documents: [] — empty list)
```

## What this fixture tests (issue #284 ACs)

The fixture is the regression anchor for the discovery primitive:

- `discover_thread_root(<path under brains-for-robots/<slug>/>)`
  returns `LAYOUT_PROJECT_BRIEF` with `project_root` = the
  `brains-for-robots/` directory.
- `discover_thread_root(<path under classic-portfolio/<thread>/>)`
  returns `LAYOUT_CLASSIC` with `project_root = None`.
- `has_project_brief(empty-documents-project/)` returns `False` (the
  empty list does NOT trigger the project-brief dispatch).

These cases are also exercised inline in `test_project_discovery.py`
against tmp-dir skeletons; the on-disk fixture exists so a future
sub-deliverable (2: BRIEF parser, 3: overlay selection) has a
canary-shaped tree it can extend without rebuilding the skeleton from
scratch.

## What this fixture does NOT contain

- No real research/comps content — the bodies are placeholder prose.
- No `_progress.json` / `_summary.md` / `_review.json` / review
  siblings — this is a **discovery fixture**, not a lifecycle
  fixture. The lifecycle commands do not yet consume the discovery
  utility (per issue #284's scope note: "commands do NOT yet consume
  this — integration lands in sub-deliverables 2 and 3").
- No `.anvil.json` files — those land with sub-deliverable 2 when the
  full BRIEF schema parser ships.
