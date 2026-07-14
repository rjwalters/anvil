"""Doc-coverage + fixture-driven tests for the per-review rubric version
stamping landed by issue #346.

Per the curated AC, this module ships:

- **Doc-coverage smoke tests**: grep-the-doc regression guards that
  ``commands/memo-review.md`` step 3 (the new `_meta.json` init with
  `rubric_id` / `rubric_total` / `advance_threshold`) and step 9
  (the new top-level `rubric` block on `_summary.md`) and step 9b
  (the `## Rubric version transition` subsection in `findings.md`)
  stay documented and don't drift back to a pre-#346 shape.
- **Snippet-coverage smoke tests**: ``snippets/scorecard_kind.md`` and
  ``snippets/progress.md`` document the per-review version stamping
  + `score_history[].rubric_id` extension; ``snippets/rubric.md``
  documents the `/40 → /44` migration prose + the per-skill `total`
  reframe (no more hardcoded "8 dimensions summing to /40" prose).
- **Fixture-driven schema-of-record tests**: the three
  ``rubric_version_transition/*.json`` fixtures (legacy `_progress` +
  stamped `_progress` + `_meta` triple + `_summary` with the new
  `rubric` block) parse cleanly as JSON and carry the load-bearing
  fields per the contracts documented in the snippets + command file.

Per-skill test filename convention (#58): this file is named
``test_memo_rubric_version_transition_doc.py`` so pytest does not collide
with future test files for adjacent issues.

Module load notes:
- The shipped #346 contract is prose-as-prompt (no Python detector
  ships); this test module treats the prose contract + JSON fixtures
  as the contract-under-test. Per-thread end-to-end behaviour belongs
  in consumer-side integration tests; here we pin the schema-of-record
  contract so the prose can't silently drift back to a pre-#346 form.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "memo"
PROPOSAL_SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "proposal"

MEMO_REVIEW_MD = SKILL_ROOT / "commands" / "memo-review.md"
PROPOSAL_REVIEW_MD = PROPOSAL_SKILL_ROOT / "commands" / "proposal-review.md"
MEMO_RUBRIC_MD = SKILL_ROOT / "rubric.md"
PROPOSAL_RUBRIC_MD = PROPOSAL_SKILL_ROOT / "rubric.md"

SNIPPETS = REPO_ROOT / "anvil" / "lib" / "snippets"
SCORECARD_KIND_MD = SNIPPETS / "scorecard_kind.md"
PROGRESS_MD = SNIPPETS / "progress.md"
RUBRIC_SNIPPET_MD = SNIPPETS / "rubric.md"

FIXTURES = Path(__file__).parent / "fixtures" / "rubric_version_transition"


# ---------------------------------------------------------------------------
# Doc-coverage: memo-review step 3 stamps `rubric_id` + `rubric_total` +
# `advance_threshold` on `_meta.json` (issue #346)
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_memo_review_step3_stamps_rubric_id():
    body = _read(MEMO_REVIEW_MD)
    assert "rubric_id" in body, (
        "memo-review.md step 3 MUST stamp `rubric_id` on `_meta.json` "
        "per issue #346 / `snippets/scorecard_kind.md` §'Rubric version "
        "stamping fields'."
    )
    # Pin the specific identifier — the memo skill ships /44 via
    # `anvil-memo-v2` per `anvil/skills/memo/rubric.md` line 3.
    assert '"anvil-memo-v2"' in body, (
        "memo-review.md step 3 MUST hardcode `rubric_id: \"anvil-memo-v2\"` "
        "(the memo skill's current /44 rubric identifier)."
    )


def test_memo_review_step3_stamps_rubric_total_and_threshold():
    body = _read(MEMO_REVIEW_MD)
    assert "rubric_total" in body and "advance_threshold" in body, (
        "memo-review.md step 3 MUST stamp `rubric_total` AND "
        "`advance_threshold` on `_meta.json` per issue #346."
    )
    # Pin the values: /44, ≥35.
    assert "rubric_total: 44" in body or '"rubric_total": 44' in body
    assert "advance_threshold: 35" in body or '"advance_threshold": 35' in body


def test_memo_review_step9_emits_top_level_rubric_block():
    body = _read(MEMO_REVIEW_MD)
    assert '"rubric": {' in body, (
        "memo-review.md step 9 MUST emit a top-level `rubric` block "
        "in `_summary.md` per issue #346 AC 3."
    )
    # The block carries `id`, `total`, `advance_threshold`, `dimensions`.
    rubric_block_idx = body.find('"rubric": {')
    end_idx = body.find("\n     }", rubric_block_idx)
    block_text = body[rubric_block_idx:end_idx]
    assert '"id"' in block_text
    assert '"total"' in block_text
    assert '"advance_threshold"' in block_text
    assert '"dimensions"' in block_text


def test_memo_review_step9_documents_prior_rubric_surfacing():
    body = _read(MEMO_REVIEW_MD)
    # AC 5: mixed-rubric thread surfacing carries `prior_rubric_id`
    # and falls back to `prior_rubric_inferred: "/40-legacy"` for
    # legacy reviews.
    assert "prior_rubric_id" in body
    assert "prior_rubric_inferred" in body
    assert "/40-legacy" in body


def test_memo_review_step9b_emits_rubric_transition_subsection():
    body = _read(MEMO_REVIEW_MD)
    assert "## Rubric version transition" in body, (
        "memo-review.md step 9b MUST emit a `## Rubric version "
        "transition` subsection in findings.md when the prior rubric "
        "differs (issue #346 AC 5)."
    )


def test_memo_review_step7_documents_score_history_rubric_id_append():
    body = _read(MEMO_REVIEW_MD)
    # AC 2: per-row `rubric_id` stamp on `score_history`.
    assert (
        "score_history" in body
        and "rubric_id" in body
    ), (
        "memo-review.md step 7 MUST document the per-row `rubric_id` "
        "stamp on `score_history` (issue #346 AC 2)."
    )


# ---------------------------------------------------------------------------
# Doc-coverage: proposal-review mirrors the memo-review changes
# ---------------------------------------------------------------------------


def test_proposal_review_step3_stamps_rubric_id():
    body = _read(PROPOSAL_REVIEW_MD)
    assert '"anvil-proposal-v2"' in body, (
        "proposal-review.md step 3 MUST hardcode "
        "`rubric_id: \"anvil-proposal-v2\"` (the proposal skill's "
        "current /44 rubric identifier per `anvil/skills/proposal/"
        "rubric.md` line 3)."
    )


def test_proposal_review_step3_stamps_rubric_total_and_threshold():
    body = _read(PROPOSAL_REVIEW_MD)
    assert "rubric_total" in body and "advance_threshold" in body
    assert "rubric_total: 44" in body or '"rubric_total": 44' in body
    assert "advance_threshold: 35" in body or '"advance_threshold": 35' in body


def test_proposal_review_emits_top_level_rubric_block():
    body = _read(PROPOSAL_REVIEW_MD)
    assert '"rubric": {' in body, (
        "proposal-review.md MUST emit a top-level `rubric` block "
        "in `_summary.md` per issue #346 AC 3."
    )


def test_proposal_review_documents_prior_rubric_surfacing():
    body = _read(PROPOSAL_REVIEW_MD)
    assert "prior_rubric_id" in body
    assert "prior_rubric_inferred" in body
    assert "/40-legacy" in body


# ---------------------------------------------------------------------------
# Snippet-coverage: scorecard_kind.md documents the per-review version
# stamping fields
# ---------------------------------------------------------------------------


def test_scorecard_kind_documents_rubric_id_field():
    body = _read(SCORECARD_KIND_MD)
    assert "rubric_id" in body, (
        "snippets/scorecard_kind.md MUST document the `rubric_id` "
        "discriminator extension per issue #346 AC 1."
    )
    assert "rubric_total" in body
    assert "advance_threshold" in body
    # The backwards-compat clause: legacy reviews tolerate missing
    # `rubric_id` and treat it as `"unknown/legacy"`.
    assert "unknown/legacy" in body or "backwards" in body.lower() or "backwards" in body


def test_scorecard_kind_pins_v2_naming_convention():
    body = _read(SCORECARD_KIND_MD)
    # The snippet documents the convention examples — the memo + proposal
    # /44 rubric ids are `-v2`, the paper /40 is `-v1`.
    assert "anvil-memo-v2" in body
    assert "anvil-proposal-v2" in body or "anvil-pub-v1" in body


# ---------------------------------------------------------------------------
# Snippet-coverage: progress.md documents the per-row `rubric_id` extension
# ---------------------------------------------------------------------------


def test_progress_documents_score_history_rubric_id():
    body = _read(PROGRESS_MD)
    assert "rubric_id" in body, (
        "snippets/progress.md MUST document the per-row `rubric_id` "
        "field on `score_history[]` entries (issue #346 AC 2)."
    )
    # The example shows a `/40 → /44` mid-thread migration.
    assert "anvil-memo-v1" in body or "anvil-memo-v2" in body
    # Backwards-compat clause.
    assert "unknown/legacy" in body or "tolerat" in body.lower()


# ---------------------------------------------------------------------------
# Snippet-coverage: rubric.md no longer hardcodes "/40 invariant" and
# documents per-skill `total` + per-review version stamping
# ---------------------------------------------------------------------------


def test_rubric_snippet_documents_per_skill_total():
    body = _read(RUBRIC_SNIPPET_MD)
    # The reframed prose mentions both /40 and /44 as v0 observed shapes.
    assert "/44" in body, (
        "snippets/rubric.md MUST acknowledge /44 as a valid v0 shape "
        "(the memo + proposal skills ship /44 today)."
    )
    # The "Observed thresholds" table carries memo + proposal at /44.
    obs_idx = body.find("Observed thresholds")
    assert obs_idx >= 0
    obs_section = body[obs_idx:obs_idx + 3000]
    # Both /44 skills surface in the table.
    assert "memo" in obs_section
    assert "proposal" in obs_section
    assert "≥35/44" in obs_section


def test_rubric_snippet_documents_per_review_version_stamping():
    body = _read(RUBRIC_SNIPPET_MD)
    assert "Per-review version stamping" in body, (
        "snippets/rubric.md MUST contain the 'Per-review version "
        "stamping' subsection documenting `_meta.json.rubric_id`, "
        "`score_history[].rubric_id`, and `_summary.md.rubric` block."
    )
    # All three surfaces named. Find the H2 section start (not the
    # cross-reference at line 11 of the file) so the slice reliably
    # covers the section even as the doc grows.
    sec_idx = body.find("## Per-review version stamping")
    assert sec_idx >= 0, "snippets/rubric.md MUST carry the H2 section"
    section = body[sec_idx:sec_idx + 4000]
    assert "_meta.json" in section
    assert "score_history" in section
    assert "_summary.md" in section
    assert "prior_rubric_id" in section


def test_rubric_snippet_drops_hardcoded_40_invariant_in_shape_requirements():
    body = _read(RUBRIC_SNIPPET_MD)
    # Find the "Shape requirements" section.
    shape_idx = body.find("## Shape requirements")
    assert shape_idx >= 0
    # Take the section text (capped at the next ##-heading).
    next_section_idx = body.find("\n## ", shape_idx + 1)
    if next_section_idx < 0:
        next_section_idx = len(body)
    shape_section = body[shape_idx:next_section_idx]
    # The reframed shape requirements name a declared `total` (not
    # hardcoded 40) and accept "8 or 9 dimensions".
    assert "declared" in shape_section.lower() or "`total`" in shape_section
    # Either explicit "8 or 9" or the softer "v0 observed counts" phrasing.
    assert (
        "8 or 9" in shape_section
        or "8 dimensions" in shape_section
        or "v0 observed" in shape_section
    )


# ---------------------------------------------------------------------------
# Fixture-driven schema-of-record contracts
# ---------------------------------------------------------------------------


def test_fixture_dir_present():
    assert FIXTURES.is_dir(), (
        "tests/skills/memo/fixtures/rubric_version_transition/ "
        "MUST exist per issue #346 AC 7."
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

    Iter 1: `anvil-memo-v1-legacy-40` (stamped /40 review).
    Iter 2: `anvil-memo-v2` (stamped /44 review).

    The reader's job is to surface this transition; the fixture pins the
    canonical shape so a downstream consumer can grep for it.
    """
    data = json.loads(
        (FIXTURES / "progress_iter2_stamped.json").read_text()
    )
    rows = data["metadata"]["score_history"]
    assert len(rows) == 2
    assert rows[0]["rubric_id"] == "anvil-memo-v1-legacy-40"
    assert rows[1]["rubric_id"] == "anvil-memo-v2"
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
    assert data["rubric_id"] == "anvil-memo-v1-legacy-40"
    assert data["rubric_total"] == 40
    assert data["advance_threshold"] == 32


