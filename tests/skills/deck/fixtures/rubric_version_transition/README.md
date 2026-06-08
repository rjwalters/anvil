# Fixtures: deck rubric version transition (issue #357, mirrors #346)

Six fixtures exercising the per-review rubric version stamping +
mixed-rubric-thread surfacing landed by issue #346 and applied to the
`deck` skill in issue #357 (the /40 → /44 migration with dim 9
*Rhetorical economy*).

The deck skill is customer-facing tier — threshold bumps
proportionally: ≥35/40 → ≥39/44 (≈ 35×44/40, rounded). Dim 9
ownership is assigned to `deck-narrative` (the arc/ask critic), per
the curator's decision matrix.

This PR only stamps the aggregator (`deck-review`); the four
specialist critics (`deck-narrative`, `deck-market`, `deck-design`,
`deck-vision`) inherit the rubric_id when their command files ship
follow-up stamping in a separate issue.

See `tests/skills/memo/fixtures/rubric_version_transition/README.md`
for the canonical pattern; this directory carries the
`anvil-deck-v1` / `anvil-deck-v2` analogues with the customer-facing
thresholds (35→39).

Consumed by
`tests/skills/deck/test_deck_rubric_version_transition_doc.py`.
