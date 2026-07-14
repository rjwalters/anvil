"""Structural smoke tests for the ``anvil:spec`` skill (issue #697/#706).

These tests assert **structural properties** of the shipped skill files
(files exist, frontmatter parses, the rubric declares 9 dimensions summing
to 44 with a >=39 advance threshold under the ``anvil-spec-v1`` id,
normative correctness is the OWNED dominant dim 1 at weight 7, the
review-side critical flags + the Phase-2-forward-referenced
implementation-mismatch flag are documented, every critic-writing command
stamps the #346 rubric fields and uses the staged-sidecar primitive, the
``code_ref`` activation contract is documented, the report-shaped
audit+figures lifecycle is present, the adoption-mode section exists, and
Phase 2/3/4 logic is NOT implemented). They are intentionally NOT
golden-file tests — the skill is a generative authoring skill and prose
varies across runs and models.

Runs under either ``pytest anvil/skills/spec/tests/`` or
``python -m unittest discover anvil/skills/spec/tests/``.

Per the #58 packaging convention this filename
(``test_spec_command_coverage``) is unique across the
``anvil/skills/*/tests/`` tree; the package carries an ``__init__.py`` to
avoid the cross-skill pytest collection collision.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SKILL_ROOT.parents[2]

RUBRIC_ID = "anvil-spec-v1"

# Every critic-writing command must carry the #346 stamps + the atomic
# sidecar primitive.
CRITIC_COMMANDS = ("commands/spec-review.md", "commands/spec-audit.md")


def _read(rel: str) -> str:
    return (_SKILL_ROOT / rel).read_text(encoding="utf-8")


def _parse_frontmatter(text: str) -> dict:
    """Parse a leading ``---``-delimited YAML frontmatter block.

    Uses PyYAML when available; falls back to a minimal ``key: value``
    parser so the test does not hard-depend on PyYAML being installed.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}
    block = "\n".join(lines[1:end])
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:
        result: dict = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"').strip("'")
        return result


class TestFilesExist(unittest.TestCase):
    """The pinned file manifest is present on disk (Phase 1 scope)."""

    EXPECTED = [
        "SKILL.md",
        "rubric.md",
        "README.md",
        "__init__.py",
        "commands/spec.md",
        "commands/spec-draft.md",
        "commands/spec-review.md",
        "commands/spec-audit.md",
        "commands/spec-revise.md",
        "commands/spec-figures.md",
        "templates/BRIEF.md.example",
        "templates/spec.template.tex",
        "tests/__init__.py",
        "tests/test_spec_command_coverage.py",
    ]

    def test_manifest_present(self):
        for rel in self.EXPECTED:
            with self.subTest(path=rel):
                self.assertTrue(
                    (_SKILL_ROOT / rel).exists(), f"missing skill file: {rel}"
                )

    def test_deferred_scope_absent(self):
        # Phase 2/3/4 do not ship here: no three-way-verdict module, no
        # constant-consistency gate, no worked example, no draft-from-scratch
        # generative command.
        for stem in ("spec-change-impact", "spec-adopt"):
            with self.subTest(command=stem):
                self.assertFalse(
                    (_SKILL_ROOT / "commands" / f"{stem}.md").exists(),
                    f"{stem}.md is deferred/out-of-scope for Phase 1",
                )
        # The Phase-3 deterministic constant-consistency gate module is NOT
        # built in Phase 1.
        self.assertFalse(
            (_SKILL_ROOT / "lib" / "constant_consistency.py").exists(),
            "the constant-consistency gate is Phase 3 scope (#708)",
        )
        # The Phase-4 worked example is NOT vendored in Phase 1.
        self.assertFalse(
            (_SKILL_ROOT / "examples").exists(),
            "the botho worked example is Phase 4 scope (#709)",
        )


