"""Tests for ``anvil/lib/hyperlink_resolver.py`` (issue #335; promoted under #460).

Moved from ``tests/skills/memo/test_hyperlink_resolver.py`` when the
module was promoted from the memo skill-local lib to ``anvil/lib/``
(``anvil:essay`` is the second consumer per the CLAUDE.md "wait for the
second consumer" rule). The memo import path keeps working through the
back-compat shim at ``anvil/skills/memo/lib/hyperlink_resolver.py`` —
see ``TestPromotionShim`` below.

Covers the acceptance criteria documented on issue #335:

1. Fixture memo with intact cross-thread refs → no findings.
2. Fixture memo with broken cross-thread ref (target version missing) →
   blocker finding + ``critical_broken_cross_thread_anchor``.
3. Fixture memo with broken markdown internal link (relative path
   doesn't exist) → important (major) finding.
4. Fixture memo with markdown external link, ``--check-external`` OFF →
   critic completes without network access; link not validated.
5. Fixture memo with markdown external link, ``--check-external`` ON
   with mocked ``curl -I`` → 404 produces important (major) finding;
   200 produces no finding.
6. Wiki-link ``[[unknown-doc]]`` → important (major) finding referencing
   BRIEF.md.
7. Auto-discovery: critic sibling dir ``<thread>.{N}.hyperlinks/`` is
   recognized by ``anvil/lib/critics.py::aggregate`` without code changes.

Per the #58 packaging convention, this filename
(``test_hyperlink_resolver.py``) is unique across the test tree.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


# Repo-root sys.path injection (this file is two levels deep).
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from anvil.lib.critics import (  # noqa: E402
    aggregate,
    discover_critics,
    load_review,
)
from anvil.lib.review_schema import (  # noqa: E402
    Kind,
    Verdict,
)
from anvil.lib.hyperlink_resolver import (  # noqa: E402
    CLASS_CROSS_THREAD,
    CLASS_MARKDOWN_EXTERNAL,
    CLASS_MARKDOWN_INTERNAL,
    CLASS_WIKI_LINK,
    CRITIC_ID,
    CRITICAL_BROKEN_CROSS_THREAD_ANCHOR,
    DIM_HYPERLINKS,
    HYPERLINKS_SUFFIX,
    HyperlinkResolverResult,
    main,
    resolve_hyperlinks,
    write_review_dir,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_project(tmpdir: Path, *, with_brief: bool = True) -> Path:
    """Build a minimal project layout: ``<project>/<thread>/<thread>.{N}/``.

    Returns the version_dir path. The thread slug is ``primary-memo``;
    the sibling thread (for cross-thread refs) is ``secondary-memo``.
    """
    project = tmpdir / "project"
    project.mkdir()
    if with_brief:
        (project / "BRIEF.md").write_text(
            "---\n"
            "project: test-project\n"
            "documents:\n"
            "  - slug: primary-memo\n"
            "    artifact_type: investment-memo\n"
            "  - slug: secondary-memo\n"
            "    artifact_type: investment-memo\n"
            "  - slug: known-doc\n"
            "    artifact_type: investment-memo\n"
            "---\n"
            "\n# Project context\n",
            encoding="utf-8",
        )
    primary = project / "primary-memo"
    primary.mkdir()
    primary_v1 = primary / "primary-memo.1"
    primary_v1.mkdir()
    return primary_v1


def _make_sibling_thread(version_dir: Path, sibling_slug: str, version: int) -> Path:
    """Create a sibling-thread version dir for cross-thread refs to resolve."""
    portfolio = version_dir.parent.parent  # <project>/
    sibling = portfolio / sibling_slug
    sibling.mkdir(exist_ok=True)
    sibling_v = sibling / f"{sibling_slug}.{version}"
    sibling_v.mkdir()
    (sibling_v / f"{sibling_slug}.md").write_text(
        "# Sibling body\n", encoding="utf-8"
    )
    return sibling_v


def _write_body(version_dir: Path, text: str) -> Path:
    """Write the memo body file (slug-echo per #295)."""
    body = version_dir / f"{version_dir.parent.name}.md"
    body.write_text(text, encoding="utf-8")
    return body


# ---------------------------------------------------------------------------
# AC1: Intact cross-thread refs → no findings
# ---------------------------------------------------------------------------


class TestIntactCrossThreadRefs(unittest.TestCase):
    def test_intact_cross_thread_ref_produces_no_findings(self):
        """Memo with a resolvable cross-thread ref produces zero findings."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _make_sibling_thread(version_dir, "secondary-memo", 2)
            _write_body(
                version_dir,
                "# Primary memo\n\n"
                "We rely on [[../secondary-memo/secondary-memo.2]] for the "
                "market sizing analysis.\n",
            )
            result = resolve_hyperlinks(version_dir)
            self.assertTrue(result.passed())
            # Every finding (we record the recognized cross-thread ref as
            # resolved=True with no severity) is non-broken.
            self.assertEqual(
                [f for f in result.findings if not f.resolved], []
            )
            self.assertEqual(result.critical_cross_thread_count, 0)
            self.assertEqual(result.to_critical_flags(), [])

    def test_no_links_at_all_is_clean(self):
        """A memo with no link expressions produces an empty findings list."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(version_dir, "# Primary memo\n\nPlain prose only.\n")
            result = resolve_hyperlinks(version_dir)
            self.assertTrue(result.passed())
            self.assertEqual(result.findings, [])


# ---------------------------------------------------------------------------
# AC2: Broken cross-thread ref → blocker + critical flag
# ---------------------------------------------------------------------------


class TestBrokenCrossThreadRef(unittest.TestCase):
    def test_missing_version_emits_blocker_and_critical_flag(self):
        """Cross-thread ref to a non-existent version raises the critical flag."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            # NOTE: We create v1 of secondary-memo but the memo cites v99.
            _make_sibling_thread(version_dir, "secondary-memo", 1)
            _write_body(
                version_dir,
                "# Primary memo\n\n"
                "See [[../secondary-memo/secondary-memo.99]] for the chart.\n",
            )
            result = resolve_hyperlinks(version_dir)
            self.assertFalse(result.passed())
            broken = [f for f in result.findings if not f.resolved]
            self.assertEqual(len(broken), 1)
            self.assertEqual(broken[0].link_class, CLASS_CROSS_THREAD)
            self.assertEqual(broken[0].severity, "blocker")
            self.assertIn("version", broken[0].reason or "")
            # Critical flag fires.
            self.assertEqual(result.critical_cross_thread_count, 1)
            flags = result.to_critical_flags()
            self.assertEqual(len(flags), 1)
            self.assertEqual(flags[0].type, CRITICAL_BROKEN_CROSS_THREAD_ANCHOR)

    def test_missing_sibling_thread_dir_emits_critical_flag(self):
        """Cross-thread ref to a non-existent sibling thread also raises the flag."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            # No sibling thread created at all.
            _write_body(
                version_dir,
                "# Primary memo\n\n"
                "See [[../missing-slug/missing-slug.1]] for the chart.\n",
            )
            result = resolve_hyperlinks(version_dir)
            self.assertFalse(result.passed())
            self.assertEqual(result.critical_cross_thread_count, 1)
            flags = result.to_critical_flags()
            self.assertEqual(len(flags), 1)
            self.assertIn("thread not found", flags[0].justification)


# ---------------------------------------------------------------------------
# AC3: Broken markdown internal link → major finding
# ---------------------------------------------------------------------------


class TestBrokenMarkdownInternal(unittest.TestCase):
    def test_missing_relative_path_emits_major_finding(self):
        """Markdown internal link to a missing file emits a major finding."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\n"
                "See [the chart](exhibits/fig-1.png) for details.\n",
            )
            result = resolve_hyperlinks(version_dir)
            self.assertFalse(result.passed())
            broken = [f for f in result.findings if not f.resolved]
            self.assertEqual(len(broken), 1)
            self.assertEqual(broken[0].link_class, CLASS_MARKDOWN_INTERNAL)
            self.assertEqual(broken[0].severity, "major")
            self.assertEqual(broken[0].reason, "file not found")
            # No cross-thread critical flag.
            self.assertEqual(result.critical_cross_thread_count, 0)

    def test_present_relative_path_resolves(self):
        """Markdown internal link to an existing file produces no finding."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            exhibits = version_dir / "exhibits"
            exhibits.mkdir()
            (exhibits / "fig-1.png").write_bytes(b"\x89PNG\r\n")
            _write_body(
                version_dir,
                "# Primary memo\n\n"
                "See [the chart](exhibits/fig-1.png) for details.\n",
            )
            result = resolve_hyperlinks(version_dir)
            self.assertTrue(result.passed())

    def test_anchor_fragment_is_stripped_for_existence_check(self):
        """``[text](file.md#section)`` resolves on file existence; anchor ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            (version_dir / "appendix.md").write_text("# Stub\n", encoding="utf-8")
            _write_body(
                version_dir,
                "# Primary memo\n\nSee [appendix](appendix.md#methodology).\n",
            )
            result = resolve_hyperlinks(version_dir)
            self.assertTrue(result.passed())


# ---------------------------------------------------------------------------
# AC4: External link, --check-external OFF → no network, no validation
# ---------------------------------------------------------------------------


class TestExternalCheckOff(unittest.TestCase):
    def test_external_link_not_probed_by_default(self):
        """With check_external=False, external links are recorded but not probed."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\n"
                "See [the SEC filing](https://www.sec.gov/edgar/example) "
                "for details.\n",
            )
            # Sentinel: monkey-patch subprocess.run so it raises if called.
            with mock.patch(
                "anvil.lib.hyperlink_resolver.subprocess.run",
                side_effect=AssertionError(
                    "subprocess.run must NOT be called with check_external=False"
                ),
            ):
                result = resolve_hyperlinks(version_dir, check_external=False)
            self.assertTrue(result.passed())
            ext = [f for f in result.findings if f.link_class == CLASS_MARKDOWN_EXTERNAL]
            self.assertEqual(len(ext), 1)
            self.assertTrue(ext[0].resolved)
            self.assertIn("external probe disabled", ext[0].reason or "")


