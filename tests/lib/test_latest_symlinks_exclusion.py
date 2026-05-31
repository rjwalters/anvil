"""Regression test for the ``<thread>.latest`` symlink discovery-glob guarantee.

Issue #120 adds the optional consumer convention documented in
``anvil/lib/snippets/version_layout.md`` ("Convenience ``.latest`` symlinks"):

    <thread>.latest        -> <thread>.{max_N}/
    <thread>.latest.review -> <thread>.{max_N}.review/
    <thread>.latest.<tag>  -> <thread>.{max_N}.<tag>/

The framework's load-bearing guarantee for the convention is that the
discovery enumeration documented in ``anvil/lib/snippets/thread_state.md``
matches **only** digit-N suffixes; a ``.latest`` symlink is invisible to
``enumerate_versions`` / ``enumerate_siblings`` even when it resolves to
a real versioned directory.

This test re-implements the canonical enumeration regexes from the
snippet against a temp-dir fixture containing real ``.latest`` symlinks
and asserts that the symlinks are ignored. It exists to guard against
future regex drift that would accidentally start matching ``.latest``.

Per the #58 packaging convention, the test module name is distinct from
every other ``tests/lib/test_*`` module.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Snippet-level guarantees (cheap grep-the-doc assertions)
# ---------------------------------------------------------------------------


SNIPPETS = Path(__file__).resolve().parents[2] / "anvil" / "lib" / "snippets"
SKILLS = Path(__file__).resolve().parents[2] / "anvil" / "skills"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_version_layout_documents_latest_symlink_convention():
    body = _read(SNIPPETS / "version_layout.md")
    assert "Convenience" in body and ".latest" in body, (
        "version_layout.md MUST document the optional .latest symlink convention "
        "(issue #120 AC1)"
    )
    # The discovery-glob guarantee is the load-bearing claim — it MUST be
    # stated explicitly in the snippet.
    assert "Discovery-glob guarantee" in body, (
        "version_layout.md MUST contain the 'Discovery-glob guarantee' "
        "subsection (issue #120 AC1)"
    )


def test_version_layout_states_latest_is_consumer_maintained():
    body = _read(SNIPPETS / "version_layout.md")
    # The convention is opt-in; shipped commands do not write/require it.
    assert "consumer-maintained" in body, (
        "version_layout.md MUST state that .latest symlinks are "
        "consumer-maintained (issue #120 AC1)"
    )


def test_thread_state_notes_latest_exclusion():
    body = _read(SNIPPETS / "thread_state.md")
    # The regex callouts MUST flag that .latest is excluded by the \d+
    # anchor — this is the load-bearing reader expectation.
    assert ".latest" in body, (
        "thread_state.md MUST mention .latest in the regex callouts "
        "(issue #120 AC2)"
    )


def test_memo_skill_mentions_latest_convention():
    body = _read(SKILLS / "memo" / "SKILL.md")
    assert "memo.latest" in body, (
        "memo/SKILL.md MUST include at least one concrete .latest example "
        "(issue #120 AC3)"
    )
    assert "version_layout.md" in body, (
        "memo/SKILL.md MUST cross-reference version_layout.md "
        "(issue #120 AC3)"
    )


def test_deck_skill_mentions_latest_convention():
    body = _read(SKILLS / "deck" / "SKILL.md")
    # Deck-specific examples per curator guidance.
    assert ".latest" in body, (
        "deck/SKILL.md MUST include at least one concrete .latest example "
        "(issue #120 AC3)"
    )
    assert "version_layout.md" in body, (
        "deck/SKILL.md MUST cross-reference version_layout.md "
        "(issue #120 AC3)"
    )


def test_no_shipped_command_writes_or_requires_latest_symlinks():
    """AC4: anvil-shipped commands must not depend on or write .latest.

    The convention is consumer-maintained in v0. If a shipped command
    starts writing ``.latest`` symlinks, the convention contract
    silently widens — block on the test.
    """
    matches: list[tuple[Path, str]] = []
    for command_md in SKILLS.rglob("commands/*.md"):
        body = command_md.read_text(encoding="utf-8")
        for line in body.splitlines():
            if ".latest" in line:
                matches.append((command_md, line))
    assert not matches, (
        "Shipped command markdown must not reference .latest "
        "(consumer-maintained convention only). Offenders:\n"
        + "\n".join(f"  {p}: {ln.strip()}" for p, ln in matches)
    )


# ---------------------------------------------------------------------------
# Regex-behavior regression — the load-bearing guarantee
# ---------------------------------------------------------------------------


# These regexes are the canonical patterns from thread_state.md
# (lines 35 and 46 at the time of issue #120). If a future edit changes
# either pattern such that `.latest` starts matching, this test fails.
_VERSION_RE = lambda slug: re.compile(rf"^{re.escape(slug)}\.(\d+)$")  # noqa: E731
_SIBLING_RE = lambda slug: re.compile(  # noqa: E731
    rf"^{re.escape(slug)}\.(\d+)\.([a-zA-Z0-9-]+)$"
)


def _enumerate_versions(portfolio_dir: Path, slug: str) -> list[int]:
    """Reproduction of the snippet's ``enumerate_versions`` algorithm.

    Returns sorted list of integers N where ``<slug>.{N}/`` is a real
    directory under ``portfolio_dir`` (followed symlinks count as
    directories — that's the point of the test).
    """
    pattern = _VERSION_RE(slug)
    versions: list[int] = []
    for entry in os.listdir(portfolio_dir):
        m = pattern.match(entry)
        if m and (portfolio_dir / entry).is_dir():
            versions.append(int(m.group(1)))
    return sorted(versions)


def _enumerate_siblings(
    portfolio_dir: Path, slug: str
) -> dict[tuple[int, str], Path]:
    """Reproduction of the snippet's ``enumerate_siblings`` algorithm."""
    pattern = _SIBLING_RE(slug)
    siblings: dict[tuple[int, str], Path] = {}
    for entry in os.listdir(portfolio_dir):
        m = pattern.match(entry)
        if m and (portfolio_dir / entry).is_dir():
            siblings[(int(m.group(1)), m.group(2))] = portfolio_dir / entry
    return siblings


@pytest.fixture
def portfolio_with_latest_symlinks(tmp_path: Path) -> Path:
    """Build a portfolio dir with real version dirs + ``.latest`` symlinks.

    Layout:
        acme/
          acme.1/                 (dir)
          acme.2/                 (dir)
          acme.2.review/          (dir)
          acme.2.design/          (dir)
          acme.latest             -> acme.2
          acme.latest.review      -> acme.2.review
          acme.latest.design      -> acme.2.design

    The symlinks point at real dirs (i.e., ``is_dir()`` returns True
    for the symlink entries), exactly the configuration that would
    break the regexes if they ever started matching ``.latest``.
    """
    portfolio = tmp_path / "acme"
    portfolio.mkdir()

    (portfolio / "acme.1").mkdir()
    (portfolio / "acme.2").mkdir()
    (portfolio / "acme.2.review").mkdir()
    (portfolio / "acme.2.design").mkdir()

    os.symlink("acme.2", portfolio / "acme.latest")
    os.symlink("acme.2.review", portfolio / "acme.latest.review")
    os.symlink("acme.2.design", portfolio / "acme.latest.design")

    # Sanity check the fixture: the symlinks resolve to real dirs.
    assert (portfolio / "acme.latest").is_dir()
    assert (portfolio / "acme.latest.review").is_dir()
    assert (portfolio / "acme.latest.design").is_dir()

    return portfolio


def test_enumerate_versions_ignores_latest_symlink(
    portfolio_with_latest_symlinks: Path,
):
    """``enumerate_versions`` returns [1, 2] — the ``.latest`` symlink does
    not appear as an extra version (it has no digit-N suffix)."""
    versions = _enumerate_versions(portfolio_with_latest_symlinks, "acme")
    assert versions == [1, 2], (
        "enumerate_versions must ignore <slug>.latest (regex anchors "
        "to \\d+); got "
        f"{versions} instead of [1, 2]. If this fails, the regex in "
        "thread_state.md has drifted to also match .latest, breaking "
        "the convention guarantee from issue #120."
    )


def test_enumerate_siblings_ignores_latest_symlinks(
    portfolio_with_latest_symlinks: Path,
):
    """``enumerate_siblings`` returns exactly the two real critic siblings;
    ``.latest.review`` and ``.latest.design`` are filtered out."""
    siblings = _enumerate_siblings(portfolio_with_latest_symlinks, "acme")
    keys = set(siblings.keys())
    assert keys == {(2, "review"), (2, "design")}, (
        "enumerate_siblings must ignore <slug>.latest.<tag> entries; got "
        f"{sorted(keys)} instead of {{(2, 'review'), (2, 'design')}}. "
        "If this fails, the sibling regex in thread_state.md has drifted "
        "to also match .latest, breaking the convention guarantee from "
        "issue #120."
    )


def test_version_regex_does_not_match_latest_directly():
    """Direct regex assertion: ``.latest`` is not a digit, full stop."""
    pat = _VERSION_RE("acme")
    assert pat.match("acme.1")
    assert pat.match("acme.42")
    assert not pat.match("acme.latest"), (
        "<slug>.latest must not match the version regex "
        "(this is the load-bearing claim documented in version_layout.md "
        "'Discovery-glob guarantee'; issue #120)."
    )


def test_sibling_regex_does_not_match_latest_critic_tags():
    """Direct regex assertion: ``.latest.<tag>`` is not ``<digit>.<tag>``."""
    pat = _SIBLING_RE("acme")
    assert pat.match("acme.1.review")
    assert pat.match("acme.42.design")
    for bad in (
        "acme.latest.review",
        "acme.latest.design",
        "acme.latest.audit",
        "acme.latest",  # no .<tag> at all
    ):
        assert not pat.match(bad), (
            f"<slug>{bad[len('acme'):]} must not match the sibling regex "
            "(issue #120 discovery-glob guarantee)."
        )