class TestSkillFrontmatter(unittest.TestCase):
    """SKILL.md frontmatter matches the sibling skills' shape."""

    def test_frontmatter(self):
        fm = _parse_frontmatter(_read("SKILL.md"))
        self.assertEqual(fm.get("name"), "spec")
        self.assertEqual(fm.get("domain"), "spec")
        self.assertEqual(fm.get("type"), "skill")
        self.assertIn(fm.get("user-invocable"), (False, "false"))

    def test_report_shaped_lifecycle(self):
        text = _read("SKILL.md")
        # Borrows the report/primer lifecycle shape — NOT a parameterization.
        self.assertIn("skill identity = artifact identity", text)
        self.assertIn("REVIEWED+AUDITED", text)
        self.assertIn("AUDITED", text)

    def test_code_ref_activation_contract_documented(self):
        text = _read("SKILL.md")
        self.assertIn("Code-ref contract", text)
        self.assertIn("resolve_code_ref", text)
        # Declared-but-missing is a defect to surface (major), absent is off.
        self.assertIn("major", text)
        self.assertIn("silent", text.lower())
        # Explicitly the mirror image of primer's spec_ref.
        self.assertIn("mirror image", text)
        self.assertIn("spec_ref", text)

    def test_adoption_mode_section_present(self):
        text = _read("SKILL.md")
        # A pub-style in-skill adoption section, NOT a project-migrate mode.
        self.assertIn("Adopting an existing spec", text)
        self.assertIn("first-class", text)

    def test_three_way_verdict_deferred_to_phase_two(self):
        text = _read("SKILL.md")
        # The three-way verdict is documented narratively as Phase 2 work.
        self.assertIn("three-way", text.lower())
        self.assertIn("#707", text)
        # Never auto-rewrites the spec toward the code.
        self.assertIn("never", text.lower())
        self.assertIn("vestigial code path", text)

    def test_latex_body_posture_documented(self):
        text = _read("SKILL.md")
        # A spec's body is LaTeX (departure from primer's markdown).
        self.assertIn("LaTeX", text)
        self.assertIn(".tex", text)

    def test_deferred_section_names_the_phases(self):
        text = _read("SKILL.md")
        self.assertIn("Deferred", text)
        for token in ("#707", "#708", "#709"):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_sidecar_stamping_and_scorecard_contracts_referenced(self):
        text = _read("SKILL.md")
        self.assertIn("staged_sidecar", text)
        self.assertIn(RUBRIC_ID, text)
        self.assertIn("human-verdict", text)


class TestCommandFrontmatter(unittest.TestCase):
    """Every command file carries a name/description frontmatter block."""

    COMMANDS = {
        "commands/spec.md": "spec",
        "commands/spec-draft.md": "spec-draft",
        "commands/spec-review.md": "spec-review",
        "commands/spec-audit.md": "spec-audit",
        "commands/spec-revise.md": "spec-revise",
        "commands/spec-figures.md": "spec-figures",
    }

    def test_command_frontmatter(self):
        for rel, expected_name in self.COMMANDS.items():
            with self.subTest(path=rel):
                fm = _parse_frontmatter(_read(rel))
                self.assertEqual(fm.get("name"), expected_name)
                self.assertTrue(
                    fm.get("description"), f"{rel} missing a description"
                )


class TestCriticCommandStamping(unittest.TestCase):
    """Both critic-writing commands stamp #346 fields + use staged_sidecar."""

    def test_stamps_and_sidecar_in_every_critic(self):
        for rel in CRITIC_COMMANDS:
            with self.subTest(command=rel):
                text = _read(rel)
                self.assertIn(RUBRIC_ID, text)
                self.assertIn("rubric_total: 44", text)
                self.assertIn("advance_threshold: 39", text)
                self.assertIn("staged_sidecar", text)
                self.assertIn("cleanup_one_staging", text)
                self.assertIn("human-verdict", text)


class TestCodeRefContractInCommands(unittest.TestCase):
    """The code_ref activation contract is wired into draft/review/audit."""

    def test_audit_resolves_code_ref_and_sweeps_when_present(self):
        text = _read("commands/spec-audit.md")
        self.assertIn("resolve_code_ref", text)
        # Absent → major finding, not a crash, not a false finding.
        self.assertIn("major", text)
        # Unresolvable path → graceful degradation, never raises.
        self.assertIn("never raises", text)
        self.assertIn("No false critical flag", text)

    def test_audit_defers_three_way_verdict_to_phase_two(self):
        text = _read("commands/spec-audit.md")
        # Phase 1 records a suspected mismatch as a major finding, NOT an
        # adjudicated critical flag; the three-way verdict is Phase 2.
        self.assertIn("#707", text)
        self.assertIn("three-way", text.lower())
        self.assertIn("major finding", text.lower())
        # Never auto-rewrites the spec toward the code (the safety property).
        self.assertIn("never", text.lower())
        self.assertIn("vestigial code path", text)
        # A clear Phase-2 extension point is left in the sweep.
        self.assertIn("extension point", text.lower())

    def test_review_records_major_finding_when_code_ref_undeclared(self):
        text = _read("commands/spec-review.md")
        self.assertIn("resolve_code_ref", text)
        self.assertIn("major", text)
        # Normative correctness is scored against the implementation.
        self.assertIn("Normative correctness", text)

    def test_draft_resolves_optional_code_ref(self):
        text = _read("commands/spec-draft.md")
        self.assertIn("resolve_code_ref", text)
        self.assertIn("code_ref_resolved", text)

    def test_draft_is_adoption_first(self):
        text = _read("commands/spec-draft.md")
        self.assertIn("adoption", text.lower())
        # Draft-from-scratch synthesis is deferred.
        self.assertIn("deferred", text.lower())
        # Never fabricates normative content.
        self.assertIn("stub", text.lower())


