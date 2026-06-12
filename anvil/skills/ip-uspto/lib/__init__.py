"""Skill-local lib for ``anvil:ip-uspto`` (first module: issue #445).

The skill directory name is hyphenated (``ip-uspto``), so this package is
NOT importable via a dotted ``python -m`` path. Consumers invoke modules
by direct file path (the project-migrate / project-share precedent):

    python3 anvil/skills/ip-uspto/lib/inventorship_evidence.py --help

and tests load modules by file path via ``importlib`` under a unique
module name (see ``tests/test_ip_uspto_inventorship_evidence.py``).

Per the lib-promotion convention (CLAUDE.md "skill-local first, lib
promotion later"), modules here move to ``anvil/lib/`` only once a
second skill consumes them. ``inventorship_evidence.py`` is deliberately
consumer-agnostic (repo path + element->paths map inputs; no BRIEF or
claims parsing) so ``anvil:ip-uspto-provisional``'s deferred
inventorship-lite pass (#480) can become that second consumer.
"""
