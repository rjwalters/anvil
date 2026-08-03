"""Tests for the perishable-claim freshness advisory (issue #863).

Covers the three legs of the issue's acceptance criteria:

- the ``Probe`` / ``ProbeLog`` contract parses from both carriers
  (``probes.json`` and ``Review.probes``);
- a pass over an older version surfaces stale + never-re-probed claims;
- pre-#863 critic siblings without any probe record are tolerated and
  reported as unknown freshness, never as a defect or an error.

The censusapi reproducer at the bottom replays the canary incident that
motivated the issue: a clean audit whose verified claims were false a day
later.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from anvil.lib.probe_freshness import (
    DEFAULT_MAX_AGE_DAYS,
    REPORT_CLEAN,
    REPORT_NEEDS_REPROBE,
    REPORT_NO_PROBES,
    STATUS_FRESH,
    STATUS_NOT_REPROBED,
    STATUS_STALE,
    check_probe_freshness,
    collect_probes,
    find_unknown_freshness_siblings,
    main,
)
from anvil.lib.review_schema import Probe, ProbeLog, Review, Score

NOW = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def _probe(target: str, days_ago: float = 0.0, **kw) -> dict:
    row = {
        "target": target,
        "method": "http_status",
        "observed": "200",
        "checked_at": _iso(days_ago),
    }
    row.update(kw)
    return row


def _write_probe_log(critic_dir: Path, version_dir: str, probes: list) -> None:
    critic_dir.mkdir(parents=True, exist_ok=True)
    (critic_dir / "probes.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "version_dir": version_dir,
                "critic_id": "proposal-audit",
                "probes": probes,
            }
        ),
        encoding="utf-8",
    )


def _write_prose_audit(critic_dir: Path) -> None:
    """A pre-#863 audit sibling: prose findings, no probe record."""
    critic_dir.mkdir(parents=True, exist_ok=True)
    (critic_dir / "findings.md").write_text("| 1 | §7 | ... |\n", encoding="utf-8")
    (critic_dir / "verdict.md").write_text("pass: true\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------


def test_probe_requires_the_four_load_bearing_fields():
    for missing in ("target", "method", "observed", "checked_at"):
        row = _probe("https://example.org/x")
        row.pop(missing)
        with pytest.raises(ValidationError):
            Probe.model_validate(row)


def test_probe_rejects_an_unparseable_timestamp():
    """A probe that looks fresh to a reader but is uncheckable by a tool is
    worse than no probe at all."""
    with pytest.raises(ValidationError):
        Probe.model_validate(_probe("https://example.org/x", checked_at="last Tuesday"))


def test_probe_accepts_both_z_and_offset_timestamps():
    assert Probe.model_validate(
        _probe("https://a", checked_at="2026-08-01T14:03:00Z")
    ).checked_at.endswith("Z")
    assert Probe.model_validate(
        _probe("https://a", checked_at="2026-08-01T14:03:00+00:00")
    )


def test_probe_log_empty_probes_is_valid():
    """An empty list is the auditor declaring the artifact durable-only."""
    log = ProbeLog(version_dir="memo.1", critic_id="memo-audit")
    assert log.probes == []


def test_review_probes_defaults_to_none_and_is_optional_for_tool_evidence():
    """Backward compatibility: a pre-#863 tool_evidence review still validates."""
    review = Review(
        kind="tool_evidence",
        version_dir="memo.1",
        critic_id="memo-audit",
        scores=[Score(dimension="evidence", score=4, max=5)],
    )
    assert review.probes is None
    assert "probes" not in review.model_dump(exclude_none=True)


def test_review_accepts_probes_when_present():
    review = Review(
        kind="tool_evidence",
        version_dir="memo.1",
        critic_id="memo-audit",
        scores=[Score(dimension="evidence", score=4, max=5)],
        probes=[Probe.model_validate(_probe("https://example.org/x"))],
    )
    assert review.probes[0].target == "https://example.org/x"


# ---------------------------------------------------------------------------
# Collection across both carriers
# ---------------------------------------------------------------------------


def test_collect_probes_reads_the_standalone_probe_log(tmp_path):
    _write_probe_log(tmp_path / "lan.1.audit", "lan.1", [_probe("https://a")])
    collected = collect_probes(tmp_path)
    assert [c.probe.target for c in collected] == ["https://a"]
    assert collected[0].version == 1
    assert collected[0].version_dir == "lan.1"


def test_collect_probes_reads_review_json_probes(tmp_path):
    critic = tmp_path / "lan.1.audit"
    critic.mkdir(parents=True)
    review = Review(
        kind="tool_evidence",
        version_dir="lan.1",
        critic_id="lan-audit",
        scores=[Score(dimension="d", score=4, max=5)],
        probes=[Probe.model_validate(_probe("https://b"))],
    )
    (critic / "_review.json").write_text(review.model_dump_json(), encoding="utf-8")
    assert [c.probe.target for c in collect_probes(tmp_path)] == ["https://b"]


def test_collect_probes_unions_both_carriers_without_duplicating(tmp_path):
    critic = tmp_path / "lan.1.audit"
    shared = _probe("https://a")
    _write_probe_log(critic, "lan.1", [shared])
    review = Review(
        kind="tool_evidence",
        version_dir="lan.1",
        critic_id="lan-audit",
        scores=[Score(dimension="d", score=4, max=5)],
        probes=[
            Probe.model_validate(shared),
            Probe.model_validate(_probe("https://c")),
        ],
    )
    (critic / "_review.json").write_text(review.model_dump_json(), encoding="utf-8")
    assert sorted(c.probe.target for c in collect_probes(tmp_path)) == [
        "https://a",
        "https://c",
    ]


def test_collect_probes_skips_a_malformed_row_but_keeps_the_rest(tmp_path):
    _write_probe_log(
        tmp_path / "lan.1.audit",
        "lan.1",
        [{"target": "https://broken"}, _probe("https://ok")],
    )
    assert [c.probe.target for c in collect_probes(tmp_path)] == ["https://ok"]


def test_collect_probes_tolerates_unreadable_json(tmp_path):
    critic = tmp_path / "lan.1.audit"
    critic.mkdir(parents=True)
    (critic / "probes.json").write_text("{not json", encoding="utf-8")
    assert collect_probes(tmp_path) == []


def test_collect_probes_ignores_a_version_dir_and_the_thread_root(tmp_path):
    (tmp_path / "lan.1").mkdir()
    _write_probe_log(tmp_path / "lan.1.audit", "lan.1", [_probe("https://a")])
    assert len(collect_probes(tmp_path)) == 1


def test_collect_probes_on_a_missing_thread_dir_is_empty(tmp_path):
    assert collect_probes(tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# Freshness classification
# ---------------------------------------------------------------------------


def test_recent_probe_against_the_current_version_is_fresh(tmp_path):
    _write_probe_log(tmp_path / "lan.2.audit", "lan.2", [_probe("https://a", 1)])
    report = check_probe_freshness(tmp_path / "lan.2", now=NOW)
    assert report.status == REPORT_CLEAN
    assert [s.status for s in report.statuses] == [STATUS_FRESH]
    assert report.needs_reprobe == []


def test_probe_older_than_the_budget_is_stale(tmp_path):
    _write_probe_log(
        tmp_path / "lan.2.audit", "lan.2", [_probe("https://a", DEFAULT_MAX_AGE_DAYS + 1)]
    )
    report = check_probe_freshness(tmp_path / "lan.2", now=NOW)
    assert report.status == REPORT_NEEDS_REPROBE
    assert report.statuses[0].status == STATUS_STALE
    assert [s.target for s in report.needs_reprobe] == ["https://a"]


def test_per_probe_max_age_days_overrides_the_default(tmp_path):
    _write_probe_log(
        tmp_path / "lan.2.audit",
        "lan.2",
        [_probe("https://quote", 3, max_age_days=2)],
    )
    report = check_probe_freshness(tmp_path / "lan.2", now=NOW)
    assert report.statuses[0].status == STATUS_STALE
    assert report.statuses[0].max_age_days == 2


def test_a_generous_per_probe_budget_keeps_an_old_probe_fresh(tmp_path):
    _write_probe_log(
        tmp_path / "lan.2.audit",
        "lan.2",
        [_probe("https://slow", 30, max_age_days=90)],
    )
    assert check_probe_freshness(tmp_path / "lan.2", now=NOW).status == REPORT_CLEAN


def test_probe_from_an_earlier_version_is_not_reprobed(tmp_path):
    """AC3: a pass over a newer version surfaces claims carried forward
    on the strength of an older verification."""
    _write_probe_log(tmp_path / "lan.1.audit", "lan.1", [_probe("https://a", 1)])
    report = check_probe_freshness(tmp_path / "lan.2", now=NOW)
    assert report.status == REPORT_NEEDS_REPROBE
    assert report.statuses[0].status == STATUS_NOT_REPROBED
    assert "version 1" in report.statuses[0].detail


def test_a_reprobe_in_the_current_version_clears_the_older_record(tmp_path):
    _write_probe_log(tmp_path / "lan.1.audit", "lan.1", [_probe("https://a", 20)])
    _write_probe_log(tmp_path / "lan.2.audit", "lan.2", [_probe("https://a", 1)])
    report = check_probe_freshness(tmp_path / "lan.2", now=NOW)
    assert report.status == REPORT_CLEAN
    assert len(report.statuses) == 1
    assert report.statuses[0].version == 2


def test_newest_probe_wins_per_target(tmp_path):
    _write_probe_log(
        tmp_path / "lan.2.audit",
        "lan.2",
        [_probe("https://a", 30, observed="404"), _probe("https://a", 1, observed="200")],
    )
    report = check_probe_freshness(tmp_path / "lan.2", now=NOW)
    assert report.statuses[0].probe.observed == "200"
    assert report.statuses[0].status == STATUS_FRESH


def test_statuses_are_sorted_by_target_for_deterministic_output(tmp_path):
    _write_probe_log(
        tmp_path / "lan.1.audit",
        "lan.1",
        [_probe("https://z"), _probe("https://a"), _probe("https://m")],
    )
    report = check_probe_freshness(tmp_path / "lan.1", now=NOW)
    assert [s.target for s in report.statuses] == [
        "https://a",
        "https://m",
        "https://z",
    ]


def test_explicit_thread_dir_overrides_the_parent(tmp_path):
    thread = tmp_path / "threads" / "lan"
    _write_probe_log(thread / "lan.1.audit", "lan.1", [_probe("https://a", 1)])
    report = check_probe_freshness(
        tmp_path / "elsewhere" / "lan.1", now=NOW, thread_dir=thread
    )
    assert report.status == REPORT_CLEAN


def test_naive_now_is_treated_as_utc(tmp_path):
    _write_probe_log(tmp_path / "lan.1.audit", "lan.1", [_probe("https://a", 1)])
    report = check_probe_freshness(
        tmp_path / "lan.1", now=datetime(2026, 8, 2, 12, 0, 0)
    )
    assert report.status == REPORT_CLEAN


# ---------------------------------------------------------------------------
# Backward compatibility (AC5)
# ---------------------------------------------------------------------------


def test_a_thread_with_no_probes_reports_no_probes_not_clean(tmp_path):
    _write_prose_audit(tmp_path / "lan.1.audit")
    report = check_probe_freshness(tmp_path / "lan.1", now=NOW)
    assert report.status == REPORT_NO_PROBES
    assert report.statuses == []
    assert "unknown" in report.detail


def test_a_markerless_audit_sibling_is_reported_as_unknown_freshness(tmp_path):
    _write_prose_audit(tmp_path / "lan.1.audit")
    _write_probe_log(tmp_path / "lan.1.corpus-audit", "lan.1", [_probe("https://a", 1)])
    report = check_probe_freshness(tmp_path / "lan.1", now=NOW)
    assert report.unknown_freshness == ["lan.1.audit"]
    assert report.status == REPORT_CLEAN


def test_an_empty_probe_list_is_not_unknown_freshness(tmp_path):
    """'I looked; nothing is perishable' must not read as 'never looked'."""
    _write_probe_log(tmp_path / "lan.1.audit", "lan.1", [])
    report = check_probe_freshness(tmp_path / "lan.1", now=NOW)
    assert report.unknown_freshness == []
    assert report.status == REPORT_NO_PROBES


def test_a_judgment_review_sibling_is_not_flagged_unknown(tmp_path):
    """Only audit-class siblings are expected to carry probes."""
    critic = tmp_path / "lan.1.review"
    critic.mkdir(parents=True)
    review = Review(
        version_dir="lan.1",
        critic_id="lan-review",
        scores=[Score(dimension="d", score=4, max=5)],
    )
    (critic / "_review.json").write_text(review.model_dump_json(), encoding="utf-8")
    assert find_unknown_freshness_siblings(tmp_path) == []


def test_a_tool_evidence_review_without_probes_is_flagged_unknown(tmp_path):
    critic = tmp_path / "lan.1.numbers"
    critic.mkdir(parents=True)
    review = Review(
        kind="tool_evidence",
        version_dir="lan.1",
        critic_id="lan-numbers",
        scores=[Score(dimension="d", score=4, max=5)],
    )
    (critic / "_review.json").write_text(review.model_dump_json(), encoding="utf-8")
    assert find_unknown_freshness_siblings(tmp_path) == ["lan.1.numbers"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_prints_json_and_exits_zero_even_when_stale(tmp_path, capsys):
    _write_probe_log(tmp_path / "lan.1.audit", "lan.1", [_probe("https://a", 99)])
    code = main([str(tmp_path / "lan.1"), "--now", _iso(0)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == REPORT_NEEDS_REPROBE
    assert payload["needs_reprobe"][0]["target"] == "https://a"


def test_cli_max_age_days_flag(tmp_path, capsys):
    _write_probe_log(tmp_path / "lan.1.audit", "lan.1", [_probe("https://a", 20)])
    assert main([str(tmp_path / "lan.1"), "--now", _iso(0), "--max-age-days", "30"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == REPORT_CLEAN


def test_cli_rejects_an_unparseable_now(tmp_path):
    assert main([str(tmp_path / "lan.1"), "--now", "yesterday"]) == 2


def test_module_is_runnable_without_a_runpy_warning(tmp_path):
    """`python -m anvil.lib.probe_freshness` is the documented invocation
    (issue #673 made the -m path warning-free; keep it that way)."""
    _write_probe_log(tmp_path / "lan.1.audit", "lan.1", [_probe("https://a", 1)])
    result = subprocess.run(
        [sys.executable, "-m", "anvil.lib.probe_freshness", str(tmp_path / "lan.1")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "RuntimeWarning" not in result.stderr
    assert json.loads(result.stdout)["version_dir"] == "lan.1"


# ---------------------------------------------------------------------------
# Canary reproducer (censusapi, 2026-08-01 → 2026-08-02)
# ---------------------------------------------------------------------------


def test_censusapi_reproducer_surfaces_both_rotted_claims(tmp_path):
    """A clean v2 audit; a v3 pass a day later. The two claims that went
    false in production are on the re-probe checklist; the durable
    arithmetic claim (which records no probe) is not."""
    _write_probe_log(
        tmp_path / "paper.2.audit",
        "paper.2",
        [
            _probe(
                "https://example.edu/papers/widget.pdf",
                1,
                method="sha256",
                observed="sha256:9f2c",
                claim="§3 pins the cited paper at 'working draft v8'",
                recheck_command="curl -sL <url> | shasum -a 256",
            ),
            _probe(
                "http://writeoff.cs.byu.edu/",
                1,
                observed="connection refused",
                claim="§5 states both published download hosts are dead",
            ),
        ],
    )
    report = check_probe_freshness(tmp_path / "paper.3", now=NOW)

    assert report.status == REPORT_NEEDS_REPROBE
    assert {s.target for s in report.needs_reprobe} == {
        "https://example.edu/papers/widget.pdf",
        "http://writeoff.cs.byu.edu/",
    }
    assert all(s.status == STATUS_NOT_REPROBED for s in report.needs_reprobe)
    # The checklist names what would become false, not just which URL to hit.
    assert all(s.probe.claim for s in report.needs_reprobe)
