# Report review rubric

The reviewer scores a report against 8 weighted dimensions summing to **40**. The threshold to advance is **≥35/40** (the customer-facing tier; higher than the ≥32/40 used by `anvil:memo`). Any **critical flag** — set by either `report-review` or `report-audit` — short-circuits the verdict regardless of total score until addressed.

Customer-facing reports fail differently from internal memos: a typo in a memo is embarrassing; an unsupported claim or wrong number in a customer report is a liability. The rubric weighting reflects this — **evidence trail and finding sufficiency dominate** (12/40 = 30%); polish dimensions exist but are deliberately not the deciding factor.

## Dimensions

| # | Dimension | Weight | What it measures |
|---|---|---|---|
| 1 | **Executive summary clarity** | 7 | First (often only) page read by the recipient. Must stand alone: state findings + recommendations + caveats in <1 page. Disproportionate weight because in practice many recipients read no further. |
| 2 | **Finding sufficiency** | 7 | Each finding supported by named evidence; no orphaned claims. Customer reports fail here most: a finding that says "we observed X" without saying who observed it, where, when, or how is not a finding — it is an assertion. |
| 3 | **Recommendation actionability** | 5 | Recommendations have owner, scope, and a "what done looks like" — not vague "consider improving X". A recipient should be able to assign each recommendation to a person and close it later. |
| 4 | **Evidence trail / citation** | 6 | Every quantitative claim cites source (interview, document, measurement, dataset). Audit-checkable: the auditor sibling can mechanically walk the citation chain. Critical-flag offense if a quantitative claim has no source. |
| 5 | **Risk & limitation disclosure** | 4 | Scope boundaries, sample limits, assumptions stated explicitly. Protects both author and recipient. A report that omits its limits is a report that overclaims. |
| 6 | **Internal consistency** | 4 | Numbers in body match exec summary match tables match prior reports in this engagement. Common failure when reports go through multiple revisions; the auditor sibling explicitly checks this. |
| 7 | **Format / presentation quality** | 4 | Tables render, figures legible, pagination clean, headers/footers consistent, recipient-appropriate branding. Customer-visible — sloppy presentation undermines trust in the technical content. `report-review` enforces a deterministic existence + freshness gate on `report.pdf` (cap at 2/4 if missing or stale; see `commands/report-review.md` step 4c). |
| 8 | **Tone & audience calibration** | 3 | Written for the named recipient (from `_project.md`) — appropriate jargon level, no hedging-to-hide, no overselling. Lowest weight but non-zero: a technically correct report in the wrong tone still damages the engagement. |
| | **Total** | **40** | Advance threshold: ≥35 |

## Vision-owned dimensions (rendered-PDF critic)

The eight dimensions above are scored from the **markdown source** by `report-review` and `report-audit`. Dimension 7 (Format / presentation quality) names the right concern — "tables render, figures legible, pagination clean" — but a source-side critic can only *guess* at it: a well-formed markdown table can still overflow the page text block after pandoc lays it out, and a figure that looks fine in source can be illegible at the recipient's print scale.

The optional `report-vision` critic (`commands/report-vision.md`) closes that gap by scoring the **rendered `report.pdf`** with a vision-language model. It owns a separate four-dimension vision rubric (`anvil-report-vision-v1`), scored /5 each (/20 total), composed from the framework `VisionRubric` / `VisionDimension` primitives in `anvil/lib/vision.py`:

| Vision dim | Weight | What it catches |
|---|---|---|
| `figure_legibility` | 5 | Chart axis labels, legends, and annotations readable at the recipient's page/print scale. |
| `table_overflow` | 5 | Wide specification tables clipped at the right margin — the report's signature rendered defect; a dropped column the recipient never sees is load-bearing data loss. |
| `layout_artifacts` | 5 | Page-break / flow quality: orphaned headings, widow lines, figures or tables split across a page boundary, inconsistent running headers/footers. |
| `palette_adherence` | 5 | Embedded charts match the report theme palette (`assets/style.css`) rather than default matplotlib colors. |

These four vision dims appear in the aggregated scorecard alongside the eight main-rubric dimensions; the existing aggregator (`anvil/lib/critics.py::aggregate`) merges them via the same mean-of-non-null path with no schema or aggregation changes. The vision critic puts `null` on the eight main dims (it does not own them); `report-review` and `report-audit` put `null` on the four vision dims. The two source-side critics and the vision critic also contribute disjoint findings — source-side critics flag prose/structure/citation issues, `report-vision` flags rendered-only layout defects.

`report-vision` reuses the two framework critical-flag types (no new flag types): `rendered_overflow_unrecoverable` (a clipped table or split figure that loses a load-bearing value) and `mathtext_artifact_breaks_meaning` (a `$X` rendered as italic math where the dollar sign carries semantic weight). Either flag short-circuits the verdict to block, consistent with the critical-flag policy below.

A report can reach `AUDITED` without a vision pass, but a customer-facing report delivered without one has not been validated against rendered-only defects. The recommendation is to run `report-vision` before `report-promote`; a missing vision pass surfaces as a gap in the reviser's `changelog.md`. See `commands/report-vision.md` and `anvil/lib/vision.py` for the rubric definition.

## Scoring guidance

For each dimension, the reviewer assigns an integer between 0 and the dimension's weight. A short justification accompanies each score (1–3 sentences pointing to specific evidence in the report).

Suggested calibration:
- **Full weight** — meets the standard convincingly; a sophisticated recipient would have no substantive objection on this dimension.
- **~75% of weight** — meets the standard with a defensible gap or one specific weakness noted.
- **~50% of weight** — partial; multiple gaps or one significant weakness.
- **~25% of weight** — present but inadequate; major rework needed.
- **0** — absent or actively misleading.

