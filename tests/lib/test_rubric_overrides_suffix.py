"""Canonical-path tests for ``anvil.lib.rubric_overrides_suffix`` (issue #393).

Promoted from ``anvil/skills/memo/lib/`` when ``anvil:deck`` became the
second consumer (per-thread rubric_overrides / dimension waivers, issue
#393). The full calibration-suffix behavioral corpus lives at
``anvil/skills/memo/tests/test_rubric_overrides_suffix_wiring.py`` and
continues to run against the canonical implementation through the memo
back-compat shim. This file pins:

- the promotion contracts (canonical import path + shim identity,
  mirroring ``tests/lib/test_project_brief.py``'s #382 shim tests),
- representative calibration-suffix behavior at the canonical path,
- the waiver normalization math (exact-``Fraction`` threshold scaling),
  net-new under #393.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from anvil.lib.project_brief import RubricOverrides, WaiverOverride
from anvil.lib.rubric_overrides_suffix import (
    CALIBRATION_PREFIX,
    apply_calibration_to_justification,
    meets_normalized_threshold,
    normalized_advance_threshold,
    waived_weight_for,
)


# Deck rubric weights per ``anvil/skills/deck/rubric.md`` (/44, >=39).
DECK_WEIGHTS = {1: 6, 2: 5, 3: 5, 4: 5, 5: 5, 6: 4, 7: 5, 8: 5, 9: 4}


# ---------------------------------------------------------------------------
# Promotion contracts (shim identity)
# ---------------------------------------------------------------------------


def test_memo_shim_reexports_same_objects() -> None:
    from anvil.skills.memo.lib import rubric_overrides_suffix as shim

    assert (
        shim.apply_calibration_to_justification
        is apply_calibration_to_justification
    )
    assert shim.CALIBRATION_PREFIX == CALIBRATION_PREFIX
    assert shim.normalized_advance_threshold is normalized_advance_threshold
    assert shim.meets_normalized_threshold is meets_normalized_threshold
    assert shim.waived_weight_for is waived_weight_for


def test_calibration_suffix_verbatim_at_canonical_path() -> None:
    overrides = RubricOverrides.model_validate(
        {"calibrations": [{"dimension": 6, "text": "score advisors only"}]}
    )
    out = apply_calibration_to_justification("Bios specific.", overrides, 6)
    assert out == "Bios specific. calibration applied: score advisors only"
    # Zero-impact on non-calibrated dims.
    assert apply_calibration_to_justification("x", overrides, 2) == "x"


# ---------------------------------------------------------------------------
# Waiver normalization math (issue #393)
# ---------------------------------------------------------------------------


def test_normalized_threshold_dim6_waived_is_exact_fraction() -> None:
    # Deck rubric, dim 6 (weight 4) waived: 39 * 40 / 44 = 390/11.
    threshold = normalized_advance_threshold(39, 44, 4)
    assert threshold == Fraction(390, 11)
    assert threshold != Fraction(3545, 100)  # NOT the rounded 35.45


def test_normalized_threshold_zero_waived_is_nominal() -> None:
    assert normalized_advance_threshold(39, 44, 0) == Fraction(39)


def test_meets_normalized_threshold_around_the_exact_boundary() -> None:
    # 390/11 ~= 35.4545...: 36/40 advances, 35/40 and 35.4/40 do not,
    # 35.5/40 does. The comparison is exact-fraction, not rounded-float.
    assert meets_normalized_threshold(36, 39, 44, 4) is True
    assert meets_normalized_threshold(35, 39, 44, 4) is False
    assert meets_normalized_threshold(35.4, 39, 44, 4) is False
    assert meets_normalized_threshold(35.5, 39, 44, 4) is True
    assert meets_normalized_threshold(Fraction(390, 11), 39, 44, 4) is True


def test_meets_nominal_threshold_when_no_waivers() -> None:
    assert meets_normalized_threshold(39, 39, 44, 0) is True
    assert meets_normalized_threshold(38.9, 39, 44, 0) is False


@pytest.mark.parametrize("waived", [-1, 44, 45])
def test_waived_weight_bounds_rejected(waived: int) -> None:
    with pytest.raises(ValueError):
        normalized_advance_threshold(39, 44, waived)


def test_waived_weight_for_sums_deck_weights() -> None:
    overrides = RubricOverrides(
        waivers=[
            WaiverOverride(dimension=6, rationale="no team content"),
            WaiverOverride(dimension=8, rationale="text-only teaser"),
        ]
    )
    assert waived_weight_for(overrides, DECK_WEIGHTS) == 4 + 5


def test_waived_weight_for_zero_impact_paths() -> None:
    assert waived_weight_for(None, DECK_WEIGHTS) == 0
    assert waived_weight_for(RubricOverrides(), DECK_WEIGHTS) == 0


def test_waived_weight_for_unknown_dimension_rejected() -> None:
    overrides = RubricOverrides(
        waivers=[WaiverOverride(dimension=9, rationale="r")]
    )
    with pytest.raises(ValueError):
        waived_weight_for(overrides, {1: 6, 2: 5})


def test_acceptance_scenario_dim6_waived_otherwise_passing() -> None:
    """AC4 of #393: deck with dim 6 waived and otherwise-passing dims
    reaches advance at the normalized threshold.

    Owned scores summing to 36 over the remaining /40 pool clear
    390/11 ~= 35.45; the same deck at 35/40 (the canary's 33-ish shape
    rescaled) does not.
    """
    waived = waived_weight_for(
        RubricOverrides(
            waivers=[WaiverOverride(dimension=6, rationale="operator directive")]
        ),
        DECK_WEIGHTS,
    )
    assert waived == 4
    assert meets_normalized_threshold(36, 39, 44, waived) is True
    assert meets_normalized_threshold(35, 39, 44, waived) is False
