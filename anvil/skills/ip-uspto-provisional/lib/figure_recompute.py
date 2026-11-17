"""Deterministic figure recompute for the advisory claim-chart critic (issue #1497).

The consumer trial behind the claim-chart command found that recomputing
every printed figure from its printed inputs surfaces real disclosure
defects — but only when each miss is *classified against its source*
before anything is reported: "Nearly every figure that failed to
reproduce was the source's own figure with a rounded input or an
unstated condition, so the recompute is only useful with a source-check
step attached."

This module is that source-check step, as code rather than prose. It is
a pure function of a **figure ledger**: the agent extracting the chart
records each printed figure's printed value, its printed inputs, the
derivation the text states (an arithmetic expression), any conditions
the derivation needs that the text does not state, and the figure's
citable source when one exists. The module then deterministically
verifies each entry and classifies every miss into exactly one of three
classes (the trial's taxonomy, verbatim):

- ``text-omits-condition`` — the recompute cannot be completed faithfully
  because the text omits something: a named unstated condition, an
  input the expression references but the text never states, an
  arithmetic impossibility (the expression only holds under conditions
  the text does not give), OR the printed figure is faithful to its
  cited source and the miss traces to the *precision of the printed
  inputs* (the benign rounded-input case — a text-precision gap, not a
  figure error).
- ``figure-differs-from-source`` — the printed figure disagrees with
  what its stated derivation produces from the printed inputs, or with
  its citable source's own value, beyond the entry's tolerance.
- ``no-source`` — the figure has neither a stated derivation nor a
  citable source value: its provenance cannot be checked mechanically
  at all.

Everything here is stdlib-only (CLAUDE.md's subprocess-only /
optional-extras philosophy; no third-party deps). Expressions are
evaluated with a whitelist AST walker — arithmetic operators, numeric
literals, and variable names only. No attribute access, no calls, no
subscripts: a ledger is untrusted input to this module in the same way
a review payload is, and the evaluator cannot be escaped by
ledger content.

The module writes nothing. The calling command owns all on-disk
effects, and those land inside its own staged sidecar
(``anvil/lib/sidecar.py``).

Public API:

- :func:`evaluate_expression` — safe arithmetic evaluation.
- :func:`classify_entry` — one ledger entry → one result record.
- :func:`recompute_ledger` — a full ledger → a report dict.
- :func:`main` — CLI (``python … figure_recompute.py ledger.json``),
  printing the human report; ``--json`` for the machine report. Exit 0
  always: a miss is a *finding to report*, not an execution error. Exit
  2 is reserved for invocation errors (unreadable ledger, invalid JSON,
  malformed entry) per the repo's tool-evidence exit-code convention.
"""

from __future__ import annotations

import ast
import json
import operator
import sys
from collections.abc import Mapping as _AbcMapping
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

__all__ = [
    "MISS_TEXT_OMITS_CONDITION",
    "MISS_FIGURE_DIFFERS",
    "MISS_NO_SOURCE",
    "STATUS_REPRODUCED",
    "STATUS_MISS",
    "ExpressionError",
    "LedgerError",
    "evaluate_expression",
    "classify_entry",
    "recompute_ledger",
    "main",
]

# Miss classes (the trial taxonomy — exactly three, see module docstring).
MISS_TEXT_OMITS_CONDITION = "text-omits-condition"
MISS_FIGURE_DIFFERS = "figure-differs-from-source"
MISS_NO_SOURCE = "no-source"

STATUS_REPRODUCED = "reproduced"
STATUS_MISS = "miss"

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# An integer ``**`` beyond this is a pathological ledger, not a real
# printed-figure derivation; refuse rather than burn CPU on it.
_MAX_INT_EXPONENT = 10_000


class ExpressionError(ValueError):
    """An expression is not safe-arithmetic, or cannot be evaluated."""


class LedgerError(ValueError):
    """A ledger entry is malformed (invocation error, not a finding)."""


