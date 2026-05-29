"""Pytest configuration: ensure the repo root is on ``sys.path``.

Anvil ships no ``pyproject.toml`` yet, so we don't rely on an installed
package. Tests import ``anvil.lib.*`` directly from the source tree.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers used by the test suite.

    - ``network``: tests that hit live external APIs (e.g. Crossref).
      Skipped by default; opt in with ``pytest -m network``.
    """

    config.addinivalue_line(
        "markers",
        "network: tests that perform live network calls (opt-in, run "
        "with `pytest -m network`).",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip ``network``-marked tests unless explicitly selected.

    Default ``pytest`` invocation skips them so CI never hits the live
    network. Operators opt in with ``pytest -m network``.
    """

    marker_expr = config.getoption("-m", default="") or ""
    if "network" in marker_expr:
        return
    skip_network = pytest.mark.skip(
        reason="network test skipped by default; run with `pytest -m network`"
    )
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip_network)
