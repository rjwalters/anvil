"""Skill-local lib for ``anvil:ip-uspto-provisional`` (issue #1497).

Modules:

- ``figure_recompute``: deterministic recompute of printed figures from
  printed inputs, with per-miss classification against the figure's
  source (``text-omits-condition`` / ``figure-differs-from-source`` /
  ``no-source``). Consumed by the advisory ``claim-chart`` command; pure
  stdlib, no network, no writes.

Posture: the skill-local-first rule (CLAUDE.md — "ship under
``anvil/skills/<skill>/lib/`` until duplication is observed across
skills"). Promotion into ``anvil/lib/`` waits for a second consumer.

Write scope: this lib writes NOTHING. It is a pure function of the
ledger JSON handed to it; the command file owns every on-disk effect
(and those land inside the command's own staged sidecar).
"""
