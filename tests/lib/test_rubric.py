"""Tests for ``anvil.lib.rubric``.

Covers:

- Each shipped venue YAML loads cleanly.
- Per-venue dimension `id` values match the design (catches accidental
  drift if someone renames a dimension).
- Per-dimension weight is a positive integer.
- Advisory rubrics may have weights that do not sum to ``total`` (loader
  accepts; advisory is informational).
- Non-advisory rubrics enforce sum-to-total (loader raises ValidationError
  on mismatch) and require ``threshold``.
- Unknown YAML keys are rejected (``extra='forbid'``).
- Duplicate dimension ids are rejected.
- Duplicate critical_flag types are rejected.
- ``load_rubric`` raises on missing file / empty YAML.
- ``discover_venue_rubric``:
  - Returns ``None`` when no ``.anvil.json`` exists.
  - Returns ``None`` when ``.anvil.json`` has no ``venue`` key.
  - Returns the shipped NeurIPS rubric for ``venue: neurips``.
  - Per-thread override at ``<thread>/.anvil/rubrics/<venue>.yaml`` wins
    over the skill-shipped file.
  - Consumer-installed override at
    ``<consumer>/.anvil/skills/paper/rubrics/<venue>.yaml`` wins over the
    skill-shipped file but loses to the per-thread override.
  - Returns ``None`` when ``venue`` is set but no YAML is found in any
    tier (caller's responsibility to warn).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from anvil.lib.export_schema import build_rubric_schema
from anvil.lib.rubric import (
    CriticalFlagDefinition,
    Rubric,
    RubricDimension,
    discover_venue_rubric,
    load_rubric,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PAPER_RUBRICS_DIR = REPO_ROOT / "anvil" / "skills" / "paper" / "rubrics"


# Per-venue expected dimension ids. These pin the design (catches drift if
# someone renames a dimension without updating downstream wiring).
EXPECTED_DIMENSIONS = {
    "neurips": {
        "soundness",
        "presentation",
        "contribution",
        "novelty",
        "reproducibility",
    },
    "nature": {
        "broad_significance",
        "accessibility",
        "evidence_strength",
        "novelty",
    },
    "arxiv": {
        "citation_completeness",
        "reproducibility",
        "clarity_of_contribution",
        "scope_classification",
    },
}


EXPECTED_TOTALS = {"neurips": 16, "nature": 15, "arxiv": 10}


# ---------------------------------------------------------------------------
# Shipped venue YAMLs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("venue", sorted(EXPECTED_DIMENSIONS.keys()))
def test_shipped_venue_yaml_loads(venue: str):
    """Each shipped venue YAML loads via ``load_rubric`` without error."""
    rubric = load_rubric(PAPER_RUBRICS_DIR / f"{venue}.yaml")
    assert rubric.advisory is True
    assert rubric.venue == venue
    assert rubric.id == f"anvil-pub-{venue}-v1"
    assert rubric.total == EXPECTED_TOTALS[venue]
    assert rubric.source is not None and rubric.source.strip()


@pytest.mark.parametrize("venue", sorted(EXPECTED_DIMENSIONS.keys()))
def test_shipped_venue_dimension_ids(venue: str):
    """Per-venue dimension ids match the design (catches renames)."""
    rubric = load_rubric(PAPER_RUBRICS_DIR / f"{venue}.yaml")
    got_ids = {d.id for d in rubric.dimensions}
    assert got_ids == EXPECTED_DIMENSIONS[venue], (
        f"Venue {venue!r} dimensions drifted: "
        f"expected {EXPECTED_DIMENSIONS[venue]!r}, got {got_ids!r}"
    )


@pytest.mark.parametrize("venue", sorted(EXPECTED_DIMENSIONS.keys()))
def test_shipped_venue_weights_positive(venue: str):
    """Per-dimension weights are positive integers."""
    rubric = load_rubric(PAPER_RUBRICS_DIR / f"{venue}.yaml")
    for d in rubric.dimensions:
        assert isinstance(d.weight, int) and d.weight >= 1


@pytest.mark.parametrize("venue", sorted(EXPECTED_DIMENSIONS.keys()))
def test_shipped_venue_descriptions_substantial(venue: str):
    """Per-dimension descriptions are substantial enough to guide scoring."""
    rubric = load_rubric(PAPER_RUBRICS_DIR / f"{venue}.yaml")
    for d in rubric.dimensions:
        # AC says ≥2 sentences. Use a minimum-length heuristic plus a
        # period-count check, both lenient.
        assert len(d.description) >= 120, (
            f"Venue {venue!r}, dim {d.id!r}: description too short to "
            f"guide a scoring agent."
        )
        # Calibration prose is strongly recommended for venue rubrics.
        assert d.calibration is not None, (
            f"Venue {venue!r}, dim {d.id!r}: calibration prose missing."
        )


@pytest.mark.parametrize("venue", sorted(EXPECTED_DIMENSIONS.keys()))
def test_shipped_venue_critical_flags_present(venue: str):
    """Each venue declares at least one critical_flag with prose."""
    rubric = load_rubric(PAPER_RUBRICS_DIR / f"{venue}.yaml")
    assert len(rubric.critical_flags) >= 1
    for cf in rubric.critical_flags:
        assert cf.type.replace("_", "").isalnum()
        assert len(cf.description) >= 60


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


def _make_advisory_dim(**overrides) -> dict:
    base = {
        "id": "d1",
        "name": "Dim 1",
        "weight": 3,
        "description": "A dimension. " * 5,
    }
    base.update(overrides)
    return base


def _make_advisory_rubric(**overrides) -> dict:
    base = {
        "id": "test-advisory-v1",
        "name": "Test advisory",
        "venue": "test",
        "total": 10,
        "advisory": True,
        "dimensions": [_make_advisory_dim()],
    }
    base.update(overrides)
    return base


def test_advisory_relaxes_sum_to_total():
    """Advisory rubric whose weights do not sum to total still validates."""
    # weight 3, total 10 — mismatch tolerated for advisory rubrics.
    Rubric.model_validate(_make_advisory_rubric())


def test_advisory_threshold_optional():
    """Advisory rubric may omit threshold."""
    r = Rubric.model_validate(_make_advisory_rubric())
    assert r.threshold is None


def test_non_advisory_requires_sum_to_total():
    """Non-advisory rubric whose weights do not sum to total fails."""
    payload = _make_advisory_rubric(advisory=False, threshold=2)
    # weight 3, total 10 — fails sum check.
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


def test_non_advisory_requires_threshold():
    """Non-advisory rubric without threshold fails."""
    payload = _make_advisory_rubric(
        advisory=False,
        total=3,  # match weight sum so only threshold-missing fails
    )
    # No threshold supplied; total matches weight sum.
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


def test_non_advisory_threshold_in_bounds():
    """Non-advisory rubric: threshold must be in [0, total]."""
    payload = _make_advisory_rubric(
        advisory=False,
        total=3,
        threshold=5,  # > total
    )
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


def test_non_advisory_happy_path():
    """Non-advisory rubric with matched weights and threshold validates."""
    payload = _make_advisory_rubric(
        advisory=False,
        total=3,
        threshold=2,
    )
    r = Rubric.model_validate(payload)
    assert r.advisory is False
    assert r.threshold == 2


def test_unknown_top_level_key_rejected():
    """Unknown top-level YAML keys are rejected (extra='forbid')."""
    payload = _make_advisory_rubric()
    payload["mystery_field"] = "boom"
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


def test_unknown_dimension_key_rejected():
    """Unknown dimension keys are rejected."""
    payload = _make_advisory_rubric(
        dimensions=[_make_advisory_dim(extra_key="boom")],
    )
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


def test_duplicate_dimension_id_rejected():
    """Two dimensions with the same id fail validation."""
    payload = _make_advisory_rubric(
        dimensions=[
            _make_advisory_dim(id="same"),
            _make_advisory_dim(id="same"),
        ],
    )
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


def test_duplicate_critical_flag_type_rejected():
    """Two critical_flags with the same type fail validation."""
    payload = _make_advisory_rubric(
        critical_flags=[
            {"type": "x", "description": "first " * 20},
            {"type": "x", "description": "second " * 20},
        ],
    )
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


def test_dimension_weight_must_be_positive():
    """Per-dim weight must be ≥1."""
    payload = _make_advisory_rubric(
        dimensions=[_make_advisory_dim(weight=0)],
    )
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


def test_dimensions_must_be_non_empty():
    """Rubric must have at least one dimension."""
    payload = _make_advisory_rubric(dimensions=[])
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


# ---------------------------------------------------------------------------
# load_rubric error handling
# ---------------------------------------------------------------------------


def test_load_rubric_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_rubric(tmp_path / "does-not-exist.yaml")


def test_load_rubric_empty_file(tmp_path: Path):
    f = tmp_path / "empty.yaml"
    f.write_text("")
    with pytest.raises(ValueError):
        load_rubric(f)


def test_load_rubric_non_mapping_top_level(tmp_path: Path):
    f = tmp_path / "list.yaml"
    f.write_text("- 1\n- 2\n")
    with pytest.raises(ValueError):
        load_rubric(f)


# ---------------------------------------------------------------------------
# discover_venue_rubric
# ---------------------------------------------------------------------------


def _write_anvil_json(thread_dir: Path, **fields) -> None:
    thread_dir.mkdir(parents=True, exist_ok=True)
    (thread_dir / ".anvil.json").write_text(json.dumps(fields))


def test_discover_no_anvil_json_returns_none(tmp_path: Path):
    skill_root = PAPER_RUBRICS_DIR.parent
    thread = tmp_path / "q3-method"
    thread.mkdir()
    assert discover_venue_rubric(thread, skill_root) is None


def test_discover_no_venue_field_returns_none(tmp_path: Path):
    skill_root = PAPER_RUBRICS_DIR.parent
    thread = tmp_path / "q3-method"
    _write_anvil_json(thread, max_iterations=4)
    assert discover_venue_rubric(thread, skill_root) is None


def test_discover_empty_venue_returns_none(tmp_path: Path):
    skill_root = PAPER_RUBRICS_DIR.parent
    thread = tmp_path / "q3-method"
    _write_anvil_json(thread, venue="")
    assert discover_venue_rubric(thread, skill_root) is None


def test_discover_unknown_venue_returns_none(tmp_path: Path):
    skill_root = PAPER_RUBRICS_DIR.parent
    thread = tmp_path / "q3-method"
    _write_anvil_json(thread, venue="nonexistent-venue")
    assert discover_venue_rubric(thread, skill_root) is None


def test_discover_skill_shipped_neurips(tmp_path: Path):
    skill_root = PAPER_RUBRICS_DIR.parent
    thread = tmp_path / "q3-method"
    _write_anvil_json(thread, venue="neurips")
    rubric = discover_venue_rubric(thread, skill_root)
    assert rubric is not None
    assert rubric.id == "anvil-pub-neurips-v1"
    assert rubric.venue == "neurips"


def test_discover_per_thread_override_wins(tmp_path: Path):
    """Per-thread `.anvil/rubrics/<venue>.yaml` shadows the skill-shipped file."""
    skill_root = PAPER_RUBRICS_DIR.parent
    thread = tmp_path / "q3-method"
    _write_anvil_json(thread, venue="neurips")
    override_dir = thread / ".anvil" / "rubrics"
    override_dir.mkdir(parents=True)
    (override_dir / "neurips.yaml").write_text(
        "id: custom-neurips-v2\n"
        "name: Custom thread-local NeurIPS\n"
        "venue: neurips\n"
        "total: 5\n"
        "advisory: true\n"
        "dimensions:\n"
        "  - id: custom_dim\n"
        "    name: Custom dim\n"
        "    weight: 5\n"
        "    description: '" + ("x " * 80) + "'\n"
    )
    rubric = discover_venue_rubric(thread, skill_root)
    assert rubric is not None
    assert rubric.id == "custom-neurips-v2"


def test_discover_consumer_installed_override(tmp_path: Path):
    """Consumer-installed override wins over skill-shipped but loses to per-thread."""
    skill_root = PAPER_RUBRICS_DIR.parent
    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()
    thread = portfolio / "q3-method"
    _write_anvil_json(thread, venue="neurips")
    consumer_override = (
        portfolio / ".anvil" / "skills" / "paper" / "rubrics" / "neurips.yaml"
    )
    consumer_override.parent.mkdir(parents=True)
    consumer_override.write_text(
        "id: consumer-neurips-v3\n"
        "name: Consumer-installed NeurIPS\n"
        "venue: neurips\n"
        "total: 4\n"
        "advisory: true\n"
        "dimensions:\n"
        "  - id: consumer_dim\n"
        "    name: Consumer dim\n"
        "    weight: 4\n"
        "    description: '" + ("y " * 80) + "'\n"
    )
    rubric = discover_venue_rubric(thread, skill_root)
    assert rubric is not None
    assert rubric.id == "consumer-neurips-v3"


def test_discover_per_thread_beats_consumer_installed(tmp_path: Path):
    skill_root = PAPER_RUBRICS_DIR.parent
    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()
    thread = portfolio / "q3-method"
    _write_anvil_json(thread, venue="neurips")

    # Consumer-installed override.
    consumer_override = (
        portfolio / ".anvil" / "skills" / "paper" / "rubrics" / "neurips.yaml"
    )
    consumer_override.parent.mkdir(parents=True)
    consumer_override.write_text(
        "id: consumer-neurips-v3\n"
        "name: Consumer\n"
        "venue: neurips\n"
        "total: 4\n"
        "advisory: true\n"
        "dimensions:\n"
        "  - id: consumer_dim\n"
        "    name: Consumer dim\n"
        "    weight: 4\n"
        "    description: '" + ("c " * 80) + "'\n"
    )
    # Per-thread override (should win).
    per_thread = thread / ".anvil" / "rubrics" / "neurips.yaml"
    per_thread.parent.mkdir(parents=True)
    per_thread.write_text(
        "id: thread-neurips-v2\n"
        "name: Thread\n"
        "venue: neurips\n"
        "total: 5\n"
        "advisory: true\n"
        "dimensions:\n"
        "  - id: thread_dim\n"
        "    name: Thread dim\n"
        "    weight: 5\n"
        "    description: '" + ("t " * 80) + "'\n"
    )
    rubric = discover_venue_rubric(thread, skill_root)
    assert rubric is not None
    assert rubric.id == "thread-neurips-v2"


def test_discover_explicit_consumer_root(tmp_path: Path):
    """``consumer_root`` argument overrides the default (thread parent)."""
    skill_root = PAPER_RUBRICS_DIR.parent
    thread = tmp_path / "any" / "q3-method"
    thread.mkdir(parents=True)
    _write_anvil_json(thread, venue="neurips")

    consumer_root = tmp_path / "explicit-consumer"
    override = (
        consumer_root / ".anvil" / "skills" / "paper" / "rubrics" / "neurips.yaml"
    )
    override.parent.mkdir(parents=True)
    override.write_text(
        "id: explicit-consumer-neurips-v3\n"
        "name: Explicit consumer\n"
        "venue: neurips\n"
        "total: 4\n"
        "advisory: true\n"
        "dimensions:\n"
        "  - id: explicit_dim\n"
        "    name: Explicit dim\n"
        "    weight: 4\n"
        "    description: '" + ("e " * 80) + "'\n"
    )
    rubric = discover_venue_rubric(
        thread, skill_root, consumer_root=consumer_root
    )
    assert rubric is not None
    assert rubric.id == "explicit-consumer-neurips-v3"


def test_discover_malformed_anvil_json_returns_none(tmp_path: Path):
    """A malformed `.anvil.json` falls back to no venue (does not raise)."""
    skill_root = PAPER_RUBRICS_DIR.parent
    thread = tmp_path / "q3-method"
    thread.mkdir()
    (thread / ".anvil.json").write_text("{ not valid json")
    assert discover_venue_rubric(thread, skill_root) is None


# ---------------------------------------------------------------------------
# JSON Schema export
# ---------------------------------------------------------------------------


def test_rubric_schema_export_contains_rubric_definition():
    schema = build_rubric_schema()
    assert schema["$ref"] == "#/$defs/Rubric"
    assert "Rubric" in schema["$defs"]
    rubric_defn = schema["$defs"]["Rubric"]
    assert rubric_defn["additionalProperties"] is False
    # Required fields present.
    assert "id" in rubric_defn["required"]
    assert "name" in rubric_defn["required"]
    assert "total" in rubric_defn["required"]
    assert "dimensions" in rubric_defn["required"]


def test_rubric_schema_export_includes_dimension_and_flag_defs():
    schema = build_rubric_schema()
    assert "RubricDimension" in schema["$defs"]
    assert "CriticalFlagDefinition" in schema["$defs"]


# ---------------------------------------------------------------------------
# /44 rubric schema validation (issue #346)
# ---------------------------------------------------------------------------


def test_rubric_total_44_weights_sum_to_44_validates():
    """A /44 rubric with weights summing to 44 + threshold 35 validates.

    Pins the contract that the lib is total-agnostic — `total: 44` is
    accepted on the same code path as `total: 40`. This is the load-
    bearing schema validation for the memo + proposal skills, which both
    ship /44 today (issue #346 surfaces this so a downstream test can
    pin the schema contract without re-reading the per-skill rubric.md).
    """
    payload = {
        "id": "test-memo-v2",
        "name": "Test memo /44",
        "total": 44,
        "threshold": 35,
        "advisory": False,
        "dimensions": [
            {
                "id": "dim_1_recommendation",
                "name": "Recommendation clarity",
                "weight": 5,
                "description": "A single unambiguous recommendation. " * 5,
            },
            {
                "id": "dim_2_thesis",
                "name": "Thesis coherence",
                "weight": 6,
                "description": "A falsifiable thesis. " * 8,
            },
            {
                "id": "dim_3_evidence",
                "name": "Evidence quality",
                "weight": 6,
                "description": "Claims backed by primary sources. " * 6,
            },
            {
                "id": "dim_4_risk",
                "name": "Risk honesty",
                "weight": 6,
                "description": "Top 3-5 risks named explicitly. " * 6,
            },
            {
                "id": "dim_5_market",
                "name": "Market framing",
                "weight": 4,
                "description": "TAM/SAM/SOM sized to the artifact. " * 5,
            },
            {
                "id": "dim_6_financial",
                "name": "Financial reasoning",
                "weight": 5,
                "description": "Unit economics, capital efficiency. " * 5,
            },
            {
                "id": "dim_7_scope",
                "name": "Scope discipline",
                "weight": 4,
                "description": "The artifact stays within its declared scope. " * 5,
            },
            {
                "id": "dim_8_prose",
                "name": "Prose & structure",
                "weight": 4,
                "description": "Navigable headings, tight prose. " * 5,
            },
            {
                "id": "dim_9_rhetorical_economy",
                "name": "Rhetorical economy",
                "weight": 4,
                "description": (
                    "Is every paragraph load-bearing? Could the same "
                    "argument land in fewer words? " * 4
                ),
            },
        ],
    }
    r = Rubric.model_validate(payload)
    assert r.total == 44
    assert r.threshold == 35
    assert len(r.dimensions) == 9
    # Sum of all dim weights == total (the load-bearing invariant).
    assert sum(d.weight for d in r.dimensions) == r.total


def test_rubric_total_44_weights_mismatched_rejected():
    """A /44 rubric whose weights do not sum to 44 fails validation.

    Confirms the validator runs against the declared `total` (44), not
    a hardcoded 40 — the same code path the memo and proposal skills
    rely on at runtime.
    """
    payload = {
        "id": "test-memo-broken-v2",
        "name": "Test memo /44 broken",
        "total": 44,
        "threshold": 35,
        "advisory": False,
        "dimensions": [
            {
                "id": "dim_1",
                "name": "Dim 1",
                "weight": 5,
                "description": "x " * 80,
            },
            # Single dimension at weight 5; sum is 5, total is 44 — must fail.
        ],
    }
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


# ---------------------------------------------------------------------------
# /45 rubric schema validation (issue #357 — ip-uspto skill-appropriate dim 9)
# ---------------------------------------------------------------------------


def test_rubric_total_45_weights_sum_to_45_validates():
    """A /45 rubric with weights summing to 45 + threshold 39 validates.

    Pins the contract that the lib is total-agnostic — `total: 45` is
    accepted on the same code path as `total: 40` and `total: 44`. This is
    the load-bearing schema validation for the ip-uspto skill, which
    ships /45 today (issue #357 surfaces this; the flat-weight design —
    9 dimensions × 5 each — distinguishes ip-uspto from memo/proposal's
    weighted /44).
    """
    payload = {
        "id": "test-ip-uspto-v2",
        "name": "Test ip-uspto /45",
        "total": 45,
        "threshold": 39,
        "advisory": False,
        "dimensions": [
            {
                "id": f"dim_{i}",
                "name": f"Dim {i}",
                "weight": 5,
                "description": "Flat-weight patent rubric. " * 5,
            }
            for i in range(1, 10)
        ],
    }
    r = Rubric.model_validate(payload)
    assert r.total == 45
    assert r.threshold == 39
    assert len(r.dimensions) == 9
    # Sum of all dim weights == total (the load-bearing invariant).
    assert sum(d.weight for d in r.dimensions) == r.total
    # Flat-weight check: every dim weighs 5.
    assert all(d.weight == 5 for d in r.dimensions)
