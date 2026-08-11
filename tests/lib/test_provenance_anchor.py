"""Tests for ``anvil/lib/provenance_anchor.py`` (issue #868).

Covers the acceptance criteria from #868:

- A ``provenance.md`` row's ``Anchor`` cell (a verbatim quoted snippet)
  is resolved against the on-disk corpus file by searching the WHOLE
  file, not just the cited ``Line range`` hint.
- A drifted anchor (text still present, but at a different line than
  cited) is detected and reported distinctly (``DRIFTED``) from an
  unsupported/missing claim (``NOT_FOUND``).
- A row whose anchor text is deleted from the corpus entirely degrades
  to ``NOT_FOUND``, not ``DRIFTED`` (edge case (a)).
- A row whose anchor text coincidentally also appears elsewhere in the
  file resolves to the occurrence nearest the cited hint, without a
  false-positive drift classification (edge case (b)).
- A legacy row with no ``Anchor`` cell (or a table with no ``Anchor``
  column at all) reports ``NO_ANCHOR`` — never an error, never a false
  drift signal.
- ``repoint_drifted_anchors`` mechanically rewrites only the ``Line
  range`` cell of ``DRIFTED`` rows, leaving every other row and every
  other cell byte-identical.
- The CLI ``check``/``repoint`` subcommands round-trip and always exit
  ``0`` (advisory/mechanical, never a pass/fail gate).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib.provenance_anchor import (
    STATUS_DRIFTED,
    STATUS_FILE_NOT_FOUND,
    STATUS_NO_ANCHOR,
    STATUS_NOT_FOUND,
    STATUS_RESOLVED,
    check_provenance_anchors,
    main,
    parse_provenance_table,
    repoint_drifted_anchors,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


CORPUS_TEXT = "\n".join(
    [f"filler line {i}" for i in range(1, 10)]
    + ["The factory burned down in the summer of 1942 during the night shift."]
    + ["filler line 11", "filler line 12"]
)


@pytest.fixture()
def corpus_dir(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    _write(root / "nita3.txt", CORPUS_TEXT)
    return root


def _provenance_table(rows: str) -> str:
    return (
        "# Claim provenance\n\n"
        "| Claim | Source file | Line range | Anchor | Notes |\n"
        "|-------|-------------|------------|--------|-------|\n" + rows
    )


def _one_table(n_rows: int, prefix: str = "row") -> str:
    """A single conforming claim table with ``n_rows`` synthetic data
    rows (content is irrelevant to row-count assertions)."""
    header = "| Claim | Source file | Line range | Anchor | Notes |\n"
    sep = "|-------|-------------|------------|--------|-------|\n"
    body = "".join(
        f'| "{prefix} claim {i}" | nita3.txt | {i} | "filler line {i}" | note {i} |\n'
        for i in range(1, n_rows + 1)
    )
    return header + sep + body


def _multi_table_doc(*row_counts: int, blank_between: bool = True) -> str:
    """Build a ``provenance.md`` with one table per entry in
    ``row_counts``, each table holding that many synthetic data rows."""
    parts = ["# Claim provenance\n\n"]
    for i, count in enumerate(row_counts):
        if i > 0:
            if blank_between:
                parts.append(f"\n## Chapter {i + 1}\n\n")
            # else: no separator at all -> tables are directly adjacent.
        parts.append(_one_table(count, prefix=f"t{i}"))
    return "".join(parts)


# ---------------------------------------------------------------------------
# parse_provenance_table
# ---------------------------------------------------------------------------


class TestParseProvenanceTable:
    def test_parses_five_column_table(self, tmp_path: Path):
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                '| "The factory burned down" | nita3.txt | 3-5 | "The factory burned down in the summer of 1942" | verbatim recall |\n'
            ),
        )
        table = parse_provenance_table(path)
        assert table.anchor_col is not None
        assert len(table.rows) == 1
        row = table.rows[0]
        assert row.source_file == "nita3.txt"
        assert row.line_range == (3, 5)
        assert row.anchor == "The factory burned down in the summer of 1942"

    def test_parses_legacy_four_column_table(self, tmp_path: Path):
        path = _write(
            tmp_path / "provenance.md",
            "| Claim | Source file | Line range | Notes |\n"
            "|-------|-------------|------------|-------|\n"
            '| "The factory burned down" | nita3.txt | 3-5 | verbatim recall |\n',
        )
        table = parse_provenance_table(path)
        assert table.anchor_col is None
        assert len(table.rows) == 1
        assert table.rows[0].anchor is None

    def test_empty_anchor_cell_is_none(self, tmp_path: Path):
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table("| Legacy claim | nita3.txt | 1-2 |  | pre-anchor row |\n"),
        )
        table = parse_provenance_table(path)
        assert table.rows[0].anchor is None

    def test_single_line_range(self, tmp_path: Path):
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table("| A claim | nita3.txt | 7 | \"filler line 7\" | note |\n"),
        )
        table = parse_provenance_table(path)
        assert table.rows[0].line_range == (7, 7)


# ---------------------------------------------------------------------------
# Multi-table regression (issue #934) — a provenance.md holding several
# independent claim tables must have EVERY table's rows parsed, not just
# the first. Row counts are hand-computed from the synthetic fixtures
# built by _multi_table_doc()/_one_table() above.
# ---------------------------------------------------------------------------


class TestMultiTableParsing:
    @pytest.mark.parametrize(
        "row_counts",
        [
            (3, 2),  # 2 tables, 5 rows
            (2, 3, 4),  # 3 tables, 9 rows
            (1, 2, 3, 4, 5),  # 5 tables, 15 rows
            (1,) * 9,  # 9 tables, 9 rows
            (5, 8, 3, 12, 1, 7, 9, 4, 6),  # 9 tables, 55 rows (varied sizes)
        ],
    )
    def test_row_count_matches_hand_count_across_tables(
        self, tmp_path: Path, row_counts
    ):
        path = _write(
            tmp_path / "provenance.md", _multi_table_doc(*row_counts)
        )
        table = parse_provenance_table(path)
        assert len(table.tables) == len(row_counts)
        assert len(table.rows) == sum(row_counts)
        # Every table's own rows are attributed to it via table_index.
        for i, count in enumerate(row_counts):
            assert sum(1 for r in table.rows if r.table_index == i) == count

    def test_two_table_baseline_regression_guard(self, tmp_path: Path):
        """The narrowest possible regression guard for #934: a
        single-table map must still report exactly its own rows (this
        already passed before the fix — see the pre-existing single-
        table tests above), and a TWO-table map must report the SUM of
        both tables' rows, not just the first table's."""
        path = _write(tmp_path / "provenance.md", _multi_table_doc(4, 6))
        table = parse_provenance_table(path)
        assert len(table.tables) == 2
        assert len(table.rows) == 10

    def test_adjacent_tables_with_no_blank_line_both_parsed(self, tmp_path: Path):
        """A second table's header immediately follows the first
        table's last data row, with no blank line in between."""
        path = _write(
            tmp_path / "provenance.md",
            _multi_table_doc(3, 4, blank_between=False),
        )
        table = parse_provenance_table(path)
        assert len(table.tables) == 2
        assert len(table.rows) == 7

    def test_nonconforming_table_reported_not_silently_skipped(self, tmp_path: Path):
        doc = (
            "# Claim provenance\n\n"
            + _one_table(2, prefix="t0")
            + "\n## Unrelated table\n\n"
            "| Foo | Bar |\n"
            "|-----|-----|\n"
            "| 1 | 2 |\n"
            "| 3 | 4 |\n"
            "\n## Chapter 2\n\n"
            + _one_table(3, prefix="t1")
        )
        path = _write(tmp_path / "provenance.md", doc)
        table = parse_provenance_table(path)
        # Only the two conforming (Claim/Source) tables contribute rows.
        assert len(table.tables) == 2
        assert len(table.rows) == 5
        # The non-conforming table is reported, not dropped.
        assert len(table.skipped_tables) == 1
        skipped = table.skipped_tables[0]
        assert skipped.header == ["Foo", "Bar"]
        assert "Claim/Source" in skipped.reason

    def test_zero_conforming_tables_still_returns_empty_result(self, tmp_path: Path):
        path = _write(
            tmp_path / "provenance.md",
            "# No tables here\n\nJust prose.\n",
        )
        table = parse_provenance_table(path)
        assert table.tables == []
        assert table.rows == []
        assert table.header == []
        assert table.line_range_col is None
        assert table.anchor_col is None


