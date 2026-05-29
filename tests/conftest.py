"""Pytest configuration: ensure the repo root is on ``sys.path``.

Anvil ships no ``pyproject.toml`` yet, so we don't rely on an installed
package. Tests import ``anvil.lib.*`` directly from the source tree.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
