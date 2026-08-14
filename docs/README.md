# docs/

Working notes and research spikes that don't belong in a shipped skill or
in the top-level `ROADMAP.md` / `WORK_LOG.md` / `WORK_PLAN.md` trio. Nothing
here is load-bearing for runtime behavior — it's provenance for decisions
made elsewhere.

## Contents

- [`codex-skill-adapter.md`](codex-skill-adapter.md) — research spike for
  #1002 (parent epic #1000) verifying the Codex CLI's skill/plugin
  discovery contract (directory layout, `SKILL.md` frontmatter, manifest
  fields) against official docs and a live install, ahead of a
  Codex-adapter implementation phase.
- [`research/919-ai-humanizer-mining.md`](research/919-ai-humanizer-mining.md)
  — corpus-mining report for #919: surveys external AI-writing-detection /
  "de-slopping" rule catalogues against `anvil/lib/rhetoric_lint.py`'s
  `DEFAULT_RHETORIC_RULES`, informing follow-up rule additions.

Add new working notes as `docs/<topic>.md` or `docs/research/<issue>-<slug>.md`
and list them here so this directory stays reachable from the repo root.
