# docs/

Working notes and research spikes that don't belong in a shipped skill or
in the top-level `ROADMAP.md` / `WORK_LOG.md` / `WORK_PLAN.md` trio. Nothing
here is load-bearing for runtime behavior — it's provenance for decisions
made elsewhere.

## Contents

- [`codex-skill-adapter.md`](codex-skill-adapter.md) — research spike for
  #1002 (parent epic #1000) verifying the Codex CLI's skill/plugin
  discovery contract (directory layout, `SKILL.md` frontmatter, manifest
  fields) against official docs and a live install. The spike informed the
  shipped adapter (#1000): `install-anvil.sh` writes
  `.agents/skills/anvil-<skill>/SKILL.md`.
- [`research/919-ai-humanizer-mining.md`](research/919-ai-humanizer-mining.md)
  — corpus-mining report for #919: surveys external AI-writing-detection /
  "de-slopping" rule catalogues against `anvil/lib/rhetoric_lint.py`'s
  `DEFAULT_RHETORIC_RULES`, informing follow-up rule additions.
- [`1198-claim-ledger-design.md`](1198-claim-ledger-design.md) — design
  decision record for #1198 (essay-review cross-version claim ledger):
  resolves the two open placement/relationship-to-`provenance.md`
  questions and is the rationale for the shipped ledger (PR #1317), and reviews what the
  killed `_convictions.md` primitive (#142/#225/#226/#227/#228) got
  wrong so the new design avoids the same structural defects.
- [`research/readerflow-acceptance-20261031.md`](research/readerflow-acceptance-20261031.md)
  — acceptance measurement for #1396 (reader-flow lens, clause 2): three
  geode-fem papers, four fresh-context reads each of the step 4j brief,
  comparing cross-version recurrence against the same-version noise floor.
  Result: clause 2 not met (cross-version R is not clearly below the floor on
  any paper); #1396 stays open.

Add new working notes as `docs/<topic>.md` or `docs/research/<issue>-<slug>.md`
and list them here so this directory stays reachable from the repo root.
