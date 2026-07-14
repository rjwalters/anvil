"""Regression tests: installer scaffolds the starter voice-grounding docs.

Issue #576 (phase A of epic #575): anvil documents the voice-grounding
contract (issue #461; ``anvil/lib/snippets/voice_grounding.md``) but shipped
zero starter grounding documents, so a consumer adopting voice grounding faced
a blank page. This issue ships two de-personalized templates
(``anvil/templates/voice/STYLE_GUIDE.template.md`` and
``VOCABULARY.template.md``) plus an installer scaffold stage (Stage 7.9) that
drops them under ``.anvil/voice/`` as ``.anvil/voice/STYLE_GUIDE.md`` /
``.anvil/voice/VOCABULARY.md`` when a voice-consuming skill (``essay`` or
``memo``) is selected. Issue #617 relocated the scaffold destination from the
consumer root to the ``.anvil/voice/`` hierarchy (root-level docs read as
*code* style guidance and cluttered the repo root); the resolver is
path-agnostic so no library change was required.

The scaffold contract (mirrors the Stage 7.8 starter-theme precedent):

  * Gated on ``essay`` or ``memo`` being among the selected skills.
  * Per-file skip-if-exists checks BOTH the new ``.anvil/voice/`` location and
    the pre-#617 consumer-root location: an existing
    ``.anvil/voice/STYLE_GUIDE.md`` (or a root-level ``STYLE_GUIDE.md`` left by
    a pre-#617 install) is PRESERVED untouched — per file, not all-or-nothing.
  * NEVER overwrites a grounding doc (warn-and-skip); a pre-#617 root doc
    suppresses the new-location scaffold so an upgrade never drops a duplicate.
  * ``--dry-run`` reports the would-scaffold action and writes nothing.
  * Reuses the existing ``voice:`` grammar — the installer prints the YAML
    snippet to paste rather than auto-editing ``BRIEF.md``.

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point a consumer hits. Pattern mirrors
``test_install_theme_scaffold.py``. Distinct filename per the #58 packaging
convention.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

# Post-#617 scaffold destination: the ``.anvil/voice/`` hierarchy under the
# consumer root (relative form matches what the operator declares in BRIEF.md).
VOICE_DST_REL = Path(".anvil") / "voice"

VOICE_SRC = REPO_ROOT / "anvil" / "templates" / "voice"
STYLE_TEMPLATE = VOICE_SRC / "STYLE_GUIDE.template.md"
VOCAB_TEMPLATE = VOICE_SRC / "VOCABULARY.template.md"
# The starter word list (issue #602). Unlike the three docs it ships WITHOUT a
# ``.template.`` infix — it is a real seed list, not a fill-in scaffold — and
# scaffolds to ``VOCABULARY.words.txt`` (sibling of ``VOCABULARY.md``), the
# path ``anvil/lib/vocab_reminder.py::resolve_word_list()`` resolves.
VOCAB_WORDS = VOICE_SRC / "vocab.words.txt"

# Author-identifying tokens from the source docs that MUST NOT survive
# de-personalization. (These are the concrete examples / domains / repo
# commands from the proven rjwalters.info shapes that were generalized away.)
BANNED_TOKENS = (
    "pnpm vocab",
    "intersubjective",
    "undergird",
    "eigenvalue",
    "hamiltonian",
    "decoherence",
    "haecceity",
    "phenomenology",
    "seigniorage",
    "stagflation",
    "zeroknowledge",
    "mempool",
    "goodhart",
    "MARL",
    "equilibrium",
    "Editorial Team and AI Training Group",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the installer with ``args`` and capture text stdout+stderr."""

    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"installer exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Source-tree shape + de-personalization
# ---------------------------------------------------------------------------


def test_voice_templates_ship() -> None:
    """Both ship-now voice templates exist with the ``.template.md`` infix."""

    assert STYLE_TEMPLATE.is_file(), f"missing {STYLE_TEMPLATE}"
    assert VOCAB_TEMPLATE.is_file(), f"missing {VOCAB_TEMPLATE}"
    assert VOCAB_WORDS.is_file(), f"missing starter word list {VOCAB_WORDS}"
    assert (VOICE_SRC / "README.md").is_file(), (
        f"missing voice templates README: {VOICE_SRC / 'README.md'}"
    )


