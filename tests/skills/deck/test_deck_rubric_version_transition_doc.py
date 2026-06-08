"""Doc-coverage + fixture-driven tests for the per-review rubric version
stamping landed by issue #346 and applied to the `deck` skill by issue
#357 (the /40 → /44 migration with dim 9 *Rhetorical economy*, owned
by deck-narrative).

Mirrors `tests/skills/memo/test_memo_rubric_version_transition_doc.py`.

The deck skill is customer-facing tier — threshold ≥39/44 (was
≥35/40), the proportional bump. Only the aggregator (deck-review)
stamps in this PR; the four specialist critics inherit on follow-up.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "deck"

DECK_REVIEW_MD = SKILL_ROOT / "commands" / "deck-review.md"
DECK_RUBRIC_MD = SKILL_ROOT / "rubric.md"

FIXTURES = Path(__file__).parent / "fixtures" / "rubric_version_transition"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Doc-coverage
# ---------------------------------------------------------------------------


def test_deck_review_step4_stamps_rubric_id():
    body = _read(DECK_REVIEW_MD)
    assert "rubric_id" in body
    assert '"anvil-deck-v2"' in body


def test_deck_review_step4_stamps_rubric_total_and_threshold():
    body = _read(DECK_REVIEW_MD)
    assert "rubric_total" in body and "advance_threshold" in body
    assert "rubric_total: 44" in body or '"rubric_total": 44' in body
    # Deck ships customer-facing tier — threshold is 39, not 35.
    assert "advance_threshold: 39" in body or '"advance_threshold": 39' in body


def test_deck_review_emits_top_level_rubric_block():
    body = _read(DECK_REVIEW_MD)
    assert '"rubric": {' in body
    rubric_block_idx = body.find('"rubric": {')
    end_idx = body.find("\n     }", rubric_block_idx)
    block_text = body[rubric_block_idx:end_idx]
    assert '"id"' in block_text
    assert '"total"' in block_text
    assert '"advance_threshold"' in block_text
    assert '"dimensions"' in block_text


def test_deck_review_documents_prior_rubric_surfacing():
    body = _read(DECK_REVIEW_MD)
    assert "prior_rubric_id" in body
    assert "prior_rubric_inferred" in body
    assert "/40-legacy" in body


def test_deck_review_emits_rubric_transition_subsection():
    body = _read(DECK_REVIEW_MD)
    assert "## Rubric version transition" in body


def test_deck_review_documents_score_history_rubric_id_append():
    body = _read(DECK_REVIEW_MD)
    assert "score_history" in body and "rubric_id" in body


# ---------------------------------------------------------------------------
# Fixture-driven schema-of-record contracts
# ---------------------------------------------------------------------------


def test_fixture_dir_present():
    assert FIXTURES.is_dir()


def test_fixture_progress_iter1_legacy_lacks_rubric_id():
    data = json.loads((FIXTURES / "progress_iter1_legacy.json").read_text())
    rows = data["metadata"]["score_history"]
    assert len(rows) == 1
    row = rows[0]
    assert "total" in row
    assert "threshold" in row
    assert "rubric_id" not in row


def test_fixture_progress_iter2_stamped_rubric_transition():
    data = json.loads(
        (FIXTURES / "progress_iter2_stamped.json").read_text()
    )
    rows = data["metadata"]["score_history"]
    assert len(rows) == 2
    assert rows[0]["rubric_id"] == "anvil-deck-v1-legacy-40"
    assert rows[1]["rubric_id"] == "anvil-deck-v2"
    # Thresholds bumped: 35 → 39 (customer-facing tier).
    assert rows[0]["threshold"] == 35
    assert rows[1]["threshold"] == 39


def test_fixture_meta_legacy_lacks_rubric_id():
    data = json.loads((FIXTURES / "meta_legacy.json").read_text())
    assert data["scorecard_kind"] == "human-verdict"
    assert "rubric_id" not in data


def test_fixture_meta_stamped_v1_carries_legacy_40_stamp():
    data = json.loads((FIXTURES / "meta_stamped_v1.json").read_text())
    assert data["rubric_id"] == "anvil-deck-v1-legacy-40"
    assert data["rubric_total"] == 40
    assert data["advance_threshold"] == 35


def test_fixture_meta_stamped_v2_carries_44_stamp():
    data = json.loads((FIXTURES / "meta_stamped_v2.json").read_text())
    assert data["rubric_id"] == "anvil-deck-v2"
    assert data["rubric_total"] == 44
    assert data["advance_threshold"] == 39


def test_fixture_summary_carries_rubric_block_with_prior_rubric_inferred():
    data = json.loads(
        (FIXTURES / "summary_with_rubric_block.json").read_text()
    )
    rubric_block = data["rubric"]
    assert rubric_block["id"] == "anvil-deck-v2"
    assert rubric_block["total"] == 44
    assert rubric_block["advance_threshold"] == 39
    assert rubric_block["dimensions"] == 9
    assert rubric_block["prior_rubric_id"] is None
    assert rubric_block["prior_rubric_inferred"] == "/40-legacy"


# ---------------------------------------------------------------------------
# Rubric file pinning
# ---------------------------------------------------------------------------


def test_deck_rubric_md_declares_44_threshold_39():
    body = _read(DECK_RUBRIC_MD)
    assert "**44**" in body or "/44" in body
    assert "≥39/44" in body or "≥39**" in body or "≥39" in body


def test_deck_rubric_md_declares_dim_9_rhetorical_economy():
    body = _read(DECK_RUBRIC_MD)
    assert "Rhetorical economy" in body
    assert "**Total**" in body and "**44**" in body


def test_deck_rubric_md_documents_dim_9_owned_by_narrative():
    """Per curator's decision matrix, dim 9 is owned by deck-narrative
    (the arc/ask critic) — "could a busy investor extract the ask in
    90 seconds?" is the arc critic's natural turf."""
    body = _read(DECK_RUBRIC_MD)
    # The dimensions table row for dim 9 should mark `deck-narrative` ownership.
    # The "Owns dimensions" table for deck-narrative MUST mention "9".
    # Search for the deck-narrative ownership line.
    idx = body.find("`deck-narrative`")
    assert idx > 0
    # Look at the row containing deck-narrative ownership for dims 1, 7, 9
    # in the "Critic dimension ownership" table.
    owns_idx = body.find("| `deck-narrative` |", idx)
    if owns_idx < 0:
        owns_idx = body.find("`deck-narrative` | 1, 7, 9")
    assert "1, 7, 9" in body or "deck-narrative` | 1, 7, 9" in body, (
        "rubric.md MUST assign dim 9 ownership to deck-narrative per "
        "issue #357's decision matrix."
    )
