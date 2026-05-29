"""Export ``review_schema.py`` as a JSON Schema document.

Run from the repo root:

    python3 -m anvil.lib.export_schema

The output is written to ``anvil/lib/review_schema.json`` and consumed by
non-Python callers (e.g., a future TypeScript orchestrator) for validation
against the same contract as the Python models.

The exported document is the union of two schemas:

- ``$defs.Review`` — the per-critic ``_review.json`` payload.
- ``$defs.AggregatedReview`` — the merged result produced by
  ``anvil/lib/critics.py::aggregate``.

The top-level schema accepts either shape (``oneOf``) so a single validator
can be pointed at any file in a critic sibling dir.
"""

from __future__ import annotations

import json
from pathlib import Path

from anvil.lib.review_schema import AggregatedReview, Review


SCHEMA_PATH = Path(__file__).parent / "review_schema.json"


def build_schema() -> dict:
    """Return the combined JSON Schema document as a dict."""
    review_schema = Review.model_json_schema(ref_template="#/$defs/{model}")
    agg_schema = AggregatedReview.model_json_schema(
        ref_template="#/$defs/{model}"
    )

    # pydantic emits a top-level "$defs" inside each schema; pull them up so
    # the combined document has a single shared "$defs" map.
    shared_defs: dict = {}
    for sub_schema in (review_schema, agg_schema):
        sub_defs = sub_schema.pop("$defs", {})
        for name, defn in sub_defs.items():
            shared_defs.setdefault(name, defn)

    shared_defs["Review"] = review_schema
    shared_defs["AggregatedReview"] = agg_schema

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://anvil.dev/schemas/review_schema.json",
        "title": "Anvil critic output schema",
        "description": (
            "Canonical JSON contract written by Anvil critic siblings "
            "as _review.json, and produced by the aggregator. Generated "
            "from anvil/lib/review_schema.py; do not edit by hand."
        ),
        "oneOf": [
            {"$ref": "#/$defs/Review"},
            {"$ref": "#/$defs/AggregatedReview"},
        ],
        "$defs": shared_defs,
    }


def write_schema(path: Path = SCHEMA_PATH) -> Path:
    """Write the schema JSON to ``path`` and return the path."""
    data = build_schema()
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return path


def main() -> None:
    out = write_schema()
    print(f"Wrote JSON Schema to {out}")


if __name__ == "__main__":
    main()
