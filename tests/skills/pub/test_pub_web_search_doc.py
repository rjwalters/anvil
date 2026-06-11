"""Doc-coverage guard for the consumer-opt-in web-search knob (issue #424).

Issue #424 adds an opt-in `web_search: true` knob (per-thread BRIEF
frontmatter; also a recognized strict-bool document-entry key in
`anvil/lib/project_brief.py`) that lets `pub-litsearch` run live web
searches under the resolver-verified-or-dropped contract — every
web-discovered candidate enters `candidates.bib` ONLY after
`anvil/lib/cite.py::resolve()` returns a `BibRecord`; unresolvable hits
(`UnsupportedIdentifierError` for pmid/url kinds, `CiteResolutionError`
after retries, no extractable identifier) become **leads** in the
`## Web leads (unverified)` section of `notes.md`, never citations.
`pub-review` stays read-only: under the knob it may run 3–5 targeted
D4 searches whose findings land in `comments.md` as `related-work`-
tagged leads recommending a `pub-litsearch` re-run.

These tests pin the load-bearing prose tokens in the three markdown
carriers (`pub-litsearch.md`, `pub-review.md`, `SKILL.md`) so a future
edit cannot silently drop the off-by-default guarantee or the
verification chokepoint.

Per the per-skill test filename convention (#58), this file is named
``test_pub_web_search_doc.py`` to avoid collision.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PUB_SKILL_DIR = REPO_ROOT / "anvil" / "skills" / "pub"
PUB_LITSEARCH_DOC = PUB_SKILL_DIR / "commands" / "pub-litsearch.md"
PUB_REVIEW_DOC = PUB_SKILL_DIR / "commands" / "pub-review.md"
PUB_SKILL_DOC = PUB_SKILL_DIR / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# pub-litsearch.md
# ---------------------------------------------------------------------------


def test_litsearch_doc_documents_web_search_knob():
    """The literal `web_search` token and the `true` opt-in shape appear."""
    text = _read(PUB_LITSEARCH_DOC)
    assert "web_search" in text, (
        "pub-litsearch.md must document the `web_search` BRIEF "
        "frontmatter knob (issue #424)."
    )
    assert "web_search: true" in text, (
        "pub-litsearch.md must show the `web_search: true` opt-in "
        "shape (issue #424)."
    )


def test_litsearch_doc_states_off_by_default_byte_identical():
    """The off-by-default guarantee must be stated explicitly."""
    text = _read(PUB_LITSEARCH_DOC)
    assert "byte-identical" in text, (
        "pub-litsearch.md must state that knob-absent / `false` "
        "behavior is byte-identical to the no-web contract "
        "(issue #424; mirrors the --rescore-mode precedent)."
    )


def test_litsearch_doc_names_resolver_chokepoint():
    """`cite.py` resolve() must be named as the verification chokepoint."""
    text = _read(PUB_LITSEARCH_DOC)
    assert "anvil/lib/cite.py" in text, (
        "pub-litsearch.md must name `anvil/lib/cite.py` as the "
        "verification chokepoint (issue #424)."
    )
    assert "resolve()" in text and "BibRecord" in text, (
        "pub-litsearch.md must state that a web-discovered candidate "
        "enters candidates.bib ONLY after `resolve()` returns a "
        "`BibRecord` (resolver-verified-or-dropped; issue #424)."
    )


def test_litsearch_doc_demotes_resolver_failures_to_leads():
    """Both v0 failure exceptions must be named as the leads path."""
    text = _read(PUB_LITSEARCH_DOC)
    assert "UnsupportedIdentifierError" in text, (
        "pub-litsearch.md must route pmid/url hits "
        "(UnsupportedIdentifierError) to leads, never citations "
        "(issue #424)."
    )
    assert "CiteResolutionError" in text, (
        "pub-litsearch.md must route retry-exhausted resolution "
        "failures (CiteResolutionError) to leads, never citations "
        "(issue #424)."
    )


def test_litsearch_doc_specifies_web_leads_section():
    """The `## Web leads (unverified)` notes.md section must be specified."""
    text = _read(PUB_LITSEARCH_DOC)
    assert "## Web leads (unverified)" in text, (
        "pub-litsearch.md must specify the `## Web leads (unverified)` "
        "section of notes.md for unresolvable hits (issue #424)."
    )


def test_litsearch_doc_specifies_provenance_table():
    """The verified-entry provenance table must be specified."""
    text = _read(PUB_LITSEARCH_DOC)
    assert "provenance" in text.lower(), (
        "pub-litsearch.md must specify the provenance table mapping "
        "web-verified bib keys to identifier + resolver (issue #424)."
    )
    assert "bib_key()" in text, (
        "pub-litsearch.md must route key generation through the lib's "
        "`bib_key()` for web-verified entries (issue #424)."
    )


def test_litsearch_doc_references_issue_424():
    """Audit-trail: the issue number must appear for traceability."""
    text = _read(PUB_LITSEARCH_DOC)
    assert "#424" in text, (
        "pub-litsearch.md must reference issue #424 in the web-search "
        "prose for audit-trail traceability."
    )


def test_litsearch_doc_keeps_no_invent_constraint_section():
    """The anti-hallucination section heading must remain in force."""
    text = _read(PUB_LITSEARCH_DOC)
    assert "## Critical constraint: do not invent citations" in text, (
        "pub-litsearch.md must keep the `Critical constraint: do not "
        "invent citations` section — web search changes where "
        "candidates come from, never the bar for entry (issue #424)."
    )


# ---------------------------------------------------------------------------
# pub-review.md
# ---------------------------------------------------------------------------


def test_review_doc_documents_web_search_knob():
    text = _read(PUB_REVIEW_DOC)
    assert "web_search" in text, (
        "pub-review.md must document the `web_search` knob for the D4 "
        "targeted-search behavior (issue #424)."
    )


def test_review_doc_keeps_reviewer_read_only_and_routes_leads():
    """The reviewer never writes citations; findings are related-work leads."""
    text = _read(PUB_REVIEW_DOC)
    knob_block_start = text.find("web_search")
    assert knob_block_start != -1
    knob_slice = text[knob_block_start:]
    assert "related-work" in knob_slice, (
        "pub-review.md's web_search prose must tag web findings as "
        "`related-work` leads in comments.md (issue #424)."
    )
    assert "pub-litsearch" in knob_slice, (
        "pub-review.md's web_search prose must route verification to a "
        "`pub-litsearch` re-run — the resolver-verified-or-dropped "
        "contract is centralized in litsearch (issue #424)."
    )


def test_review_doc_states_byte_identical_when_knob_unset():
    text = _read(PUB_REVIEW_DOC)
    knob_block_start = text.find("web_search")
    knob_slice = text[knob_block_start : text.find("--rescore-mode")]
    assert "byte-identical" in knob_slice, (
        "pub-review.md's web_search Inputs bullet must state the "
        "byte-identical-when-unset contract, mirroring --rescore-mode "
        "(issue #424)."
    )


def test_review_doc_references_issue_424():
    text = _read(PUB_REVIEW_DOC)
    assert "#424" in text, (
        "pub-review.md must reference issue #424 in the web-search "
        "prose for audit-trail traceability."
    )


# ---------------------------------------------------------------------------
# SKILL.md
# ---------------------------------------------------------------------------


def test_skill_doc_documents_knob_and_contract():
    text = _read(PUB_SKILL_DOC)
    assert "web_search" in text, (
        "pub SKILL.md must document the `web_search` knob (issue #424)."
    )
    assert "resolver-verified-or-dropped" in text, (
        "pub SKILL.md must name the resolver-verified-or-dropped "
        "contract (issue #424)."
    )
    assert "## Web leads (unverified)" in text or "Web leads (unverified)" in text, (
        "pub SKILL.md must mention the `Web leads (unverified)` leads "
        "section (issue #424)."
    )
