"""Snippet-content smoke tests for the ``.review/`` vs ``.audit/`` codification.

Per issue #29 acceptance criteria: cheap "grep-the-doc" tests that the
codified CRITIC tool-vs-judgment distinction stays in the framework
snippets and doesn't drift back to ambiguous prose in a later edit.

These tests assert on substring presence only — they do NOT validate
prose quality or structure.
"""

from __future__ import annotations

from pathlib import Path


SNIPPETS = Path(__file__).resolve().parents[2] / "anvil" / "lib" / "snippets"
LIB_README = Path(__file__).resolve().parents[2] / "anvil" / "lib" / "README.md"
SKILL_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "anvil" / "templates" / "SKILL.md"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# audit.md (new)
# ---------------------------------------------------------------------------


def test_audit_snippet_exists():
    assert (SNIPPETS / "audit.md").exists(), (
        "anvil/lib/snippets/audit.md MUST exist per issue #29 AC1"
    )


def test_audit_snippet_names_load_bearing_fields():
    body = _read(SNIPPETS / "audit.md")
    assert "tool_evidence" in body, (
        "audit.md MUST name 'tool_evidence' as a load-bearing field"
    )
    assert "tool_calls" in body, (
        "audit.md MUST name 'tool_calls' as a load-bearing field"
    )


def test_audit_snippet_documents_critical_flags():
    body = _read(SNIPPETS / "audit.md")
    assert "Critical-flag" in body or "Critical flag" in body, (
        "audit.md MUST contain a section heading for critical flags"
    )


def test_audit_snippet_has_skill_mapping_table():
    body = _read(SNIPPETS / "audit.md")
    # Five v0 skills ship audit commands; memo is the explicit non-shipper.
    for skill in ("memo", "pub", "report", "deck", "slides", "ip-uspto"):
        assert skill in body, (
            f"audit.md MUST mention skill '{skill}' in the audit-vs-review "
            f"mapping table"
        )


def test_audit_snippet_notes_no_memo_audit():
    body = _read(SNIPPETS / "audit.md")
    # Memo intentionally has no audit command in v0.
    assert "memo" in body
    # Either explicit "no" in the table or prose noting memo's audit slot
    # is reserved for consumer extension.
    assert any(
        marker in body
        for marker in ("no `memo-audit`", "no\n", "consumer extension", "| no |")
    ), "audit.md MUST note that memo ships no audit command"


def test_audit_snippet_cross_references_validator():
    body = _read(SNIPPETS / "audit.md")
    assert "review_schema.py" in body, (
        "audit.md MUST cross-reference the schema validator location"
    )


# ---------------------------------------------------------------------------
# state_machine.md
# ---------------------------------------------------------------------------


def test_state_machine_cross_references_audit_md():
    body = _read(SNIPPETS / "state_machine.md")
    assert "audit.md" in body, (
        "state_machine.md MUST cross-reference audit.md (issue #29 AC2)"
    )


def test_state_machine_attributes_audit_to_tool_evidence():
    body = _read(SNIPPETS / "state_machine.md")
    assert "tool_evidence" in body or "tool-evidence" in body, (
        "state_machine.md MUST attribute audit to tool-evidence verification"
    )


# ---------------------------------------------------------------------------
# critics.md
# ---------------------------------------------------------------------------


def test_critics_documents_tool_evidence_kind():
    body = _read(SNIPPETS / "critics.md")
    assert "tool_evidence" in body, (
        "critics.md MUST document kind: tool_evidence"
    )
    assert "tool_calls" in body, (
        "critics.md MUST document the tool_calls requirement"
    )


def test_critics_references_schema_validator():
    body = _read(SNIPPETS / "critics.md")
    assert "review_schema.py" in body, (
        "critics.md MUST cross-reference review_schema.py's validator"
    )


def test_critics_adding_new_critic_section_mentions_kind():
    body = _read(SNIPPETS / "critics.md")
    # The "Adding a new critic" section must mention picking the kind.
    adding_section_idx = body.find("Adding a new critic")
    assert adding_section_idx >= 0
    adding_section = body[adding_section_idx:]
    assert "kind" in adding_section, (
        "'Adding a new critic' section MUST mention the kind decision"
    )
    assert "tool_evidence" in adding_section


# ---------------------------------------------------------------------------
# rubric.md
# ---------------------------------------------------------------------------


def test_rubric_has_judgment_vs_tool_evidence_subsection():
    body = _read(SNIPPETS / "rubric.md")
    assert "Judgment dimensions vs tool-evidence dimensions" in body, (
        "rubric.md MUST contain the 'Judgment dimensions vs tool-evidence "
        "dimensions' subsection (issue #29 AC4)"
    )


def test_rubric_worked_examples_cover_pub_and_ip_uspto():
    body = _read(SNIPPETS / "rubric.md")
    section_idx = body.find("Judgment dimensions vs tool-evidence dimensions")
    assert section_idx >= 0
    section = body[section_idx:]
    assert "anvil:pub" in section or "`pub" in section or "pub-audit" in section
    assert (
        "anvil:ip-uspto" in section
        or "ip-uspto-audit" in section
        or "ip-uspto" in section
    )


# ---------------------------------------------------------------------------
# anvil/lib/README.md
# ---------------------------------------------------------------------------


def test_lib_readme_has_review_vs_audit_overview():
    body = _read(LIB_README)
    assert "Review vs audit" in body, (
        "anvil/lib/README.md MUST contain a 'Review vs audit' overview "
        "paragraph (issue #29 AC5)"
    )


def test_lib_readme_kind_field_mentions_audit_class():
    body = _read(LIB_README)
    # The expanded `kind` field description must say more than the old
    # "reserved for #29" placeholder.
    assert "tool_evidence" in body
    # Must point at the snippet.
    assert "snippets/audit.md" in body


# ---------------------------------------------------------------------------
# templates/SKILL.md
# ---------------------------------------------------------------------------


def test_skill_template_lifecycle_table_points_at_audit_snippet():
    body = _read(SKILL_TEMPLATE)
    # The `<type>-audit` row in the lifecycle table must cross-reference
    # the new snippet.
    assert "snippets/audit.md" in body, (
        "templates/SKILL.md MUST cross-reference snippets/audit.md from "
        "the audit lifecycle row (issue #29 AC6)"
    )


def test_skill_template_has_tool_evidence_example():
    body = _read(SKILL_TEMPLATE)
    # The minimal `_review.json` example block must show `kind: tool_evidence`
    # with `tool_calls`.
    assert '"kind": "tool_evidence"' in body, (
        "templates/SKILL.md MUST include a minimal _review.json example with "
        "kind: tool_evidence (issue #29 AC6)"
    )
    assert "tool_calls" in body
