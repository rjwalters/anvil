"""Tests for ``anvil.lib.theme`` (issue #322 — Phase A theme primitive).

Covers the framework-level pieces of the theme system:

- :class:`Theme` pydantic model field shape (typed knobs +
  ``extra="allow"`` for per-skill nested blocks).
- :func:`load_theme` — absence-tolerant theme.yml reader.
- :func:`find_consumer_root` — walks up to find ``<root>/.anvil/``.
- :func:`resolve_theme_for_path` — convenience combiner.

The per-skill *asset resolver* (memo only in Phase A) is tested
separately under ``anvil/skills/memo/tests/test_theme_resolution.py``.

Per the #58 packaging convention, this file's filename
(``test_theme.py``) is unique within the ``tests/lib/`` tree so pytest's
cross-file basename discovery doesn't collide.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from anvil.lib.theme import (
    ANVIL_DIRNAME,
    THEME_FILENAME,
    THEMES_DIRNAME,
    Theme,
    find_consumer_root,
    load_theme,
    resolve_theme_for_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_theme_yml(
    consumer_root: Path, theme_name: str, body: str
) -> Path:
    """Write a ``<consumer>/.anvil/themes/<name>/theme.yml`` and return path."""
    theme_dir = consumer_root / ANVIL_DIRNAME / THEMES_DIRNAME / theme_name
    theme_dir.mkdir(parents=True, exist_ok=True)
    theme_file = theme_dir / THEME_FILENAME
    theme_file.write_text(body, encoding="utf-8")
    return theme_file


def _seed_consumer(tmp_path: Path) -> Path:
    """Create a fake consumer repo with an empty ``.anvil/`` marker."""
    (tmp_path / ANVIL_DIRNAME).mkdir(parents=True, exist_ok=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Theme model
# ---------------------------------------------------------------------------


def test_theme_model_minimal():
    """A Theme with just the required ``name`` field constructs cleanly."""
    theme = Theme(name="my-brand")
    assert theme.name == "my-brand"
    assert theme.accent_color is None
    assert theme.studio is None
    assert theme.render_engine is None
    assert theme.raw == {}


def test_theme_model_all_typed_fields():
    """All five typed framework-level fields round-trip."""
    theme = Theme(
        name="sphere-semi",
        accent_color="#526AE5",
        studio="Sphere Semi",
        body_font="Helvetica Neue",
        mono_font="Menlo",
        render_engine="xelatex",
        raw={"memo": {"signature_color": "#526AE5"}},
    )
    assert theme.accent_color == "#526AE5"
    assert theme.studio == "Sphere Semi"
    assert theme.body_font == "Helvetica Neue"
    assert theme.mono_font == "Menlo"
    assert theme.render_engine == "xelatex"


def test_theme_skill_block_returns_dict_for_known_skill():
    """``skill_block`` extracts nested per-skill knobs from ``raw``."""
    theme = Theme(
        name="2am-logic",
        raw={
            "memo": {"signature_color": "#E94560"},
            "proposal": {"signature_color": "#E94560"},
        },
    )
    assert theme.skill_block("memo") == {"signature_color": "#E94560"}
    assert theme.skill_block("proposal") == {"signature_color": "#E94560"}


def test_theme_skill_block_empty_for_unknown_skill():
    """``skill_block`` returns an empty dict for a skill the theme omits."""
    theme = Theme(name="2am-logic", raw={"memo": {}})
    assert theme.skill_block("ip-uspto") == {}


def test_theme_skill_block_handles_non_dict_block():
    """A non-dict value at a skill key returns an empty dict (graceful)."""
    theme = Theme(name="weird", raw={"memo": "not a dict"})
    assert theme.skill_block("memo") == {}


def test_theme_skill_block_returns_copy():
    """The returned dict is a copy — mutation does not affect the theme."""
    theme = Theme(name="x", raw={"memo": {"a": 1}})
    block = theme.skill_block("memo")
    block["a"] = 999
    # Re-fetching should still show the original value.
    assert theme.skill_block("memo") == {"a": 1}


# ---------------------------------------------------------------------------
# find_consumer_root
# ---------------------------------------------------------------------------


def test_find_consumer_root_locates_anvil_dir(tmp_path):
    """Walking up from a nested path finds the dir containing ``.anvil/``."""
    consumer = _seed_consumer(tmp_path)
    nested = consumer / "projects" / "brains-for-robots" / "investment-memo"
    nested.mkdir(parents=True)
    assert find_consumer_root(nested) == consumer


def test_find_consumer_root_returns_consumer_itself_when_started_at_root(
    tmp_path,
):
    """Starting at the consumer root returns the consumer root."""
    consumer = _seed_consumer(tmp_path)
    assert find_consumer_root(consumer) == consumer


def test_find_consumer_root_none_when_no_marker(tmp_path):
    """No ``.anvil/`` anywhere upstream → ``None``."""
    # No _seed_consumer — there's no .anvil/ marker.
    nested = tmp_path / "nested" / "deep"
    nested.mkdir(parents=True)
    assert find_consumer_root(nested) is None


def test_find_consumer_root_tolerates_nonexistent_path(tmp_path):
    """A start path that doesn't exist still walks up correctly."""
    consumer = _seed_consumer(tmp_path)
    # ``ghost`` does not exist on disk.
    ghost = consumer / "ghost" / "version-dir.1"
    assert find_consumer_root(ghost) == consumer


