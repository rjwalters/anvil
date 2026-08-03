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