def evaluate_expression(expression: str, inputs: Mapping[str, float]) -> float:
    """Safely evaluate ``expression`` over ``inputs``.

    Whitelist: numeric literals, variable names resolving into
    ``inputs`` (via :class:`ast.Name`), unary ``+``/``-``, and the
    binary operators ``+ - * / // % **``. Anything else — function
    calls, attribute access, subscripts, comparisons, booleans — raises
    :class:`ExpressionError`. Names absent from ``inputs`` raise
    :class:`ExpressionError` (the caller classifies that as a
    text-omits-condition miss: the text never states that input).
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"not an arithmetic expression: {expression!r}") from exc
    return _eval_node(tree.body, inputs)


def _eval_node(node: ast.AST, inputs: Mapping[str, float]) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExpressionError(f"non-numeric literal: {node.value!r}")
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in inputs:
            raise ExpressionError(f"input not stated in the text: {node.id!r}")
        return inputs[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_node(node.operand, inputs))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _eval_node(node.left, inputs)
        right = _eval_node(node.right, inputs)
        if isinstance(node.op, ast.Pow) and isinstance(left, int) and isinstance(
            right, int
        ) and abs(right) > _MAX_INT_EXPONENT:
            raise ExpressionError(
                "integer exponent too large to evaluate (ledger is data, not compute)"
            )
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    raise ExpressionError(f"disallowed syntax in expression: {type(node).__name__}")


def _as_number(entry_id: str, field: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LedgerError(
            f"entry {entry_id!r}: field {field!r} must be a number, got {value!r}"
        )
    return value


# A ledger entry that states no ``relative_tolerance`` gets this small
# default so binary float representation alone (``0.1 + 0.2`` vs
# ``0.3``) can never produce a miss — an unstated tolerance means
# "faithful to the printed precision", not exact float equality.
_DEFAULT_RELATIVE_TOLERANCE = 1e-9


def _within_tolerance(
    computed: float, printed: float, tolerance: float, relative_tolerance: float
) -> bool:
    slack = max(tolerance, relative_tolerance * max(abs(computed), abs(printed)))
    return abs(computed - printed) <= slack


def classify_entry(entry: Mapping[str, Any]) -> dict:
    """Classify one ledger entry deterministically.

    Schema (all locations are free-text anchors for the counsel note):

    ``id`` (required, str), ``printed_value`` (required, number),
    ``expression`` (optional, str — the derivation the text states),
    ``inputs`` (optional, object of name → number),
    ``unstated_inputs`` (optional, list of str — conditions the
    derivation needs that the text does not state),
    ``source`` (optional, object with optional ``value`` number),
    ``tolerance`` (optional, absolute, default 0.0),
    ``relative_tolerance`` (optional, default 1e-9 — small enough that
    binary float representation alone, e.g. ``0.1 + 0.2`` vs ``0.3``,
    never produces a miss).

    Classification order (documented, stable):

    1. ``unstated_inputs`` non-empty → miss ``text-omits-condition``.
    2. ``expression`` present → evaluate over ``inputs``:

       - evaluation impossible (unknown name, arithmetic error) → miss
         ``text-omits-condition``;
       - within tolerance → ``reproduced``;
       - beyond tolerance, but ``source.value`` is within tolerance of
         the printed value → miss ``text-omits-condition`` (benign
         rounded-input case: the figure is faithful to its source; the
         printed inputs lack the precision to reproduce it);
       - otherwise → miss ``figure-differs-from-source``.
    3. No ``expression`` but ``source.value`` present: within tolerance
       → ``reproduced``; beyond → miss ``figure-differs-from-source``.
    4. Neither → miss ``no-source``.
    """
    entry_id = entry.get("id")
    if not isinstance(entry_id, str) or not entry_id:
        raise LedgerError(f"entry missing required string 'id': {entry!r}")
    if "printed_value" not in entry:
        raise LedgerError(f"entry {entry_id!r}: missing required 'printed_value'")

    printed = _as_number(entry_id, "printed_value", entry["printed_value"])
    tolerance = _as_number(entry_id, "tolerance", entry.get("tolerance", 0.0))
    relative_tolerance = _as_number(
        entry_id,
        "relative_tolerance",
        entry.get("relative_tolerance", _DEFAULT_RELATIVE_TOLERANCE),
    )
    unstated = entry.get("unstated_inputs") or []
    if not isinstance(unstated, list) or not all(isinstance(u, str) for u in unstated):
        raise LedgerError(
            f"entry {entry_id!r}: 'unstated_inputs' must be a list of str"
        )
    inputs = entry.get("inputs") or {}
    if not isinstance(inputs, _AbcMapping):
        raise LedgerError(f"entry {entry_id!r}: 'inputs' must be an object")
    for name, value in inputs.items():
        _as_number(entry_id, f"inputs.{name}", value)
    source = entry.get("source")
    source_value: Optional[float] = None
    if source is not None:
        if not isinstance(source, _AbcMapping):
            raise LedgerError(f"entry {entry_id!r}: 'source' must be an object")
        if "value" in source and source["value"] is not None:
            source_value = _as_number(
                entry_id, "source.value", source["value"]
            )

    base = {
        "id": entry_id,
        "printed_value": printed,
    }

    # 1. Named unstated conditions — the text omits what the derivation needs.
    if unstated:
        return {
            **base,
            "status": STATUS_MISS,
            "class": MISS_TEXT_OMITS_CONDITION,
            "note": "derivation requires condition(s) the text does not state: "
            + ", ".join(unstated),
        }

    expression = entry.get("expression")
    # 2. The stated derivation is recomputed from the printed inputs.
    if isinstance(expression, str) and expression.strip():
        try:
            computed = evaluate_expression(expression, inputs)
        except ExpressionError as exc:
            return {
                **base,
                "status": STATUS_MISS,
                "class": MISS_TEXT_OMITS_CONDITION,
                "note": f"recompute impossible from stated inputs: {exc}",
            }
        except (ZeroDivisionError, OverflowError) as exc:
            return {
                **base,
                "status": STATUS_MISS,
                "class": MISS_TEXT_OMITS_CONDITION,
                "note": f"expression only holds under unstated conditions: {exc}",
            }
        record = {
            **base,
            "status": None,
            "computed_value": computed,
        }
        if _within_tolerance(computed, printed, tolerance, relative_tolerance):
            record["status"] = STATUS_REPRODUCED
            return record
        if (
            source_value is not None
            and _within_tolerance(
                source_value, printed, tolerance, relative_tolerance
            )
        ):
            return {
                **record,
                "status": STATUS_MISS,
                "class": MISS_TEXT_OMITS_CONDITION,
                "note": "printed figure matches its cited source; miss traces to "
                "the precision of the printed inputs (rounded input)",
            }
        return {
            **record,
            "status": STATUS_MISS,
            "class": MISS_FIGURE_DIFFERS,
            "note": "printed figure differs from what its stated derivation "
            "produces from the printed inputs",
        }

    # 3. No stated derivation — check the figure against its cited source.
    if source_value is not None:
        if _within_tolerance(source_value, printed, tolerance, relative_tolerance):
            return {**base, "status": STATUS_REPRODUCED}
        return {
            **base,
            "status": STATUS_MISS,
            "class": MISS_FIGURE_DIFFERS,
            "note": "printed figure differs from its cited source's value",
        }

    # 4. Nothing to check against.
    return {
        **base,
        "status": STATUS_MISS,
        "class": MISS_NO_SOURCE,
        "note": "no stated derivation and no citable source value — "
        "provenance not checkable",
    }


def recompute_ledger(ledger: Mapping[str, Any]) -> dict:
    """Run :func:`classify_entry` over every entry and summarize.

    ``ledger`` shape: ``{"figures": [entry, ...]}``. Returns a report
    dict with per-entry results plus a summary block of counts by
    status and class. Deterministic: output ordering follows input
    ordering; no timestamps, no randomness, no environment reads.
    """
    figures = ledger.get("figures")
    if not isinstance(figures, list):
        raise LedgerError("ledger must be an object with a 'figures' list")
    results = [classify_entry(entry) for entry in figures]

    summary: dict[str, int] = {
        "total": len(results),
        STATUS_REPRODUCED: 0,
        STATUS_MISS: 0,
        MISS_TEXT_OMITS_CONDITION: 0,
        MISS_FIGURE_DIFFERS: 0,
        MISS_NO_SOURCE: 0,
    }
    for result in results:
        summary[result["status"]] += 1
        if result["status"] == STATUS_MISS:
            summary[result["class"]] += 1
    return {"results": results, "summary": summary}


def _render_human(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"figures: {summary['total']} — "
        f"{summary[STATUS_REPRODUCED]} reproduced, "
        f"{summary[STATUS_MISS]} miss "
        f"(text-omits-condition {summary[MISS_TEXT_OMITS_CONDITION]}, "
        f"figure-differs-from-source {summary[MISS_FIGURE_DIFFERS]}, "
        f"no-source {summary[MISS_NO_SOURCE]})",
    ]
    for result in report["results"]:
        if result["status"] == STATUS_REPRODUCED:
            computed = result.get("computed_value")
            detail = (
                f"recomputed {computed}" if computed is not None else "source match"
            )
            lines.append(f"  {result['id']}: reproduced ({detail})")
        else:
            lines.append(
                f"  {result['id']}: MISS {result['class']} — {result.get('note', '')}"
            )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        print(
            "usage: figure_recompute.py <ledger.json> [--json]",
            file=sys.stderr,
        )
        return 2
    path = Path(paths[0])
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
        report = recompute_ledger(ledger)
    except (OSError, ValueError, ArithmeticError) as exc:
        # ArithmeticError: a pathological ledger (e.g. an integer
        # exponent beyond float range) overflows the tolerance
        # comparison's float conversion — an invocation error, not a
        # traceback.
        print(f"figure_recompute: {exc}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=False))
    else:
        print(_render_human(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