def test_style_guide_preserves_generalizable_craft_rules() -> None:
    """The style guide keeps the craft rules that generalize across authors."""

    text = STYLE_TEMPLATE.read_text(encoding="utf-8")
    # Em-dash discipline (the strongest AI-tell family).
    assert "Em-dashes (any use is suspect)" in text
    assert "Sandwich em-dashes" in text
    # Thesis-statement-chain avoidance.
    assert "Thesis-statement chains" in text
    # Self-flattering-adjective AI-tell.
    assert "Self-flattering adjectives" in text
    # The "X is not just Y, it is Z" anti-trope.
    assert "Not just X, it is Y" in text
    # The anti-tropes checklist table survives.
    assert "Quick Anti-Tropes Checklist" in text
    # All ten sections survive.
    for heading in (
        "## 1. Voice and Tone",
        "## 2. Structure and Flow",
        "## 3. Word Choice",
        "## 4. Sentence Rhythm",
        "## 5. Paragraph Style",
        "## 6. Figurative Language",
        "## 7. Openings and Closings",
        "## 8. Authenticity Checks",
        "## 9. Quick Anti-Tropes Checklist",
        "## 10. Style Philosophy",
    ):
        assert heading in text, f"style guide lost section: {heading}"


def test_vocabulary_preserves_philosophy_and_tests() -> None:
    """The vocabulary doc keeps the reminder-tool philosophy + judgment tests."""

    text = VOCAB_TEMPLATE.read_text(encoding="utf-8")
    assert "reminder tool" in text, "lost the reminder-tool philosophy"
    assert "not an injection tool" in text, "lost the injection-tool contrast"
    assert "Precision over novelty" in text, "lost the precision-over-novelty test"
    assert "Gloss Pattern" in text, "lost the gloss pattern"
    assert "Red Flags" in text, "lost the red-flags list"
    assert "Word Categories" in text, "lost the word-category framing"


def test_templates_are_depersonalized() -> None:
    """No author-identifying tokens survive; marked placeholders are present."""

    for template in (STYLE_TEMPLATE, VOCAB_TEMPLATE):
        text = template.read_text(encoding="utf-8")
        for token in BANNED_TOKENS:
            assert token not in text, (
                f"{template.name} still contains the author-specific token "
                f"{token!r} — de-personalization incomplete"
            )
        # Every removed author example becomes a marked placeholder.
        assert "<!-- replace me" in text, (
            f"{template.name} has no <!-- replace me --> placeholder — "
            "the examples must be marked as fill-in-your-own"
        )


def test_vocabulary_references_optional_vocab_tool_as_additive() -> None:
    """The vocab CLI tool (#579) is referenced as optional, not depended on."""

    text = VOCAB_TEMPLATE.read_text(encoding="utf-8")
    assert "optional" in text.lower(), (
        "VOCABULARY template must frame the reminder tool as optional/additive"
    )


# ---------------------------------------------------------------------------
# Fresh install scaffolds (gated on a voice-consuming skill)
# ---------------------------------------------------------------------------


def test_fresh_install_scaffolds_voice_docs_with_memo(tmp_path: Path) -> None:
    """``--skills=memo`` scaffolds the voice docs under ``.anvil/voice/``."""

    target = tmp_path / "memo-target"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    style = target / VOICE_DST_REL / "STYLE_GUIDE.md"
    vocab = target / VOICE_DST_REL / "VOCABULARY.md"
    words = target / VOICE_DST_REL / "VOCABULARY.words.txt"
    assert style.is_file(), f"did not scaffold {style}; stdout:\n{result.stdout}"
    assert vocab.is_file(), f"did not scaffold {vocab}; stdout:\n{result.stdout}"
    assert words.is_file(), f"did not scaffold {words}; stdout:\n{result.stdout}"
    # Regression guard (#617): the old consumer-root paths must NOT be created.
    assert not (target / "STYLE_GUIDE.md").exists(), (
        "fresh install created a root-level STYLE_GUIDE.md — the scaffold must "
        f"live under .anvil/voice/ post-#617; stdout:\n{result.stdout}"
    )
    assert not (target / "VOCABULARY.md").exists(), (
        "fresh install created a root-level VOCABULARY.md — the scaffold must "
        f"live under .anvil/voice/ post-#617; stdout:\n{result.stdout}"
    )
    assert not (target / "VOCABULARY.words.txt").exists(), (
        "fresh install created a root-level VOCABULARY.words.txt — the scaffold "
        f"must live under .anvil/voice/ post-#617; stdout:\n{result.stdout}"
    )

    # Byte-faithful copy of the shipped templates (the `.template` infix is
    # stripped from the destination filename, content is identical).
    assert style.read_text(encoding="utf-8") == STYLE_TEMPLATE.read_text(
        encoding="utf-8"
    ), "scaffolded STYLE_GUIDE.md differs from the shipped template"
    assert vocab.read_text(encoding="utf-8") == VOCAB_TEMPLATE.read_text(
        encoding="utf-8"
    ), "scaffolded VOCABULARY.md differs from the shipped template"
    # The word list scaffolds byte-identical to the shipped starter (the source
    # ships WITHOUT a `.template.` infix — the `vocab.words.txt` stem is renamed
    # to the sibling-resolved `VOCABULARY.words.txt` on copy).
    assert words.read_text(encoding="utf-8") == VOCAB_WORDS.read_text(
        encoding="utf-8"
    ), "scaffolded VOCABULARY.words.txt differs from the shipped starter list"