def test_find_consumer_root_walks_past_files(tmp_path):
    """A file path's parent dir starts the walk."""
    consumer = _seed_consumer(tmp_path)
    nested = consumer / "thread"
    nested.mkdir()
    file_path = nested / "memo.md"
    file_path.write_text("body", encoding="utf-8")
    assert find_consumer_root(file_path) == consumer


# ---------------------------------------------------------------------------
# load_theme
# ---------------------------------------------------------------------------


def test_load_theme_returns_none_when_consumer_root_is_none():
    """``consumer_root=None`` short-circuits to ``None`` without I/O."""
    assert load_theme(None, "sphere-semi") is None


def test_load_theme_returns_none_when_theme_name_is_none(tmp_path):
    """``theme_name=None`` (no theme declared) → ``None``."""
    consumer = _seed_consumer(tmp_path)
    assert load_theme(consumer, None) is None


def test_load_theme_returns_none_when_theme_name_is_empty(tmp_path):
    """Empty / whitespace-only theme name → ``None``."""
    consumer = _seed_consumer(tmp_path)
    assert load_theme(consumer, "") is None
    assert load_theme(consumer, "   ") is None


def test_load_theme_returns_none_when_theme_dir_missing(tmp_path):
    """A theme name pointing to a missing dir → ``None`` (no raise)."""
    consumer = _seed_consumer(tmp_path)
    assert load_theme(consumer, "ghost-theme") is None


def test_load_theme_returns_none_when_theme_yml_missing(tmp_path):
    """Theme dir exists but no theme.yml inside → ``None``."""
    consumer = _seed_consumer(tmp_path)
    theme_dir = consumer / ANVIL_DIRNAME / THEMES_DIRNAME / "thin"
    theme_dir.mkdir(parents=True)
    # No theme.yml written.
    assert load_theme(consumer, "thin") is None


def test_load_theme_returns_none_when_theme_yml_unparseable(tmp_path):
    """Malformed YAML → ``None`` (no raise)."""
    consumer = _seed_consumer(tmp_path)
    # Unclosed bracket → YAML parse error.
    _write_theme_yml(consumer, "broken", "accent_color: [unclosed")
    assert load_theme(consumer, "broken") is None


def test_load_theme_returns_none_for_non_dict_top_level(tmp_path):
    """YAML that parses to a list (not a dict) → ``None``."""
    consumer = _seed_consumer(tmp_path)
    _write_theme_yml(consumer, "wrongshape", "- foo\n- bar\n")
    assert load_theme(consumer, "wrongshape") is None


