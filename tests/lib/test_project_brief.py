"""Canonical-path tests for ``anvil.lib.project_brief`` (issue #382).

Promoted from ``anvil/skills/memo/lib/`` under factoring A of issue
#382. The full behavioral corpus lives at
``anvil/skills/memo/tests/test_project_brief.py`` and continues to run
against the canonical implementation through the memo back-compat shim.
This file pins the promotion contracts (canonical import path + shim
identity) plus representative parse behavior, including the paired
iteration-cap override that ``anvil:project-migrate`` now writes when
merging a deck thread's ``.anvil.json`` (issue #382).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from anvil.lib.project_brief import (
    DEFAULT_MAX_ITERATIONS,
    BriefDocument,
    CompanionRefTypeError,
    ProjectBrief,
    load_project_brief,
    resolve_code_ref,
    resolve_spec_ref,
)
from anvil.lib.project_discovery import BRIEF_FILENAME


def _write_brief(project: Path, frontmatter: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / BRIEF_FILENAME).write_text(
        f"---\n{textwrap.dedent(frontmatter)}---\n\n# BRIEF\n",
        encoding="utf-8",
    )


def test_shim_reexports_same_objects() -> None:
    from anvil.skills.memo.lib import project_brief as shim

    assert shim.load_project_brief is load_project_brief
    assert shim.ProjectBrief is ProjectBrief
    assert shim.BriefDocument is BriefDocument
    assert shim.DEFAULT_MAX_ITERATIONS == DEFAULT_MAX_ITERATIONS
    # Non-__all__ module attributes historically importable from the
    # memo path (consumed by sys.path-injected top-level imports).
    assert shim.BRIEF_FILENAME == BRIEF_FILENAME


def test_load_well_formed_brief(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert [d.slug for d in brief.documents] == ["acme"]


def test_absent_brief_returns_none(tmp_path: Path) -> None:
    project = tmp_path / "empty"
    project.mkdir()
    assert load_project_brief(project) is None


def test_paired_iteration_cap_override_parses(tmp_path: Path) -> None:
    """The shape project-migrate writes for a deck thread (issue #382)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: series-a-deck
            artifact_type: investment-memo
            max_iterations: 6
            iteration_cap_rationale: |
              One extra pass to land the outcome detail.
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    doc = brief.documents[0]
    assert doc.max_iterations == 6
    assert "outcome detail" in (doc.iteration_cap_rationale or "")


def test_unpaired_max_iterations_rejected(tmp_path: Path) -> None:
    """STRICT contract: max_iterations without rationale raises — this is
    why the migrate planner drops unpaired overrides instead of carrying
    them into the BRIEF."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
            max_iterations: 6
        """,
    )
    with pytest.raises(ValueError):
        load_project_brief(project)


# ---------------------------------------------------------------------------
# web_search opt-in knob (issue #424)
# ---------------------------------------------------------------------------


def test_web_search_true_parses(tmp_path: Path) -> None:
    """`web_search: true` on a pub document entry parses as a strict bool."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: q3-method
            artifact_type: pub
            web_search: true
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.documents[0].web_search is True


def test_web_search_false_parses(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: q3-method
            artifact_type: pub
            web_search: false
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.documents[0].web_search is False


def test_web_search_absent_defaults_to_none(tmp_path: Path) -> None:
    """Knob absent → None (≡ disabled); the off-by-default contract."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: q3-method
            artifact_type: pub
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.documents[0].web_search is None


@pytest.mark.parametrize("raw", ['"true"', '"yes"', "1", "0", "[true]"])
def test_web_search_non_bool_rejected(tmp_path: Path, raw: str) -> None:
    """Strict bool: strings / ints / lists raise with a field-path message.

    A silently-coerced truthy string must not flip the anti-hallucination
    posture (issue #424).
    """
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        documents:
          - slug: q3-method
            artifact_type: pub
            web_search: {raw}
        """,
    )
    with pytest.raises(ValueError, match=r"web_search"):
        load_project_brief(project)


def test_web_search_error_message_is_helpful(tmp_path: Path) -> None:
    """The rejection names the field path and suggests the YAML-bool fix."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: q3-method
            artifact_type: pub
            web_search: "true"
        """,
    )
    with pytest.raises(ValueError) as excinfo:
        load_project_brief(project)
    msg = str(excinfo.value)
    assert "documents[0].web_search" in msg
    assert "boolean" in msg
    assert "web_search: true" in msg


@pytest.mark.parametrize("value", ["deck", "slides", "proposal"])
def test_skill_identity_artifact_types_accepted(
    tmp_path: Path, value: str
) -> None:
    """Issue #386: the enum grew skill-identity values so migration can
    write honest types for deck/slides/proposal threads."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        documents:
          - slug: some-thread
            artifact_type: {value}
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.documents[0].artifact_type.value == value


