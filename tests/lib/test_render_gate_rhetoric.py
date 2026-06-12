"""Gate-integration tests for the ``memo_rhetoric_lint`` dimension (issue #463).

Covers the seventh memo render-gate dimension added to
``anvil/lib/render_gate.py``'s memo gate — the #395 ``memo_image_dimensions``
advisory model applied verbatim to the deterministic rhetoric lint:

- findings recorded, ``passed`` unaffected, no ``CriticalFlag``;
- ``DIM_MEMO_RHETORIC`` listed in ``ordered_dims`` (future severity
  promotion emits flags in documented order);
- per-line suppression via ``<!-- anvil-lint-disable: memo_rhetoric_lint -->``
  surfaces as info findings through the gate;
- ``rhetoric_rules_path`` forwarded by the public ``gate()`` dispatcher
  (consumer merge + disable + malformed-JSON graceful-degrade);
- body-missing skip breadcrumb;
- zero findings on clean prose through the gate.

The renderer is stubbed unavailable (the ``test_render_gate_image_dims``
``_run_gate`` pattern): compile graceful-degrades and the rhetoric lint
(filesystem-only) still runs — proving check 7 is independent of the
render outcome.

Test filename is distinct from ``test_render_gate.py`` /
``test_render_gate_memo.py`` / ``test_render_gate_image_dims.py`` per
the #58 packaging convention.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib import render_gate as rg
from anvil.lib.render_gate import DIM_MEMO_RHETORIC


@pytest.fixture
def memo_version_dir(tmp_path):
    """Minimal ``<thread>/<thread>.{N}/`` version dir."""
    thread_root = tmp_path / "halcyon"
    vd = thread_root / "halcyon.1"
    vd.mkdir(parents=True)
    (vd / "halcyon.md").write_text(
        "# Memo\n\nPlain prose body.\n", encoding="utf-8"
    )
    return vd


def _write_body(version_dir: Path, body: str) -> Path:
    md = version_dir / "halcyon.md"
    md.write_text(body, encoding="utf-8")
    return md


def _run_gate(memo_version_dir, monkeypatch, **kwargs):
    """Drive the memo gate with the renderer stubbed unavailable."""
    from anvil.lib import render as _render

    monkeypatch.setattr(_render, "check_pandoc_available", lambda: False)
    return rg.gate(kind="memo", version_dir=memo_version_dir, **kwargs)


def _dim_findings(result):
    return [f for f in result.findings if f.gate == DIM_MEMO_RHETORIC]


# ---------------------------------------------------------------------------
# Advisory severity model (#395 verbatim)
# ---------------------------------------------------------------------------


def test_tell_laden_body_findings_present_passed_unchanged(
    memo_version_dir, monkeypatch
):
    """Warnings recorded; passed stays True; no CriticalFlag emitted."""
    _write_body(
        memo_version_dir,
        "# Memo\n\nWe delve into a rich tapestry of synergies.\n",
    )
    result = _run_gate(memo_version_dir, monkeypatch)
    hits = _dim_findings(result)
    assert len(hits) == 2  # no-delve + no-tapestry
    assert all(f.severity == "warning" for f in hits)
    assert result.passed is True
    assert DIM_MEMO_RHETORIC not in result.failed_gates
    assert result.to_critical_flags() == []
    # Findings flow to _progress.json.render_gate.findings via to_json().
    payload = result.to_json()
    assert any(f["gate"] == DIM_MEMO_RHETORIC for f in payload["findings"])
    assert payload["pass"] is True
    # An advisory reason breadcrumb names the dim 9 evidence channel.
    assert any(
        r.startswith(f"{DIM_MEMO_RHETORIC}:") and "Rhetorical economy" in r
        for r in result.reasons
    )


def test_finding_location_anchors_body_line(memo_version_dir, monkeypatch):
    _write_body(memo_version_dir, "# Memo\n\nProse.\n\nWe delve here.\n")
    result = _run_gate(memo_version_dir, monkeypatch)
    hits = _dim_findings(result)
    assert len(hits) == 1
    assert hits[0].location.endswith("halcyon.md:L5")
    assert "no-delve" in hits[0].message


def test_clean_body_no_findings_no_reason(memo_version_dir, monkeypatch):
    _write_body(
        memo_version_dir,
        "# Memo\n\nThe pipeline is thinner than the deck suggests.\n",
    )
    result = _run_gate(memo_version_dir, monkeypatch)
    assert _dim_findings(result) == []
    assert not any(
        r.startswith(f"{DIM_MEMO_RHETORIC}:") for r in result.reasons
    )
    assert result.passed is True


def test_body_missing_skip_breadcrumb(tmp_path, monkeypatch):
    vd = tmp_path / "halcyon" / "halcyon.1"
    vd.mkdir(parents=True)  # no halcyon.md
    result = _run_gate(vd, monkeypatch)
    assert _dim_findings(result) == []
    assert any(
        r.startswith(f"{DIM_MEMO_RHETORIC}:") and "skipped" in r
        for r in result.reasons
    )


# ---------------------------------------------------------------------------
# Suppression through the gate
# ---------------------------------------------------------------------------


def test_suppression_surfaces_as_info_through_gate(
    memo_version_dir, monkeypatch
):
    _write_body(
        memo_version_dir,
        "# Memo\n\n"
        "<!-- anvil-lint-disable: memo_rhetoric_lint -->\n"
        "We delve into it.\n",
    )
    result = _run_gate(memo_version_dir, monkeypatch)
    hits = _dim_findings(result)
    assert [f.severity for f in hits] == ["info"]
    assert "(suppressed)" in hits[0].message
    assert result.passed is True


def test_suppression_same_line_through_gate(memo_version_dir, monkeypatch):
    _write_body(
        memo_version_dir,
        "# Memo\n\n"
        "We delve into it. <!-- anvil-lint-disable: memo_rhetoric_lint -->\n",
    )
    result = _run_gate(memo_version_dir, monkeypatch)
    assert [f.severity for f in _dim_findings(result)] == ["info"]


# ---------------------------------------------------------------------------
# Consumer rules via rhetoric_rules_path (the #461 fallback integration point)
# ---------------------------------------------------------------------------


def test_gate_threads_rhetoric_rules_path(memo_version_dir, monkeypatch, tmp_path):
    rules = tmp_path / "rules.json"
    rules.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "no-widget",
                        "kind": "phrase",
                        "pattern": "widgetify",
                        "message": "no widgetify",
                    }
                ],
                "disable": ["no-delve"],
            }
        ),
        encoding="utf-8",
    )
    _write_body(memo_version_dir, "# Memo\n\nWe widgetify and delve.\n")
    result = _run_gate(
        memo_version_dir, monkeypatch, rhetoric_rules_path=rules
    )
    hits = _dim_findings(result)
    assert len(hits) == 1
    assert "no-widget" in hits[0].message
    assert not any("no-delve" in f.message for f in hits)


def test_gate_malformed_consumer_json_defaults_plus_config_warning(
    memo_version_dir, monkeypatch, tmp_path
):
    rules = tmp_path / "rules.json"
    rules.write_text("{not json", encoding="utf-8")
    _write_body(memo_version_dir, "# Memo\n\nWe delve in.\n")
    result = _run_gate(
        memo_version_dir, monkeypatch, rhetoric_rules_path=rules
    )
    hits = _dim_findings(result)
    config = [f for f in hits if "rhetoric_lint_config" in f.message]
    assert len(config) == 1 and config[0].severity == "warning"
    assert any("no-delve" in f.message for f in hits)  # defaults still ran
    assert result.passed is True


def test_defaults_identical_with_and_without_rules_path(
    memo_version_dir, monkeypatch
):
    """No consumer rules declared → identical defaults-only behavior."""
    _write_body(memo_version_dir, "# Memo\n\nWe delve in.\n")
    without = _run_gate(memo_version_dir, monkeypatch)
    explicit_none = _run_gate(
        memo_version_dir, monkeypatch, rhetoric_rules_path=None
    )
    key = lambda r: [f.to_dict() for f in _dim_findings(r)]  # noqa: E731
    assert key(without) == key(explicit_none)


# ---------------------------------------------------------------------------
# ordered_dims future-proofing
# ---------------------------------------------------------------------------


def test_ordered_dims_future_proofing():
    """DIM_MEMO_RHETORIC emits a flag iff force-failed (severity promotion)."""
    result = rg.GateResult(
        pdf_path="x.pdf",
        log_path=None,
        pages=None,
        page_cap=None,
        overfull_boxes=[],
        overfull_threshold_pt=0.0,
        compile_status=rg.COMPILE_SKIPPED,
        compile_exit_code=None,
        placeholders=[],
        passed=False,
        reasons=[f"{DIM_MEMO_RHETORIC}: forced"],
        failed_gates={DIM_MEMO_RHETORIC},
    )
    flags = result.to_critical_flags()
    assert len(flags) == 1
    assert flags[0].type == f"render_gate_{DIM_MEMO_RHETORIC}"
