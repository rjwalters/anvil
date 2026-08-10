"""Tests for `anvil:deslop`'s deterministic no-fabrication gate (issue #922).

Covers the acceptance criteria named in the issue: a clean revision (no
new facts) passes silently; a revision that invents a number/name/
citation is flagged; a revision that pulls a specific detail from a
resolved voice-grounding doc is NOT flagged. Also covers the shared
`rhetoric_lint` scan exclusions (fenced code / HTML comments / inline
code) and the `anvil-lint-disable` escape hatch for explicit
operator-supplied detail.
"""

from __future__ import annotations

from _deslop_skill_lib import fabrication_gate as fg


# ---------------------------------------------------------------------------
# Clean revision: no new facts -> no findings
# ---------------------------------------------------------------------------


def test_clean_revision_with_no_new_facts_passes_silently() -> None:
    prior = "Acme Corp raised $50M in Q1. See [1] for details.\n"
    new = "Acme Corp closed a $50M round. See [1] for details.\n"

    result = fg.check_no_fabrication(prior, new)

    assert result.findings == []
    assert result.total == 0


def test_identical_revision_has_no_findings() -> None:
    body = "The Acme Corporation shipped 42 widgets last quarter.\n"
    result = fg.check_no_fabrication(body, body)
    assert result.findings == []


# ---------------------------------------------------------------------------
# Invented numerals / proper nouns / citations are flagged
# ---------------------------------------------------------------------------


def test_invented_numeral_is_flagged() -> None:
    prior = "Our product helps teams ship faster.\n"
    new = "Our product helped teams cut cycle time by $2.5M last year.\n"

    result = fg.check_no_fabrication(prior, new)

    tokens = {f.token for f in result.findings}
    kinds = {f.kind for f in result.findings}
    assert "$2.5M" in tokens
    assert fg.KIND_NUMERAL in kinds
    assert all(f.severity == "warning" for f in result.findings)


def test_invented_proper_noun_is_flagged() -> None:
    prior = "Our product helps teams ship faster.\n"
    new = "Our product is trusted by Acme Corporation and their partners.\n"

    result = fg.check_no_fabrication(prior, new)

    matches = [f for f in result.findings if f.kind == fg.KIND_PROPER_NOUN]
    assert any(f.token == "Acme Corporation" for f in matches)


def test_invented_citation_is_flagged() -> None:
    prior = "Our product helps teams ship faster.\n"
    new = 'Our product helps teams ship faster, per "an internal survey".\n'

    result = fg.check_no_fabrication(prior, new)

    matches = [f for f in result.findings if f.kind == fg.KIND_CITATION]
    assert any(f.token == '"an internal survey"' for f in matches)


def test_a_single_capitalized_word_is_not_flagged_as_proper_noun() -> None:
    # Sentence-initial capitalization alone must not fire — only 2+
    # consecutive Title-Case words count as a proper-noun-shaped token
    # (issue #922 acceptance criterion).
    prior = "Teams move faster with less process.\n"
    new = "Teams move faster. Speed compounds across every sprint.\n"

    result = fg.check_no_fabrication(prior, new)

    assert not any(f.kind == fg.KIND_PROPER_NOUN for f in result.findings)


# ---------------------------------------------------------------------------
# Voice-grounding docs: legitimate specificity is NOT flagged
# ---------------------------------------------------------------------------


def test_detail_sourced_from_voice_grounding_doc_is_not_flagged() -> None:
    prior = "Our product helps teams ship faster.\n"
    new = "Our product helped Acme Corporation cut cycle time by $2.5M.\n"
    voice_doc = "# Corpus excerpt\n\nAcme Corporation is our flagship case study, worth $2.5M in savings.\n"

    result = fg.check_no_fabrication(prior, new, known_texts=[voice_doc])

    assert result.findings == []


def test_voice_doc_only_covers_the_tokens_it_actually_carries() -> None:
    prior = "Our product helps teams ship faster.\n"
    new = "Our product helped Acme Corporation cut cycle time by $2.5M.\n"
    # The voice doc only mentions the company, not the dollar figure.
    voice_doc = "# Corpus excerpt\n\nAcme Corporation is our flagship case study.\n"

    result = fg.check_no_fabrication(prior, new, known_texts=[voice_doc])

    tokens = {f.token for f in result.findings}
    assert "$2.5M" in tokens
    assert "Acme Corporation" not in tokens


# ---------------------------------------------------------------------------
# Scan exclusions mirror rhetoric_lint (fenced code / HTML comments / inline code)
# ---------------------------------------------------------------------------


def test_numeral_inside_fenced_code_block_is_not_flagged() -> None:
    prior = "Our product ships fast.\n"
    new = "Our product ships fast.\n\n```\nconst LIMIT = 500000;\n```\n"

    result = fg.check_no_fabrication(prior, new)

    assert result.findings == []


def test_numeral_inside_html_comment_is_not_flagged() -> None:
    prior = "Our product ships fast.\n"
    new = "Our product ships fast.\n<!-- internal note: target is $500000 -->\n"

    result = fg.check_no_fabrication(prior, new)

    assert result.findings == []


def test_numeral_inside_inline_code_span_is_not_flagged() -> None:
    prior = "Our product ships fast.\n"
    new = "Our product ships fast, configured via `MAX_RETRIES=500000`.\n"

    result = fg.check_no_fabrication(prior, new)

    assert result.findings == []


# ---------------------------------------------------------------------------
# anvil-lint-disable escape hatch (explicit operator-supplied detail)
# ---------------------------------------------------------------------------


def test_lint_disable_directive_downgrades_finding_to_info() -> None:
    prior = "Our product ships fast.\n"
    new = (
        "Our product ships fast.\n"
        "Revenue grew to $2.5M last year. "
        "<!-- anvil-lint-disable: deslop_no_fabrication -->\n"
    )

    result = fg.check_no_fabrication(prior, new)

    assert result.warnings == []
    assert len(result.infos) == 1
    assert result.infos[0].token == "$2.5M"
    assert "suppressed" in result.infos[0].message


def test_lint_disable_on_standalone_line_above_suppresses_next_line() -> None:
    prior = "Our product ships fast.\n"
    new = (
        "Our product ships fast.\n"
        "<!-- anvil-lint-disable: deslop_no_fabrication -->\n"
        "Revenue grew to $2.5M last year.\n"
    )

    result = fg.check_no_fabrication(prior, new)

    assert result.warnings == []
    assert len(result.infos) == 1
    assert result.infos[0].token == "$2.5M"


def test_lint_disable_for_a_different_rule_does_not_suppress() -> None:
    prior = "Our product ships fast.\n"
    new = (
        "Our product ships fast.\n"
        "Revenue grew to $2.5M last year. "
        "<!-- anvil-lint-disable: some-other-rule -->\n"
    )

    result = fg.check_no_fabrication(prior, new)

    assert len(result.warnings) == 1
    assert result.warnings[0].token == "$2.5M"


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


def test_to_json_shape() -> None:
    prior = "Our product ships fast.\n"
    new = "Our product ships fast. Revenue grew to $2.5M.\n"

    result = fg.check_no_fabrication(prior, new)
    payload = result.to_json()

    assert payload["gate"] == "fabrication_gate"
    assert payload["rule"] == fg.RULE_ID
    assert payload["warnings"] == 1
    assert payload["infos"] == 0
    assert len(payload["findings"]) == 1
    assert payload["findings"][0]["token"] == "$2.5M"
