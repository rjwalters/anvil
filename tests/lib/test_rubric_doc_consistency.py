"""Cross-file rubric-threshold consistency lint (issue #618).

Every artifact-class skill ships a canonical ``rubric.md`` that declares the
scoring total and the advance threshold as the single source of truth
(e.g. ``summing to **44**`` and ``The threshold to advance is **≥39/44**``).
The same ``≥NN/MM`` fact is then restated as prose in the skill's
``SKILL.md`` (the documented entry point) and across its ``commands/*.md``
(reviewer ``Thresholds:`` lines, score examples, ``advance_threshold`` stamp
values). That restatement is hand-synced.

## Why this lint exists (rubric-denominator migration history)

The denominator has now moved three times, and each migration is prose-only:

* **v0.4.0 (#346)** — ``/40 → /44`` (added dim 9 *Rhetorical economy*).
  The migration updated ``deck/rubric.md`` but left ``deck/SKILL.md``
  asserting the pre-migration ``≥35/40``. The self-contradiction shipped in
  the release itself and a downstream canary (2AM Logic Studio) nearly wired
  the wrong convergence bar into a live thread's review loop before catching
  it by cross-reading the sibling ``rubric.md``.
* **#357** — ``deck`` threshold re-proportioned ``≥35/40 → ≥39/44``.
* **#550** — ``deck`` migrated ``/44 → /49`` (added dim 10), threshold
  ``≥39/44 → ≥43/49``.

This test is the mechanical guard the canary asked for: it fails the build
if any ``SKILL.md`` or ``commands/*.md`` restates a threshold that disagrees
with its own ``rubric.md`` — either a **stale denominator** left over from a
prior migration or a **wrong threshold numerator** under the current
denominator. It is a pure static read (no subprocess, no LLM) and is
parameterized per skill so a single skill's drift is reported in isolation.

## What is deliberately NOT a violation

* **Comparative cross-references.** A doc may legitimately cite another
  skill's tier for contrast (e.g. ``report`` notes its ``≥39/44`` is "higher
  than the ≥35/44 used by ``anvil:memo``"). Such a line also carries the
  skill's own canonical ``≥thr/total`` string, so any line containing the
  canonical value is skipped wholesale — the comparison is anchored by the
  correct value being present.
* **Per-dimension score references.** Revise guidance says things like "keep
  it at ≥5/6" or "≥6/7" — these match ``≥NN/MM`` shape but the denominator is
  a per-dimension max, not a rubric total. Only denominators that are actual
  rubric totals (current totals plus the historical ``40``) are treated as
  threshold claims.
* **Rubric-version-transition boilerplate.** The ``*-review.md`` transition
  prose cites prior rubrics in the reversed ``(/40, ≥32)`` form, which does
  not match the ``≥NN/MM`` shape and so is never picked up.

Note ``rubric.md`` itself is intentionally NOT scanned: its first paragraph
is the source of truth and its later paragraphs carry migration history
(``pre-#357 was ≥35/40 …``) by design. ``anvil/lib/snippets/`` is likewise
out of scope — those files mix denominators across skills on purpose.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


SKILLS_DIR = Path(__file__).resolve().parents[2] / "anvil" / "skills"

# ``≥NN/MM`` — the shape both rubric.md and its sibling docs use for a
# threshold declaration.
_THRESHOLD_RE = re.compile(r"≥(\d+)/(\d+)")
_TOTAL_RE = re.compile(r"summing to \*\*(\d+)\*\*")

# Denominators from prior rubric generations that must never resurface as a
# current threshold claim. Union'd with every skill's live total (computed at
# import time) to form the set of values that count as a *rubric* denominator
# — everything else (``≥5/6`` per-dimension floors, etc.) is ignored.
_HISTORICAL_DENOMINATORS = {40}


def _skill_dirs_with_rubric() -> list[Path]:
    return sorted(
        d
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "rubric.md").exists()
    )


def _rubric_denominators() -> set[int]:
    """Every value that legitimately denotes a rubric total.

    Current totals are read from each ``rubric.md`` so a future migration
    (e.g. ``/49 → /54``) is picked up automatically; historical denominators
    are added so a stale value from a prior generation is still recognized as
    a *threshold* claim (and thus flagged) rather than silently ignored.
    """
    denoms = set(_HISTORICAL_DENOMINATORS)
    for skill_dir in _skill_dirs_with_rubric():
        total, _ = _parse_rubric_md(skill_dir / "rubric.md")
        denoms.add(total)
    return denoms


def _parse_rubric_md(rubric_path: Path) -> tuple[int, int]:
    """Return ``(total, threshold)`` declared in the rubric's first paragraph.

    Asserts the ``summing to **NN**`` total agrees with the ``≥NN/MM``
    denominator — an internally inconsistent rubric.md is itself a failure.
    """
    text = rubric_path.read_text(encoding="utf-8")
    total_m = _TOTAL_RE.search(text)
    threshold_m = _THRESHOLD_RE.search(text)
    assert total_m, f"no 'summing to **NN**' total found in {rubric_path}"
    assert threshold_m, f"no '≥NN/MM' threshold found in {rubric_path}"
    total = int(total_m.group(1))
    threshold = int(threshold_m.group(1))
    denominator = int(threshold_m.group(2))
    assert total == denominator, (
        f"{rubric_path}: declared total {total} disagrees with its own "
        f"threshold denominator ≥{threshold}/{denominator}"
    )
    return total, threshold


def _sibling_docs(skill_dir: Path) -> list[Path]:
    """SKILL.md + commands/*.md — the hand-synced restatement surface.

    ``rubric.md`` is excluded on purpose (it is the source of truth and holds
    migration history); nested example/asset dirs are not scanned.
    """
    docs: list[Path] = []
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        docs.append(skill_md)
    docs.extend(sorted((skill_dir / "commands").glob("*.md")))
    return docs


def _scan_for_stale_threshold(
    skill_dir: Path, total: int, threshold: int, denominators: set[int]
) -> list[str]:
    """Return ``path:line: text`` for each disagreeing threshold mention."""
    canonical = f"≥{threshold}/{total}"
    violations: list[str] = []
    for path in _sibling_docs(skill_dir):
        rel = path.relative_to(SKILLS_DIR.parent.parent)
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            # A line carrying the correct value is anchored — any other
            # threshold on it is a deliberate comparative reference.
            if canonical in line:
                continue
            for m in _THRESHOLD_RE.finditer(line):
                num, den = int(m.group(1)), int(m.group(2))
                if den not in denominators:
                    # Not a rubric total (e.g. a per-dimension ≥5/6 floor).
                    continue
                if den != total:
                    violations.append(
                        f"{rel}:{lineno}: stale denominator {m.group(0)} "
                        f"(current rubric is ≥{threshold}/{total}): "
                        f"{line.strip()}"
                    )
                elif num != threshold:
                    violations.append(
                        f"{rel}:{lineno}: wrong threshold {m.group(0)} "
                        f"(current rubric is ≥{threshold}/{total}): "
                        f"{line.strip()}"
                    )
    return violations


@pytest.mark.parametrize(
    "skill_name",
    [d.name for d in _skill_dirs_with_rubric()],
)
def test_skill_threshold_prose_matches_rubric_md(skill_name: str) -> None:
    """SKILL.md + commands/*.md threshold prose agrees with rubric.md.

    Regression guard for the #618 canary: a rubric-denominator migration that
    updates ``rubric.md`` but misses a sibling doc leaves the documented entry
    point asserting a convergence bar that no longer exists.

    This assertion FAILS if, for example, ``memo/rubric.md`` were bumped from
    ``summing to **44**`` / ``≥35/44`` to ``**45**`` / ``≥35/45`` without the
    matching edit to ``memo/SKILL.md``: every ``≥35/44`` restatement would be
    flagged as a stale denominator (44 ≠ 45).
    """
    skill_dir = SKILLS_DIR / skill_name
    total, threshold = _parse_rubric_md(skill_dir / "rubric.md")
    denominators = _rubric_denominators()
    violations = _scan_for_stale_threshold(
        skill_dir, total, threshold, denominators
    )
    assert violations == [], (
        f"skill '{skill_name}': threshold prose disagrees with rubric.md "
        f"(canonical ≥{threshold}/{total}):\n" + "\n".join(violations)
    )


def test_lint_covers_the_full_skill_fleet() -> None:
    """Discovery is automatic and covers every rubric-bearing skill.

    Guards against the parameterization silently collapsing to zero cases
    (which would make the lint pass vacuously). The 11 artifact-class skills
    each ship a rubric.md; the utility/bridge skills (project-*, etc.) do not.
    """
    skills = [d.name for d in _skill_dirs_with_rubric()]
    assert len(skills) >= 11, (
        f"expected at least 11 rubric-bearing skills, found {len(skills)}: "
        f"{skills}"
    )
    # Spot-check anchors so a rename/removal is loud rather than silent.
    for expected in ("memo", "deck", "report", "ip-uspto"):
        assert expected in skills, f"skill '{expected}' missing from lint set"