# ---------------------------------------------------------------------------
# resolve_anchor / check_provenance_anchors
# ---------------------------------------------------------------------------


class TestResolveAnchor:
    def test_resolved_when_anchor_at_hinted_line(self, tmp_path: Path, corpus_dir: Path):
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                '| "factory" | nita3.txt | 10 | "The factory burned down in the summer of 1942" | recall |\n'
            ),
        )
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["counts"][STATUS_RESOLVED] == 1
        assert report["drifted"] is False

    def test_drifted_when_anchor_moved(self, tmp_path: Path, corpus_dir: Path):
        """The canary's exact failure mode: a 6-line insertion above the
        cited passage shifts the row's Line range hint out from under it."""
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                '| "factory" | nita3.txt | 3-5 | "The factory burned down in the summer of 1942" | recall |\n'
            ),
        )
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["counts"][STATUS_DRIFTED] == 1
        assert report["drifted"] is True
        row = report["rows"][0]
        assert row["status"] == STATUS_DRIFTED
        assert row["resolved_range"] == [10, 10]
        # Distinct classification from a content-mismatch/not-found
        # finding (the detail text explains the distinction, so it
        # legitimately mentions "MISMATCH" — assert on the status enum,
        # not an absence-of-substring in the human-readable prose).
        assert row["status"] != "MISMATCH"
        assert row["status"] != STATUS_NOT_FOUND
        assert "stale" in row["detail"]

    def test_anchor_deleted_degrades_to_not_found(self, tmp_path: Path, corpus_dir: Path):
        """Edge case (a): the anchor text is gone entirely — NOT_FOUND,
        not a drift finding."""
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                '| "gone" | nita3.txt | 3-5 | "this text was never in the corpus at all" | recall |\n'
            ),
        )
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["counts"][STATUS_NOT_FOUND] == 1
        assert report["counts"][STATUS_DRIFTED] == 0
        assert report["drifted"] is False

    def test_coincidental_duplicate_resolves_to_nearest_hint(self, tmp_path: Path):
        """Edge case (b): the anchor text appears twice in the file; the
        row's hint already points at the correct (unmoved) occurrence —
        must NOT be misclassified as drifted just because a second,
        irrelevant occurrence exists elsewhere in the file."""
        root = tmp_path / "corpus2"
        text = "\n".join(
            ["She said the journey took six weeks in total."]
            + [f"filler {i}" for i in range(2, 9)]
            + ["She said the journey took six weeks in total."]
        )
        _write(root / "dup.txt", text)
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                '| Journey took six weeks | dup.txt | 9 | "She said the journey took six weeks in total." | inferred |\n'
            ),
        )
        report = check_provenance_anchors(path, [root])
        row = report["rows"][0]
        assert row["status"] == STATUS_RESOLVED
        assert row["occurrences"] == 2
        assert row["resolved_range"] == [9, 9]

    def test_legacy_row_reports_no_anchor(self, tmp_path: Path, corpus_dir: Path):
        path = _write(
            tmp_path / "provenance.md",
            "| Claim | Source file | Line range | Notes |\n"
            "|-------|-------------|------------|-------|\n"
            '| "The factory burned down" | nita3.txt | 3-5 | verbatim recall |\n',
        )
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["anchor_column_present"] is False
        assert report["counts"][STATUS_NO_ANCHOR] == 1
        assert report["drifted"] is False

    def test_unresolvable_source_file(self, tmp_path: Path, corpus_dir: Path):
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                '| A claim | missing.txt | 1-2 | "some anchor text" | note |\n'
            ),
        )
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["counts"][STATUS_FILE_NOT_FOUND] == 1

    def test_curly_quotes_and_whitespace_normalize(self, tmp_path: Path, corpus_dir: Path):
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                "| factory | nita3.txt | 10 | “The   factory burned   down” | recall |\n"
            ),
        )
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["counts"][STATUS_RESOLVED] == 1


