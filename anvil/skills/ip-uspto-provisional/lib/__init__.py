"""Skill-local lib for ``anvil:ip-uspto-provisional`` (first modules: #1497, #1500).

The skill directory name is hyphenated (``ip-uspto-provisional``), so this
package is NOT importable via a dotted ``python -m`` path. Consumers invoke
modules by direct file path (the ip-uspto / project-migrate / project-share
precedent), e.g.:

    python3 anvil/skills/ip-uspto-provisional/lib/numeral_names.py <thread>.{N}

and tests load modules by file path via ``importlib`` under a unique
module name (see ``tests/test_ip_uspto_provisional_numeral_names.py``).

Modules:

- ``figure_recompute.py`` (#1497) — deterministic recompute of printed
  figures from printed inputs, with per-miss classification against the
  figure's source (``text-omits-condition`` / ``figure-differs-from-source``
  / ``no-source``). Consumed by the advisory ``claim-chart`` command. Pure
  stdlib, no network, no writes: it is a pure function of the ledger JSON
  handed to it; the command file owns every on-disk effect (and those land
  inside the command's own staged sidecar).
- ``numeral_names.py`` (#1500) — one-name-per-reference-numeral check for
  the pre-flight (Check 5b, ``minor`` advisory) and the audit (Check 3
  candidate findings). Whitespace-normalised matching so a name split
  across source lines is still found; heuristic walk-back noun-phrase
  capture; advisory by default (a confirmed rename mismatch keeps the
  audit's existing ``blocker`` severity).

Per the lib-promotion convention (CLAUDE.md "skill-local first, lib
promotion later"), modules here move to ``anvil/lib/`` only once a second
skill consumes them.
"""
