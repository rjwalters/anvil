"""Doc-coverage + fixture-driven tests for the per-review rubric version
stamping landed by issue #346 and applied to the `pub` skill by issue
#357 (the /40 → /44 migration with dim 9 *Rhetorical economy*).

Mirrors `tests/skills/memo/test_memo_rubric_version_transition_doc.py`;
see that file for the canonical pattern.

Per-skill test filename convention (#58): this file is named
``test_pub_rubric_version_transition_doc.py`` so pytest does not collide
with future test files for adjacent issues.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "pub"

PUB_REVIEW_MD = SKILL_ROOT / "commands" / "pub-review.md"
PUB_RUBRIC_MD = SKILL_ROOT / "rubric.md"

FIXTURES = Path(__file__).parent / "fixtures" / "rubric_version_transition"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Doc-coverage: pub-review step 3 stamps `rubric_id` + `rubric_total` +
# `advance_threshold` on `_meta.json` (issue #346)
# ---------------------------------------------------------------------------


def test_pub_review_step3_stamps_rubric_id():
    body = _read(PUB_REVIEW_MD)
    assert "rubric_id" in body, (
        "pub-review.md step 3 MUST stamp `rubric_id` on `_meta.json` "
        "per issue #346 / `snippets/scorecard_kind.md` §'Rubric version "
        "stamping fields'."
    )
    # Pin the specific identifier — the pub skill ships /44 via
    # `anvil-pub-v2` per `anvil/skills/pub/rubric.md` line 3.
    assert '"anvil-pub-v2"' in body, (
        "pub-review.md step 3 MUST hardcode `rubric_id: \"anvil-pub-v2\"` "
        "(the pub skill's current /44 rubric identifier)."
    )


def test_pub_review_step3_stamps_rubric_total_and_threshold():
    body = _read(PUB_REVIEW_MD)
    assert "rubric_total" in body and "advance_threshold" in body, (
        "pub-review.md step 3 MUST stamp `rubric_total` AND "
        "`advance_threshold` on `_meta.json` per issue #346."
    )
    # Pin the values: /44, ≥35.
    assert "rubric_total: 44" in body or '"rubric_total": 44' in body
    assert "advance_threshold: 35" in body or '"advance_threshold": 35' in body


def test_pub_review_emits_top_level_rubric_block():
    body = _read(PUB_REVIEW_MD)
    assert '"rubric": {' in body, (
        "pub-review.md MUST emit a top-level `rubric` block "
        "in `_summary.md` per issue #346 AC 3."
    )
    # The block carries `id`, `total`, `advance_threshold`, `dimensions`.
    rubric_block_idx = body.find('"rubric": {')
    # Find end of block by counting braces from this position
    end_idx = body.find("\n      }", rubric_block_idx)
    block_text = body[rubric_block_idx:end_idx]
    assert '"id"' in block_text
    assert '"total"' in block_text
    assert '"advance_threshold"' in block_text
    assert '"dimensions"' in block_text


def test_pub_review_documents_prior_rubric_surfacing():
    body = _read(PUB_REVIEW_MD)
    # AC 5: mixed-rubric thread surfacing carries `prior_rubric_id`
    # and falls back to `prior_rubric_inferred: "/40-legacy"` for
    # legacy reviews.
    assert "prior_rubric_id" in body
    assert "prior_rubric_inferred" in body
    assert "/40-legacy" in body


def test_pub_review_emits_rubric_transition_subsection():
    body = _read(PUB_REVIEW_MD)
    assert "## Rubric version transition" in body, (
        "pub-review.md MUST emit a `## Rubric version "
        "transition` subsection in findings.md when the prior rubric "
        "differs (issue #346 AC 5)."
    )


def test_pub_review_documents_score_history_rubric_id_append():
    body = _read(PUB_REVIEW_MD)
    # AC 2: per-row `rubric_id` stamp on `score_history`.
    assert (
        "score_history" in body
        and "rubric_id" in body
    ), (
        "pub-review.md MUST document the per-row `rubric_id` "
        "stamp on `score_history` (issue #346 AC 2)."
    )


# ---------------------------------------------------------------------------
# Fixture-driven schema-of-record contracts
# ---------------------------------------------------------------------------


def test_fixture_dir_present():
    assert FIXTURES.is_dir(), (
        "tests/skills/pub/fixtures/rubric_version_transition/ "
        "MUST exist per issue #357 AC."
    )


def test_fixture_progress_iter1_legacy_lacks_rubric_id():
    """Legacy `_progress.json` row has no `rubric_id` — reader tolerates."""
    data = json.loads((FIXTURES / "progress_iter1_legacy.json").read_text())
    rows = data["metadata"]["score_history"]
    assert len(rows) == 1
    row = rows[0]
    # The load-bearing claim: the legacy row carries `total` + `threshold`
    # but NO `rubric_id` — readers must tolerate the absence.
    assert "total" in row
    assert "threshold" in row
    assert "rubric_id" not in row


def test_fixture_progress_iter2_stamped_rubric_transition():
    """Stamped `_progress.json` carries different `rubric_id` per row.

    Iter 1: `anvil-pub-v1-legacy-40` (stamped /40 review).
    Iter 2: `anvil-pub-v2` (stamped /44 review).
    """
    data = json.loads(
        (FIXTURES / "progress_iter2_stamped.json").read_text()
    )
    rows = data["metadata"]["score_history"]
    assert len(rows) == 2
    assert rows[0]["rubric_id"] == "anvil-pub-v1-legacy-40"
    assert rows[1]["rubric_id"] == "anvil-pub-v2"
    # Thresholds bumped: 32 → 35; totals on different point pools
    # (30/40, 36/44) — the canonical /40 → /44 transition fingerprint.
    assert rows[0]["threshold"] == 32
    assert rows[1]["threshold"] == 35


def test_fixture_meta_legacy_lacks_rubric_id():
    """Legacy `_meta.json` predates per-review version stamping."""
    data = json.loads((FIXTURES / "meta_legacy.json").read_text())
    # The discriminator + scorecard_kind ARE present (these landed earlier);
    # but `rubric_id` / `rubric_total` / `advance_threshold` are absent.
    assert data["scorecard_kind"] == "human-verdict"
    assert "rubric_id" not in data
    assert "rubric_total" not in data
    assert "advance_threshold" not in data


def test_fixture_meta_stamped_v1_carries_legacy_40_stamp():
    data = json.loads((FIXTURES / "meta_stamped_v1.json").read_text())
    assert data["rubric_id"] == "anvil-pub-v1-legacy-40"
    assert data["rubric_total"] == 40
    assert data["advance_threshold"] == 32


def test_fixture_meta_stamped_v2_carries_44_stamp():
    data = json.loads((FIXTURES / "meta_stamped_v2.json").read_text())
    assert data["rubric_id"] == "anvil-pub-v2"
    assert data["rubric_total"] == 44
    assert data["advance_threshold"] == 35


def test_fixture_summary_carries_rubric_block_with_prior_rubric_inferred():
    """Summary fixture shows the legacy-prior-rubric fallback path."""
    data = json.loads(
        (FIXTURES / "summary_with_rubric_block.json").read_text()
    )
    rubric_block = data["rubric"]
    assert rubric_block["id"] == "anvil-pub-v2"
    assert rubric_block["total"] == 44
    assert rubric_block["advance_threshold"] == 35
    assert rubric_block["dimensions"] == 9
    # The legacy-prior surfacing path.
    assert rubric_block["prior_rubric_id"] is None
    assert rubric_block["prior_rubric_inferred"] == "/40-legacy"


# ---------------------------------------------------------------------------
# Rubric file pinning: pub /44 rubric line 3
# ---------------------------------------------------------------------------


def test_pub_rubric_md_declares_44_threshold_35():
    body = _read(PUB_RUBRIC_MD)
    assert "**44**" in body or "/44" in body
    assert "≥35/44" in body or "≥35**" in body


def test_pub_rubric_md_declares_dim_9_rhetorical_economy():
    """The pub rubric MUST carry a dim 9 row for *Rhetorical economy* at
    weight 4 per the issue #357 decision matrix.
    """
    body = _read(PUB_RUBRIC_MD)
    # Dim 9 row present, named "Rhetorical economy"
    assert "Rhetorical economy" in body
    # The total row reads 44
    assert "**Total**" in body and "**44**" in body
