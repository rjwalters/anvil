"""Doc-coverage smoke tests for the deck ``deck-imagegen`` command spec
and the ``deck-imagegen-adapter`` contract doc.

Per issue #131 (Epic #130 / Phase 1A) acceptance criteria: cheap
"grep-the-doc" regression guard that both new foundation docs exist as
first-class command specs (NOT stubs), reference each other coherently,
and surface the load-bearing opt-in framing in SKILL.md (the "Not
shipped in v0" disclaimer was replaced with the
``imagery_policy: generative-eligible`` opt-in model per the issue AC).

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The command itself is LLM-driven, so
behavioural assertions belong in consumer-side integration tests, not
here. The actual command implementation lands in Phase 2 (Epic #130 /
issue E); this issue ships foundation docs only.

Per-skill test filename convention (#58): this file is named with a
``test_deck_`` prefix so it never collides with a parallel-skill test
of the same shape.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"
SKILL_MD = SKILL_ROOT / "SKILL.md"
IMAGEGEN_MD = SKILL_ROOT / "commands" / "deck-imagegen.md"
ADAPTER_MD = SKILL_ROOT / "commands" / "deck-imagegen-adapter.md"
FIGURES_MD = SKILL_ROOT / "commands" / "deck-figures.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# deck-imagegen.md — first-class command spec (new in #131)
# ---------------------------------------------------------------------------


def test_deck_imagegen_command_exists():
    assert IMAGEGEN_MD.exists(), (
        "anvil/skills/deck/commands/deck-imagegen.md MUST exist per "
        "issue #131 (Epic #130 Phase 1A)"
    )


def test_deck_imagegen_has_frontmatter():
    body = _read(IMAGEGEN_MD)
    # SKILL-command convention: YAML frontmatter with name + description.
    assert body.lstrip().startswith("---"), (
        "deck-imagegen.md MUST open with YAML frontmatter per skill convention"
    )
    assert "name: deck-imagegen" in body, (
        "deck-imagegen.md frontmatter MUST set name: deck-imagegen"
    )
    assert "description:" in body, (
        "deck-imagegen.md frontmatter MUST include a description"
    )


def test_deck_imagegen_is_not_a_stub():
    """Per issue #131 AC: 'first-class command spec (NOT a stub)'. We
    check that the doc has the standard command sections (Inputs,
    Outputs, Procedure, etc.) rather than being a redirect placeholder."""
    body = _read(IMAGEGEN_MD)
    # Standard command-spec sections.
    assert "## Inputs" in body, "deck-imagegen.md MUST have an Inputs section"
    assert "## Outputs" in body, "deck-imagegen.md MUST have an Outputs section"
    assert "## Procedure" in body, "deck-imagegen.md MUST have a Procedure section"
    # First-class command specs document failure modes and when to run.
    assert "Failure modes" in body or "## Failure" in body, (
        "deck-imagegen.md MUST document failure modes (first-class spec)"
    )
    assert "When to run" in body or "## When" in body, (
        "deck-imagegen.md MUST document when to run it (first-class spec)"
    )


def test_deck_imagegen_documents_opt_in_precondition():
    body = _read(IMAGEGEN_MD)
    # Per issue #131 AC: preconditions include
    # `imagery_policy: generative-eligible` in BRIEF.md frontmatter.
    assert "imagery_policy: generative-eligible" in body, (
        "deck-imagegen.md MUST document the imagery_policy: generative-eligible "
        "opt-in precondition (issue #131 AC; Epic #130 Phase 1B contract)"
    )
    assert "BRIEF.md" in body, (
        "deck-imagegen.md MUST point at BRIEF.md as the opt-in location"
    )


def test_deck_imagegen_documents_postconditions():
    body = _read(IMAGEGEN_MD)
    # Per issue #131 AC: postconditions are PNG assets + prompt journal.
    assert "assets/" in body, (
        "deck-imagegen.md MUST document the assets/ output directory"
    )
    assert "_prompts.json" in body, (
        "deck-imagegen.md MUST document the prompt journal at "
        "assets/_prompts.json (issue #131 AC; Phase 2 primitive)"
    )


def test_deck_imagegen_documents_failure_modes():
    body = _read(IMAGEGEN_MD)
    # Per issue #131 AC: failure modes include missing adapter config,
    # adapter error, missing policy.
    lowered = body.lower()
    assert "missing" in lowered or "absent" in lowered, (
        "deck-imagegen.md MUST document missing-precondition failure modes"
    )
    assert "BackendError" in body or "backend error" in lowered, (
        "deck-imagegen.md MUST document adapter error handling"
    )


def test_deck_imagegen_cross_references_adapter_doc():
    body = _read(IMAGEGEN_MD)
    # Per issue #131 AC: cross-reference to deck-imagegen-adapter.md.
    assert "deck-imagegen-adapter.md" in body, (
        "deck-imagegen.md MUST cross-reference deck-imagegen-adapter.md "
        "(issue #131 AC)"
    )


def test_deck_imagegen_documents_progress_phase():
    body = _read(IMAGEGEN_MD)
    # Every anvil command writes a _progress.json phase entry per the
    # framework snippet contract.
    assert "_progress.json" in body, (
        "deck-imagegen.md MUST document _progress.json per snippets/progress.md"
    )
    assert "phases.imagegen" in body or "imagegen" in body, (
        "deck-imagegen.md MUST name its phase entry (phases.imagegen)"
    )


# ---------------------------------------------------------------------------
# deck-imagegen-adapter.md — adapter contract (new in #131)
# ---------------------------------------------------------------------------


def test_deck_imagegen_adapter_exists():
    assert ADAPTER_MD.exists(), (
        "anvil/skills/deck/commands/deck-imagegen-adapter.md MUST exist "
        "per issue #131 (Epic #130 Phase 1A)"
    )


def test_deck_imagegen_adapter_has_frontmatter():
    body = _read(ADAPTER_MD)
    assert body.lstrip().startswith("---"), (
        "deck-imagegen-adapter.md MUST open with YAML frontmatter per "
        "skill convention"
    )
    assert "name: deck-imagegen-adapter" in body, (
        "deck-imagegen-adapter.md frontmatter MUST set "
        "name: deck-imagegen-adapter"
    )


def test_deck_imagegen_adapter_documents_minimal_signature():
    body = _read(ADAPTER_MD)
    # Per issue #131 AC: minimal
    # `class ImageBackend: def generate(self, prompt: str, style: str,
    # steps: int | None) -> bytes` signature.
    assert "class ImageBackend" in body, (
        "deck-imagegen-adapter.md MUST document the ImageBackend class "
        "(issue #131 AC)"
    )
    assert "def generate" in body, (
        "deck-imagegen-adapter.md MUST document the generate() method "
        "signature (issue #131 AC)"
    )
    # Parameter names from the contract.
    assert "prompt: str" in body, (
        "deck-imagegen-adapter.md MUST document the prompt: str parameter"
    )
    assert "style: str" in body, (
        "deck-imagegen-adapter.md MUST document the style: str parameter"
    )
    assert "steps: int | None" in body, (
        "deck-imagegen-adapter.md MUST document the steps: int | None parameter"
    )
    # Return type.
    assert "-> bytes" in body, (
        "deck-imagegen-adapter.md MUST document the -> bytes return type "
        "(issue #131 AC)"
    )


def test_deck_imagegen_adapter_documents_consumer_registration():
    body = _read(ADAPTER_MD)
    # Per issue #131 AC: consumer registration via .anvil/config.toml.
    assert ".anvil/config.toml" in body, (
        "deck-imagegen-adapter.md MUST document the .anvil/config.toml "
        "registration mechanism (issue #131 AC)"
    )
    assert "[deck.imagegen]" in body, (
        "deck-imagegen-adapter.md MUST document the [deck.imagegen] "
        "config-toml section"
    )
    assert "backend" in body, (
        "deck-imagegen-adapter.md MUST document the backend = ... key"
    )


def test_deck_imagegen_adapter_documents_non_goals():
    body = _read(ADAPTER_MD)
    # Per issue #131 AC: explicit non-goals (retry, rate-limit,
    # deterministic seeds, auth) are CONSUMER responsibility.
    lowered = body.lower()
    assert "non-goal" in lowered or "non goal" in lowered, (
        "deck-imagegen-adapter.md MUST have an explicit 'Non-goals' section "
        "(issue #131 AC)"
    )
    # Each named non-goal must appear.
    assert "retry" in lowered, (
        "deck-imagegen-adapter.md MUST name retry/backoff as a non-goal "
        "(issue #131 AC)"
    )
    assert "rate limit" in lowered or "rate-limit" in lowered, (
        "deck-imagegen-adapter.md MUST name rate limiting as a non-goal "
        "(issue #131 AC)"
    )
    assert "seed" in lowered, (
        "deck-imagegen-adapter.md MUST name deterministic seeds as a non-goal "
        "(issue #131 AC)"
    )
    assert "auth" in lowered, (
        "deck-imagegen-adapter.md MUST name auth/secrets as a non-goal "
        "(issue #131 AC)"
    )
    # The consumer-responsibility framing.
    assert "consumer" in lowered, (
        "deck-imagegen-adapter.md MUST frame non-goals as consumer "
        "responsibility (issue #131 AC)"
    )


def test_deck_imagegen_adapter_documents_BackendError():
    body = _read(ADAPTER_MD)
    # BackendError is the exception type that surfaces failures from
    # the adapter to deck-imagegen.
    assert "BackendError" in body, (
        "deck-imagegen-adapter.md MUST document the BackendError exception type"
    )


def test_deck_imagegen_adapter_cross_references_command_doc():
    body = _read(ADAPTER_MD)
    assert "deck-imagegen.md" in body, (
        "deck-imagegen-adapter.md MUST cross-reference deck-imagegen.md "
        "(issue #131 AC)"
    )


def test_deck_imagegen_adapter_documents_anvil_responsibility_boundary():
    body = _read(ADAPTER_MD)
    # The architect's load-bearing framing: anvil's responsibility ends
    # at "dispatch the call, surface the error, write the journal."
    lowered = body.lower()
    assert "dispatch" in lowered and "journal" in lowered, (
        "deck-imagegen-adapter.md MUST document anvil's responsibility "
        "boundary (dispatch / surface / journal)"
    )


# ---------------------------------------------------------------------------
# SKILL.md — opt-in framing replaces "Not shipped in v0" (issue #131 AC)
# ---------------------------------------------------------------------------


def test_skill_md_removes_not_shipped_in_v0_disclaimer():
    body = _read(SKILL_MD)
    # Per issue #131 AC: delete the "Not shipped in v0" disclaimer in
    # the generative-imagery bullet of the Asset generation section.
    # The phrase MUST NOT remain in the generative-imagery bullet of
    # the Asset generation section. (It may appear in other contexts
    # like the pre-flight lint section; we narrow the check to the
    # asset-generation bullet.)
    asset_section_start = body.find("## Asset generation")
    asset_section_end = body.find("## Output format")
    assert asset_section_start > -1 and asset_section_end > -1
    asset_block = body[asset_section_start:asset_section_end]
    assert "Not shipped in v0" not in asset_block, (
        "SKILL.md Asset generation section MUST NOT contain the "
        "'Not shipped in v0' disclaimer (issue #131 AC; replaced with "
        "the opt-in framing)"
    )


def test_skill_md_documents_opt_in_framing():
    body = _read(SKILL_MD)
    # Per issue #131 AC: replace with "Opt-in via
    # `imagery_policy: generative-eligible`".
    assert "imagery_policy: generative-eligible" in body, (
        "SKILL.md MUST document the imagery_policy: generative-eligible "
        "opt-in framing (issue #131 AC; replaces the 'Not shipped in v0' "
        "disclaimer)"
    )
    lowered = body.lower()
    assert "opt-in" in lowered or "opt in" in lowered, (
        "SKILL.md MUST surface the opt-in framing in the asset-generation "
        "section"
    )


def test_skill_md_documents_backwards_compat():
    body = _read(SKILL_MD)
    # Per issue #131 AC: decks without imagery_policy default to
    # deterministic-only (current behavior).
    assert "deterministic-only" in body, (
        "SKILL.md MUST document the deterministic-only default that "
        "preserves backwards compatibility (issue #131 AC)"
    )


def test_skill_md_references_adapter_contract():
    body = _read(SKILL_MD)
    # The opt-in framing in SKILL.md MUST point readers at the
    # adapter-contract doc.
    assert "deck-imagegen-adapter.md" in body, (
        "SKILL.md MUST cross-reference deck-imagegen-adapter.md so the "
        "reader sees the adapter contract without crawling commands/"
    )


# ---------------------------------------------------------------------------
# Cross-file coherence: command <-> adapter <-> SKILL.md
# ---------------------------------------------------------------------------


def test_cross_file_references_are_bidirectional():
    """The two new docs MUST cross-reference each other; SKILL.md MUST
    point at both. Otherwise a reader landing on one doc can't find the
    other."""
    command_body = _read(IMAGEGEN_MD)
    adapter_body = _read(ADAPTER_MD)
    skill_body = _read(SKILL_MD)
    assert "deck-imagegen-adapter.md" in command_body, (
        "deck-imagegen.md MUST reference deck-imagegen-adapter.md"
    )
    assert "deck-imagegen.md" in adapter_body, (
        "deck-imagegen-adapter.md MUST reference deck-imagegen.md"
    )
    assert "deck-imagegen.md" in skill_body, (
        "SKILL.md MUST reference deck-imagegen.md"
    )
    assert "deck-imagegen-adapter.md" in skill_body, (
        "SKILL.md MUST reference deck-imagegen-adapter.md"
    )


def test_deck_figures_references_imagegen_as_parallel_asset_path():
    """deck-figures.md (the deterministic asset path) should reference
    deck-imagegen as the parallel generative path so a reader landing on
    figures sees the full asset story."""
    body = _read(FIGURES_MD)
    assert "deck-imagegen" in body, (
        "deck-figures.md MUST reference deck-imagegen (the parallel "
        "generative-imagery asset path) so readers see the full asset "
        "story without crawling SKILL.md"
    )
