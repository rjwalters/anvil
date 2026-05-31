"""Tests for ``anvil.lib.figures`` — the shared on-brand figure-theming primitive.

Covers:

- **Single-source-of-truth drift guard**: ``palette.py``'s named constants are
  parsed against the hexes in ``anvil/skills/deck/assets/anvil-deck.css``
  ``:root``. Any future palette drift between the deck CSS chrome and the
  figure palette fails CI. This is the enforcement mechanism for the
  "no generator, just a test" sync contract.
- ``apply()`` sets the expected ``rcParams`` (navy first in ``axes.prop_cycle``,
  ``savefig.dpi == 200``, ``figure.figsize == (12, 7)``, transparent savefig).
  Gated behind an import-skip so the suite passes when matplotlib is absent.
- ``mermaid-theme.json`` is valid JSON, uses ``theme: base``, and its
  ``primaryColor`` / ``lineColor`` / ``fontFamily`` match the palette.
- Constants are importable without matplotlib (module-level constants; lazy
  ``apply`` import) and the package re-exports them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from anvil.lib.figures import palette


# --- Paths -------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
CSS_PATH = REPO_ROOT / "anvil" / "skills" / "deck" / "assets" / "anvil-deck.css"
MERMAID_PATH = REPO_ROOT / "anvil" / "lib" / "figures" / "mermaid-theme.json"
MPLSTYLE_PATH = REPO_ROOT / "anvil" / "lib" / "figures" / "anvil.mplstyle"
PALETTE_JSON_PATH = REPO_ROOT / "anvil" / "lib" / "figures" / "palette.json"


# --- Helpers -----------------------------------------------------------------


def _parse_css_root_vars(css_text: str) -> dict[str, str]:
    """Parse the ``--anvil-*: #hex;`` custom properties from the CSS ``:root``.

    Returns a mapping of custom-property name (e.g. ``--anvil-accent``) to its
    lowercased hex value. Only the first ``:root { ... }`` block is parsed.
    """
    match = re.search(r":root\s*\{(.*?)\}", css_text, re.DOTALL)
    assert match is not None, "anvil-deck.css must contain a :root block"
    body = match.group(1)
    pairs = re.findall(r"(--anvil-[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", body)
    return {name: value.lower() for name, value in pairs}


@pytest.fixture(scope="module")
def css_vars() -> dict[str, str]:
    return _parse_css_root_vars(CSS_PATH.read_text())


# --- Drift guard: palette.py constants == anvil-deck.css :root ----------------


def test_assets_exist() -> None:
    assert CSS_PATH.is_file(), f"missing palette source: {CSS_PATH}"
    assert MERMAID_PATH.is_file(), f"missing mermaid theme: {MERMAID_PATH}"
    assert MPLSTYLE_PATH.is_file(), f"missing mplstyle: {MPLSTYLE_PATH}"
    assert PALETTE_JSON_PATH.is_file(), f"missing palette JSON mirror: {PALETTE_JSON_PATH}"
    # palette.py resolves the mplstyle relative to its own module.
    assert palette.MPLSTYLE_PATH == MPLSTYLE_PATH


def test_palette_constants_match_css_root(css_vars: dict[str, str]) -> None:
    """SINGLE SOURCE OF TRUTH: each palette constant equals the CSS :root hex.

    If a future change edits anvil-deck.css :root without updating palette.py
    (or vice versa), this assertion fails — the drift is caught in CI.
    """
    expected = {
        "--anvil-accent": palette.ANVIL_NAVY,
        "--anvil-text": palette.ANVIL_INK,
        "--anvil-muted": palette.ANVIL_MUTED,
        "--anvil-rule": palette.ANVIL_RULE,
        "--anvil-bg": palette.ANVIL_BG,
        "--anvil-bg-section": palette.ANVIL_BG_SECTION,
        "--anvil-warning": palette.ANVIL_WARNING,
        "--anvil-success": palette.ANVIL_SUCCESS,
    }
    for css_name, constant in expected.items():
        assert css_name in css_vars, f"{css_name} missing from anvil-deck.css :root"
        assert constant.lower() == css_vars[css_name], (
            f"palette drift: {css_name}={css_vars[css_name]} in CSS but "
            f"constant={constant} in palette.py"
        )


def test_palette_json_matches_palette_py() -> None:
    """SINGLE SOURCE OF TRUTH: each ``palette.json`` value equals ``palette.py``.

    ``palette.json`` is the no-PYTHONPATH consumption path for figure scripts
    run via bare ``python3`` in a consumer install topology — the JSON ships
    alongside ``palette.py`` so a script can ``json.load(...)`` the palette
    without importing ``anvil``. This test enforces the drift contract: any
    future edit to ``palette.py`` (or ``palette.json``) without updating the
    other fails CI.
    """
    data = json.loads(PALETTE_JSON_PATH.read_text())

    # Scalar string constants — value-for-value match with palette.py.
    expected_scalars = {
        "ANVIL_NAVY": palette.ANVIL_NAVY,
        "ANVIL_INK": palette.ANVIL_INK,
        "ANVIL_MUTED": palette.ANVIL_MUTED,
        "ANVIL_GREY": palette.ANVIL_GREY,
        "ANVIL_RULE": palette.ANVIL_RULE,
        "ANVIL_BG": palette.ANVIL_BG,
        "ANVIL_BG_SECTION": palette.ANVIL_BG_SECTION,
        "ANVIL_WARNING": palette.ANVIL_WARNING,
        "ANVIL_SUCCESS": palette.ANVIL_SUCCESS,
        "ANVIL_NAVY_TINT": palette.ANVIL_NAVY_TINT,
    }
    for name, py_value in expected_scalars.items():
        assert name in data, f"{name} missing from palette.json"
        assert data[name] == py_value, (
            f"palette drift: {name}={data[name]!r} in palette.json but "
            f"{py_value!r} in palette.py"
        )

    # ANVIL_RAMP is a tuple in Python, a list in JSON; compare element-wise.
    assert "ANVIL_RAMP" in data, "ANVIL_RAMP missing from palette.json"
    json_ramp = data["ANVIL_RAMP"]
    py_ramp = list(palette.ANVIL_RAMP)
    assert json_ramp == py_ramp, (
        f"palette drift: ANVIL_RAMP={json_ramp!r} in palette.json but "
        f"{py_ramp!r} in palette.py"
    )


def test_palette_json_carries_sync_note() -> None:
    """JSON can't have comments, so the sync note lives in a ``_comment`` key.

    The note points at ``palette.py`` as the canonical Python source and
    references the drift test that enforces the contract, mirroring the
    convention used in ``mermaid-theme.json`` (see
    ``test_mermaid_theme_carries_sync_note``).
    """
    data = json.loads(PALETTE_JSON_PATH.read_text())
    assert "_comment" in data
    assert "palette.py" in data["_comment"]


def test_grey_is_alias_for_muted() -> None:
    assert palette.ANVIL_GREY == palette.ANVIL_MUTED


def test_ramp_is_navy_anchored() -> None:
    """The series ramp must start with navy and avoid the flagged off-palette hues."""
    assert palette.ANVIL_RAMP[0] == palette.ANVIL_NAVY
    assert palette.ANVIL_MUTED in palette.ANVIL_RAMP  # secondary stays brand grey
    # Guard against the rose/crimson/magenta/gold the design critic flagged.
    banned = {"#b5476b", "#bb0088"}
    assert not (set(c.lower() for c in palette.ANVIL_RAMP) & banned)


# --- Package re-exports -------------------------------------------------------


def test_package_reexports_constants() -> None:
    from anvil.lib import figures

    for name in ("ANVIL_NAVY", "ANVIL_INK", "ANVIL_MUTED", "ANVIL_RULE",
                 "ANVIL_BG", "ANVIL_BG_SECTION", "ANVIL_WARNING",
                 "ANVIL_SUCCESS", "ANVIL_RAMP", "apply"):
        assert hasattr(figures, name), f"anvil.lib.figures does not re-export {name}"


# --- mermaid-theme.json ------------------------------------------------------


def test_mermaid_theme_is_valid_json_and_on_palette() -> None:
    theme = json.loads(MERMAID_PATH.read_text())
    assert theme["theme"] == "base"
    tv = theme["themeVariables"]
    assert tv["primaryColor"] == palette.ANVIL_NAVY
    assert tv["lineColor"] == palette.ANVIL_MUTED
    assert tv["primaryBorderColor"] == palette.ANVIL_INK
    assert tv["secondaryColor"] == palette.ANVIL_BG_SECTION
    assert tv["tertiaryColor"] == palette.ANVIL_BG
    assert tv["textColor"] == palette.ANVIL_INK
    assert "Helvetica" in tv["fontFamily"]


def test_mermaid_theme_carries_sync_note() -> None:
    """JSON can't have comments, so the sync note lives in a _comment key."""
    theme = json.loads(MERMAID_PATH.read_text())
    assert "_comment" in theme
    assert "palette.py" in theme["_comment"]
    assert "anvil-deck.css" in theme["_comment"]


