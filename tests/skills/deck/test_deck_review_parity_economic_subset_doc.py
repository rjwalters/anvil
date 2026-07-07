"""Doc-coverage guard for the deck-review / deck-revise economic-subset
parity-lint wiring (issue #553).

The issue layers a load-bearingness filter over the existing
``only_in_memo`` set in the deck↔memo parity lint, promoting a strict
subset of findings to ``side="only_in_memo_economic"``. The reviser is
taught to consult the promoted subset BEFORE bulk-dismissing the
broader ``only_in_memo`` set (the canary failure mode from Docent,
2026-06-12).

The runtime classifier lives in ``anvil/lib/parity.py``; this test
pins the prose surfaces so a future doc edit cannot silently drop the
load-bearingness contract from either command file.

Per the per-skill test filename convention (#58), this file is named
``test_deck_review_parity_economic_subset_doc.py`` to avoid
cross-skill pytest collection collisions.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DECK_REVIEW_DOC = (
    REPO_ROOT / "anvil" / "skills" / "deck" / "commands" / "deck-review.md"
)
DECK_REVISE_DOC = (
    REPO_ROOT / "anvil" / "skills" / "deck" / "commands" / "deck-revise.md"
)
MEMO_REVIEW_DOC = (
    REPO_ROOT / "anvil" / "skills" / "memo" / "commands" / "memo-review.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_deck_review_doc_names_only_in_memo_economic_side_value():
    """The deck-review step 5d prose must name the new ``Finding.side``
    literal value so a reviser reading the command file finds the
    contract documented (not buried in the lib docstring).
    """
    text = _read(DECK_REVIEW_DOC)
    assert "only_in_memo_economic" in text, (
        "deck-review.md must document the `only_in_memo_economic` "
        "Finding.side value (issue #553)."
    )


def test_deck_review_doc_references_economic_context_vocabulary():
    """The prose must name the vocab constant so a reviser knows where
    the seed list lives (for canary-driven calibration follow-on).
    """
    text = _read(DECK_REVIEW_DOC)
    assert "ECONOMIC_CONTEXT_VOCABULARY" in text, (
        "deck-review.md must reference `ECONOMIC_CONTEXT_VOCABULARY` "
        "so the calibration knob is discoverable from the command file."
    )


def test_deck_review_doc_describes_load_bearingness_classifier():
    """The prose must explicitly frame the classifier as a load-
    bearingness filter — the curator brief's load-bearing framing.
    """
    text = _read(DECK_REVIEW_DOC)
    assert "load-bearing" in text.lower() or "load-bearingness" in text.lower(), (
        "deck-review.md must frame the classifier as a load-bearingness "
        "filter (issue #553 — the canary's accurate complaint)."
    )


def test_deck_review_doc_summary_example_carries_only_in_memo_economic_key():
    """The `_summary.md` schema example block in the deck-review doc
    must include the new top-level key under the `deck_memo_parity`
    block so a downstream consumer reading the schema sees the new
    field documented as first-class.
    """
    text = _read(DECK_REVIEW_DOC)
    # Find the deck_memo_parity block and confirm the key appears within.
    parity_block_start = text.find('"deck_memo_parity"')
    assert parity_block_start != -1
    parity_block = text[parity_block_start : parity_block_start + 2500]
    assert '"only_in_memo_economic"' in parity_block, (
        "deck-review.md's deck_memo_parity schema example must carry the "
        "new `only_in_memo_economic` key at the top level (issue #553)."
    )


def test_deck_review_doc_findings_md_renders_economic_subsection():
    """The findings.md rendering example must include the new
    "Economic substance dropped from deck" subsection so the operator
    sees the sharper framing as a distinct visual block.
    """
    text = _read(DECK_REVIEW_DOC)
    assert "Economic substance dropped from deck" in text, (
        "deck-review.md must render the load-bearing-economic subset in a "
        "distinct subsection of `findings.md` § Parity-lint findings "
        "(issue #553 — bulk-dismissal prevention)."
    )


def test_deck_revise_doc_consumes_economic_subset_with_distinct_framing():
    """The deck-revise consumption step must:

    1. Name the new field by its literal key (so the reviser knows
       which `_summary.md` block to read).
    2. Frame the consumption as "BEFORE bulk-dismissing" the broader
       only_in_memo set (the canary failure mode contract).
    3. Distinguish the three resolutions: port / deliberate omission /
       decline.
    """
    text = _read(DECK_REVISE_DOC)
    assert "only_in_memo_economic" in text, (
        "deck-revise.md must document reading the `only_in_memo_economic` "
        "list from the review summary (issue #553)."
    )
    # The framing contract: "before bulk-dismissing" is the key phrase
    # the curator brief pinned.
    lowered = text.lower()
    assert "before bulk-dismiss" in lowered or "before accept" in lowered, (
        "deck-revise.md must frame the consumption step as 'consult BEFORE "
        "bulk-dismissing' / 'before accepting' the broader only_in_memo set "
        "(issue #553 — the canary failure mode is bulk-dismissal)."
    )


def test_deck_revise_doc_revision_log_carries_economic_subset_subsection():
    """The revision-log template must include a "Parity-lint resolutions
    (economic subset)" subsection so each token in the subset gets a
    per-token audit row.
    """
    text = _read(DECK_REVISE_DOC)
    assert "Parity-lint resolutions (economic subset)" in text, (
        "deck-revise.md's `_revision-log.md` template must include a "
        "'Parity-lint resolutions (economic subset)' subsection (issue #553)."
    )


def test_deck_revise_doc_references_issue_553():
    """Audit trail: the issue number must appear in the doc for
    traceability so a future maintainer can follow the contract back to
    the curator brief.
    """
    text = _read(DECK_REVISE_DOC)
    assert "#553" in text, (
        "deck-revise.md must reference issue #553 for audit-trail "
        "traceability of the economic-subset contract."
    )


def test_deck_review_doc_references_issue_553():
    """Same audit-trail pin on the review side."""
    text = _read(DECK_REVIEW_DOC)
    assert "#553" in text, (
        "deck-review.md must reference issue #553 in the deck_memo_parity "
        "step 5d prose for audit-trail traceability."
    )


def test_deck_review_doc_documents_figure_carried_csv_lookup():
    """Issue #623: the step 5d prose must document that a token whose
    numeric value appears in a `figures/src/*.csv` source is NOT promoted
    to `only_in_memo_economic` — the figure-carried suppression contract.
    """
    text = _read(DECK_REVIEW_DOC)
    assert "figures/src" in text, (
        "deck-review.md must document the `figures/src/*.csv` figure-corpus "
        "lookup that suppresses false economic promotions (issue #623)."
    )


def test_deck_review_doc_names_figure_corpus_helpers():
    """The prose must name the two runtime helpers so a maintainer can
    trace the CSV-lookup contract from the command file to the lib.
    """
    text = _read(DECK_REVIEW_DOC)
    assert "_extract_figure_corpus" in text, (
        "deck-review.md must reference `_extract_figure_corpus` (issue #623)."
    )
    assert "_strip_token_numeric" in text, (
        "deck-review.md must reference `_strip_token_numeric` (issue #623)."
    )


def test_deck_review_doc_references_issue_623():
    """Audit trail: the issue number must appear in the deck-review doc so
    a future maintainer can follow the figure-carried contract back to the
    curator brief.
    """
    text = _read(DECK_REVIEW_DOC)
    assert "#623" in text, (
        "deck-review.md must reference issue #623 in the deck_memo_parity "
        "step 5d prose for audit-trail traceability of the figure-carried "
        "suppression contract."
    )


def test_memo_review_doc_schema_carries_only_in_memo_economic_key():
    """Schema parity: the memo-side schema example must carry the new
    `only_in_memo_economic` key so a downstream consumer aggregating
    across deck-side and memo-side review summaries sees a consistent
    wire shape. The memo-side rendering is informational only (per the
    curator brief), but the schema field is present.
    """
    text = _read(MEMO_REVIEW_DOC)
    # Find the JSON-in-markdown schema example block. The literal token
    # appears multiple times in prose (e.g. ``rule="memo_deck_parity"``
    # in step 4d's call-shape description); the schema block opens with
    # the JSON-style key + colon + brace shape. Scan from the first
    # JSON-shape occurrence forward.
    needle = '"memo_deck_parity": {'
    parity_block_start = text.find(needle)
    assert parity_block_start != -1, (
        "memo-review.md must contain a JSON schema example block opening "
        f"with `{needle}` (issue #553 schema-parity contract)."
    )
    parity_block = text[parity_block_start : parity_block_start + 2500]
    assert '"only_in_memo_economic"' in parity_block, (
        "memo-review.md's memo_deck_parity schema example must carry the "
        "new `only_in_memo_economic` key for schema parity with the "
        "deck-side (issue #553)."
    )