# ---------------------------------------------------------------------------
# AC5: External link, --check-external ON with mocked curl
# ---------------------------------------------------------------------------


def _fake_curl_factory(http_code: int):
    """Build a ``subprocess.run`` replacement that mocks ``curl -I``.

    Returns a ``subprocess.CompletedProcess`` with ``stdout=<code>``.
    The mock validates the command shape so a test failure surfaces if
    the resolver invokes curl with unexpected arguments.
    """

    def _fake_run(cmd, *args, **kwargs):
        # The resolver invokes:
        # ['curl', '-I', '-s', '-o', '/dev/null', '-w', '%{http_code}',
        #  '--max-time', '<int>', '<url>']
        assert cmd[0] == "curl", f"expected curl invocation, got {cmd!r}"
        assert "-I" in cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=str(http_code),
            stderr="",
        )

    return _fake_run


class TestExternalCheckOn(unittest.TestCase):
    def test_external_200_produces_no_finding(self):
        """HTTP 200 → resolved=True, no finding."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\nSee [source](https://example.com/ok).\n",
            )
            with mock.patch(
                "anvil.lib.hyperlink_resolver.subprocess.run",
                side_effect=_fake_curl_factory(200),
            ):
                result = resolve_hyperlinks(version_dir, check_external=True)
            self.assertTrue(result.passed())

    def test_external_404_produces_major_finding(self):
        """HTTP 404 → major finding."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\nSee [missing](https://example.com/gone).\n",
            )
            with mock.patch(
                "anvil.lib.hyperlink_resolver.subprocess.run",
                side_effect=_fake_curl_factory(404),
            ):
                result = resolve_hyperlinks(version_dir, check_external=True)
            self.assertFalse(result.passed())
            broken = [f for f in result.findings if not f.resolved]
            self.assertEqual(len(broken), 1)
            self.assertEqual(broken[0].link_class, CLASS_MARKDOWN_EXTERNAL)
            self.assertEqual(broken[0].severity, "major")
            self.assertEqual(broken[0].reason, "HTTP 404")

    def test_external_500_produces_major_finding(self):
        """HTTP 500 → major finding (5xx tier)."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\nSee [oops](https://example.com/err).\n",
            )
            with mock.patch(
                "anvil.lib.hyperlink_resolver.subprocess.run",
                side_effect=_fake_curl_factory(500),
            ):
                result = resolve_hyperlinks(version_dir, check_external=True)
            self.assertFalse(result.passed())
            broken = [f for f in result.findings if not f.resolved]
            self.assertEqual(broken[0].reason, "HTTP 500")

    def test_curl_missing_graceful_degrade(self):
        """When curl is absent from PATH, external links are recorded as unverified."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\nSee [src](https://example.com/x).\n",
            )
            with mock.patch(
                "anvil.lib.hyperlink_resolver.shutil.which",
                return_value=None,
            ):
                result = resolve_hyperlinks(version_dir, check_external=True)
            # No finding fires (we can't prove it broken without curl).
            self.assertTrue(result.passed())
            self.assertTrue(
                any("curl not on PATH" in r for r in result.reasons),
                f"expected graceful-degrade reason; got reasons={result.reasons}",
            )


