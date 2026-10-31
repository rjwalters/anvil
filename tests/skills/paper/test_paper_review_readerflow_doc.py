"""Prompt-contract guard for the paper-review reader-flow lens (issue #1397).

Pins step 4j of ``paper-review.md``, the dim 7 text in ``rubric.md``, the
``SKILL.md`` sidecar listing, and that a sidecar of the documented shape
validates against ``review_schema`` and is discovered by ``critics``.

Named ``test_paper_review_readerflow_doc.py`` per the #58 filename convention.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.critics import aggregate, discover_critics, load_review
from anvil.lib.review_schema import Finding, Kind, Review, Score
from anvil.lib.testing import read_text as _read

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL = REPO_ROOT / "anvil" / "skills" / "paper"
REVIEW_DOC = SKILL / "commands" / "paper-review.md"
RUBRIC = SKILL / "rubric.md"
SKILL_MD = SKILL / "SKILL.md"


def test_review_step_4j_contract():
    text = _read(REVIEW_DOC)
    assert "4j. **Run the reader-flow lens" in text
    for needle in (
        "fresh-context",
        "no access to this scoring pass",
        ".readerflow/",
        'critic_id: "readerflow"',
        "kind: \"judgment\"",
        "glossary",
        "class 8",
        "reworded-caveats list",
        "Tooling-absent / no-PDF",
        "No declared audience",
    ):
        assert needle in text, needle
    for cls in (
        "define-before-use",
        "naming drift",
        "roadmap order",
        "float proximity",
        "results before objects",
        "repeated caveats",
        "number variants",
    ):
        assert cls in text, cls
    assert "9. **narrative placement**" in text
    assert "every glossary row" in text
    assert "class-1" in text


def test_rubric_documents_class_9_and_glossary_rule():
    text = _read(RUBRIC)
    assert "**Narrative placement**" in text
    assert "Every glossary row" in text


def test_skill_md_lists_class_9():
    assert "class 1-7, 9" in _read(SKILL_MD)


def test_rubric_dim7_names_lens_and_documents_cap():
    text = _read(RUBRIC)
    assert "Reader flow (issue #1397)" in text
    assert "## Reader flow (dim 7)" in text
    assert "cap dim 7 at 2/4" in text


def test_skill_md_lists_sidecar():
    assert "<thread>.1.readerflow/" in _read(SKILL_MD)


def test_sidecar_validates_and_is_discovered(tmp_path):
    version = tmp_path / "paper.1"
    version.mkdir()
    review = Review(
        version_dir="paper.1",
        critic_id="readerflow",
        kind=Kind.JUDGMENT,
        scores=[Score(dimension="7_prose", score=None, max=4)],
        findings=[
            Finding(
                severity="major",
                dimension="7",
                rationale="class 1: 'S18' used in Fig. 2 caption, defined in §4",
                suggested_fix="Define S18 at first use.",
            )
        ],
    )
    sidecar = tmp_path / "paper.1.readerflow"
    sidecar.mkdir()
    (sidecar / "_review.json").write_text(review.model_dump_json(indent=2))
    assert sidecar in discover_critics(version)
    loaded = load_review(sidecar)
    assert loaded.critic_id == "readerflow" and not loaded.critical_flags
    agg = aggregate([loaded])
    assert agg is not None


def test_recurrence_step_and_unchanged_isolation_brief():
    text = _read(REVIEW_DOC)
    assert "Recurrence measure (post-lens, scoring pass only)" in text
    assert "readerflow_recurrence.py" in text
    assert "never passed to the subagent" in text
    # the lens brief keeps its isolation constraint
    assert "Do NOT pass it `scoring.md`, step 4c-4i findings, or any prior review." in text


def test_rubric_documents_recurrence_measure():
    text = _read(RUBRIC)
    assert "recurrence, not finding count" in text
    assert "0.5 or below" in text
    assert "42 -> 31" in text


def test_lens_gets_both_inputs_and_referent_baseline_subrule():
    text = _read(REVIEW_DOC)
    assert "**both** paper inputs" in text
    assert "Referent/baseline sub-rule (#1432)" in text
    assert "every percentage or ratio in the abstract names what it compares" in text
    assert "Do NOT pass it `scoring.md`, step 4c-4i findings, or any prior review." in text
    rubric = _read(RUBRIC)
    assert "Referent/baseline sub-rule (#1432)" in rubric
    assert "referent/baseline sub-rule" in _read(SKILL_MD)


def test_lens_brief_is_source_led():
    text = _read(REVIEW_DOC)
    assert "**source-led (#1437)**" in text
    assert "first read the `\\input` tree front to back" in text
    assert "solely to judge page placement (classes 4 and 9)" in text
    # no longer a PDF-primary, rendered-order read
    assert "using the source only to confirm where a term first appears" not in text
