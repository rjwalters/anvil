"""Doc-coverage + fixture-driven tests for the per-review rubric version
stamping landed by issue #346 and applied to the `ip-uspto` skill by
issue #357.

Unlike the other 5 skills migrated by #357 (memo-mirror dim 9
*Rhetorical economy*), ip-uspto takes a **skill-appropriate dim 9
*Claim-spec correspondence*** at weight 5, preserving the flat-weight
design. The result is **/45 total** (9 dims × 5 each), threshold
≥39/45 (proportional bump from ≥35/40).

The fixtures use `scorecard_kind: "machine-summary"` (not
`human-verdict` like the other 5 skills) — the three rubric-stamping
fields are independent of `scorecard_kind` per
`snippets/scorecard_kind.md` §"The discriminator".

Mirrors `tests/skills/memo/test_memo_rubric_version_transition_doc.py`.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "ip-uspto"

IP_USPTO_REVIEW_MD = SKILL_ROOT / "commands" / "ip-uspto-review.md"
IP_USPTO_RUBRIC_MD = SKILL_ROOT / "rubric.md"

FIXTURES = Path(__file__).parent / "fixtures" / "rubric_version_transition"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Doc-coverage
# ---------------------------------------------------------------------------


def test_ip_uspto_review_step3_stamps_rubric_id():
    body = _read(IP_USPTO_REVIEW_MD)
    assert "rubric_id" in body
    assert '"anvil-ip-uspto-v2"' in body


def test_ip_uspto_review_step3_stamps_rubric_total_and_threshold():
    body = _read(IP_USPTO_REVIEW_MD)
    assert "rubric_total" in body and "advance_threshold" in body
    # ip-uspto ships /45 (preserves flat-weight design: 9 × 5).
    assert "rubric_total: 45" in body or '"rubric_total": 45' in body
    # Threshold is 39 (proportional bump from ≥35/40).
    assert "advance_threshold: 39" in body or '"advance_threshold": 39' in body


def test_ip_uspto_review_emits_top_level_rubric_block():
    body = _read(IP_USPTO_REVIEW_MD)
    assert '"rubric": {' in body
    rubric_block_idx = body.find('"rubric": {')
    end_idx = body.find("\n     }", rubric_block_idx)
    block_text = body[rubric_block_idx:end_idx]
    assert '"id"' in block_text
    assert '"total"' in block_text
    assert '"advance_threshold"' in block_text
    assert '"dimensions"' in block_text


def test_ip_uspto_review_documents_prior_rubric_surfacing():
    body = _read(IP_USPTO_REVIEW_MD)
    assert "prior_rubric_id" in body
    assert "prior_rubric_inferred" in body
    assert "/40-legacy" in body


def test_ip_uspto_review_emits_rubric_transition_subsection():
    body = _read(IP_USPTO_REVIEW_MD)
    assert "## Rubric version transition" in body


def test_ip_uspto_review_documents_score_history_rubric_id_append():
    body = _read(IP_USPTO_REVIEW_MD)
    assert "score_history" in body and "rubric_id" in body


def test_ip_uspto_review_preserves_machine_summary_scorecard_kind():
    """ip-uspto-review emits machine-summary scorecard kind; the rubric
    stamping fields are independent of scorecard_kind per
    snippets/scorecard_kind.md §"The discriminator"."""
    body = _read(IP_USPTO_REVIEW_MD)
    assert '"machine-summary"' in body or "machine-summary" in body
    # And the rubric stamping coexists with machine-summary.
    assert '"anvil-ip-uspto-v2"' in body


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
    assert rows[0]["rubric_id"] == "anvil-ip-uspto-v1-legacy-40"
    assert rows[1]["rubric_id"] == "anvil-ip-uspto-v2"
    # Thresholds bumped: 35 → 39.
    assert rows[0]["threshold"] == 35
    assert rows[1]["threshold"] == 39


def test_fixture_meta_legacy_lacks_rubric_id():
    data = json.loads((FIXTURES / "meta_legacy.json").read_text())
    # machine-summary, not human-verdict.
    assert data["scorecard_kind"] == "machine-summary"
    assert "rubric_id" not in data


def test_fixture_meta_stamped_v1_carries_legacy_40_stamp():
    data = json.loads((FIXTURES / "meta_stamped_v1.json").read_text())
    assert data["rubric_id"] == "anvil-ip-uspto-v1-legacy-40"
    assert data["rubric_total"] == 40
    assert data["advance_threshold"] == 35
    # machine-summary discriminator preserved.
    assert data["scorecard_kind"] == "machine-summary"


def test_fixture_meta_stamped_v2_carries_45_stamp():
    """ip-uspto is the only skill in #357 that uses /45 (flat-weight
    design preserved: 9 × 5).
    """
    data = json.loads((FIXTURES / "meta_stamped_v2.json").read_text())
    assert data["rubric_id"] == "anvil-ip-uspto-v2"
    assert data["rubric_total"] == 45
    assert data["advance_threshold"] == 39
    assert data["scorecard_kind"] == "machine-summary"


def test_fixture_summary_carries_rubric_block_with_prior_rubric_inferred():
    data = json.loads(
        (FIXTURES / "summary_with_rubric_block.json").read_text()
    )
    rubric_block = data["rubric"]
    assert rubric_block["id"] == "anvil-ip-uspto-v2"
    assert rubric_block["total"] == 45
    assert rubric_block["advance_threshold"] == 39
    assert rubric_block["dimensions"] == 9
    assert rubric_block["prior_rubric_id"] is None
    assert rubric_block["prior_rubric_inferred"] == "/40-legacy"


# ---------------------------------------------------------------------------
# Rubric file pinning
# ---------------------------------------------------------------------------


def test_ip_uspto_rubric_md_declares_45_threshold_39():
    body = _read(IP_USPTO_RUBRIC_MD)
    assert "**45**" in body or "/45" in body
    assert "≥39/45" in body or "≥39**" in body or "≥39" in body


def test_ip_uspto_rubric_md_declares_dim_9_claim_spec_correspondence():
    """The ip-uspto rubric MUST carry a dim 9 row for *Claim-spec
    correspondence* (NOT *Rhetorical economy* — that's the other 5 skills)
    at weight 5 per the issue #357 decision matrix.
    """
    body = _read(IP_USPTO_RUBRIC_MD)
    # Dim 9 row present, named "Claim-spec correspondence"
    assert "Claim-spec correspondence" in body
    # NOT named "Rhetorical economy" — patent applications are the
    # inverse of memos on bloat.
    # (The rationale prose may mention Rhetorical economy as the
    # alternative considered-and-rejected, so we don't reject "Rhetorical
    # economy" as a substring; we just confirm "Claim-spec correspondence"
    # is the named dim 9.)
    # The total row reads 45.
    assert "**Total**" in body and "**45**" in body


def test_ip_uspto_rubric_md_preserves_flat_weight_design():
    """The flat-weight design (every dim weighted 5) is preserved post-#357.

    9 dimensions × 5 each = 45. The rubric prose explicitly calls this
    out.
    """
    body = _read(IP_USPTO_RUBRIC_MD)
    assert "flat" in body.lower()
    # Specifically: "5/45" or "5 each" or similar language.
    assert "5/45" in body or "weighted equally at **5/45**" in body
