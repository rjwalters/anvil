"""Tests for ``anvil/lib/operator_feedback.py`` (issue #1322).

The post-READY operator-feedback path: a human read-through that finds a
defect after the critics converged writes ``<thread>.{N}.operator/`` — an
ordinary ``Review`` (``kind: judgment``, ``critic_id: "operator"``,
``verdict: BLOCK``) whose critical flags make ``paper-revise`` step 4's
pre-check require one more revision. No schema change: ``critic_id`` and
``CriticalFlag.type`` are free-form.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib.convergence import PENDING_DEPENDENCY_FLAG_TYPE
from anvil.lib.critics import aggregate, compute_verdict, discover_critics, load_review
from anvil.lib.operator_feedback import (
    BRIEF_AMENDMENT_FLAG_TYPE,
    CRITIC_ID,
    DEFAULT_FLAG_TYPE,
    OPERATOR_SUFFIX,
    build_operator_review,
    main,
    operator_blocking_flags,
    revise_required_by_operator,
    write_operator_review,
)
from anvil.lib.review_schema import CriticalFlag, Kind, Review, Score, Verdict


def _version(tmp_path: Path) -> Path:
    v = tmp_path / "t" / "t.4"
    v.mkdir(parents=True)
    (v / "main.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
    return v


def _flag(t: str = DEFAULT_FLAG_TYPE) -> CriticalFlag:
    return CriticalFlag(
        type=t,
        justification="Sec. 4.4 says 'No replay wave is authorized' — addressed to the operator.",
        evidence_span="main.tex:L120",
    )


def test_build_operator_review_shape():
    review = build_operator_review("t.4", [_flag()])
    assert review.kind == Kind.JUDGMENT
    assert review.critic_id == CRITIC_ID == "operator"
    assert review.verdict == Verdict.BLOCK
    assert [s.score for s in review.scores] == [None]
    empty = build_operator_review("t.4", [])
    assert empty.verdict is None and empty.critical_flags == []


def test_no_sibling_means_no_operator_revision(tmp_path):
    v = _version(tmp_path)
    assert operator_blocking_flags(v) == []
    assert revise_required_by_operator(v) is False


def test_written_sibling_is_discovered_and_blocks(tmp_path):
    v = _version(tmp_path)
    out = write_operator_review(v, build_operator_review(v.name, [_flag()]), notes="Read-through v4.")
    assert out == v.parent / f"{v.name}.{OPERATOR_SUFFIX}"
    for name in ("_review.json", "_meta.json", "operator.md"):
        assert (out / name).is_file()
    meta = json.loads((out / "_meta.json").read_text(encoding="utf-8"))
    assert meta["scorecard_kind"] == "human-verdict"
    assert meta["critic"] == "operator"
    assert "Read-through v4." in (out / "operator.md").read_text(encoding="utf-8")
    assert out in discover_critics(v)
    assert revise_required_by_operator(v) is True
    assert [f.type for f in operator_blocking_flags(v)] == [DEFAULT_FLAG_TYPE]

    # A passing content review + the operator sibling aggregates to BLOCK.
    content = Review(
        schema_version="1",
        kind=Kind.JUDGMENT,
        version_dir=v.name,
        critic_id="review",
        scores=[Score(dimension="content", score=37, max=44, justification="ok")],
        findings=[],
        critical_flags=[],
    )
    agg = aggregate([content, load_review(out)])
    assert agg.total == 37
    assert compute_verdict(agg, threshold=35) == Verdict.BLOCK


def test_operator_sibling_is_immutable(tmp_path):
    v = _version(tmp_path)
    write_operator_review(v, build_operator_review(v.name, [_flag()]))
    with pytest.raises(FileExistsError):
        write_operator_review(v, build_operator_review(v.name, [_flag()]))


def test_pending_typed_flag_does_not_require_revision(tmp_path):
    v = _version(tmp_path)
    write_operator_review(v, build_operator_review(v.name, [_flag(PENDING_DEPENDENCY_FLAG_TYPE)]))
    assert revise_required_by_operator(v) is False


def test_cli_write_and_check(tmp_path, capsys):
    v = _version(tmp_path)
    assert main(["check", str(v)]) == 0
    capsys.readouterr()
    rc = main([
        "write", str(v),
        "--flag", f"{BRIEF_AMENDMENT_FLAG_TYPE}: BRIEF audience narrowed after READY",
        "--flag", "Appendix B cites internal goal numbers",
        "--notes", "Operator read-through of v4.",
    ])
    assert rc == 0
    capsys.readouterr()
    assert main(["check", str(v)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["revise_required"] is True
    assert [f["type"] for f in payload["blocking_flags"]] == [
        BRIEF_AMENDMENT_FLAG_TYPE,
        DEFAULT_FLAG_TYPE,
    ]
    # A second write to the same version is refused (exit 2), not overwritten.
    assert main(["write", str(v), "--flag", "x: y"]) == 2
    assert main(["check", str(tmp_path / "missing.1")]) == 2
