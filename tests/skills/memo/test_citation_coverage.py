"""Tests for ``anvil/skills/memo/lib/citation_coverage.py`` (Epic #328 Phase 3).

Per-skill test filename convention (#58): this file is named
``test_citation_coverage.py`` and lives under ``tests/skills/memo/``; the
``tests/skills/memo/__init__.py`` chain prevents collision with any sibling
skill that ships a same-named detector test in the future.

The fixture suite locks in the conservative false-positive discipline
documented in the citation_coverage module: every detector class has at
least one positive case AND one false-positive case. The two coordinates
of the conservative posture (version-context suppression, self-reference
suppression, hedge suppression, quoted suppression) each have a dedicated
test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib.critics import aggregate, discover_critics, load_review
from anvil.lib.review_schema import Kind, Review
from anvil.skills.memo.lib.citation_coverage import (
    CRITIC_ID,
    CRITICAL_FLAG_TYPE,
    CRITICAL_UNHOOKED_THRESHOLD,
    BrokenCitation,
    CoverageResult,
    UnhookedClaim,
    collect_refs_keys,
    scan,
    scan_version_dir,
)


# ---------------------------------------------------------------------------
# Module surface guards
# ---------------------------------------------------------------------------


def test_critic_id_is_citations():
    """The critic-id constant matches the sibling-dir tag convention."""
    assert CRITIC_ID == "citations"


def test_critical_flag_type_matches_issue_body():
    """The critical-flag type matches the issue body's suggested name."""
    assert CRITICAL_FLAG_TYPE == "critical_unsourced_load_bearing_claim"


def test_critical_threshold_defaults_to_five():
    """The unhooked-claim count threshold defaults to >5 per issue suggestion."""
    assert CRITICAL_UNHOOKED_THRESHOLD == 5


def test_coverage_result_total_findings():
    """``total_findings`` sums unhooked + broken."""
    r = CoverageResult(
        unhooked_claims=[
            UnhookedClaim(
                claim_class="numeric",
                text="$2.3B",
                line=1,
                rationale="",
                suggested_fix="",
            )
        ],
        broken_citations=[
            BrokenCitation(
                key="ghost",
                style="latex",
                line=2,
                closest_match=None,
                suggested_fix="",
            )
        ],
    )
    assert r.total_findings == 2


def test_coverage_result_emits_tool_evidence_review():
    """``to_review`` yields a ``kind=tool_evidence`` review that validates."""
    r = CoverageResult(
        unhooked_claims=[
            UnhookedClaim(
                claim_class="numeric",
                text="$2.3B",
                line=1,
                rationale="rationale",
                suggested_fix="fix",
            )
        ],
        body_path="memo.md",
    )
    review = r.to_review(version_dir="memo.1")
    assert isinstance(review, Review)
    assert review.kind == Kind.TOOL_EVIDENCE
    assert review.critic_id == "citations"
    assert len(review.scores) == 1
    # The single null-scored row owns no rubric dim.
    assert review.scores[0].score is None
    # Every finding must carry tool_calls=[] when kind=tool_evidence.
    for f in review.findings:
        assert f.tool_calls == []


# ---------------------------------------------------------------------------
# Positive cases — claims that SHOULD fire as unhooked
# ---------------------------------------------------------------------------


def test_positive_unhooked_numeric_money_claim():
    """A bare ``$2.3B`` with no citation marker on the line fires."""
    body = "The market is $2.3B and growing.\n"
    result = scan(body, refs_keys=set())
    assert any(
        c.claim_class == "numeric" and "$2.3B" in c.text
        for c in result.unhooked_claims
    )


def test_positive_unhooked_numeric_percent_claim():
    """``42 %`` with no citation marker fires."""
    body = "Conversion landed at 42 % across the cohort.\n"
    result = scan(body, refs_keys=set())
    assert any(
        c.claim_class == "numeric" and "42" in c.text and "%" in c.text
        for c in result.unhooked_claims
    )


def test_positive_unhooked_named_author_paren_claim():
    """``Smith (2023) showed`` with no citation fires + flags named-author."""
    body = "Smith (2023) showed that the effect persists.\n"
    result = scan(body, refs_keys=set())
    named_author = [
        c for c in result.unhooked_claims if c.claim_class == "named_author"
    ]
    assert len(named_author) >= 1
    assert "Smith" in named_author[0].text and "2023" in named_author[0].text


def test_positive_unhooked_named_author_possessive_claim():
    """``Karpathy's 2024 talk`` fires as named-author."""
    body = "Per Karpathy's 2024 talk on transformers, the trend holds.\n"
    result = scan(body, refs_keys=set())
    assert any(
        c.claim_class == "named_author" for c in result.unhooked_claims
    )


