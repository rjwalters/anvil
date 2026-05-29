"""Convergence/termination primitives for the review/revise loop.

This module is the load-bearing primitive for #27 — *stable-score termination
as secondary stop condition*. It exists alongside ``anvil/lib/critics.py``
(per-iteration aggregation and verdict) and is invoked by an orchestrator or
skill review-command that has access to per-iteration score history.

The functions here are **pure**: no filesystem access, no ``_progress.json``
reads. The caller is responsible for extracting score history from the
canonical ``metadata.score_history`` array documented in
``anvil/lib/snippets/progress.md`` and passing it in.

Resolution order
----------------

When deciding whether to terminate the draft↔review↔revise loop, the
following conditions are evaluated in order — the **first** match wins:

1. ``CRITICAL_FLAG`` (``Verdict.BLOCK``) — any critical flag is set.
2. ``THRESHOLD_MET`` (``Verdict.ADVANCE``) — latest total meets threshold.
3. ``MAX_ITERATIONS`` (``Verdict.REVISE``) — iteration cap exhausted. The
   verdict remains ``REVISE`` because the work did not converge; the
   orchestrator/human reads ``termination_reason`` to know why the loop
   stopped.
4. ``STALLED`` (``Verdict.STALLED``) — the last ``lookback`` totals are
   all within ``± window`` of each other AND below the threshold. This is
   the lowest-priority terminator: the loop has plateaued but did not
   demonstrably converge or fail a harder check.
5. Otherwise — ``(Verdict.REVISE, "")``: no termination, the loop
   continues.

Defaults match the rationale in #27: ``window=1``, ``lookback=2`` — two
consecutive rounds within ±1 trigger ``STALLED``.

This file's behavior is mirrored in the markdown convention layer at
``anvil/lib/snippets/rubric.md`` ("Convergence logic") and
``anvil/lib/snippets/state_machine.md`` ("Convergence and iteration cap").
The Python implementation here is the source of truth for programmatic use;
the snippets are the source of truth for LLM-side authoring. They MUST agree.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from anvil.lib.review_schema import Verdict


# Canonical termination_reason values. These match the optional top-level
# ``termination_reason`` field documented in ``anvil/lib/snippets/progress.md``.
TERMINATION_THRESHOLD_MET = "THRESHOLD_MET"
TERMINATION_CRITICAL_FLAG = "CRITICAL_FLAG"
TERMINATION_STALLED = "STALLED"
TERMINATION_MAX_ITERATIONS = "MAX_ITERATIONS"


def check_stable(
    history: List[Optional[int]],
    window: int = 1,
    lookback: int = 2,
) -> bool:
    """Return True when the last ``lookback`` totals are all within ``± window``.

    A "stable" history means successive revisions have stopped improving:
    the aggregated total bounces inside a small window without crossing the
    threshold. This is the input to the ``STALLED`` termination branch.

    Parameters
    ----------
    history:
        Per-iteration aggregated totals in iteration order. ``None`` entries
        represent iterations where no scorecard was produced (e.g., a
        critical-flag short-circuit occurred before scoring). ``None`` in the
        relevant window prevents a stability decision and returns ``False``.
    window:
        Allowed spread (max - min) across the last ``lookback`` totals.
        Default ``1`` (two consecutive rounds within ±1).
    lookback:
        Number of trailing entries to examine. Default ``2`` (compare the
        last two rounds).

    Returns
    -------
    bool
        ``True`` when (1) there are at least ``lookback`` entries, (2) none of
        the last ``lookback`` entries are ``None``, and (3) the max-minus-min
        spread of the last ``lookback`` entries is ``<= window``. Otherwise
        ``False``.
    """
    if lookback < 2:
        # A single-entry "stability" check is meaningless. The contract is
        # that stability requires comparison across at least two entries.
        return False
    if len(history) < lookback:
        return False
    tail = history[-lookback:]
    if any(x is None for x in tail):
        return False
    # mypy/pyright: after the None check, all entries are int.
    ints: List[int] = [int(x) for x in tail]  # type: ignore[arg-type]
    return (max(ints) - min(ints)) <= window


def decide_termination(
    history: List[Optional[int]],
    threshold: int,
    any_critical: bool,
    iteration: int,
    max_iterations: int,
    window: int = 1,
    lookback: int = 2,
) -> Tuple[Verdict, str]:
    """Decide the next-step verdict + termination_reason for the loop.

    Resolution order (first match wins):

    1. ``any_critical`` -> ``(BLOCK, "CRITICAL_FLAG")``
    2. ``history[-1] >= threshold`` -> ``(ADVANCE, "THRESHOLD_MET")``
    3. ``iteration >= max_iterations`` -> ``(REVISE, "MAX_ITERATIONS")``.
       The verdict stays ``REVISE`` (not ``STALLED``) because hitting the cap
       is a different signal from a demonstrated plateau: the work simply ran
       out of budget. The orchestrator/human reads ``termination_reason`` to
       distinguish the two.
    4. ``check_stable(history, window, lookback)`` -> ``(STALLED, "STALLED")``
    5. Else -> ``(REVISE, "")`` — loop continues, no termination yet.

    Parameters
    ----------
    history:
        Per-iteration aggregated totals in iteration order. ``None`` entries
        are allowed (see ``check_stable``). Pass ``[]`` if no scorecard is
        available yet; the threshold check requires at least one entry.
    threshold:
        The advance threshold for this rubric.
    any_critical:
        Whether the latest review surfaced any critical flag.
    iteration:
        Current iteration number (1-indexed). The iteration that just
        produced ``history[-1]``.
    max_iterations:
        Iteration cap from ``<thread>/.anvil.json`` (default ``4``).
    window:
        Stability window. Default ``1``.
    lookback:
        Number of trailing entries to examine for stability. Default ``2``.

    Returns
    -------
    tuple[Verdict, str]
        The decided verdict and termination_reason. ``termination_reason``
        is the empty string when the loop should continue (no termination).
    """
    # 1. Critical flag short-circuits everything.
    if any_critical:
        return (Verdict.BLOCK, TERMINATION_CRITICAL_FLAG)

    # 2. Threshold met — convergence achieved.
    if history and history[-1] is not None and history[-1] >= threshold:
        return (Verdict.ADVANCE, TERMINATION_THRESHOLD_MET)

    # 3. Iteration cap exhausted. Verdict stays REVISE (the work did not
    #    converge); the termination_reason is MAX_ITERATIONS.
    if iteration >= max_iterations:
        return (Verdict.REVISE, TERMINATION_MAX_ITERATIONS)

    # 4. Demonstrated plateau — score stable across the last `lookback` rounds.
    if check_stable(history, window=window, lookback=lookback):
        return (Verdict.STALLED, TERMINATION_STALLED)

    # 5. No termination — loop continues.
    return (Verdict.REVISE, "")


__all__ = [
    "TERMINATION_THRESHOLD_MET",
    "TERMINATION_CRITICAL_FLAG",
    "TERMINATION_STALLED",
    "TERMINATION_MAX_ITERATIONS",
    "check_stable",
    "decide_termination",
]