class TestReviseSafetyProperty(unittest.TestCase):
    """The reviser never rewrites the spec to match a vestigial code path."""

    def test_revise_escalates_ambiguous_mismatch(self):
        text = _read("commands/spec-revise.md")
        self.assertIn("vestigial code path", text)
        self.assertIn("operator", text.lower())
        # An ambiguous mismatch is escalated, not silently reconciled.
        self.assertIn("escalat", text.lower())


class TestFigurePlanContract(unittest.TestCase):
    """The draft-time figure-reference contract is documented across
    draft / figures / review."""

    def test_draft_records_figure_plan(self):
        text = _read("commands/spec-draft.md")
        self.assertIn("figure_plan", text)
        self.assertIn("exhibits/figN-slug.png", text)
        # Zero-figure threads are the silent-off default.
        self.assertIn("silent-off", text)

    def test_figures_ungated_from_audited_and_renders_referenced_paths(self):
        text = _read("commands/spec-figures.md")
        # No longer gated on AUDITED — runs any time after draft.
        self.assertIn("No terminal-state gate", text)
        self.assertIn("figure_plan", text)
        # Renders to exactly the drafter-referenced paths, never invents one.
        self.assertIn("exactly the", text)
        self.assertIn("never invent", text.lower())
        # Existence validation mirrors report/primer-figures.
        self.assertIn("Validation by file existence", text)
        # LaTeX render path (not pandoc/markdown) + the render gate.
        self.assertIn("render_gate.py", text)
        self.assertIn("xelatex", text.lower())

    def test_review_has_exhibit_existence_freshness_check(self):
        text = _read("commands/spec-review.md")
        self.assertIn("4c", text)
        self.assertIn("figure_plan", text)
        self.assertIn("stale", text.lower())
        # Zero-figure thread is a silent no-op (regression safety).
        self.assertIn("silent no-op", text)
        # No critical flag from the exhibit check.
        self.assertIn("no critical flag", text.lower())


class TestPolishFlagContract(unittest.TestCase):
    """The operator-directed revision flag is wired into spec-revise.md +
    SKILL.md, references the shared snippet, and bypasses ONLY the step-2
    combined verdict pre-check."""

    def test_revise_has_cli_flags_section_with_polish(self):
        text = _read("commands/spec-revise.md")
        self.assertIn("## CLI flags", text)
        self.assertIn('### `--polish "<reason>"`', text)
        self.assertIn("directed_revision.md", text)

    def test_revise_polish_bypasses_step_two_only(self):
        text = _read("commands/spec-revise.md")
        self.assertIn("Bypasses step 2 ONLY", text)
        self.assertIn("step 1", text)
        self.assertIn("step 3", text)
        self.assertIn("`--polish` bypass", text)

    def test_revise_polish_required_reason(self):
        text = _read("commands/spec-revise.md")
        self.assertIn('--polish ""', text)
        self.assertIn("whitespace-only", text)
        self.assertIn("left untouched", text)

    def test_revise_polish_no_inherited_credit(self):
        text = _read("commands/spec-revise.md")
        self.assertIn("No inherited credit", text)
        self.assertIn("own rubric merits", text)

    def test_revise_polish_audit_trail_fields(self):
        text = _read("commands/spec-revise.md")
        self.assertIn('metadata.revision_mode = "polish"', text)
        self.assertIn("metadata.revise_force_reason", text)
        self.assertIn("NO state-machine impact", text)

    def test_skill_documents_polish_pass(self):
        text = _read("SKILL.md")
        self.assertIn("Operator-initiated polish passes", text)
        self.assertIn("directed_revision.md", text)
        self.assertIn('--polish "<reason>"', text)
        self.assertIn("No inherited credit", text)


