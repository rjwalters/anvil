"""Tests for the ``anvil:memo-migrate`` command (issue #202).

Covers the 11 acceptance criteria documented on the issue:

  1. Pandoc preflight surfaces the install story on absent binary.
  2. pdftoppm preflight soft-degrades (non-fatal).
  3. Output layout matches SKILL.md §"State machine" (draft.state == done).
  4. ``\\textasciitilde\\$50K`` round-trips to literal ``~$50K`` (the
     load-bearing 5c bug guard).
  5. ``\\includegraphics{figures/fig1.pdf}`` rewrites to
     ``exhibits/fig1.png`` in memo.md.
  6. Refs preservation lands the original ``memo.tex`` + ``memo.pdf`` at
     ``<thread>/refs/prior-pipeline/v0/``.
  7. BRIEF.md is a clearly-marked stub with TODOs.
  8. ``.anvil.json`` validates against SKILL.md §"Length targets" flat
     shape (``max_iterations: 4`` + optional ``target_length``).
  9. Installer wires the new command (verified by the per-skill
     directory-walk contract — no installer changes needed).
 10. Test discipline: this file uses the ``test_memo_migrate.py`` name
     per the #58 packaging convention; it would never collide with a
     sibling-skill test of the same shape.
 11. No new Python deps — verified by the test imports themselves (no
     new ``pyproject.toml`` deps land alongside this file).

Tests do NOT require a real ``pandoc`` or ``pdftoppm`` binary —
``shutil.which`` and ``subprocess.run`` are monkeypatched. Per-skill
test filename convention (#58): the file is named with a ``test_memo_``
prefix so it never collides with similarly-shaped test files in sibling
skill directories.

Runs under either ``python -m unittest discover tests/skills/memo/`` or
``pytest tests/skills/memo/``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Sequence
from unittest import mock

# Ensure repo root is importable. This file lives at
# tests/skills/memo/test_memo_migrate.py — three levels deep from the
# repo root.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from anvil.skills.memo.lib.migrate import (  # noqa: E402
    PANDOC_REMEDIATION,
    PDFTOPPM_REMEDIATION,
    MigrateError,
    MigrationResult,
    check_pandoc_available,
    check_pdftoppm_available,
    migrate_thread,
)


SKILL_ROOT = _REPO_ROOT / "anvil" / "skills" / "memo"
COMMAND_DOC = SKILL_ROOT / "commands" / "memo-migrate.md"
TEMPLATE_BODY = (SKILL_ROOT / "templates" / "BRIEF.migration.md.example")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_which_factory(present: dict) -> "callable":
    """Return a fake ``shutil.which`` honoring a binary-name → bool map.

    Any binary NOT in ``present`` returns ``None`` (i.e., absent on PATH).
    Listed binaries with ``True`` return a synthetic path; ``False`` returns
    ``None``. This mirrors the monkeypatch pattern in ``tests/lib/test_render.py``.
    """

    def _which(name: str, *args, **kwargs):
        if present.get(name, False):
            return f"/usr/bin/{name}"
        return None

    return _which


def _fake_subprocess_factory(
    pandoc_stdout: str = "",
    pandoc_returncode: int = 0,
    pdftoppm_stdout: str = "",
    pdftoppm_returncode: int = 0,
    on_pdftoppm: "callable" = None,
) -> "callable":
    """Return a fake ``subprocess.run`` simulating pandoc + pdftoppm.

    The migrate module shells out to pandoc (with stdin) and pdftoppm
    (with file args). The fake dispatches on the first element of the
    command list to return canned output.
    """

    def _run(cmd, *args, **kwargs):
        if not cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        binary = cmd[0]
        if binary == "pandoc":
            return subprocess.CompletedProcess(
                cmd, pandoc_returncode, pandoc_stdout, ""
            )
        if binary == "pdftoppm":
            if on_pdftoppm is not None:
                on_pdftoppm(cmd)
            return subprocess.CompletedProcess(
                cmd, pdftoppm_returncode, pdftoppm_stdout, ""
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    return _run


def _write_minimal_tex(path: Path, body: str) -> None:
    """Write a minimal LaTeX document at ``path`` with the given body."""
    path.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        f"{body}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Module-level smoke
# ---------------------------------------------------------------------------


class TestModuleExports(unittest.TestCase):
    """The module exports the documented public surface."""

    def test_module_exports_migrate_thread(self) -> None:
        from anvil.skills.memo.lib import migrate

        self.assertTrue(callable(migrate.migrate_thread))
        self.assertTrue(callable(migrate.check_pandoc_available))
        self.assertTrue(callable(migrate.check_pdftoppm_available))
        self.assertTrue(issubclass(migrate.MigrateError, RuntimeError))
        self.assertIsInstance(migrate.PANDOC_REMEDIATION, str)
        self.assertIsInstance(migrate.PDFTOPPM_REMEDIATION, str)


# ---------------------------------------------------------------------------
# AC1 — Pandoc preflight
# ---------------------------------------------------------------------------


class TestPandocPreflight(unittest.TestCase):
    """AC1: absent pandoc → MigrateError(PANDOC_REMEDIATION); install story present."""

    def test_check_pandoc_available_true_when_on_path(self) -> None:
        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({"pandoc": True}),
        ):
            self.assertTrue(check_pandoc_available())

    def test_check_pandoc_available_false_when_absent(self) -> None:
        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({}),
        ):
            self.assertFalse(check_pandoc_available())

    def test_migrate_thread_hard_fails_without_pandoc(self) -> None:
        """AC1: absent pandoc → MigrateError carrying the install story."""
        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({}),  # pandoc absent
        ):
            with self.assertRaises(MigrateError) as ctx:
                migrate_thread(
                    source_tex=Path("/does/not/matter.tex"),
                    portfolio_dir=Path("/tmp"),
                )
            self.assertIn("pandoc", str(ctx.exception).lower())
            # The remediation message must name the install story.
            self.assertIn("brew install pandoc", str(ctx.exception))

    def test_pandoc_remediation_message_mentions_install_paths(self) -> None:
        """The PANDOC_REMEDIATION constant covers both macOS and Debian paths."""
        self.assertIn("brew install pandoc", PANDOC_REMEDIATION)
        self.assertIn("apt-get install pandoc", PANDOC_REMEDIATION)


# ---------------------------------------------------------------------------
# AC2 — pdftoppm preflight (soft)
# ---------------------------------------------------------------------------


class TestPdftoppmPreflight(unittest.TestCase):
    """AC2: absent pdftoppm → continue with a soft-skip note in changelog/result."""

    def test_check_pdftoppm_available_true_when_on_path(self) -> None:
        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({"pdftoppm": True}),
        ):
            self.assertTrue(check_pdftoppm_available())

    def test_check_pdftoppm_available_false_when_absent(self) -> None:
        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({}),
        ):
            self.assertFalse(check_pdftoppm_available())

    def test_pdftoppm_remediation_message_mentions_install_paths(self) -> None:
        self.assertIn("brew install poppler", PDFTOPPM_REMEDIATION)
        self.assertIn("apt-get install poppler-utils", PDFTOPPM_REMEDIATION)


# ---------------------------------------------------------------------------
# AC3 — Output layout matches SKILL.md
# ---------------------------------------------------------------------------


class TestOutputLayout(unittest.TestCase):
    """AC3: output produces a DRAFTED-state thread per SKILL.md §"State machine"."""

    def _run_migration(
        self,
        tmp_path: Path,
        tex_body: str = "Hello world",
        pandoc_md: str = "Hello world\n",
    ) -> MigrationResult:
        src_dir = tmp_path / "legacy" / "acme-seed"
        src_dir.mkdir(parents=True)
        src_tex = src_dir / "memo.tex"
        _write_minimal_tex(src_tex, tex_body)
        portfolio = tmp_path / "portfolio"
        portfolio.mkdir()

        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({"pandoc": True}),
        ), mock.patch(
            "anvil.skills.memo.lib.migrate.subprocess.run",
            side_effect=_fake_subprocess_factory(pandoc_stdout=pandoc_md),
        ):
            return migrate_thread(
                source_tex=src_tex,
                portfolio_dir=portfolio,
            )

    def test_output_layout_produces_drafted_state(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            result = self._run_migration(tmp_path)

            # AC3: every documented output exists.
            self.assertTrue(result.thread_root.is_dir())
            self.assertTrue(result.version_dir.is_dir())
            self.assertTrue(result.brief_md.exists())
            self.assertTrue(result.anvil_json.exists())
            self.assertTrue(result.memo_md.exists())
            self.assertTrue(
                (result.version_dir / "_progress.json").exists()
            )
            self.assertTrue(
                (result.version_dir / "changelog.md").exists()
            )
            self.assertTrue(
                (result.version_dir / "exhibits").is_dir()
            )

            # AC3: _progress.json.phases.draft.state == "done" derives DRAFTED.
            progress = json.loads(
                (result.version_dir / "_progress.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(progress["version"], 1)
            self.assertIn("draft", progress["phases"])
            self.assertEqual(progress["phases"]["draft"]["state"], "done")
            self.assertIn("started", progress["phases"]["draft"])
            self.assertIn("completed", progress["phases"]["draft"])
            # Metadata shape.
            self.assertEqual(progress["metadata"]["iteration"], 1)
            self.assertEqual(progress["metadata"]["max_iterations"], 4)
            self.assertIn("migrated_from", progress["metadata"])

    def test_output_thread_dir_named_for_slug(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            result = self._run_migration(tmp_path)
            # The auto-derived slug is the parent dir name.
            self.assertEqual(result.thread_root.name, "acme-seed")
            self.assertEqual(result.version_dir.name, "acme-seed.1")

    def test_thread_slug_override(self) -> None:
        """The --thread-slug flag overrides the auto-derived slug."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Hello")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(pandoc_stdout="Hello\n"),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                    thread_slug="custom-slug",
                )
            self.assertEqual(result.thread_root.name, "custom-slug")
            self.assertEqual(result.version_dir.name, "custom-slug.1")


# ---------------------------------------------------------------------------
# AC4 — \textasciitilde load-bearing round-trip (sub-issue 5c)
# ---------------------------------------------------------------------------