# --- mplstyle header sync note ------------------------------------------------


def test_mplstyle_carries_sync_header() -> None:
    text = MPLSTYLE_PATH.read_text()
    assert "keep in sync" in text
    assert "palette.py" in text
    assert "anvil-deck.css" in text


# --- apply() rcParams (matplotlib-gated) -------------------------------------

mpl = pytest.importorskip("matplotlib", reason="matplotlib not installed")


def test_apply_sets_navy_first_in_prop_cycle() -> None:
    import matplotlib as _mpl

    with _mpl.rc_context():
        palette.apply()
        cycle_colors = _mpl.rcParams["axes.prop_cycle"].by_key()["color"]
        # matplotlib normalizes hex to lowercase; compare case-insensitively.
        assert cycle_colors[0].lower().lstrip("#") == palette.ANVIL_NAVY.lstrip("#").lower()


def test_apply_sets_dpi_figsize_transparent() -> None:
    import matplotlib as _mpl

    with _mpl.rc_context():
        palette.apply()
        assert _mpl.rcParams["savefig.dpi"] == 200
        assert tuple(_mpl.rcParams["figure.figsize"]) == (12.0, 7.0)
        assert _mpl.rcParams["savefig.transparent"] is True


def test_apply_sets_brand_axis_colors() -> None:
    import matplotlib as _mpl

    def _norm(c: str) -> str:
        return _mpl.colors.to_hex(c).lower()

    with _mpl.rc_context():
        palette.apply()
        assert _norm(_mpl.rcParams["axes.labelcolor"]) == palette.ANVIL_INK.lower()
        assert _norm(_mpl.rcParams["axes.edgecolor"]) == palette.ANVIL_RULE.lower()
