"""Doc-coverage tests for the proposal `cost_basis` knob (issue #840).

Not every buildable-system proposal is a hardware system with a
vendor-sourceable BOM — a partnership/integration proposal (a
data-backed challenge to another company) has no hardware BOM and no
vendor quotes at all. Issue #840 adds a `cost_basis` frontmatter key
(`quoted` / `estimated` / `none`; default `quoted`) that:

1. Gates `templates/proposal.tex.j2` section 7's priced-table contract.
2. Calibrates `rubric.md` dim 6 (Cost credibility) scoring.
3. Gates `proposal-audit`'s vendor-quote sourceability walk (step 7).
4. Is documented on `proposal-draft.md`'s recognized frontmatter keys
   and `templates/BRIEF.md.example`.

This implementation surface spans six files; this test pins the
doc-coverage so future drift is caught early, mirroring the sibling
`test_proposal_recommendation_target_doc.py` (issue #356) pattern.

Per the #58 packaging convention, this filename
(`test_proposal_cost_basis_doc.py`) is unique across `tests/skills/*/`.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.testing import read_text as _read

# tests/skills/proposal → anvil/skills/proposal
SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "proposal"
RUBRIC = SKILL_ROOT / "rubric.md"
REVIEW_COMMAND = SKILL_ROOT / "commands" / "proposal-review.md"
DRAFT_COMMAND = SKILL_ROOT / "commands" / "proposal-draft.md"
AUDIT_COMMAND = SKILL_ROOT / "commands" / "proposal-audit.md"
PROJECT_BRIEF = SKILL_ROOT / "lib" / "project_brief.py"
BRIEF_TEMPLATE = SKILL_ROOT / "templates" / "BRIEF.md.example"
TEX_TEMPLATE = SKILL_ROOT / "templates" / "proposal.tex.j2"


# ---------------------------------------------------------------------------
# rubric.md — new §"Dim 6 — cost_basis calibration"
# ---------------------------------------------------------------------------


def test_rubric_documents_cost_basis_section() -> None:
    """The rubric MUST have a section dedicated to the dim 6 cost_basis calibration."""
    body = _read(RUBRIC)
    assert (
        "Dim 6 — `cost_basis` calibration" in body
        or "Dim 6 — cost_basis calibration" in body
    ), (
        "rubric.md MUST have a `## Dim 6 — `cost_basis` calibration` "
        "section documenting the new calibration (issue #840)"
    )


def test_rubric_documents_three_way_closed_set() -> None:
    """The section MUST document all three closed-set values."""
    body = _read(RUBRIC)
    for value in ("`quoted`", "`estimated`", "`none`"):
        assert value in body, (
            f"rubric.md MUST document the {value} cost_basis value "
            f"(issue #840 closed set)"
        )


def test_rubric_documents_estimate_basis_consistency_language() -> None:
    """The section MUST describe estimate-basis-consistency scoring for `estimated`."""
    body = _read(RUBRIC)
    assert "estimate-basis consistency" in body, (
        "rubric.md MUST document that `cost_basis: estimated` routes dim 6 "
        "scoring to estimate-basis consistency, not vendor sourceability "
        "(issue #840 acceptance criteria)"
    )


def test_rubric_documents_none_drops_sourceability_requirement() -> None:
    """The section MUST state that unsourced claims are not penalized under `none`/`estimated`."""
    body = _read(RUBRIC)
    assert "NOT" in body and "sourceability defect" in body, (
        "rubric.md MUST explicitly state an unsourced estimate is not scored "
        "as a sourceability defect under the estimated/none calibration "
        "(issue #840 acceptance criteria)"
    )


def test_rubric_documents_suffix_shape() -> None:
    """The section MUST document the verbatim suffixes for the audit trail."""
    body = _read(RUBRIC)
    assert (
        "cost_basis: estimated — scoring dim 6 on estimate-basis consistency, "
        "not vendor sourceability" in body
    ), (
        "rubric.md MUST document the verbatim `estimated` suffix appended to "
        "dim 6's scoring.md justification (issue #840)"
    )
    assert "cost_basis: none — no hardware BOM" in body, (
        "rubric.md MUST document the verbatim `none` suffix appended to "
        "dim 6's scoring.md justification (issue #840)"
    )


def test_rubric_documents_backwards_compat() -> None:
    """The section MUST document the byte-identical-when-quoted-or-absent contract."""
    body = _read(RUBRIC)
    assert "byte-identical" in body.lower(), (
        "rubric.md MUST document that the calibration is byte-identical "
        "when the trigger value is absent or `quoted` (issue #840 "
        "backwards-compat AC)"
    )


def test_rubric_documents_orthogonality_to_customer_kind() -> None:
    """The section MUST document that cost_basis is orthogonal to customer_kind."""
    body = _read(RUBRIC)
    assert "orthogonal" in body.lower(), (
        "rubric.md MUST document that `cost_basis` is orthogonal to "
        "`customer_kind` — the missing axis this issue closes (issue #840)"
    )


# ---------------------------------------------------------------------------
# proposal-review.md — step 4k (load) + step 5 sub-step (apply) + _summary.md
# ---------------------------------------------------------------------------


def test_proposal_review_references_load_cost_basis() -> None:
    """proposal-review.md MUST reference the new load_cost_basis helper."""
    body = _read(REVIEW_COMMAND)
    assert "load_cost_basis" in body, (
        "proposal-review.md MUST reference `load_cost_basis` so the "
        "reviewer agent knows to call the helper when reading inputs "
        "(issue #840 acceptance criteria)"
    )


def test_proposal_review_describes_dim_6_calibration_sub_step() -> None:
    """proposal-review.md MUST describe the dim 6 sub-step that applies the calibration."""
    body = _read(REVIEW_COMMAND)
    assert "cost_basis_resolved" in body, (
        "proposal-review.md MUST cache the resolved value as "
        "`cost_basis_resolved` and reference it in the dim 6 scoring "
        "sub-step + the `_summary.md` write (issue #840)"
    )
    assert "Dim 6" in body or "dim 6" in body.lower(), (
        "proposal-review.md MUST name dim 6 as the calibrated dimension "
        "(issue #840)"
    )


def test_proposal_review_summary_md_block_documented() -> None:
    """The `_summary.md.cost_basis_resolved` block MUST be in the spec."""
    body = _read(REVIEW_COMMAND)
    assert '"cost_basis_resolved"' in body, (
        "proposal-review.md step 9b MUST show the `cost_basis_resolved` "
        "block in the `_summary.md` example (issue #840 audit-trail AC)"
    )


# ---------------------------------------------------------------------------
# proposal-draft.md — recognized-keys list + priced-table dispatch
# ---------------------------------------------------------------------------


def test_proposal_draft_documents_cost_basis_key() -> None:
    """proposal-draft.md MUST recognize cost_basis as a frontmatter key."""
    body = _read(DRAFT_COMMAND)
    assert "cost_basis" in body, (
        "proposal-draft.md MUST list `cost_basis` as a recognized "
        "frontmatter key on the proposal thread-level BRIEF (issue #840)"
    )


# ---------------------------------------------------------------------------
# proposal-audit.md — step 7 gating
# ---------------------------------------------------------------------------


def test_proposal_audit_gates_sourceability_walk_on_cost_basis() -> None:
    """proposal-audit.md step 7 MUST gate the vendor-quote walk on cost_basis."""
    body = _read(AUDIT_COMMAND)
    assert "load_cost_basis" in body, (
        "proposal-audit.md MUST reference `load_cost_basis` (issue #840)"
    )
    assert "cost_basis_resolved" in body, (
        "proposal-audit.md MUST cache the resolved value as "
        "`cost_basis_resolved` and dispatch step 7 on it (issue #840)"
    )
    assert "skipped" in body.lower(), (
        "proposal-audit.md MUST document that the vendor-quote back-check "
        "is SKIPPED when cost_basis is `none` (issue #840 acceptance "
        "criteria)"
    )


# ---------------------------------------------------------------------------
# Helper export — project_brief.py exposes load_cost_basis
# ---------------------------------------------------------------------------


def test_project_brief_exports_load_cost_basis() -> None:
    """The helper MUST be exported from project_brief.py via __all__."""
    body = _read(PROJECT_BRIEF)
    assert "def load_cost_basis" in body, (
        "project_brief.py MUST define `load_cost_basis` (issue #840)"
    )
    assert '"load_cost_basis"' in body, (
        "project_brief.py's `__all__` MUST include `load_cost_basis` "
        "(issue #840)"
    )


def test_project_brief_documents_closed_set() -> None:
    """The helper MUST document the closed set of recognized values."""
    body = _read(PROJECT_BRIEF)
    for value in ("quoted", "estimated", "none"):
        assert value in body, (
            f"project_brief.py MUST recognize {value!r} as one of the "
            f"closed-set values for cost_basis (issue #840)"
        )


def test_project_brief_stays_skill_local() -> None:
    """The helper MUST stay skill-local; promotion to anvil/lib/ is deferred."""
    assert PROJECT_BRIEF.exists(), (
        "the proposal-local project_brief.py MUST live at "
        f"{PROJECT_BRIEF} (skill-local-first per CLAUDE.md)"
    )


# ---------------------------------------------------------------------------
# Template — the shipped BRIEF.md.example demonstrates the default
# ---------------------------------------------------------------------------


def test_brief_template_demonstrates_quoted_default() -> None:
    """The shipped BRIEF.md.example MUST carry the quoted default."""
    body = _read(BRIEF_TEMPLATE)
    assert "cost_basis: quoted" in body, (
        "BRIEF.md.example MUST demonstrate `cost_basis: quoted` as the "
        "documented, byte-identical-compatible default (issue #840)"
    )


# ---------------------------------------------------------------------------
# proposal.tex.j2 — priced-table contract gated on cost_basis_resolved
# ---------------------------------------------------------------------------


def test_tex_template_gates_section_7_on_cost_basis() -> None:
    """proposal.tex.j2 MUST branch section 7 on cost_basis_resolved."""
    body = _read(TEX_TEMPLATE)
    assert "cost_basis_resolved" in body, (
        "proposal.tex.j2 MUST set/branch on `cost_basis_resolved` "
        "(issue #840)"
    )
    assert 'cost_basis | default("quoted")' in body, (
        "proposal.tex.j2 MUST default `cost_basis` to `quoted` "
        "(issue #840 backward compatibility)"
    )
    assert "Cost Basis" in body, (
        "proposal.tex.j2 MUST emit a lighter 'Cost Basis' section when "
        "`cost_basis: none` drops the priced-table requirement "
        "(issue #840)"
    )
