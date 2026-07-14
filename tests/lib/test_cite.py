"""Tests for ``anvil.lib.cite``.

Strategy
--------

- **Unit tests (no network).** Parsing, key generation, BibTeX writer
  idempotency, and cache behavior are tested without any patching.
- **Cassette tests (patched network).** ``resolve()`` is exercised by
  patching ``urllib.request.urlopen`` to return the bytes of a fixture
  file under ``tests/lib/cassettes/cite/``.
- **One opt-in live test.** A single ``@pytest.mark.network`` test
  hits the real Crossref API; skipped by default. Run with
  ``pytest -m network`` from the repo root.

Recording new cassettes
-----------------------

Cassettes are hand-curated; to add one:

::

    curl -H "User-Agent: anvil-cite/0.0.1" \\
      "https://api.crossref.org/works/10.xxx/xxx" \\
      > tests/lib/cassettes/cite/crossref-10.xxx_xxx.json

    curl -H "User-Agent: anvil-cite/0.0.1" \\
      "https://export.arxiv.org/api/query?id_list=YYMM.NNNNN" \\
      > tests/lib/cassettes/cite/arxiv-YYMM.NNNNN.xml

    curl -H "User-Agent: anvil-cite/0.0.1" \\
      "https://api.datacite.org/dois/10.xxx/xxx" \\
      > tests/lib/cassettes/cite/datacite-10.xxx_xxx.json

DataCite fallback cassettes are hand-curated down to the fields the
resolver reads (titles / creators / publicationYear / types / url) so
they stay stable against the live record drifting over time.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import pytest

from anvil.lib.cite import (
    BibRecord,
    CiteResolutionError,
    Identifier,
    IdentifierKind,
    UnsupportedIdentifierError,
    bib_key,
    cite,
    parse_identifier,
    resolve,
)
# NOTE: ``anvil.lib`` re-exports the function ``cite`` at the package
# level, which shadows the submodule when accessed via attribute lookup
# (``import anvil.lib.cite as ...`` returns the function, not the module).
# Resolve the actual module via ``sys.modules`` so monkeypatching module-
# level globals (``_CACHE_ROOT``) works.
cite_mod = sys.modules["anvil.lib.cite"]


CASSETTES = Path(__file__).resolve().parent / "cassettes" / "cite"


# ---------------------------------------------------------------------------
# Cassette helper
# ---------------------------------------------------------------------------


def _http_404(url: str) -> urllib.error.HTTPError:
    """Build an ``HTTPError`` that mimics a registry "DOI not here" 404.

    Both Crossref and DataCite return a 404 for a DOI they do not have
    registered; the cassette layer raises this when no fixture exists so
    the fallback / verified-or-dropped paths are exercised without the
    network.
    """

    return urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)


def _cassette_for(url: str) -> bytes:
    """Map a URL to the hand-curated cassette bytes.

    Test patches ``urllib.request.urlopen`` to call this helper. A URL
    whose cassette file is absent raises a 404 ``HTTPError`` — the same
    signal the live registry sends for an unregistered DOI. This lets the
    Crossref→DataCite fallback and the double-miss failure path be tested
    purely from the presence/absence of fixture files.
    """

    if url.startswith("https://api.crossref.org/works/"):
        doi = url.rsplit("/works/", 1)[1]
        # The doi may have been URL-quoted by the resolver; unquote so
        # the cassette filename matches the human-readable form.
        doi = urllib.parse.unquote(doi)
        # File-naming convention: '/' replaced with '_'.
        safe = doi.replace("/", "_")
        path = CASSETTES / f"crossref-{safe}.json"
        if not path.exists():
            raise _http_404(url)
        return path.read_bytes()
    if url.startswith("https://api.datacite.org/dois/"):
        doi = url.rsplit("/dois/", 1)[1]
        doi = urllib.parse.unquote(doi)
        safe = doi.replace("/", "_")
        path = CASSETTES / f"datacite-{safe}.json"
        if not path.exists():
            raise _http_404(url)
        return path.read_bytes()
    if url.startswith("https://export.arxiv.org/api/query"):
        query = urllib.parse.urlparse(url).query
        params = urllib.parse.parse_qs(query)
        ids = params.get("id_list", [""])[0]
        path = CASSETTES / f"arxiv-{ids}.xml"
        return path.read_bytes()
    raise AssertionError(f"unexpected URL in test: {url}")


class _FakeResponse:
    """Minimal stand-in for the ``urlopen`` context manager."""

    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return self._data


def _make_urlopen(spy: dict) -> Callable:
    """Return a patched urlopen that records calls into ``spy``."""

    def _urlopen(req, timeout=None):  # noqa: ARG001 - test stub
        url = req.full_url if hasattr(req, "full_url") else str(req)
        spy.setdefault("calls", []).append(url)
        return _FakeResponse(_cassette_for(url))

    return _urlopen


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Redirect ``~/.cache/anvil/cite`` to a per-test tmp dir.

    Also ensures CITE_CACHE_BYPASS is unset by default, so each test
    starts with a clean, isolated cache.
    """

    monkeypatch.setattr(cite_mod, "_CACHE_ROOT", tmp_path / "cite-cache")
    monkeypatch.delenv("CITE_CACHE_BYPASS", raising=False)
    yield


