r"""Doc-coverage guard for the paper-review multi-file ``\input``/``\include``
resolution wiring (issue #643).

``paper`` is the one anvil skill explicitly designed for multi-file LaTeX
papers — a master ``main.tex`` that ``\input{sections/...}``s many section
files is a normal whitepaper shape. Historically ``paper-review.md`` step 4
told the reviewer to "load ``main.tex``" with no instruction to follow
``\input``/``\include``, so a reviewer obeying the literal step scored a
near-empty ~90-line shell against the /44 rubric and silently missed the
paper body.

This module pins the prose contract that step 4 (content read), step 4b
(render-gate ``source_paths``), and step 5/5b (quoted-evidence check) now
resolve the ``\input``/``\include`` tree via
``anvil/lib/tex_includes.py::resolve_tex_inputs`` — and that the resolver
module itself ships with the required behavior (extension defaulting,
nested walk, comment masking, cycle guard, missing-file surfacing).

Per the per-skill test filename convention (#58), this file is named
``test_paper_review_tex_includes_doc.py`` to avoid collision with the other
``test_paper_review_*_doc.py`` guards.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PUB_REVIEW_DOC = (
    REPO_ROOT / "anvil" / "skills" / "paper" / "commands" / "paper-review.md"
)
PUB_AUDIT_DOC = (
    REPO_ROOT / "anvil" / "skills" / "paper" / "commands" / "paper-audit.md"
)
RESOLVER_MODULE = REPO_ROOT / "anvil" / "lib" / "tex_includes.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The resolver module ships and exports the primitive
# ---------------------------------------------------------------------------


def test_resolver_module_exists():
    """Issue #643: the ``\\input``/``\\include`` resolver ships in lib."""
    assert RESOLVER_MODULE.is_file(), (
        "anvil/lib/tex_includes.py MUST exist — the multi-file LaTeX "
        "resolver primitive (issue #643)"
    )


def test_resolver_importable_and_behaves():
    """The resolver's public behavior is load-bearing for the doc contract —
    verify it resolves nested ``\\input``, defaults ``.tex``, masks
    comments, surfaces missing files, and does not cycle."""
    import tempfile

    from anvil.lib.tex_includes import resolve_tex_inputs

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "sections").mkdir()
        (root / "sections" / "intro.tex").write_text(
            "Intro body.\n", encoding="utf-8"
        )
        (root / "sections" / "method.tex").write_text(
            "Method body.\n\\input{sections/details}\n", encoding="utf-8"
        )
        (root / "sections" / "details.tex").write_text(
            "Details body.\n", encoding="utf-8"
        )
        (root / "main.tex").write_text(
            "\\input{sections/intro}\n"
            "\\input{sections/method}\n"
            "% \\input{sections/commented-out}\n"
            "\\input{sections/gone}\n",
            encoding="utf-8",
        )
        result = resolve_tex_inputs(root / "main.tex")
        names = [f.name for f in result.files]
        # Nested walk + extension defaulting + document order.
        assert names == ["main.tex", "intro.tex", "method.tex", "details.tex"]
        assert "Details body." in result.body
        # Comment masking — the commented-out include never resolves.
        assert "commented-out.tex" not in names
        # Missing-file target surfaced, not raised.
        assert result.has_missing
        assert any("gone" in t for t, _ in result.missing)


# ---------------------------------------------------------------------------
# paper-review.md step 4 — content read resolves the tree
# ---------------------------------------------------------------------------


def test_step4_names_the_resolver():
    """Issue #643 AC: step 4 explicitly documents recursively resolving
    ``\\input``/``\\include`` and names the resolver that performs it."""
    body = _read(PUB_REVIEW_DOC)
    assert "resolve_tex_inputs" in body, (
        "paper-review.md MUST name the resolver function resolve_tex_inputs "
        "(issue #643 AC — step 4 names the code that resolves the tree)"
    )
    assert "tex_includes" in body, (
        "paper-review.md MUST reference anvil/lib/tex_includes.py (issue #643)"
    )


def test_step4_does_not_regress_to_main_tex_only():
    """Issue #643 AC: step 4 MUST NOT regress to loading only main.tex —
    it documents that the reviewable document is main.tex PLUS children."""
    body = _read(PUB_REVIEW_DOC)
    idx = body.find("**Read inputs**")
    assert idx > -1, "paper-review.md MUST retain a 'Read inputs' step"
    # The step body must document the \input/\include recursion.
    nearby = body[idx : idx + 3000]
    lowered = nearby.lower()
    assert "recursively resolve" in lowered or "recursively-resolved" in lowered, (
        "paper-review.md step 4 MUST document recursively resolving "
        "\\input/\\include children (issue #643 AC)"
    )
    assert "\\input" in nearby and "\\include" in nearby, (
        "paper-review.md step 4 MUST name both \\input and \\include "
        "(issue #643 AC)"
    )


def test_step4_documents_reviewable_document_is_the_tree():
    """Issue #643 AC: the reviewable document is the concatenated tree, not
    the master alone."""
    body = _read(PUB_REVIEW_DOC)
    idx = body.find("**Read inputs**")
    nearby = body[idx : idx + 3000]
    lowered = nearby.lower()
    # The concatenated-body framing (the master PLUS children).
    assert "plus its resolved children" in lowered or "plus its children" in lowered or (
        "main.tex` plus" in lowered
    ) or ("plus its resolved" in lowered), (
        "paper-review.md step 4 MUST frame the reviewable document as "
        "main.tex PLUS its resolved children (issue #643 AC)"
    )