def test_fresh_install_scaffolds_voice_docs_with_essay(tmp_path: Path) -> None:
    """``--skills=essay`` (the heavy voice consumer) also scaffolds the docs."""

    target = tmp_path / "essay-target"
    target.mkdir()

    result = _run("--skills=essay", str(target))
    _assert_ok(result)

    assert (target / VOICE_DST_REL / "STYLE_GUIDE.md").is_file(), (
        f"essay install did not scaffold .anvil/voice/STYLE_GUIDE.md; "
        f"stdout:\n{result.stdout}"
    )
    assert (target / VOICE_DST_REL / "VOCABULARY.md").is_file(), (
        f"essay install did not scaffold .anvil/voice/VOCABULARY.md; "
        f"stdout:\n{result.stdout}"
    )
    assert (target / VOICE_DST_REL / "VOCABULARY.words.txt").is_file(), (
        f"essay install did not scaffold .anvil/voice/VOCABULARY.words.txt; "
        f"stdout:\n{result.stdout}"
    )


def test_install_without_voice_skill_does_not_scaffold(tmp_path: Path) -> None:
    """``--skills=paper`` (no voice consumer) scaffolds no grounding docs."""

    target = tmp_path / "no-voice-target"
    target.mkdir()

    result = _run("--skills=paper", str(target))
    _assert_ok(result)

    assert not (target / VOICE_DST_REL / "STYLE_GUIDE.md").exists(), (
        "scaffolded STYLE_GUIDE.md even though no voice-consuming skill was "
        f"selected; stdout:\n{result.stdout}"
    )
    assert not (target / VOICE_DST_REL / "VOCABULARY.md").exists(), (
        "scaffolded VOCABULARY.md even though no voice-consuming skill was "
        f"selected; stdout:\n{result.stdout}"
    )
    assert not (target / VOICE_DST_REL / "VOCABULARY.words.txt").exists(), (
        "scaffolded VOCABULARY.words.txt even though no voice-consuming skill "
        f"was selected; stdout:\n{result.stdout}"
    )
    assert "skipping voice-grounding scaffold" in result.stdout, (
        f"expected the no-voice-skill skip note; got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Idempotency + per-file skip-if-exists (never clobber)
# ---------------------------------------------------------------------------


def test_reinstall_is_idempotent_no_duplicate_no_error(tmp_path: Path) -> None:
    """Running the installer twice is a no-op on the grounding docs."""

    target = tmp_path / "idempotent-target"
    target.mkdir()

    first = _run("--skills=memo", str(target))
    _assert_ok(first)
    style = target / VOICE_DST_REL / "STYLE_GUIDE.md"
    words = target / VOICE_DST_REL / "VOCABULARY.words.txt"
    first_content = style.read_text(encoding="utf-8")
    first_words = words.read_text(encoding="utf-8")

    second = _run("--skills=memo", str(target))
    _assert_ok(second)
    assert style.read_text(encoding="utf-8") == first_content, (
        "second install changed STYLE_GUIDE.md"
    )
    assert words.read_text(encoding="utf-8") == first_words, (
        "second install changed VOCABULARY.words.txt"
    )
    assert "preserving" in second.stdout, (
        f"expected the skip-if-exists 'preserving' note on re-install; "
        f"got:\n{second.stdout}"
    )


def test_existing_grounding_doc_is_never_clobbered(tmp_path: Path) -> None:
    """A pre-existing .anvil/voice/STYLE_GUIDE.md is preserved verbatim."""

    target = tmp_path / "clobber-target"
    (target / VOICE_DST_REL).mkdir(parents=True)

    sentinel = "# My hand-authored style guide\n\nDo not touch this.\n"
    (target / VOICE_DST_REL / "STYLE_GUIDE.md").write_text(sentinel, encoding="utf-8")
    words_sentinel = "my-own-precision-word\nanother-one\n"
    (target / VOICE_DST_REL / "VOCABULARY.words.txt").write_text(
        words_sentinel, encoding="utf-8"
    )

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    assert (
        target / VOICE_DST_REL / "STYLE_GUIDE.md"
    ).read_text(encoding="utf-8") == sentinel, (
        "installer clobbered a pre-existing hand-authored STYLE_GUIDE.md"
    )
    assert (
        target / VOICE_DST_REL / "VOCABULARY.words.txt"
    ).read_text(encoding="utf-8") == words_sentinel, (
        "installer clobbered a pre-existing hand-authored VOCABULARY.words.txt"
    )


def test_skip_is_per_file_not_all_or_nothing(tmp_path: Path) -> None:
    """A custom STYLE_GUIDE.md does not block VOCABULARY.md from scaffolding."""

    target = tmp_path / "per-file-target"
    (target / VOICE_DST_REL).mkdir(parents=True)

    sentinel = "# custom style guide\n"
    (target / VOICE_DST_REL / "STYLE_GUIDE.md").write_text(sentinel, encoding="utf-8")
    # A custom word list must likewise not block the docs from scaffolding.
    words_sentinel = "custom-word\n"
    (target / VOICE_DST_REL / "VOCABULARY.words.txt").write_text(
        words_sentinel, encoding="utf-8"
    )

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    # Custom STYLE_GUIDE.md preserved...
    assert (
        target / VOICE_DST_REL / "STYLE_GUIDE.md"
    ).read_text(encoding="utf-8") == sentinel, "custom STYLE_GUIDE.md was overwritten"
    # ...custom VOCABULARY.words.txt preserved...
    assert (
        target / VOICE_DST_REL / "VOCABULARY.words.txt"
    ).read_text(encoding="utf-8") == words_sentinel, (
        "custom VOCABULARY.words.txt was overwritten"
    )
    # ...and VOCABULARY.md STILL scaffolded (per-file, not all-or-nothing).
    assert (target / VOICE_DST_REL / "VOCABULARY.md").is_file(), (
        "VOCABULARY.md was not scaffolded — the skip must be per-file, not "
        f"all-or-nothing; stdout:\n{result.stdout}"
    )
    assert (target / VOICE_DST_REL / "VOCABULARY.md").read_text(
        encoding="utf-8"
    ) == VOCAB_TEMPLATE.read_text(encoding="utf-8"), (
        "scaffolded VOCABULARY.md differs from the shipped template"
    )


# ---------------------------------------------------------------------------
# Migration guard (#617): a pre-#617 root doc suppresses the new scaffold
# ---------------------------------------------------------------------------


def test_pre617_root_doc_suppresses_new_scaffold(tmp_path: Path) -> None:
    """A root-level STYLE_GUIDE.md (pre-#617 install, possibly user-edited) is
    preserved at root and suppresses the new ``.anvil/voice/`` scaffold so an
    upgrade never drops a confusing duplicate."""

    target = tmp_path / "migration-target"
    target.mkdir()

    sentinel = "# pre-#617 hand-authored style guide\n\nKeep me at root.\n"
    (target / "STYLE_GUIDE.md").write_text(sentinel, encoding="utf-8")

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    # The old root doc is preserved verbatim.
    assert (target / "STYLE_GUIDE.md").read_text(encoding="utf-8") == sentinel, (
        "installer clobbered a pre-#617 root-level STYLE_GUIDE.md"
    )
    # ...and the new-location scaffold is SUPPRESSED (no duplicate).
    assert not (target / VOICE_DST_REL / "STYLE_GUIDE.md").exists(), (
        "installer scaffolded a duplicate .anvil/voice/STYLE_GUIDE.md beside a "
        f"pre-#617 root doc; stdout:\n{result.stdout}"
    )
    # The preservation note explains why the new scaffold was skipped.
    assert "pre-#617" in result.stdout, (
        f"expected the pre-#617 migration preservation note; got:\n{result.stdout}"
    )
    # Per-file: the OTHER docs still scaffold to the new location.
    assert (target / VOICE_DST_REL / "VOCABULARY.md").is_file(), (
        "VOCABULARY.md was not scaffolded to .anvil/voice/ — the migration "
        f"guard must be per-file; stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# --dry-run honesty (issue #81)
# ---------------------------------------------------------------------------


def test_dry_run_reports_and_writes_nothing(tmp_path: Path) -> None:
    """``--dry-run`` reports the would-scaffold action and writes nothing."""

    target = tmp_path / "dry-run-target"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=memo", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    assert (
        "[dry-run] scaffold voice-grounding doc at .anvil/voice/STYLE_GUIDE.md"
        in result.stdout
    ), (
        "expected the '[dry-run] scaffold voice-grounding doc at "
        f".anvil/voice/STYLE_GUIDE.md ...' action line; got:\n{result.stdout}"
    )
    assert (
        "[dry-run] scaffold voice-grounding doc at .anvil/voice/VOCABULARY.words.txt"
        in result.stdout
    ), (
        "expected the '[dry-run] scaffold voice-grounding doc at "
        f".anvil/voice/VOCABULARY.words.txt ...' action line; got:\n{result.stdout}"
    )
    assert not (target / VOICE_DST_REL / "STYLE_GUIDE.md").exists(), (
        "--dry-run wrote STYLE_GUIDE.md to the target"
    )
    assert not (target / VOICE_DST_REL / "VOCABULARY.md").exists(), (
        "--dry-run wrote VOCABULARY.md to the target"
    )
    assert not (target / VOICE_DST_REL / "VOCABULARY.words.txt").exists(), (
        "--dry-run wrote VOCABULARY.words.txt to the target"
    )
    # The post-action confirmation must not fire under --dry-run.
    assert "ok: .anvil/voice/STYLE_GUIDE.md scaffolded" not in result.stdout, (
        f"--dry-run emitted the lying 'ok: ... scaffolded' confirmation; "
        f"got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Stage 11 voice-block hint (reuses the existing grammar; no BRIEF auto-edit)
# ---------------------------------------------------------------------------


def test_summary_prints_voice_block_snippet(tmp_path: Path) -> None:
    """Stage 11 prints the exact ``voice:`` YAML to paste into BRIEF.md."""

    target = tmp_path / "hint-target"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)
    stdout = result.stdout

    # The reused grammar's keys must appear so the operator can wire it, now
    # pointing at the .anvil/voice/ destination (issue #617).
    assert "voice:" in stdout
    assert "style_guide: .anvil/voice/STYLE_GUIDE.md" in stdout, (
        f"Stage 11 hint missing the style_guide wiring; got:\n{stdout}"
    )
    assert "vocabulary: .anvil/voice/VOCABULARY.md" in stdout, (
        f"Stage 11 hint missing the vocabulary wiring; got:\n{stdout}"
    )

    # The sibling word-list convention (issue #602) must be documented so a
    # consumer migrating an existing word list knows where it resolves.
    assert "VOCABULARY.words.txt" in stdout, (
        f"Stage 11 hint missing the VOCABULARY.words.txt sibling convention; "
        f"got:\n{stdout}"
    )
    assert "anvil.lib.vocab_reminder" in stdout, (
        f"Stage 11 hint missing the vocab_reminder resolution note; got:\n{stdout}"
    )

    # The installer must NOT have written a BRIEF.md (it prints, never edits).
    assert not (target / "BRIEF.md").exists(), (
        "installer auto-created/edited a BRIEF.md — it must only print the "
        "voice: snippet to paste, never write the BRIEF"
    )


def test_no_voice_hint_when_no_voice_skill(tmp_path: Path) -> None:
    """No voice-block hint when no voice-consuming skill is selected."""

    target = tmp_path / "no-hint-target"
    target.mkdir()

    result = _run("--skills=paper", str(target))
    _assert_ok(result)

    assert "style_guide: .anvil/voice/STYLE_GUIDE.md" not in result.stdout, (
        f"voice hint printed even though no voice skill was selected; "
        f"got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Wiring guards: templates referenced from the contract + catalog
# ---------------------------------------------------------------------------


def test_voice_grounding_snippet_references_templates() -> None:
    """The #461 contract snippet points at the shipped starter templates."""

    snippet = (
        REPO_ROOT / "anvil" / "lib" / "snippets" / "voice_grounding.md"
    ).read_text(encoding="utf-8")
    assert "anvil/templates/voice/STYLE_GUIDE.template.md" in snippet, (
        "voice_grounding.md must reference the shipped STYLE_GUIDE template"
    )
    assert "anvil/templates/voice/VOCABULARY.template.md" in snippet, (
        "voice_grounding.md must reference the shipped VOCABULARY template"
    )


def test_templates_catalog_lists_voice_row() -> None:
    """anvil/templates/README.md lists the new voice/ row."""

    catalog = (REPO_ROOT / "anvil" / "templates" / "README.md").read_text(
        encoding="utf-8"
    )
    assert re.search(r"`voice/`", catalog), (
        "anvil/templates/README.md missing the voice/ shipped-templates row"
    )
