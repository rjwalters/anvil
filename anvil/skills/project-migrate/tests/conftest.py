"""Pytest fixtures + sys.path wiring for `anvil:project-migrate` tests (issue #297).

Mirrors the pattern in ``anvil/skills/memo/tests/`` where the per-skill
lib lives at ``anvil/skills/<skill>/lib/`` and tests import the modules
via a sys.path insert. The skill-local lib has a package __init__ so we
add the SKILL root (not the lib root) to sys.path and import via the
``lib.<module>`` form.

Also adds the tests/ directory itself to sys.path so test modules can
``from _fixtures import ...`` without ceremony.
"""

from __future__ import annotations

import sys
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_SKILL_ROOT = _HERE.parent
# Skill root gives us ``from lib.detect import ...``.
sys.path.insert(0, str(_SKILL_ROOT))
# Tests dir gives us ``from _fixtures import ...``.
sys.path.insert(0, str(_HERE))
