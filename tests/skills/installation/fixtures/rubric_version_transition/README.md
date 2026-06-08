# Fixtures: installation rubric version transition (issue #357, mirrors #346)

Six fixtures exercising the per-review rubric version stamping +
mixed-rubric-thread surfacing landed by issue #346 and applied to the
`installation` skill in issue #357 (the /40 → /44 migration with
dim 9 *Rhetorical economy*).

See `tests/skills/memo/fixtures/rubric_version_transition/README.md`
for the canonical pattern; this directory carries the
`anvil-installation-v1` / `anvil-installation-v2` analogues.

Consumed by
`tests/skills/installation/test_installation_rubric_version_transition_doc.py`.
