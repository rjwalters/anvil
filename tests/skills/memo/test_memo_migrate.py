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
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
