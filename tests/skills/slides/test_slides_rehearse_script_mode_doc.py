"""Doc-coverage guard for slides-rehearse script mode + the D8 evidence cap (issue #1371)."""

from __future__ import annotations

from pathlib import Path

from anvil.lib.testing import read_text

REPO_ROOT = Path(__file__).resolve().parents[3]
SLIDES = REPO_ROOT / "anvil" / "skills" / "slides"
REHEARSE = SLIDES / "commands" / "slides-rehearse.md"
REVIEW = SLIDES / "commands" / "slides-review.md"
RUBRIC = SLIDES / "rubric.md"


def test_rehearse_documents_script_mode_heading_and_formula():
    text = read_text(REHEARSE)
    assert "## Script (timed core)" in text
    assert "## Transition" in text
    assert "script_words / wpm * 60" in text
    assert "does NOT apply" in text  # 180s cap


def test_rehearse_documents_script_wpm_knob_and_default():
    text = read_text(REHEARSE)
    assert "script_wpm" in text
    assert "130" in text


def test_rehearse_documents_150_wpm_flag_and_mode_column():
    text = read_text(REHEARSE)
    assert "150 wpm" in text
    assert "script|cues|full" in text or "Mode" in text


def test_rehearse_documents_precedence():
    text = read_text(REHEARSE)
    assert "`## Script (timed core)` > `## Cues` > whole-file fallback" in text


def test_d8_cap_wording_in_rubric_and_review():
    for doc in (RUBRIC, REVIEW):
        text = read_text(doc)
        assert "2/3" in text
        assert "aloud_timing_minutes" in text
        assert "timing.md" in text