# ---------------------------------------------------------------------------
# AC6: Wiki-link [[unknown-doc]] → major finding referencing BRIEF.md
# ---------------------------------------------------------------------------


class TestWikiLink(unittest.TestCase):
    def test_known_doc_resolves(self):
        """``[[known-doc]]`` resolves when listed in BRIEF.md documents:."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\nSee [[known-doc]] for context.\n",
            )
            result = resolve_hyperlinks(version_dir)
            self.assertTrue(result.passed())

    def test_unknown_doc_emits_major_finding(self):
        """``[[unknown-doc]]`` not in BRIEF.md documents: emits a major finding."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\nSee [[unknown-doc]] for context.\n",
            )
            result = resolve_hyperlinks(version_dir)
            self.assertFalse(result.passed())
            broken = [f for f in result.findings if not f.resolved]
            self.assertEqual(len(broken), 1)
            self.assertEqual(broken[0].link_class, CLASS_WIKI_LINK)
            self.assertEqual(broken[0].severity, "major")
            self.assertEqual(broken[0].reason, "unknown document")

    def test_missing_brief_reports_brief_not_found(self):
        """No BRIEF.md → wiki-link reason is 'BRIEF.md not found'."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp), with_brief=False)
            _write_body(
                version_dir,
                "# Primary memo\n\nSee [[any-doc]] for context.\n",
            )
            result = resolve_hyperlinks(version_dir)
            self.assertFalse(result.passed())
            broken = [f for f in result.findings if not f.resolved]
            self.assertEqual(broken[0].reason, "BRIEF.md not found")


# ---------------------------------------------------------------------------
# AC7: Auto-discovery via critics.aggregate
# ---------------------------------------------------------------------------


class TestAutoDiscovery(unittest.TestCase):
    def test_critic_sibling_dir_is_discovered_by_aggregate(self):
        """``<version_dir>.hyperlinks/`` is picked up by ``discover_critics``."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _make_sibling_thread(version_dir, "secondary-memo", 1)
            _write_body(
                version_dir,
                "# Primary memo\n\n"
                "See [[../secondary-memo/secondary-memo.99]] for the chart.\n",
            )
            result = resolve_hyperlinks(version_dir)
            review_path = write_review_dir(version_dir, result)
            self.assertTrue(review_path.exists())
            self.assertTrue(
                review_path.parent.name.endswith(f".{HYPERLINKS_SUFFIX}"),
                f"sibling dir name {review_path.parent.name!r} should end with "
                f".{HYPERLINKS_SUFFIX}",
            )
            # discover_critics finds it.
            critic_dirs = discover_critics(version_dir)
            self.assertEqual(len(critic_dirs), 1)
            self.assertEqual(critic_dirs[0], review_path.parent)
            # load_review parses it as a TOOL_EVIDENCE review.
            review = load_review(critic_dirs[0])
            self.assertEqual(review.kind, Kind.TOOL_EVIDENCE)
            self.assertEqual(review.critic_id, CRITIC_ID)
            # Aggregator merges the findings + critical flag.
            agg = aggregate([review])
            self.assertEqual(agg.verdict, Verdict.BLOCK)
            self.assertEqual(len(agg.critical_flags), 1)
            self.assertEqual(
                agg.critical_flags[0].type,
                CRITICAL_BROKEN_CROSS_THREAD_ANCHOR,
            )