For a customer-facing report, the ≥35 threshold means the report has at most ~12% of points missing — roughly equivalent to "one major weakness across the eight dimensions, or two minor weaknesses." This is a deliberately tight tolerance for material that will be delivered externally.

## Advance threshold

- **≥35/40** — advance to `READY` (subject to also having `pass: true` in the audit sibling). This skill's terminal pre-promotion state is `AUDITED` (which for this skill means both `.review/` advance AND `.audit/` pass).
- **<35/40** — block; revise.
- **Any critical flag set** (in either `.review/` or `.audit/`) — block regardless of total. The next revision must address the flagged issue specifically and the relevant critic must re-evaluate the flag before the threshold check applies.

## Critical flags

A critical flag is an issue severe enough that **a sophisticated recipient would lose confidence in the report**, regardless of how well other dimensions score. Set a flag whenever such an issue is identified — this list is illustrative, not exhaustive:

### Review-side flags (stylistic / structural)

- **Recommendation contradicts a finding** — the report recommends action X while one of its own findings makes X inadvisable. Indicates the report was assembled without internal review.
- **Named third party mischaracterized** — a person, vendor, or organization is described in a way they would dispute. High legal and reputational exposure.
- **Legal or compliance statement made without disclaimer** — the report asserts something with regulatory implications (privacy, security, accessibility, financial) without the standard "this is not legal advice / consult your counsel" framing.
- **Scope creep beyond engagement** — the report makes findings or recommendations on subjects outside the engagement scope declared in `_project.md`. Undermines the engagement contract.

### Audit-side flags (factual / evidence)

- **Unsupported quantitative claim** — a number, percentage, ratio, or count appears in the report with no source citation. Audit-checkable: the auditor walks every quantitative claim and flags any without a cited source.
- **Cited source does not support claim** — a citation exists but the cited document/interview/measurement does not actually contain what the report says it contains. Worse than an uncited claim because it is misleading.
- **Internal contradiction** — two parts of the report (body, exec summary, table, exhibit) disagree on a fact. The auditor must call this out by exact location.
- **Contradicts prior report in engagement** — the current report disagrees with a fact stated in a previously-delivered report from the same engagement (`prior_reports[]` in `_project.md`). The auditor must reconcile or explicitly note the change with cause.
- **Unreachable external citation** (`audit_unreachable_external_citation` / `CRITICAL_FLAG_AUDIT_UNREACHABLE_EXTERNAL_CITATION`) — any row in the auditor's `findings.md` with `Verified? = n/a` whose `Cited source` is an external URL (`http://` or `https://`, case-insensitive). An external citation the auditor could not fetch is operationally indistinguishable from a fabricated one; the recipient cannot tell the difference either. The reviser MUST either supply the cited source under `refs/` (so the auditor can verify) or remove the claim. **Carve-out:** narrative-claim `n/a` (uncited prose, `(none — uncited)`, `(internal)`, or any non-URL parenthesized literal) does NOT trigger this flag; uncited *quantitative* claims are caught by the separate **Unsupported quantitative claim** flag above (no overlap, no double-counting). An `n/a` against an in-tree `refs/<path>` reference is an auditor-mistake case (the auditor CAN read in-tree refs) and is out of scope for this flag — recommend the auditor re-run the verification.

The reviewer and auditor should each raise a flag for any other issue that, in their judgment, meets the standard above — these eight examples are starting points, not a closed set.

## Verdict format

### Review verdict (`<thread>.{N}.review/verdict.md`)

1. **Total score**: `XX / 40`.
2. **Decision**: `advance: true` or `advance: false`. (`advance: true` requires `total ≥ 35` AND `no unresolved critical flag`.)
3. **Critical flags** (if any): bullet list, each with one-paragraph justification.
4. **Dimension summary**: a markdown table of per-dimension scores (full detail lives in `scoring.md`).
5. **Top 3 revision priorities** (if `advance: false`): the highest-leverage changes the reviser should focus on.

### Audit verdict (`<thread>.{N}.audit/verdict.md`)

1. **Pass**: `pass: true` or `pass: false`.
2. **Findings count**: total findings logged + breakdown by severity (`blocker` / `major` / `minor`).
3. **Critical flags** (if any): bullet list, each with one-paragraph justification pointing to specific location in the report and the specific evidence (or absence thereof).
4. **Prior-report cross-check**: explicit confirmation that the auditor compared this report against each entry in `_project.md`'s `prior_reports[]`, with the result for each.
5. **Top revision priorities** (if `pass: false`): the specific factual fixes required.

The auditor's `findings.md` contains the per-claim audit log (claim, location, cited source, audit result). The auditor's `evidence.md` contains the citation traceability map (every cited source → which claims depend on it). Both are required outputs.

## Combined advance gate

For the thread to reach the `AUDITED` state (this skill's terminal pre-promotion state):

```
advance = review.advance == true
       AND audit.pass == true
       AND no unresolved critical flags in either sibling
```

If either sibling blocks, the thread stays in `REVIEWED+AUDITED` (with both verdicts written) and the operator runs `report-revise` to produce `<thread>.{N+1}/`, which is then re-reviewed and re-audited.

## Output layout

```
<thread>.{N}.review/
  verdict.md       Top-level decision (see above)
  scoring.md       Per-dimension score + justification
  comments.md      Line-level comments keyed to report.md
  _progress.json   { phases.review.state == done }

<thread>.{N}.audit/
  verdict.md       Pass/fail + critical flags + cross-check
  findings.md      Per-claim audit log
  evidence.md      Citation traceability map
  _progress.json   { phases.audit.state == done }
```

Both critic sibling dirs are **read-only once written**. Revisions consume them without modifying them.
