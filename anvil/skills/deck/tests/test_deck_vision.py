"""Tests for the deck-vision critic wiring.

This exercises the deck skill's vision integration against three fixture
decks that reproduce open bugs:

- #23 (mathtext italicization of `$11B` → italic `11B`).
- #24 (vertical overflow on figure + bullets slides).
- #25 (`_class: ask` H1 + H2 + bullets overflow).

The VLM call is stubbed with a callback that simulates the expected
detection. Real Anthropic calls are out of scope for this test (see
``tests/lib/test_vision.py::test_real_anthropic_vlm_smoke`` for the
opt-in smoke path).

Each fixture reproduces the bug pattern at the markdown source level
even though rendered defects cannot literally be observed without
running Marp; the stub callback encodes the expected vision detection
for that fixture's bug family.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

import pytest


# Ensure repo root is importable. This file lives at
# anvil/skills/deck/tests/test_deck_vision.py — four levels deep from
# the repo root.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from anvil.lib.review_schema import Kind, Review  # noqa: E402
from anvil.lib.vision import (  # noqa: E402
    CRITICAL_FLAG_MATHTEXT_ARTIFACT_BREAKS_MEANING,
    CRITICAL_FLAG_RENDERED_OVERFLOW_UNRECOVERABLE,
    DEFAULT_VISION_DIMENSIONS,
    VisionCritic,
    default_vision_rubric,
)


FIXTURES = _HERE / "fixtures" / "vision"


def _clean_score_row(dim_name: str, max: int) -> Dict:
    return {
        "dimension": dim_name,
        "score": max - 1,
        "critical": False,
        "justification": "Default clean score for this fixture.",
        "fix": None,
    }


def _baseline_payload() -> Dict:
    """A "all clean" payload that individual fixtures perturb."""
    return {
        "scores": [
            _clean_score_row(d.name, d.max) for d in DEFAULT_VISION_DIMENSIONS
        ],
        "findings": [],
        "critical_flags": [],
    }


# ---------------------------------------------------------------------------
# Fixture presence
# ---------------------------------------------------------------------------


def test_fixture_decks_present():
    """The three #23/#24/#25 repro decks exist under the fixtures dir."""
    assert (FIXTURES / "repro_23_mathtext.md").exists()
    assert (FIXTURES / "repro_24_figure_plus_bullets.md").exists()
    assert (FIXTURES / "repro_25_ask_h1_h2.md").exists()


# ---------------------------------------------------------------------------
# #23 — mathtext italicization
# ---------------------------------------------------------------------------


def _make_stub_for_23(images, prompt):
    """Stub returning the expected detection for the #23 mathtext repro."""
    payload = _baseline_payload()
    # mathtext_artifacts is the load-bearing dim for #23.
    for s in payload["scores"]:
        if s["dimension"] == "mathtext_artifacts":
            s["score"] = 0
            s["critical"] = True
            s["justification"] = (
                "'$11B' on slide 1 is rendered as italic '11B' (the $ "
                "opens a MathJax math span). Load-bearing semantic loss "
                "for a traction slide."
            )
            s["fix"] = (
                "Escape the dollar sign as `\\$11B` or use a non-dollar "
                "formatting (e.g. 'USD 11B')."
            )
    payload["critical_flags"].append(
        {
            "type": CRITICAL_FLAG_MATHTEXT_ARTIFACT_BREAKS_MEANING,
            "justification": (
                "The ARR figure on the traction slide rendered without "
                "its dollar sign; a sophisticated reader would not parse "
                "the number as a currency amount."
            ),
            "evidence_span": "deck.pdf:slide=1",
        }
    )
    payload["findings"].append(
        {
            "severity": "major",
            "dimension": "mathtext_artifacts",
            "rationale": "Slide 1 'Traction': '$11B' renders as italic '11B'.",
            "suggested_fix": "Escape the dollar or use 'USD 11B'.",
            "evidence_span": "deck.pdf:slide=1",
        }
    )
    return payload


def test_vision_detects_23_mathtext_artifact(tmp_path):
    """AC6: deck-vision asserts expected detections for the #23 repro."""
    fixture_image = tmp_path / "page-1.png"
    fixture_image.write_bytes(b"\x89PNG fake")

    critic = VisionCritic(
        critic_id="deck-vision",
        callback=_make_stub_for_23,
    )
    review = critic.critique(
        images=[fixture_image],
        rubric=default_vision_rubric(),
        version_dir="acme.1",
        rendered_artifact="deck.pdf",
    )

    # mathtext_artifacts dim was scored 0 with critical=True.
    mathtext = next(
        s for s in review.scores if s.dimension == "mathtext_artifacts"
    )
    assert mathtext.score == 0
    assert mathtext.critical is True

    # The critical flag with the expected type is present.
    flags = [cf.type for cf in review.critical_flags]
    assert CRITICAL_FLAG_MATHTEXT_ARTIFACT_BREAKS_MEANING in flags


# ---------------------------------------------------------------------------
# #24 — vertical overflow on figure + bullets
# ---------------------------------------------------------------------------


