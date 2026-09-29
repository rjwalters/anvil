"""Regression tests for ``scripts/check-install-staleness.sh`` (issue #1320).

The script is the "am I actually current?" read site that
``/repo:update-tools`` lacked: it reads a consumer's
``.anvil/install-metadata.json`` and reports whether every installed skill's
body is at the recorded top-level ``anvil_version``, or whether some are frozen
behind it because a prior install declined to overwrite consumer-modified
files.

Contract under test:

* exit ``0`` — uniformly current (``skipped_overrides`` empty)
* exit ``1`` — N skill(s) frozen behind, each named with its ``skill_versions``
  value (or ``unknown`` for a pre-#633 manifest)
* exit ``2`` — could not evaluate (no manifest, no ``anvil_version``)

The manifest is written directly rather than produced by a full installer run:
these cases are about the *parse and verdict*, and the installer's own
manifest-writing contract is covered by ``test_install_staleness_report.py``.
That keeps the suite fast and lets the pre-#633 / malformed shapes be
constructed exactly.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK = REPO_ROOT / "scripts" / "check-install-staleness.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(CHECK), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _write_manifest(target: Path, manifest: dict, *, pretty: bool = False) -> Path:
    anvil = target / ".anvil"
    anvil.mkdir(parents=True, exist_ok=True)
    path = anvil / "install-metadata.json"
    path.write_text(
        json.dumps(manifest, indent=2 if pretty else None) + "\n",
    )
    return path


def _manifest(
    *,
    version: str = "0.11.6",
    commit: str = "abc1234",
    installed: list[str] | None = None,
    skipped: list[str] | None = None,
    skill_versions: dict[str, str] | None = None,
) -> dict:
    out = {
        "anvil_version": version,
        "commit": commit,
        "layout_version": 2,
        "installed_skills": installed if installed is not None else ["memo", "deck"],
        "skipped_overrides": skipped or [],
        "skill_hashes": {},
        "lib_hash": "",
    }
    if skill_versions is not None:
        out["skill_versions"] = skill_versions
    return out


# ---------------------------------------------------------------------------
# Verdict cases
# ---------------------------------------------------------------------------


def test_uniformly_current_exits_zero(tmp_path: Path) -> None:
    """No skipped overrides → exit 0 and no frozen-skill wording."""

    _write_manifest(
        tmp_path,
        _manifest(skill_versions={"memo": "0.11.6", "deck": "0.11.6"}),
    )

    result = _run(str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0.11.6" in result.stdout
    assert "all 2 installed skill(s) at 0.11.6" in result.stdout, result.stdout
    assert "frozen" not in result.stdout, (
        f"a uniformly-current tree reported frozen skills:\n{result.stdout}"
    )


def test_one_of_several_frozen_exits_one_and_names_the_skill(tmp_path: Path) -> None:
    """The reported incident's shape: version matches, content does not."""

    _write_manifest(
        tmp_path,
        _manifest(
            version="0.11.6",
            installed=["deck"],
            skipped=["memo"],
            skill_versions={"memo": "0.10.1", "deck": "0.11.6"},
        ),
    )

    result = _run(str(tmp_path))
    assert result.returncode == 1, (
        "a tree with a frozen skill must not report exit 0 (the bare 'current' "
        f"this script exists to remove):\n{result.stdout}{result.stderr}"
    )
    assert "NOT uniformly current" in result.stdout, result.stdout
    assert "1 of 2" in result.stdout, result.stdout
    assert "memo" in result.stdout and "0.10.1" in result.stdout, result.stdout
    # The skill that upgraded cleanly is never named — the report lists the
    # frozen skills only, so a mention of `deck` anywhere is a false positive.
    assert "deck" not in result.stdout, (
        f"an up-to-date skill was reported as frozen:\n{result.stdout}"
    )


def test_all_skills_frozen(tmp_path: Path) -> None:
    """Edge case: every skill skipped — the whole tree is behind."""

    _write_manifest(
        tmp_path,
        _manifest(
            installed=[],
            skipped=["memo", "deck", "help"],
            skill_versions={"memo": "0.10.1", "deck": "0.10.1", "help": "0.9.0"},
        ),
    )

    result = _run(str(tmp_path))
    assert result.returncode == 1
    assert "3 of 3" in result.stdout, result.stdout
    for skill, ver in (("memo", "0.10.1"), ("deck", "0.10.1"), ("help", "0.9.0")):
        assert skill in result.stdout, result.stdout
        assert ver in result.stdout, result.stdout