# ---------------------------------------------------------------------------
# Schema compliance — review_schema.py contract
# ---------------------------------------------------------------------------


class TestReviewSchemaCompliance(unittest.TestCase):
    def test_review_validates_against_canonical_schema(self):
        """Emitted Review parses cleanly via ``Review.model_validate``."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\n[missing](exhibits/missing.png)\n",
            )
            result = resolve_hyperlinks(version_dir)
            review = result.to_review(version_dir=version_dir.name)
            # Schema requires kind=tool_evidence with tool_calls on every finding.
            self.assertEqual(review.kind, Kind.TOOL_EVIDENCE)
            for f in review.findings:
                self.assertIsNotNone(f.tool_calls)
                self.assertEqual(f.tool_calls, [])
            # Round-trip via JSON.
            payload = review.model_dump(mode="json")
            re_parsed = type(review).model_validate(payload)
            self.assertEqual(re_parsed.kind, Kind.TOOL_EVIDENCE)
            self.assertEqual(re_parsed.critic_id, CRITIC_ID)

    def test_finding_dimension_is_hyperlinks(self):
        """Every emitted Finding has ``dimension=hyperlinks``."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\n[missing](exhibits/missing.png)\n",
            )
            result = resolve_hyperlinks(version_dir)
            review = result.to_review(version_dir=version_dir.name)
            self.assertGreater(len(review.findings), 0)
            for f in review.findings:
                self.assertEqual(f.dimension, DIM_HYPERLINKS)

    def test_no_suggested_fix_uses_action_or_target_anchor_field(self):
        """Schema discipline: no schema delta. ``Finding.fix`` / ``suggested_fix``
        carries free-form text; no ``action`` / ``target_anchor`` /
        ``proposed_content`` field exists on the model."""
        from anvil.lib.review_schema import Finding

        # The Finding model must NOT carry the deferred-experiment fields
        # (Epic #328 reframed kickoff explicitly deferred them).
        forbidden_fields = {"action", "target_anchor", "proposed_content"}
        present = set(Finding.model_fields.keys())
        self.assertEqual(
            forbidden_fields & present,
            set(),
            f"Phase 2 was settled with no schema delta; Finding model "
            f"should not carry {forbidden_fields & present}",
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


class TestCLI(unittest.TestCase):
    def test_cli_clean_pass_exits_zero(self):
        """CLI exit code is 0 when every link resolves."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(version_dir, "# Primary memo\n\nPlain prose.\n")
            rc = main([str(version_dir)])
            self.assertEqual(rc, 0)

    def test_cli_broken_link_exits_one(self):
        """CLI exit code is 1 when any link fails."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\n[missing](exhibits/missing.png)\n",
            )
            rc = main([str(version_dir)])
            self.assertEqual(rc, 1)

    def test_cli_missing_version_dir_exits_two(self):
        """CLI exit code is 2 when the version dir does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            rc = main([str(missing)])
            self.assertEqual(rc, 2)

    def test_cli_write_review_creates_sibling_dir(self):
        """``--write-review`` produces ``<version_dir>.hyperlinks/_review.json``."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(version_dir, "# Primary memo\n\nPlain prose.\n")
            rc = main([str(version_dir), "--write-review"])
            self.assertEqual(rc, 0)
            sibling = (
                version_dir.parent
                / f"{version_dir.name}.{HYPERLINKS_SUFFIX}"
            )
            self.assertTrue(sibling.is_dir())
            self.assertTrue((sibling / "_review.json").is_file())
            # JSON parses and is a tool_evidence review.
            payload = json.loads((sibling / "_review.json").read_text())
            self.assertEqual(payload["kind"], "tool_evidence")
            self.assertEqual(payload["critic_id"], CRITIC_ID)


