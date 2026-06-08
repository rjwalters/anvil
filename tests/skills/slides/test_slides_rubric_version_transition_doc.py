"""Doc-coverage + fixture-driven tests for the per-review rubric version
stamping landed by issue #346 and applied to the `slides` skill by
issue #357 (the /40 → /44 migration with dim 9 *Rhetorical economy* at
the talk level).

Mirrors `tests/skills/memo/test_memo_rubric_version_transition_doc.py`.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "slides"

SLIDES_REVIEW_MD = SKILL_ROOT / "commands" / "slides-review.md"
SLIDES_RUBRIC_MD = SKILL_ROOT / "rubric.md"

FIXTURES = Path(__file__).parent / "fixtures" / "rubric_version_transition"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Doc-coverage
# ---------------------------------------------------------------------------


def test_slides_review_step3_stamps_rubric_id():
    body = _read(SLIDES_REVIEW_MD)
    assert "rubric_id" in body
    assert '"anvil-slides-v2"' in body


def test_slides_review_step3_stamps_rubric_total_and_threshold():
    body = _read(SLIDES_REVIEW_MD)
    assert "rubric_total" in body and "advance_threshold" in body
    assert "rubric_total: 44" in body or '"rubric_total": 44' in body
    assert "advance_threshold: 35" in body or '"advance_threshold": 35' in body


def test_slides_review_emits_top_level_rubric_block():
    body = _read(SLIDES_REVIEW_MD)
    assert '"rubric": {' in body
    rubric_block_idx = body.find('"rubric": {')
    end_idx = body.find("\n      }", rubric_block_idx)
    block_text = body[rubric_block_idx:end_idx]
    assert '"id"' in block_text
    assert '"total"' in block_text
    assert '"advance_threshold"' in block_text
    assert '"dimensions"' in block_text


def test_slides_review_documents_prior_rubric_surfacing():
    body = _read(SLIDES_REVIEW_MD)
    assert "prior_rubric_id" in body
    assert "prior_rubric_inferred" in body
    assert "/40-legacy" in body


def test_slides_review_emits_rubric_transition_subsection():
    body = _read(SLIDES_REVIEW_MD)
    assert "## Rubric version transition" in body


def test_slides_review_documents_score_history_rubric_id_append():
    body = _read(SLIDES_REVIEW_MD)
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
    assert rows[0]["rubric_id"] == "anvil-slides-v1-legacy-40"
    assert rows[1]["rubric_id"] == "anvil-slides-v2"
    assert rows[0]["threshold"] == 32
    assert rows[1]["threshold"] == 35


def test_fixture_meta_legacy_lacks_rubric_id():
    data = json.loads((FIXTURES / "meta_legacy.json").read_text())
    assert data["scorecard_kind"] == "human-verdict"
    assert "rubric_id" not in data


def test_fixture_meta_stamped_v1_carries_legacy_40_stamp():
    data = json.loads((FIXTURES / "meta_stamped_v1.json").read_text())
    assert data["rubric_id"] == "anvil-slides-v1-legacy-40"
    assert data["rubric_total"] == 40
    assert data["advance_threshold"] == 32


def test_fixture_meta_stamped_v2_carries_44_stamp():
    data = json.loads((FIXTURES / "meta_stamped_v2.json").read_text())
    assert data["rubric_id"] == "anvil-slides-v2"
    assert data["rubric_total"] == 44
    assert data["advance_threshold"] == 35


def test_fixture_summary_carries_rubric_block_with_prior_rubric_inferred():
    data = json.loads(
        (FIXTURES / "summary_with_rubric_block.json").read_text()
    )
    rubric_block = data["rubric"]
    assert rubric_block["id"] == "anvil-slides-v2"
    assert rubric_block["total"] == 44
    assert rubric_block["advance_threshold"] == 35
    assert rubric_block["dimensions"] == 9
    assert rubric_block["prior_rubric_id"] is None
    assert rubric_block["prior_rubric_inferred"] == "/40-legacy"


# ---------------------------------------------------------------------------
# Rubric file pinning
# ---------------------------------------------------------------------------


def test_slides_rubric_md_declares_44_threshold_35():
    body = _read(SLIDES_RUBRIC_MD)
    assert "**44**" in body or "/44" in body
    assert "≥35/44" in body or "≥35**" in body


def test_slides_rubric_md_declares_dim_9_rhetorical_economy():
    body = _read(SLIDES_RUBRIC_MD)
    assert "Rhetorical economy" in body
    assert "**Total**" in body and "**44**" in body
