# Fixtures: report rubric version transition (issue #357, mirrors #346)

Six fixtures exercising the per-review rubric version stamping +
mixed-rubric-thread surfacing landed by issue #346 and applied to the
`report` skill in issue #357 (the /40 → /44 migration with dim 9
*Rhetorical economy*).

The report skill is customer-facing tier, so the threshold bumps
proportionally: ≥35/40 → ≥39/44 (≈ 35×44/40, rounded).

See `tests/skills/memo/fixtures/rubric_version_transition/README.md`
for the canonical pattern; this directory carries the
`anvil-report-v1` / `anvil-report-v2` analogues with threshold values
appropriate to the customer-facing tier.

Consumed by
`tests/skills/report/test_report_rubric_version_transition_doc.py`.
