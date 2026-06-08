"""Doc-coverage + fixture-driven tests for the per-review rubric version
stamping landed by issue #346 and applied to the `report` skill by
issue #357 (the /40 → /44 migration with dim 9 *Rhetorical economy*).

Mirrors `tests/skills/memo/test_memo_rubric_version_transition_doc.py`.

The report skill is customer-facing tier — threshold ≥39/44 (was
≥35/40), the proportional bump from the memo's ≥35/44 to preserve
the customer-facing-vs-internal-memo gap.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "report"

REPORT_REVIEW_MD = SKILL_ROOT / "commands" / "report-review.md"
REPORT_RUBRIC_MD = SKILL_ROOT / "rubric.md"

FIXTURES = Path(__file__).parent / "fixtures" / "rubric_version_transition"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Doc-coverage
# ---------------------------------------------------------------------------


def test_report_review_step3_stamps_rubric_id():
    body = _read(REPORT_REVIEW_MD)
    assert "rubric_id" in body
    assert '"anvil-report-v2"' in body


def test_report_review_step3_stamps_rubric_total_and_threshold():
    body = _read(REPORT_REVIEW_MD)
    assert "rubric_total" in body and "advance_threshold" in body
    assert "rubric_total: 44" in body or '"rubric_total": 44' in body
    # Report ships customer-facing tier — threshold is 39, not 35.
    assert "advance_threshold: 39" in body or '"advance_threshold": 39' in body


def test_report_review_emits_top_level_rubric_block():
    body = _read(REPORT_REVIEW_MD)
    assert '"rubric": {' in body
    rubric_block_idx = body.find('"rubric": {')
    end_idx = body.find("\n     }", rubric_block_idx)
    block_text = body[rubric_block_idx:end_idx]
    assert '"id"' in block_text
    assert '"total"' in block_text
    assert '"advance_threshold"' in block_text
    assert '"dimensions"' in block_text


def test_report_review_documents_prior_rubric_surfacing():
    body = _read(REPORT_REVIEW_MD)
    assert "prior_rubric_id" in body
    assert "prior_rubric_inferred" in body
    assert "/40-legacy" in body


def test_report_review_emits_rubric_transition_subsection():
    body = _read(REPORT_REVIEW_MD)
    assert "## Rubric version transition" in body


def test_report_review_documents_score_history_rubric_id_append():
    body = _read(REPORT_REVIEW_MD)
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
    assert rows[0]["rubric_id"] == "anvil-report-v1-legacy-40"
    assert rows[1]["rubric_id"] == "anvil-report-v2"
    # Thresholds bumped: 35 → 39 (customer-facing tier).
    assert rows[0]["threshold"] == 35
    assert rows[1]["threshold"] == 39


def test_fixture_meta_legacy_lacks_rubric_id():
    data = json.loads((FIXTURES / "meta_legacy.json").read_text())
    assert data["scorecard_kind"] == "human-verdict"
    assert "rubric_id" not in data


def test_fixture_meta_stamped_v1_carries_legacy_40_stamp():
    data = json.loads((FIXTURES / "meta_stamped_v1.json").read_text())
    assert data["rubric_id"] == "anvil-report-v1-legacy-40"
    assert data["rubric_total"] == 40
    # Customer-facing tier: pre-migration threshold was 35.
    assert data["advance_threshold"] == 35


def test_fixture_meta_stamped_v2_carries_44_stamp():
    data = json.loads((FIXTURES / "meta_stamped_v2.json").read_text())
    assert data["rubric_id"] == "anvil-report-v2"
    assert data["rubric_total"] == 44
    # Post-migration customer-facing threshold is 39.
    assert data["advance_threshold"] == 39


def test_fixture_summary_carries_rubric_block_with_prior_rubric_inferred():
    data = json.loads(
        (FIXTURES / "summary_with_rubric_block.json").read_text()
    )
    rubric_block = data["rubric"]
    assert rubric_block["id"] == "anvil-report-v2"
    assert rubric_block["total"] == 44
    assert rubric_block["advance_threshold"] == 39
    assert rubric_block["dimensions"] == 9
    assert rubric_block["prior_rubric_id"] is None
    assert rubric_block["prior_rubric_inferred"] == "/40-legacy"


# ---------------------------------------------------------------------------
# Rubric file pinning
# ---------------------------------------------------------------------------


def test_report_rubric_md_declares_44_threshold_39():
    body = _read(REPORT_RUBRIC_MD)
    assert "**44**" in body or "/44" in body
    # Customer-facing tier: ≥39/44 threshold.
    assert "≥39/44" in body or "≥39**" in body or "≥39" in body


def test_report_rubric_md_declares_dim_9_rhetorical_economy():
    body = _read(REPORT_RUBRIC_MD)
    assert "Rhetorical economy" in body
    assert "**Total**" in body and "**44**" in body
