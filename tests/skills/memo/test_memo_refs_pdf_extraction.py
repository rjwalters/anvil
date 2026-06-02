"""Unit + doc-coverage tests for the optional ``pdftotext`` PDF refs back-check (#167).

The ``anvil:memo`` skill's source-of-truth ``refs/`` convention (PR #162 /
issue #144) handles markdown / text / JSON refs by reading them into drafter
context and back-checking reviewer claims against them. **PDFs were
presence-only** in that v0 because anvil shipped no PDF text extraction.

This file covers the **opt-in** PDF text extraction path added in #167:

  1. ``check_pdftotext_available()`` returns ``True`` / ``False`` based on
     ``shutil.which("pdftotext")`` (monkeypatched — no real binary at test
     time).
  2. ``extract_pdf_text(...)`` raises ``RenderError`` (the skill-local
     mirror, with the ``PDFTOTEXT_REMEDIATION`` message) when the binary
     is absent.
  3. ``extract_pdf_text(...)`` raises ``FileNotFoundError`` for a
     non-existent path.
  4. ``extract_pdf_text(...)`` returns the captured stdout on a successful
     subprocess (monkeypatched ``subprocess.run`` returning a
     ``CompletedProcess`` with ``returncode=0``).
  5. ``extract_pdf_text(...)`` raises ``RenderError`` with captured stderr
     on non-zero exit.
  6. ``extract_pdf_text(...)`` does NOT treat empty extraction (image-based
     / scanned PDF) as an error — empty string is a valid return.
  7. Doc-coverage smoke test that all four memo doc files (SKILL.md,
     memo-draft.md, memo-review.md, refs_pdf.py) reference the
     ``pdftotext`` opt-in capability and the graceful-degradation contract.

Tests do NOT require a real ``pdftotext`` binary at test time —
``shutil.which`` and ``subprocess.run`` are monkeypatched. The test file
therefore runs on the stock CI venv with no system poppler install.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with similarly-shaped test
files in sibling skill directories.

Runs under either ``python -m unittest discover tests/skills/memo/`` or
``pytest tests/skills/memo/``.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

# Ensure repo root is importable. This file lives at
# tests/skills/memo/test_memo_refs_pdf_extraction.py — three levels deep
# from the repo root.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from anvil.skills.memo.lib.refs_pdf import (  # noqa: E402
    PDFTOTEXT_REMEDIATION,
    RenderError,
    check_pdftotext_available,
    extract_pdf_text,
)


SKILL_ROOT = _REPO_ROOT / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
DRAFT_MD = SKILL_ROOT / "commands" / "memo-draft.md"
REVIEW_MD = SKILL_ROOT / "commands" / "memo-review.md"
REFS_PDF_PY = SKILL_ROOT / "lib" / "refs_pdf.py"


# ---------------------------------------------------------------------------
# check_pdftotext_available
# ---------------------------------------------------------------------------


class TestCheckPdftotextAvailable(unittest.TestCase):
    """``check_pdftotext_available`` returns a bool based on PATH presence only."""

    def test_returns_true_when_pdftotext_on_path(self) -> None:
        with mock.patch(
            "anvil.skills.memo.lib.refs_pdf.shutil.which",
            return_value="/usr/local/bin/pdftotext",
        ) as which:
            self.assertTrue(check_pdftotext_available())
            which.assert_called_once_with("pdftotext")

    def test_returns_false_when_pdftotext_absent(self) -> None:
        with mock.patch(
            "anvil.skills.memo.lib.refs_pdf.shutil.which",
            return_value=None,
        ) as which:
            self.assertFalse(check_pdftotext_available())
            which.assert_called_once_with("pdftotext")

    def test_does_not_spawn_subprocess(self) -> None:
        """The preflight must be a pure PATH check — no subprocess spawn.

        Mirrors the same property asserted for the ``check_pdfjam_available``
        preflight: if the check shelled out to ``pdftotext``, this test —
        which stubs only ``shutil.which`` — would have to stub
        ``subprocess`` too. It does not, proving the check stays
        binary-presence-only and is safe to run in CI without poppler
        installed.
        """
        with mock.patch(
            "anvil.skills.memo.lib.refs_pdf.subprocess.run",
            side_effect=AssertionError(
                "preflight must not spawn a subprocess"
            ),
        ):
            with mock.patch(
                "anvil.skills.memo.lib.refs_pdf.shutil.which",
                return_value="/usr/local/bin/pdftotext",
            ):
                self.assertTrue(check_pdftotext_available())


# ---------------------------------------------------------------------------
# extract_pdf_text — error paths
# ---------------------------------------------------------------------------


class TestExtractPdfTextErrorPaths(unittest.TestCase):
    """Error paths: missing binary, missing file, non-zero exit."""

    def test_raises_file_not_found_for_missing_path(self) -> None:
        """A non-existent PDF path raises ``FileNotFoundError``.

        This is the programmer-side error path (the caller should have
        checked existence first). It is intentionally distinct from the
        "binary is absent" graceful-skip path, which is the operator-side
        opt-in story.
        """
        # Use a path under /tmp that is overwhelmingly unlikely to exist.
        missing = Path("/tmp/__anvil_memo_refs_pdf_nonexistent_xyz.pdf")
        # Defensive: make sure the path truly does not exist before asserting.
        self.assertFalse(missing.exists())
        with self.assertRaises(FileNotFoundError) as ctx:
            extract_pdf_text(missing)
        self.assertIn(str(missing), str(ctx.exception))

    def test_raises_render_error_when_binary_absent(self) -> None:
        """``pdftotext`` absent → ``RenderError`` with the remediation."""
        # Create a fake PDF on disk so the file-existence guard passes.
        # We never actually shell out to pdftotext because the binary is
        # monkeypatched-absent.
        with mock.patch(
            "anvil.skills.memo.lib.refs_pdf.shutil.which",
            return_value=None,
        ):
            with mock.patch(
                "anvil.skills.memo.lib.refs_pdf.Path.exists",
                return_value=True,
            ):
                with self.assertRaises(RenderError) as ctx:
                    extract_pdf_text(Path("/tmp/whatever.pdf"))
                self.assertEqual(str(ctx.exception), PDFTOTEXT_REMEDIATION)

    def test_raises_render_error_on_nonzero_exit(self) -> None:
        """Non-zero subprocess exit → ``RenderError`` with captured stderr."""
        fake_completed = subprocess.CompletedProcess(
            args=["pdftotext", "/tmp/whatever.pdf", "-"],
            returncode=1,
            stdout="",
            stderr="Syntax Error: Couldn't find trailer dictionary",
        )
        with mock.patch(
            "anvil.skills.memo.lib.refs_pdf.shutil.which",
            return_value="/usr/local/bin/pdftotext",
        ):
            with mock.patch(
                "anvil.skills.memo.lib.refs_pdf.Path.exists",
                return_value=True,
            ):
                with mock.patch(
                    "anvil.skills.memo.lib.refs_pdf.subprocess.run",
                    return_value=fake_completed,
                ):
                    with self.assertRaises(RenderError) as ctx:
                        extract_pdf_text(Path("/tmp/whatever.pdf"))
                    msg = str(ctx.exception)
                    self.assertIn("exit 1", msg)
                    self.assertIn("Syntax Error", msg)

    def test_raises_render_error_falls_back_to_stdout_when_stderr_empty(
        self,
    ) -> None:
        """When stderr is empty on failure, the message uses stdout instead.

        Mirrors the same shape used by ``render_marp_to_pdf`` in
        ``anvil/lib/render.py``: ``f"{result.stderr.strip() or
        result.stdout.strip()}"`` — covers the case where the failing tool
        writes its error to stdout.
        """
        fake_completed = subprocess.CompletedProcess(
            args=["pdftotext", "/tmp/whatever.pdf", "-"],
            returncode=2,
            stdout="some-stdout-error",
            stderr="",
        )
        with mock.patch(
            "anvil.skills.memo.lib.refs_pdf.shutil.which",
            return_value="/usr/local/bin/pdftotext",
        ):
            with mock.patch(
                "anvil.skills.memo.lib.refs_pdf.Path.exists",
                return_value=True,
            ):
                with mock.patch(
                    "anvil.skills.memo.lib.refs_pdf.subprocess.run",
                    return_value=fake_completed,
                ):
                    with self.assertRaises(RenderError) as ctx:
                        extract_pdf_text(Path("/tmp/whatever.pdf"))
                    self.assertIn("some-stdout-error", str(ctx.exception))


# ---------------------------------------------------------------------------
# extract_pdf_text — happy paths
# ---------------------------------------------------------------------------


class TestExtractPdfTextHappyPaths(unittest.TestCase):
    """Successful extraction returns stdout; empty extraction is OK."""

    def test_returns_stdout_on_success(self) -> None:
        """Returncode 0 → return the captured stdout verbatim."""
        expected_text = (
            "Sphere Semiconductor, Palo Alto CA, 2026–current\n"
            "Staff Scientist, ...\n"
        )
        fake_completed = subprocess.CompletedProcess(
            args=["pdftotext", "/tmp/cv.pdf", "-"],
            returncode=0,
            stdout=expected_text,
            stderr="",
        )
        with mock.patch(
            "anvil.skills.memo.lib.refs_pdf.shutil.which",
            return_value="/usr/local/bin/pdftotext",
        ):
            with mock.patch(
                "anvil.skills.memo.lib.refs_pdf.Path.exists",
                return_value=True,
            ):
                with mock.patch(
                    "anvil.skills.memo.lib.refs_pdf.subprocess.run",
                    return_value=fake_completed,
                ) as run:
                    result = extract_pdf_text(Path("/tmp/cv.pdf"))
                    self.assertEqual(result, expected_text)
                    # Sanity check the subprocess invocation shape.
                    args, kwargs = run.call_args
                    invoked_cmd = args[0]
                    self.assertEqual(invoked_cmd[0], "pdftotext")
                    self.assertEqual(invoked_cmd[-1], "-")
                    self.assertTrue(kwargs.get("capture_output"))
                    self.assertTrue(kwargs.get("text"))

    def test_empty_extraction_is_not_an_error(self) -> None:
        """Image-based / scanned PDFs return empty string — NOT an error.

        Load-bearing for the reviewer-side info-level note: ``pdftotext``
        returns an empty string on a PDF with no extractable text (e.g.,
        image-only / scanned). The helper does NOT treat this as an error;
        the caller decides what to do. The reviewer-side recommendation
        is documented in ``memo-review.md`` step 5: log an info-level note
        and fall back to presence-only handling.
        """
        fake_completed = subprocess.CompletedProcess(
            args=["pdftotext", "/tmp/scanned.pdf", "-"],
            returncode=0,
            stdout="",
            stderr="",
        )
        with mock.patch(
            "anvil.skills.memo.lib.refs_pdf.shutil.which",
            return_value="/usr/local/bin/pdftotext",
        ):
            with mock.patch(
                "anvil.skills.memo.lib.refs_pdf.Path.exists",
                return_value=True,
            ):
                with mock.patch(
                    "anvil.skills.memo.lib.refs_pdf.subprocess.run",
                    return_value=fake_completed,
                ):
                    # Must NOT raise; must return empty string.
                    result = extract_pdf_text(Path("/tmp/scanned.pdf"))
                    self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# PDFTOTEXT_REMEDIATION — actionable message
# ---------------------------------------------------------------------------


class TestRemediationMessage(unittest.TestCase):
    """The remediation string carries an actionable install story."""

    def test_names_the_required_binary(self) -> None:
        self.assertIn("pdftotext", PDFTOTEXT_REMEDIATION)

    def test_names_the_underlying_package(self) -> None:
        # poppler-utils is the canonical package name on Debian/Ubuntu;
        # poppler on Homebrew. Both should be discoverable from the
        # remediation message so an operator on either OS knows what to
        # install.
        self.assertIn("poppler", PDFTOTEXT_REMEDIATION.lower())

    def test_names_install_commands_for_macos_and_debian(self) -> None:
        self.assertIn("brew install poppler", PDFTOTEXT_REMEDIATION)
        self.assertIn("poppler-utils", PDFTOTEXT_REMEDIATION)

    def test_names_graceful_skip_contract(self) -> None:
        """The remediation must remind the operator that the rest of
        memo-draft / memo-review still works without the binary —
        graceful degradation is the load-bearing property."""
        lowered = PDFTOTEXT_REMEDIATION.lower()
        self.assertIn("presence-only", lowered)


# ---------------------------------------------------------------------------
# Doc-coverage smoke tests — the four touched files reference pdftotext
# ---------------------------------------------------------------------------


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestDocCoverage(unittest.TestCase):
    """Grep-the-doc regression guards that the four touched memo doc files
    reference the ``pdftotext`` opt-in capability and the
    graceful-degradation contract.

    Mirrors the doc-coverage smoke-test pattern from
    ``test_memo_refs_back_check_doc.py``. Substring presence only — the
    lifecycle commands themselves are LLM-driven, so behavioural
    assertions belong in consumer-side integration tests.
    """

    def test_skill_md_references_pdftotext(self) -> None:
        body = _read(SKILL_MD)
        self.assertIn("pdftotext", body)

    def test_skill_md_references_refs_pdf_module(self) -> None:
        body = _read(SKILL_MD)
        self.assertIn("refs_pdf", body)

    def test_skill_md_documents_graceful_degradation(self) -> None:
        """When `pdftotext` is absent, PDFs fall back to presence-only.
        The graceful-degradation contract MUST be documented so the
        operator knows the skill still works without poppler."""
        body = _read(SKILL_MD).lower()
        self.assertIn("presence-only", body)
        # SKILL.md should also point at the lint entry the reviewer
        # writes so the consumer knows where to find the install story.
        self.assertIn("refs_pdf_extraction", body)

    def test_memo_draft_references_pdftotext(self) -> None:
        body = _read(DRAFT_MD)
        self.assertIn("pdftotext", body)
        self.assertIn("check_pdftotext_available", body)

    def test_memo_draft_references_extract_pdf_text(self) -> None:
        body = _read(DRAFT_MD)
        self.assertIn("extract_pdf_text", body)

    def test_memo_draft_documents_graceful_fallback_for_pdfs(self) -> None:
        """When pdftotext is absent, the drafter falls back to v0
        presence-only behavior — the load-bearing graceful-degrade."""
        body = _read(DRAFT_MD).lower()
        self.assertIn("presence-only", body)

    def test_memo_review_references_pdftotext(self) -> None:
        body = _read(REVIEW_MD)
        self.assertIn("pdftotext", body)
        self.assertIn("check_pdftotext_available", body)

    def test_memo_review_documents_summary_lint_block(self) -> None:
        """memo-review.md MUST document the
        ``_summary.md.lint.refs_pdf_extraction`` block so the reviewer
        knows the JSON shape."""
        body = _read(REVIEW_MD)
        self.assertIn("refs_pdf_extraction", body)

    def test_memo_review_documents_empty_extraction_handling(self) -> None:
        """Image-only PDFs return empty string; the reviewer logs an
        info-level note and falls back to presence-only — no deduction."""
        body = _read(REVIEW_MD).lower()
        self.assertIn("image-based", body)
        # No deduction either way: the recommendation must be explicit.
        self.assertIn("no deduction", body)

    def test_refs_pdf_module_exports_expected_symbols(self) -> None:
        """The lib module MUST export the three documented symbols so
        consumer code paths importing from it do not break silently."""
        body = _read(REFS_PDF_PY)
        self.assertIn("PDFTOTEXT_REMEDIATION", body)
        self.assertIn("def check_pdftotext_available", body)
        self.assertIn("def extract_pdf_text", body)

    def test_refs_pdf_module_defines_local_render_error(self) -> None:
        """The module MUST define a skill-local ``RenderError`` mirror and
        MUST NOT import it from ``anvil.lib.render`` at runtime.

        Rationale (issue #199): consumer installs land the framework at
        ``.anvil/`` with no top-level ``anvil/`` package on ``sys.path``,
        so a runtime ``from anvil.lib.render import RenderError`` dangles
        on every consumer install. The skill-local mirror preserves the
        documented exception semantics for in-skill callers while keeping
        ``refs_pdf.py`` skill-local-pure (zero ``anvil.*`` runtime imports)
        per the CLAUDE.md "skill-local first, lib promotion later" pattern.

        The substring assertions target ONLY the executable portion of
        the module (i.e., everything after the leading module docstring).
        The docstring is allowed to reference ``anvil.lib.render`` for
        historical context — what must NOT appear is an actual runtime
        import statement.
        """
        body = _read(REFS_PDF_PY)
        # The module defines its own RenderError.
        self.assertIn("class RenderError(RuntimeError)", body)

        # Slice past the leading module docstring so the runtime-import
        # assertions only inspect executable lines. The docstring
        # legitimately discusses ``anvil.lib.render`` in design-note 5.
        first_triple = body.find('"""')
        self.assertEqual(
            first_triple,
            0,
            "refs_pdf.py does not start with a docstring",
        )
        second_triple = body.find('"""', first_triple + 3)
        self.assertGreater(
            second_triple,
            first_triple,
            "refs_pdf.py docstring is unterminated",
        )
        executable = body[second_triple + 3 :]

        # No ``anvil.*`` runtime imports at all in the executable
        # portion — match the skill-local-pure shape of the sibling
        # ``memo_image_refs.py``.
        self.assertNotIn("from anvil.", executable)
        self.assertNotIn("import anvil", executable)

    def test_refs_pdf_module_exports_render_error(self) -> None:
        """``__all__`` must include ``RenderError`` so in-skill callers
        can ``from .refs_pdf import RenderError`` to catch the exception
        symmetrically with how they import the helper functions."""
        from anvil.skills.memo.lib import refs_pdf

        self.assertIn("RenderError", refs_pdf.__all__)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