# ---------------------------------------------------------------------------
# Doc-coverage: memo-hyperlinks command shipped
# ---------------------------------------------------------------------------


class TestCommandDocShipped(unittest.TestCase):
    def test_command_doc_exists(self):
        """``anvil/skills/memo/commands/memo-hyperlinks.md`` exists."""
        cmd = (
            _REPO_ROOT
            / "anvil"
            / "skills"
            / "memo"
            / "commands"
            / "memo-hyperlinks.md"
        )
        self.assertTrue(cmd.is_file(), f"expected command doc at {cmd}")

    def test_command_doc_has_frontmatter(self):
        """The command doc has the standard YAML frontmatter."""
        cmd = (
            _REPO_ROOT
            / "anvil"
            / "skills"
            / "memo"
            / "commands"
            / "memo-hyperlinks.md"
        )
        body = cmd.read_text(encoding="utf-8")
        self.assertTrue(
            body.startswith("---\n"),
            "command doc should begin with --- YAML frontmatter",
        )
        self.assertIn("name: memo-hyperlinks", body)
        self.assertIn("description:", body)

    def test_command_doc_references_check_external_flag(self):
        """The command doc documents the off-by-default ``--check-external`` flag."""
        cmd = (
            _REPO_ROOT
            / "anvil"
            / "skills"
            / "memo"
            / "commands"
            / "memo-hyperlinks.md"
        )
        body = cmd.read_text(encoding="utf-8")
        self.assertIn("--check-external", body)
        self.assertIn("off by default", body.lower())

    def test_command_doc_references_critical_flag(self):
        """The command doc names the critical_broken_cross_thread_anchor flag."""
        cmd = (
            _REPO_ROOT
            / "anvil"
            / "skills"
            / "memo"
            / "commands"
            / "memo-hyperlinks.md"
        )
        body = cmd.read_text(encoding="utf-8")
        self.assertIn(CRITICAL_BROKEN_CROSS_THREAD_ANCHOR, body)

    def test_command_doc_references_output_dir_convention(self):
        """The command doc names the .hyperlinks/ sibling-dir convention."""
        cmd = (
            _REPO_ROOT
            / "anvil"
            / "skills"
            / "memo"
            / "commands"
            / "memo-hyperlinks.md"
        )
        body = cmd.read_text(encoding="utf-8")
        self.assertIn(".hyperlinks", body)