def test_positive_unhooked_date_pinned_event():
    """``On March 5, 2025,`` fires as a date-pinned event."""
    body = "On March 5, 2025, the company filed its S-1.\n"
    result = scan(body, refs_keys=set())
    assert any(
        c.claim_class == "date_pinned" for c in result.unhooked_claims
    )


def test_positive_unhooked_quantitative_summary():
    """``we found that …`` fires as a quantitative summary claim."""
    body = "After running the model, we found that the median was 12 ms.\n"
    result = scan(body, refs_keys=set())
    assert any(c.claim_class == "summary" for c in result.unhooked_claims)


def test_positive_broken_latex_cite_marker():
    """``\\cite{ghost}`` with empty refs source fires as broken (severity blocker)."""
    body = "The thesis rests on prior work \\cite{ghost-key}.\n"
    result = scan(body, refs_keys={"realone2024foo"})
    assert any(b.key == "ghost-key" and b.style == "latex"
               for b in result.broken_citations)
    review = result.to_review(version_dir="memo.1")
    blocker_findings = [f for f in review.findings if f.severity == "blocker"]
    assert len(blocker_findings) >= 1


def test_positive_broken_pandoc_cite_marker():
    """``[@ghost-key]`` fires as broken pandoc-style."""
    body = "See the prior work [@ghost-key] for context.\n"
    result = scan(body, refs_keys={"realone2024foo"})
    assert any(b.key == "ghost-key" and b.style == "pandoc"
               for b in result.broken_citations)


# ---------------------------------------------------------------------------
# False-positive cases — claims that MUST NOT fire
# ---------------------------------------------------------------------------


def test_false_positive_version_number_does_not_fire():
    """``version 3 of the API`` is a version context — no numeric finding."""
    body = "We are on version 3 of the API.\n"
    result = scan(body, refs_keys=set())
    assert all(c.claim_class != "numeric" for c in result.unhooked_claims)


def test_false_positive_python_version_does_not_fire():
    """``Python 3.12 deprecated`` is a version context."""
    body = "Python 3.12 deprecated the asyncio.coroutine decorator.\n"
    result = scan(body, refs_keys=set())
    assert all(c.claim_class != "numeric" for c in result.unhooked_claims)


def test_false_positive_nodejs_version_does_not_fire():
    """``Node.js 22.0.0`` is a version context."""
    body = "Node.js 22.0.0 introduced the new fetch API.\n"
    result = scan(body, refs_keys=set())
    assert all(c.claim_class != "numeric" for c in result.unhooked_claims)


def test_false_positive_see_figure_does_not_fire():
    """``see Figure 3`` is a self-reference — no numeric finding."""
    body = "The trend is clear — see Figure 3 for the chart.\n"
    result = scan(body, refs_keys=set())
    assert all(c.claim_class != "numeric" for c in result.unhooked_claims)


def test_false_positive_section_reference_does_not_fire():
    """``Section 4 reports`` is a self-reference."""
    body = "Section 4 reports the methodology details.\n"
    result = scan(body, refs_keys=set())
    assert all(c.claim_class != "numeric" for c in result.unhooked_claims)


def test_false_positive_hedged_numeric_claim_does_not_fire():
    """``roughly 30 customers`` is hedged — no numeric finding."""
    body = "We talked to roughly 30 customers in the discovery phase.\n"
    result = scan(body, refs_keys=set())
    assert all(c.claim_class != "numeric" for c in result.unhooked_claims)


def test_false_positive_estimated_market_does_not_fire():
    """``an estimated $1B market`` is hedged."""
    body = "The TAM is an estimated $1B market based on our model.\n"
    result = scan(body, refs_keys=set())
    assert all(c.claim_class != "numeric" for c in result.unhooked_claims)


def test_false_positive_blockquoted_numeric_does_not_fire():
    """A blockquoted ``42 % of users`` does not fire — quoted material."""
    body = "> 42 % of users churn within the first 30 days.\n"
    result = scan(body, refs_keys=set())
    assert not result.unhooked_claims


def test_false_positive_fenced_code_block_does_not_fire():
    """Numeric content inside fenced code does not fire."""
    body = "Here is the calculation:\n```\nrevenue = $2.3B\n```\n"
    result = scan(body, refs_keys=set())
    assert not result.unhooked_claims


