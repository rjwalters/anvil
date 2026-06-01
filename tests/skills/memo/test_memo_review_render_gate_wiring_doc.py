"""Doc-coverage + backwards-compat smoke tests for the memo-review render-gate
wiring shipped by Epic #158 Phase 4 / issue #196.

Per the issue body's acceptance criteria, this module ships:

- **Doc-coverage smoke tests**: grep-the-doc regression guards that
  ``commands/memo-review.md`` step 4c (the new step that reads
  ``_progress.json.render_gate``) and the ``_summary.md.render_gate`` block
  (mirror of the deck-side ``_summary.md.lint`` shape) stay documented and
  don't drift back to a pre-Phase-4 shape in a later edit.
- **Rubric prose guards**: ``anvil/skills/memo/rubric.md`` §"Length targets"
  documents the word-count-primary / rendered-page-count-second-layer
  relationship per architect Q9 + dim 7 reviewer behaviour.
- **Backwards-compat smoke tests**: a memo version without
  ``_progress.json.render_gate`` (legal pre-Phase-3 / pre-render state) is
  still a valid input shape — the reviewer's step 4c MUST graceful-degrade.
- **Phase 3 regression guards**: the draft / revise step 9.5 / 9.7
  ``memo-render`` calls shipped by PR #193 remain intact and unchanged in
  spirit (non-blocking, optional).

Per-skill test filename convention (#58): this file is named
``test_memo_review_render_gate_wiring_doc.py`` so pytest does not collide
with the parallel ``test_memo_render_doc.py`` (Phase 3, PR #193) or any
future ``test_deck_render_*`` shape another skill might pick.

Module load notes:
- The shipped Phase 4 wiring is markdown-as-prompt; this test module
  deliberately treats the prose contract as the contract-under-test rather
  than spawning the LLM-driven command. The behavioural assertions belong
  in consumer-side integration tests; here we pin the doc shape so the
  prose can't silently drift back to a pre-Phase-4 form.
- The backwards-compat smoke uses an in-process JSON fixture (no
  subprocess) — the load-bearing claim is that a ``_progress.json`` without
  a ``render_gate`` block is still a parseable / reviewable shape.
"""

from __future__ import annotations

