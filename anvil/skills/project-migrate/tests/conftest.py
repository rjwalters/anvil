"""Pytest sys.path wiring for `anvil:project-migrate` tests (issue #297).

Adds the tests directory itself to sys.path so test modules can do
``from _fixtures import ...`` and ``from _project_migrate_skill_lib import ...``
without ceremony.

The skill's lib modules are loaded under a unique package name
(``project_migrate_lib``) via ``_project_migrate_skill_lib`` to
avoid cross-skill collisions when this test suite runs alongside
other per-skill test suites that each ship their own ``lib/``
package (e.g., ``rubric-rebackport``). See issue #358 / PR #362
for the precedent. The helper filename itself is also unique
(rather than the precedent's ``_skill_lib.py``) to dodge the
secondary ``sys.modules['_skill_lib']`` cache collision that arises
when both suites ship identically-named helpers — see issue #367.
"""

from __future__ import annotations

import sys
from pathlib import Path


_HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(_HERE))