def test_false_positive_inline_backtick_does_not_fire():
    """Numeric content inside inline backticks does not fire."""
    body = "The constant is `$2.3B` in the config.\n"
    result = scan(body, refs_keys=set())
    # The "$2.3B" inside backticks should be stripped before detection.
    numeric = [c for c in result.unhooked_claims if c.claim_class == "numeric"]
    assert not numeric


# ---------------------------------------------------------------------------
# Refs-resolution cases — claims that DO have valid hooks
# ---------------------------------------------------------------------------


def test_refs_resolved_latex_cite_does_not_fire():
    """``\\cite{real-key}`` with ``real-key`` in refs — no broken finding."""
    body = "The thesis rests on prior work \\cite{karpathy2024foo}.\n"
    result = scan(body, refs_keys={"karpathy2024foo"})
    assert not result.broken_citations


def test_refs_resolved_pandoc_cite_does_not_fire():
    """``[@real-key]`` with ``real-key`` in refs — no broken finding."""
    body = "Prior work [@karpathy2024foo] frames the problem.\n"
    result = scan(body, refs_keys={"karpathy2024foo"})
    assert not result.broken_citations


def test_line_with_cite_marker_suppresses_numeric_claim():
    """A line with a citation marker hooks every claim on the line."""
    body = "The market is $2.3B \\cite{realsource2024}.\n"
    result = scan(body, refs_keys={"realsource2024"})
    assert not result.unhooked_claims


def test_multi_key_latex_cite_resolves_each_key():
    """``\\cite{a,b,c}`` where ``a``, ``b``, ``c`` all exist — clean."""
    body = "Per prior work \\cite{a2024one,b2024two,c2024three}.\n"
    result = scan(body, refs_keys={"a2024one", "b2024two", "c2024three"})
    assert not result.broken_citations


def test_multi_key_pandoc_cite_resolves_each_key():
    """``[@a; @b]`` where ``a``, ``b`` exist — clean."""
    body = "Per prior work [@a2024one; @b2024two].\n"
    result = scan(body, refs_keys={"a2024one", "b2024two"})
    assert not result.broken_citations


# ---------------------------------------------------------------------------
# Closest-match suggestion
# ---------------------------------------------------------------------------


def test_closest_match_suggests_real_key_for_typo():
    """``\\cite{karpathy204}`` with ``karpathy2024`` in refs suggests it."""
    body = "Per prior work \\cite{karpathy204}.\n"
    result = scan(body, refs_keys={"karpathy2024"})
    broken = result.broken_citations
    assert len(broken) == 1
    assert broken[0].key == "karpathy204"
    assert broken[0].closest_match == "karpathy2024"
    assert "karpathy2024" in broken[0].suggested_fix


def test_closest_match_pandoc_typo():
    """``[@karpathy204]`` suggests ``karpathy2024`` from refs."""
    body = "See [@karpathy204] for context.\n"
    result = scan(body, refs_keys={"karpathy2024"})
    broken = result.broken_citations
    assert len(broken) == 1
    assert broken[0].closest_match == "karpathy2024"


def test_no_closest_match_when_keys_too_different():
    """An entirely unrelated key gets no close-match suggestion."""
    body = "Per work \\cite{totallyunrelated}.\n"
    result = scan(body, refs_keys={"karpathy2024foo"})
    broken = result.broken_citations
    assert len(broken) == 1
    assert broken[0].closest_match is None
    assert "Add a refs entry" in broken[0].suggested_fix


# ---------------------------------------------------------------------------
# Critical-flag heuristic
# ---------------------------------------------------------------------------


def test_critical_flag_fires_on_any_named_author_unhooked():
    """A single unhooked named-author claim triggers the critical flag."""
    body = "Smith (2023) reported the trend.\n"
    result = scan(body, refs_keys=set())
    assert result.should_emit_critical_flag()
    review = result.to_review(version_dir="memo.1")
    assert any(cf.type == CRITICAL_FLAG_TYPE for cf in review.critical_flags)


def test_critical_flag_does_not_fire_below_threshold():
    """1-5 unhooked numeric claims do NOT trigger the critical flag."""
    body = "\n".join([
        "The market is $1B.",
        "Latency is 12 ms.",
        "Headcount is 250 employees.",
    ]) + "\n"
    result = scan(body, refs_keys=set())
    # 3 unhooked, all numeric, no named-author — should NOT fire.
    assert not result.should_emit_critical_flag()


