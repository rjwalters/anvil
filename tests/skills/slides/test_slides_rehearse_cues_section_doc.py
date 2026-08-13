"""Doc-coverage guard for slides-rehearse Cues/Script + saturation handling (issue #1016).

Guards the four acceptance criteria:
1. `## Cues` section recognition (step 5) with fall-back to full-file word count.
2. The Cues/Script convention documented in slides-rehearse.md, mirrored in
   SKILL.md's slides-rehearse description and the "Density check" note.
3. Short-slot base-tuning guidance in the Heuristic calibration note.
4. A saturated-estimate caveat in the timing.md template.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REHEARSE_DOC = (
    REPO_ROOT / "anvil" / "skills" / "slides" / "commands" / "slides-rehearse.md"
)
SKILL_DOC = REPO_ROOT / "anvil" / "skills" / "slides" / "SKILL.md"
BRIEF_EXAMPLE = REPO_ROOT / "anvil" / "skills" / "slides" / "templates" / "BRIEF.md.example"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- AC1: `## Cues` recognition -------------------------------------------------


def test_rehearse_doc_step_5_recognizes_cues_heading():
    text = _read(REHEARSE_DOC)
    assert "## Cues" in text
    assert "fall back" in text.lower() or "fallback" in text.lower()


def test_rehearse_doc_describes_cues_section_boundary():
    text = _read(REHEARSE_DOC)
    # The section is bounded from the `## Cues` heading to the next `##`
    # heading or EOF — same pattern language as elsewhere in the doc.
    assert "next `##` heading" in text or "next ## heading" in text


# --- AC2: Cues/Script convention documented + mirrored ---------------------------


def test_rehearse_doc_documents_cues_vs_script_convention():
    text = _read(REHEARSE_DOC)
    assert "Cues vs. Script sections" in text
    assert "## Script" in text


def test_skill_doc_mirrors_cues_summary_in_rehearse_description():
    text = _read(SKILL_DOC)
    assert "## Cues" in text


def test_skill_doc_mirrors_cues_summary_in_density_check_note():
    text = _read(SKILL_DOC)
    assert "Cues vs. Script sections" in text


# --- AC3: short-slot base tuning guidance ----------------------------------------


def test_rehearse_doc_documents_short_slot_base_tuning():
    text = _read(REHEARSE_DOC)
    assert "Short-slot base tuning" in text
    assert "time_per_slide_seconds_base" in text


def test_brief_example_points_to_short_slot_guidance():
    text = _read(BRIEF_EXAMPLE)
    assert "time_per_slide_seconds_base" in text


# --- AC4: saturated-estimate caveat in timing.md template -----------------------


def test_rehearse_doc_timing_template_flags_saturated_estimate():
    text = _read(REHEARSE_DOC)
    assert "saturated estimate" in text.lower()
    assert "180s cap" in text or "180-second cap" in text
    # Threshold must be documented, not left implicit.
    assert "more than half" in text.lower() or "majority" in text.lower()