def test_step4_documents_single_file_degradation():
    """Issue #643 AC / test plan: a single-file thread (no \\input) degrades
    to just main.tex — byte-identical to pre-#643."""
    body = _read(PUB_REVIEW_DOC)
    idx = body.find("**Read inputs**")
    nearby = body[idx : idx + 3000]
    lowered = nearby.lower()
    assert "single-file thread" in lowered or "byte-identical" in lowered, (
        "paper-review.md step 4 MUST document the single-file degradation "
        "(no \\input → just main.tex, byte-identical) — issue #643 "
        "regression guard"
    )


def test_step4_documents_missing_include_as_signal():
    """Issue #643 AC: a dangling \\input/\\include is surfaced as reviewer
    signal (a broken document), not a crash."""
    body = _read(PUB_REVIEW_DOC)
    idx = body.find("**Read inputs**")
    nearby = body[idx : idx + 3000]
    lowered = nearby.lower()
    assert "missing" in lowered and "signal" in lowered, (
        "paper-review.md step 4 MUST document dangling \\input as reviewer "
        "signal (a broken document) — issue #643"
    )


# ---------------------------------------------------------------------------
# paper-review.md step 4b — source_paths reuses the resolved list
# ---------------------------------------------------------------------------


def test_step4b_source_paths_uses_resolver():
    """Issue #643 AC: step 4b's source_paths is wired to the SAME resolver —
    no more unimplemented 'plus any \\input/\\include children' prose."""
    body = _read(PUB_REVIEW_DOC)
    idx = body.find("`source_paths`")
    assert idx > -1, "paper-review.md MUST retain the render-gate source_paths input"
    nearby = body[idx : idx + 900]
    assert "ResolvedTex.files" in nearby or "resolve_tex_inputs" in nearby, (
        "paper-review.md step 4b source_paths MUST reuse the resolver's "
        "resolved-file list (ResolvedTex.files), not the bare [main.tex] "
        "placeholder prose (issue #643 AC)"
    )


# ---------------------------------------------------------------------------
# paper-review.md step 5 / 5b — quoted-evidence covers children
# ---------------------------------------------------------------------------


def test_quoted_evidence_covers_input_children():
    """Issue #643 AC: the quoted-evidence rule (step 5) covers quotes drawn
    from \\input-ed children, not just main.tex."""
    body = _read(PUB_REVIEW_DOC)
    idx = body.find("Quoted-evidence requirement")
    assert idx > -1
    nearby = body[idx : idx + 1200]
    assert "resolved body" in nearby.lower(), (
        "paper-review.md step 5 quoted-evidence rule MUST reference the "
        "resolved body (main.tex OR its \\input/\\include children) so a "
        "quote from a section file is valid evidence (issue #643 AC)"
    )


def test_evidence_check_documented_to_expand_tex_body():
    """Issue #643 AC: step 5b's evidence_check self-check is documented to
    check against the resolved body (main.tex + children), preventing false
    fabricated_evidence findings for legitimate child-section quotes."""
    body = _read(PUB_REVIEW_DOC)
    idx = body.find("Validate quoted evidence")
    assert idx > -1
    nearby = body[idx : idx + 2500]
    lowered = nearby.lower()
    assert "resolved body" in lowered, (
        "paper-review.md step 5b MUST document that evidence_check verifies "
        "against the resolved body (issue #643 AC)"
    )
    assert "resolve_tex_inputs" in nearby, (
        "paper-review.md step 5b MUST reference resolve_tex_inputs — the "
        "check_version_dir tex-body expansion (issue #643 AC point 6)"
    )
    assert "fabricated_evidence" in nearby or "fabricated evidence" in lowered, (
        "paper-review.md step 5b MUST explain the false-fabricated_evidence "
        "failure mode the expansion prevents (issue #643 AC point 6)"
    )


# ---------------------------------------------------------------------------
# Frontmatter + Outputs prose updated
# ---------------------------------------------------------------------------


def test_frontmatter_reads_line_reflects_children():
    """Issue #643 AC: the frontmatter Reads line stops implying main.tex is
    the sole content source."""
    body = _read(PUB_REVIEW_DOC)
    reads_idx = body.find("**Reads**")
    assert reads_idx > -1
    reads_line = body[reads_idx : body.find("\n", reads_idx)]
    assert "\\input" in reads_line and "\\include" in reads_line, (
        "paper-review.md frontmatter Reads line MUST reflect that the "
        "reviewable document includes \\input/\\include children (issue "
        "#643 AC)"
    )


def test_outputs_comments_line_reflects_children():
    """Issue #643 AC: the Outputs comments.md line reflects that comments
    key to headings/excerpts across the resolved tree."""
    body = _read(PUB_REVIEW_DOC)
    idx = body.find("comments.md        Line-level comments")
    assert idx > -1, "paper-review.md MUST retain the comments.md output line"
    nearby = body[idx : idx + 250]
    assert "\\input" in nearby or "children" in nearby, (
        "paper-review.md Outputs comments.md line MUST reflect that comments "
        "can key to \\input/\\include children (issue #643 AC)"
    )


# ---------------------------------------------------------------------------
# paper-audit.md sibling doc fix (guidance point 7)
# ---------------------------------------------------------------------------


def test_paper_audit_cite_enumeration_covers_children():
    """Issue #643 guidance 7: paper-audit's \\cite enumeration + claim
    inventory (LLM-driven passes over main.tex text) cover \\input children
    too — the pdflatex compile pulls them in, but the text-level passes
    historically read only main.tex."""
    body = _read(PUB_AUDIT_DOC)
    assert "resolve_tex_inputs" in body, (
        "paper-audit.md MUST reference resolve_tex_inputs so its cite "
        "enumeration + claim inventory cover \\input/\\include children "
        "(issue #643 guidance point 7)"
    )
