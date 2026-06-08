# Fixtures: ip-uspto rubric version transition (issue #357, mirrors #346)

Six fixtures exercising the per-review rubric version stamping +
mixed-rubric-thread surfacing landed by issue #346 and applied to the
`ip-uspto` skill in issue #357.

**Distinct from the other 5 skills** (memo-mirror dim 9 *Rhetorical
economy*), ip-uspto takes a **skill-appropriate dim 9 *Claim-spec
correspondence*** at weight 5. The flat-weight design is preserved:
9 dimensions × 5 each = **/45 total**, threshold ≥39 (proportional
bump from ≥35/40).

Patent applications are the inverse of memos on bloat — fewer words
is often a §112(a) enablement failure, and "rhetorical economy" is
actively counterproductive. The natural ninth dim is the per-
limitation cross-walk a sophisticated examiner does first.

The fixtures use `scorecard_kind: "machine-summary"` (not
`human-verdict` like the other 5 skills) — the three rubric-stamping
fields are independent of `scorecard_kind` per
`snippets/scorecard_kind.md` §"The discriminator".

Consumed by
`tests/skills/ip-uspto/test_ip_uspto_rubric_version_transition_doc.py`.
