"""Doc-coverage tests for the deck-side per-thread ``rubric_overrides``
contract (issue #393): calibration suffixes + dimension waivers.

Pins that:

- ``deck-review.md`` documents the loader step (``load_rubric_overrides_
  for_slug`` against the project-level BRIEF), the promoted suffix helper
  at ``anvil/lib/rubric_overrides_suffix.py``, the waiver-normalized
  verdict math (exact-fraction ``39 x (44 - waived_weight) / 44``), the
  verbatim-rationale surfacing in ``verdict.md``, the nominal ``_meta.json``
  stamping, and the critical-flags-are-not-waivable boundary.
- ``rubric.md`` carries the "Per-thread rubric overrides" section with
  both key families and the normalization contract.

Distinct filename per the issue #58 cross-skill packaging convention.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "deck"

DECK_REVIEW_MD = SKILL_ROOT / "commands" / "deck-review.md"
DECK_RUBRIC_MD = SKILL_ROOT / "rubric.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# deck-review.md — loader step (the memo-review 4h mirror)
# ---------------------------------------------------------------------------


def test_deck_review_documents_loader_step() -> None:
    body = _read(DECK_REVIEW_MD)
    assert "load_rubric_overrides_for_slug" in body
    # Canonical lib path, not the memo shim path.
    assert "anvil/lib/project_brief.py::load_rubric_overrides_for_slug" in body
    # Project dir = parent of the thread root (post-#382 nested model).
    assert "parent of the thread root" in body


def test_deck_review_documents_lenient_empty_state() -> None:
    body = _read(DECK_REVIEW_MD)
    assert "empty `RubricOverrides`" in body
    assert "byte-identical" in body


def test_deck_review_references_promoted_suffix_helper() -> None:
    body = _read(DECK_REVIEW_MD)
    assert "anvil/lib/rubric_overrides_suffix.py" in body
    assert "apply_calibration_to_justification" in body
    assert "calibration applied: " in body


# ---------------------------------------------------------------------------
# deck-review.md — waiver normalization in the verdict (step 12)
# ---------------------------------------------------------------------------


def test_deck_review_documents_waiver_normalization_math() -> None:
    body = _read(DECK_REVIEW_MD)
    assert "dim_N_waiver" in body
    # The exact-fraction normalization contract against the CURRENT
    # /44, >=39 rubric (NOT the issue body's legacy 35/40 figures).
    assert "39 × (44 − waived_weight) / 44" in body
    assert "390/11" in body
    assert "normalized_advance_threshold" in body
    assert "meets_normalized_threshold" in body
    assert "do NOT round" in body or "never a rounded" in body


def test_deck_review_documents_numerator_and_denominator_exclusion() -> None:
    body = _read(DECK_REVIEW_MD)
    assert "BOTH the numerator and the denominator" in body
    assert "total_over_remaining" in body


def test_deck_review_critical_flags_not_waivable() -> None:
    body = _read(DECK_REVIEW_MD)
    assert "Critical flags are NOT waivable" in body
    # The canary boundary example: dim-6 waiver does not suppress the
    # fabricated-credentials flag.
    assert "Fabricated team credentials" in body


def test_deck_review_meta_stamping_stays_nominal() -> None:
    body = _read(DECK_REVIEW_MD)
    assert "stamping stays NOMINAL" in body
    # Stamped values are unchanged by waivers.
    assert "rubric_total: 44" in body or '"rubric_total": 44' in body
    assert "advance_threshold: 39" in body or '"advance_threshold": 39' in body


def test_deck_review_verdict_quotes_waiver_rationale_verbatim() -> None:
    body = _read(DECK_REVIEW_MD)
    assert "Waived dimensions" in body
    assert "verbatim" in body
    # The verdict example states the normalized judgment explicitly.
    assert "waiver-normalized" in body


# ---------------------------------------------------------------------------
# deck-review.md — _summary.md audit block (step 9)
# ---------------------------------------------------------------------------


def test_deck_review_summary_block_shape() -> None:
    body = _read(DECK_REVIEW_MD)
    assert '"rubric_overrides": {' in body
    block_idx = body.find('"rubric_overrides": {')
    block = body[block_idx : block_idx + 1200]
    assert '"ran"' in block
    assert '"calibrations_applied"' in block
    assert '"waivers"' in block
    assert '"waived_weight"' in block


def test_deck_review_summary_block_is_observational_only() -> None:
    body = _read(DECK_REVIEW_MD)
    assert (
        "`rubric_overrides` block does NOT participate in `critical_flag`"
        in body
    )


# ---------------------------------------------------------------------------
# rubric.md — overrides section
# ---------------------------------------------------------------------------


def test_rubric_carries_overrides_section() -> None:
    body = _read(DECK_RUBRIC_MD)
    assert "## Per-thread rubric overrides" in body
    assert "dim_N_calibration" in body
    assert "dim_N_waiver" in body


def test_rubric_documents_rationale_mandatory_and_conflict() -> None:
    body = _read(DECK_RUBRIC_MD)
    assert "REQUIRES a non-empty rationale" in body
    assert "rejected at parse time" in body
    assert "both waived and calibrated" in body


def test_rubric_documents_normalization_and_flag_boundary() -> None:
    body = _read(DECK_RUBRIC_MD)
    assert "39 × (44 − waived_weight) / 44" in body
    assert "390/11" in body
    assert "Critical flags are NOT waivable" in body
    assert "stamping stays nominal" in body


def test_rubric_documents_rationale_as_value_example() -> None:
    body = _read(DECK_RUBRIC_MD)
    assert "dim_6_waiver:" in body
    assert "rationale-as-value" in body