# ---------------------------------------------------------------------------
# 1. parse_identifier — DOI variants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("10.1038/nature12373", "10.1038/nature12373"),
        ("doi:10.1038/nature12373", "10.1038/nature12373"),
        ("https://doi.org/10.1038/nature12373", "10.1038/nature12373"),
        ("https://dx.doi.org/10.1038/nature12373", "10.1038/nature12373"),
        ("DOI:10.1038/nature12373", "10.1038/nature12373"),
    ],
)
def test_parse_doi_variants(raw, expected):
    ident = parse_identifier(raw)
    assert ident.kind == IdentifierKind.DOI
    assert ident.value == expected


# ---------------------------------------------------------------------------
# 2. parse_identifier — arXiv variants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2305.14325", "2305.14325"),
        ("2305.14325v3", "2305.14325"),
        ("arxiv:2305.14325", "2305.14325"),
        ("arXiv:2305.14325v3", "2305.14325"),
        ("https://arxiv.org/abs/2305.14325", "2305.14325"),
        ("https://arxiv.org/abs/2305.14325v3", "2305.14325"),
    ],
)
def test_parse_arxiv_variants(raw, expected):
    ident = parse_identifier(raw)
    assert ident.kind == IdentifierKind.ARXIV
    assert ident.value == expected


# ---------------------------------------------------------------------------
# 3. parse_identifier — URL fallback
# ---------------------------------------------------------------------------


def test_parse_url_fallback():
    ident = parse_identifier("https://example.com/papers/foo.pdf")
    assert ident.kind == IdentifierKind.URL
    assert ident.value == "https://example.com/papers/foo.pdf"


# ---------------------------------------------------------------------------
# 4. parse_identifier — garbage input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["", "   ", "not a citation", "10.shortdoi"])
def test_parse_garbage_raises(raw):
    with pytest.raises(ValueError):
        parse_identifier(raw)


# ---------------------------------------------------------------------------
# 5. bib_key — canonical case
# ---------------------------------------------------------------------------


def test_bib_key_canonical():
    record = BibRecord(
        entry_type="article",
        authors=["Smith, John"],
        title="Transformers for Everyone",
        year=2024,
    )
    assert bib_key(record) == "smith2024transformers"


# ---------------------------------------------------------------------------
# 6. bib_key — stopword skipping
# ---------------------------------------------------------------------------


def test_bib_key_skips_stopwords():
    record = BibRecord(
        entry_type="article",
        authors=["Doe, Jane"],
        title="The Foo Bar",
        year=2020,
    )
    assert bib_key(record) == "doe2020foo"


