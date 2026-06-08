# Fixtures: rubric version transition (issue #346)

Three fixtures exercising the per-review rubric version stamping +
mixed-rubric-thread surfacing landed by issue #346:

- **`progress_iter1_legacy.json`** — a `_progress.json.metadata.score_history`
  with a single iteration 1 row in the legacy pre-#346 shape (no
  `rubric_id` field). Readers must tolerate the absence.
- **`progress_iter2_stamped.json`** — a `_progress.json.metadata.score_history`
  spanning two iterations: iter 1 with `rubric_id: "anvil-memo-v1-legacy-40"`
  (a stamped /40 review), iter 2 with `rubric_id: "anvil-memo-v2"`
  (a stamped /44 review). Threshold bumped 32 → 35; total range bumped
  /40 → /44.
- **`meta_legacy.json`** + **`meta_stamped_v1.json`** + **`meta_stamped_v2.json`**
  — minimal `_meta.json` fixtures exercising the three reader states
  (legacy/no `rubric_id`, stamped v1 /40, stamped v2 /44). The reader
  contract derives `prior_rubric_inferred: "/40-legacy"` for the legacy
  case.
- **`summary_with_rubric_block.json`** — a `_summary.md`-shaped JSON
  carrying the new top-level `rubric` block with `prior_rubric_id` and
  `prior_rubric_inferred` fields.

These fixtures are consumed by `test_memo_rubric_version_transition.py`
in this directory's parent and pin the schema-of-record contract
documented in `anvil/lib/snippets/scorecard_kind.md` §"Rubric version
stamping fields" + `anvil/lib/snippets/progress.md` §"Convergence
fields → score_history" + `anvil/skills/memo/commands/memo-review.md`
step 3 / step 9 / step 9b.
