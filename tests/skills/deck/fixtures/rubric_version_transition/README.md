# Fixtures: deck rubric version transition (issues #357 + #550, mirrors #346)

Fixtures exercising the per-review rubric version stamping +
mixed-rubric-thread surfacing landed by issue #346 and applied to the
`deck` skill in two migrations:

- **#357** (the /40 → /44 migration with dim 9 *Rhetorical economy*).
- **#550** (the /44 → /49 migration with dim 10 *Business-model &
  unit-economics credibility*).

The deck skill is customer-facing tier — threshold bumps
proportionally: ≥35/40 → ≥39/44 (≈ 35×44/40, rounded) → ≥43/49 (≈
39×49/44, rounded down — same threshold-rounding convention #357
set). Dim 9 ownership is assigned to `deck-narrative` (the arc/ask
critic); dim 10 ownership is assigned to `deck-review` as fallback
(sibling #551 will introduce `deck-economics` and reassign primary
ownership).

This PR only stamps the aggregator (`deck-review`); the four
specialist critics (`deck-narrative`, `deck-market`, `deck-design`,
`deck-vision`) inherit the rubric_id when their command files ship
follow-up stamping in a separate issue.

## Fixture inventory

- `meta_legacy.json` — legacy pre-#346 review meta (no rubric_id stamped).
- `meta_stamped_v1.json` — v1 /40 stamped (`anvil-deck-v1-legacy-40`).
- `meta_stamped_v2.json` — v2 /44 stamped (`anvil-deck-v2`, post-#357).
- `meta_stamped_v3.json` — v3 /49 stamped (`anvil-deck-v3`, post-#550).
- `progress_iter1_legacy.json` — single-row score_history without
  rubric_id (legacy pre-#346 row).
- `progress_iter2_stamped.json` — two-row score_history exercising
  the v1 → v2 transition.
- `summary_with_rubric_block.json` — v2 `_summary.md` `rubric` block
  with `prior_rubric_id: null` + `prior_rubric_inferred: "/40-legacy"`
  (legacy → v2 transition).
- `summary_with_rubric_block_v3.json` — v3 `_summary.md` `rubric`
  block with `prior_rubric_id: "anvil-deck-v2"` (v2 → v3 transition,
  post-#550).

The `_v2` siblings are preserved (not replaced) so the existing
/40-legacy → /44 transition tests still pass — per-review stamping
means downstream consumers route on the stamp, not the current
rubric, and the legacy /44 + /40 fixtures continue to serve any
backwards-compat path.

See `tests/skills/memo/fixtures/rubric_version_transition/README.md`
for the canonical pattern.

Consumed by
`tests/skills/deck/test_deck_rubric_version_transition_doc.py`.
