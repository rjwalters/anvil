"""Calibration-suffix attachment for ``rubric_overrides`` reviewer integration.

Sub-issue 2 of #233 (#265) — the reviewer-integration deliverable. Wires
``anvil_config.load_rubric_overrides`` into the ``memo-review`` lifecycle so
that any per-dimension ``dim_N_calibration`` value declared in
``<thread>/.anvil.json`` appears as a verbatim suffix on that dimension's
justification in both ``_review.json`` and ``scoring.md``.

The schema-of-record for the loader is ``anvil/skills/memo/lib/anvil_config.py``
(sub-issue 1 / PR #267). This module is the thin glue between the loader and
the reviewer's per-dimension scoring write path: it accepts a
``RubricOverrides`` instance (or ``None``) and a justification string, and
returns the suffix-appended justification when a calibration applies, or the
input justification unchanged otherwise.

Why this lives in its own module
--------------------------------
``anvil_config.py`` is the schema + reader and is intentionally side-effect-
free — it knows nothing about reviewer output. This module owns the suffix
formatting contract (the verbatim ``"calibration applied: <override text>"``
shape) and the per-dimension dispatch. Splitting the two preserves the
schema-reader / consumer separation that lets sub-issue 1 stay
reviewer-agnostic and lets this module stay independently testable.

The split mirrors the existing precedent in this skill: ``memo_image_refs.py``
(the lint detector) and the reviewer's ``_summary.md`` write path are
separate concerns; the detector returns a typed ``LintResult`` and the
reviewer formats it into the JSON-in-markdown scorecard. Here, the loader
returns a typed ``RubricOverrides`` and this module formats it into the
calibration-suffix string.

Suffix shape contract
---------------------
Per the issue body of #233 and the AC list of #265, the suffix shape is::

    calibration applied: <verbatim override text>

The override text is **verbatim** — no rewording, no truncation, no
whitespace normalization. The author's exact wording is the load-bearing
audit trail: a reader of ``scoring.md`` MUST be able to see exactly which
calibration the reviewer applied to which dimension, in the author's words.

The leading prefix ``calibration applied: `` is the contract. It is the
mechanical anchor that lets a downstream consumer (a reviser, a CI grep, a
human reader skimming `scoring.md`) cheaply detect which justifications
carry a calibration. Changing the prefix is a breaking change to the
contract.

When the suffix attaches to an existing justification, the two are joined
with a single space — the suffix is appended in-line at the end of the
justification, not pushed to a new paragraph. This keeps the per-dimension
``scoring.md`` table cell compact (one row per dimension) and the
``_review.json`` ``justification`` field a single string per the v1
schema in ``anvil/lib/review_schema.py``.

Empty / missing justification
-----------------------------
When the reviewer has not yet written a justification for a dimension (the
input ``justification`` is ``None`` or empty), the suffix becomes the entire
justification. This is the load-bearing path for a reviewer that scored a
dimension at full weight and didn't write a justification body but
*should* still record the calibration in the audit trail. The author's
calibration text remains the verbatim record.

Zero-impact when overrides absent
---------------------------------
When ``rubric_overrides`` is ``None`` (the empty-state from the loader for
threads without a ``.anvil.json``, without a ``rubric_overrides`` block, or
with a malformed block) the helper returns the input justification
unchanged. The reviewer's per-dimension write path is **byte-identical** to
its pre-#233 behavior. This is the AC3 zero-impact contract from #265.

This same zero-impact behavior applies dimension-by-dimension: a dimension
without a ``dim_<N>_calibration`` declared returns the input justification
unchanged even when other dimensions carry calibrations. A reviewer that
sets ``dim_1_calibration`` only sees the suffix on dim 1; dims 2-9 see
their justifications unchanged.

Public API
----------
``CALIBRATION_PREFIX``
    The verbatim ``"calibration applied: "`` prefix (trailing space). Exported
    so callers (test suites, reviser consumers) can grep ``scoring.md`` for
    calibrated justifications without hard-coding the literal.
``format_calibration_suffix(text)``
    Format a single override text as the verbatim suffix string. Pure
    function; no side effects.
``apply_calibration_to_justification(justification, overrides, dimension)``
    Attach the calibration suffix for ``dimension`` (if declared in
    ``overrides``) to the given ``justification``. Returns the suffix-
    appended justification, or the input justification unchanged when no
    calibration applies.
``apply_calibrations_to_scores(scores, overrides)``
    Convenience helper for the per-dimension scoring write path. Accepts a
    list of ``Score`` instances (one per dimension) and returns a new list
    with calibration suffixes attached per dimension. The input list is not
    mutated.

This module is intentionally **skill-local** under
``anvil/skills/memo/lib/`` per the CLAUDE.md "skill-local first, lib
promotion later" pattern. Promotion to ``anvil/lib/`` is queued for the
second-consumer trigger (likely ``anvil:report`` or ``anvil:pub`` if they
adopt subtype calibration), same as the loader at ``anvil_config.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# anvil_config is a sibling module under anvil/skills/memo/lib/. Import using
# the package-relative form so tests under tests/test_*.py and the production
# reviewer code path both resolve the same module.
try:
    # Production: ``anvil`` is on PYTHONPATH as an installable package.
    from anvil.skills.memo.lib.anvil_config import RubricOverrides
except ImportError:  # pragma: no cover
    # Test / standalone path: the tests add the lib dir to sys.path directly.
    from anvil_config import RubricOverrides  # type: ignore[no-redef]


# The verbatim suffix prefix shape. Per the issue body of #233 and AC2 of
# #265, the trailing space is part of the contract: ``calibration applied: ``
# (one trailing space) is the anchor a downstream consumer greps for.
CALIBRATION_PREFIX = "calibration applied: "


@dataclass
class ScoreLike:
    """Lightweight value-object for a per-dimension score row.

    The memo-review command writes per-dimension scores into:

    - ``scoring.md`` — as a markdown table row (``# | Dimension | Weight | Score | Justification``)
    - ``_summary.md`` — as a JSON-in-markdown ``dimensions`` block (scores only)
    - ``_review.json`` — as a typed ``Score`` per ``anvil/lib/review_schema.py``

    The reviewer agent assembles the per-dim score in a generic dict / model
    shape before formatting it for each output. ``ScoreLike`` is the
    common-denominator shape this helper accepts: a dict with ``dimension``
    and ``justification`` keys, or any value-object that exposes those two
    attributes. The helper does NOT depend on the typed ``Score`` model from
    ``anvil/lib/review_schema.py`` because the memo-review write path is
    markdown-first and the typed ``_review.json`` write is currently
    deferred (forward-compat with the ``Score`` model is preserved by the
    suffix string shape).

    Use ``ScoreLike(dimension=N, justification=...)`` in tests; production
    callers MAY pass any object with the two attributes.
    """

    dimension: int
    justification: Optional[str] = None
    # Optional fields the reviewer also assembles; preserved so the helper
    # can return a new ScoreLike without losing context.
    score: Optional[int] = None
    weight: Optional[int] = None
    name: Optional[str] = None
    extra: dict = field(default_factory=dict)


def format_calibration_suffix(text: str) -> str:
    """Return the verbatim calibration suffix for ``text``.

    The suffix is ``"calibration applied: <text>"`` with the prefix exactly
    as declared in :data:`CALIBRATION_PREFIX` and the ``text`` reproduced
    verbatim — no trimming, no normalization. The author's exact wording is
    the load-bearing audit trail.

    This is a pure function; it does not touch any I/O and does not validate
    ``text`` beyond the type contract. The loader at
    ``anvil_config.load_rubric_overrides`` is responsible for rejecting
    empty / non-string override values; this helper trusts its input.

    Parameters
    ----------
    text
        The verbatim calibration override text from ``dim_N_calibration``.

    Returns
    -------
    str
        The suffix string to append to (or use as) a dimension's justification.
    """
    return f"{CALIBRATION_PREFIX}{text}"


def apply_calibration_to_justification(
    justification: Optional[str],
    overrides: Optional[RubricOverrides],
    dimension: int,
) -> Optional[str]:
    """Attach a calibration suffix to ``justification`` for ``dimension``.

    Looks up ``dim_<dimension>_calibration`` in ``overrides`` (via
    ``RubricOverrides.calibration_for``). When a calibration is declared,
    appends the verbatim suffix to ``justification`` and returns the result.
    When no calibration is declared (or ``overrides`` is ``None`` /
    empty), returns ``justification`` unchanged.

    Suffix-attachment rules:

    - ``justification`` is a non-empty string AND a calibration is declared:
      returns ``"<justification> calibration applied: <text>"`` (one space
      separator between the prose and the suffix).
    - ``justification`` is ``None`` or empty AND a calibration is declared:
      returns the suffix string alone (``"calibration applied: <text>"``).
      The reviewer typically writes 1-3 sentences of justification per
      dimension, but a full-weight score sometimes ships without one; the
      calibration MUST still be recorded for the audit trail.
    - ``overrides`` is ``None`` OR no calibration is declared for
      ``dimension``: returns ``justification`` unchanged (including ``None``
      and empty-string preserved verbatim). This is the AC3 zero-impact
      contract.

    Parameters
    ----------
    justification
        The reviewer's per-dimension justification prose, or ``None`` /
        empty when not yet written.
    overrides
        The parsed ``RubricOverrides`` from
        ``anvil_config.load_rubric_overrides``, or ``None`` when no
        overrides are configured for this thread.
    dimension
        The memo rubric dimension number (1-9). Out-of-range values silently
        return the input justification — the loader already validates the
        on-disk range, but a caller that hand-builds a ``RubricOverrides``
        instance with an out-of-range dim won't trip this helper.

    Returns
    -------
    Optional[str]
        The suffix-appended justification, or the input justification
        unchanged when no calibration applies.
    """
    if overrides is None:
        return justification

    text = overrides.calibration_for(dimension)
    if text is None:
        return justification

    suffix = format_calibration_suffix(text)
    if justification is None or not justification:
        return suffix

    # Preserve the original justification verbatim and append the suffix
    # in-line. A single space separates the two; the suffix carries no
    # leading or trailing whitespace beyond the prefix's single trailing
    # space (so "<prose> calibration applied: <text>"). Newlines inside
    # the input justification are preserved.
    return f"{justification} {suffix}"


def apply_calibrations_to_scores(
    scores: List[ScoreLike],
    overrides: Optional[RubricOverrides],
) -> List[ScoreLike]:
    """Return a copy of ``scores`` with calibration suffixes attached.

    Iterates each dimension's score and rewrites the ``justification`` field
    when a ``dim_<N>_calibration`` is declared for that dimension. Returns a
    new list of ``ScoreLike`` instances; the input list is not mutated.

    Convenience wrapper around ``apply_calibration_to_justification`` for
    the common per-dim batch path: a reviewer that has assembled all 9
    dimension scores in a single list calls this helper once at the end of
    the scoring loop to attach all suffixes in one pass.

    When ``overrides`` is ``None`` or empty (no calibrations declared), the
    returned list carries the same justifications byte-for-byte — the AC3
    zero-impact contract holds at the list level too.

    Parameters
    ----------
    scores
        List of per-dimension scores. Each entry MUST carry a ``dimension``
        attribute (1-9) and a ``justification`` attribute (``Optional[str]``).
    overrides
        The parsed ``RubricOverrides``, or ``None`` when no overrides are
        configured.

    Returns
    -------
    List[ScoreLike]
        New list of suffix-applied scores in the same order as the input.
    """
    if overrides is None or overrides.is_empty:
        # Fast path: nothing to attach. Return a shallow copy so callers
        # who mutate the returned list don't inadvertently mutate the input.
        return [
            ScoreLike(
                dimension=s.dimension,
                justification=s.justification,
                score=s.score,
                weight=s.weight,
                name=s.name,
                extra=dict(s.extra),
            )
            for s in scores
        ]

    out: List[ScoreLike] = []
    for s in scores:
        new_justification = apply_calibration_to_justification(
            s.justification, overrides, s.dimension
        )
        out.append(
            ScoreLike(
                dimension=s.dimension,
                justification=new_justification,
                score=s.score,
                weight=s.weight,
                name=s.name,
                extra=dict(s.extra),
            )
        )
    return out


__all__ = [
    "CALIBRATION_PREFIX",
    "ScoreLike",
    "apply_calibration_to_justification",
    "apply_calibrations_to_scores",
    "format_calibration_suffix",
]
