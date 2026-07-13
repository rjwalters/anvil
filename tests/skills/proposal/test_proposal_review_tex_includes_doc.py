r"""Doc-coverage guard for the proposal-review multi-file
``\input``/``\include`` resolution wiring (issue #653, follow-up to #643).

The proposal skill ships a first-class ``\input{figures/<name>.tex}``
TikZ-standalone figure convention (``proposal-figures.md`` — topology /
system diagrams inlined at build time). Historically ``proposal-review.md``
step 4 told the reviewer to "load ``proposal.tex``" with no instruction to
follow ``\input``/``\include``, and its render-gate ``extra_source_paths``
note called the convention a hypothetical "consumer override" ("none in the
default skeleton, but consumer overrides may add them"). A reviewer obeying
the literal step scored the master shell and silently missed inline TikZ
figure content — the same class of bug PR #654 fixed for ``pub``.

This module pins the prose contract that step 4 (content read) and step 4b
(render-gate ``extra_source_paths``) now resolve the ``\input``/``\include``
tree via ``anvil/lib/tex_includes.py::resolve_tex_inputs``, mirroring the
``pub-review.md`` pattern, and that the "hypothetical consumer override"
framing is gone.

Per the per-skill test filename convention (#58), this file is named
``test_proposal_review_tex_includes_doc.py`` to avoid collision.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_DOC = (
    REPO_ROOT
    / "anvil"
    / "skills"
    / "proposal"
    / "commands"
    / "proposal-review.md"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_step4_names_the_resolver() -> None:
    r"""Issue #653: step 4 explicitly documents recursively resolving
    ``\input``/``\include`` and names the resolver that performs it."""
    body = _read(REVIEW_DOC)
    assert "resolve_tex_inputs" in body, (
        "proposal-review.md MUST name the resolver function resolve_tex_inputs "
        "(issue #653 — step 4 resolves the \\input tree)"
    )
    assert "tex_includes" in body, (
        "proposal-review.md MUST reference anvil/lib/tex_includes.py"
    )


def test_step4_does_not_regress_to_single_file_only() -> None:
    r"""Issue #653: step 4 documents the reviewable document is
    ``proposal.tex`` PLUS its ``\input``/``\include`` children."""
    body = _read(REVIEW_DOC)
    idx = body.find("**Read inputs**")
    assert idx > -1, "proposal-review.md MUST retain a 'Read inputs' step"
    nearby = body[idx : idx + 3000]
    lowered = nearby.lower()
    assert "recursively resolve" in lowered, (
        "proposal-review.md step 4 MUST document recursively resolving "
        "\\input/\\include children (issue #653)"
    )
    assert "\\input" in nearby and "\\include" in nearby, (
        "proposal-review.md step 4 MUST name both \\input and \\include"
    )
    assert "plus its resolved children" in lowered or (
        "proposal.tex` plus" in lowered
    ), (
        "proposal-review.md step 4 MUST frame the reviewable document as "
        "proposal.tex PLUS its resolved children (issue #653)"
    )


def test_step4_documents_single_file_degradation() -> None:
    r"""Issue #653: a single-file thread (no ``\input``) degrades to just
    ``proposal.tex`` — byte-identical to pre-#643."""
    body = _read(REVIEW_DOC)
    idx = body.find("**Read inputs**")
    nearby = body[idx : idx + 3000]
    lowered = nearby.lower()
    assert "single-file thread" in lowered or "byte-identical" in lowered, (
        "proposal-review.md step 4 MUST document the single-file degradation "
        "(byte-identical to pre-#643) — regression guard"
    )


def test_step4_documents_missing_include_as_signal() -> None:
    r"""Issue #653: a dangling ``\input``/``\include`` is surfaced as reviewer
    signal (a broken document), not a crash."""
    body = _read(REVIEW_DOC)
    idx = body.find("**Read inputs**")
    nearby = body[idx : idx + 3000]
    lowered = nearby.lower()
    assert "missing" in lowered and "signal" in lowered, (
        "proposal-review.md step 4 MUST document dangling \\input as reviewer "
        "signal (issue #653)"
    )


def test_step4b_extra_source_paths_uses_resolver() -> None:
    r"""Issue #653: step 4b's ``extra_source_paths`` is wired to the SAME
    resolver — the old 'none in the default skeleton, but consumer overrides
    may add them' hypothetical framing is gone."""
    body = _read(REVIEW_DOC)
    idx = body.find("`extra_source_paths`")
    assert idx > -1, (
        "proposal-review.md MUST retain the render-gate extra_source_paths"
    )
    nearby = body[idx : idx + 900]
    assert "ResolvedTex.files" in nearby or "resolve_tex_inputs" in nearby, (
        "proposal-review.md step 4b extra_source_paths MUST reuse the "
        "resolver's resolved-file list (issue #653)"
    )
    assert "none in the default skeleton, but consumer overrides may add them" not in body, (
        "proposal-review.md MUST drop the 'hypothetical consumer override' "
        "framing — the \\input{figures/<name>.tex} TikZ convention is real "
        "(issue #653)"
    )


def test_step4_names_the_tikz_input_convention() -> None:
    r"""Issue #653: the doc grounds the wiring in proposal's real first-class
    ``\input{figures/<name>.tex}`` TikZ convention."""
    body = _read(REVIEW_DOC)
    assert "figures/<name>.tex" in body, (
        "proposal-review.md MUST cite the \\input{figures/<name>.tex} "
        "TikZ-standalone convention as the reason for wiring the resolver "
        "(issue #653)"
    )
    assert "proposal-figures.md" in body, (
        "proposal-review.md MUST cross-reference proposal-figures.md as the "
        "source of the \\input figure convention (issue #653)"
    )


def test_step5_quoted_evidence_covers_input_children() -> None:
    r"""Issue #653: the quoted-evidence rule (step 5) covers quotes drawn from
    ``\input``-ed children. The literal 'verbatim quote from `proposal.tex`'
    phrase is retained for the #475 rollout guard."""
    body = _read(REVIEW_DOC)
    assert "verbatim quote from `proposal.tex`" in body
    idx = body.find("Quoted-evidence requirement")
    assert idx > -1
    nearby = body[idx : idx + 1400]
    assert "\\input" in nearby and "\\include" in nearby, (
        "proposal-review.md step 5 quote rule MUST note \\input/\\include "
        "children are valid evidence sources (issue #653)"
    )


def test_step5b_evidence_check_documents_resolved_body() -> None:
    r"""Issue #653: step 5b's evidence_check self-check checks against the
    resolved body (``proposal.tex`` + children) via ``resolve_tex_inputs``,
    preventing false ``fabricated_evidence`` findings for child quotes."""
    body = _read(REVIEW_DOC)
    idx = body.find("Validate quoted evidence")
    assert idx > -1
    nearby = body[idx : idx + 2500]
    lowered = nearby.lower()
    assert "resolved body" in lowered, (
        "proposal-review.md step 5b MUST document evidence_check verifying "
        "against the resolved body (issue #653)"
    )
    assert "resolve_tex_inputs" in nearby, (
        "proposal-review.md step 5b MUST reference resolve_tex_inputs "
        "(issue #653)"
    )
    assert "fabricated_evidence" in nearby, (
        "proposal-review.md step 5b MUST explain the false-fabricated_evidence "
        "failure mode the expansion prevents (issue #653)"
    )