def test_critical_flag_fires_above_threshold():
    """More than 5 unhooked numeric claims triggers the critical flag."""
    lines = [
        "The market is $1B.",
        "Latency is 12 ms.",
        "Headcount is 250 employees.",
        "Revenue grew 50 %.",
        "Cycle time is 30 days.",
        "Storage budget is 5 GB.",
        "Margin is 65 %.",
    ]
    body = "\n".join(lines) + "\n"
    result = scan(body, refs_keys=set())
    assert len(result.unhooked_claims) > CRITICAL_UNHOOKED_THRESHOLD
    assert result.should_emit_critical_flag()


def test_clean_body_emits_no_findings_no_critical_flag():
    """A body with no claims at all emits no findings."""
    body = "This memo describes the methodology and conclusions.\n"
    result = scan(body, refs_keys=set())
    assert not result.unhooked_claims
    assert not result.broken_citations
    assert not result.should_emit_critical_flag()
    review = result.to_review(version_dir="memo.1")
    assert not review.findings
    assert not review.critical_flags


# ---------------------------------------------------------------------------
# Filesystem integration — scan_version_dir + collect_refs_keys
# ---------------------------------------------------------------------------


def _write_memo_version(
    project_root: Path, slug: str, body: str, version: int = 1
) -> Path:
    """Create a memo thread + version dir + body markdown.

    Mirrors the post-#295 shape: ``<project>/<slug>/<slug>.{N}/<slug>.md``.
    Returns the version directory path.
    """
    thread = project_root / slug
    version_dir = thread / f"{slug}.{version}"
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / f"{slug}.md").write_text(body, encoding="utf-8")
    return version_dir


def test_collect_refs_keys_from_thread_refs(tmp_path: Path):
    """``collect_refs_keys`` reads bibtex keys from per-thread refs/."""
    slug = "demo"
    version_dir = _write_memo_version(tmp_path, slug, "body\n")
    thread = version_dir.parent
    refs = thread / "refs"
    refs.mkdir()
    (refs / "refs.bib").write_text(
        "@article{smith2024transformers,\n"
        "  title={The Title},\n"
        "}\n"
        "@misc{karpathy2024foo,\n"
        "  title={Another Title},\n"
        "}\n",
        encoding="utf-8",
    )
    keys = collect_refs_keys(version_dir)
    assert "smith2024transformers" in keys
    assert "karpathy2024foo" in keys


def test_collect_refs_keys_from_version_dir_local_bib(tmp_path: Path):
    """``collect_refs_keys`` also picks up the version dir's own refs.bib."""
    slug = "demo"
    version_dir = _write_memo_version(tmp_path, slug, "body\n")
    (version_dir / "refs.bib").write_text(
        "@article{local2024key,\n  title={x},\n}\n",
        encoding="utf-8",
    )
    keys = collect_refs_keys(version_dir)
    assert "local2024key" in keys


def test_collect_refs_keys_from_portfolio_research(tmp_path: Path):
    """``collect_refs_keys`` walks ``<portfolio>/research/`` bibtex files."""
    slug = "demo"
    version_dir = _write_memo_version(tmp_path, slug, "body\n")
    research = tmp_path / "research"
    research.mkdir()
    (research / "shared.bib").write_text(
        "@article{shared2024key,\n  title={x},\n}\n",
        encoding="utf-8",
    )
    keys = collect_refs_keys(version_dir)
    assert "shared2024key" in keys


def test_scan_version_dir_returns_findings(tmp_path: Path):
    """``scan_version_dir`` runs the full pipeline from disk."""
    slug = "demo"
    body = (
        "The market is $2.3B.\n"
        "Smith (2023) reports the same.\n"
        "Prior work \\cite{ghost-key}.\n"
    )
    version_dir = _write_memo_version(tmp_path, slug, body)
    result = scan_version_dir(version_dir)
    assert result.body_path == f"{slug}.md"
    assert result.unhooked_claims  # something fired
    assert any(b.key == "ghost-key" for b in result.broken_citations)


def test_scan_version_dir_missing_body_returns_empty(tmp_path: Path):
    """Missing body markdown returns an empty result (graceful-degrade)."""
    slug = "demo"
    thread = tmp_path / slug
    version_dir = thread / f"{slug}.1"
    version_dir.mkdir(parents=True)
    # No <slug>.md present.
    result = scan_version_dir(version_dir)
    assert result.body_path is None
    assert not result.unhooked_claims
    assert not result.broken_citations


# ---------------------------------------------------------------------------
# Auto-discovery contract — the ``.citations/`` sibling is recognized by
# ``anvil/lib/critics.py::aggregate`` without code changes.
# ---------------------------------------------------------------------------


