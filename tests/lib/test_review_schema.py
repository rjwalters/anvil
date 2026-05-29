"""Tests for ``anvil.lib.review_schema``.

Covers:

- Valid load + round-trip of the worked example fixture.
- Partial scorecard (`score: null`) round-trip.
- Schema rejection on missing required fields.
- Score-out-of-bounds rejection.
- Unknown ``verdict`` value rejection.
- ``kind == "vision"`` requires ``rendered_artifact``.
- ``kind == "tool_evidence"`` requires ``tool_calls`` on every finding.
- JSON Schema export round-trip via ``jsonschema``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from anvil.lib.export_schema import build_schema
from anvil.lib.review_schema import (
    SCHEMA_VERSION,
    AggregatedReview,
    CriticalFlag,
    Finding,
    Kind,
    Review,
    Score,
    ToolCall,
    Verdict,
)


EXAMPLE_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "anvil"
    / "lib"
    / "examples"
    / "review-example.json"
)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_example_fixture_loads():
    data = json.loads(EXAMPLE_FIXTURE.read_text())
    review = Review.model_validate(data)
    assert review.schema_version == SCHEMA_VERSION
    assert review.critic_id == "memo-review"
    assert review.verdict == Verdict.REVISE
    assert review.kind == Kind.JUDGMENT
    assert len(review.scores) == 8
    # Dim 5 is unowned by this critic.
    market = next(s for s in review.scores if s.dimension == "market_framing")
    assert market.score is None
    assert market.justification.startswith("n/a")


def test_example_fixture_round_trips():
    data = json.loads(EXAMPLE_FIXTURE.read_text())
    review = Review.model_validate(data)
    redumped = json.loads(review.model_dump_json())
    # Reload and compare structurally.
    review2 = Review.model_validate(redumped)
    assert review == review2


def test_partial_scorecard_null_round_trip():
    review = Review(
        version_dir="thread.1",
        critic_id="specialist",
        scores=[
            Score(dimension="d1", score=None, max=5),
            Score(dimension="d2", score=4, max=5, fix="..."),
        ],
    )
    blob = review.model_dump_json()
    reloaded = Review.model_validate_json(blob)
    assert reloaded.scores[0].score is None
    assert reloaded.scores[1].score == 4


# ---------------------------------------------------------------------------
# Rejection
# ---------------------------------------------------------------------------


def _base_payload() -> dict:
    return {
        "schema_version": "1",
        "kind": "judgment",
        "version_dir": "thread.1",
        "critic_id": "x",
        "scores": [{"dimension": "d", "score": 3, "max": 5, "critical": False}],
    }


def test_missing_required_field_rejected():
    payload = _base_payload()
    del payload["version_dir"]
    with pytest.raises(ValidationError) as ei:
        Review.model_validate(payload)
    assert "version_dir" in str(ei.value)


def test_missing_scores_rejected():
    payload = _base_payload()
    payload["scores"] = []
    with pytest.raises(ValidationError) as ei:
        Review.model_validate(payload)
    assert "scores" in str(ei.value)


def test_score_out_of_bounds_rejected_high():
    payload = _base_payload()
    payload["scores"] = [{"dimension": "d", "score": 99, "max": 5, "critical": False}]
    with pytest.raises(ValidationError) as ei:
        Review.model_validate(payload)
    assert "out of bounds" in str(ei.value)


def test_score_out_of_bounds_rejected_negative():
    payload = _base_payload()
    payload["scores"] = [{"dimension": "d", "score": -1, "max": 5, "critical": False}]
    with pytest.raises(ValidationError) as ei:
        Review.model_validate(payload)
    assert "out of bounds" in str(ei.value)


def test_max_must_be_positive():
    payload = _base_payload()
    payload["scores"] = [{"dimension": "d", "score": 0, "max": 0, "critical": False}]
    with pytest.raises(ValidationError):
        Review.model_validate(payload)


def test_unknown_verdict_rejected():
    payload = _base_payload()
    payload["verdict"] = "MAYBE"
    with pytest.raises(ValidationError) as ei:
        Review.model_validate(payload)
    assert "verdict" in str(ei.value).lower()


def test_unknown_kind_rejected():
    payload = _base_payload()
    payload["kind"] = "telepathy"
    with pytest.raises(ValidationError):
        Review.model_validate(payload)


def test_unknown_severity_rejected():
    payload = _base_payload()
    payload["findings"] = [
        {"severity": "catastrophic", "rationale": "x", "suggested_fix": "y"}
    ]
    with pytest.raises(ValidationError):
        Review.model_validate(payload)


def test_extra_fields_rejected_on_review():
    payload = _base_payload()
    payload["mystery_field"] = 42
    with pytest.raises(ValidationError):
        Review.model_validate(payload)


def test_extra_fields_rejected_on_score():
    payload = _base_payload()
    payload["scores"] = [
        {
            "dimension": "d",
            "score": 3,
            "max": 5,
            "critical": False,
            "rogue": True,
        }
    ]
    with pytest.raises(ValidationError):
        Review.model_validate(payload)


# ---------------------------------------------------------------------------
# kind-conditional validation
# ---------------------------------------------------------------------------


def test_vision_kind_requires_rendered_artifact():
    payload = _base_payload()
    payload["kind"] = "vision"
    with pytest.raises(ValidationError) as ei:
        Review.model_validate(payload)
    assert "rendered_artifact" in str(ei.value)


def test_vision_kind_with_rendered_artifact_ok():
    payload = _base_payload()
    payload["kind"] = "vision"
    payload["rendered_artifact"] = "thread.1/rendered.png"
    review = Review.model_validate(payload)
    assert review.kind == Kind.VISION


def test_tool_evidence_requires_tool_calls_on_findings():
    payload = _base_payload()
    payload["kind"] = "tool_evidence"
    payload["findings"] = [
        {
            "severity": "major",
            "rationale": "x",
            "suggested_fix": "y",
            # tool_calls intentionally missing
        }
    ]
    with pytest.raises(ValidationError) as ei:
        Review.model_validate(payload)
    assert "tool_calls" in str(ei.value)


def test_tool_evidence_with_tool_calls_ok():
    payload = _base_payload()
    payload["kind"] = "tool_evidence"
    payload["findings"] = [
        {
            "severity": "major",
            "rationale": "x",
            "suggested_fix": "y",
            "tool_calls": [{"tool": "grep", "args": {"pattern": "foo"}}],
        }
    ]
    review = Review.model_validate(payload)
    assert review.findings[0].tool_calls[0].tool == "grep"


def test_tool_evidence_no_findings_ok():
    # kind=tool_evidence with empty findings is fine; the validator only
    # enforces tool_calls when there ARE findings.
    payload = _base_payload()
    payload["kind"] = "tool_evidence"
    review = Review.model_validate(payload)
    assert review.kind == Kind.TOOL_EVIDENCE


# ---------------------------------------------------------------------------
# AggregatedReview shape
# ---------------------------------------------------------------------------


def test_aggregated_review_minimal():
    agg = AggregatedReview(
        version_dir="thread.1",
        critic_ids=["a", "b"],
        scores=[Score(dimension="d", score=3, max=5)],
        total=3,
        threshold=32,
        verdict=Verdict.REVISE,
    )
    assert agg.schema_version == SCHEMA_VERSION
    assert agg.verdict == Verdict.REVISE


# ---------------------------------------------------------------------------
# JSON Schema export
# ---------------------------------------------------------------------------


def test_jsonschema_validates_example_fixture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = build_schema()
    data = json.loads(EXAMPLE_FIXTURE.read_text())
    # Validate against the Review subschema specifically (the top-level
    # oneOf accepts either Review or AggregatedReview; we want a hard
    # assertion that the fixture parses as a Review).
    review_subschema = {
        "$ref": "#/$defs/Review",
        "$defs": schema["$defs"],
    }
    jsonschema.validate(data, review_subschema)


def test_jsonschema_rejects_invalid_fixture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = build_schema()
    payload = _base_payload()
    payload["scores"][0]["score"] = 999  # out of bounds (max=5)
    review_subschema = {
        "$ref": "#/$defs/Review",
        "$defs": schema["$defs"],
    }
    # The JSON Schema does not currently encode the cross-field
    # "0 <= score <= max" constraint (pydantic enforces it at runtime via
    # the @model_validator), but it does enforce the type / enum / etc.
    # constraints. Use a different rejection that the JSON Schema CAN see:
    # set verdict to an invalid enum.
    payload["verdict"] = "MAYBE"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, review_subschema)


def test_schema_version_pinned():
    payload = _base_payload()
    payload["schema_version"] = "2"
    with pytest.raises(ValidationError):
        Review.model_validate(payload)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_kind_defaults_to_judgment():
    payload = _base_payload()
    del payload["kind"]
    review = Review.model_validate(payload)
    assert review.kind == Kind.JUDGMENT


def test_critical_defaults_to_false_on_score():
    review = Review.model_validate(
        {
            "version_dir": "t.1",
            "critic_id": "c",
            "scores": [{"dimension": "d", "score": 3, "max": 5}],
        }
    )
    assert review.scores[0].critical is False


def test_total_optional_on_per_critic_review():
    review = Review.model_validate(
        {
            "version_dir": "t.1",
            "critic_id": "c",
            "scores": [{"dimension": "d", "score": 3, "max": 5}],
        }
    )
    assert review.total is None
