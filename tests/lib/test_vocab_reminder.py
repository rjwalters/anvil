"""Tests for ``anvil/lib/vocab_reminder.py`` (issue #579).

The precision-vocabulary REMINDER tool — a stdlib port of the
rjwalters.info ``vocab`` tool. Tests assert on SHAPE (N words returned,
all drawn from the source, no dupes, determinism via injected RNG) —
never on specific draws — per the reproducibility caveat in the issue.

Coverage mirrors the curated Test Plan:

- Sampler shape: exactly N for ``n <= len``; membership; no dupes;
  ``n > len`` clamps to the whole list; empty source → ``[]``;
  determinism via injected seed (the seam exists, not a hardcoded
  sequence).
- Source resolution: sibling word-list wins when present; falls back to
  the anvil default when absent / no ``voice:`` block; never raises on a
  declared-but-missing vocabulary doc.
- The shipped default ships, is non-empty, and is SMALL (well under the
  ~3,800-word source list).
"""

from __future__ import annotations

import random
import textwrap
from pathlib import Path

import pytest

from anvil.lib.project_brief import BRIEF_FILENAME
from anvil.lib.vocab_reminder import (
    DEFAULT_SAMPLE_COUNT,
    DEFAULT_WORD_LIST_PATH,
    WORDS_SIBLING_SUFFIX,
    load_word_list,
    parse_word_list,
    resolve_word_list,
    sample_reminder_words,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

WORDS = [f"word{i}" for i in range(50)]


def _write_brief(project: Path, frontmatter: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / BRIEF_FILENAME).write_text(
        f"---\n{textwrap.dedent(frontmatter)}---\n\n# BRIEF\n",
        encoding="utf-8",
    )


_DOCS_STANZA = (
    "documents:\n"
    "          - slug: acme\n"
    "            artifact_type: essay\n"
)


# ---------------------------------------------------------------------------
# parse_word_list
# ---------------------------------------------------------------------------


def test_parse_drops_blanks_and_comments() -> None:
    text = "# header\n\nalpha\n  beta  \n# mid comment\ngamma\n\n"
    assert parse_word_list(text) == ["alpha", "beta", "gamma"]


def test_parse_dedupes_preserving_first_order() -> None:
    text = "alpha\nbeta\nalpha\ngamma\nbeta\n"
    assert parse_word_list(text) == ["alpha", "beta", "gamma"]


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_word_list(tmp_path / "nope.txt") == []


# ---------------------------------------------------------------------------
# sample_reminder_words — SHAPE assertions only
# ---------------------------------------------------------------------------


def test_sample_returns_exactly_n_when_n_le_len() -> None:
    out = sample_reminder_words(WORDS, 10, rng=random.Random(0))
    assert len(out) == 10


def test_sample_every_item_drawn_from_source() -> None:
    out = sample_reminder_words(WORDS, 15, rng=random.Random(1))
    assert all(w in WORDS for w in out)


def test_sample_no_duplicates() -> None:
    out = sample_reminder_words(WORDS, 25, rng=random.Random(2))
    assert len(out) == len(set(out))


def test_sample_n_greater_than_len_returns_whole_list() -> None:
    out = sample_reminder_words(WORDS, len(WORDS) + 100, rng=random.Random(3))
    assert len(out) == len(WORDS)
    assert set(out) == set(WORDS)


def test_sample_empty_source_returns_empty() -> None:
    assert sample_reminder_words([], 5) == []


def test_sample_non_positive_n_returns_empty() -> None:
    assert sample_reminder_words(WORDS, 0, rng=random.Random(4)) == []
    assert sample_reminder_words(WORDS, -3, rng=random.Random(4)) == []


def test_sample_default_count_constant() -> None:
    out = sample_reminder_words(WORDS, rng=random.Random(5))
    assert len(out) == DEFAULT_SAMPLE_COUNT


def test_sample_determinism_via_injected_seed() -> None:
    """Same seed → same draw (asserts the seam, not a hardcoded sequence)."""
    a = sample_reminder_words(WORDS, 12, rng=random.Random(99))
    b = sample_reminder_words(WORDS, 12, rng=random.Random(99))
    assert a == b


def test_sample_different_seeds_can_differ() -> None:
    a = sample_reminder_words(WORDS, 12, rng=random.Random(1))
    b = sample_reminder_words(WORDS, 12, rng=random.Random(2))
    # Not a strict guarantee in theory, but overwhelmingly likely for a
    # 50-word pool — confirms the RNG actually drives the draw.
    assert a != b


# ---------------------------------------------------------------------------
# resolve_word_list — source resolution + fallback
# ---------------------------------------------------------------------------


def test_resolve_sibling_word_list_wins(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          vocabulary: VOCABULARY.md
        {_DOCS_STANZA}""",
    )
    (project / "VOCABULARY.md").write_text("# guidance prose\n", encoding="utf-8")
    sibling = project / ("VOCABULARY" + WORDS_SIBLING_SUFFIX)
    sibling.write_text("zeta\neta\ntheta\n", encoding="utf-8")

    words = resolve_word_list(project, consumer_root=tmp_path)
    assert words == ["zeta", "eta", "theta"]


def test_resolve_falls_back_to_default_when_no_sibling(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          vocabulary: VOCABULARY.md
        {_DOCS_STANZA}""",
    )
    (project / "VOCABULARY.md").write_text("# guidance prose\n", encoding="utf-8")
    # No sibling .words.txt → default.
    words = resolve_word_list(project, consumer_root=tmp_path)
    assert words == load_word_list(DEFAULT_WORD_LIST_PATH)
    assert len(words) > 0


def test_resolve_falls_back_when_no_voice_block(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(project, f"        project: proj\n        {_DOCS_STANZA}")
    words = resolve_word_list(project, consumer_root=tmp_path)
    assert words == load_word_list(DEFAULT_WORD_LIST_PATH)


def test_resolve_falls_back_when_no_brief(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    words = resolve_word_list(project, consumer_root=tmp_path)
    assert words == load_word_list(DEFAULT_WORD_LIST_PATH)


def test_resolve_missing_vocabulary_doc_never_raises(tmp_path: Path) -> None:
    """Declared-but-missing vocabulary doc → graceful default fallback."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          vocabulary: VOCABULARY.md
        {_DOCS_STANZA}""",
    )
    # VOCABULARY.md intentionally absent.
    words = resolve_word_list(project, consumer_root=tmp_path)
    assert words == load_word_list(DEFAULT_WORD_LIST_PATH)


# ---------------------------------------------------------------------------
# Shipped default word list
# ---------------------------------------------------------------------------


def test_default_word_list_ships_and_is_nonempty() -> None:
    words = load_word_list(DEFAULT_WORD_LIST_PATH)
    assert DEFAULT_WORD_LIST_PATH.is_file()
    assert len(words) > 0


def test_default_word_list_is_small() -> None:
    """Guard against accidentally vendoring the ~3,800-word source list."""
    words = load_word_list(DEFAULT_WORD_LIST_PATH)
    assert len(words) <= 400, (
        "default list should stay a small curated set; consumers point at "
        "their own larger list via a sibling <stem>.words.txt"
    )


def test_default_word_list_no_duplicates() -> None:
    words = load_word_list(DEFAULT_WORD_LIST_PATH)
    assert len(words) == len(set(words))


# ---------------------------------------------------------------------------
# End-to-end: resolved list feeds the sampler with stable shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [1, 5, 20])
def test_resolved_list_samples_with_correct_shape(tmp_path: Path, n: int) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    words = resolve_word_list(project, consumer_root=tmp_path)
    out = sample_reminder_words(words, n, rng=random.Random(7))
    assert len(out) == min(n, len(words))
    assert all(w in words for w in out)
    assert len(out) == len(set(out))
