"""Tests for the shared frontmatter-extraction primitive (issue #1075).

``anvil/lib/frontmatter.py::extract_frontmatter`` consolidates five
byte-for-byte-identical ``_extract_frontmatter()`` copies that had
accumulated across ``anvil/lib/project_discovery.py``,
``anvil/lib/project_brief.py``, ``anvil/skills/project-share/lib/config.py``,
``anvil/skills/project-book/lib/config.py``, and
``anvil/skills/proposal/lib/project_brief.py``. This module tests the
shared primitive directly; the five call sites already have their own
behavioral coverage (e.g. ``test_project_discovery.py``,
``test_project_brief.py``, the project-share/project-book/proposal
skill test suites) which continues to pass unmodified against the
now-imported function.
"""

from __future__ import annotations

from anvil.lib.frontmatter import FRONTMATTER_DELIM, extract_frontmatter


def test_extracts_simple_dict() -> None:
    text = "---\nfoo: 1\nbar: two\n---\nbody text here\n"
    assert extract_frontmatter(text) == {"foo": 1, "bar": "two"}


def test_extracts_nested_structures() -> None:
    text = "---\nfoo: [a, b, c]\nnested:\n  x: 1\n  y: 2\n---\nbody\n"
    assert extract_frontmatter(text) == {
        "foo": ["a", "b", "c"],
        "nested": {"x": 1, "y": 2},
    }


def test_no_opening_delimiter_returns_none() -> None:
    assert extract_frontmatter("just some prose, no frontmatter\n") is None


def test_no_closing_delimiter_returns_none() -> None:
    text = "---\nfoo: 1\nno closer here\n"
    assert extract_frontmatter(text) is None


def test_non_dict_yaml_returns_none() -> None:
    # A bare scalar / sequence parses as valid YAML but is not a dict.
    assert extract_frontmatter("---\n- a\n- b\n---\nbody\n") is None
    assert extract_frontmatter("---\njust a string\n---\nbody\n") is None


def test_malformed_yaml_returns_none() -> None:
    # Unbalanced flow-mapping brace is invalid YAML.
    text = "---\nfoo: {unbalanced\n---\nbody\n"
    assert extract_frontmatter(text) is None


def test_leading_blank_lines_are_tolerated() -> None:
    text = "\n\n---\nfoo: 1\n---\nbody\n"
    assert extract_frontmatter(text) == {"foo": 1}


def test_leading_bom_is_stripped() -> None:
    text = "﻿---\nfoo: 1\n---\nbody\n"
    assert extract_frontmatter(text) == {"foo": 1}


def test_empty_text_returns_none() -> None:
    assert extract_frontmatter("") is None


def test_only_opening_delimiter_returns_none() -> None:
    assert extract_frontmatter("---\n") is None


def test_empty_frontmatter_body_returns_none() -> None:
    # An empty YAML body parses to None, not a dict.
    assert extract_frontmatter("---\n---\nbody\n") is None


def test_frontmatter_delim_constant_is_triple_dash() -> None:
    assert FRONTMATTER_DELIM == "---"