class TestCheckProvenanceAnchorsAggregation:
    """`total_rows` / `anchor_column_present` must describe the WHOLE
    FILE (aggregated across every table), not just the first table
    (issue #934 acceptance criterion)."""

    def test_total_rows_sums_across_all_tables(self, tmp_path: Path, corpus_dir: Path):
        path = _write(
            tmp_path / "provenance.md", _multi_table_doc(2, 3, 4)
        )
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["table_count"] == 3
        assert report["total_rows"] == 9
        assert len(report["rows"]) == 9

    def test_anchor_column_present_true_if_any_table_has_it(
        self, tmp_path: Path, corpus_dir: Path
    ):
        """Table 1 is legacy (no Anchor column); table 2 has one — the
        file-level flag must be True because AT LEAST ONE table has it,
        not False just because the first table lacks it."""
        doc = (
            "# Claim provenance\n\n"
            "| Claim | Source file | Line range | Notes |\n"
            "|-------|-------------|------------|-------|\n"
            '| "legacy claim" | nita3.txt | 1 | pre-anchor row |\n'
            "\n## Chapter 2\n\n"
            + _one_table(2, prefix="t1")
        )
        path = _write(tmp_path / "provenance.md", doc)
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["table_count"] == 2
        assert report["anchor_column_present"] is True
        assert report["total_rows"] == 3

    def test_skipped_tables_surfaced_in_report(self, tmp_path: Path, corpus_dir: Path):
        doc = (
            "# Claim provenance\n\n"
            + _one_table(2, prefix="t0")
            + "\n## Unrelated\n\n"
            "| Foo | Bar |\n"
            "|-----|-----|\n"
            "| 1 | 2 |\n"
        )
        path = _write(tmp_path / "provenance.md", doc)
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["total_rows"] == 2
        assert len(report["skipped_tables"]) == 1
        assert report["skipped_tables"][0]["header"] == ["Foo", "Bar"]


