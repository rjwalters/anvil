"""Snippet-content smoke tests for the perspective sibling codification.

Per issue #148 acceptance criteria: cheap "grep-the-doc" tests that the
perspective-sibling contract stays in the framework snippet and doesn't
drift in a later edit. Phase 1B (#149, deck-perspective) and Phase 1C
(#150, deck-market cross-check) BOTH reference this snippet — keeping
the contract points stable is load-bearing.

These tests assert on substring presence only — they do NOT validate
prose quality or structure.
"""

from __future__ import annotations

from pathlib import Path


SNIPPETS = Path(__file__).resolve().parents[2] / "anvil" / "lib" / "snippets"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# perspective.md (new in #148)
# ---------------------------------------------------------------------------


def test_perspective_snippet_exists():
    assert (SNIPPETS / "perspective.md").exists(), (
        "anvil/lib/snippets/perspective.md MUST exist per issue #148"
    )


def test_perspective_snippet_documents_layout():
    body = _read(SNIPPETS / "perspective.md")
    # Layout contract: <thread>.{N}.perspective/ sibling dir.
    assert "<thread>.{N}.perspective/" in body or (
        "<thread>.0.perspective/" in body
        and "<thread>.{N}.perspective/" in body
    ), "perspective.md MUST document the sibling-dir layout pattern"
    # Holds notes / candidate list / meta / progress per the spec.
    assert "notes.md" in body
    assert "_meta.json" in body
    assert "_progress.json" in body


def test_perspective_snippet_documents_non_gating():
    body = _read(SNIPPETS / "perspective.md")
    # State-machine non-gating: absence does NOT block draft/review/revise.
    assert "non-gating" in body or "non gating" in body, (
        "perspective.md MUST contain a 'non-gating' section heading or marker"
    )
    assert "does NOT block" in body or "does not block" in body, (
        "perspective.md MUST state that absence does NOT block the state machine"
    )


def test_perspective_snippet_documents_no_fabrication():
    body = _read(SNIPPETS / "perspective.md")
    assert "No-fabrication" in body or "no-fabrication" in body or (
        "No fabrication" in body
    ), "perspective.md MUST have a no-fabrication rule section"
    # Candidate entries MUST include source URLs / citation pointers.
    assert "source pointer" in body or "source URL" in body or "URL" in body
    assert "MUST" in body, (
        "perspective.md MUST use normative MUST language around no-fabrication"
    )


def test_perspective_snippet_names_three_consumer_classes():
    body = _read(SNIPPETS / "perspective.md")
    # Consumers: drafter, per-skill cross-check critics, *-audit provenance check.
    assert "rafter" in body, "perspective.md MUST name the drafter consumer"
    assert "cross-check" in body or "cross check" in body, (
        "perspective.md MUST name the cross-check critic consumer"
    )
    assert "audit" in body, (
        "perspective.md MUST name the audit-provenance consumer"
    )


def test_perspective_snippet_documents_rerun_pattern():
    body = _read(SNIPPETS / "perspective.md")
    assert "Re-run" in body or "re-run" in body, (
        "perspective.md MUST document the re-run pattern"
    )
    # Re-run is per-version, picking up a new sibling at <thread>.{N}.perspective/.
    assert "<thread>.{N}.perspective/" in body


def test_perspective_snippet_reaffirms_subprocess_only():
    body = _read(SNIPPETS / "perspective.md")
    # Subprocess-only-by-default: anvil does NOT mandate a fetcher.
    assert "ubprocess-only" in body or "ubprocess only" in body, (
        "perspective.md MUST reaffirm the subprocess-only-by-default posture"
    )
    assert "fetcher" in body, (
        "perspective.md MUST explicitly address fetcher mandate (and decline it)"
    )
    assert "not mandate" in body or "does NOT mandate" in body or (
        "does not mandate" in body
    ), "perspective.md MUST state that anvil does NOT mandate a fetcher"


def test_perspective_snippet_documents_naming_rationale():
    body = _read(SNIPPETS / "perspective.md")
    # Naming: "perspective" NOT "research".
    assert "perspective" in body
    assert "research" in body, (
        "perspective.md MUST explicitly contrast 'perspective' against 'research'"
    )
    # The disambiguation argument from anvil:pub's domain.
    assert "anvil:pub" in body or "pub" in body, (
        "perspective.md MUST cite anvil:pub's 'research papers' domain "
        "as the disambiguation driver"
    )


def test_perspective_snippet_cites_pub_litsearch_as_precedent():
    body = _read(SNIPPETS / "perspective.md")
    assert "pub-litsearch" in body, (
        "perspective.md MUST cite pub-litsearch.md as the load-bearing "
        "existing precedent"
    )


def test_perspective_snippet_has_see_also_section():
    body = _read(SNIPPETS / "perspective.md")
    assert "See also" in body, (
        "perspective.md MUST have a 'See also' section per snippet convention"
    )
    # Cross-references to the established snippets in the family.
    assert "critics.md" in body
    assert "version_layout.md" in body
    assert "progress.md" in body


def test_perspective_snippet_not_in_default_critic_sets():
    """Perspective is non-gating; it MUST NOT appear in critics.md's
    skill-side default critic set table as a required critic."""
    critics_body = _read(SNIPPETS / "critics.md")
    # The default critic set table lists required critics per skill. Per the
    # perspective contract, none of these rows should require perspective.
    # We check the loose property: 'perspective' does NOT appear in any
    # default-set row of the table. The snippet's contract section explicitly
    # forbids the addition.
    #
    # This test is a forward-guard: if a later PR mistakenly adds perspective
    # as required, the test fails and surfaces the contract violation.
    table_start = critics_body.find("Default critic set")
    assert table_start >= 0
    # The table ends at the next blank-line-separated section heading.
    table_end = critics_body.find("\n## ", table_start)
    table_section = critics_body[table_start:table_end if table_end > 0 else None]
    assert "perspective" not in table_section, (
        "perspective MUST NOT appear in critics.md's default-critic-set "
        "table — it is non-gating by design (issue #148)"
    )
