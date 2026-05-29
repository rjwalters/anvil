"""Framework primitives shared across Anvil skills.

Public modules:

- ``review_schema``: the canonical typed schema for ``_review.json`` critic
  outputs. See ``anvil/lib/README.md`` for the field-by-field reference.
- ``critics``: discovery, loading, aggregation, and verdict computation for
  the "N parallel critics, one reviser" primitive.
- ``cite``: identifier parsing (DOI/arXiv), Crossref / arXiv resolution,
  deterministic BibTeX key generation, and idempotent ``refs.bib``
  writing. See ``anvil/lib/snippets/cite.md`` for the on-disk convention.
- ``convergence``: ``check_stable`` and ``decide_termination`` — pure
  functions for the multi-iteration termination decision (threshold met /
  critical flag / max-iterations / stalled). Produces ``Verdict.STALLED``
  when successive revisions have plateaued.
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
from anvil.lib.convergence import (
    TERMINATION_CRITICAL_FLAG,
    TERMINATION_MAX_ITERATIONS,
    TERMINATION_STALLED,
    TERMINATION_THRESHOLD_MET,
    check_stable,
    decide_termination,
)


__all__ = [
    "BibRecord",
    "CiteResolutionError",
    "Identifier",
    "IdentifierKind",
    "TERMINATION_CRITICAL_FLAG",
    "TERMINATION_MAX_ITERATIONS",
    "TERMINATION_STALLED",
    "TERMINATION_THRESHOLD_MET",
    "UnsupportedIdentifierError",
    "bib_key",
    "check_stable",
    "cite",
    "decide_termination",
    "parse_identifier",
    "resolve",
]