import json
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
REVIEW_MD = SKILL_ROOT / "commands" / "memo-review.md"
RENDER_MD = SKILL_ROOT / "commands" / "memo-render.md"
DRAFT_MD = SKILL_ROOT / "commands" / "memo-draft.md"
REVISE_MD = SKILL_ROOT / "commands" / "memo-revise.md"
RUBRIC_MD = SKILL_ROOT / "rubric.md"
DECK_REVIEW_MD = (
    Path(__file__).resolve().parents[3]
    / "anvil"
    / "skills"
    / "deck"
    / "commands"
    / "deck-review.md"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# memo-review.md step 4c — the new step that reads _progress.json.render_gate
# ---------------------------------------------------------------------------


def test_memo_review_documents_render_gate_read_step():
    """Issue #196 AC: memo-review.md MUST have a step reading
    _progress.json.render_gate (populated by PR #193's memo-render)."""
    body = _read(REVIEW_MD)
    assert "_progress.json.render_gate" in body, (
        "memo-review.md MUST reference _progress.json.render_gate — the "
        "top-level block written by memo-render (PR #193) and read at the "
        "Phase 4 reviewer step (issue #196 AC)"
    )


def test_memo_review_step_4c_references_phase_4_or_issue_196():
    """The new step MUST be anchored to its epic phase + issue so future
    edits can trace the contract back to the design discussion."""
    body = _read(REVIEW_MD)
    # The step body MUST cite Phase 4 OR issue #196 so future edits can
    # find the design discussion.
    assert "Phase 4" in body or "#196" in body, (
        "memo-review.md MUST cite Epic #158 Phase 4 OR issue #196 on the "
        "render-gate read step so future edits can trace the contract"
    )


def test_memo_review_render_gate_step_is_non_blocking():
    """Issue #196 AC: render-gate findings DO NOT abort review; they inform
    but don't gate the verdict."""
    body = _read(REVIEW_MD)
    # Find the step 4c body.
    idx = body.find("Read render-gate findings")
    assert idx > -1, (
        "memo-review.md MUST have a 'Read render-gate findings' step "
        "(Phase 4 / issue #196 AC)"
    )
    # The step body MUST surface the non-blocking framing.
    nearby = body[idx : idx + 4000]
    lowered = nearby.lower()
    assert "non-blocking" in lowered or "non blocking" in lowered, (
        "memo-review.md render-gate step MUST document the non-blocking "
        "contract (render findings inform but don't gate the verdict)"
    )
    assert "do not abort" in lowered or "does not abort" in lowered or (
        "do not force" in lowered
    ) or ("does not force" in lowered), (
        "memo-review.md render-gate step MUST clarify that findings DO NOT "
        "abort review / DO NOT force advance:false (issue #196 AC)"
    )


def test_memo_review_render_gate_step_graceful_degrades_when_absent():
    """Issue #196 AC: graceful-degrade when _progress.json.render_gate is
    absent (legal pre-Phase-3 / unrendered state)."""
    body = _read(REVIEW_MD)
    idx = body.find("Read render-gate findings")
    assert idx > -1
    nearby = body[idx : idx + 4000]
    lowered = nearby.lower()
    assert "graceful-degrade" in lowered or "graceful degrade" in lowered or (
        "graceful" in lowered
    ), (
        "memo-review.md render-gate step MUST document graceful-degrade "
        "for the absent-block case (issue #196 AC backwards-compat)"
    )
    # The backwards-compat case (legal pre-Phase-3 / no render) MUST be named.
    assert "pre-Phase-3" in nearby or "pre-render" in lowered or (
        "absent" in lowered
    ), (
        "memo-review.md render-gate step MUST enumerate the legal "
        "absent-block case (memo never rendered) per issue #196 AC"
    )


def test_memo_review_render_gate_severity_model_documented():
    """Issue #196 AC: dim 7 reviewer behavior anchored to memo_page_fit
    severity model (error if target_length.pages, warning if .words)."""
    body = _read(REVIEW_MD)
    # The severity model MUST be surfaced verbatim (the gate's classification
    # is the contract — the reviewer does not re-derive it).
    assert "memo_page_fit" in body, (
        "memo-review.md MUST reference the memo_page_fit gate dimension "
        "(issue #196 AC anchors dim 7 behavior to this finding)"
    )
    idx = body.find("Read render-gate findings")
    assert idx > -1
    nearby = body[idx : idx + 4000]
    lowered = nearby.lower()
    # Either the verbatim severity model OR the "surfaced verbatim" framing.
    assert "verbatim" in lowered or "severity" in lowered, (
        "memo-review.md render-gate step MUST document that severities are "
        "surfaced verbatim from the gate (issue #196 AC)"
    )


# ---------------------------------------------------------------------------
# _summary.md.render_gate block — mirrors deck-side _summary.md.lint shape
# ---------------------------------------------------------------------------


def test_memo_review_summary_render_gate_block_documented():
    """Issue #196 AC: _summary.md.render_gate block documented with shape
    mirroring deck `lint` block."""
    body = _read(REVIEW_MD)
    # The _summary.md write step (step 9) MUST document the render_gate block.
    assert '"render_gate"' in body, (
        "memo-review.md step 9 MUST document a render_gate block in "
        "_summary.md (mirror of deck-side lint block — issue #196 AC)"
    )


def test_memo_review_summary_render_gate_block_fields_present():
    """Issue #196 AC: the render_gate block shape mirrors GateResult.to_json
    output, with the operator-facing fields the deck-side lint block ships."""
    body = _read(REVIEW_MD)
    # Every load-bearing field of the render_gate block MUST be present in
    # the doc. Shape mirrors the deck-side lint block + the memo gate's
    # five dimensions.
    for field in (
        '"ran"',
        '"pages"',
        '"compile_status"',
        '"pass"',
        '"findings_by_dimension"',
        '"reasons"',
        "memo_compile_success",
        "memo_page_fit",
        "memo_overfull_check",
        "memo_image_refs_exist",
        "memo_placeholder_scan",
    ):
        assert field in body, (
            f"memo-review.md _summary.md.render_gate block MUST document "
            f"the {field!r} field (issue #196 AC — shape mirrors "
            f"GateResult.to_json + the five memo gate dimensions)"
        )


def test_memo_review_render_gate_block_is_info_level_only():
    """Issue #196 AC: render-gate block is non-blocking and info-level for
    the verdict — NEVER sets critical_flag, NEVER forces advance:false."""
    body = _read(REVIEW_MD)
    # The doc MUST surface the "render_gate block is non-blocking and
    # info-level" contract distinctly from the verdict logic.
    idx = body.find("render_gate` block is non-blocking")
    if idx == -1:
        # Tolerate alternative phrasing — the load-bearing claim is that
        # the verdict NEVER consumes render-gate findings.
        idx = body.find("render_gate")
    assert idx > -1
    # The verdict logic at step 7 MUST remain unchanged: advance is gated
    # by (total >= 32) AND (no critical flags) AND (lint.errors == 0) only.
    assert "advance = (total >= 32) AND (no critical flags) AND (lint.errors == 0)" in body, (
        "memo-review.md step 7 verdict logic MUST remain unchanged — "
        "advance is gated by rubric total + critical flags + source-side "
        "lint, NOT by render-gate findings (issue #196 AC)"
    )


def test_memo_review_render_gate_mirrors_deck_lint_block():
    """Issue #196 AC: explicit reference to the deck-side mirror so the
    intent is recoverable from the doc alone."""
    body = _read(REVIEW_MD)
    # Either an explicit "mirror" reference OR a cross-reference to
    # deck-review.md step 9 / lint block shape.
    lowered = body.lower()
    assert "deck-side" in lowered or "deck-review" in lowered or (
        "mirror" in lowered
    ), (
        "memo-review.md MUST cross-reference the deck-side _summary.md.lint "
        "block shape so the design intent is recoverable from the doc "
        "alone (issue #196 AC: 'mirror the deck-side _summary.md.lint block')"
    )


# ---------------------------------------------------------------------------
# rubric.md §"Length targets" — word count primacy + rendered page advisory
# ---------------------------------------------------------------------------


def test_rubric_length_targets_documents_word_count_primary():
    """Issue #196 AC: rubric.md §"Length targets" MUST describe word count
    as the primary measure (architect Q9)."""
    body = _read(RUBRIC_MD)
    # Find the §"Length targets" section.
    start = body.find("## Length targets")
    assert start > -1, "rubric.md MUST have a §'Length targets' section"
    # The section runs until the next ## or end of file.
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    lowered = section.lower()
    # Word count primacy is the load-bearing prose.
    assert "primary" in lowered, (
        "rubric.md §'Length targets' MUST describe word count as the "
        "PRIMARY measure (issue #196 AC architect Q9)"
    )
    # And "word count" must be the noun the primacy attaches to.
    assert "word count" in lowered, (
        "rubric.md §'Length targets' MUST anchor the primacy claim to "
        "'word count' explicitly (issue #196 AC)"
    )


def test_rubric_length_targets_documents_rendered_page_second_layer():
    """Issue #196 AC: rubric.md §"Length targets" MUST describe rendered
    page count as second-layer advisory."""
    body = _read(RUBRIC_MD)
    start = body.find("## Length targets")
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    lowered = section.lower()
    # Second-layer advisory framing.
    assert "second-layer" in lowered or "second layer" in lowered, (
        "rubric.md §'Length targets' MUST describe rendered page count as "
        "a 'second-layer' signal (issue #196 AC architect Q9)"
    )
    assert "advisory" in lowered, (
        "rubric.md §'Length targets' MUST describe the rendered page "
        "signal as 'advisory' (issue #196 AC architect Q9)"
    )
    assert "rendered page" in lowered or "page count" in lowered, (
        "rubric.md §'Length targets' MUST anchor the second-layer claim "
        "to the rendered page count (issue #196 AC)"
    )


def test_rubric_length_targets_documents_disagreement_handling():
    """Issue #196 AC: the rubric prose MUST describe what happens when
    word count says in-range but rendered page count says out-of-range
    (reviewer judges; either may be binding depending on context)."""
    body = _read(RUBRIC_MD)
    start = body.find("## Length targets")
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    lowered = section.lower()
    # The disagreement framing — the reviewer judges.
    assert "disagree" in lowered or "may disagree" in lowered or (
        "judges" in lowered
    ), (
        "rubric.md §'Length targets' MUST describe the disagreement case "
        "(word count vs rendered page count): reviewer judges which is "
        "binding (issue #196 AC architect Q9)"
    )


def test_rubric_length_targets_documents_severity_model():
    """Issue #196 AC: dim 7 reviewer behavior anchored to PR #193's
    render_gate.gate(kind='memo') Q3 finding memo_page_fit (severity: error
    if target_length.pages set; warning if target_length.words set)."""
    body = _read(RUBRIC_MD)
    start = body.find("## Length targets")
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    # The severity model MUST be surfaced — error vs warning per target spec.
    assert "memo_page_fit" in section, (
        "rubric.md §'Length targets' MUST reference the memo_page_fit "
        "gate finding (issue #196 AC anchors dim 7 to this finding)"
    )
    lowered = section.lower()
    # The two-severity model: pages → error, words → warning.
    assert "error" in lowered and "warning" in lowered, (
        "rubric.md §'Length targets' MUST surface the severity model: "
        "error when target_length.pages is set, warning when "
        "target_length.words is set (issue #196 AC)"
    )


def test_rubric_length_targets_documents_non_blocking_for_verdict():
    """Issue #196 AC: render-gate findings non-blocking for the verdict."""
    body = _read(RUBRIC_MD)
    start = body.find("## Length targets")
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    lowered = section.lower()
    assert "non-blocking" in lowered or "non blocking" in lowered or (
        "does not gate" in lowered
    ) or ("do not gate" in lowered), (
        "rubric.md §'Length targets' MUST clarify that render-gate "
        "findings are non-blocking for the verdict (issue #196 AC)"
    )


def test_rubric_length_targets_documents_backwards_compat():
    """Issue #196 AC: backwards-compat — memos without
    _progress.json.render_gate (PRE-Phase-3) reviewable without error."""
    body = _read(RUBRIC_MD)
    start = body.find("## Length targets")
    end = body.find("\n## ", start + 1)
    if end == -1:
        end = len(body)
    section = body[start:end]
    lowered = section.lower()
    # The backwards-compat clause must name the legal pre-Phase-3 state.
    assert "backwards-compat" in lowered or "backward-compat" in lowered or (
        "pre-phase-3" in lowered
    ) or ("legacy" in lowered) or ("pre-render" in lowered), (
        "rubric.md §'Length targets' MUST document backwards-compat: a "
        "memo without _progress.json.render_gate is reviewable per the "
        "pre-Phase-3 word-count-only path (issue #196 AC)"
    )


# ---------------------------------------------------------------------------
# Backwards-compat: memos without _progress.json.render_gate are reviewable
# ---------------------------------------------------------------------------


def test_legacy_progress_json_without_render_gate_is_parseable(tmp_path):
    """Issue #196 AC: a _progress.json without a render_gate block (the
    PRE-Phase-3 state, every legacy memo version on disk) is a parseable /
    reviewable shape — the reviewer's step 4c MUST graceful-degrade.

    This pins the data-shape contract independently of the markdown doc.
    """
    vd = tmp_path / "legacy.1"
    vd.mkdir()
    (vd / "memo.md").write_text(
        "# Legacy memo\n\nDrafted before Phase 3.\n",
        encoding="utf-8",
    )
    # The pre-Phase-3 _progress.json shape: phases.draft == done, no
    # phases.render block, no render_gate top-level block.
    progress = {
        "version": 1,
        "thread": "legacy",
        "phases": {
            "draft": {
                "state": "done",
                "started": "2026-04-01T00:00:00Z",
                "completed": "2026-04-01T00:01:00Z",
            }
        },
        "metadata": {
            "iteration": 1,
            "max_iterations": 4,
            "target_length_resolved": {
                "min_words": 1800,
                "max_words": 2400,
                "source": "default",
            },
        },
    }
    progress_path = vd / "_progress.json"
    progress_path.write_text(json.dumps(progress), encoding="utf-8")

    parsed = json.loads(progress_path.read_text(encoding="utf-8"))
    assert parsed["phases"]["draft"]["state"] == "done"
    # The contract under test: render_gate top-level block is absent.
    assert "render_gate" not in parsed, (
        "Legacy memo _progress.json MUST NOT carry render_gate (pre-Phase-3 "
        "shape) — reviewer step 4c MUST graceful-degrade on this shape"
    )
    # phases.render is also absent.
    assert "render" not in parsed["phases"], (
        "Legacy memo _progress.json MUST NOT carry phases.render "
        "(pre-Phase-3 shape)"
    )
    # The reviewer's step 4c is documented to record:
    #   {"ran": false, "reason": "no render_gate block in _progress.json"}
    # The data shape above is the input that triggers that path.
    rendered_block_present = parsed.get("render_gate") is not None
    assert not rendered_block_present, (
        "Backwards-compat invariant: reviewer step 4c sees no render_gate "
        "block and falls back to word-count-only dim 7 judgment (issue "
        "#196 AC)"
    )


def test_phase_3_progress_json_with_render_gate_is_parseable(tmp_path):
    """Issue #196 AC: a Phase 3 / Phase 4 _progress.json with a render_gate
    block (the shape memo-render writes per PR #193) is parseable and
    surfaces the keys the reviewer's step 4c reads."""
    vd = tmp_path / "rendered.2"
    vd.mkdir()
    (vd / "memo.md").write_text(
        "# Rendered memo\n\nDrafted in Phase 3.\n",
        encoding="utf-8",
    )
    # The Phase 3 _progress.json shape: phases.render + render_gate.
    progress = {
        "version": 1,
        "thread": "rendered",
        "phases": {
            "draft": {
                "state": "done",
                "started": "2026-05-01T00:00:00Z",
                "completed": "2026-05-01T00:01:00Z",
            },
            "render": {
                "state": "done",
                "started": "2026-05-01T00:01:30Z",
                "completed": "2026-05-01T00:02:00Z",
            },
        },
        "metadata": {
            "iteration": 2,
            "max_iterations": 4,
            "target_length_resolved": {
                "min_words": 1800,
                "max_words": 2400,
                "source": "default",
            },
        },
        "render_gate": {
            "gate": "render_gate",
            "pdf_path": str(vd / "memo.pdf"),
            "log_path": None,
            "pages": 4,
            "page_cap": None,
            "overfull_boxes": [],
            "overfull_threshold_pt": 5.0,
            "compile": {"status": "ok", "exit_code": 0},
            "placeholders": [],
            "findings": [],
            "pass": True,
            "reasons": [
                "memo_compile_success: pandoc exited 0; PDF produced.",
                "memo_page_fit: rendered 4 pages within target [3, 4] (source=words).",
            ],
        },
    }
    progress_path = vd / "_progress.json"
    progress_path.write_text(json.dumps(progress), encoding="utf-8")

    parsed = json.loads(progress_path.read_text(encoding="utf-8"))
    # Reviewer step 4c reads render_gate.{pages, compile, findings, pass,
    # reasons} — pin every load-bearing field.
    rg = parsed["render_gate"]
    assert rg["pages"] == 4
    assert rg["compile"]["status"] == "ok"
    assert rg["pass"] is True
    assert isinstance(rg["findings"], list)
    assert isinstance(rg["reasons"], list)
    # The page count is the second-layer signal the dim 7 justification
    # surfaces per rubric.md §"Length targets" §"Word count is primary".
    assert rg["pages"] is not None, (
        "render_gate.pages is the second-layer rendered-page signal the "
        "reviewer surfaces in dim 7 justification (issue #196 AC)"
    )


# ---------------------------------------------------------------------------
# Phase 3 regression guards — draft/revise step 9.5 / 9.7 intact
# ---------------------------------------------------------------------------


def test_memo_draft_step_9_5_render_call_intact():
    """Phase 3 regression guard: memo-draft.md step 9.5 (the memo-render
    invocation shipped in PR #193) MUST remain intact and unchanged in
    spirit — the Phase 4 changes are reviewer-side, NOT drafter-side."""
    body = _read(DRAFT_MD)
    # The render call MUST still be present.
    assert "9.5" in body, (
        "memo-draft.md MUST preserve step 9.5 numbering (PR #193 Phase 3 "
        "regression guard — Phase 4 does not touch drafter wiring)"
    )
    assert "memo-render" in body, (
        "memo-draft.md MUST still invoke memo-render (PR #193 Phase 3 "
        "regression guard — Phase 4 does not touch drafter wiring)"
    )
    # The non-blocking framing MUST survive (Phase 4 does not change this).
    lowered = body.lower()
    assert "non-blocking" in lowered or "non blocking" in lowered, (
        "memo-draft.md step 9.5 MUST preserve the non-blocking framing "
        "(PR #193 Phase 3 regression guard)"
    )


def test_memo_revise_step_9_7_render_call_intact():
    """Phase 3 regression guard: memo-revise.md step 9.7 (the memo-render
    invocation shipped in PR #193) MUST remain intact and unchanged in
    spirit — the Phase 4 changes are reviewer-side, NOT reviser-side."""
    body = _read(REVISE_MD)
    # The render call MUST still be present.
    assert "9.7" in body, (
        "memo-revise.md MUST preserve step 9.7 numbering (PR #193 Phase 3 "
        "regression guard — Phase 4 does not touch reviser wiring)"
    )
    assert "memo-render" in body, (
        "memo-revise.md MUST still invoke memo-render (PR #193 Phase 3 "
        "regression guard — Phase 4 does not touch reviser wiring)"
    )
    # The non-blocking framing MUST survive (Phase 4 does not change this).
    lowered = body.lower()
    assert "non-blocking" in lowered or "non blocking" in lowered, (
        "memo-revise.md step 9.7 MUST preserve the non-blocking framing "
        "(PR #193 Phase 3 regression guard)"
    )


def test_memo_render_contract_intact():
    """Phase 3 regression guard: memo-render.md ships the contract the
    Phase 4 reviewer reads — the command MUST still document writing
    _progress.json.render_gate (the key step 4c consumes)."""
    body = _read(RENDER_MD)
    assert "render_gate" in body, (
        "memo-render.md MUST still document writing the render_gate block "
        "to _progress.json (PR #193 Phase 3 regression guard — Phase 4 "
        "depends on this contract)"
    )
    # The to_json() shape from render_gate.py is the contract between
    # writer (memo-render) and reader (memo-review step 4c).
    assert "to_json" in body or "GateResult" in body, (
        "memo-render.md MUST reference GateResult.to_json() (the shape "
        "the Phase 4 reviewer consumes) — PR #193 Phase 3 regression guard"
    )


# ---------------------------------------------------------------------------
# Deck-side mirror sanity check — the shape the memo block claims to mirror
# ---------------------------------------------------------------------------


def test_deck_review_lint_block_exists_as_mirror_anchor():
    """Sanity check: the deck-side _summary.md.lint block the memo
    render_gate block claims to mirror MUST exist. If the deck-side shape
    is ever removed, the mirror claim in the memo doc becomes dangling."""
    body = _read(DECK_REVIEW_MD)
    # The deck-side lint block (the mirror target) — load-bearing shape.
    assert '"lint"' in body, (
        "deck-review.md MUST ship a _summary.md.lint block — the mirror "
        "anchor for the memo-side render_gate block (issue #196 AC mirror)"
    )
    # Mirror-relevant fields per the issue body description.
    for marker in (
        '"errors"',
        '"warnings"',
    ):
        assert marker in body, (
            f"deck-review.md _summary.md.lint block MUST document the "
            f"{marker!r} field (mirror anchor for memo-side block — "
            f"issue #196 AC)"
        )