def test_aggregate_picks_up_citations_sibling(tmp_path: Path):
    """A ``<version_dir>.citations/`` sibling is auto-discovered.

    Acceptance-criteria validation: write a CoverageResult.to_review()
    into ``<version_dir>.citations/_review.json``, then call
    ``discover_critics`` + ``aggregate`` and confirm the verdict
    aggregator merges the findings into the AggregatedReview.
    """
    slug = "demo"
    version_dir = _write_memo_version(tmp_path, slug, "body\n")

    # Synthesize a CoverageResult with one unhooked claim and one broken
    # citation, then write the typed review into the sibling.
    coverage = CoverageResult(
        unhooked_claims=[
            UnhookedClaim(
                claim_class="numeric",
                text="$2.3B",
                line=1,
                rationale="unhooked numeric",
                suggested_fix="add a refs entry",
            )
        ],
        broken_citations=[
            BrokenCitation(
                key="ghost",
                style="latex",
                line=2,
                closest_match=None,
                suggested_fix="add a refs entry for 'ghost'",
            )
        ],
        body_path=f"{slug}.md",
    )
    review = coverage.to_review(version_dir=version_dir.name)
    sibling = version_dir.parent / f"{version_dir.name}.{CRITIC_ID}"
    sibling.mkdir()
    (sibling / "_review.json").write_text(
        review.model_dump_json(indent=2), encoding="utf-8"
    )

    # Auto-discovery should pick up the sibling.
    discovered = discover_critics(version_dir)
    assert sibling in discovered

    # Loading the review should succeed and round-trip the findings.
    loaded = load_review(sibling)
    assert loaded.kind == Kind.TOOL_EVIDENCE
    assert loaded.critic_id == CRITIC_ID
    assert len(loaded.findings) == 2

    # Aggregation should merge findings without raising.
    agg = aggregate([loaded])
    assert len(agg.findings) == 2
    # The blocker (broken cite) is the strongest severity present.
    severities = {f.severity for f in agg.findings}
    assert "blocker" in severities


# ---------------------------------------------------------------------------
# CLI entry-point smoke test
# ---------------------------------------------------------------------------


def test_cli_main_writes_review_json(tmp_path: Path):
    """``python -m anvil.skills.memo.lib.citation_coverage <dir>`` works."""
    from anvil.skills.memo.lib.citation_coverage import _cli_main

    slug = "demo"
    body = "Smith (2023) showed a clear trend.\n"
    version_dir = _write_memo_version(tmp_path, slug, body)

    rc = _cli_main([str(version_dir)])
    assert rc == 0

    sibling = version_dir.parent / f"{version_dir.name}.{CRITIC_ID}"
    review_path = sibling / "_review.json"
    findings_path = sibling / "_findings.json"
    assert review_path.is_file()
    assert findings_path.is_file()

    # _review.json validates against the typed schema.
    review = Review.model_validate_json(review_path.read_text())
    assert review.kind == Kind.TOOL_EVIDENCE
    assert review.critic_id == CRITIC_ID
    # Named-author claim → critical flag emitted.
    assert any(
        cf.type == CRITICAL_FLAG_TYPE for cf in review.critical_flags
    )

    # _findings.json is well-formed JSON with the documented shape.
    findings_data = json.loads(findings_path.read_text())
    assert findings_data["critic"] == "citations"
    assert findings_data["total_findings"] >= 1


# ---------------------------------------------------------------------------
# Doc-coverage: memo-citations command file references the lib correctly.
# ---------------------------------------------------------------------------


_COMMANDS_DIR = (
    Path(__file__).resolve().parents[3]
    / "anvil"
    / "skills"
    / "memo"
    / "commands"
)


def test_memo_citations_command_doc_exists():
    """``anvil/skills/memo/commands/memo-citations.md`` ships."""
    doc = _COMMANDS_DIR / "memo-citations.md"
    assert doc.is_file()


def test_memo_citations_command_doc_references_lib_module():
    """Command doc points at the lib module path."""
    doc = (_COMMANDS_DIR / "memo-citations.md").read_text(encoding="utf-8")
    assert "anvil.skills.memo.lib.citation_coverage" in doc


def test_memo_citations_command_doc_documents_critical_flag():
    """Command doc names the critical-flag type so operators can grep."""
    doc = (_COMMANDS_DIR / "memo-citations.md").read_text(encoding="utf-8")
    assert "critical_unsourced_load_bearing_claim" in doc


def test_memo_citations_command_doc_documents_sibling_dir_convention():
    """Command doc names the ``.citations/`` sibling-dir tag."""
    doc = (_COMMANDS_DIR / "memo-citations.md").read_text(encoding="utf-8")
    assert ".citations/" in doc