# ---------------------------------------------------------------------------
# 7. bib_key — ASCII folding
# ---------------------------------------------------------------------------


def test_bib_key_ascii_folds_diacritics():
    record = BibRecord(
        entry_type="article",
        authors=["Müller, Hans"],
        title="Über Quantengravitation",
        year=2019,
    )
    # 'Müller' -> 'muller'; 'Über' (stopword? no) -> 'uber'.
    assert bib_key(record) == "muller2019uber"


# ---------------------------------------------------------------------------
# 8. bib_key — collision resolution
# ---------------------------------------------------------------------------


def test_bib_key_collision_appends_b(tmp_path):
    refs = tmp_path / "refs.bib"
    refs.write_text(
        "@article{smith2024transformers,\n"
        "  author = {Smith, John},\n"
        "}\n",
        encoding="utf-8",
    )
    record = BibRecord(
        entry_type="article",
        authors=["Smith, John"],
        title="Transformers Strike Back",
        year=2024,
    )
    assert bib_key(record, refs_bib=refs) == "smith2024transformersb"


# ---------------------------------------------------------------------------
# 9. resolve(DOI) — Crossref cassette
# ---------------------------------------------------------------------------


def test_resolve_doi_crossref_cassette():
    spy: dict = {}
    ident = Identifier(kind=IdentifierKind.DOI, value="10.1038/nature12373")
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        record = resolve(ident)
    assert record.entry_type == "article"
    assert record.title == "Nanometre-scale thermometry in a living cell"
    assert record.journal == "Nature"
    assert record.year == 2013
    assert record.volume == "500"
    assert record.issue == "7460"
    assert record.pages == "54-58"
    assert record.doi == "10.1038/nature12373"
    assert record.authors[0] == "Kucsko, G."
    assert len(record.authors) >= 3


# ---------------------------------------------------------------------------
# 10. resolve(arXiv) — arXiv cassette
# ---------------------------------------------------------------------------


def test_resolve_arxiv_cassette():
    spy: dict = {}
    ident = Identifier(kind=IdentifierKind.ARXIV, value="1706.03762")
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        record = resolve(ident)
    assert record.entry_type == "misc"
    assert record.title == "Attention Is All You Need"
    assert record.year == 2017
    assert record.eprint == "1706.03762"
    assert record.eprinttype == "arxiv"
    assert record.url == "https://arxiv.org/abs/1706.03762"
    assert record.authors[0] == "Vaswani, Ashish"
    assert len(record.authors) == 8


# ---------------------------------------------------------------------------
# 10a. resolve(DOI) — DataCite fallback on Crossref miss
# ---------------------------------------------------------------------------


def test_resolve_doi_datacite_fallback():
    """A Zenodo DOI (404 on Crossref) resolves via DataCite."""

    spy: dict = {}
    ident = Identifier(kind=IdentifierKind.DOI, value="10.5281/zenodo.4618153")
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        record = resolve(ident)
    # Crossref was tried first (and 404'd), then DataCite.
    assert any("api.crossref.org" in c for c in spy["calls"])
    assert any("api.datacite.org" in c for c in spy["calls"])
    # DataCite software record maps to @misc per its types.bibtex hint.
    assert record.entry_type == "misc"
    assert record.title.startswith("Qiskit Metal")
    assert record.year == 2021
    assert record.doi == "10.5281/zenodo.4618153"
    assert record.url == "https://zenodo.org/record/4618153"
    # familyName/givenName split renders surname-first.
    assert record.authors[0] == "McConkey, Thomas G"
    assert record.authors[1] == "Minev, Zlatko"
    # Organizational creator (name-only, no family/given) renders as-is.
    assert "Qiskit Metal Development Team" in record.authors


def test_resolve_doi_datacite_not_article_or_journal():
    """DataCite-sourced software records carry no journal/volume fields."""

    spy: dict = {}
    ident = Identifier(kind=IdentifierKind.DOI, value="10.5281/zenodo.4618153")
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        record = resolve(ident)
    assert record.journal is None
    assert record.volume is None
    assert record.issue is None
    assert record.eprint is None


