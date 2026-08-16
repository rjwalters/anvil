"""Tests for ``anvil.lib.body_resolution`` (issue #1110).

Coverage:

- **resolve_body_path slug-echo discovery** — ``<slug>.md`` wins over any
  ``fallback_names`` entry when both exist.
- **resolve_body_path fallback chain** — first-match-wins across a
  multi-name ``fallback_names`` tuple (the ``evidence_check.py``
  ``FIXED_BODY_NAMES`` shape), and the default single-name
  ``("main.tex",)`` chain (the ``pending_marker.py`` /
  ``numeric_consistency.py`` shape).
- **resolve_body_path override** — a relative override resolves against
  ``version_dir``, an absolute override is used as-is, and a missing
  override raises naming the override (not the discovery chain).
- **resolve_body_path missing body** — raises ``FileNotFoundError`` listing
  the full discovery chain (slug-echo name + every fallback name), with
  the optional ``caller_name`` prefix applied verbatim.
- **record_body_path** — bare filename when inside ``version_dir``,
  portfolio-relative when outside ``version_dir`` but inside the
  portfolio root, absolute as the final fallback.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.lib.body_resolution import record_body_path, resolve_body_path


def _make_version_dir(tmp_path: Path, slug: str = "acme-seed") -> Path:
    version_dir = tmp_path / slug / f"{slug}.1"
    version_dir.mkdir(parents=True)
    return version_dir


class TestResolveBodyPathDiscovery:
    def test_slug_echo_wins_over_fallback(self, tmp_path: Path) -> None:
        version_dir = _make_version_dir(tmp_path)
        (version_dir / "acme-seed.md").write_text("slug body\n", encoding="utf-8")
        (version_dir / "main.tex").write_text("fallback body\n", encoding="utf-8")
        result = resolve_body_path(version_dir)
        assert result == version_dir / "acme-seed.md"

    def test_default_fallback_is_main_tex(self, tmp_path: Path) -> None:
        version_dir = _make_version_dir(tmp_path)
        (version_dir / "main.tex").write_text("paper body\n", encoding="utf-8")
        result = resolve_body_path(version_dir)
        assert result == version_dir / "main.tex"

    def test_custom_fallback_chain_first_match_wins(self, tmp_path: Path) -> None:
        version_dir = _make_version_dir(tmp_path)
        (version_dir / "deck.md").write_text("deck body\n", encoding="utf-8")
        (version_dir / "report.md").write_text("report body\n", encoding="utf-8")
        result = resolve_body_path(
            version_dir, fallback_names=("report.md", "deck.md")
        )
        # report.md is first in the chain, so it wins even though both exist.
        assert result == version_dir / "report.md"

    def test_custom_fallback_chain_second_entry(self, tmp_path: Path) -> None:
        version_dir = _make_version_dir(tmp_path)
        (version_dir / "deck.md").write_text("deck body\n", encoding="utf-8")
        result = resolve_body_path(
            version_dir, fallback_names=("report.md", "deck.md")
        )
        assert result == version_dir / "deck.md"


class TestResolveBodyPathOverride:
    def test_relative_override_resolves_against_version_dir(
        self, tmp_path: Path
    ) -> None:
        version_dir = _make_version_dir(tmp_path)
        (version_dir / "paper.tex").write_text("body\n", encoding="utf-8")
        result = resolve_body_path(version_dir, body=Path("paper.tex"))
        assert result == version_dir / "paper.tex"

    def test_absolute_override_used_as_is(self, tmp_path: Path) -> None:
        version_dir = _make_version_dir(tmp_path)
        staged = tmp_path / "scratch" / "paper.tex"
        staged.parent.mkdir(parents=True)
        staged.write_text("body\n", encoding="utf-8")
        result = resolve_body_path(version_dir, body=staged)
        assert result == staged

    def test_missing_override_raises_naming_the_override(
        self, tmp_path: Path
    ) -> None:
        version_dir = _make_version_dir(tmp_path)
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_body_path(version_dir, body=Path("does-not-exist.tex"))
        assert "does-not-exist.tex" in str(excinfo.value)

    def test_missing_override_message_carries_caller_prefix(
        self, tmp_path: Path
    ) -> None:
        version_dir = _make_version_dir(tmp_path)
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_body_path(
                version_dir,
                body=Path("does-not-exist.tex"),
                caller_name="evidence_check",
            )
        assert str(excinfo.value).startswith("evidence_check: --body override")


class TestResolveBodyPathMissing:
    def test_raises_when_nothing_found(self, tmp_path: Path) -> None:
        version_dir = _make_version_dir(tmp_path)
        with pytest.raises(FileNotFoundError):
            resolve_body_path(version_dir)

    def test_message_lists_full_default_chain(self, tmp_path: Path) -> None:
        version_dir = _make_version_dir(tmp_path)
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_body_path(version_dir)
        message = str(excinfo.value)
        assert "acme-seed.md" in message
        assert "main.tex" in message

    def test_message_lists_full_custom_chain(self, tmp_path: Path) -> None:
        version_dir = _make_version_dir(tmp_path)
        fallback_names = ("main.tex", "report.md", "deck.md")
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_body_path(version_dir, fallback_names=fallback_names)
        message = str(excinfo.value)
        assert "acme-seed.md" in message
        for name in fallback_names:
            assert name in message

    def test_message_carries_caller_prefix(self, tmp_path: Path) -> None:
        version_dir = _make_version_dir(tmp_path)
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_body_path(version_dir, caller_name="pending_marker")
        assert str(excinfo.value).startswith(
            "pending_marker: no body file found"
        )

    def test_no_caller_name_has_no_prefix(self, tmp_path: Path) -> None:
        version_dir = _make_version_dir(tmp_path)
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_body_path(version_dir)
        assert str(excinfo.value).startswith("no body file found")


class TestRecordBodyPath:
    def test_body_inside_version_dir_records_bare_filename(
        self, tmp_path: Path
    ) -> None:
        version_dir = _make_version_dir(tmp_path)
        body = version_dir / "acme-seed.md"
        body.write_text("x\n", encoding="utf-8")
        assert record_body_path(version_dir, body) == "acme-seed.md"

    def test_body_outside_version_dir_records_portfolio_relative(
        self, tmp_path: Path
    ) -> None:
        version_dir = _make_version_dir(tmp_path, slug="tractatus")
        scratch = tmp_path / "tractatus" / "scratch"
        scratch.mkdir(parents=True)
        staged = scratch / "paper.tex"
        staged.write_text("x\n", encoding="utf-8")
        result = record_body_path(version_dir, staged)
        assert result == "tractatus/scratch/paper.tex"

    def test_body_outside_portfolio_root_records_absolute(
        self, tmp_path: Path
    ) -> None:
        version_dir = _make_version_dir(tmp_path)
        elsewhere = tmp_path.parent / "elsewhere.tex"
        elsewhere.write_text("x\n", encoding="utf-8")
        result = record_body_path(version_dir, elsewhere)
        assert result == str(elsewhere.resolve())
