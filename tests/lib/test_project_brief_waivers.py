"""Waiver-half schema tests for ``anvil.lib.project_brief`` (issue #393).

Issue #393 adds the ``dim_N_waiver`` key family (operator-directed
dimension exclusions, rationale-as-value) to the per-doc
``rubric_overrides:`` block. The calibration half (``dim_N_calibration``)
was already artifact-type-agnostic post-#382/#386 — deck entries carry it
with no schema change — so this file covers:

- waiver parse round-trip on a ``artifact_type: deck`` entry (AC1),
- parse-time rejection of unjustified waivers (AC2),
- waiver+calibration conflict rejection naming both keys (AC3),
- dim-out-of-range and duplicate-waiver rejection,
- ``is_empty`` / ``waiver_for`` accessors,
- a deck-typed entry carrying ``dim_N_calibration`` (the "schema already
  done" half, pinned here as the deck regression anchor),
- byte-identical empty-state behavior for waiver-free entries (AC6).

This file is a deliberate sibling of ``tests/lib/test_project_brief.py``
(distinct filename per the issue #58 packaging convention, and to keep the
waiver corpus mergeable alongside concurrent ``project_brief`` work).
"""

from __future__ import annotations

import textwrap
import warnings
from pathlib import Path

import pytest

from anvil.lib.project_brief import (
    RubricOverrides,
    WaiverOverride,
    load_project_brief,
    load_rubric_overrides_for_slug,
)
from anvil.lib.project_discovery import BRIEF_FILENAME


WAIVER_RATIONALE = (
    "Operator directive 2026-06-09: no team content in this deck; "
    "team story lives in team-thesis.latest."
)


def _write_brief(project: Path, frontmatter: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / BRIEF_FILENAME).write_text(
        f"---\n{textwrap.dedent(frontmatter)}---\n\n# BRIEF\n",
        encoding="utf-8",
    )


def _deck_brief(project: Path, rubric_overrides_yaml: str) -> None:
    _write_brief(
        project,
        f"""\
        project: proj
        documents:
          - slug: series-a-deck
            artifact_type: deck
            rubric_overrides:
{textwrap.indent(textwrap.dedent(rubric_overrides_yaml), "              ")}
        """,
    )


# ---------------------------------------------------------------------------
# AC1 — waiver parse round-trip (deck entry, rationale-as-value)
# ---------------------------------------------------------------------------


def test_deck_waiver_parses_to_typed_waiver(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _deck_brief(project, f'dim_6_waiver: "{WAIVER_RATIONALE}"\n')

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # no unknown-key warning allowed
        overrides = load_rubric_overrides_for_slug(project, "series-a-deck")

    assert overrides.waivers == [
        WaiverOverride(dimension=6, rationale=WAIVER_RATIONALE)
    ]
    assert overrides.unknown_keys == {}
    assert not overrides.is_empty
    assert overrides.waiver_for(6) == WAIVER_RATIONALE
    assert overrides.waiver_for(1) is None


def test_multiple_waivers_sorted_by_dimension(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _deck_brief(
        project,
        'dim_8_waiver: "rendered-design waived: text-only teaser deck"\n'
        f'dim_6_waiver: "{WAIVER_RATIONALE}"\n',
    )
    overrides = load_rubric_overrides_for_slug(project, "series-a-deck")
    assert [w.dimension for w in overrides.waivers] == [6, 8]


# ---------------------------------------------------------------------------
# AC2 — unjustified waiver rejected at parse time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ['""', '"   "', "true", "3", "null"])
def test_waiver_without_rationale_rejected(tmp_path: Path, value: str) -> None:
    project = tmp_path / "proj"
    _deck_brief(project, f"dim_6_waiver: {value}\n")
    with pytest.raises(ValueError, match=r"dim_6_waiver"):
        load_project_brief(project)


# ---------------------------------------------------------------------------
# AC3 — waiver + calibration on the same dim rejected, naming both keys
# ---------------------------------------------------------------------------


def test_waiver_calibration_conflict_rejected_naming_both_keys(
    tmp_path: Path,
) -> None:
    project = tmp_path / "proj"
    _deck_brief(
        project,
        f'dim_6_waiver: "{WAIVER_RATIONALE}"\n'
        'dim_6_calibration: "score team on advisors only"\n',
    )
    with pytest.raises(ValueError) as exc_info:
        load_project_brief(project)
    message = str(exc_info.value)
    assert "dim_6_waiver" in message
    assert "dim_6_calibration" in message


def test_waiver_and_calibration_on_different_dims_coexist(
    tmp_path: Path,
) -> None:
    project = tmp_path / "proj"
    _deck_brief(
        project,
        f'dim_6_waiver: "{WAIVER_RATIONALE}"\n'
        'dim_5_calibration: "pre-revenue: score traction on pilots"\n',
    )
    overrides = load_rubric_overrides_for_slug(project, "series-a-deck")
    assert overrides.waiver_for(6) == WAIVER_RATIONALE
    assert overrides.calibration_for(5) == "pre-revenue: score traction on pilots"


# ---------------------------------------------------------------------------
# Shape errors — range / duplicates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["dim_0_waiver", "dim_10_waiver"])
def test_waiver_dimension_out_of_range_rejected(tmp_path: Path, key: str) -> None:
    project = tmp_path / "proj"
    _deck_brief(project, f'{key}: "some rationale"\n')
    with pytest.raises(ValueError, match=r"out\s+of\s+range"):
        load_project_brief(project)


def test_waiver_key_not_swallowed_by_unknown_keys(tmp_path: Path) -> None:
    """Regression anchor: pre-#393 a ``dim_N_waiver`` key fell into the
    lenient ``unknown_keys`` passthrough with a UserWarning and was never
    applied. Post-#393 it parses as a typed waiver — no warning."""
    project = tmp_path / "proj"
    _deck_brief(project, f'dim_6_waiver: "{WAIVER_RATIONALE}"\n')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        overrides = load_rubric_overrides_for_slug(project, "series-a-deck")
    assert overrides.unknown_keys == {}
    assert not any("unknown key" in str(w.message) for w in caught)


# ---------------------------------------------------------------------------
# Calibration half — deck entry carries dim_N_calibration (already-works pin)
# ---------------------------------------------------------------------------


def test_deck_entry_carries_calibration(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _deck_brief(
        project,
        'dim_5_calibration: "pre-revenue pilot-stage deck — score traction '
        'on pilot conversion evidence, not revenue"\n',
    )
    overrides = load_rubric_overrides_for_slug(project, "series-a-deck")
    assert overrides.calibration_for(5) is not None
    assert overrides.waivers == []


# ---------------------------------------------------------------------------
# AC6 — empty-state / zero-impact fast path
# ---------------------------------------------------------------------------


def test_deck_without_overrides_is_empty_instance(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: series-a-deck
            artifact_type: deck
        """,
    )
    overrides = load_rubric_overrides_for_slug(project, "series-a-deck")
    assert overrides.is_empty
    assert overrides.waivers == []
    assert overrides.waiver_for(6) is None


def test_is_empty_false_when_only_waivers_present() -> None:
    overrides = RubricOverrides(
        waivers=[WaiverOverride(dimension=6, rationale="x")]
    )
    assert not overrides.is_empty


def test_waiver_model_rejects_empty_rationale() -> None:
    with pytest.raises(Exception):
        WaiverOverride(dimension=6, rationale="")
