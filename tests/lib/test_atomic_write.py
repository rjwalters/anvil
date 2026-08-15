"""Tests for ``anvil.lib.atomic_write`` (issue #1104).

Coverage:

- **atomic_write_bytes / atomic_write_text / atomic_write_json** — the
  destination is written with the exact content, no ``.tmp`` sibling is
  left behind, and re-running overwrites cleanly (idempotent, no
  ``FileExistsError``).
- **atomic_write_json formatting** — ``indent=2`` + trailing newline by
  default (the shared on-disk convention every consolidated call site
  already used), and an ``indent=None`` override for a caller that wants
  compact JSON.
- **atomic_replace** — the bare tmp-to-destination swap for a caller
  whose tmp file was populated by something other than
  ``write_text``/``write_bytes`` (e.g. a subprocess writing directly to
  the tmp path, mirroring ``anvil/skills/report/lib/figure_adapters.py``).
- **No partial-write artifact** — after a successful write, only the
  final destination exists in the directory; nothing named ``*.tmp``
  remains.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib.atomic_write import (
    atomic_replace,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
)


class TestAtomicWriteBytes:
    def test_writes_exact_content(self, tmp_path: Path) -> None:
        target = tmp_path / "out.bin"
        atomic_write_bytes(target, b"\x00\x01\xff")
        assert target.read_bytes() == b"\x00\x01\xff"

    def test_no_tmp_sibling_left_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "out.bin"
        atomic_write_bytes(target, b"data")
        leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []

    def test_overwrite_is_idempotent(self, tmp_path: Path) -> None:
        target = tmp_path / "out.bin"
        atomic_write_bytes(target, b"first")
        atomic_write_bytes(target, b"second")
        assert target.read_bytes() == b"second"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["out.bin"]

    def test_accepts_str_path(self, tmp_path: Path) -> None:
        target = tmp_path / "out.bin"
        atomic_write_bytes(str(target), b"data")
        assert target.read_bytes() == b"data"


class TestAtomicWriteText:
    def test_writes_exact_text(self, tmp_path: Path) -> None:
        target = tmp_path / "out.md"
        atomic_write_text(target, "hello\nworld\n")
        assert target.read_text(encoding="utf-8") == "hello\nworld\n"

    def test_default_encoding_is_utf8(self, tmp_path: Path) -> None:
        target = tmp_path / "out.md"
        atomic_write_text(target, "café")
        assert target.read_bytes() == "café".encode()

    def test_custom_encoding(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        atomic_write_text(target, "hello", encoding="ascii")
        assert target.read_bytes() == b"hello"

    def test_no_tmp_sibling_left_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "out.md"
        atomic_write_text(target, "content")
        leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []


class TestAtomicWriteJson:
    def test_default_indent_and_trailing_newline(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        atomic_write_json(target, {"a": 1, "b": [1, 2]})
        text = target.read_text(encoding="utf-8")
        assert text == json.dumps({"a": 1, "b": [1, 2]}, indent=2) + "\n"
        assert text.endswith("\n")

    def test_round_trips(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        payload = {"version": 1, "phases": {"draft": {"score": 40}}}
        atomic_write_json(target, payload)
        assert json.loads(target.read_text(encoding="utf-8")) == payload

    def test_compact_indent_override(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        atomic_write_json(target, {"a": 1}, indent=None)
        text = target.read_text(encoding="utf-8")
        assert text == json.dumps({"a": 1}, indent=None) + "\n"

    def test_no_tmp_sibling_left_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        atomic_write_json(target, {"x": True})
        leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []


class TestAtomicReplace:
    def test_swaps_tmp_over_destination(self, tmp_path: Path) -> None:
        dest = tmp_path / "final.png"
        dest.write_bytes(b"old")
        tmp = tmp_path / ".final.tmp.png"
        tmp.write_bytes(b"new")
        atomic_replace(tmp, dest)
        assert dest.read_bytes() == b"new"
        assert not tmp.exists()

    def test_creates_destination_when_absent(self, tmp_path: Path) -> None:
        dest = tmp_path / "final.png"
        tmp = tmp_path / ".final.tmp.png"
        tmp.write_bytes(b"content")
        atomic_replace(tmp, dest)
        assert dest.read_bytes() == b"content"

    def test_missing_tmp_raises_oserror(self, tmp_path: Path) -> None:
        dest = tmp_path / "final.png"
        tmp = tmp_path / ".missing.tmp.png"
        with pytest.raises(OSError):
            atomic_replace(tmp, dest)
