# Fixtures: slides rubric version transition (issue #357, mirrors #346)

Six fixtures exercising the per-review rubric version stamping +
mixed-rubric-thread surfacing landed by issue #346 and applied to the
`slides` skill in issue #357 (the /40 → /44 migration with dim 9
*Rhetorical economy* at the **talk level** — distinct from per-slide
density dim 4).

See `tests/skills/memo/fixtures/rubric_version_transition/README.md`
for the canonical pattern; this directory carries the
`anvil-slides-v1` / `anvil-slides-v2` analogues.

Consumed by
`tests/skills/slides/test_slides_rubric_version_transition_doc.py`.