class TestRubric(unittest.TestCase):
    """rubric.md declares 9 dims summing to 44, >=39, normative-correctness
    dominant."""

    def setUp(self):
        self.text = _read("rubric.md")

    def test_nine_dimensions_sum_to_forty_four(self):
        rows = re.findall(
            r"^\|\s*([1-9])\s*\|\s*\*\*[^|]+\*\*\s*\|\s*(\d+)\s*\|",
            self.text,
            flags=re.MULTILINE,
        )
        self.assertEqual(
            len(rows), 9, f"expected 9 dimension rows, found {len(rows)}"
        )
        indices = sorted(int(i) for i, _ in rows)
        self.assertEqual(indices, [1, 2, 3, 4, 5, 6, 7, 8, 9])
        total = sum(int(w) for _, w in rows)
        self.assertEqual(total, 44, f"dimension weights sum to {total}, not 44")

    def test_dim_one_is_normative_correctness_dominant(self):
        self.assertTrue(
            re.search(
                r"^\|\s*1\s*\|\s*\*\*Normative correctness[^|]*\*\*\s*\|\s*7\s*\|",
                self.text,
                flags=re.MULTILINE,
            ),
            "dim 1 must be Normative correctness at weight 7",
        )

    def test_dim_one_is_the_unique_maximum(self):
        rows = re.findall(
            r"^\|\s*([1-9])\s*\|\s*\*\*[^|]+\*\*\s*\|\s*(\d+)\s*\|",
            self.text,
            flags=re.MULTILINE,
        )
        weights = {int(i): int(w) for i, w in rows}
        top = max(weights.values())
        winners = [i for i, w in weights.items() if w == top]
        self.assertEqual(
            winners, [1], f"dim 1 must be the unique dominant dim, got {winners}"
        )

    def test_advance_threshold_is_audit_grade_band(self):
        self.assertTrue(
            re.search(
                r"threshold to advance is \*\*≥39/44\*\*",
                self.text,
                re.IGNORECASE,
            ),
            "rubric must declare the >=39/44 audit-grade advance threshold",
        )

    def test_rubric_id_declared(self):
        self.assertIn(RUBRIC_ID, self.text)

    def test_named_critical_flags(self):
        text = self.text
        self.assertIn("Self-contradiction", text)
        self.assertIn("Undefined normative term", text)
        self.assertIn("Implementation contradicts normative claim", text)

    def test_three_way_verdict_is_phase_two_forward_reference(self):
        # The implementation-mismatch flag is documented as a Phase-2 forward
        # reference, NOT implemented three-way logic in Phase 1.
        self.assertIn("#707", self.text)
        self.assertIn("three-way", self.text.lower())
        # Phase 1 posture: major finding, never auto-rewrite.
        self.assertIn("major", self.text.lower())
        self.assertIn("never", self.text.lower())

    def test_flag_inactive_when_code_ref_undeclared(self):
        self.assertIn("cannot fire", self.text)
        self.assertIn("undeclared", self.text)

    def test_stamping_fields_in_meta_example(self):
        self.assertIn(f'"rubric_id": "{RUBRIC_ID}"', self.text)
        self.assertIn('"rubric_total": 44', self.text)
        self.assertIn('"advance_threshold": 39', self.text)

    def test_human_verdict_scorecard_kind(self):
        self.assertIn("human-verdict", self.text)


class TestRegistryIntegration(unittest.TestCase):
    """spec is registered as a skill-identity artifact type and the
    code_ref resolver + per-phase agents exist."""

    def _import_registry(self):
        import sys

        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        from anvil.lib import project_brief

        return project_brief

    def test_artifact_type_registered_as_skill_identity(self):
        pb = self._import_registry()
        self.assertIn("spec", pb.REGISTERED_ARTIFACT_TYPES)
        self.assertIn(pb.ArtifactType.SPEC, pb.SKILL_IDENTITY_ARTIFACT_TYPES)
        # NOT a memo subtype — selects no memo rubric overlay.
        self.assertNotIn(pb.ArtifactType.SPEC, pb.MEMO_ARTIFACT_TYPES)

    def test_resolve_code_ref_is_exported(self):
        pb = self._import_registry()
        self.assertTrue(hasattr(pb, "resolve_code_ref"))
        self.assertTrue(hasattr(pb, "ResolvedCodeRef"))

    def test_lifecycle_agents_generated(self):
        agents_dir = _REPO_ROOT / "anvil" / "agents"
        for name in (
            "anvil-spec-drafter.md",
            "anvil-spec-reviewer.md",
            "anvil-spec-reviser.md",
            "anvil-spec-auditor.md",
            "anvil-spec-figurer.md",
        ):
            with self.subTest(agent=name):
                self.assertTrue(
                    (agents_dir / name).is_file(),
                    f"missing agent registration {name} "
                    f"(run scripts/generate-anvil-agents.py)",
                )


