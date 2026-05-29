"""Framework primitives shared across Anvil skills.

Public modules:

- ``review_schema``: the canonical typed schema for ``_review.json`` critic
  outputs. See ``anvil/lib/README.md`` for the field-by-field reference.
- ``critics``: discovery, loading, aggregation, and verdict computation for
  the "N parallel critics, one reviser" primitive.
- ``cite``: identifier parsing (DOI/arXiv), Crossref / arXiv resolution,
  deterministic BibTeX key generation, and idempotent ``refs.bib``
  writing. See ``anvil/lib/snippets/cite.md`` for the on-disk convention.
"""

from anvil.lib.cite import (
    BibRecord,
    CiteResolutionError,
    Identifier,
    IdentifierKind,
    UnsupportedIdentifierError,
    bib_key,
    cite,
    parse_identifier,
    resolve,
)


__all__ = [
    "BibRecord",
    "CiteResolutionError",
    "Identifier",
    "IdentifierKind",
    "UnsupportedIdentifierError",
    "bib_key",
    "cite",
    "parse_identifier",
    "resolve",
]
