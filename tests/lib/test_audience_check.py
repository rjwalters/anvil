"""Tests for ``anvil/lib/audience_check.py`` (issue #1322).

The deterministic audience-fit pre-flight: governance vocabulary addressed to
the project's operator (authorization, commissioning, publication gates,
budget caps, internal goal/ticket numbers), private locators a reader cannot
follow (``s3://``, room-message numbers, home-directory paths), and bare
repo-relative artifact paths in an artifacts/availability section with no
``\\href``/``\\url``.

The fixture sentences are the ones quoted in #1322 from a consumer thread
that reached AUDITED at anvil 0.11.6 with every one of them still in the text.

Covered contract:

- each defect class is detected; ordinary prose (including the mathematical
  sense of "operator") is not;
- severity is ``major`` in the body and ``minor`` after ``\\appendix``
  (including an appendix pulled in through ``\\input``);
- LaTeX comments, verbatim and markdown code are masked; a
  ``anvil-lint-disable: audience_check`` directive suppresses a line;
- link hygiene: ``\\href``/``\\url``-wrapped paths and paths explicitly
  marked "not published" pass; the public repository URL resolves from
  ``.anvil.json`` > BRIEF frontmatter > the paper's own forge links;
- the review is ADVISORY: ``kind: tool_evidence``, no critical flag, owns
  no rubric dimension, never changes the aggregated verdict;
- ``--write-review`` lands ``<thread>.{N}.audience/_review.json``, which
  ``critics.discover_critics`` picks up with no aggregator change.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib.audience_check import (
    AUDIENCE_SUFFIX,
    CHECK_NAME,
    CRITIC_ID,
    RULE_GOVERNANCE,
    RULE_PRIVATE_LOCATOR,
    RULE_UNLINKED_PATH,
    check_audience,
    find_audience_hits,
    load_declared_audience,
    main,
    REPO_SOURCE_ANVIL_JSON,
    REPO_SOURCE_BRIEF,
    REPO_SOURCE_DERIVED,
    resolve_public_repo_url,
    resolve_public_repo_url_with_source,
    write_review_dir,
)
from anvil.lib.critics import aggregate, compute_verdict, discover_critics, load_review
from anvil.lib.review_schema import Kind, Review, Score, Verdict


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DEFECT_TEX = r"""\documentclass{article}
\begin{document}
\section{Cost to verify}
Replaying the certificates costs about 80 dollars per day.
No replay wave is authorized by this estimate.
A requester-pays copy is subject to the operator's publication gate.
The Laplace operator is self-adjoint on this domain.
\section{Artifacts and receipts}
The repository is \url{https://github.com/example/proofs}.
Timing data: \texttt{refs/CENSUS\_TIMING\_20260928.md}.
Solver timing: \href{https://github.com/example/proofs/blob/main/sat49/H1.md}{\texttt{sat49/H1.md}}.
The room transcript (message 31994) is not published with this paper.
The raw log \texttt{logs/run.txt} is not published.
Bucket: s3://example-private/certs/.
% goal #99 authorized this comment, which a reader never sees
\section{Conclusion}
See \texttt{outside/section.md} for more.
\appendix
\section{Solver attempts}
All 20 authorized solver attempts ended UNKNOWN.
\section{Process}
Goal \#39 authorized the certificate campaign; goal \#40 commissioned this manuscript.
\end{document}
"""

_CLEAN_TEX = r"""\documentclass{article}
\begin{document}
\section{Results}
The bound holds for every $n \ge 3$; the Laplace operator is self-adjoint.
\section{Data availability}
All scripts are at \href{https://github.com/example/proofs/tree/main/scripts}{\texttt{scripts/run.py}}.
\end{document}
"""


def _make_thread(tmp_path: Path, body: str, *, name: str = "main.tex") -> Path:
    thread = tmp_path / "erdos-drop"
    version = thread / "erdos-drop.4"
    version.mkdir(parents=True)
    (version / name).write_text(body, encoding="utf-8")
    return version


def _by_rule(hits, rule):
    return [h for h in hits if h.rule == rule]


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_governance_vocabulary_detected_with_region_severity():
    hits = find_audience_hits(_DEFECT_TEX, latex=True)
    gov = _by_rule(hits, RULE_GOVERNANCE)
    lines = {h.line: h for h in gov}
    # §4.4-shaped body sentences -> major
    assert lines[5].severity == "major" and lines[5].region == "body"
    assert any("authorized" in t.lower() for t in lines[5].terms)
    assert lines[6].severity == "major"
    # Appendix sentences -> minor
    assert lines[20].region == "appendix" and lines[20].severity == "minor"
    terms22 = " ".join(lines[22].terms).lower()
    assert "goal" in terms22 and "39" in terms22
    assert "commissioned" in terms22
    assert lines[22].severity == "minor"


def test_math_operator_and_ordinary_prose_not_flagged():
    hits = find_audience_hits(_DEFECT_TEX, latex=True)
    assert all(h.line not in (4, 7) for h in hits)
    assert find_audience_hits(_CLEAN_TEX, latex=True) == []


def test_latex_comment_is_masked():
    hits = find_audience_hits(_DEFECT_TEX, latex=True)
    assert all(h.line != 15 for h in hits)


def test_private_locators_detected():
    hits = _by_rule(find_audience_hits(_DEFECT_TEX, latex=True), RULE_PRIVATE_LOCATOR)
    lines = {h.line for h in hits}
    assert 12 in lines  # message 31994
    assert 14 in lines  # s3://
    home = find_audience_hits("Data lives in /Users/alice/work/data.csv today.\n")
    assert _by_rule(home, RULE_PRIVATE_LOCATOR)


def test_unlinked_artifact_path_scoped_to_artifacts_section():
    hits = _by_rule(find_audience_hits(_DEFECT_TEX, latex=True), RULE_UNLINKED_PATH)
    lines = {h.line for h in hits}
    assert 10 in lines  # bare \texttt{refs/CENSUS\_TIMING...}
    assert 11 not in lines  # wrapped in \href
    assert 9 not in lines  # \url to the repo root
    assert 13 not in lines  # explicitly "not published"
    assert 17 not in lines  # outside the artifacts section
    hit = next(h for h in hits if h.line == 10)
    assert "refs/CENSUS_TIMING_20260928.md" in hit.terms
    assert hit.severity == "major"


def test_markdown_body_masks_fences_but_checks_inline_code_paths():
    md = (
        "# Results\n"
        "```\n"
        "goal #7 authorized inside a fence\n"
        "```\n"
        "Some `goal #8` inline code.\n"
        "## Code availability\n"
        "Receipts: `refs/timing.md` and [the log](https://github.com/x/y/blob/main/log.txt).\n"
        "# Appendix A\n"
        "Budget cap approved by the operator review.\n"
    )
    hits = find_audience_hits(md, latex=False)
    assert all(h.line not in (3, 5) for h in hits)
    paths = _by_rule(hits, RULE_UNLINKED_PATH)
    assert [h.line for h in paths] == [7]
    assert paths[0].terms == ("refs/timing.md",)
    gov = _by_rule(hits, RULE_GOVERNANCE)
    assert [h.line for h in gov] == [9]
    assert gov[0].severity == "minor"


def test_lint_disable_suppresses_line():
    text = (
        "Intro.\n"
        "<!-- anvil-lint-disable: audience_check -->\n"
        "The committee authorized the study protocol (IRB 2024-17).\n"
        "Then goal #3 was commissioned.\n"
    )
    hits = find_audience_hits(text)
    suppressed = [h for h in hits if h.suppressed]
    active = [h for h in hits if not h.suppressed]
    assert [h.line for h in suppressed] == [3]
    assert suppressed[0].severity == "nit"
    assert [h.line for h in active] == [4]
    tex = "% anvil-lint-disable: audience_check\nWe were authorized to use the data.\n"
    assert all(h.suppressed for h in find_audience_hits(tex, latex=True))


# ---------------------------------------------------------------------------
# Filesystem entry point, BRIEF, public repo URL
# ---------------------------------------------------------------------------


def test_check_audience_follows_input_into_appendix(tmp_path):
    main_tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\section{Intro}\nWe study sums.\n"
        "\\appendix\n\\input{process}\n\\end{document}\n"
    )
    version = _make_thread(tmp_path, main_tex)
    (version / "process.tex").write_text(
        "\\section{Process}\nOperator goal \\#25 made the outline the allocation instrument.\n",
        encoding="utf-8",
    )
    result = check_audience(version)
    gov = _by_rule(result.active_hits, RULE_GOVERNANCE)
    assert len(gov) == 1
    assert gov[0].path == "process.tex" and gov[0].line == 2
    assert gov[0].region == "appendix" and gov[0].severity == "minor"
    assert "process.tex" in result.files


def test_declared_audience_from_frontmatter_and_heading(tmp_path):
    thread = tmp_path / "t"
    thread.mkdir()
    (thread / "BRIEF.md").write_text(
        "---\naudience: Combinatorialists and formal-methods readers\n---\n# Brief\n",
        encoding="utf-8",
    )
    assert load_declared_audience(thread) == [
        "Combinatorialists and formal-methods readers"
    ]
    (thread / "BRIEF.md").write_text(
        "# Brief\n\n## Audience\n\nNumber theorists.\n\n## Scope\nx\n",
        encoding="utf-8",
    )
    assert load_declared_audience(thread) == ["Number theorists."]
    (thread / "BRIEF.md").unlink()
    assert load_declared_audience(thread) == []


def test_public_repo_url_resolution_order(tmp_path):
    version = _make_thread(tmp_path, _DEFECT_TEX)
    thread = version.parent
    # Derived from the paper's own forge link when nothing is declared.
    assert resolve_public_repo_url(thread, _DEFECT_TEX) == "https://github.com/example/proofs"
    (thread / "BRIEF.md").write_text(
        "---\npublic_repo_url: https://gitlab.com/brief/repo\n---\n", encoding="utf-8"
    )
    assert resolve_public_repo_url(thread, _DEFECT_TEX) == "https://gitlab.com/brief/repo"
    (thread / ".anvil.json").write_text(
        json.dumps({"public_repo_url": "https://codeberg.org/json/repo"}), encoding="utf-8"
    )
    assert resolve_public_repo_url(thread, _DEFECT_TEX) == "https://codeberg.org/json/repo"
    assert resolve_public_repo_url(tmp_path / "nowhere", "no links here") is None


def test_result_json_and_fix_names_public_repo(tmp_path):
    version = _make_thread(tmp_path, _DEFECT_TEX)
    (version.parent / "BRIEF.md").write_text(
        "---\naudience: Combinatorialists\n---\n", encoding="utf-8"
    )
    result = check_audience(version)
    payload = result.to_json()
    assert payload["check"] == CHECK_NAME
    assert payload["declared_audience"] == ["Combinatorialists"]
    assert payload["public_repo_url"] == "https://github.com/example/proofs"
    assert payload["pass"] is False
    assert payload["counts"][RULE_GOVERNANCE] >= 3
    review = result.to_review(version_dir=version.name)
    path_findings = [f for f in review.findings if "refs/CENSUS_TIMING_20260928.md" in f.rationale]
    assert path_findings
    assert "https://github.com/example/proofs" in path_findings[0].suggested_fix
    gov_findings = [f for f in review.findings if "Combinatorialists" in f.rationale]
    assert gov_findings
    assert "non-published process log" in gov_findings[0].suggested_fix


_CITED_DEPENDENCY_TEX = r"""\documentclass{article}
\begin{document}
\section{Introduction}
We build on Mathlib \url{https://github.com/leanprover-community/mathlib4}.
\section{Artifacts and receipts}
The timing census is in refs/CENSUS_TIMING_20260928.md and sat49/H1_TIMING.md.
\end{document}
"""


def test_cited_dependency_outside_artifacts_is_not_the_public_repo(tmp_path):
    """Judge finding on PR #1325: a repo cited in the introduction (Mathlib)
    must not be reported as the paper's own repository, must not make the
    link-hygiene hits critical-eligible, and must not template an invented
    \\href."""
    version = _make_thread(tmp_path, _CITED_DEPENDENCY_TEX)
    result = check_audience(version)
    payload = result.to_json()
    assert payload["public_repo_url"] is None
    assert payload["public_repo_url_source"] is None
    assert payload["public_repo_url_declared"] is False
    paths = _by_rule(result.active_hits, RULE_UNLINKED_PATH)
    assert [h.terms for h in paths] == [
        ("refs/CENSUS_TIMING_20260928.md", "sat49/H1_TIMING.md")
    ]
    review = result.to_review(version_dir=version.name)
    assert review.critical_flags == []
    fixes = [f.suggested_fix for f in review.findings if "CENSUS" in f.rationale]
    assert fixes
    for fix in fixes:
        assert "mathlib4" not in fix
        assert "\\href{http" not in fix
        assert "declare `public_repo_url`" in fix


def test_derived_repo_url_is_a_candidate_not_a_concrete_href(tmp_path):
    # _DEFECT_TEX links its repository inside the artifacts section, so the
    # URL is derived — but still unconfirmed: no concrete \href is templated.
    version = _make_thread(tmp_path, _DEFECT_TEX)
    result = check_audience(version)
    assert result.public_repo_url == "https://github.com/example/proofs"
    assert result.public_repo_url_source == REPO_SOURCE_DERIVED
    assert result.public_repo_url_declared is False
    review = result.to_review(version_dir=version.name)
    fix = next(
        f.suggested_fix for f in review.findings if "refs/CENSUS_TIMING_20260928.md" in f.rationale
    )
    assert "\\href{https://github.com/example/proofs" not in fix
    assert "NOT confirmed" in fix
    assert "never invent a URL" in fix


def test_declared_repo_url_templates_concrete_href(tmp_path):
    version = _make_thread(tmp_path, _CITED_DEPENDENCY_TEX)
    (version.parent / "BRIEF.md").write_text(
        "---\npublic_repo_url: https://github.com/example/proofs\n---\n", encoding="utf-8"
    )
    result = check_audience(version)
    assert result.public_repo_url_source == REPO_SOURCE_BRIEF
    assert result.public_repo_url_declared is True
    assert result.to_json()["public_repo_url_declared"] is True
    fix = next(
        f.suggested_fix
        for f in result.to_review(version_dir=version.name).findings
        if "CENSUS" in f.rationale
    )
    assert (
        "\\href{https://github.com/example/proofs/blob/<ref>/refs/CENSUS_TIMING_20260928.md}"
        in fix
    )


def test_public_repo_url_source_order(tmp_path):
    thread = tmp_path / "t"
    thread.mkdir()
    text = "Repo: https://github.com/example/proofs/tree/main/x"
    assert resolve_public_repo_url_with_source(thread, text) == (
        "https://github.com/example/proofs",
        REPO_SOURCE_DERIVED,
    )
    (thread / "BRIEF.md").write_text(
        "---\npublic_repo_url: https://gitlab.com/brief/repo/\n---\n", encoding="utf-8"
    )
    assert resolve_public_repo_url_with_source(thread, text) == (
        "https://gitlab.com/brief/repo",
        REPO_SOURCE_BRIEF,
    )
    (thread / ".anvil.json").write_text(
        json.dumps({"public_repo_url": "https://codeberg.org/json/repo"}), encoding="utf-8"
    )
    assert resolve_public_repo_url_with_source(thread, text) == (
        "https://codeberg.org/json/repo",
        REPO_SOURCE_ANVIL_JSON,
    )
    assert resolve_public_repo_url_with_source(tmp_path / "nowhere", "") == (None, None)


# ---------------------------------------------------------------------------
# Derived candidate: dependency links inside the availability section (#1329)
# ---------------------------------------------------------------------------


_DEPENDENCY_AVAILABILITY_TEX = r"""\documentclass{article}
\begin{document}
\section{Data availability}
The pipeline requires NumPy \url{https://github.com/numpy/numpy}.
The timing census is in refs/CENSUS_TIMING_20260928.md and sat49/H1_TIMING.md.
\end{document}
"""


def test_dependency_link_in_availability_yields_no_candidate(tmp_path):
    """#1329: the availability section's only forge link is introduced as a
    dependency ("requires NumPy, \\url{...}"), so it is NOT offered as the
    paper's candidate repository — the fix asks for a declaration instead."""
    version = _make_thread(tmp_path, _DEPENDENCY_AVAILABILITY_TEX)
    result = check_audience(version)
    payload = result.to_json()
    assert payload["public_repo_url"] is None
    assert payload["public_repo_url_source"] is None
    assert payload["public_repo_url_declared"] is False
    fixes = [f.suggested_fix for f in result.to_review(version_dir=version.name).findings]
    assert fixes
    for fix in fixes:
        assert "numpy" not in fix
    census = next(
        f.suggested_fix
        for f in result.to_review(version_dir=version.name).findings
        if "CENSUS" in f.rationale
    )
    assert "declare `public_repo_url`" in census
    assert "Candidate repository" not in census


_WRAPPED_DEPENDENCY_AVAILABILITY_TEX = r"""\documentclass{article}
\begin{document}
\section{Data availability}
The pipeline requires NumPy
\url{https://github.com/numpy/numpy}.
The timing census is in refs/CENSUS_TIMING_20260928.md and sat49/H1_TIMING.md.
\end{document}
"""


def test_hard_wrapped_dependency_link_yields_no_candidate(tmp_path):
    """#1329: the same availability section as above, hard-wrapped so the
    dependency verb and its URL land on different *source* lines.

    ``_artifacts_text()`` preserves the ``.tex`` source's line structure
    verbatim, so segmenting on any newline would put "requires NumPy" and
    ``\\url{...}`` in different segments and lose the dependency signal —
    making the fix formatting-dependent. Segmenting on paragraph breaks keeps
    the wrapped sentence whole.
    """
    version = _make_thread(tmp_path, _WRAPPED_DEPENDENCY_AVAILABILITY_TEX)
    result = check_audience(version)
    payload = result.to_json()
    assert payload["public_repo_url"] is None
    assert payload["public_repo_url_source"] is None
    assert payload["public_repo_url_declared"] is False
    fixes = [f.suggested_fix for f in result.to_review(version_dir=version.name).findings]
    assert fixes
    for fix in fixes:
        assert "numpy" not in fix


def test_hard_wrapped_signals_scope_across_source_lines(tmp_path):
    """Both vocabularies scope across a wrapped line, and a paragraph break
    still separates two sentences that would otherwise be conflated."""
    thread = tmp_path / "t"
    thread.mkdir()
    # Dependency verb on the previous wrapped line still suppresses the link.
    for text in (
        "The pipeline requires NumPy\n\\url{https://github.com/numpy/numpy}.\n",
        "The solver is built on\nhttps://gitlab.com/example/solver\nfor its core.\n",
    ):
        assert resolve_public_repo_url_with_source(thread, text) == (None, None)
    # Ownership signal on the previous wrapped line still claims the link
    # (the Judge's note that the same weakness cuts both ways on #1340).
    wrapped_ownership = (
        "The pipeline requires NumPy\n\\url{https://github.com/numpy/numpy}.\n"
        "Our code is at\n\\url{https://github.com/example/proofs}.\n"
    )
    assert resolve_public_repo_url_with_source(thread, wrapped_ownership) == (
        "https://github.com/example/proofs",
        REPO_SOURCE_DERIVED,
    )
    # A paragraph break is still a segment boundary: the dependency framing in
    # the first paragraph does not reach the link in the second.
    assert resolve_public_repo_url_with_source(
        thread,
        "Our experiments used NumPy throughout\nand SciPy for the solvers\n\n"
        "Everything is at\n\\url{https://github.com/example/proofs}\n",
    ) == ("https://github.com/example/proofs", REPO_SOURCE_DERIVED)


def test_dependency_signal_only_applies_when_it_precedes_the_link(tmp_path):
    thread = tmp_path / "t"
    thread.mkdir()
    for text in (
        "The pipeline requires NumPy \\url{https://github.com/numpy/numpy}.",
        "Built on https://github.com/numpy/numpy.",
        "The solver depends on https://gitlab.com/example/solver for its core.",
        "Timings were produced using https://github.com/numpy/numpy.",
    ):
        assert resolve_public_repo_url_with_source(thread, text) == (None, None)
    # A trailing mention of a dependency does not flag a link ahead of it.
    assert resolve_public_repo_url_with_source(
        thread, "Everything is at https://github.com/example/proofs; it requires NumPy."
    ) == ("https://github.com/example/proofs", REPO_SOURCE_DERIVED)


def test_ownership_signal_wins_over_a_dependency_link(tmp_path):
    thread = tmp_path / "t"
    thread.mkdir()
    text = (
        "The pipeline requires NumPy \\url{https://github.com/numpy/numpy}.\n"
        "Our code is at \\url{https://github.com/example/proofs}.\n"
    )
    assert resolve_public_repo_url_with_source(thread, text) == (
        "https://github.com/example/proofs",
        REPO_SOURCE_DERIVED,
    )
    text = (
        "We build on \\url{https://github.com/leanprover-community/mathlib4}.\n"
        "The repository for this paper is "
        "\\url{https://codeberg.org/example/proofs/src/branch/main}.\n"
    )
    assert resolve_public_repo_url_with_source(thread, text) == (
        "https://codeberg.org/example/proofs",
        REPO_SOURCE_DERIVED,
    )


def test_two_unflagged_links_are_ambiguous_and_yield_no_candidate(tmp_path):
    thread = tmp_path / "t"
    thread.mkdir()
    text = (
        "Certificates: \\url{https://github.com/example/proofs}.\n"
        "Solver: \\url{https://gitlab.com/example/solver}.\n"
    )
    assert resolve_public_repo_url_with_source(thread, text) == (None, None)
    # Two ownership-flagged repositories are equally ambiguous.
    text = (
        "Our code is at \\url{https://github.com/example/proofs}.\n"
        "Our code is also at \\url{https://gitlab.com/example/solver}.\n"
    )
    assert resolve_public_repo_url_with_source(thread, text) == (None, None)


def test_repeated_links_to_one_repo_remain_a_sole_candidate(tmp_path):
    """Regression guard for ``_DEFECT_TEX``: the availability section links
    the same repository twice (a ``\\url`` and a deep ``\\href``), which is
    still exactly one candidate repository."""
    thread = tmp_path / "t"
    thread.mkdir()
    text = (
        "The repository is \\url{https://github.com/example/proofs}.\n"
        "Solver timing: \\href{https://github.com/example/proofs/blob/main/sat49/H1.md}"
        "{\\texttt{sat49/H1.md}}.\n"
    )
    assert resolve_public_repo_url_with_source(thread, text) == (
        "https://github.com/example/proofs",
        REPO_SOURCE_DERIVED,
    )


# ---------------------------------------------------------------------------
# Advisory review + sidecar
# ---------------------------------------------------------------------------


def test_review_is_advisory_tool_evidence(tmp_path):
    version = _make_thread(tmp_path, _DEFECT_TEX)
    review = check_audience(version).to_review(version_dir=version.name)
    assert review.kind == Kind.TOOL_EVIDENCE
    assert review.critic_id == CRITIC_ID
    assert review.critical_flags == []
    assert all(s.score is None for s in review.scores)
    severities = {f.severity for f in review.findings}
    assert severities <= {"major", "minor", "nit"}
    assert "major" in severities and "minor" in severities
    assert all(f.tool_calls == [] for f in review.findings)


def test_write_review_dir_is_discovered_and_never_changes_verdict(tmp_path):
    version = _make_thread(tmp_path, _DEFECT_TEX)
    out = write_review_dir(version, check_audience(version))
    assert out == version.parent / f"{version.name}.{AUDIENCE_SUFFIX}" / "_review.json"
    Review.model_validate_json(out.read_text(encoding="utf-8"))
    assert out.parent in discover_critics(version)

    # A passing content review alongside the audience sidecar still ADVANCEs:
    # the audience review owns no rubric dimension and carries no flag.
    content = Review(
        schema_version="1",
        kind=Kind.JUDGMENT,
        version_dir=version.name,
        critic_id="review",
        scores=[Score(dimension="content", score=40, max=44, justification="ok")],
        findings=[],
        critical_flags=[],
    )
    audience = load_review(out.parent)
    agg = aggregate([content, audience])
    assert agg.total == 40
    assert compute_verdict(agg, threshold=35) == Verdict.ADVANCE
    # Regeneration on a later pass replaces the prior sidecar.
    (version / "main.tex").write_text(_CLEAN_TEX, encoding="utf-8")
    out2 = write_review_dir(version, check_audience(version))
    assert json.loads(out2.read_text(encoding="utf-8"))["findings"] == []


def test_cli_exit_codes(tmp_path, capsys):
    version = _make_thread(tmp_path, _DEFECT_TEX)
    assert main([str(version), "--write-review"]) == 1
    assert (version.parent / f"{version.name}.{AUDIENCE_SUFFIX}" / "_review.json").is_file()
    out = json.loads(capsys.readouterr().out)
    assert out["pass"] is False
    clean = _make_thread(tmp_path / "c", _CLEAN_TEX)
    assert main([str(clean)]) == 0
    assert main([str(tmp_path / "missing.1")]) == 2