def test_legacy_manifest_without_skill_versions_reports_unknown(
    tmp_path: Path,
) -> None:
    """A pre-#633 manifest degrades to 'unknown' — never a guess, never a crash."""

    _write_manifest(
        tmp_path,
        _manifest(version="0.11.6", installed=["deck"], skipped=["memo"]),
    )

    result = _run(str(tmp_path))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "unknown" in result.stdout, (
        f"legacy manifest did not degrade to 'unknown':\n{result.stdout}"
    )
    assert "memo                     frozen at unknown" in result.stdout, result.stdout
    assert "frozen at 0.11.6" not in result.stdout, (
        "the top-level anvil_version was substituted for a missing per-skill "
        f"version — the exact conflation #1320 is about:\n{result.stdout}"
    )


def test_pretty_printed_manifest_parses_identically(tmp_path: Path) -> None:
    """The parse must not depend on one-line vs. indented JSON.

    A consumer, an editor, or another tool may have reformatted the manifest;
    the installer's own readers flatten newlines first for exactly this reason.
    """

    _write_manifest(
        tmp_path,
        _manifest(
            installed=["deck"],
            skipped=["memo"],
            skill_versions={"memo": "0.10.1", "deck": "0.11.6"},
        ),
        pretty=True,
    )

    result = _run(str(tmp_path))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "memo" in result.stdout and "0.10.1" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# Could-not-evaluate cases
# ---------------------------------------------------------------------------


def test_missing_manifest_exits_two(tmp_path: Path) -> None:
    """Not an anvil install → 'could not evaluate', never a false 'current'."""

    result = _run(str(tmp_path))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "could not evaluate" in result.stderr, result.stderr


def test_manifest_without_anvil_version_exits_two(tmp_path: Path) -> None:
    """A manifest missing the version field cannot be judged — say so."""

    manifest = _manifest()
    manifest.pop("anvil_version")
    _write_manifest(tmp_path, manifest)

    result = _run(str(tmp_path))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "anvil_version" in result.stderr, result.stderr


# ---------------------------------------------------------------------------
# Output modes
# ---------------------------------------------------------------------------


def test_json_mode_emits_parseable_output(tmp_path: Path) -> None:
    """``--json`` is the shape a tool (e.g. /repo:update-tools) consumes."""

    _write_manifest(
        tmp_path,
        _manifest(
            version="0.11.6",
            installed=["deck"],
            skipped=["memo"],
            skill_versions={"memo": "0.10.1", "deck": "0.11.6"},
        ),
    )

    result = _run(str(tmp_path), "--json")
    assert result.returncode == 1, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["anvil_version"] == "0.11.6"
    assert payload["uniformly_current"] is False
    assert payload["frozen_count"] == 1
    assert payload["skill_count"] == 2
    assert payload["frozen_skills"] == [{"skill": "memo", "frozen_at": "0.10.1"}]


def test_json_mode_on_a_clean_install(tmp_path: Path) -> None:
    """The empty ``frozen_skills`` array must still be valid JSON."""

    _write_manifest(
        tmp_path, _manifest(skill_versions={"memo": "0.11.6", "deck": "0.11.6"})
    )

    result = _run(str(tmp_path), "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["uniformly_current"] is True
    assert payload["frozen_skills"] == []
    assert payload["frozen_count"] == 0


def test_quiet_mode_is_exit_code_only(tmp_path: Path) -> None:
    """``--quiet`` suppresses the report but keeps the verdict."""

    _write_manifest(
        tmp_path,
        _manifest(
            installed=["deck"], skipped=["memo"], skill_versions={"memo": "0.10.1"}
        ),
    )

    result = _run(str(tmp_path), "--quiet")
    assert result.returncode == 1
    assert result.stdout.strip() == "", (
        f"--quiet still printed a report:\n{result.stdout}"
    )


def test_script_never_writes_to_the_target(tmp_path: Path) -> None:
    """Strictly read-only: the manifest's bytes and mtime are untouched.

    The script is invoked against live consumer repos by an "am I current"
    check; a read site that mutates what it inspects would be a far worse
    defect than the one it fixes.
    """

    manifest_path = _write_manifest(
        tmp_path,
        _manifest(
            installed=["deck"], skipped=["memo"], skill_versions={"memo": "0.10.1"}
        ),
    )
    before_bytes = manifest_path.read_bytes()
    before_mtime = manifest_path.stat().st_mtime_ns
    before_tree = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    assert _run(str(tmp_path)).returncode == 1

    assert manifest_path.read_bytes() == before_bytes
    assert manifest_path.stat().st_mtime_ns == before_mtime
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before_tree


def test_unknown_option_exits_two(tmp_path: Path) -> None:
    """Bad args are a 'could not evaluate', not a silent pass."""

    result = _run(str(tmp_path), "--no-such-flag")
    assert result.returncode == 2, result.stdout + result.stderr