# ---------------------------------------------------------------------------
# repoint_drifted_anchors
# ---------------------------------------------------------------------------


class TestRepointDriftedAnchors:
    def test_repoints_only_drifted_rows(self, tmp_path: Path, corpus_dir: Path):
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                '| "factory" | nita3.txt | 3-5 | "The factory burned down in the summer of 1942" | recall |\n'
                '| Legacy claim | nita3.txt | 1-2 |  | pre-anchor row |\n'
            ),
        )
        original = path.read_text(encoding="utf-8")
        result = repoint_drifted_anchors(path, [corpus_dir])
        assert len(result["repointed"]) == 1
        assert result["repointed"][0]["old_line_range"] == "3-5"
        assert result["repointed"][0]["new_line_range"] == "10"

        new_text = path.read_text(encoding="utf-8")
        assert new_text != original
        # The legacy row (no anchor) must be untouched.
        assert "| Legacy claim | nita3.txt | 1-2 |  | pre-anchor row |" in new_text
        # Claim / Source file / Anchor / Notes preserved for the repointed row.
        assert '"factory"' in new_text
        assert "The factory burned down in the summer of 1942" in new_text
        assert "recall" in new_text
        # Re-checking now reports RESOLVED, not DRIFTED.
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["drifted"] is False

    def test_noop_when_nothing_drifted(self, tmp_path: Path, corpus_dir: Path):
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                '| "factory" | nita3.txt | 10 | "The factory burned down in the summer of 1942" | recall |\n'
            ),
        )
        original = path.read_text(encoding="utf-8")
        result = repoint_drifted_anchors(path, [corpus_dir])
        assert result["repointed"] == []
        assert path.read_text(encoding="utf-8") == original

    def test_noop_on_legacy_table_with_no_anchor_column(
        self, tmp_path: Path, corpus_dir: Path
    ):
        path = _write(
            tmp_path / "provenance.md",
            "| Claim | Source file | Line range | Notes |\n"
            "|-------|-------------|------------|-------|\n"
            '| "The factory burned down" | nita3.txt | 3-5 | verbatim recall |\n',
        )
        original = path.read_text(encoding="utf-8")
        result = repoint_drifted_anchors(path, [corpus_dir])
        assert result["repointed"] == []
        assert path.read_text(encoding="utf-8") == original

    def test_repoints_drifted_rows_across_multiple_tables(
        self, tmp_path: Path, corpus_dir: Path
    ):
        """The sharpest edge from #934: repoint_drifted_anchors must not
        report success having only examined table 1 of several — a
        drifted row in the SECOND table must also get repointed."""
        second_text = "\n".join(
            [f"other filler {i}" for i in range(1, 7)]
            + ["She said the journey took six weeks in total."]
            + ["other filler 8"]
        )
        _write(corpus_dir / "second.txt", second_text)

        doc = (
            "# Claim provenance\n\n"
            + "| Claim | Source file | Line range | Anchor | Notes |\n"
            "|-------|-------------|------------|--------|-------|\n"
            '| "factory" | nita3.txt | 3-5 | "The factory burned down in the summer of 1942" | recall |\n'
            "\n## Chapter 2\n\n"
            "| Claim | Source file | Line range | Anchor | Notes |\n"
            "|-------|-------------|------------|--------|-------|\n"
            '| "journey" | second.txt | 1-2 | "She said the journey took six weeks in total." | recall |\n'
        )
        path = _write(tmp_path / "provenance.md", doc)

        result = repoint_drifted_anchors(path, [corpus_dir])
        assert len(result["repointed"]) == 2
        assert result["table_count"] == 2
        old_ranges = {r["old_line_range"] for r in result["repointed"]}
        new_ranges = {r["new_line_range"] for r in result["repointed"]}
        assert old_ranges == {"3-5", "1-2"}
        assert new_ranges == {"10", "7"}

        # Re-checking now reports no drift in either table.
        report = check_provenance_anchors(path, [corpus_dir])
        assert report["drifted"] is False
        assert report["total_rows"] == 2

    def test_refuses_and_warns_on_nonconforming_table(
        self, tmp_path: Path, corpus_dir: Path
    ):
        """A non-conforming table alongside a conforming, drifted one:
        the conforming table is still repointed, and the non-conforming
        one is explicitly surfaced — never silently dropped."""
        doc = (
            "# Claim provenance\n\n"
            + "| Claim | Source file | Line range | Anchor | Notes |\n"
            "|-------|-------------|------------|--------|-------|\n"
            '| "factory" | nita3.txt | 3-5 | "The factory burned down in the summer of 1942" | recall |\n'
            "\n## Unrelated\n\n"
            "| Foo | Bar |\n"
            "|-----|-----|\n"
            "| 1 | 2 |\n"
        )
        path = _write(tmp_path / "provenance.md", doc)
        result = repoint_drifted_anchors(path, [corpus_dir])
        assert len(result["repointed"]) == 1
        assert len(result["skipped_tables"]) == 1
        assert "WARNING" in result["detail"]
        assert "not" in result["detail"].lower()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_check_cli_round_trips_and_exits_zero(
        self, tmp_path: Path, corpus_dir: Path, capsys
    ):
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                '| "factory" | nita3.txt | 3-5 | "The factory burned down in the summer of 1942" | recall |\n'
            ),
        )
        exit_code = main(["check", str(path), str(corpus_dir)])
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["drifted"] is True

    def test_repoint_cli_round_trips_and_exits_zero(
        self, tmp_path: Path, corpus_dir: Path, capsys
    ):
        path = _write(
            tmp_path / "provenance.md",
            _provenance_table(
                '| "factory" | nita3.txt | 3-5 | "The factory burned down in the summer of 1942" | recall |\n'
            ),
        )
        exit_code = main(["repoint", str(path), str(corpus_dir)])
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["repointed"]) == 1
