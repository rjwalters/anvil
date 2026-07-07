"""Regression tests: VALUES.template.md ships + scaffolds privately (#578).

Phase C of epic #575. ``VALUES.md`` is the highest-leverage voice-grounding
doc (audience, stances, anti-stances, standing, voice signatures, named failure
modes) but also the most personal — one author's actual first-person beliefs
cannot ship as library content. The right library unit is a **schema/template**:
the proven *shape* of a values doc with instructive placeholders, scaffolded
**private by default** as a gitignored ``VALUES.local.md`` (reusing the
``*.local.md`` private path #577 shipped) so a consumer's first-person stances
never get committed by accident.

The contract this test enforces:

  * The template ships at ``anvil/templates/voice/VALUES.template.md`` with the
    nine proven sections (Audience, Stances, Anti-stances, Substrate, Forming
    positions, Voice modes, Standing, Voice signatures, Failure modes) and is
    **de-personalized** — no canary author belief
    content survives; every author-specific slot is a ``<!-- replace me -->``
    placeholder.
  * The header's ``voice:`` example shows the PRIVATE wiring
    (``values: VALUES.local.md``), not a committed path.
  * Stage 7.9 scaffolds ``VALUES.template.md → .anvil/voice/VALUES.local.md``
    (NOT a committed ``VALUES.md``), covered by the ``*.local.md`` gitignore
    line — which matches the ``.local.md`` suffix anywhere in the tree, so the
    post-#617 ``.anvil/voice/`` relocation needs no new pattern.
  * Per-file skip-if-exists / ``--dry-run`` / never-clobber, like its siblings.
  * The template is cross-linked to the rhetoric lint (#463) and the
    example-coherence / numeric-consistency gates, and referenced from
    ``README.md`` + ``voice_grounding.md``.

Distinct filename per the #58 packaging convention (sibling to
``test_install_voice_scaffold.py`` / ``test_install_voice_gitignore.py``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

# Post-#617 scaffold destination under the consumer root.
VOICE_DST_REL = Path(".anvil") / "voice"

VOICE_SRC = REPO_ROOT / "anvil" / "templates" / "voice"
VALUES_TEMPLATE = VOICE_SRC / "VALUES.template.md"

# Canary author-specific tokens drawn from the source rjwalters.info VALUES.md.
# NONE of these belief/domain/post-slug strings may survive de-personalization —
# the template ships schema, not content (the load-bearing epic tenet). This is
# the load-bearing de-personalization guard.
BANNED_TOKENS = (
    "dinner party",
    "dinner-party",
    "Camus",
    "Kierkegaard",
    "Sisyphus",
    "vibesql",
    "VibeSQL",
    "praxisist",
    "leangenius",
    "Howl",
    "Ginsberg",
    "Ram Dass",
    "Hofstadter",
    "toaster",
    "Genette",
    "paratext",
    "Wittgenstein",
    "Heidegger",
    "Tractatus",
    "Polanyi",
    "grazer",
    "clanker",
    "group-MoE",
    "Group-MoE",
    "Moloch",
    "Be Here Now",
    "Be There Tomorrow",
    "Rap Genius",
    "Robb",
    "burning man",
)

# The nine proven sections that must survive generalization. Substrate,
# Forming positions, and Voice modes were added in #600 — the essay rubric
# (dim 5 substrate / forming positions; dim 2 declared modes) and
# voice_grounding.md already consume these concepts; the starter template now
# gives authors a place to declare them.
REQUIRED_SECTIONS = (
    "## Audience",
    "## Stances",
    "## Anti-stances",
    "## Substrate",
    "## Forming positions",
    "## Voice modes",
    "## Standing",
    "## Voice signatures",
    "## Failure modes",
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
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
# Source-tree shape: the template ships with the six sections, de-personalized
# ---------------------------------------------------------------------------


def test_values_template_ships() -> None:
    assert VALUES_TEMPLATE.is_file(), f"missing {VALUES_TEMPLATE}"


def test_values_template_has_all_nine_sections() -> None:
    """All nine proven sections survive generalization (six original + the
    three #600 additions: Substrate, Forming positions, Voice modes)."""
    text = VALUES_TEMPLATE.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in text, f"VALUES template lost section: {section}"


def test_values_template_is_depersonalized() -> None:
    """No canary belief/domain/post-slug token survives; placeholders present."""
    text = VALUES_TEMPLATE.read_text(encoding="utf-8")
    lowered = text.lower()
    for token in BANNED_TOKENS:
        assert token.lower() not in lowered, (
            f"VALUES.template.md still contains the canary author-specific "
            f"token {token!r} — de-personalization incomplete; the template "
            f"must ship schema, not content"
        )
    # Every author-specific slot is a marked placeholder.
    assert "<!-- replace me" in text, (
        "VALUES template has no <!-- replace me --> placeholder — the stances / "
        "anti-stances / standing slots must be marked fill-in-your-own"
    )


def test_values_template_header_shows_private_wiring() -> None:
    """The header's voice: example uses the PRIVATE path, not a committed one."""
    text = VALUES_TEMPLATE.read_text(encoding="utf-8")
    assert "values: .anvil/voice/VALUES.local.md" in text, (
        "VALUES template header must show the private "
        "'values: .anvil/voice/VALUES.local.md' wiring (private by default, "
        "resolved at the post-#617 scaffold destination), not a committed "
        "VALUES.md path"
    )


def test_values_template_cross_links_lint_and_gates() -> None:
    """Failure-modes / anti-stances cross-reference the lint + gates (#463)."""
    text = VALUES_TEMPLATE.read_text(encoding="utf-8")
    # Rhetoric lint cross-link (deterministic word/em-dash screening is #463).
    assert "#463" in text, (
        "VALUES template must cross-link the rhetoric lint (#463) so judgment "
        "and the deterministic gate reinforce rather than duplicate"
    )
    # Example-coherence / numeric-consistency gates are pointed at, not redone.
    assert "example" in text.lower() and "coherence" in text.lower(), (
        "VALUES template failure-modes section must point at the "
        "example-coherence gate concern rather than re-implement it"
    )


# ---------------------------------------------------------------------------
# Private-by-default scaffold: VALUES.local.md, NOT a committed VALUES.md
# ---------------------------------------------------------------------------


def test_scaffolds_values_local_not_committed_values(tmp_path: Path) -> None:
    target = tmp_path / "values-target"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    local = target / VOICE_DST_REL / "VALUES.local.md"
    committed = target / VOICE_DST_REL / "VALUES.md"
    assert local.is_file(), (
        f"did not scaffold the private .anvil/voice/VALUES.local.md; "
        f"stdout:\n{result.stdout}"
    )
    assert not committed.exists(), (
        "scaffolded a COMMITTED VALUES.md — the values doc must be private by "
        "default (VALUES.local.md only)"
    )
    # Regression guard (#617): the old consumer-root path must NOT be created.
    assert not (target / "VALUES.local.md").exists(), (
        "fresh install created a root-level VALUES.local.md — the values doc "
        f"must scaffold under .anvil/voice/ post-#617; stdout:\n{result.stdout}"
    )
    # Byte-faithful copy of the shipped template.
    assert local.read_text(encoding="utf-8") == VALUES_TEMPLATE.read_text(
        encoding="utf-8"
    ), "scaffolded VALUES.local.md differs from the shipped template"


def test_scaffolded_values_local_is_gitignored(tmp_path: Path) -> None:
    """The scaffolded VALUES.local.md is covered by the *.local.md ignore line."""
    target = tmp_path / "values-ignored"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    gi = (target / ".gitignore").read_text(encoding="utf-8")
    lines = [
        ln.strip()
        for ln in gi.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert "*.local.md" in lines, (
        f"*.local.md not in .gitignore — VALUES.local.md is not protected: {lines}"
    )
    # And git actually ignores the relocated path (the authoritative check).
    # The ``*.local.md`` pattern (no leading slash) matches the ``.local.md``
    # suffix anywhere in the tree, so ``.anvil/voice/VALUES.local.md`` is
    # covered without a new pattern.
    check = subprocess.run(
        ["git", "check-ignore", ".anvil/voice/VALUES.local.md"],
        capture_output=True,
        text=True,
        cwd=target,
    )
    # git check-ignore exits 0 when the path IS ignored. A non-git target dir
    # (no .git) returns 128 — tolerate that and rely on the .gitignore line
    # assertion above; when git IS available the path must be ignored.
    if check.returncode not in (0, 128):
        raise AssertionError(
            f"git check-ignore unexpected rc={check.returncode}: {check.stderr}"
        )


def test_no_values_scaffold_without_voice_skill(tmp_path: Path) -> None:
    target = tmp_path / "no-voice-values"
    target.mkdir()

    result = _run("--skills=pub", str(target))
    _assert_ok(result)

    assert not (target / VOICE_DST_REL / "VALUES.local.md").exists(), (
        "scaffolded VALUES.local.md even though no voice-consuming skill was "
        f"selected; stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Idempotency + per-file skip-if-exists + --dry-run
# ---------------------------------------------------------------------------


def test_reinstall_preserves_existing_values_local(tmp_path: Path) -> None:
    target = tmp_path / "values-idempotent"
    target.mkdir()

    _assert_ok(_run("--skills=memo", str(target)))
    local = target / VOICE_DST_REL / "VALUES.local.md"
    sentinel = "# my private values\n\nMy real stances live here.\n"
    local.write_text(sentinel, encoding="utf-8")

    second = _run("--skills=memo", str(target))
    _assert_ok(second)
    assert local.read_text(encoding="utf-8") == sentinel, (
        "re-install clobbered a hand-authored VALUES.local.md"
    )


def test_skip_is_per_file_values_does_not_block_others(tmp_path: Path) -> None:
    """A custom VALUES.local.md does not block STYLE_GUIDE.md from scaffolding."""
    target = tmp_path / "values-per-file"
    (target / VOICE_DST_REL).mkdir(parents=True)
    (target / VOICE_DST_REL / "VALUES.local.md").write_text(
        "# custom\n", encoding="utf-8"
    )

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    assert (
        target / VOICE_DST_REL / "VALUES.local.md"
    ).read_text(encoding="utf-8") == "# custom\n"
    assert (target / VOICE_DST_REL / "STYLE_GUIDE.md").is_file(), (
        "STYLE_GUIDE.md not scaffolded — the skip must be per-file"
    )


def test_dry_run_does_not_write_values_local(tmp_path: Path) -> None:
    target = tmp_path / "values-dry-run"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=memo", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    assert (
        "[dry-run] scaffold voice-grounding doc at .anvil/voice/VALUES.local.md"
        in result.stdout
    ), f"expected the dry-run VALUES.local.md action line; got:\n{result.stdout}"
    assert not (target / VOICE_DST_REL / "VALUES.local.md").exists(), (
        "--dry-run wrote VALUES.local.md to the target"
    )


def test_summary_hint_shows_private_values_wiring(tmp_path: Path) -> None:
    """Stage 11 hint shows the private values: VALUES.local.md wiring."""
    target = tmp_path / "values-hint"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)
    assert "values: .anvil/voice/VALUES.local.md" in result.stdout, (
        f"Stage 11 hint missing the private values wiring; got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Wiring guards: template referenced from the contract + README
# ---------------------------------------------------------------------------


def test_voice_grounding_snippet_references_values_template() -> None:
    snippet = (
        REPO_ROOT / "anvil" / "lib" / "snippets" / "voice_grounding.md"
    ).read_text(encoding="utf-8")
    assert "anvil/templates/voice/VALUES.template.md" in snippet, (
        "voice_grounding.md must reference the shipped VALUES template"
    )


def test_readme_flips_values_row_to_yes() -> None:
    readme = (VOICE_SRC / "README.md").read_text(encoding="utf-8")
    # The taxonomy row no longer says "deferred to issue #578".
    assert "deferred to issue #578" not in readme, (
        "README still marks VALUES as deferred — flip the row to Yes"
    )
    assert "VALUES.template.md" in readme, (
        "README does not reference the shipped VALUES.template.md"
    )
    assert "VALUES.local.md" in readme, (
        "README must document the private VALUES.local.md scaffold destination"
    )
