"""Tests for ``anvil.lib.vision``.

These tests exercise the VLM critic without ever calling Anthropic — the
``callback=`` injection point bypasses the SDK entirely. The default
six-dimension rubric is exercised end-to-end so we know:

- The returned ``Review`` validates against the canonical schema with
  ``kind=Kind.VISION`` and the required ``rendered_artifact`` set.
- Per-dim ``critical`` flags and top-level ``critical_flags`` both
  surface unchanged through the critic.
- The prompt mentions every rubric dimension and the two shipped
  critical-flag types.
- The default rubric has six dims totaling 30.
- A real Anthropic call is gated behind ``ANVIL_ENABLE_VLM_TESTS=1``
  (the smoke test below is skipped by default).

Per the AC list, the test suite also asserts the stub-driven path
produces output that ``Review.model_validate`` accepts (no schema
violation) and that the aggregator merges the vision review with a
judgment review cleanly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

import pytest
from pydantic import ValidationError

from anvil.lib.critics import (
    CANONICAL_REVIEW_FILENAME,
    aggregate,
    compute_verdict,
    discover_critics,
    load_review,
)
from anvil.lib.review_schema import Kind, Review, Score, Verdict
from anvil.lib.vision import (
    CRITICAL_FLAG_MATHTEXT_ARTIFACT_BREAKS_MEANING,
    CRITICAL_FLAG_RENDERED_OVERFLOW_UNRECOVERABLE,
    DEFAULT_MODEL,
    DEFAULT_VISION_DIMENSIONS,
    VISION_CRITICAL_FLAG_TYPES,
    VisionCritic,
    VisionDimension,
    VisionRubric,
    _parse_json_payload,
    build_prompt,
    default_vision_rubric,
)


# ---------------------------------------------------------------------------
# Default rubric
# ---------------------------------------------------------------------------


def test_default_rubric_has_six_dimensions_totaling_thirty():
    rubric = default_vision_rubric()
    assert len(rubric.dimensions) == 6
    assert rubric.max_total() == 30
    names = [d.name for d in rubric.dimensions]
    assert names == [
        "vertical_overflow",
        "label_cropping",
        "axis_legibility",
        "palette_adherence",
        "mathtext_artifacts",
        "slide_density",
    ]
    # Each dim is /5.
    for d in rubric.dimensions:
        assert d.max == 5


def test_default_rubric_has_a_pinned_rubric_id():
    rubric = default_vision_rubric()
    assert rubric.rubric_id == "anvil-vision-v1"


def test_critical_flag_types_pin_the_two_initial_flags():
    assert CRITICAL_FLAG_RENDERED_OVERFLOW_UNRECOVERABLE in VISION_CRITICAL_FLAG_TYPES
    assert CRITICAL_FLAG_MATHTEXT_ARTIFACT_BREAKS_MEANING in VISION_CRITICAL_FLAG_TYPES
    assert len(VISION_CRITICAL_FLAG_TYPES) == 2


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def test_prompt_mentions_every_rubric_dimension():
    prompt = build_prompt(default_vision_rubric())
    for d in DEFAULT_VISION_DIMENSIONS:
        assert d.name in prompt


def test_prompt_names_both_critical_flag_types():
    prompt = build_prompt(default_vision_rubric())
    assert CRITICAL_FLAG_RENDERED_OVERFLOW_UNRECOVERABLE in prompt
    assert CRITICAL_FLAG_MATHTEXT_ARTIFACT_BREAKS_MEANING in prompt


def test_prompt_includes_optional_context_when_provided():
    prompt = build_prompt(
        default_vision_rubric(), context="12-slide pitch deck"
    )
    assert "12-slide pitch deck" in prompt


def test_prompt_omits_context_section_when_none():
    prompt = build_prompt(default_vision_rubric())
    assert "Context:" not in prompt


# ---------------------------------------------------------------------------
# Stub callback
# ---------------------------------------------------------------------------


def _clean_payload() -> dict:
    return {
        "scores": [
            {"dimension": d.name, "score": d.max - 1, "critical": False,
             "justification": "clean enough",
             "fix": None}
            for d in DEFAULT_VISION_DIMENSIONS
        ],
        "findings": [],
        "critical_flags": [],
    }


def test_critique_returns_validated_vision_review(tmp_path):
    """AC2: VisionCritic.critique() returns a Review with kind=VISION
    and rendered_artifact populated."""
    img = tmp_path / "page-1.png"
    img.write_bytes(b"\x89PNG fake")

    payload = _clean_payload()
    critic = VisionCritic(
        critic_id="deck-vision",
        callback=lambda images, prompt: payload,
    )
    review = critic.critique(
        images=[img],
        rubric=default_vision_rubric(),
        version_dir="acme-seed.1",
        rendered_artifact="deck.pdf",
    )
    assert isinstance(review, Review)
    assert review.kind == Kind.VISION
    assert review.rendered_artifact == "deck.pdf"
    assert review.version_dir == "acme-seed.1"
    assert review.critic_id == "deck-vision"
    assert review.model == DEFAULT_MODEL
    assert review.rubric == "anvil-vision-v1"
    assert review.threshold == 30
    # Six dims, each scored max-1 = 4 -> total 24.
    assert review.total == 24
    assert len(review.scores) == 6


def test_critique_callback_payload_round_trips_through_schema(tmp_path):
    """AC3: the stub-driven Review validates against the canonical schema."""
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    critic = VisionCritic(
        critic_id="deck-vision",
        callback=lambda images, prompt: _clean_payload(),
    )
    review = critic.critique(
        images=[img],
        rubric=default_vision_rubric(),
        version_dir="acme.1",
        rendered_artifact="deck.pdf",
    )
    # Round-trip JSON through model_validate, the same path the file
    # loader uses.
    text = review.model_dump_json()
    parsed = Review.model_validate(json.loads(text))
    assert parsed.kind == Kind.VISION
    assert parsed.rendered_artifact == "deck.pdf"


def test_critique_omits_unspecified_dimensions_as_null(tmp_path):
    """A payload missing a dim entry must produce score=None on that dim."""
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    payload = _clean_payload()
    # Drop the axis_legibility row from the payload.
    payload["scores"] = [
        s for s in payload["scores"] if s["dimension"] != "axis_legibility"
    ]

    critic = VisionCritic(
        critic_id="deck-vision",
        callback=lambda images, prompt: payload,
    )
    review = critic.critique(
        images=[img],
        rubric=default_vision_rubric(),
        version_dir="acme.1",
        rendered_artifact="deck.pdf",
    )
    dims = {s.dimension: s.score for s in review.scores}
    assert dims["axis_legibility"] is None
    # Total drops by 4 (the missing dim's score), so 24 - 4 = 20.
    assert review.total == 20


def test_critique_surfaces_findings(tmp_path):
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    payload = _clean_payload()
    payload["findings"] = [
        {
            "severity": "major",
            "dimension": "vertical_overflow",
            "rationale": "Bottom bullet clipped.",
            "suggested_fix": "Drop the bullet or split the slide.",
            "evidence_span": "deck.pdf:slide=4",
        }
    ]
    critic = VisionCritic(
        critic_id="deck-vision",
        callback=lambda images, prompt: payload,
    )
    review = critic.critique(
        images=[img],
        rubric=default_vision_rubric(),
        version_dir="acme.1",
        rendered_artifact="deck.pdf",
    )
    assert len(review.findings) == 1
    f = review.findings[0]
    assert f.severity == "major"
    assert f.dimension == "vertical_overflow"


def test_critique_surfaces_critical_flag(tmp_path):
    """AC10: a vision review with critical_flags forces Verdict.BLOCK."""
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    payload = _clean_payload()
    payload["critical_flags"] = [
        {
            "type": CRITICAL_FLAG_MATHTEXT_ARTIFACT_BREAKS_MEANING,
            "justification": "Slide 5 shows italic 11B; the dollar sign was lost.",
            "evidence_span": "deck.pdf:slide=5",
        }
    ]
    critic = VisionCritic(
        critic_id="deck-vision",
        callback=lambda images, prompt: payload,
    )
    review = critic.critique(
        images=[img],
        rubric=default_vision_rubric(),
        version_dir="acme.1",
        rendered_artifact="deck.pdf",
    )
    assert len(review.critical_flags) == 1
    assert review.critical_flags[0].type == (
        CRITICAL_FLAG_MATHTEXT_ARTIFACT_BREAKS_MEANING
    )


def test_critique_clamps_out_of_range_scores(tmp_path):
    """Defensive: a model returning a 7/5 must be clamped (or schema fails)."""
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    payload = _clean_payload()
    payload["scores"][0]["score"] = 99  # max=5, but model overshoot.

    critic = VisionCritic(
        critic_id="deck-vision",
        callback=lambda images, prompt: payload,
    )
    review = critic.critique(
        images=[img],
        rubric=default_vision_rubric(),
        version_dir="acme.1",
        rendered_artifact="deck.pdf",
    )
    # The clamp keeps the score at the rubric max (5), not 99.
    first = next(s for s in review.scores if s.dimension == "vertical_overflow")
    assert first.score == 5


def test_critique_rejects_payload_missing_rendered_artifact_field():
    """The schema validator at Review._validate_kind_required_fields
    raises if Kind.VISION is set but rendered_artifact is missing.
    Construction via VisionCritic always supplies it; this test asserts
    the contract by constructing a Review manually."""
    with pytest.raises(ValidationError):
        Review(
            schema_version="1",
            kind=Kind.VISION,
            version_dir="thread.1",
            critic_id="deck-vision",
            scores=[Score(dimension="x", score=3, max=5)],
        )


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def test_parse_json_payload_plain_json():
    payload = _parse_json_payload('{"scores": []}')
    assert payload == {"scores": []}


def test_parse_json_payload_wrapped_in_fence():
    raw = "Here is the JSON:\n```json\n{\"scores\": []}\n```\n"
    payload = _parse_json_payload(raw)
    assert payload == {"scores": []}


def test_parse_json_payload_empty_raises():
    with pytest.raises(ValueError):
        _parse_json_payload("")


def test_parse_json_payload_no_object_raises():
    with pytest.raises(ValueError):
        _parse_json_payload("the model refused to answer")


# ---------------------------------------------------------------------------
# Integration with discovery + aggregation
# ---------------------------------------------------------------------------


def _make_judgment_review(version_dir: str = "acme-seed.1") -> Review:
    """A sibling judgment review to exercise aggregate() merging."""
    return Review(
        schema_version="1",
        kind=Kind.JUDGMENT,
        version_dir=version_dir,
        critic_id="deck-review",
        scores=[
            Score(dimension="1_narrative_arc", score=5, max=6),
            Score(dimension="2_problem_clarity", score=4, max=5),
            Score(dimension="vertical_overflow", score=None, max=5),
        ],
        threshold=35,
    )


def test_aggregator_merges_vision_with_judgment_review(tmp_path):
    """AC5: discover_critics finds .vision/; aggregate merges cleanly."""
    version_dir = tmp_path / "acme-seed.1"
    version_dir.mkdir()

    # Sibling 1: judgment review.
    review_sibling = tmp_path / "acme-seed.1.review"
    review_sibling.mkdir()
    j = _make_judgment_review()
    (review_sibling / CANONICAL_REVIEW_FILENAME).write_text(
        j.model_dump_json(indent=2)
    )

    # Sibling 2: vision review via VisionCritic + stub callback.
    vision_sibling = tmp_path / "acme-seed.1.vision"
    vision_sibling.mkdir()
    img = vision_sibling / "page-1.png"
    img.write_bytes(b"\x89PNG")

    critic = VisionCritic(
        critic_id="deck-vision",
        callback=lambda images, prompt: _clean_payload(),
    )
    vision_review = critic.critique(
        images=[img],
        rubric=default_vision_rubric(),
        version_dir="acme-seed.1",
        rendered_artifact="deck.pdf",
    )
    (vision_sibling / CANONICAL_REVIEW_FILENAME).write_text(
        vision_review.model_dump_json(indent=2)
    )

    # Discover.
    siblings = discover_critics(version_dir)
    sibling_names = sorted(s.name for s in siblings)
    assert sibling_names == ["acme-seed.1.review", "acme-seed.1.vision"]

    # Load.
    reviews = [load_review(s) for s in siblings]
    assert {r.kind for r in reviews} == {Kind.JUDGMENT, Kind.VISION}

    # Aggregate.
    agg = aggregate(reviews)
    # All six vision dims appear in the aggregated scorecard alongside
    # the judgment dims.
    dim_names = [s.dimension for s in agg.scores]
    for d in DEFAULT_VISION_DIMENSIONS:
        assert d.name in dim_names
    assert "1_narrative_arc" in dim_names
    assert "2_problem_clarity" in dim_names


def test_aggregator_block_when_vision_critical_flag_fires(tmp_path):
    """AC10: vision critical flag -> aggregated Verdict.BLOCK."""
    version_dir = tmp_path / "thread.1"
    version_dir.mkdir()

    vision_sibling = tmp_path / "thread.1.vision"
    vision_sibling.mkdir()
    img = vision_sibling / "p.png"
    img.write_bytes(b"\x89PNG")

    payload = _clean_payload()
    payload["critical_flags"] = [
        {
            "type": CRITICAL_FLAG_RENDERED_OVERFLOW_UNRECOVERABLE,
            "justification": "Slide 4 drops the source-data citation.",
        }
    ]
    critic = VisionCritic(
        critic_id="deck-vision",
        callback=lambda images, prompt: payload,
    )
    review = critic.critique(
        images=[img],
        rubric=default_vision_rubric(),
        version_dir="thread.1",
        rendered_artifact="deck.pdf",
    )
    (vision_sibling / CANONICAL_REVIEW_FILENAME).write_text(
        review.model_dump_json(indent=2)
    )

    siblings = discover_critics(version_dir)
    reviews = [load_review(s) for s in siblings]
    agg = aggregate(reviews)
    verdict = compute_verdict(agg)
    assert verdict == Verdict.BLOCK


# ---------------------------------------------------------------------------
# Opt-in real Anthropic smoke test (AC14)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("ANVIL_ENABLE_VLM_TESTS") != "1",
    reason="Real Anthropic VLM call is opt-in; set ANVIL_ENABLE_VLM_TESTS=1.",
)
def test_real_anthropic_vlm_smoke(tmp_path):
    """AC14: Opt-in smoke test that exercises the real Anthropic SDK.

    Skipped unless ANVIL_ENABLE_VLM_TESTS=1 is set. Requires
    ``pip install anthropic`` and a configured API key.
    """
    img = tmp_path / "p.png"
    # A tiny 1x1 PNG. Not visually meaningful but exercises the encode
    # + send path.
    img.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?\x00\x05\xfe\x02"
        b"\xfeA\xc5\x8f\x0c\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    critic = VisionCritic(critic_id="deck-vision")
    review = critic.critique(
        images=[img],
        rubric=default_vision_rubric(),
        version_dir="smoke.1",
        rendered_artifact="page-1.png",
        context="Single 1x1-pixel test image.",
    )
    assert review.kind == Kind.VISION