# ---------------------------------------------------------------------------
# Per-document pandoc passthrough knobs (issue #391):
# render_template / render_lua_filters / render_metadata
# ---------------------------------------------------------------------------


def test_render_passthrough_knobs_happy_path(tmp_path: Path) -> None:
    """The canary's full per-doc shape parses to the typed model verbatim
    (with scalars coerced to strings; {N} carried unexpanded)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: investment-memo
            artifact_type: investment-memo
            render_engine: xelatex
            render_template: sphere-memo-template.tex
            render_lua_filters: [strip-alt.lua, second.lua]
            render_metadata:
              doc-type: "Investment Memo"
              doc-version: "Draft v{N}"
              revision: 7
              internal: true
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    doc = brief.documents[0]
    assert doc.render_template == "sphere-memo-template.tex"
    # Declaration order preserved — pandoc applies filters in flag order.
    assert doc.render_lua_filters == ["strip-alt.lua", "second.lua"]
    assert doc.render_metadata == {
        "doc-type": "Investment Memo",
        # {N} is a render-time token — carried verbatim at parse time.
        "doc-version": "Draft v{N}",
        # Scalars coerce to strings; bools to lowercase per pandoc/YAML.
        "revision": "7",
        "internal": "true",
    }


def test_render_passthrough_knobs_absent_default_none(tmp_path: Path) -> None:
    """Back-compat: entries without the #391 knobs parse with all three
    fields ``None`` (the byte-identical-render regression anchor)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    doc = brief.documents[0]
    assert doc.render_template is None
    assert doc.render_lua_filters is None
    assert doc.render_metadata is None


def test_render_passthrough_empty_values_normalize_to_none(
    tmp_path: Path,
) -> None:
    """Empty string / empty list / empty map → ``None`` (a YAML author can
    leave the right-hand side blank and get back-compat behavior)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
            render_template: "   "
            render_lua_filters: []
            render_metadata: {}
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    doc = brief.documents[0]
    assert doc.render_template is None
    assert doc.render_lua_filters is None
    assert doc.render_metadata is None


def test_render_template_non_string_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
            render_template: [a.tex]
        """,
    )
    with pytest.raises(ValueError, match=r"documents\[0\]\.render_template"):
        load_project_brief(project)


def test_render_lua_filters_non_list_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
            render_lua_filters: strip-alt.lua
        """,
    )
    with pytest.raises(
        ValueError, match=r"documents\[0\]\.render_lua_filters"
    ):
        load_project_brief(project)


def test_render_lua_filters_empty_element_rejected(tmp_path: Path) -> None:
    """Element-level field path names the offending index."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
            render_lua_filters: ["strip-alt.lua", ""]
        """,
    )
    with pytest.raises(
        ValueError, match=r"documents\[0\]\.render_lua_filters\[1\]"
    ):
        load_project_brief(project)


def test_render_metadata_non_map_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
            render_metadata: [doc-type, Investment Memo]
        """,
    )
    with pytest.raises(ValueError, match=r"documents\[0\]\.render_metadata"):
        load_project_brief(project)


def test_render_metadata_non_scalar_value_rejected(tmp_path: Path) -> None:
    """Nested values are injection-shaped and rejected with the key named."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
            render_metadata:
              doc-type: ["Investment", "Memo"]
        """,
    )
    with pytest.raises(
        ValueError, match=r"documents\[0\]\.render_metadata\['doc-type'\]"
    ):
        load_project_brief(project)


def test_unknown_artifact_type_rejected(tmp_path: Path) -> None:
    """Closed-ended governance retained (#386): the studio's informal
    'pitch-deck' is NOT registered — the error lists the registered set
    so the fix is self-correcting."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: series-a-deck
            artifact_type: pitch-deck
        """,
    )
    with pytest.raises(ValueError, match="pitch-deck"):
        load_project_brief(project)


# ---------------------------------------------------------------------------
# Issue #394: registered canary genres + the consumer artifact-type tier
# ---------------------------------------------------------------------------


