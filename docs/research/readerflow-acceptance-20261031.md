# Reader-flow lens acceptance, clause 2 (issue #1396)

Measured 2026-10-31 at anvil `25bcafef2a500092512e0f89aeeed9dec4855061` (step 4j brief as shipped after #1438, extracted verbatim).
Trees: `rjwalters/geode-fem` @ `443a10ce`, `papers/<thread>/<thread>.<N>/`.

**Result: clause 2 NOT met.** On all three papers the cross-version R is not clearly below the same-version noise floor. #1396 stays open.

## Method

Per paper, four fresh-context subagent reads of the step 4j brief: A1, A2 on the pre-flow version, B1, B2 on the flow-revised version. Each saw only the brief, the version dir and the declared audience. R is `recurrence()` from `readerflow_recurrence.py` (#1419); `nit` findings are excluded from the prior total. Cross-version R is `recurrence(A1, B1)`. Noise floors are `recurrence(A1, A2)` and `recurrence(B1, B2)`.

Pass rule, fixed here: cross R is at least **0.05** below the lower noise floor. The margin was chosen after seeing the data (the issue only asked that it be stated), so read the raw numbers too.

## Results

| Paper (pre → revised) | Findings A1/A2/B1/B2 (maj+min+nit total) | Cross R A1→B1 | Floor A1→A2 | Floor B1→B2 | Pass |
|---|---|---|---|---|---|
| conformal-antenna-diffopt 11 → 12 | 27 / 26 / 34 / 36 | 0.292 (7/24) | 0.333 (8/24) | 0.444 (12/27) | no (0.041 under the lower floor, short of 0.05) |
| transmon-benchmark 22 → 23 | 32 / 50 / 28 / 26 | 0.400 (12/30) | 0.367 (11/30) | 0.440 (11/25) | no (above the floor) |
| motor-gradient-optimization 21 → 22 | 28 / 41 / 36 / 30 | 0.261 (6/23) | 0.348 (8/23) | 0.250 (9/36) | no (above the lower floor) |

Cross-checking with the second pair, `recurrence(A2, B2)`: antenna 0.273, transmon 0.180, motor 0.152. These sit below the floors, but A2 and B2 are the larger-count reads, and the spread between A1→B1 and A2→B2 (0.40 vs 0.18 on transmon) is as large as the effect being tested. The noise floor is wide, so the measure cannot separate revised from unrevised versions at this read count.

The operator's earlier source-mode R (0.284 / 0.403 / 0.400) agrees with the cross R here for antenna and transmon.

## Limitations

- **No PDF consulted.** `pdftotext`/`pdfinfo` are not installed on the dispatch host, so every read was source-only. The shipped brief's PDF step (classes 4 and 9, float placement) did not run; class 4 findings come from source order only. This is a deviation from the shipped flow, not a different brief.
- Two motor reads (B1, B2) stopped partway through the appendix tables; their finding lists do not cover the unread tail.
- One read per cell for the headline cross R; the A2→B2 pair is reported above as the spread, not averaged in.

## Clause 1

Met per the operator's 2026-10-31 07:20 comment on #1396: union of two fresh reads of the shipped (source-led) brief, merged by the #1419 matcher, scored 14 clean · 1 partial · 0 missed against the 15 external findings. The raw reads live with the operator's round artifacts, not in this repo, so they are not fixtured.

## Fixtures

`tests/skills/paper/fixtures/readerflow_acceptance/<paper>_{A1,A2,B1,B2}.json`, pinned by `tests/skills/paper/test_paper_readerflow_acceptance.py`.
