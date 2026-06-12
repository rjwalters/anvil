"""Doc-coverage smoke tests for the memo-review scope-tagging contract.

Per issue #242 acceptance criteria: cheap "grep-the-doc" regression guard
that the critic-side `scope: preserve | expand | reduce` tagging contract
stays documented in the four files it touches (rubric.md, memo-review.md,
SKILL.md, and this doc-AC test) and that the contract surfaces compose
coherently across the rubric prose and the command spec.

The contract codifies the critic-side counterweight to dim 9 *Rhetorical
economy* (#244 / PR #254): every `comments.md` entry carries a `scope`
label alongside its severity grouping; every dim 9 deduction's named
anti-pattern instance mechanically surfaces as a `scope: reduce` comment;
every `scope: expand` comment proposing ≥1 paragraph or ≥1 subsection must
name a trim candidate or downgrade from major to minor; `_summary.md`
carries a `scope_distribution` block; and `verdict.md`'s "Top 3 revision
priorities" includes a `scope: reduce` priority when dim 9 < 4/4.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The lifecycle commands themselves are
LLM-driven, so behavioural assertions belong in consumer-side integration
tests, not here. The contract under test is the **reviewer-prose
discipline** — the documented procedure prose, not a Python module
(per AC 7: no `anvil/lib/` schema changes ship in Phase A).

Per-skill test filename convention (#58): this file is named
``test_memo_review_scope_tagging_doc.py`` so pytest does not collide
with similarly-shaped doc-AC tests another skill might pick. The
``test_memo_review_`` prefix mirrors the existing
``test_memo_review_render_gate_wiring_doc.py`` (issue #196) pattern.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
RUBRIC_MD = SKILL_ROOT / "rubric.md"
REVIEW_MD = SKILL_ROOT / "commands" / "memo-review.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# rubric.md — §"Scope tagging (comments.md)" subsection ships the contract
# ---------------------------------------------------------------------------


def test_rubric_has_scope_tagging_section():
    """Issue #242 AC (file-touch list): rubric.md MUST add a §"Scope tagging"
    top-level subsection (sibling to §"Citation hooks (dim 3)" / §"Refs
    back-check (dim 3)" / §"Summary-detail consistency") defining the
    three-valued scope vocabulary."""
    body = _read(RUBRIC_MD)
    assert "## Scope tagging" in body, (
        "rubric.md MUST add a top-level §'Scope tagging' subsection — "
        "issue #242 AC file-touch list"
    )


def test_rubric_scope_tagging_names_three_values():
    """Issue #242 AC 1: the three-valued vocabulary `preserve | expand |
    reduce` is the contract; all three values MUST be named in rubric.md."""
    body = _read(RUBRIC_MD)
    start = body.find("## Scope tagging")
    assert start > -1
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    for value in ("scope: preserve", "scope: expand", "scope: reduce"):
        assert value in section, (
            f"rubric.md §'Scope tagging' MUST name the {value!r} value — "
            f"issue #242 AC 1 (three-valued vocabulary)"
        )


def test_rubric_dim_9_has_surfacing_subsection():
    """Issue #242 AC (file-touch list): rubric.md §"Dim 9 — rhetorical
    economy" MUST extend with a "Surfacing to comments.md" subsection
    codifying the rubric-side commitment (dim 9 deductions surface as
    `scope: reduce` comments)."""
    body = _read(RUBRIC_MD)
    # The Dim 9 section MUST carry a subsection (### header) about
    # surfacing — the rubric-side commitment to the echo rule.
    assert "## Dim 9" in body, (
        "rubric.md MUST still have a §'Dim 9' top-level section — issue "
        "#244 / PR #254 regression guard (dim 9 *Rhetorical economy*)"
    )
    # The subsection MUST reference comments.md surfacing.
    assert "Surfacing to `comments.md`" in body or "Surfacing to comments.md" in body, (
        "rubric.md §'Dim 9 — rhetorical economy' MUST add a "
        "'Surfacing to comments.md' subsection (issue #242 AC file-touch "
        "list)"
    )


def test_rubric_scope_tagging_documents_dim_9_echo_rule():
    """Issue #242 AC 2: the rubric MUST document the dim 9 echo rule
    (when dim 9 < 4/4, every cited anti-pattern instance MUST appear as
    a `scope: reduce` comment)."""
    body = _read(RUBRIC_MD)
    start = body.find("## Scope tagging")
    assert start > -1
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    # The dim 9 echo rule MUST be named.
    lowered = section.lower()
    assert "dim 9 echo" in lowered or "dim 9 echo rule" in lowered, (
        "rubric.md §'Scope tagging' MUST document the dim 9 echo rule by "
        "name — issue #242 AC 2"
    )
    # The conditional MUST be named: when dim 9 < 4/4.
    assert "4/4" in section or "< 4" in section or "full weight" in lowered, (
        "rubric.md §'Scope tagging' MUST anchor the echo rule to the "
        "dim 9 < 4/4 (sub-full-weight) condition — issue #242 AC 2"
    )


def test_rubric_scope_tagging_documents_expand_trim_candidate_rule():
    """Issue #242 AC 3: any `scope: expand` comment proposing ≥1 paragraph
    or ≥1 subsection MUST name a trim candidate; comments lacking the
    clause are downgraded from major to minor."""
    body = _read(RUBRIC_MD)
    start = body.find("## Scope tagging")
    assert start > -1
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    lowered = section.lower()
    # The trim-candidate rule MUST be named.
    assert "trim candidate" in lowered or "trim-candidate" in lowered, (
        "rubric.md §'Scope tagging' MUST name the trim-candidate rule — "
        "issue #242 AC 3"
    )
    # The downgrade rule (major → minor) MUST be documented.
    assert "downgrad" in lowered and "major" in lowered and "minor" in lowered, (
        "rubric.md §'Scope tagging' MUST document the major→minor "
        "downgrade for `scope: expand` comments lacking a trim "
        "candidate — issue #242 AC 3"
    )


def test_rubric_scope_tagging_documents_backwards_compat():
    """Issue #242 AC 6: legacy reviews without `scope` labels remain
    valid; the reviser falls back to severity-only when absent."""
    body = _read(RUBRIC_MD)
    start = body.find("## Scope tagging")
    assert start > -1
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    lowered = section.lower()
    # Backwards-compat MUST be named.
    assert "backwards-compat" in lowered or "backward-compat" in lowered, (
        "rubric.md §'Scope tagging' MUST document the backwards-compat "
        "contract — issue #242 AC 6"
    )
    # The fallback rule MUST be named: reviser falls back to severity-only
    # when scope is absent.
    assert "severity-only" in lowered or "severity only" in lowered or (
        "fall back" in lowered
    ) or ("falls back" in lowered), (
        "rubric.md §'Scope tagging' MUST document the reviser-side "
        "fallback to severity-only ordering when scope labels are "
        "absent (legacy review siblings) — issue #242 AC 6"
    )


def test_rubric_scope_tagging_documents_no_lib_schema_changes():
    """Issue #242 AC 7: the contract ships as reviewer-prose-only;
    `anvil/lib/` schema is untouched."""
    body = _read(RUBRIC_MD)
    # The Phase A framing — reviewer-prose-only, mirroring #245 — MUST
    # be visible somewhere in the file (typically in the §"Scope tagging"
    # section or its composition subsection).
    lowered = body.lower()
    assert "reviewer-prose" in lowered or "reviewer prose" in lowered, (
        "rubric.md MUST mention the reviewer-prose-only Phase A framing "
        "(no `anvil/lib/` schema changes) — issue #242 AC 7"
    )


# ---------------------------------------------------------------------------
# memo-review.md step 5 — dim 9 echo sub-step
# ---------------------------------------------------------------------------


def test_memo_review_step_5_documents_dim_9_scope_reduce_echo():
    """Issue #242 AC 2: memo-review.md step 5 (per-dim scoring) MUST be
    extended to require `scope: reduce` echo for every dim 9 deduction's
    named instance."""
    body = _read(REVIEW_MD)
    # Find step 5 — start near "Score each dimension".
    idx = body.find("Score each dimension")
    assert idx > -1, "memo-review.md MUST have a step 5 'Score each dimension'"
    # The dim 9 echo sub-step lives inside step 5 (or in its trailing prose).
    # It MUST reference both dim 9 and `scope: reduce`. Window sized to
    # cover step 5's sub-steps as they grow (widened 6000 → 8000 when the
    # #478 elision contract extended the quoted-evidence sub-step).
    nearby = body[idx : idx + 8000]
    assert "Dim 9" in nearby or "dim 9" in nearby, (
        "memo-review.md step 5 MUST reference dim 9 in the echo sub-step — "
        "issue #242 AC 2"
    )
    assert "scope: reduce" in nearby, (
        "memo-review.md step 5 MUST require `scope: reduce` echoes for "
        "dim 9 anti-pattern instances — issue #242 AC 2"
    )


# ---------------------------------------------------------------------------
# memo-review.md step 8 — line-level comments carry the scope label
# ---------------------------------------------------------------------------


def test_memo_review_step_8_documents_scope_label_shape():
    """Issue #242 AC 1: memo-review.md step 8 MUST document the
    per-comment `scope` label shape (alongside severity)."""
    body = _read(REVIEW_MD)
    # Find step 8 by the canonical step-8 framing.
    idx = body.find("Write line-level comments")
    assert idx > -1, (
        "memo-review.md MUST have a step 8 'Write line-level comments'"
    )
    nearby = body[idx : idx + 6000]
    # All three scope values MUST be named in the step 8 prose.
    for value in ("scope: preserve", "scope: expand", "scope: reduce"):
        assert value in nearby, (
            f"memo-review.md step 8 MUST document the {value!r} value "
            f"(issue #242 AC 1)"
        )


def test_memo_review_step_8_documents_dim_9_scope_reduce_echo():
    """Issue #242 AC 2: memo-review.md step 8 MUST document the dim 9
    `scope: reduce` echo requirement."""
    body = _read(REVIEW_MD)
    idx = body.find("Write line-level comments")
    assert idx > -1
    nearby = body[idx : idx + 6000]
    # Dim 9 echo requirement MUST appear in step 8.
    lowered = nearby.lower()
    assert "dim 9" in lowered and "echo" in lowered, (
        "memo-review.md step 8 MUST document the dim 9 → `scope: reduce` "
        "echo requirement — issue #242 AC 2"
    )


def test_memo_review_step_8_documents_expand_trim_candidate_rule():
    """Issue #242 AC 3: memo-review.md step 8 MUST document the
    `scope: expand` trim-candidate rule and the major→minor downgrade."""
    body = _read(REVIEW_MD)
    idx = body.find("Write line-level comments")
    assert idx > -1
    nearby = body[idx : idx + 6000]
    lowered = nearby.lower()
    # The trim-candidate rule MUST appear.
    assert "trim candidate" in lowered or "trim-candidate" in lowered, (
        "memo-review.md step 8 MUST document the trim-candidate rule "
        "for `scope: expand` comments — issue #242 AC 3"
    )
    # The downgrade rule MUST appear.
    assert "downgrad" in lowered and "major" in lowered and "minor" in lowered, (
        "memo-review.md step 8 MUST document the major→minor downgrade "
        "for `scope: expand` comments lacking a trim candidate — issue "
        "#242 AC 3"
    )


# ---------------------------------------------------------------------------
# memo-review.md step 9 — _summary.md.scope_distribution block
# ---------------------------------------------------------------------------


def test_memo_review_step_9_documents_scope_distribution_block():
    """Issue #242 AC 5: memo-review.md step 9 (_summary.md write) MUST
    document a top-level `scope_distribution` block (sibling to `lint`
    and `render_gate`)."""
    body = _read(REVIEW_MD)
    # The block MUST appear as a JSON key in the documented _summary.md
    # template.
    assert '"scope_distribution"' in body, (
        "memo-review.md step 9 MUST document a `scope_distribution` "
        "block in the _summary.md template — issue #242 AC 5"
    )


def test_memo_review_step_9_scope_distribution_names_three_keys():
    """Issue #242 AC 5: the `scope_distribution` block MUST report
    counts for `preserve`, `expand`, and `reduce`."""
    body = _read(REVIEW_MD)
    # Find the scope_distribution block region.
    idx = body.find('"scope_distribution"')
    assert idx > -1
    nearby = body[idx : idx + 1000]
    # All three keys MUST appear in the block shape.
    for key in ('"preserve"', '"expand"', '"reduce"'):
        assert key in nearby, (
            f"memo-review.md step 9 `scope_distribution` block MUST "
            f"document the {key!r} key — issue #242 AC 5"
        )


def test_memo_review_step_9_scope_distribution_is_top_level():
    """Issue #242 AC 5: the `scope_distribution` block lives at the top
    level of _summary.md (NOT nested under `lint`) per the schema-notes
    rationale (same placement as the summary-detail-consistency block at
    issue #245)."""
    body = _read(REVIEW_MD)
    # The doc MUST clarify the top-level placement vs nested-under-lint.
    idx = body.find("scope_distribution")
    assert idx > -1
    # Look around the block for the top-level framing prose.
    region_start = max(0, idx - 500)
    region_end = min(len(body), idx + 3000)
    region = body[region_start:region_end]
    lowered = region.lower()
    assert "top level" in lowered or "top-level" in lowered, (
        "memo-review.md step 9 MUST document the top-level placement of "
        "the `scope_distribution` block (NOT nested under `lint`) — "
        "issue #242 AC 5 schema-notes framing"
    )


# ---------------------------------------------------------------------------
# memo-review.md step 10 — `scope: reduce` first-priority rule
# ---------------------------------------------------------------------------


def test_memo_review_step_10_documents_scope_reduce_first_priority_rule():
    """Issue #242 AC 4: memo-review.md step 10 (verdict.md write) MUST
    require at least one `scope: reduce` revision priority when dim 9
    scored < 4/4."""
    body = _read(REVIEW_MD)
    # Find step 10 by the verdict.md write framing.
    idx = body.find("Write `verdict.md`")
    assert idx > -1, "memo-review.md MUST have a step 10 'Write `verdict.md`'"
    nearby = body[idx : idx + 6000]
    # The scope: reduce first-priority rule MUST be documented.
    assert "scope: reduce" in nearby, (
        "memo-review.md step 10 MUST document the `scope: reduce` "
        "first-priority rule — issue #242 AC 4"
    )
    # The conditional MUST be anchored to dim 9 < 4/4.
    assert "dim 9" in nearby.lower(), (
        "memo-review.md step 10 MUST anchor the `scope: reduce` "
        "first-priority rule to dim 9 — issue #242 AC 4"
    )
    assert "4/4" in nearby or "full weight" in nearby.lower() or "< 4" in nearby, (
        "memo-review.md step 10 MUST anchor the `scope: reduce` "
        "first-priority rule to the dim 9 < 4/4 condition — issue #242 "
        "AC 4"
    )


def test_memo_review_step_10_mirrors_existing_first_priority_precedents():
    """Issue #242 AC 4: the `scope: reduce` first-priority rule mirrors
    the existing critical-flag-driven first-priority precedents (lint
    error first priority at issue #146; CONTRADICTED first priority at
    issue #245). The doc SHOULD surface this precedent linkage so the
    intent is recoverable."""
    body = _read(REVIEW_MD)
    idx = body.find("Write `verdict.md`")
    assert idx > -1
    nearby = body[idx : idx + 6000]
    # The mirror framing MUST appear (either "mirror" / "precedent" /
    # reference to lint or summary-detail-consistency).
    lowered = nearby.lower()
    assert (
        "mirror" in lowered
        or "precedent" in lowered
        or "lint block" in lowered
        or "summary-detail" in lowered
    ), (
        "memo-review.md step 10 MUST cross-reference the existing "
        "first-priority precedents (lint, summary-detail-consistency) "
        "so the design intent is recoverable from the doc — issue #242 "
        "AC 4"
    )


# ---------------------------------------------------------------------------
# SKILL.md — short reference in the "Critics → reviser" framing
# ---------------------------------------------------------------------------


def test_skill_md_references_scope_tagging():
    """Issue #242 AC (file-touch list): SKILL.md MUST add a short
    reference to the scope-tagging contract pointing to rubric +
    command spec."""
    body = _read(SKILL_MD)
    # The short reference MUST name the contract.
    assert "scope tagging" in body.lower() or "scope: reduce" in body or (
        "scope: expand" in body
    ), (
        "SKILL.md MUST reference the scope-tagging contract (one "
        "paragraph; full contract lives in rubric + command spec) — "
        "issue #242 AC file-touch list"
    )


def test_skill_md_scope_tagging_paragraph_cites_rubric_and_command():
    """Issue #242 AC (file-touch list): the SKILL.md reference MUST
    point at the rubric subsection + command-spec step that carry the
    full contract."""
    body = _read(SKILL_MD)
    lowered = body.lower()
    # The SKILL.md paragraph MUST cite rubric.md (for the rubric-side
    # contract) AND commands/memo-review.md (for the command-side step).
    # The cross-reference is the load-bearing claim: SKILL.md is the
    # short summary; the full contract lives in the cited files.
    assert "rubric.md" in body, (
        "SKILL.md scope-tagging paragraph MUST cite rubric.md (the "
        "full contract) — issue #242 AC file-touch list"
    )
    assert "memo-review" in body, (
        "SKILL.md scope-tagging paragraph MUST cite "
        "commands/memo-review.md (the command-side procedure) — issue "
        "#242 AC file-touch list"
    )
    # The dim 9 composition MUST be visible — the contract's "why"
    # is the dim 9 countervailing pressure.
    assert "dim 9" in lowered, (
        "SKILL.md scope-tagging paragraph MUST cite dim 9 *Rhetorical "
        "economy* (the rubric-side counterweight the scope-tagging "
        "contract composes with) — issue #242 AC composition"
    )


# ---------------------------------------------------------------------------
# Composition guards — the contract composes with #241 and #244 / PR #254
# ---------------------------------------------------------------------------


def test_rubric_scope_tagging_documents_composition_with_241():
    """Issue #242 AC 8: composition with #241 (reviser additivity).
    When #241 ships, the reviser reads `scope: reduce` comments first,
    addresses them as compression directives, and only THEN consumes
    `scope: expand` comments at their declared severity. The rubric
    SHOULD surface this composition so the design intent is
    recoverable."""
    body = _read(RUBRIC_MD)
    start = body.find("## Scope tagging")
    assert start > -1
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    # The composition with #241 MUST be referenced.
    assert "#241" in section, (
        "rubric.md §'Scope tagging' MUST cite #241 (reviser additivity) "
        "in the composition subsection — issue #242 AC 8"
    )


def test_rubric_scope_tagging_documents_composition_with_244():
    """Issue #242 AC composition: dim 9 (issue #244 / PR #254) is the
    rubric-side countervailing pressure; scope-tagging is the
    comments-stream-side countervailing pressure. The two compose."""
    body = _read(RUBRIC_MD)
    start = body.find("## Scope tagging")
    assert start > -1
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    # Dim 9 / Rhetorical economy MUST appear in the composition prose.
    lowered = section.lower()
    assert "dim 9" in lowered and "rhetorical economy" in lowered, (
        "rubric.md §'Scope tagging' MUST cite dim 9 *Rhetorical "
        "economy* in the composition subsection — issue #242 AC "
        "composition with #244 / PR #254"
    )


# ---------------------------------------------------------------------------
# Verdict-logic regression guard — the scope-tagging contract does NOT
# change the existing advance aggregation (AC 7 reviewer-prose-only).
# ---------------------------------------------------------------------------


def test_verdict_logic_unchanged_by_scope_tagging():
    """Issue #242 AC 7: the scope-tagging contract is reviewer-prose-only
    and does NOT change the existing verdict aggregation. The advance
    formula at step 7 MUST remain byte-identical to its pre-#242 shape
    (the same shape PR #254 / issue #244 already documented for the /44
    rubric)."""
    body = _read(REVIEW_MD)
    # The verdict formula MUST remain unchanged in shape from issue
    # #244 / PR #254 (which set the threshold to ≥35).
    assert "advance = (total >= 35) AND (no critical flags) AND (lint.errors == 0)" in body, (
        "memo-review.md step 7 verdict logic MUST remain byte-identical "
        "to the post-#244 shape (the scope-tagging contract at #242 is "
        "reviewer-prose-only and does NOT change verdict aggregation) — "
        "issue #242 AC 7"
    )
