"""Drift guard for the committed ``anvil/lib/*_schema.json`` artifacts.

The two JSON Schema documents under ``anvil/lib/`` are generated from the
pydantic model sources via ``python3 -m anvil.lib.export_schema``. They are
interop artifacts (consumed by non-Python callers, e.g. a future TypeScript
orchestrator) — nothing loads them at Python runtime, so a model/docstring
edit that forgets to regenerate the JSON silently desyncs the checked-in
schema (issue #714: a missing ``NO_GO`` verdict enum from #559, and a stale
``pub/rubric.md`` path from the #713 ``pub → paper`` rename).

These tests assert that a fresh in-memory build (``build_schema()`` /
``build_rubric_schema()``) equals the committed file. Comparison is on parsed
dicts (``json.loads``), not raw bytes: ``write_schema`` / ``write_rubric_schema``
serialize with ``json.dumps(..., indent=2, sort_keys=True)`` plus a trailing
newline, and a dict comparison is robust to any future whitespace/key-order
tweak in those writers while still catching every semantic drift. The builders
are called directly (rather than shelling out like
``tests/agents/test_generator_idempotent.py``) because ``export_schema.py``
already exposes importable in-memory builders separate from the disk writes.
"""

from __future__ import annotations

import json

from anvil.lib.export_schema import (
    RUBRIC_SCHEMA_PATH,
    SCHEMA_PATH,
    build_rubric_schema,
    build_schema,
)


def test_review_schema_matches_committed_file() -> None:
    """The committed review_schema.json equals a fresh in-memory build."""
    committed = json.loads(SCHEMA_PATH.read_text())
    assert build_schema() == committed, (
        "anvil/lib/review_schema.json has drifted from "
        "anvil/lib/review_schema.py. Regenerate with "
        "`python3 -m anvil.lib.export_schema` and commit."
    )


def test_rubric_schema_matches_committed_file() -> None:
    """The committed rubric_schema.json equals a fresh in-memory build."""
    committed = json.loads(RUBRIC_SCHEMA_PATH.read_text())
    assert build_rubric_schema() == committed, (
        "anvil/lib/rubric_schema.json has drifted from "
        "anvil/lib/rubric.py. Regenerate with "
        "`python3 -m anvil.lib.export_schema` and commit."
    )