# ---------------------------------------------------------------------------
# Promotion shim (issue #460): memo path keeps working, same objects
# ---------------------------------------------------------------------------


class TestPromotionShim(unittest.TestCase):
    def test_memo_shim_reexports_canonical_objects(self):
        """``anvil.skills.memo.lib.hyperlink_resolver`` re-exports the
        canonical ``anvil.lib.hyperlink_resolver`` objects (identity, not
        copies) per the #382/#393 promotion-shim pattern."""
        import anvil.lib.hyperlink_resolver as canonical
        import anvil.skills.memo.lib.hyperlink_resolver as shim

        for name in (
            "resolve_hyperlinks",
            "write_review_dir",
            "main",
            "HyperlinkFinding",
            "HyperlinkResolverResult",
        ):
            self.assertIs(
                getattr(shim, name),
                getattr(canonical, name),
                f"shim attribute {name!r} is not the canonical object",
            )
        self.assertEqual(shim.CRITIC_ID, canonical.CRITIC_ID)
        self.assertEqual(
            shim.CRITICAL_BROKEN_CROSS_THREAD_ANCHOR,
            canonical.CRITICAL_BROKEN_CROSS_THREAD_ANCHOR,
        )
        self.assertEqual(shim.HYPERLINKS_SUFFIX, canonical.HYPERLINKS_SUFFIX)

    def test_memo_shim_behavioral_smoke(self):
        """The shim import path resolves links end-to-end (a representative
        behavioral check through the historical import path)."""
        from anvil.skills.memo.lib.hyperlink_resolver import (
            resolve_hyperlinks as shim_resolve,
        )

        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_project(Path(tmp))
            _write_body(
                version_dir,
                "# Primary memo\n\n[missing](exhibits/missing.png)\n",
            )
            result = shim_resolve(version_dir)
            self.assertFalse(result.passed())


if __name__ == "__main__":
    unittest.main()