def test_resolve_doi_missing_from_both_registries_raises():
    """A DOI unknown to Crossref AND DataCite preserves verified-or-dropped."""

    spy: dict = {}
    # No cassette exists for this DOI under either registry, so both 404.
    ident = Identifier(kind=IdentifierKind.DOI, value="10.9999/does.not.exist")
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        with pytest.raises(CiteResolutionError):
            resolve(ident)
    # Both registries were consulted before giving up.
    assert any("api.crossref.org" in c for c in spy["calls"])
    assert any("api.datacite.org" in c for c in spy["calls"])


def test_datacite_fallback_cache_roundtrip():
    """DataCite records cache under the shared doi/ namespace, hit-first."""

    spy: dict = {}
    ident = Identifier(kind=IdentifierKind.DOI, value="10.5281/zenodo.4618153")
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        resolve(ident)
        first_calls = len(spy["calls"])
        assert first_calls >= 2  # Crossref miss + DataCite hit.
        resolve(ident)
        # Second resolve is served from cache — no new network calls.
        assert len(spy["calls"]) == first_calls
    # Cache file lives under the DOI namespace, not a datacite-specific one.
    cache_file = cite_mod._cache_path(ident)
    assert cache_file.exists()
    assert cache_file.parent.name == "doi"
    BibRecord.model_validate_json(cache_file.read_text(encoding="utf-8"))


def test_datacite_fallback_respects_cache_bypass(monkeypatch):
    """CITE_CACHE_BYPASS disables read+write for DataCite-sourced records."""

    monkeypatch.setenv("CITE_CACHE_BYPASS", "1")
    spy: dict = {}
    ident = Identifier(kind=IdentifierKind.DOI, value="10.5281/zenodo.4618153")
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        resolve(ident)
        resolve(ident)
    # No cache short-circuit: the second resolve re-hits both registries.
    crossref_calls = [c for c in spy["calls"] if "api.crossref.org" in c]
    datacite_calls = [c for c in spy["calls"] if "api.datacite.org" in c]
    assert len(crossref_calls) == 2
    assert len(datacite_calls) == 2
    assert not cite_mod._cache_path(ident).exists()


def test_cite_writes_datacite_entry(tmp_path):
    """cite() writes a @misc DataCite entry and returns the @key."""

    spy: dict = {}
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        token = cite("10.5281/zenodo.4618153", tmp_path)
    text = (tmp_path / "refs.bib").read_text(encoding="utf-8")
    assert token.startswith("@")
    assert "@misc{mcconkey2021qiskit," in text
    assert "doi = {10.5281/zenodo.4618153}," in text
    assert "url = {https://zenodo.org/record/4618153}," in text
    # No journal field on a software record.
    assert "journal" not in text


# ---------------------------------------------------------------------------
# 11. resolve(PMID / URL) — unsupported in v0
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind, value",
    [
        (IdentifierKind.PMID, "12345"),
        (IdentifierKind.URL, "https://example.com/paper.html"),
    ],
)
def test_resolve_unsupported_kinds(kind, value):
    ident = Identifier(kind=kind, value=value)
    with pytest.raises(UnsupportedIdentifierError):
        resolve(ident)


# ---------------------------------------------------------------------------
# 12. cite() writes a new entry and returns the @key
# ---------------------------------------------------------------------------


def test_cite_writes_entry_and_returns_token(tmp_path):
    spy: dict = {}
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        token = cite("10.1038/nature12373", tmp_path)
    refs = tmp_path / "refs.bib"
    assert refs.exists()
    text = refs.read_text(encoding="utf-8")
    assert token.startswith("@")
    assert token == "@kucsko2013nanometre"
    assert "@article{kucsko2013nanometre," in text
    assert "title = {Nanometre-scale thermometry in a living cell}," in text
    assert "doi = {10.1038/nature12373}," in text


