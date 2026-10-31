"""Pins the #1396 clause-2 acceptance measurement (reader-flow recurrence).

Four fresh reads per paper (A1/A2 on the pre-flow version, B1/B2 on the
flow-revised version) are fixtured under ``fixtures/readerflow_acceptance/``.
The recorded R values and the pass/fail call are in
``docs/research/readerflow-acceptance-20261031.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.skills.paper.lib.readerflow_recurrence import recurrence

FIX = Path(__file__).parent / "fixtures" / "readerflow_acceptance"
MARGIN = 0.05  # "clearly below" = at least this far under the lower noise floor

# paper -> (cross A1->B1, floor A1->A2, floor B1->B2, passes)
EXPECTED = {
    "antenna": (0.292, 0.333, 0.444, False),
    "transmon": (0.400, 0.367, 0.440, False),
    "motor": (0.261, 0.348, 0.250, False),
}


def _load(paper: str, read: str) -> list:
    return json.loads((FIX / f"{paper}_{read}.json").read_text())["findings"]


@pytest.mark.parametrize("paper", sorted(EXPECTED))
def test_recorded_recurrence_values(paper):
    cross, floor_a, floor_b, passes = EXPECTED[paper]
    got_cross = recurrence(_load(paper, "A1"), _load(paper, "B1"))["share"]
    got_a = recurrence(_load(paper, "A1"), _load(paper, "A2"))["share"]
    got_b = recurrence(_load(paper, "B1"), _load(paper, "B2"))["share"]
    assert (got_cross, got_a, got_b) == (cross, floor_a, floor_b)
    assert (got_cross <= min(got_a, got_b) - MARGIN) is passes


@pytest.mark.parametrize("paper", sorted(EXPECTED))
@pytest.mark.parametrize("read", ["A1", "A2", "B1", "B2"])
def test_reads_are_nonempty_and_well_formed(paper, read):
    findings = _load(paper, read)
    assert findings
    for f in findings:
        assert f["severity"] in {"major", "minor", "nit"}
        assert f["evidence_span"]