def test_fixture_meta_stamped_v2_carries_44_stamp():
    data = json.loads((FIXTURES / "meta_stamped_v2.json").read_text())
    assert data["rubric_id"] == "anvil-memo-v2"
    assert data["rubric_total"] == 44
    assert data["advance_threshold"] == 35


def test_fixture_summary_carries_rubric_block_with_prior_rubric_inferred():
    """Summary fixture shows the legacy-prior-rubric fallback path.

    When the prior review sibling exists but lacks `rubric_id`,
    `prior_rubric_id` resolves to `null` AND the `rubric` block carries
    `prior_rubric_inferred: "/40-legacy"` to signal "this thread's prior
    iteration was scored against the pre-#346 /40 rubric".
    """
    data = json.loads(
        (FIXTURES / "summary_with_rubric_block.json").read_text()
    )
    rubric_block = data["rubric"]
    assert rubric_block["id"] == "anvil-memo-v2"
    assert rubric_block["total"] == 44
    assert rubric_block["advance_threshold"] == 35
    assert rubric_block["dimensions"] == 9
    # The legacy-prior surfacing path.
    assert rubric_block["prior_rubric_id"] is None
    assert rubric_block["prior_rubric_inferred"] == "/40-legacy"


# ---------------------------------------------------------------------------
# Rubric file pinning: memo + proposal /44 rubric line 3
# ---------------------------------------------------------------------------


def test_memo_rubric_md_declares_44_threshold_35():
    body = _read(MEMO_RUBRIC_MD)
    assert "**44**" in body or "/44" in body
    assert "≥35/44" in body or "≥35**" in body


def test_proposal_rubric_md_declares_44_threshold_35():
    body = _read(PROPOSAL_RUBRIC_MD)
    assert "**44**" in body or "/44" in body
    assert "≥35/44" in body or "≥35**" in body