def _write_consumer_overlay(consumer_root: Path, type_name: str) -> Path:
    """Materialize a minimal valid consumer overlay JSON for ``type_name``."""
    import json

    overlay_dir = consumer_root / ".anvil" / "skills" / "memo" / "rubric_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    path = overlay_dir / f"{type_name}.json"
    path.write_text(
        json.dumps(
            {
                "artifact_type": type_name,
                "description": f"Consumer-declared {type_name} overlay.",
                "weight_adjustments": {"dim_6": -2},
                "calibration_prose": {"dim_1": f"{type_name} calibration."},
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("value", ["challenge-memo", "strategy-memo"])
def test_canary_memo_genres_registered(tmp_path: Path, value: str) -> None:
    """Issue #394 part 1: the canary-proven genres are registered enum
    members — a BRIEF declaring either parses cleanly."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        documents:
          - slug: some-thread
            artifact_type: {value}
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.documents[0].artifact_type.value == value


def test_consumer_overlay_backed_type_accepted(tmp_path: Path) -> None:
    """Issue #394 part 2: an unregistered type backed by
    ``<consumer>/.anvil/skills/memo/rubric_overlays/<type>.json`` parses
    cleanly (consumer root discovered via the ``.anvil/`` marker walk)."""
    _write_consumer_overlay(tmp_path, "field-note")
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: notes
            artifact_type: field-note
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    doc = brief.documents[0]
    # Consumer types are carried as validated plain strings that
    # interoperate with the str-enum frozenset membership checks.
    assert doc.artifact_type == "field-note"
    assert isinstance(doc.artifact_type, str)


def test_consumer_root_explicit_override(tmp_path: Path) -> None:
    """The explicit ``consumer_root`` parameter bypasses the marker walk
    (testability + callers that already know the root)."""
    consumer = tmp_path / "elsewhere"
    _write_consumer_overlay(consumer, "field-note")
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: notes
            artifact_type: field-note
        """,
    )
    # Without the override there is no .anvil ancestor → rejected.
    with pytest.raises(ValueError, match="field-note"):
        load_project_brief(project)
    # With the override the consumer tier resolves.
    brief = load_project_brief(project, consumer_root=consumer)
    assert brief is not None
    assert brief.documents[0].artifact_type == "field-note"


def test_unknown_type_error_names_consumer_extension_path(
    tmp_path: Path,
) -> None:
    """An unregistered type with NO consumer overlay still fails loudly,
    and the error enumerates registered values, discovered consumer
    types, and the consumer-overlay extension path."""
    _write_consumer_overlay(tmp_path, "field-note")
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: notes
            artifact_type: lab-journal
        """,
    )
    with pytest.raises(ValueError) as excinfo:
        load_project_brief(project)
    msg = str(excinfo.value)
    assert "lab-journal" in msg
    assert "challenge-memo" in msg  # registered set enumerated
    assert "field-note" in msg  # discovered consumer types enumerated
    assert ".anvil" in msg  # extension path named


def test_no_anvil_ancestor_skips_consumer_tier(tmp_path: Path) -> None:
    """Source-tree / tmp runs without a ``.anvil/`` ancestor skip the
    consumer tier gracefully: registered types parse, unregistered types
    raise with the generic extension-path hint."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None

    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: field-note
        """,
    )
    with pytest.raises(
        ValueError, match=r"\.anvil/skills/memo/rubric_overlays"
    ):
        load_project_brief(project)


# ---------------------------------------------------------------------------
# Companion-ref resolution: code_ref / spec_ref (issue #718)
# ---------------------------------------------------------------------------
#
# The bug fixed by #718: a *malformed* (wrong-type) code_ref / spec_ref
# raised a ValueError at BRIEF-parse time that resolve_code_ref /
# resolve_spec_ref blanket-swallowed into the SAME None result as "no
# code_ref/spec_ref declared" — silently disabling the consistency tier.
# The fix: a malformed declared value must resolve to a structured
# missing=True result (tier ACTIVE, major finding), never None (tier
# inactive). Only a genuinely ABSENT field, a structurally-unparseable
# BRIEF, or a malformed *other* companion field yields None.


def _write_spec_brief(project: Path, doc_lines: str) -> None:
    _write_brief(
        project,
        f"""\
        project: proj
        documents:
          - slug: sp
            artifact_type: spec
{doc_lines}
        """,
    )


def _write_primer_brief(project: Path, doc_lines: str) -> None:
    _write_brief(
        project,
        f"""\
        project: proj
        documents:
          - slug: pr
            artifact_type: primer
{doc_lines}
        """,
    )


# ---- code_ref (spec) --------------------------------------------------------


def test_resolve_code_ref_absent_is_inactive(tmp_path: Path) -> None:
    """No code_ref declared → None (tier INACTIVE), unchanged."""
    project = tmp_path / "proj"
    _write_spec_brief(project, "")
    assert resolve_code_ref(project, "sp") is None


def test_resolve_code_ref_null_is_inactive(tmp_path: Path) -> None:
    """`code_ref:` with an empty RHS (YAML null) → None (undeclared)."""
    project = tmp_path / "proj"
    _write_spec_brief(project, "            code_ref:")
    assert resolve_code_ref(project, "sp") is None


def test_resolve_code_ref_valid_resolves_active(tmp_path: Path) -> None:
    """A valid code_ref pointing at a real file → active, not missing."""
    project = tmp_path / "proj"
    (project).mkdir(parents=True, exist_ok=True)
    (project / "impl.rs").write_text("fn main() {}\n", encoding="utf-8")
    _write_spec_brief(project, "            code_ref: impl.rs")
    resolved = resolve_code_ref(project, "sp")
    assert resolved is not None
    assert resolved.missing is False
    assert resolved.paths
    assert resolved.paths[0].endswith("impl.rs")


def test_resolve_code_ref_bad_path_is_missing_active(tmp_path: Path) -> None:
    """Declared-but-unresolvable (bad path) → missing=True (tier ACTIVE)."""
    project = tmp_path / "proj"
    _write_spec_brief(project, "            code_ref: nope/missing.rs")
    resolved = resolve_code_ref(project, "sp")
    assert resolved is not None
    assert resolved.missing is True


def test_resolve_code_ref_malformed_list_is_missing_active(
    tmp_path: Path,
) -> None:
    """THE BUG (#718): a list-form code_ref must NOT degrade to None.

    A malformed (wrong-type) code_ref is a declared-but-broken
    declaration — it must ACTIVATE the tier via missing=True, exactly like
    a bad path, not silently disable the consistency tier.
    """
    project = tmp_path / "proj"
    _write_spec_brief(
        project,
        "            code_ref:\n"
        "              - crypto/pq/src/**/*.rs\n"
        "              - botho/src/block.rs",
    )
    resolved = resolve_code_ref(project, "sp")
    assert resolved is not None, "malformed code_ref must NOT resolve to None"
    assert resolved.missing is True
    # The clear type error is surfaced, not swallowed.
    assert "must be a string path/glob" in resolved.declared


def test_resolve_code_ref_malformed_int_is_missing_active(
    tmp_path: Path,
) -> None:
    """A non-string scalar (int) code_ref → missing=True (tier ACTIVE)."""
    project = tmp_path / "proj"
    _write_spec_brief(project, "            code_ref: 42")
    resolved = resolve_code_ref(project, "sp")
    assert resolved is not None
    assert resolved.missing is True


def test_resolve_code_ref_malformed_dict_is_missing_active(
    tmp_path: Path,
) -> None:
    """A mapping-form code_ref → missing=True (tier ACTIVE)."""
    project = tmp_path / "proj"
    _write_spec_brief(
        project,
        "            code_ref:\n              path: src/**/*.rs",
    )
    resolved = resolve_code_ref(project, "sp")
    assert resolved is not None
    assert resolved.missing is True


def test_resolve_code_ref_structurally_invalid_brief_is_none(
    tmp_path: Path,
) -> None:
    """A structurally-unparseable BRIEF still swallows to None (unchanged).

    A malformed *field* must surface (missing=True), but a whole-BRIEF
    schema failure (here: missing required `documents`) must remain the
    lenient None swallow — the narrow catch must not widen.
    """
    project = tmp_path / "proj"
    _write_brief(project, "project: proj\n")
    assert resolve_code_ref(project, "sp") is None


def test_resolve_code_ref_ignores_unrelated_malformed_spec_ref(
    tmp_path: Path,
) -> None:
    """A malformed spec_ref must not make resolve_code_ref return missing.

    resolve_code_ref only owns code_ref; an unrelated malformed companion
    field is swallowed to None for it, exactly like any other BRIEF-parse
    failure.
    """
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: sp
            artifact_type: primer
            spec_ref:
              - a.md
        """,
    )
    assert resolve_code_ref(project, "sp") is None


# ---- spec_ref (primer) ------------------------------------------------------


def test_resolve_spec_ref_absent_is_inactive(tmp_path: Path) -> None:
    """No spec_ref declared → None (tier INACTIVE), unchanged."""
    project = tmp_path / "proj"
    _write_primer_brief(project, "")
    assert resolve_spec_ref(project, "pr") is None


def test_resolve_spec_ref_valid_resolves_active(tmp_path: Path) -> None:
    """A valid spec_ref pointing at a real file → active, not missing."""
    project = tmp_path / "proj"
    project.mkdir(parents=True, exist_ok=True)
    (project / "spec.md").write_text("# Spec\n", encoding="utf-8")
    _write_primer_brief(project, "            spec_ref: spec.md")
    resolved = resolve_spec_ref(project, "pr")
    assert resolved is not None
    assert resolved.missing is False
    assert resolved.paths
    assert resolved.paths[0].endswith("spec.md")


def test_resolve_spec_ref_bad_path_is_missing_active(tmp_path: Path) -> None:
    """Declared-but-unresolvable (bad path) → missing=True (tier ACTIVE)."""
    project = tmp_path / "proj"
    _write_primer_brief(project, "            spec_ref: nope/missing.md")
    resolved = resolve_spec_ref(project, "pr")
    assert resolved is not None
    assert resolved.missing is True


def test_resolve_spec_ref_malformed_list_is_missing_active(
    tmp_path: Path,
) -> None:
    """THE BUG (#718), primer mirror: a list-form spec_ref must NOT be None."""
    project = tmp_path / "proj"
    _write_primer_brief(
        project,
        "            spec_ref:\n"
        "              - ../whitepaper/a.md\n"
        "              - ../whitepaper/b.md",
    )
    resolved = resolve_spec_ref(project, "pr")
    assert resolved is not None, "malformed spec_ref must NOT resolve to None"
    assert resolved.missing is True
    assert "must be a string path/glob" in resolved.declared


def test_resolve_spec_ref_malformed_int_is_missing_active(
    tmp_path: Path,
) -> None:
    """A non-string scalar (int) spec_ref → missing=True (tier ACTIVE)."""
    project = tmp_path / "proj"
    _write_primer_brief(project, "            spec_ref: 7")
    resolved = resolve_spec_ref(project, "pr")
    assert resolved is not None
    assert resolved.missing is True


def test_resolve_spec_ref_malformed_dict_is_missing_active(
    tmp_path: Path,
) -> None:
    """A mapping-form spec_ref → missing=True (tier ACTIVE)."""
    project = tmp_path / "proj"
    _write_primer_brief(
        project,
        "            spec_ref:\n              path: spec.md",
    )
    resolved = resolve_spec_ref(project, "pr")
    assert resolved is not None
    assert resolved.missing is True


def test_resolve_spec_ref_structurally_invalid_brief_is_none(
    tmp_path: Path,
) -> None:
    """A structurally-unparseable BRIEF still swallows to None (unchanged)."""
    project = tmp_path / "proj"
    _write_brief(project, "project: proj\n")
    assert resolve_spec_ref(project, "pr") is None


def test_resolve_spec_ref_ignores_unrelated_malformed_code_ref(
    tmp_path: Path,
) -> None:
    """A malformed code_ref must not make resolve_spec_ref return missing."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: pr
            artifact_type: spec
            code_ref:
              - a.rs
        """,
    )
    assert resolve_spec_ref(project, "pr") is None


# ---- validator-level: distinct exception type -------------------------------


def test_malformed_code_ref_raises_companion_ref_type_error(
    tmp_path: Path,
) -> None:
    """load_project_brief raises the distinct subclass for a bad code_ref.

    The subclass is a ValueError (so every other caller is unchanged), but
    carries the `field` discriminator the resolvers use.
    """
    project = tmp_path / "proj"
    _write_spec_brief(
        project, "            code_ref:\n              - a.rs"
    )
    with pytest.raises(CompanionRefTypeError) as excinfo:
        load_project_brief(project)
    assert excinfo.value.field == "code_ref"
    assert isinstance(excinfo.value, ValueError)


def test_malformed_spec_ref_raises_companion_ref_type_error(
    tmp_path: Path,
) -> None:
    """load_project_brief raises the distinct subclass for a bad spec_ref."""
    project = tmp_path / "proj"
    _write_primer_brief(
        project, "            spec_ref:\n              - a.md"
    )
    with pytest.raises(CompanionRefTypeError) as excinfo:
        load_project_brief(project)
    assert excinfo.value.field == "spec_ref"
    assert isinstance(excinfo.value, ValueError)