def test_load_theme_minimal_yaml(tmp_path):
    """A theme.yml with just one field loads with the rest as None."""
    consumer = _seed_consumer(tmp_path)
    _write_theme_yml(
        consumer,
        "minimal",
        "accent_color: '#FF00AA'\n",
    )
    theme = load_theme(consumer, "minimal")
    assert theme is not None
    assert theme.name == "minimal"
    assert theme.accent_color == "#FF00AA"
    assert theme.studio is None
    assert theme.render_engine is None


def test_load_theme_full_yaml(tmp_path):
    """All framework-level typed fields round-trip from YAML."""
    consumer = _seed_consumer(tmp_path)
    body = textwrap.dedent(
        """
        accent_color: "#526AE5"
        studio: "Sphere Semi"
        body_font: "Helvetica Neue"
        mono_font: "Menlo"
        render_engine: xelatex
        """
    ).strip() + "\n"
    _write_theme_yml(consumer, "sphere-semi", body)
    theme = load_theme(consumer, "sphere-semi")
    assert theme is not None
    assert theme.name == "sphere-semi"
    assert theme.accent_color == "#526AE5"
    assert theme.studio == "Sphere Semi"
    assert theme.body_font == "Helvetica Neue"
    assert theme.mono_font == "Menlo"
    assert theme.render_engine == "xelatex"


def test_load_theme_preserves_per_skill_blocks(tmp_path):
    """Per-skill nested blocks survive via the ``raw`` field."""
    consumer = _seed_consumer(tmp_path)
    body = textwrap.dedent(
        """
        accent_color: "#E94560"
        memo:
          signature_color: "#E94560"
          extra_pin: foo
        proposal:
          signature_color: "#E94560"
        """
    ).strip() + "\n"
    _write_theme_yml(consumer, "2am-logic", body)
    theme = load_theme(consumer, "2am-logic")
    assert theme is not None
    memo_block = theme.skill_block("memo")
    assert memo_block == {"signature_color": "#E94560", "extra_pin": "foo"}
    proposal_block = theme.skill_block("proposal")
    assert proposal_block == {"signature_color": "#E94560"}
    # Unmentioned skill returns empty dict.
    assert theme.skill_block("ip-uspto") == {}


def test_load_theme_tolerates_wrong_type_for_typed_field(tmp_path):
    """A non-string value for a typed field falls back to ``None``.

    The field-level resilience matches the broader graceful-degrade
    contract: misconfiguration in theme.yml shouldn't crash the render.
    """
    consumer = _seed_consumer(tmp_path)
    body = textwrap.dedent(
        """
        accent_color: 42
        studio: "Real Studio"
        """
    ).strip() + "\n"
    _write_theme_yml(consumer, "weird", body)
    theme = load_theme(consumer, "weird")
    assert theme is not None
    # accent_color was a wrong type → treated as absent.
    assert theme.accent_color is None
    # studio was correct → present.
    assert theme.studio == "Real Studio"


# ---------------------------------------------------------------------------
# resolve_theme_for_path (convenience combiner)
# ---------------------------------------------------------------------------


def test_resolve_theme_for_path_happy_path(tmp_path):
    """Convenience combiner walks up + loads theme in one call."""
    consumer = _seed_consumer(tmp_path)
    _write_theme_yml(
        consumer,
        "2am-logic",
        "accent_color: '#E94560'\nstudio: '2AM Logic'\n",
    )
    nested = consumer / "projects" / "demo" / "thread.1"
    nested.mkdir(parents=True)
    theme = resolve_theme_for_path(nested, "2am-logic")
    assert theme is not None
    assert theme.studio == "2AM Logic"


def test_resolve_theme_for_path_returns_none_when_no_consumer_root(tmp_path):
    """No ``.anvil/`` upstream → ``None`` (theme can't apply)."""
    # No _seed_consumer — no .anvil/ marker.
    nested = tmp_path / "nested"
    nested.mkdir()
    assert resolve_theme_for_path(nested, "sphere-semi") is None


def test_resolve_theme_for_path_returns_none_when_theme_missing(tmp_path):
    """Consumer found but theme name unknown → ``None``."""
    consumer = _seed_consumer(tmp_path)
    nested = consumer / "nested"
    nested.mkdir()
    assert resolve_theme_for_path(nested, "no-such-theme") is None