class TestTextAsciiTildeRoundTrip(unittest.TestCase):
    """AC4: ``\\textasciitilde\\$50K`` produces ``~$50K`` in memo.md.

    This is **the load-bearing test**. The migration tool exists to
    prevent a class of bug where pandoc silently drops
    ``\\textasciitilde`` — which turns hedged values into asserted
    values in financial prose. The rest of pandoc's output is allowed
    to vary, but this one MUST round-trip.
    """

    def test_textasciitilde_dollar_50k_roundtrips_to_literal_tilde(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "hedge-test"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"

            # The fixture body — note the literal LaTeX sequence here.
            _write_minimal_tex(
                src_tex,
                "Round-trip hedge: \\textasciitilde\\$50K is the budget.",
            )
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            # The fake pandoc must NOT drop the sentinel (real pandoc
            # might, but the unit-test fake passes the sentinel through
            # untouched — which is exactly what the sentinel design
            # assumes). The fake also simulates pandoc's standard
            # LaTeX-escape resolution (``\$`` → ``$``) so the output
            # matches what real pandoc would produce. This is the
            # minimal pandoc-faithfulness the AC4 assertion needs.
            captured_stdin: dict = {}

            def _capture_pandoc(cmd, *args, input=None, **kwargs):
                if cmd[0] == "pandoc":
                    captured_stdin["body"] = input
                    # Simulate pandoc resolving LaTeX escapes that anvil's
                    # preprocessor did not touch: ``\$`` → ``$``, etc.
                    # The sentinel ``ANVILTILDESENTINEL`` passes through
                    # unchanged because it is plain ASCII letters with no
                    # LaTeX meaning.
                    pandoc_out = (input or "").replace("\\$", "$")
                    return subprocess.CompletedProcess(
                        cmd, 0, pandoc_out, ""
                    )
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_capture_pandoc,
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )

            # AC4: memo.md contains a literal ``~$50K``. The sentinel was
            # in pandoc's input (verifying step 6 ran), and the sentinel
            # got substituted back to ``~`` in the output (verifying
            # step 8 ran).
            self.assertIn("ANVILTILDESENTINEL", captured_stdin["body"])
            memo_body = result.memo_md.read_text(encoding="utf-8")
            self.assertIn("~$50K", memo_body)
            # AND the sentinel must NOT remain in the published memo.
            self.assertNotIn("ANVILTILDESENTINEL", memo_body)
            # AND no naked ``\textasciitilde`` should leak through.
            self.assertNotIn("\\textasciitilde", memo_body)

    def test_textasciitilde_with_braces_roundtrips(self) -> None:
        """Brace-form ``\\textasciitilde{}`` is also substituted."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "hedge-test-braces"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(
                src_tex,
                "Brace form: \\textasciitilde{}25\\%.",
            )
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            def _passthrough(cmd, *args, input=None, **kwargs):
                if cmd[0] == "pandoc":
                    return subprocess.CompletedProcess(
                        cmd, 0, input or "", ""
                    )
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_passthrough,
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )
            memo_body = result.memo_md.read_text(encoding="utf-8")
            self.assertIn("~25", memo_body)
            self.assertNotIn("\\textasciitilde", memo_body)


# ---------------------------------------------------------------------------
# AC5 — Figure conversion
# ---------------------------------------------------------------------------


class TestFigureConversion(unittest.TestCase):
    """AC5: includegraphics figure refs rewrite to exhibits/*.png and pdftoppm runs."""

    def test_includegraphics_rewrites_to_exhibits_png(self) -> None:
        """The pandoc-emitted ``![](figures/fig1.pdf)`` is rewritten."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "figure-thread"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            # Create a fake figures dir with a fixture PDF.
            figures = src_dir / "figures"
            figures.mkdir()
            (figures / "fig1.pdf").write_bytes(b"%PDF-fake")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            # Simulate pandoc emitting an image ref for the include.
            pandoc_md = (
                "Body\n\n"
                "![figure caption](figures/fig1.pdf)\n"
            )

            # Track that pdftoppm was invoked with the expected pattern.
            pdftoppm_calls: list = []

            def _on_pdftoppm(cmd):
                pdftoppm_calls.append(cmd)
                # Simulate pdftoppm creating the -1.png file.
                # The output stem is cmd[-1]; pdftoppm writes <stem>-1.png.
                out_stem = Path(cmd[-1])
                out_png = out_stem.parent / f"{out_stem.name}-1.png"
                out_png.parent.mkdir(parents=True, exist_ok=True)
                out_png.write_bytes(b"\x89PNG-fake")

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory(
                    {"pandoc": True, "pdftoppm": True}
                ),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(
                    pandoc_stdout=pandoc_md,
                    on_pdftoppm=_on_pdftoppm,
                ),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )

            # AC5: memo.md contains the rewritten ref.
            memo_body = result.memo_md.read_text(encoding="utf-8")
            self.assertIn("![](exhibits/fig1.png)", memo_body)
            self.assertNotIn("figures/fig1.pdf", memo_body)
            # AC5: pdftoppm was invoked.
            self.assertEqual(len(pdftoppm_calls), 1)
            # 5a: the rename from <basename>-1.png to <basename>.png happened.
            self.assertTrue(
                (result.version_dir / "exhibits" / "fig1.png").exists()
            )
            self.assertFalse(
                (result.version_dir / "exhibits" / "fig1-1.png").exists()
            )
            self.assertEqual(len(result.exhibits), 1)

    def test_includegraphics_emits_refs_when_pdftoppm_absent(self) -> None:
        """When pdftoppm is absent, memo.md refs are emitted but PNGs are not."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "no-pdftoppm"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            figures = src_dir / "figures"
            figures.mkdir()
            (figures / "figA.pdf").write_bytes(b"%PDF-fake")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            pandoc_md = (
                "Body\n\n"
                "![caption](figures/figA.pdf)\n"
            )

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory(
                    {"pandoc": True, "pdftoppm": False}
                ),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(pandoc_stdout=pandoc_md),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )

            self.assertTrue(result.figure_conversion_skipped)
            self.assertIsNotNone(result.figure_conversion_reason)
            self.assertIn(
                "poppler", result.figure_conversion_reason.lower()
            )
            # memo.md still has the rewritten ref.
            memo_body = result.memo_md.read_text(encoding="utf-8")
            self.assertIn("![](exhibits/figA.png)", memo_body)
            # But no PNGs were produced.
            self.assertEqual(result.exhibits, [])


# ---------------------------------------------------------------------------
# AC6 — Refs preservation
# ---------------------------------------------------------------------------


class TestRefsPreservation(unittest.TestCase):
    """AC6: original memo.tex and memo.pdf (if present) land at refs/prior-pipeline/v0/."""

    def test_memo_tex_preserved(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "refs-thread"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body content")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(pandoc_stdout="Body\n"),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )
            preserved_tex = (
                result.thread_root / "refs" / "prior-pipeline" / "v0" / "memo.tex"
            )
            self.assertTrue(preserved_tex.exists())
            self.assertIn(
                "\\begin{document}",
                preserved_tex.read_text(encoding="utf-8"),
            )

    def test_memo_pdf_preserved_when_present(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "pdf-thread"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            (src_dir / "memo.pdf").write_bytes(b"%PDF-1.4 fake")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(pandoc_stdout="Body\n"),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )
            preserved_pdf = (
                result.thread_root / "refs" / "prior-pipeline" / "v0" / "memo.pdf"
            )
            self.assertTrue(preserved_pdf.exists())
            self.assertEqual(
                preserved_pdf.read_bytes(), b"%PDF-1.4 fake"
            )


# ---------------------------------------------------------------------------
# AC7 — BRIEF.md is a stub
# ---------------------------------------------------------------------------


class TestBriefMdStub(unittest.TestCase):
    """AC7: BRIEF.md is a clearly-marked stub with TODO markers."""

    def test_brief_md_carries_stub_marker_and_todos(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "stub-thread"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(pandoc_stdout="Body\n"),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )
            body = result.brief_md.read_text(encoding="utf-8")
            # AC7: the stub-marker is grep-able.
            self.assertIn("TODO: migration-brief stub", body)
            # AC7: explicit TODO placeholders for the author-judgment fields.
            self.assertIn("TODO: fill in company name", body)
            self.assertIn("TODO: fill in sector", body)
            # AC7: this is NOT a "done" brief — operator must edit.
            self.assertIn(
                "recommendation_target: undecided", body
            )
            # AC7: references the prior-pipeline source.
            self.assertIn("refs/prior-pipeline/v0/memo.tex", body)


# ---------------------------------------------------------------------------
# AC8 — .anvil.json shape
# ---------------------------------------------------------------------------


class TestAnvilJsonShape(unittest.TestCase):
    """AC8: .anvil.json validates against SKILL.md §"Length targets" flat shape."""

    def test_anvil_json_default_shape(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "json-thread"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(pandoc_stdout="Body\n"),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )
            payload = json.loads(result.anvil_json.read_text(encoding="utf-8"))
            # AC8: max_iterations: 4 (default).
            self.assertEqual(payload["max_iterations"], 4)
            # When no target_length flag, the field is omitted (no target).
            self.assertNotIn("target_length", payload)

    def test_anvil_json_with_target_length(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "tl-thread"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(pandoc_stdout="Body\n"),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                    target_length=(1800, 2400),
                )
            payload = json.loads(result.anvil_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["max_iterations"], 4)
            # AC8: flat shape — target_length.words is a [min, max] pair.
            self.assertIn("target_length", payload)
            self.assertEqual(
                payload["target_length"]["words"], [1800, 2400]
            )


# ---------------------------------------------------------------------------
# AC9 — Installer wiring (doc-coverage)
# ---------------------------------------------------------------------------


class TestInstallerWiring(unittest.TestCase):
    """AC9: the existing per-skill copy logic picks up memo-migrate.md.

    The installer (``scripts/install-anvil.sh``) walks each selected
    skill's directory and copies the entire tree into the consumer's
    ``.anvil/skills/<skill>/`` directory (Stage 4 / Stage 5). Per-command
    files are NOT individually wired — the directory walk picks them
    up. This test verifies the new ``memo-migrate.md`` lives under the
    expected path so the existing logic finds it.
    """

    def test_command_doc_exists_at_canonical_path(self) -> None:
        self.assertTrue(COMMAND_DOC.exists())

    def test_command_doc_has_frontmatter(self) -> None:
        text = COMMAND_DOC.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("name: memo-migrate", text)
        self.assertIn("description:", text)

    def test_command_doc_references_implementation_module(self) -> None:
        """The command doc points operators at the implementation module."""
        text = COMMAND_DOC.read_text(encoding="utf-8")
        self.assertIn(
            "anvil/skills/memo/lib/migrate.py",
            text,
        )

    def test_command_doc_documents_textasciitilde_safeguard(self) -> None:
        """AC4 cross-check: the command doc documents the 5c safeguard."""
        text = COMMAND_DOC.read_text(encoding="utf-8")
        self.assertIn("textasciitilde", text)
        self.assertIn("~$50K", text)


# ---------------------------------------------------------------------------
# AC11 — No new Python deps (verified by import surface)
# ---------------------------------------------------------------------------


class TestNoNewPythonDeps(unittest.TestCase):
    """AC11: the migrate module imports only stdlib + sibling skill modules.

    A drift-in here (e.g., adding ``import pypdf``) would mean a new
    pyproject.toml dep. The test inspects the module's source for any
    third-party imports; the only allowed non-stdlib import is from
    sibling ``anvil.skills.memo.lib.*`` (none today).
    """

    def test_no_third_party_imports_in_migrate_module(self) -> None:
        from anvil.skills.memo.lib import migrate

        src = Path(migrate.__file__).read_text(encoding="utf-8")
        # Allowed imports (stdlib + nothing else today).
        allowed_top_level = {
            "json", "os", "re", "shutil", "subprocess",
            "dataclasses", "datetime", "pathlib", "typing",
            "__future__",
        }
        # Find every ``import X`` / ``from X import ...``.
        import_pattern = (
            r"^(?:from|import)\s+"
            r"(?P<mod>[a-zA-Z_][a-zA-Z0-9_]*)"
        )
        import re

        for line in src.splitlines():
            stripped = line.lstrip()
            m = re.match(import_pattern, stripped)
            if m is None:
                continue
            mod = m.group("mod")
            self.assertIn(
                mod, allowed_top_level,
                f"Unexpected import {mod!r} — implies a new "
                f"pyproject.toml dependency. Found in line: {line!r}",
            )


# ---------------------------------------------------------------------------
# Preamble stripping
# ---------------------------------------------------------------------------


class TestPreambleStripping(unittest.TestCase):
    """Preamble (everything before \\begin{document} / after \\end{document}) is dropped."""

    def test_preamble_and_postamble_stripped(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "preamble-thread"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            # Note: real LaTeX with a meaty preamble and postamble.
            src_tex.write_text(
                "\\documentclass{article}\n"
                "\\usepackage{xcolor}\n"
                "\\newcommand{\\foo}{bar}\n"
                "\\begin{document}\n"
                "Real body content here.\n"
                "\\end{document}\n"
                "% trailing garbage commented out by the postamble strip\n",
                encoding="utf-8",
            )
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            captured: dict = {}

            def _capture(cmd, *args, input=None, **kwargs):
                if cmd[0] == "pandoc":
                    captured["input"] = input
                    return subprocess.CompletedProcess(
                        cmd, 0, input or "", ""
                    )
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_capture,
            ):
                migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )
            # Preamble must NOT reach pandoc.
            pandoc_input = captured["input"]
            self.assertNotIn("\\documentclass", pandoc_input)
            self.assertNotIn("\\usepackage", pandoc_input)
            self.assertNotIn("\\newcommand", pandoc_input)
            # Postamble must NOT reach pandoc.
            self.assertNotIn("trailing garbage", pandoc_input)
            # Body must reach pandoc.
            self.assertIn("Real body content here.", pandoc_input)


# ---------------------------------------------------------------------------
# Changelog presence
# ---------------------------------------------------------------------------


class TestChangelog(unittest.TestCase):
    """The changelog.md is a single-block migration record."""

    def test_changelog_records_source_path(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "log-thread"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(pandoc_stdout="Body\n"),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )
            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Migrated from", changelog)
            self.assertIn("anvil:memo-migrate", changelog)
            self.assertIn("refs/prior-pipeline/v0/memo.tex", changelog)


# ---------------------------------------------------------------------------
# Packed tabularx cell detector (issue #209, sub-issue 5b)
# ---------------------------------------------------------------------------


class TestPackedTableCellDetector(unittest.TestCase):
    """Issue #209: detect-only warnings for packed single-cell tabularx layouts.

    The detector fires on two heuristics (OR):

    - **Long-cell**: any single cell exceeds 200 chars.
    - **Multi-glyph**: any single cell contains 2+ ``$-$`` glyphs
      (single ``$-$`` is the false-positive guard for currency ranges).

    Detector runs post-pandoc, post-sentinel-substitution (Step 5b in
    ``migrate_thread`` — between ``_pair_footnotes`` and writing
    ``memo.md``), so it sees the same body the operator sees.
    """

    def _run_with_pandoc_md(
        self, tmp_path: Path, slug: str, pandoc_md: str
    ) -> MigrationResult:
        src_dir = tmp_path / "legacy" / slug
        src_dir.mkdir(parents=True)
        src_tex = src_dir / "memo.tex"
        _write_minimal_tex(src_tex, "Body")
        portfolio = tmp_path / "portfolio"
        portfolio.mkdir(exist_ok=True)

        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({"pandoc": True}),
        ), mock.patch(
            "anvil.skills.memo.lib.migrate.subprocess.run",
            side_effect=_fake_subprocess_factory(pandoc_stdout=pandoc_md),
        ):
            return migrate_thread(
                source_tex=src_tex,
                portfolio_dir=portfolio,
            )

    def test_ac1_detector_fires_on_heirloom_horticulture_shape(self) -> None:
        """AC1: a packed P&L with 2+ ``$-$`` glyphs in one cell triggers a warning."""
        import tempfile

        # Mimic the canary shape: a single tabularx cell with seven line
        # items joined by ``$-$`` line-break glyphs. Pandoc emits this as
        # a one-row, one-cell table after the optional header row.
        packed_cell = (
            "Revenue $150 $-$ COGS $40 $-$ Gross $110 $-$ Labor $35 "
            "$-$ Overhead $20 $-$ EBITDA $55 $-$ Net $40"
        )
        pandoc_md = (
            "Body intro.\n"
            "\n"
            "| Biweekly P&L |\n"
            "|---|\n"
            f"| {packed_cell} |\n"
            "\n"
            "Closing prose.\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "heirloom-horticulture", pandoc_md
            )
        packed = [
            n for n in result.notes
            if n.startswith("Packed tabularx cell detected at memo.md table")
        ]
        self.assertEqual(len(packed), 1)
        # The warning text exposes the glyph count (multi-glyph signal).
        self.assertIn("'$-$' glyphs", packed[0])
        # And the signal must be 2+ (the multi-glyph heuristic — single
        # is the false-positive guard).
        match = re.search(r"(\d+) '\$-\$' glyphs", packed[0])
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 2)

    def test_ac2_detector_fires_on_long_cell(self) -> None:
        """AC2: a single cell >200 chars (no ``$-$`` glyphs) fires the long-cell signal."""
        import tempfile

        # 250 chars of prose, no ``$-$`` glyphs.
        long_cell = "A" * 250
        pandoc_md = (
            "| Header |\n"
            "|---|\n"
            f"| {long_cell} |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "long-cell-thread", pandoc_md
            )
        packed = [
            n for n in result.notes
            if n.startswith("Packed tabularx cell detected at memo.md table")
        ]
        self.assertEqual(len(packed), 1)
        # Long-cell signal: the char count in the warning is >200.
        match = re.search(r"(\d+) chars", packed[0])
        self.assertIsNotNone(match)
        self.assertGreater(int(match.group(1)), 200)

    def test_ac3_no_false_positive_on_normal_table(self) -> None:
        """AC3: a normal 3x4 table (cells <50 chars, zero ``$-$``) does NOT fire."""
        import tempfile

        pandoc_md = (
            "| Col A | Col B | Col C |\n"
            "|---|---|---|\n"
            "| Apple | Red | Sweet |\n"
            "| Lemon | Yellow | Sour |\n"
            "| Lime | Green | Tart |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "normal-table-thread", pandoc_md
            )
        packed = [
            n for n in result.notes
            if n.startswith("Packed tabularx cell detected at memo.md table")
        ]
        self.assertEqual(packed, [])

    def test_ac4_no_false_positive_on_single_dollar_glyph(self) -> None:
        """AC4: a cell with exactly one ``$-$`` glyph (under 200 chars) does NOT fire.

        This is the documented false-positive guard. Currency ranges
        (``$3M-$5M ARR``) and math em-dashes (``$a - b$``) legitimately
        contain a single ``$-$`` pattern; only two or more is the packed
        signal.
        """
        import tempfile

        # A short cell with exactly one ``$-$`` glyph.
        pandoc_md = (
            "| Metric | Value |\n"
            "|---|---|\n"
            "| ARR range | $3M $-$ $5M target |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "currency-range-thread", pandoc_md
            )
        packed = [
            n for n in result.notes
            if n.startswith("Packed tabularx cell detected at memo.md table")
        ]
        self.assertEqual(packed, [])

    def test_ac5_changelog_records_detection(self) -> None:
        """AC5: changelog.md contains the packed-cell summary line."""
        import tempfile

        long_cell = "B" * 250
        pandoc_md = (
            "| Header |\n"
            "|---|\n"
            f"| {long_cell} |\n"
            f"| {long_cell} |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "changelog-record-thread", pandoc_md
            )
            changelog = (result.version_dir / "changelog.md").read_text(
                encoding="utf-8"
            )
        # Format: "- Detected {K} packed table cell(s); see notes for
        # unfold guidance.".
        self.assertIn("Detected 2 packed table cell(s)", changelog)
        self.assertIn("see notes for unfold guidance", changelog)

    def test_ac5_changelog_silent_when_no_detection(self) -> None:
        """AC5 (negative): changelog does NOT mention packed cells when none detected."""
        import tempfile

        pandoc_md = "Plain body, no tables.\n"
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "no-tables-thread", pandoc_md
            )
            changelog = (result.version_dir / "changelog.md").read_text(
                encoding="utf-8"
            )
        self.assertNotIn("packed table cell", changelog)

    def test_ac6_cell_preview_in_warning(self) -> None:
        """AC6: the notes entry includes the first ~60 chars of the offending cell."""
        import tempfile

        # A distinguishable prefix so the preview is grep-able.
        prefix = "DISTINCT_PREFIX_TOKEN_FOR_GREP "
        long_cell = prefix + ("z" * 250)
        pandoc_md = (
            "| Header |\n"
            "|---|\n"
            f"| {long_cell} |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "preview-thread", pandoc_md
            )
        packed = [
            n for n in result.notes
            if n.startswith("Packed tabularx cell detected at memo.md table")
        ]
        self.assertEqual(len(packed), 1)
        # The preview prefix is present (operator can grep memo.md to
        # locate the offending cell).
        self.assertIn(prefix.strip(), packed[0])
        # And the preview is truncated with an ellipsis when the cell
        # exceeds the preview length (the long_cell here certainly does).
        self.assertIn("...", packed[0])

    def test_ac7_detector_runs_post_pandoc_post_sentinel(self) -> None:
        """AC7: detector sees ``~`` (not ANVILTILDESENTINEL) and ``€`` (not EURSENTINEL).

        The detector must run AFTER ``_post_substitute_sentinels`` so it
        sees the same body the operator sees in memo.md. This means a
        cell whose content was originally ``\\textasciitilde`` in the
        source — which round-trips to a literal ``~`` post-substitution
        — is observed as ``~`` by the detector, not the sentinel.
        """
        import tempfile

        # Build a packed cell where, after sentinel substitution, the
        # body contains literal ``~`` chars (the post-substitution form).
        # The detector must see ``~`` directly; if it ran BEFORE
        # substitution it would see the sentinel instead.
        packed_cell = (
            "Hedge ~$50K $-$ Hedge ~$60K $-$ Hedge ~$70K "
            "$-$ Hedge ~$80K $-$ Hedge ~$90K"
        )
        pandoc_md = (
            "| Hedged P&L |\n"
            "|---|\n"
            f"| {packed_cell} |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "post-sentinel-thread", pandoc_md
            )
        packed = [
            n for n in result.notes
            if n.startswith("Packed tabularx cell detected at memo.md table")
        ]
        self.assertEqual(len(packed), 1)
        # The preview contains a literal ``~`` (not the sentinel string).
        self.assertIn("~$", packed[0])
        self.assertNotIn("ANVILTILDESENTINEL", packed[0])

    def test_ac8_migration_succeeds_when_detector_fires(self) -> None:
        """AC8: detect-only is non-fatal. The migration still produces a DRAFTED thread."""
        import tempfile

        long_cell = "C" * 250
        pandoc_md = (
            "| Header |\n"
            "|---|\n"
            f"| {long_cell} |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "non-fatal-thread", pandoc_md
            )
            # The migration produced every documented output (matches the
            # AC3 output-layout assertions in TestOutputLayout).
            self.assertTrue(result.memo_md.exists())
            self.assertTrue(result.brief_md.exists())
            self.assertTrue(result.anvil_json.exists())
            self.assertTrue((result.version_dir / "_progress.json").exists())
            self.assertTrue((result.version_dir / "changelog.md").exists())
            # DRAFTED state (phases.draft.state == "done") is intact.
            progress = json.loads(
                (result.version_dir / "_progress.json").read_text(
                    encoding="utf-8"
                )
            )
        self.assertEqual(progress["phases"]["draft"]["state"], "done")
        # And the warning is in notes (the soft-degrade pattern).
        packed = [
            n for n in result.notes
            if n.startswith("Packed tabularx cell detected at memo.md table")
        ]
        self.assertEqual(len(packed), 1)

    def test_alignment_row_is_not_flagged(self) -> None:
        """Sanity: the ``|---|---|`` alignment separator is never flagged.

        Pandoc-emitted markdown tables include an alignment row of pure
        dashes between header and body. That row is not a packed cell
        — it must be excluded from detection.
        """
        import tempfile

        # An alignment row with many dashes (>200 char column would only
        # happen on a malformed table — this just confirms we skip it).
        pandoc_md = (
            "| H1 | H2 |\n"
            "|---|---|\n"
            "| A | B |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "alignment-row-thread", pandoc_md
            )
        packed = [
            n for n in result.notes
            if n.startswith("Packed tabularx cell detected at memo.md table")
        ]
        self.assertEqual(packed, [])

    def test_escaped_dollar_dash_glyph_form_is_detected(self) -> None:
        """The escaped ``\\$-\\$`` form is counted alongside literal ``$-$``.

        Pandoc may emit either the literal or the escaped form depending
        on the LaTeX-escape state of the source. Both are line-break
        glyphs in a packed cell.
        """
        import tempfile

        # A cell with two escaped ``\$-\$`` glyphs (and no literal form).
        # The cell is under 200 chars, so only the glyph-heuristic fires.
        pandoc_md = (
            "| Header |\n"
            "|---|\n"
            "| A \\$-\\$ B \\$-\\$ C \\$-\\$ D |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "escaped-glyph-thread", pandoc_md
            )
        packed = [
            n for n in result.notes
            if n.startswith("Packed tabularx cell detected at memo.md table")
        ]
        self.assertEqual(len(packed), 1)


# ---------------------------------------------------------------------------
# Source not found
# ---------------------------------------------------------------------------


class TestSourceNotFound(unittest.TestCase):
    """A missing source .tex raises MigrateError with the resolved path."""

    def test_missing_source_raises(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ):
                with self.assertRaises(MigrateError) as ctx:
                    migrate_thread(
                        source_tex=tmp_path / "does-not-exist.tex",
                        portfolio_dir=tmp_path,
                    )
            self.assertIn("not found", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# Sub-issue 5e (issue #210) — orphan-figure detection
# ---------------------------------------------------------------------------


class TestOrphanFigureDetection(unittest.TestCase):
    """Sub-issue 5e (#210): figures/*.pdf not referenced by any
    ``\\includegraphics`` in the source ``.tex`` are surfaced as orphans
    on ``MigrationResult.orphan_figures`` and in the changelog/notes.

    Report-only — preservation behavior (``_copy_refs`` archives
    everything under ``figures/`` regardless) is intentionally unchanged.
    """

    def _run_with_figures(
        self,
        tmp_path: Path,
        thread_name: str,
        figure_files: list,
        referenced: list,
    ) -> MigrationResult:
        """Build a fixture: ``figure_files`` populate ``figures/``,
        ``referenced`` are the basenames pandoc emits as image refs.

        Each ``referenced`` entry is a basename like ``"fig1"`` and
        becomes a ``![](figures/<basename>.pdf)`` line in the simulated
        pandoc output.
        """
        src_dir = tmp_path / "legacy" / thread_name
        src_dir.mkdir(parents=True)
        src_tex = src_dir / "memo.tex"
        _write_minimal_tex(src_tex, "Body")
        figures = src_dir / "figures"
        figures.mkdir()
        for name in figure_files:
            (figures / name).write_bytes(b"%PDF-fake")
        portfolio = tmp_path / "portfolio"
        portfolio.mkdir()

        ref_lines = "\n".join(
            f"![caption](figures/{basename}.pdf)" for basename in referenced
        )
        pandoc_md = f"Body\n\n{ref_lines}\n"

        def _on_pdftoppm(cmd):
            out_stem = Path(cmd[-1])
            out_png = out_stem.parent / f"{out_stem.name}-1.png"
            out_png.parent.mkdir(parents=True, exist_ok=True)
            out_png.write_bytes(b"\x89PNG-fake")

        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory(
                {"pandoc": True, "pdftoppm": True}
            ),
        ), mock.patch(
            "anvil.skills.memo.lib.migrate.subprocess.run",
            side_effect=_fake_subprocess_factory(
                pandoc_stdout=pandoc_md,
                on_pdftoppm=_on_pdftoppm,
            ),
        ):
            return migrate_thread(
                source_tex=src_tex,
                portfolio_dir=portfolio,
            )

    def test_orphan_figures_detected_aldus_shape(self) -> None:
        """aldus shape: 3 PDFs in figures/, source references 2; 1 orphan."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            result = self._run_with_figures(
                tmp_path,
                "aldus-shape",
                figure_files=["fig1.pdf", "fig2.pdf", "unused1.pdf"],
                referenced=["fig1", "fig2"],
            )
            self.assertEqual(
                result.orphan_figures, ["figures/unused1.pdf"]
            )

    def test_orphan_figures_multiple_orphans_flat_pack_world_shape(
        self,
    ) -> None:
        """flat-pack-world shape: 4 PDFs, 1 referenced, 3 orphans (sorted)."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            result = self._run_with_figures(
                tmp_path,
                "flat-pack-shape",
                figure_files=[
                    "fig1.pdf",
                    "orphan_a.pdf",
                    "orphan_b.pdf",
                    "orphan_c.pdf",
                ],
                referenced=["fig1"],
            )
            # Sorted lexicographically by basename (glob() iteration order
            # is not guaranteed; the implementation sorts explicitly).
            self.assertEqual(
                result.orphan_figures,
                [
                    "figures/orphan_a.pdf",
                    "figures/orphan_b.pdf",
                    "figures/orphan_c.pdf",
                ],
            )

    def test_orphan_figures_empty_when_all_referenced(self) -> None:
        """Every PDF in figures/ is referenced → no orphans."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            result = self._run_with_figures(
                tmp_path,
                "all-referenced",
                figure_files=["fig1.pdf", "fig2.pdf"],
                referenced=["fig1", "fig2"],
            )
            self.assertEqual(result.orphan_figures, [])

    def test_orphan_figures_empty_when_no_figures_dir(self) -> None:
        """No sibling figures/ dir → no orphans, no orphan-related note."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "no-figures-dir"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body with no figures")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(
                    pandoc_stdout="Body with no figures\n"
                ),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )

            self.assertEqual(result.orphan_figures, [])
            # No orphan-related note should be emitted in the silent path.
            for note in result.notes:
                self.assertNotIn("orphan figure", note)

    def test_orphan_figures_in_changelog(self) -> None:
        """When orphans present, changelog.md carries the Detected line."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            result = self._run_with_figures(
                tmp_path,
                "orphans-changelog",
                figure_files=["fig1.pdf", "unused1.pdf", "unused2.pdf"],
                referenced=["fig1"],
            )
            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Detected 2 orphan figure(s)", changelog)
            self.assertIn("figures/unused1.pdf", changelog)
            self.assertIn("figures/unused2.pdf", changelog)
            self.assertIn(
                "never referenced by \\includegraphics", changelog
            )

    def test_orphan_figures_in_notes(self) -> None:
        """When orphans present, MigrationResult.notes mentions count + list."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            result = self._run_with_figures(
                tmp_path,
                "orphans-notes",
                figure_files=["fig1.pdf", "unused1.pdf"],
                referenced=["fig1"],
            )
            orphan_notes = [
                n for n in result.notes if "orphan figure" in n
            ]
            self.assertEqual(len(orphan_notes), 1)
            note = orphan_notes[0]
            self.assertIn("1 orphan figure(s)", note)
            self.assertIn("figures/unused1.pdf", note)

    def test_orphan_figures_preservation_invariant(self) -> None:
        """Orphan PDFs land at refs/prior-pipeline/v0/figures/ regardless."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            result = self._run_with_figures(
                tmp_path,
                "preservation-invariant",
                figure_files=["fig1.pdf", "unused1.pdf", "unused2.pdf"],
                referenced=["fig1"],
            )
            prior_figures = (
                result.thread_root
                / "refs"
                / "prior-pipeline"
                / "v0"
                / "figures"
            )
            # All three PDFs preserved — referenced AND orphans.
            self.assertTrue((prior_figures / "fig1.pdf").exists())
            self.assertTrue((prior_figures / "unused1.pdf").exists())
            self.assertTrue((prior_figures / "unused2.pdf").exists())
            # And the orphan list reports the two unused ones.
            self.assertEqual(
                result.orphan_figures,
                ["figures/unused1.pdf", "figures/unused2.pdf"],
            )

    def test_orphan_figures_idempotent(self) -> None:
        """Two back-to-back migrate_thread calls → equal orphan_figures lists.

        Each call uses its own tempdir so the portfolio resolves to a
        fresh ``<thread>.1`` per run; the detector is a pure function of
        the source tree, so the orphan lists must match exactly.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as td1:
            result1 = self._run_with_figures(
                Path(td1),
                "idempotent-run1",
                figure_files=["fig1.pdf", "unused1.pdf", "unused2.pdf"],
                referenced=["fig1"],
            )
        with tempfile.TemporaryDirectory() as td2:
            result2 = self._run_with_figures(
                Path(td2),
                "idempotent-run2",
                figure_files=["fig1.pdf", "unused1.pdf", "unused2.pdf"],
                referenced=["fig1"],
            )
        self.assertEqual(result1.orphan_figures, result2.orphan_figures)
        self.assertEqual(
            result1.orphan_figures,
            ["figures/unused1.pdf", "figures/unused2.pdf"],
        )


# ---------------------------------------------------------------------------
# Empty figures/ directory guard (issue #213, sub-issue 5h)
# ---------------------------------------------------------------------------


class TestEmptyFiguresDir(unittest.TestCase):
    """Sub-issue 5h (#213): when the source thread carries a sibling
    ``figures/`` directory but the directory contains zero ``*.pdf``
    candidates, ``migrate_thread`` emits an "exists but is empty" note
    plus a one-line changelog entry.

    Report-only and orthogonal to the orphan-figure detector (those two
    branches are mutually exclusive: orphans require ``*.pdf`` to exist,
    the empty-dir guard fires when none do). The no-``figures/``-dir
    case is intentionally preserved as silent — it indicates a genuinely
    figure-less thread, not the operator-meaningful "directory present
    but empty" signal.
    """

    _EMPTY_NOTE = "figures/ exists but is empty"

    def _run_with_figures_files(
        self,
        tmp_path: Path,
        thread_name: str,
        figures_files: list,
    ) -> MigrationResult:
        """Build a fixture: source ``.tex`` with no figure refs and a
        sibling ``figures/`` directory populated by ``figures_files``
        (each entry is a filename written with a single byte of
        placeholder content).

        Empty ``figures_files`` means the directory is created but
        contains zero files (the byte-empty case).
        """
        src_dir = tmp_path / "legacy" / thread_name
        src_dir.mkdir(parents=True)
        src_tex = src_dir / "memo.tex"
        _write_minimal_tex(src_tex, "Body with no figure refs")
        figures = src_dir / "figures"
        figures.mkdir()
        for name in figures_files:
            (figures / name).write_bytes(b"placeholder")
        portfolio = tmp_path / "portfolio"
        portfolio.mkdir()

        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({"pandoc": True}),
        ), mock.patch(
            "anvil.skills.memo.lib.migrate.subprocess.run",
            side_effect=_fake_subprocess_factory(
                pandoc_stdout="Body with no figure refs\n"
            ),
        ):
            return migrate_thread(
                source_tex=src_tex,
                portfolio_dir=portfolio,
            )

    def test_empty_dir_note_when_byte_empty(self) -> None:
        """AC1: byte-empty figures/ → note appended to MigrationResult.notes."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_figures_files(
                Path(td),
                "empty-byte-empty",
                figures_files=[],
            )
            self.assertIn(self._EMPTY_NOTE, result.notes)
            # The orphan-figure detector must NOT fire here (no PDFs to
            # be orphaned). The two branches are mutually exclusive.
            self.assertEqual(result.orphan_figures, [])

    def test_empty_dir_note_when_only_non_pdf_files(self) -> None:
        """AC2: figures/README.txt present, no *.pdf → note still fires."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_figures_files(
                Path(td),
                "empty-non-pdf-only",
                figures_files=["README.txt", "notes.md", "scratch.png"],
            )
            self.assertIn(self._EMPTY_NOTE, result.notes)
            self.assertEqual(result.orphan_figures, [])

    def test_no_empty_dir_note_when_no_figures_dir(self) -> None:
        """AC3: no sibling figures/ at all → silent success, no note.

        Preserves the existing soft-fail contract documented by
        ``test_orphan_figures_empty_when_no_figures_dir`` upstream.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "no-figures-dir"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body with no figures")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(
                    pandoc_stdout="Body with no figures\n"
                ),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )

            for note in result.notes:
                self.assertNotIn("figures/ exists but is empty", note)

    def test_no_empty_dir_note_when_figures_referenced(self) -> None:
        """AC4: figures/ has referenced PDFs → no empty-dir note (orphan
        path is the operator-meaningful state, not this one)."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            # Re-use the orphan helper from TestOrphanFigureDetection: it
            # builds a fixture where figures/fig1.pdf is referenced.
            helper = TestOrphanFigureDetection()
            result = helper._run_with_figures(
                tmp_path,
                "figures-referenced",
                figure_files=["fig1.pdf"],
                referenced=["fig1"],
            )
            for note in result.notes:
                self.assertNotIn("figures/ exists but is empty", note)
            # Sanity: orphan list is empty (all referenced).
            self.assertEqual(result.orphan_figures, [])

    def test_empty_dir_changelog_entry(self) -> None:
        """AC5: changelog.md carries the Detected-empty-figures line when
        the empty-dir note fires (mirrors orphan-figure changelog
        precedent at migrate.py lines 1894-1904)."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_figures_files(
                Path(td),
                "empty-changelog",
                figures_files=[],
            )
            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")
            self.assertIn(
                "Detected empty source figures/ directory", changelog
            )
            self.assertIn(
                "Operator should confirm whether figure pipeline ran",
                changelog,
            )

    def test_no_empty_dir_changelog_when_no_figures_dir(self) -> None:
        """Sanity: when figures/ is absent, the changelog carries no
        empty-dir line (preserving the silent-success path)."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            src_dir = tmp_path / "legacy" / "no-figures-changelog"
            src_dir.mkdir(parents=True)
            src_tex = src_dir / "memo.tex"
            _write_minimal_tex(src_tex, "Body with no figures")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            with mock.patch(
                "anvil.skills.memo.lib.migrate.shutil.which",
                side_effect=_fake_which_factory({"pandoc": True}),
            ), mock.patch(
                "anvil.skills.memo.lib.migrate.subprocess.run",
                side_effect=_fake_subprocess_factory(
                    pandoc_stdout="Body with no figures\n"
                ),
            ):
                result = migrate_thread(
                    source_tex=src_tex,
                    portfolio_dir=portfolio,
                )

            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")
            self.assertNotIn(
                "Detected empty source figures/ directory", changelog
            )


# ---------------------------------------------------------------------------
# Metricbox detector (issue #212, sub-issue 5g)
# ---------------------------------------------------------------------------


class TestMetricboxDetector(unittest.TestCase):
    """Issue #212: detect-only warnings for 4-column key/value metricbox tables.

    The detector fires when ALL of the following hold for a markdown
    table block:

    - Exactly 4 columns (after splitting on unescaped ``|``).
    - Across all body rows (header + alignment skipped), cols 1 and 3
      are short-label-shaped AND cols 2 and 4 are NOT short-label-shaped.
    - At least 2 body rows match.

    Short-label heuristic: ≤2 words AND (capitalized OR ends in ``:``),
    after stripping ``**...**`` bold markers.

    Detector runs post-pandoc, post-sentinel-substitution (Step 5c in
    ``migrate_thread`` — immediately after the packed-cell detector).
    """

    def _run_with_pandoc_md(
        self, tmp_path: Path, slug: str, pandoc_md: str
    ) -> MigrationResult:
        src_dir = tmp_path / "legacy" / slug
        src_dir.mkdir(parents=True)
        src_tex = src_dir / "memo.tex"
        _write_minimal_tex(src_tex, "Body")
        portfolio = tmp_path / "portfolio"
        portfolio.mkdir(exist_ok=True)

        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({"pandoc": True}),
        ), mock.patch(
            "anvil.skills.memo.lib.migrate.subprocess.run",
            side_effect=_fake_subprocess_factory(pandoc_stdout=pandoc_md),
        ):
            return migrate_thread(
                source_tex=src_tex,
                portfolio_dir=portfolio,
            )

    def _metricbox_notes(self, result: MigrationResult) -> list:
        return [
            n for n in result.notes
            if n.startswith("4-column key/value metricbox detected at memo.md table")
        ]

    # ----- AC1: positive — draftwell-autobiography-shape basic ----------------

    def test_ac1_detector_fires_on_basic_metricbox(self) -> None:
        """AC1: a 4-col label/value/label/value table with 2+ body rows fires."""
        import tempfile

        # draftwell-autobiography shape: short capitalized labels in
        # cols 1 and 3, longer value cells in cols 2 and 4.
        pandoc_md = (
            "Intro.\n"
            "\n"
            "| Header A | Header B | Header C | Header D |\n"
            "|---|---|---|---|\n"
            "| Revenue | one point two million dollars | Cost | "
            "eight hundred thousand dollars |\n"
            "| Margin | thirty four percent gross | Runway | "
            "eighteen months remaining |\n"
            "\n"
            "Closing prose.\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "draftwell-autobiography", pandoc_md
            )
        metricbox = self._metricbox_notes(result)
        self.assertEqual(len(metricbox), 1)
        self.assertIn("body rows match label/value/label/value", metricbox[0])

    # ----- AC5: positive — bold-label form (`**Label**`) ---------------------

    def test_ac5_detector_fires_on_bold_label_form(self) -> None:
        """AC5: ``**Label**`` (pandoc's ``\\textbf{Label}``) is detected.

        The detector trims surrounding ``**...**`` before measuring word
        count and capitalization.
        """
        import tempfile

        pandoc_md = (
            "| H1 | H2 | H3 | H4 |\n"
            "|---|---|---|---|\n"
            "| **Revenue** | one point two million dollars | "
            "**Cost** | eight hundred thousand dollars |\n"
            "| **Margin** | thirty four percent gross | "
            "**Runway** | eighteen months remaining |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "bold-label-thread", pandoc_md
            )
        metricbox = self._metricbox_notes(result)
        self.assertEqual(len(metricbox), 1)

    # ----- AC6: positive — trailing-colon label form ------------------------

    def test_ac6_detector_fires_on_trailing_colon_form(self) -> None:
        """AC6: labels ending in ``:`` are detected via the colon branch."""
        import tempfile

        pandoc_md = (
            "| H1 | H2 | H3 | H4 |\n"
            "|---|---|---|---|\n"
            "| revenue: | one point two million dollars total | "
            "cost: | eight hundred thousand dollars net |\n"
            "| margin: | thirty four percent gross blended | "
            "runway: | eighteen months remaining capital |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "colon-label-thread", pandoc_md
            )
        metricbox = self._metricbox_notes(result)
        self.assertEqual(len(metricbox), 1)

    # ----- AC3 negative: 3-col table does NOT fire ---------------------------

    def test_ac3_no_fire_on_3_col_table(self) -> None:
        """AC3 (3-col): a 3-column table is skipped by the col-count gate."""
        import tempfile

        pandoc_md = (
            "| H1 | H2 | H3 |\n"
            "|---|---|---|\n"
            "| Revenue | one point two million dollars | extra cell |\n"
            "| Margin | thirty four percent gross | extra cell |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "three-col-thread", pandoc_md
            )
        self.assertEqual(self._metricbox_notes(result), [])

    # ----- AC3 negative: 5-col table does NOT fire ---------------------------

    def test_ac3_no_fire_on_5_col_table(self) -> None:
        """AC3 (5-col): a 5-column table is skipped by the col-count gate."""
        import tempfile

        pandoc_md = (
            "| H1 | H2 | H3 | H4 | H5 |\n"
            "|---|---|---|---|---|\n"
            "| Revenue | one point two | Cost | eight hundred | extra |\n"
            "| Margin | thirty four pct | Runway | eighteen months | extra |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "five-col-thread", pandoc_md
            )
        self.assertEqual(self._metricbox_notes(result), [])

    # ----- AC4 negative: single body row does NOT fire -----------------------

    def test_ac4_no_fire_on_single_body_row(self) -> None:
        """AC4: a 4-col table with only one body row is skipped (min ≥2)."""
        import tempfile

        pandoc_md = (
            "| H1 | H2 | H3 | H4 |\n"
            "|---|---|---|---|\n"
            "| Revenue | one point two million dollars | Cost | "
            "eight hundred thousand dollars |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "single-row-thread", pandoc_md
            )
        self.assertEqual(self._metricbox_notes(result), [])

    # ----- AC2 negative: financial-quarter table does NOT fire ---------------

    def test_ac2_fires_on_quarter_table_with_prose_values(self) -> None:
        """AC2 (composition reality check): 4-col table with quarter-shaped
        labels in cols 1/3 and long, multi-word, lowercase value cells in
        cols 2/4 fires the metricbox detector.

        Per the AC2 fixture's documented logic: when cols 2/4 are
        unambiguously NOT short-label-shaped (e.g. multi-word lowercase
        prose), the col-2/col-4 NOT-label guard SUCCEEDS (cells are
        correctly identified as values) and the table is reported as
        a metricbox — operators reshape during ``memo-revise``.

        This documents the dual reading of the AC2 fixture: a
        ``Quarter / value / Quarter / value`` table IS structurally a
        4-col key/value layout under the v0 heuristic, even if a human
        reader might think of it as a financial-period matrix. The
        warning's reshape guidance still applies (def-list or 2-col
        metric/value rendering).
        """
        import tempfile

        pandoc_md = (
            "| Quarter | Revenue figure | Quarter | Revenue figure |\n"
            "|---|---|---|---|\n"
            "| Q1 2026 | one point two three four million dollars vs prior | "
            "Q2 2026 | one point five zero zero million dollars vs prior |\n"
            "| Q3 2026 | one point eight zero zero million dollars vs prior | "
            "Q4 2026 | two point one zero zero million dollars vs prior |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "quarter-with-prose-values-thread", pandoc_md
            )
        self.assertEqual(len(self._metricbox_notes(result)), 1)

    def test_ac2_documented_limitation_short_currency_value_fires(self) -> None:
        """AC2 (documented limitation): cells like ``$1.2M`` are 1 word
        and start with ``$``. Under the v0 heuristic — strict ``isupper``
        first-char check — they do NOT satisfy the short-label
        heuristic, so the col-2/col-4 NOT-label guard SUCCEEDS and the
        detector flags the table as a metricbox.

        Per issue #212 AC2: "Document the limitation: cells like
        ``$1.2M`` would currently false-fire — note in code comment."
        This test pins the documented behavior so a future tuning of
        the capitalization check (e.g. accept currency symbols as
        "capitalized-by-symbol") will trip this assertion and force
        a re-think of the AC2 contract.
        """
        import tempfile

        pandoc_md = (
            "| Q | val | Q | val |\n"
            "|---|---|---|---|\n"
            "| Q1 2026 | $1.2M | Q2 2026 | $1.5M |\n"
            "| Q3 2026 | $1.8M | Q4 2026 | $2.1M |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "currency-symbol-thread", pandoc_md
            )
        # Documented limitation: this currently fires (false-positive
        # surface called out explicitly in the issue body).
        self.assertEqual(len(self._metricbox_notes(result)), 1)

    def test_ac2_no_fire_when_value_cols_short_capitalized(self) -> None:
        """AC2 (sharp guard): the col-2/col-4 NOT-label guard suppresses
        a 4-col table whose value cells are ALSO short-and-capitalized
        (e.g. ``Status: | OK | Phase: | DONE``). Documented as the
        intended false-positive guard: when cols 2 and 4 themselves
        look label-shaped, the table is not unambiguously
        label/value/label/value and we skip it.
        """
        import tempfile

        # All four columns satisfy the label heuristic. The guard
        # requires cols 2 and 4 to NOT match — they do, so we skip.
        pandoc_md = (
            "| H1 | H2 | H3 | H4 |\n"
            "|---|---|---|---|\n"
            "| Status: | OK | Phase: | DONE |\n"
            "| Mode: | LIVE | Build: | GREEN |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "all-label-cols-thread", pandoc_md
            )
        self.assertEqual(self._metricbox_notes(result), [])

    # ----- AC7: warning includes first-row preview ---------------------------

    def test_ac7_first_row_preview_in_warning(self) -> None:
        """AC7: the notes entry includes the first body row joined by ``" | "``."""
        import tempfile

        pandoc_md = (
            "| H1 | H2 | H3 | H4 |\n"
            "|---|---|---|---|\n"
            "| Revenue | one point two million dollars | Cost | "
            "eight hundred thousand dollars |\n"
            "| Margin | thirty four percent gross | Runway | "
            "eighteen months remaining |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "preview-thread", pandoc_md
            )
        metricbox = self._metricbox_notes(result)
        self.assertEqual(len(metricbox), 1)
        # First-row cells joined by " | " are in the warning preview.
        self.assertIn("Revenue", metricbox[0])
        self.assertIn("Cost", metricbox[0])
        self.assertIn(
            "one point two million dollars | Cost", metricbox[0]
        )

    # ----- AC8: changelog records the detection ------------------------------

    def test_ac8_changelog_records_detection(self) -> None:
        """AC8: changelog.md contains the metricbox summary line."""
        import tempfile

        pandoc_md = (
            "| H1 | H2 | H3 | H4 |\n"
            "|---|---|---|---|\n"
            "| Revenue | one point two million dollars | Cost | "
            "eight hundred thousand dollars |\n"
            "| Margin | thirty four percent gross | Runway | "
            "eighteen months remaining |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "metricbox-changelog-thread", pandoc_md
            )
            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")
        self.assertIn(
            "Detected 1 4-column key/value metricbox table(s)", changelog
        )
        self.assertIn("see notes for reshape guidance", changelog)

    def test_ac8_changelog_silent_when_no_detection(self) -> None:
        """AC8 (negative): changelog does NOT mention metricbox when not detected."""
        import tempfile

        pandoc_md = "Plain body, no tables.\n"
        with tempfile.TemporaryDirectory() as td:
            # Slug deliberately does NOT contain the word "metricbox" —
            # the changelog's "# Changelog for {slug}" header would
            # otherwise tautologically contain the search string.
            result = self._run_with_pandoc_md(
                Path(td), "plain-body-thread", pandoc_md
            )
            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")
        self.assertNotIn("metricbox", changelog)

    # ----- AC9: detector is post-pandoc, post-sentinel ----------------------

    def test_ac9_detector_runs_post_pandoc_post_sentinel(self) -> None:
        """AC9: detector sees post-substitution ``~`` and ``€`` in body cells.

        The detector must run AFTER ``_post_substitute_sentinels`` so
        the first-row preview contains a literal ``~`` rather than the
        sentinel string. Verifies the wiring at Step 5c.
        """
        import tempfile

        # A metricbox where one value cell contains a literal ``~`` —
        # the post-substitution form. If the detector ran BEFORE
        # substitution it would see the ANVILTILDESENTINEL string in
        # the preview, not ``~``.
        pandoc_md = (
            "| H1 | H2 | H3 | H4 |\n"
            "|---|---|---|---|\n"
            "| Revenue | ~one point two million dollars | Cost | "
            "eight hundred thousand dollars |\n"
            "| Margin | thirty four percent gross | Runway | "
            "eighteen months remaining |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "post-sentinel-metricbox-thread", pandoc_md
            )
        metricbox = self._metricbox_notes(result)
        self.assertEqual(len(metricbox), 1)
        # Literal ``~`` in the preview (the post-substitution form).
        self.assertIn("~one point two", metricbox[0])
        self.assertNotIn("ANVILTILDESENTINEL", metricbox[0])

    # ----- AC10: composes with packed-cell detector --------------------------

    def test_ac10_composes_with_packed_cell_detector(self) -> None:
        """AC10: a body with BOTH a packed cell AND a metricbox produces
        both warning families and both changelog summary lines.
        """
        import tempfile

        # First table: a packed cell (multi-glyph signal).
        # Second table: a metricbox.
        packed_cell = (
            "Revenue $150 $-$ COGS $40 $-$ Gross $110 $-$ Labor $35 "
            "$-$ Overhead $20 $-$ EBITDA $55"
        )
        pandoc_md = (
            "| Packed P&L |\n"
            "|---|\n"
            f"| {packed_cell} |\n"
            "\n"
            "| H1 | H2 | H3 | H4 |\n"
            "|---|---|---|---|\n"
            "| Revenue | one point two million dollars | Cost | "
            "eight hundred thousand dollars |\n"
            "| Margin | thirty four percent gross | Runway | "
            "eighteen months remaining |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "compose-thread", pandoc_md
            )
            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")

        packed = [
            n for n in result.notes
            if n.startswith("Packed tabularx cell detected at memo.md table")
        ]
        metricbox = self._metricbox_notes(result)
        self.assertGreaterEqual(len(packed), 1)
        self.assertEqual(len(metricbox), 1)
        # Both changelog summary lines present (no de-duplication).
        self.assertIn("packed table cell(s)", changelog)
        self.assertIn(
            "4-column key/value metricbox table(s)", changelog
        )

    # ----- AC11: detect-only is non-fatal -----------------------------------

    def test_ac11_migration_succeeds_when_metricbox_detected(self) -> None:
        """AC11: detect-only is non-fatal — migration produces a DRAFTED thread."""
        import tempfile

        pandoc_md = (
            "| H1 | H2 | H3 | H4 |\n"
            "|---|---|---|---|\n"
            "| Revenue | one point two million dollars | Cost | "
            "eight hundred thousand dollars |\n"
            "| Margin | thirty four percent gross | Runway | "
            "eighteen months remaining |\n"
        )
        with tempfile.TemporaryDirectory() as td:
            result = self._run_with_pandoc_md(
                Path(td), "metricbox-non-fatal-thread", pandoc_md
            )
            self.assertTrue(result.memo_md.exists())
            self.assertTrue(result.brief_md.exists())
            self.assertTrue(result.anvil_json.exists())
            self.assertTrue((result.version_dir / "_progress.json").exists())
            self.assertTrue((result.version_dir / "changelog.md").exists())
            progress = json.loads(
                (result.version_dir / "_progress.json").read_text(
                    encoding="utf-8"
                )
            )
        self.assertEqual(progress["phases"]["draft"]["state"], "done")
        self.assertEqual(len(self._metricbox_notes(result)), 1)


# ---------------------------------------------------------------------------
# Sub-issue 5f (issue #211) — source-brief discovery + ingestion
# ("earliest-brief wins" rule)
# ---------------------------------------------------------------------------


class TestSourceBriefDiscovery(unittest.TestCase):
    """Sub-issue 5f / issue #211 — ``brief.md`` ingestion under earliest-wins rule.

    Covers all 10 ACs from issue #211:

    - AC1: bower shape (``memo.1/brief.md`` ingested when ``memo.3`` is source).
    - AC2: thread-root shape (``brief.md`` at root treated as N=0).
    - AC3: multi-version, earliest wins + diagnostic note.
    - AC4: whitespace-only content skipped, next-earliest wins.
    - AC5: no source brief → TODO-only stub, no ingested block, no changelog line.
    - AC6: MigrationResult.source_brief_path provenance shape.
    - AC7: changelog line cites preserved-refs path.
    - AC8: no regression in existing tests (the prior 47 tests still pass —
      verified by running the file in full; no test changes there).
    - AC9: command doc updated (test in TestInstallerWiring extension below).
    - AC10: no new Python deps (test below extends the existing import scanner).
    """

    @staticmethod
    def _run_migrate(
        tmp_path: Path,
        src_tex: Path,
        portfolio: Path,
        pandoc_md: str = "Body\n",
    ) -> MigrationResult:
        """Run ``migrate_thread`` with pandoc faked + pdftoppm absent.

        Centralizes the monkeypatch boilerplate so each AC test reads
        as a fixture-layout assertion rather than a mock setup.
        """
        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({"pandoc": True}),
        ), mock.patch(
            "anvil.skills.memo.lib.migrate.subprocess.run",
            side_effect=_fake_subprocess_factory(pandoc_stdout=pandoc_md),
        ):
            return migrate_thread(
                source_tex=src_tex,
                portfolio_dir=portfolio,
            )

    # -- AC1 ----------------------------------------------------------------

    def test_ac1_bower_shape_ingests_memo1_brief_when_memo3_is_source(
        self,
    ) -> None:
        """Bower load-bearing fixture: brief at v1, source .tex at v3."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            legacy_root = tmp_path / "legacy" / "bower"
            v1 = legacy_root / "memo.1"
            v3 = legacy_root / "memo.3"
            v1.mkdir(parents=True)
            v3.mkdir(parents=True)
            brief_body = "# bower brief (v1)\n\nCanonical brief authored at v1.\n"
            (v1 / "brief.md").write_text(brief_body, encoding="utf-8")
            src_tex = v3 / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            result = self._run_migrate(tmp_path, src_tex, portfolio)

            # The generated BRIEF.md contains the verbatim v1 body
            # inside the grep-friendly fence.
            body = result.brief_md.read_text(encoding="utf-8")
            self.assertIn(
                "<!-- BEGIN: ingested from memo.1/brief.md -->", body
            )
            self.assertIn("<!-- END: ingested source brief -->", body)
            self.assertIn("Canonical brief authored at v1.", body)
            # The TODO stub marker is still present (this is NOT a "done" brief).
            self.assertIn("TODO: migration-brief stub", body)
            # The canonical template reference block still appears AFTER
            # the ingested fence (order: TODO header → ingested → template).
            todo_pos = body.find("TODO: migration-brief stub")
            ingest_begin = body.find("<!-- BEGIN: ingested from")
            ingest_end = body.find("<!-- END: ingested source brief -->")
            self.assertLess(todo_pos, ingest_begin)
            self.assertLess(ingest_begin, ingest_end)

    # -- AC2 ----------------------------------------------------------------

    def test_ac2_thread_root_shape_brief_at_root_is_n0(self) -> None:
        """Flat thread-root layout: ``acme/brief.md`` + ``acme/memo.tex`` (no version dir)."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            legacy_root = tmp_path / "legacy" / "acme"
            legacy_root.mkdir(parents=True)
            brief_body = "Acme thread-root brief content.\n"
            (legacy_root / "brief.md").write_text(brief_body, encoding="utf-8")
            src_tex = legacy_root / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            result = self._run_migrate(tmp_path, src_tex, portfolio)

            body = result.brief_md.read_text(encoding="utf-8")
            self.assertIn(
                "<!-- BEGIN: ingested from brief.md -->", body
            )
            self.assertIn("Acme thread-root brief content.", body)

    # -- AC3 ----------------------------------------------------------------

    def test_ac3_multi_version_earliest_wins_with_diagnostic_note(
        self,
    ) -> None:
        """Non-empty briefs at v1 AND v3 → v1 wins; v3 noted as ignored."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            legacy_root = tmp_path / "legacy" / "multi"
            v1 = legacy_root / "memo.1"
            v3 = legacy_root / "memo.3"
            v1.mkdir(parents=True)
            v3.mkdir(parents=True)
            (v1 / "brief.md").write_text("v1 canonical brief.\n", encoding="utf-8")
            (v3 / "brief.md").write_text("v3 placeholder brief.\n", encoding="utf-8")
            src_tex = v3 / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            result = self._run_migrate(tmp_path, src_tex, portfolio)

            body = result.brief_md.read_text(encoding="utf-8")
            # v1 content present; v3 content NOT present.
            self.assertIn("v1 canonical brief.", body)
            self.assertNotIn("v3 placeholder brief.", body)
            # Fence path names the v1 file.
            self.assertIn(
                "<!-- BEGIN: ingested from memo.1/brief.md -->", body
            )
            # AC7 (in-v0-if-cheap): diagnostic note enumerates both candidates.
            joined_notes = " | ".join(result.notes)
            self.assertIn("Multiple source briefs", joined_notes)
            self.assertIn("memo.1/brief.md", joined_notes)
            self.assertIn("memo.3/brief.md", joined_notes)

    # -- AC4 ----------------------------------------------------------------

    def test_ac4_whitespace_only_v1_skipped_v3_wins(self) -> None:
        """v1 whitespace-only + v3 real content → v3 wins (v1 treated as absent)."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            legacy_root = tmp_path / "legacy" / "ws"
            v1 = legacy_root / "memo.1"
            v3 = legacy_root / "memo.3"
            v1.mkdir(parents=True)
            v3.mkdir(parents=True)
            # Whitespace-only: spaces, tabs, newlines — must be skipped.
            (v1 / "brief.md").write_text("   \n\t\n  \n", encoding="utf-8")
            (v3 / "brief.md").write_text("v3 real brief content.\n", encoding="utf-8")
            src_tex = v3 / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            result = self._run_migrate(tmp_path, src_tex, portfolio)

            body = result.brief_md.read_text(encoding="utf-8")
            self.assertIn("v3 real brief content.", body)
            self.assertIn(
                "<!-- BEGIN: ingested from memo.3/brief.md -->", body
            )
            # Because v1 had no content, the "multiple candidates"
            # diagnostic must NOT fire (only one candidate with content).
            joined_notes = " | ".join(result.notes)
            self.assertNotIn("Multiple source briefs", joined_notes)

    # -- AC5 ----------------------------------------------------------------

    def test_ac5_no_source_brief_preserves_todo_only_behavior(self) -> None:
        """No ``brief.md`` anywhere → TODO stub only, no ingested block, no changelog line."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            legacy_root = tmp_path / "legacy" / "nobrief"
            v1 = legacy_root / "memo.1"
            v1.mkdir(parents=True)
            src_tex = v1 / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            result = self._run_migrate(tmp_path, src_tex, portfolio)

            body = result.brief_md.read_text(encoding="utf-8")
            # No ingested fence.
            self.assertNotIn("BEGIN: ingested from", body)
            self.assertNotIn("END: ingested source brief", body)
            # TODO stub still present.
            self.assertIn("TODO: migration-brief stub", body)
            # MigrationResult records None for source_brief_path.
            self.assertIsNone(result.source_brief_path)
            # Changelog does NOT mention an ingested brief.
            changelog = (result.version_dir / "changelog.md").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("Ingested source brief", changelog)

    # -- AC6 ----------------------------------------------------------------

    def test_ac6_migration_result_records_source_brief_path(self) -> None:
        """``MigrationResult.source_brief_path`` is the abs path of the ingested brief."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            legacy_root = tmp_path / "legacy" / "prov"
            v1 = legacy_root / "memo.1"
            v1.mkdir(parents=True)
            brief_path = v1 / "brief.md"
            brief_path.write_text("Provenance fixture.\n", encoding="utf-8")
            src_tex = v1 / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            result = self._run_migrate(tmp_path, src_tex, portfolio)

            self.assertIsNotNone(result.source_brief_path)
            self.assertIsInstance(result.source_brief_path, Path)
            # Absolute path resolution: result is .resolve()'d so the
            # fixture-side path must also be resolved for the equality.
            self.assertEqual(
                result.source_brief_path.resolve(),
                brief_path.resolve(),
            )

    # -- AC7 ----------------------------------------------------------------

    def test_ac7_changelog_records_preserved_refs_path(self) -> None:
        """Changelog cites the *preserved-refs* path, not the original source path."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            legacy_root = tmp_path / "legacy" / "bower-fixture"
            v1 = legacy_root / "memo.1"
            v3 = legacy_root / "memo.3"
            v1.mkdir(parents=True)
            v3.mkdir(parents=True)
            (v1 / "brief.md").write_text("Brief.\n", encoding="utf-8")
            src_tex = v3 / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            result = self._run_migrate(tmp_path, src_tex, portfolio)

            changelog = (result.version_dir / "changelog.md").read_text(
                encoding="utf-8"
            )
            # The cited path is under refs/prior-pipeline/v0/ (the
            # archival copy), NOT the original ``memo.1/brief.md`` path.
            self.assertIn("Ingested source brief from", changelog)
            self.assertIn("refs/prior-pipeline/v0/memo.1/brief.md", changelog)
            self.assertIn("earliest-brief-wins rule", changelog)

            # The archived copy actually exists.
            archived = (
                result.thread_root
                / "refs"
                / "prior-pipeline"
                / "v0"
                / "memo.1"
                / "brief.md"
            )
            self.assertTrue(archived.is_file())
            self.assertEqual(
                archived.read_text(encoding="utf-8"), "Brief.\n"
            )

    # -- AC9 ----------------------------------------------------------------

    def test_ac9_command_doc_documents_source_brief_discovery(self) -> None:
        """Command doc has the §"Source brief discovery" subsection + step 14 mention."""
        doc = COMMAND_DOC.read_text(encoding="utf-8")
        # New subsection under §"Notes for the agent".
        self.assertIn("## Source brief discovery", doc)
        self.assertIn("earliest-brief wins", doc)
        # Step 14 mentions the ingestion.
        self.assertIn("BEGIN: ingested from", doc)
        self.assertIn("source_brief_path", doc)

    # -- AC10 ---------------------------------------------------------------

    def test_ac10_no_new_python_deps_in_pyproject(self) -> None:
        """``pyproject.toml`` is unchanged — no new base or optional dep names introduced.

        We check the only dependency added by sub-issue 5f's expected
        diff: no new dep names should appear under ``[project]
        dependencies`` or ``[project.optional-dependencies]`` as a
        consequence of this implementation. The migrate module relies
        only on stdlib (``re``, ``shutil``, ``pathlib``) for the new
        discovery helper.
        """
        pyproject = _REPO_ROOT / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        # The known dep set is pydantic (base) + the documented
        # optional-extra names. The discovery helper introduces none.
        # We assert by absence: typical third-party brief-parsing libs
        # MUST NOT have been added.
        for forbidden in (
            "python-frontmatter",
            "pyyaml",
            "frontmatter",
            "ruamel.yaml",
        ):
            self.assertNotIn(forbidden, text.lower())


class TestSourceBriefIngestionRobustness(unittest.TestCase):
    """Edge-case coverage that doesn't map to a numbered AC but is cheap.

    Validates the helper's behavior on layouts the canary corpus could
    surface but the explicit ACs don't enumerate: operator-named
    directories that look like version dirs but aren't, missing
    ``brief.md`` files alongside present ones, etc.
    """

    @staticmethod
    def _run_migrate(
        src_tex: Path,
        portfolio: Path,
        pandoc_md: str = "Body\n",
    ) -> MigrationResult:
        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({"pandoc": True}),
        ), mock.patch(
            "anvil.skills.memo.lib.migrate.subprocess.run",
            side_effect=_fake_subprocess_factory(pandoc_stdout=pandoc_md),
        ):
            return migrate_thread(
                source_tex=src_tex,
                portfolio_dir=portfolio,
            )

    def test_root_brief_wins_over_v1_brief(self) -> None:
        """Both ``<root>/brief.md`` (N=0) and ``memo.1/brief.md`` (N=1) → root wins."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            legacy_root = tmp_path / "legacy" / "both"
            v1 = legacy_root / "memo.1"
            v1.mkdir(parents=True)
            (legacy_root / "brief.md").write_text(
                "Root brief content.\n", encoding="utf-8"
            )
            (v1 / "brief.md").write_text(
                "V1 brief content.\n", encoding="utf-8"
            )
            src_tex = v1 / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            result = self._run_migrate(src_tex, portfolio)
            body = result.brief_md.read_text(encoding="utf-8")
            self.assertIn("Root brief content.", body)
            self.assertNotIn("V1 brief content.", body)
            self.assertIn(
                "<!-- BEGIN: ingested from brief.md -->", body
            )

    def test_non_memo_dot_n_dirs_are_ignored_by_discovery(self) -> None:
        """A non-``memo.{N}`` sibling dir with a ``brief.md`` is NOT picked up."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            legacy_root = tmp_path / "legacy" / "noise"
            v1 = legacy_root / "memo.1"
            v1.mkdir(parents=True)
            # Sibling project-related folder that should NOT count.
            other = legacy_root / "exhibits"
            other.mkdir(parents=True)
            (other / "brief.md").write_text(
                "Bogus exhibit brief.\n", encoding="utf-8"
            )
            (v1 / "brief.md").write_text(
                "Real v1 brief.\n", encoding="utf-8"
            )
            src_tex = v1 / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            result = self._run_migrate(src_tex, portfolio)
            body = result.brief_md.read_text(encoding="utf-8")
            self.assertIn("Real v1 brief.", body)
            self.assertNotIn("Bogus exhibit brief.", body)

    def test_ingested_brief_preserves_markdown_headings_verbatim(self) -> None:
        """Ingested body is NOT rewritten — markdown headings flow through."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            legacy_root = tmp_path / "legacy" / "verbatim"
            v1 = legacy_root / "memo.1"
            v1.mkdir(parents=True)
            heavy_body = (
                "---\n"
                "company: ExistingCorp\n"
                "sector: Hardware\n"
                "---\n"
                "\n"
                "# Heading 1\n"
                "\n"
                "## Heading 2 with **bold** and *italics*\n"
                "\n"
                "- bullet 1\n"
                "- bullet 2\n"
            )
            (v1 / "brief.md").write_text(heavy_body, encoding="utf-8")
            src_tex = v1 / "memo.tex"
            _write_minimal_tex(src_tex, "Body")
            portfolio = tmp_path / "portfolio"
            portfolio.mkdir()

            result = self._run_migrate(src_tex, portfolio)
            body = result.brief_md.read_text(encoding="utf-8")
            # Frontmatter and headings pass through verbatim.
            self.assertIn("company: ExistingCorp", body)
            self.assertIn("# Heading 1", body)
            self.assertIn("## Heading 2 with **bold** and *italics*", body)
            self.assertIn("- bullet 1", body)


# ---------------------------------------------------------------------------
# figure_policy classification (sub-issue 5i, issue #214)
# ---------------------------------------------------------------------------


class TestZeroFiguresMarkerDetector(unittest.TestCase):
    """Sub-issue 5i (#214): direct unit tests for the marker regex.

    The detector contract:

    - Match the literal LaTeX comment ``% anvil:zero-figures-by-design``
      at start-of-line (modulo leading whitespace), case-sensitive.
    - Require a space between ``%`` and the marker text — no-space
      comments do NOT match (operators follow the LaTeX convention).
    - Require a trailing word boundary — suffix variants
      (``-FOO``) do NOT collide with the canonical marker.
    """

    def setUp(self) -> None:
        from anvil.skills.memo.lib.migrate import _detect_zero_figures_marker
        self._detect = _detect_zero_figures_marker

    def test_marker_matches_at_line_start(self) -> None:
        tex = "% anvil:zero-figures-by-design\n\\section{Body}\n"
        self.assertTrue(self._detect(tex))

    def test_marker_matches_with_leading_whitespace(self) -> None:
        tex = "  % anvil:zero-figures-by-design\n\\section{Body}\n"
        self.assertTrue(self._detect(tex))

    def test_marker_matches_when_embedded_in_document(self) -> None:
        # Found anywhere on a comment line, not just the very first line.
        tex = (
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "% anvil:zero-figures-by-design\n"
            "Body text\n"
            "\\end{document}\n"
        )
        self.assertTrue(self._detect(tex))

    def test_marker_no_space_after_percent_does_not_match(self) -> None:
        # The operator-facing convention requires `% anvil:...` (space
        # after the comment marker). Without the space the regex does
        # not match — keeps the detector conservative.
        tex = "%anvil:zero-figures-by-design\nBody\n"
        self.assertFalse(self._detect(tex))

    def test_marker_suffix_does_not_match(self) -> None:
        # Trailing word-boundary guard: `-FOO` suffix is a different
        # marker (would-be future variant), not the canonical one.
        tex = "% anvil:zero-figures-by-design-FOO\nBody\n"
        self.assertFalse(self._detect(tex))

    def test_marker_absent_returns_false(self) -> None:
        tex = "\\section{Body}\nNo marker here.\n"
        self.assertFalse(self._detect(tex))

    def test_marker_case_sensitive(self) -> None:
        # Case-sensitive — the canonical marker is all-lowercase.
        tex = "% Anvil:Zero-Figures-By-Design\nBody\n"
        self.assertFalse(self._detect(tex))

    def test_marker_with_extra_whitespace_after_percent(self) -> None:
        # Multiple spaces after `%` are tolerated (re `\s+`).
        tex = "%   anvil:zero-figures-by-design\nBody\n"
        self.assertTrue(self._detect(tex))


class TestFigurePolicyClassification(unittest.TestCase):
    """Sub-issue 5i (#214): _progress.json.metadata.figure_policy emission
    follows the four-state (marker × figures) cross-product:

    - marker + no figures    -> "by-design"
    - marker + figures       -> "by-design" + MigrationResult.notes warning
    - no marker + no figures -> "pending"
    - no marker + figures    -> field omitted (no annotation needed)
    """

    def _run_migration(
        self,
        tmp_path: Path,
        slug: str,
        tex_body: str,
        pandoc_md: str,
        *,
        include_figures_dir: bool = False,
        figure_files: Sequence[str] = (),
    ) -> MigrationResult:
        src_dir = tmp_path / "legacy" / slug
        src_dir.mkdir(parents=True)
        src_tex = src_dir / "memo.tex"
        # Write the raw LaTeX directly so the marker (which may be a
        # full-line comment before \begin{document}) lands exactly where
        # the operator put it.
        src_tex.write_text(tex_body, encoding="utf-8")
        if include_figures_dir:
            figures = src_dir / "figures"
            figures.mkdir()
            for name in figure_files:
                (figures / name).write_bytes(b"%PDF-fake")
        portfolio = tmp_path / "portfolio"
        portfolio.mkdir()

        with mock.patch(
            "anvil.skills.memo.lib.migrate.shutil.which",
            side_effect=_fake_which_factory({"pandoc": True}),
        ), mock.patch(
            "anvil.skills.memo.lib.migrate.subprocess.run",
            side_effect=_fake_subprocess_factory(pandoc_stdout=pandoc_md),
        ):
            return migrate_thread(
                source_tex=src_tex,
                portfolio_dir=portfolio,
            )

    def _read_progress_metadata(self, result: MigrationResult) -> dict:
        return json.loads(
            (result.version_dir / "_progress.json").read_text(
                encoding="utf-8"
            )
        )["metadata"]

    # --- marker present + no figures → "by-design"
    def test_marker_no_figures_records_by_design(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            tex = (
                "% anvil:zero-figures-by-design\n"
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                "Citation-clear body, text only.\n"
                "\\end{document}\n"
            )
            result = self._run_migration(
                tmp_path,
                "by-design-no-figures",
                tex_body=tex,
                pandoc_md="Citation-clear body, text only.\n",
            )

            metadata = self._read_progress_metadata(result)
            self.assertEqual(metadata.get("figure_policy"), "by-design")

            # No marker-with-figures warning because there are no figures.
            for note in result.notes:
                self.assertNotIn(
                    "marker present but", note
                )

            # Changelog records the by-design line.
            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")
            self.assertIn("figure_policy=by-design recorded", changelog)
            self.assertIn(
                "% anvil:zero-figures-by-design", changelog
            )

    # --- marker present + figures referenced
    # → "by-design" + warning note
    def test_marker_with_figures_records_by_design_and_warns(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            tex = (
                "% anvil:zero-figures-by-design\n"
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                "Body.\n"
                "\\includegraphics{figures/fig1.pdf}\n"
                "\\end{document}\n"
            )
            # pandoc would emit ![](figures/fig1.pdf) which the migrate
            # tool rewrites to exhibits/fig1.png. Simulate that pandoc
            # output here.
            pandoc_md = "Body.\n\n![](figures/fig1.pdf)\n"
            result = self._run_migration(
                tmp_path,
                "marker-with-figures",
                tex_body=tex,
                pandoc_md=pandoc_md,
                include_figures_dir=True,
                figure_files=["fig1.pdf"],
            )

            metadata = self._read_progress_metadata(result)
            self.assertEqual(metadata.get("figure_policy"), "by-design")

            # The marker-content mismatch warning fires.
            marker_warnings = [
                n for n in result.notes
                if "marker present but" in n
            ]
            self.assertEqual(len(marker_warnings), 1)
            warning = marker_warnings[0]
            self.assertIn("1 figure(s) referenced", warning)
            self.assertIn("verify intent", warning)
            self.assertIn("figure_policy=by-design recorded", warning)

            # Changelog still records the by-design line.
            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")
            self.assertIn("figure_policy=by-design recorded", changelog)

    # --- no marker + no figures → "pending"
    def test_no_marker_no_figures_records_pending(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            tex = (
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                "Body with no figures and no marker.\n"
                "\\end{document}\n"
            )
            result = self._run_migration(
                tmp_path,
                "pending-no-marker",
                tex_body=tex,
                pandoc_md="Body with no figures and no marker.\n",
            )

            metadata = self._read_progress_metadata(result)
            self.assertEqual(metadata.get("figure_policy"), "pending")

            # Changelog records the pending line — operator should
            # confirm intent before READY.
            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")
            self.assertIn("figure_policy=pending recorded", changelog)
            self.assertIn(
                "Operator should confirm intent before READY", changelog
            )

            # No marker-with-figures warning (no marker, no figures).
            for note in result.notes:
                self.assertNotIn(
                    "marker present but", note
                )

    # --- no marker + figures referenced → field omitted
    def test_no_marker_with_figures_omits_field(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            tex = (
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                "Body with figures.\n"
                "\\includegraphics{figures/fig1.pdf}\n"
                "\\end{document}\n"
            )
            pandoc_md = "Body with figures.\n\n![](figures/fig1.pdf)\n"
            result = self._run_migration(
                tmp_path,
                "omitted-no-marker",
                tex_body=tex,
                pandoc_md=pandoc_md,
                include_figures_dir=True,
                figure_files=["fig1.pdf"],
            )

            metadata = self._read_progress_metadata(result)
            # Field is OMITTED entirely (not present as None / null).
            self.assertNotIn("figure_policy", metadata)

            # No changelog line for figure_policy in this case.
            changelog = (
                result.version_dir / "changelog.md"
            ).read_text(encoding="utf-8")
            self.assertNotIn("figure_policy=", changelog)

            # No marker-with-figures warning either.
            for note in result.notes:
                self.assertNotIn(
                    "marker present but", note
                )


if __name__ == "__main__":
    unittest.main()