class TestCodeRefResolver(unittest.TestCase):
    """resolve_code_ref honors the declared/absent/missing activation
    contract (mirror of resolve_spec_ref)."""

    def _import_registry(self):
        import sys

        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        from anvil.lib import project_brief

        return project_brief

    def _write_brief(self, project_dir: Path, code_ref_line: str) -> None:
        (project_dir / "BRIEF.md").write_text(
            "---\n"
            "project: toy\n"
            "documents:\n"
            "  - slug: toy-spec\n"
            "    artifact_type: spec\n"
            f"{code_ref_line}"
            "---\n\n"
            "# Toy spec project\n",
            encoding="utf-8",
        )

    def test_absent_code_ref_is_inactive_none(self):
        import tempfile

        pb = self._import_registry()
        with tempfile.TemporaryDirectory() as d:
            project_dir = Path(d)
            self._write_brief(project_dir, code_ref_line="")
            resolved = pb.resolve_code_ref(
                project_dir, "toy-spec", consumer_root=project_dir
            )
            self.assertIsNone(
                resolved, "absent code_ref must resolve to None (tier off)"
            )

    def test_declared_and_resolves(self):
        import tempfile

        pb = self._import_registry()
        with tempfile.TemporaryDirectory() as d:
            project_dir = Path(d)
            impl = project_dir / "impl.rs"
            impl.write_text("fn main() {}\n", encoding="utf-8")
            self._write_brief(
                project_dir, code_ref_line="    code_ref: impl.rs\n"
            )
            resolved = pb.resolve_code_ref(
                project_dir, "toy-spec", consumer_root=project_dir
            )
            self.assertIsNotNone(resolved)
            self.assertFalse(resolved.missing)
            self.assertEqual(len(resolved.paths), 1)
            self.assertTrue(Path(resolved.paths[0]).is_file())

    def test_declared_glob_resolves_multifile(self):
        import tempfile

        pb = self._import_registry()
        with tempfile.TemporaryDirectory() as d:
            project_dir = Path(d)
            src = project_dir / "src"
            src.mkdir()
            (src / "a.rs").write_text("fn a() {}\n", encoding="utf-8")
            (src / "b.rs").write_text("fn b() {}\n", encoding="utf-8")
            self._write_brief(
                project_dir, code_ref_line="    code_ref: src/*.rs\n"
            )
            resolved = pb.resolve_code_ref(
                project_dir, "toy-spec", consumer_root=project_dir
            )
            self.assertIsNotNone(resolved)
            self.assertFalse(resolved.missing)
            self.assertEqual(len(resolved.paths), 2)

    def test_declared_but_missing_activates_without_crash(self):
        import tempfile

        pb = self._import_registry()
        with tempfile.TemporaryDirectory() as d:
            project_dir = Path(d)
            self._write_brief(
                project_dir, code_ref_line="    code_ref: no-such-impl.rs\n"
            )
            resolved = pb.resolve_code_ref(
                project_dir, "toy-spec", consumer_root=project_dir
            )
            self.assertIsNotNone(
                resolved,
                "declared-but-missing code_ref must ACTIVATE (not None)",
            )
            self.assertTrue(resolved.missing)
            self.assertEqual(resolved.paths, [])

    def test_no_matching_slug_is_inactive_none(self):
        import tempfile

        pb = self._import_registry()
        with tempfile.TemporaryDirectory() as d:
            project_dir = Path(d)
            self._write_brief(
                project_dir, code_ref_line="    code_ref: impl.rs\n"
            )
            resolved = pb.resolve_code_ref(
                project_dir, "not-a-slug", consumer_root=project_dir
            )
            self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