def _make_stub_for_24(images, prompt):
    payload = _baseline_payload()
    for s in payload["scores"]:
        if s["dimension"] == "vertical_overflow":
            s["score"] = 1
            s["critical"] = True
            s["justification"] = (
                "Slide 1 'Market — TAM / SAM / SOM': figure + 4 bullets + "
                "source line. The source line and the last bullet are "
                "clipped below the safe area."
            )
            s["fix"] = (
                "Move the source line into speaker notes; split into two "
                "slides if the figure stays."
            )
    payload["critical_flags"].append(
        {
            "type": CRITICAL_FLAG_RENDERED_OVERFLOW_UNRECOVERABLE,
            "justification": (
                "The source-attribution line names load-bearing market "
                "data providers; clipping it loses citation context that "
                "an investor would expect to see on the slide."
            ),
            "evidence_span": "deck.pdf:slide=1",
        }
    )
    payload["findings"].append(
        {
            "severity": "blocker",
            "dimension": "vertical_overflow",
            "rationale": (
                "Slide 1 figure + 4 bullets + source line overflows the "
                "16:9 safe area. Source line is fully clipped."
            ),
            "suggested_fix": (
                "Move source line into speaker notes and reduce bullets to 3."
            ),
            "evidence_span": "deck.pdf:slide=1",
        }
    )
    return payload


def test_vision_detects_24_vertical_overflow(tmp_path):
    """AC6: deck-vision asserts expected detections for the #24 repro."""
    fixture_image = tmp_path / "page-1.png"
    fixture_image.write_bytes(b"\x89PNG fake")

    critic = VisionCritic(
        critic_id="deck-vision",
        callback=_make_stub_for_24,
    )
    review = critic.critique(
        images=[fixture_image],
        rubric=default_vision_rubric(),
        version_dir="acme.1",
        rendered_artifact="deck.pdf",
    )

    overflow = next(
        s for s in review.scores if s.dimension == "vertical_overflow"
    )
    assert overflow.score == 1
    assert overflow.critical is True

    flags = [cf.type for cf in review.critical_flags]
    assert CRITICAL_FLAG_RENDERED_OVERFLOW_UNRECOVERABLE in flags


# ---------------------------------------------------------------------------
# #25 — _class: ask H1+H2 overflow
# ---------------------------------------------------------------------------


def _make_stub_for_25(images, prompt):
    payload = _baseline_payload()
    for s in payload["scores"]:
        if s["dimension"] == "vertical_overflow":
            s["score"] = 2
            s["justification"] = (
                "Slide 1 'The Ask' (`_class: ask`): H1 + H2 + 4 bullets + "
                "closing italicized line. Closing line is clipped; bullets "
                "are tight against the safe area."
            )
            s["fix"] = (
                "Drop H2 or move the closing line into the H2 subheading."
            )
        if s["dimension"] == "slide_density":
            s["score"] = 2
            s["justification"] = (
                "Combined density (H1 + H2 + 4 bullets + 1 italic line) "
                "exceeds the 6-element working bar for an ask slide."
            )
    payload["findings"].append(
        {
            "severity": "major",
            "dimension": "vertical_overflow",
            "rationale": (
                "Ask slide H1 + H2 + bullets + closing line exceeds 16:9 "
                "safe area; closing line cropped."
            ),
            "suggested_fix": (
                "Promote the closing line into the H2 subhead and drop the "
                "italics."
            ),
            "evidence_span": "deck.pdf:slide=1",
        }
    )
    payload["findings"].append(
        {
            "severity": "minor",
            "dimension": "slide_density",
            "rationale": "Ask slide is dense for a climactic slide.",
            "suggested_fix": "Compress to 3 bullets.",
            "evidence_span": "deck.pdf:slide=1",
        }
    )
    return payload


def test_vision_detects_25_ask_overflow(tmp_path):
    """AC6: deck-vision asserts expected detections for the #25 repro."""
    fixture_image = tmp_path / "page-1.png"
    fixture_image.write_bytes(b"\x89PNG fake")

    critic = VisionCritic(
        critic_id="deck-vision",
        callback=_make_stub_for_25,
    )
    review = critic.critique(
        images=[fixture_image],
        rubric=default_vision_rubric(),
        version_dir="acme.1",
        rendered_artifact="deck.pdf",
    )

    overflow = next(
        s for s in review.scores if s.dimension == "vertical_overflow"
    )
    assert overflow.score == 2

    density = next(
        s for s in review.scores if s.dimension == "slide_density"
    )
    assert density.score == 2

    # Two findings surface (vertical_overflow major + slide_density minor).
    assert len(review.findings) == 2
    severities = {f.severity for f in review.findings}
    assert "major" in severities
    assert "minor" in severities


# ---------------------------------------------------------------------------
# Command spec presence
# ---------------------------------------------------------------------------


def test_deck_vision_command_spec_exists():
    """AC4: anvil/skills/deck/commands/deck-vision.md is present."""
    cmd = (
        _REPO_ROOT
        / "anvil"
        / "skills"
        / "deck"
        / "commands"
        / "deck-vision.md"
    )
    assert cmd.exists()
    text = cmd.read_text()
    # The six owned dims are documented.
    for d in DEFAULT_VISION_DIMENSIONS:
        assert d.name in text
    # The two shipped critical-flag types are documented.
    assert CRITICAL_FLAG_RENDERED_OVERFLOW_UNRECOVERABLE in text
    assert CRITICAL_FLAG_MATHTEXT_ARTIFACT_BREAKS_MEANING in text
    # The progress/meta shapes are referenced.
    assert "_progress.json" in text
    assert "_meta.json" in text
    assert "_review.json" in text
    # Marp config pin reference.
    assert "config.yml" in text
