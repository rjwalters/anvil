"""Framework primitives shared across Anvil skills.

Public modules:

- ``review_schema``: the canonical typed schema for ``_review.json`` critic
  outputs. See ``anvil/lib/README.md`` for the field-by-field reference.
- ``critics``: discovery, loading, aggregation, and verdict computation for
  the "N parallel critics, one reviser" primitive.
"""