# ---------------------------------------------------------------------------
# 13. cite() idempotency
# ---------------------------------------------------------------------------


def test_cite_idempotent_on_second_call(tmp_path):
    spy: dict = {}
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        token1 = cite("10.1038/nature12373", tmp_path)
        token2 = cite("10.1038/nature12373", tmp_path)
    assert token1 == token2
    text = (tmp_path / "refs.bib").read_text(encoding="utf-8")
    # Only one entry; count occurrences of '@article{'.
    assert text.count("@article{") == 1


# ---------------------------------------------------------------------------
# 14. cite() with two different identifiers producing colliding keys
# ---------------------------------------------------------------------------


def test_cite_collision_appends_suffix(tmp_path):
    """Two distinct records that hash to the same base key get b/c suffixes."""

    # We can't easily force two real DOIs to collide on lastname+year+word;
    # instead, seed refs.bib with a hand-crafted entry that collides with
    # the Crossref nature record's key, then cite() the real DOI.
    refs = tmp_path / "refs.bib"
    refs.write_text(
        "@article{kucsko2013nanometre,\n"
        "  author = {Different, Author},\n"
        "  title = {Different paper, same key},\n"
        "  doi = {10.9999/other},\n"
        "  year = {2013},\n"
        "}\n",
        encoding="utf-8",
    )
    spy: dict = {}
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        token = cite("10.1038/nature12373", tmp_path)
    assert token == "@kucsko2013nanometreb"
    text = refs.read_text(encoding="utf-8")
    assert "@article{kucsko2013nanometre," in text
    assert "@article{kucsko2013nanometreb," in text


# ---------------------------------------------------------------------------
# 15. cache hit short-circuits the second resolve call
# ---------------------------------------------------------------------------


def test_cache_hit_skips_network():
    spy: dict = {}
    ident = Identifier(kind=IdentifierKind.DOI, value="10.1038/nature12373")
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        resolve(ident)
        assert len(spy["calls"]) == 1
        resolve(ident)
        # Second call must be served from cache; no additional urlopen.
        assert len(spy["calls"]) == 1


# ---------------------------------------------------------------------------
# 16. cache miss writes the expected file
# ---------------------------------------------------------------------------


def test_cache_miss_writes_file():
    spy: dict = {}
    ident = Identifier(kind=IdentifierKind.DOI, value="10.1038/nature12373")
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        resolve(ident)
    expected = cite_mod._cache_path(ident)
    assert expected.exists()
    # Roundtrip-loadable as a BibRecord.
    data = expected.read_text(encoding="utf-8")
    BibRecord.model_validate_json(data)


# ---------------------------------------------------------------------------
# 17. CITE_CACHE_BYPASS disables read AND write
# ---------------------------------------------------------------------------


def test_cite_cache_bypass_disables_read_and_write(monkeypatch):
    monkeypatch.setenv("CITE_CACHE_BYPASS", "1")
    spy: dict = {}
    ident = Identifier(kind=IdentifierKind.DOI, value="10.1038/nature12373")
    with patch("anvil.lib.cite.urllib.request.urlopen", _make_urlopen(spy)):
        resolve(ident)
        resolve(ident)
    # Both calls hit the network (no read short-circuit).
    assert len(spy["calls"]) == 2
    # And no cache file was written.
    assert not cite_mod._cache_path(ident).exists()


# ---------------------------------------------------------------------------
# 18. (opt-in) Live network smoke test
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_live_doi_resolution_smoke():
    """One live test against a stable DOI.

    Skipped by default. Invoke with ``pytest -m network`` to run.
    Acts as the cassette-recording reference: if this passes against
    the real Crossref API and the cassette tests pass, the cassette is
    still representative of the live API shape.
    """

    record = resolve("10.1038/nature12373")
    assert record.entry_type == "article"
    assert record.year == 2013
    assert "Nanometre" in record.title or "nanometre" in record.title.lower()
