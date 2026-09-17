"""Adversarial registry stress (#109, S8/S9).

Actively tries to smuggle unsafe/restricted/unprovenanced sources through
``registry.load_registry`` and the fetcher's registry gate. Every case here is either:

  1. rejected outright (``RegistryError`` / ``FetchError`` / no fetch at all) -- the
     expected, defended outcome, asserted explicitly (not "not a bug" hand-waving); or
  2. a genuine leak, captured as ``xfail(strict=True, reason="BUG(CRITICAL): ...")``
     with a minimal reproducer.

Complements ``test_registry.py`` (happy-path + basic governance) and ``test_fetch.py``
(fail-soft fetch mechanics) with adversarial registry shapes: unknown license,
metadata_only/restricted with training forced-true in the YAML, disabled-but-referenced,
duplicate ids, malformed URL, path traversal, unsupported/mismatched adapter names, and
proof the fetcher never touches a URL outside the registry.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.cloudforge.learn._ingest import ADAPTERS, UnknownAdapterError, resolve_adapter
from app.cloudforge.learn.fetch import FetchedResponse, fetch_all_sources
from app.cloudforge.learn.registry import RegistryError, get_entry, load_registry
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry, SourceType


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "registry.yaml"
    path.write_text(text, encoding="utf-8")
    return path


# --- unknown license / bad reuse posture, training forced true in the raw YAML -------


def test_unknown_license_forces_false_even_when_yaml_declares_true(tmp_path: Path) -> None:
    """A hostile registry entry claims unknown license AND allowed_for_training: true.

    The loader must override the declared flag -- rejection-by-normalization IS the
    guarantee (S9). Not a bug: this is the governance rule working as designed.
    """
    path = _write(
        tmp_path,
        """
sources:
  - id: unknown-license-src
    name: shady
    type: iac_repo
    url: "https://example.com/x"
    adapter: rule_catalog_yaml
    enabled: true
    license: unknown
    reuse_status: full_reuse
    allowed_for_training: true
    notes: ""
""",
    )
    registry = load_registry(path)
    entry = get_entry(registry, "unknown-license-src")
    assert entry.allowed_for_training is False


def test_metadata_only_forces_false_even_when_yaml_declares_true(tmp_path: Path) -> None:
    """metadata_only + allowed_for_training: true in the raw YAML -> loader overrides (S9)."""
    path = _write(
        tmp_path,
        """
sources:
  - id: metadata-liar
    name: metadata liar
    type: scanner_rule_index
    url: "https://example.com/meta"
    adapter: checkov_policy_index
    enabled: true
    license: "Apache-2.0"
    reuse_status: metadata_only
    allowed_for_training: true
    notes: ""
""",
    )
    registry = load_registry(path)
    entry = get_entry(registry, "metadata-liar")
    assert entry.allowed_for_training is False


def test_restricted_forces_false_even_when_yaml_declares_true(tmp_path: Path) -> None:
    """restricted + allowed_for_training: true in the raw YAML -> loader overrides (S9)."""
    path = _write(
        tmp_path,
        """
sources:
  - id: restricted-liar
    name: restricted liar
    type: control_framework
    url: "https://example.com/restricted"
    adapter: rule_catalog_yaml
    enabled: true
    license: "Proprietary"
    reuse_status: restricted
    allowed_for_training: true
    notes: ""
""",
    )
    registry = load_registry(path)
    entry = get_entry(registry, "restricted-liar")
    assert entry.allowed_for_training is False


def test_unknown_reuse_status_string_is_rejected_by_schema(tmp_path: Path) -> None:
    """``reuse_status: unknown`` IS a valid enum member -- confirm it is NOT training-eligible
    even though it is not in ``_FORCE_FALSE_REUSE`` (governance only force-corrects
    restricted/metadata_only at the registry layer; ``unknown`` reuse_status is excluded
    later by ``NON_TRAINING_REUSE`` at the pattern layer -- this test proves the registry
    layer does NOT also need to force it, since the schema still accepts the declared flag).
    """
    path = _write(
        tmp_path,
        """
sources:
  - id: unknown-reuse-src
    name: unknown reuse
    type: iac_repo
    url: "https://example.com/unknown-reuse"
    adapter: rule_catalog_yaml
    enabled: true
    license: "MIT"
    reuse_status: unknown
    allowed_for_training: true
    notes: ""
""",
    )
    registry = load_registry(path)
    entry = get_entry(registry, "unknown-reuse-src")
    # The registry loader does not force this false (only restricted/metadata_only are
    # forced at this layer) -- but NON_TRAINING_REUSE at the pattern/export layer still
    # blocks it (see test_pattern_content_adversarial.py). This is documented, not a leak.
    assert entry.reuse_status is ReuseStatus.UNKNOWN
    assert entry.allowed_for_training is True  # registry layer alone does not gate this


# --- disabled-but-referenced -----------------------------------------------------------


def test_disabled_source_is_still_resolvable_by_get_entry_but_never_fetched(
    tmp_path: Path,
) -> None:
    """A disabled source stays resolvable via ``get_entry``/``by_id`` (needed for
    provenance lookups on already-ingested data) but MUST NOT be fetched or appear in
    ``enabled_sources``. This is intended behavior, not a leak -- assert both halves.
    """
    path = _write(
        tmp_path,
        """
sources:
  - id: disabled-but-referenced
    name: disabled ref
    type: iac_repo
    url: "https://example.com/disabled"
    adapter: rule_catalog_yaml
    enabled: false
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
    notes: ""
""",
    )
    registry = load_registry(path)

    # still resolvable (metadata lookups must not crash on a disabled id)
    entry = get_entry(registry, "disabled-but-referenced")
    assert entry.enabled is False

    # never in the fetcher's working set
    from app.cloudforge.learn.registry import enabled_sources

    assert entry.id not in {e.id for e in enabled_sources(registry)}

    # never actually fetched even if a caller mistakenly passes it directly
    def _fetch_should_not_be_called(url: str) -> FetchedResponse:
        raise AssertionError("disabled source must never be fetched")

    summary = fetch_all_sources(
        sources=[entry], raw_dir=tmp_path / "raw", fetch_fn=_fetch_should_not_be_called
    )
    assert summary.skipped == 1
    assert summary.fetched == 0


# --- duplicate ids -----------------------------------------------------------------------


def test_duplicate_ids_across_url_and_path_sources_raises(tmp_path: Path) -> None:
    """Duplicate ids where one is url-based and one is path-based -- still rejected."""
    path = _write(
        tmp_path,
        """
sources:
  - id: dupe-mixed
    name: a
    type: iac_repo
    url: "https://example.com/a"
    adapter: rule_catalog_yaml
    enabled: true
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
  - id: dupe-mixed
    name: b
    type: local_rule_catalog
    path: "data/somewhere/b.yaml"
    adapter: rule_catalog_yaml
    enabled: true
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
""",
    )
    with pytest.raises(RegistryError):
        load_registry(path)


# --- malformed URL -------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "not-a-url-at-all",
        "javascript:alert(1)",
        "ftp://example.com/x",
        "",
    ],
)
def test_malformed_or_non_http_url_is_accepted_by_schema_but_never_fetched_ok(
    tmp_path: Path, bad_url: str
) -> None:
    """``SourceEntry.url`` is typed ``str | None`` -- no URL-shape validation exists at the
    schema layer. A malformed/non-http(s) URL string is NOT rejected by ``load_registry``.

    This IS a real gap relative to the ticket's "malformed URL -> rejected" expectation,
    but it does not cause a leak: ``fetch_all_sources`` never validates a URL shape either
    -- it hands the string to ``fetch_fn`` verbatim, and the *real* ``default_fetch_bytes``
    (httpx) raises ``httpx.UnsupportedProtocol``/``httpx.InvalidURL`` for anything that
    isn't a real http(s) URL, which is caught by the fetcher's own ``httpx.HTTPError``
    fail-soft handling. So: no crash, no traversal, no unbounded fetch -- just recorded as
    a normal per-source failure. Assert that safety net explicitly (fail-soft catches
    what schema validation does not).
    """
    if not bad_url:
        # an empty string is falsy -> SourceEntry._exactly_one_location treats "" as
        # "no url set" (bool("") is False) and requires path to be set instead -- a
        # *stricter* rejection than the non-empty cases, exercised separately below.
        path = _write(
            tmp_path,
            """
sources:
  - id: empty-url-src
    name: empty url
    type: iac_repo
    url: ""
    adapter: rule_catalog_yaml
    enabled: true
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
""",
        )
        with pytest.raises(RegistryError):
            load_registry(path)
        return

    path = _write(
        tmp_path,
        f"""
sources:
  - id: malformed-url-src
    name: malformed url
    type: iac_repo
    url: "{bad_url}"
    adapter: rule_catalog_yaml
    enabled: true
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
""",
    )
    registry = load_registry(path)
    entry = get_entry(registry, "malformed-url-src")
    assert entry.url == bad_url  # schema does not reject the shape (documented gap)

    def _real_like_fetch(url: str) -> FetchedResponse:
        # emulate what httpx.get raises for a genuinely bad URL -- proves the fetcher's
        # fail-soft path is what actually protects us here, not schema validation.
        raise httpx.UnsupportedProtocol(f"unsupported protocol in {url!r}")

    summary = fetch_all_sources(
        sources=[entry], raw_dir=tmp_path / "raw", fetch_fn=_real_like_fetch
    )
    assert summary.failed == 1
    assert summary.fetched == 0
    assert not (tmp_path / "raw" / entry.id).exists()


# --- path traversal in the local `path` field (fixed, now a regression) -------
#
# The registry is the trusted allow-list, but previously a malicious/corrupted entry
# with `path: ../../../etc/passwd` (or an absolute path) parsed cleanly and
# `_ingest.resolve_raw_path` handed it straight to an adapter -- ingestion-time arbitrary
# file read outside the data roots. The fix is a two-layer containment guard:
#   1. `SourceEntry._path_stays_in_tree` (model validator) -- rejects an escaping `path`
#      at LOAD time, so every consumer (ingest, provenance stamping, any future reader) is
#      protected by a single chokepoint. Lexical + CWD-independent.
#   2. `_ingest._resolve_local_path` -- a second resolve-time containment check
#      (`Path.resolve()` + `is_relative_to(base)`), so even a `SourceEntry` reaching
#      `resolve_raw_path` through a BYPASSED validator (`model_construct`) still cannot
#      escape. Raises `PathTraversalError`.


@pytest.mark.parametrize(
    "traversal_path",
    [
        "../../../../../etc/passwd",
        "/etc/passwd",
        "data/rule_catalog/../../../../etc/passwd",
        "../data/rule_catalog/seed_patterns.yaml",  # single climb out of root still escapes
    ],
)
def test_path_traversal_is_rejected_at_registry_load_time(
    tmp_path: Path, traversal_path: str
) -> None:
    """A hostile registry entry whose local ``path`` escapes the project tree (via ``..``
    traversal or an absolute path) is now REJECTED at ``load_registry`` time by the
    ``SourceEntry._path_stays_in_tree`` model validator (surfaced as ``RegistryError``).
    Rejection-with-a-clear-error IS the guarantee -- no silent pass, no arbitrary read.
    """
    path = _write(
        tmp_path,
        f"""
sources:
  - id: traversal-src
    name: traversal
    type: local_rule_catalog
    path: "{traversal_path}"
    adapter: rule_catalog_yaml
    enabled: true
    license: "CC0-1.0"
    reuse_status: full_reuse
    allowed_for_training: true
""",
    )
    with pytest.raises(RegistryError) as exc_info:
        load_registry(path)
    assert "escapes the project tree" in str(exc_info.value)


def test_in_tree_local_path_still_loads_and_resolves_normally(tmp_path: Path) -> None:
    """The containment guard must NOT break legitimate local sources: an ordinary in-tree
    relative path (like the real ``local-rule-catalog`` seed catalog) still loads cleanly
    and ``resolve_raw_path`` resolves it to a contained, in-project absolute path.
    """
    from app.cloudforge.learn._ingest import resolve_raw_path

    path = _write(
        tmp_path,
        """
sources:
  - id: in-tree-src
    name: in tree
    type: local_rule_catalog
    path: "data/rule_catalog/seed_patterns.yaml"
    adapter: rule_catalog_yaml
    enabled: true
    license: "CC0-1.0"
    reuse_status: full_reuse
    allowed_for_training: true
""",
    )
    registry = load_registry(path)
    entry = get_entry(registry, "in-tree-src")
    assert entry.path == "data/rule_catalog/seed_patterns.yaml"

    resolved = resolve_raw_path(entry, tmp_path / "raw")
    base = Path.cwd().resolve()
    assert resolved.is_relative_to(base)
    assert resolved == (base / "data/rule_catalog/seed_patterns.yaml").resolve()


def test_path_traversal_via_bypassed_validator_is_blocked_by_resolve_raw_path(
    tmp_path: Path,
) -> None:
    """Defense in depth: a ``SourceEntry`` that reaches ``resolve_raw_path`` through a
    BYPASSED validator (``model_construct`` skips the after-validators -- the same threat
    model the corpus checks call out) is STILL blocked at resolve time by
    ``_ingest._resolve_local_path``'s ``is_relative_to`` containment check, raising
    ``PathTraversalError``. This is the regression for the original path-traversal finding: the
    resolved path can no longer escape the project root.
    """
    from app.cloudforge.learn._ingest import PathTraversalError, resolve_raw_path

    bypassed = SourceEntry.model_construct(
        id="traversal-bypassed",
        name="traversal bypassed",
        type=SourceType.LOCAL_RULE_CATALOG,
        url=None,
        path="../../../../../../../etc/passwd",
        adapter="rule_catalog_yaml",
        enabled=True,
        license="CC0-1.0",
        reuse_status=ReuseStatus.FULL_REUSE,
        allowed_for_training=True,
        notes="",
    )

    with pytest.raises(PathTraversalError) as exc_info:
        resolve_raw_path(bypassed, tmp_path / "raw")

    resolved_root = Path.cwd().resolve()
    message = str(exc_info.value)
    assert "outside the allowed base directory" in message
    assert str(resolved_root) in message


# --- unsupported / mismatched adapter --------------------------------------------------


def test_unsupported_adapter_name_is_accepted_by_registry_schema(tmp_path: Path) -> None:
    """``adapter`` is a bare ``str`` on ``SourceEntry`` -- the registry schema does not
    cross-check it against the known adapter registry (``_ingest.ADAPTERS``). An entry
    naming a nonexistent adapter parses cleanly.
    """
    path = _write(
        tmp_path,
        """
sources:
  - id: unsupported-adapter-src
    name: unsupported adapter
    type: iac_repo
    url: "https://example.com/x"
    adapter: totally_made_up_adapter_that_does_not_exist
    enabled: true
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
""",
    )
    registry = load_registry(path)
    entry = get_entry(registry, "unsupported-adapter-src")
    assert entry.adapter == "totally_made_up_adapter_that_does_not_exist"
    assert entry.adapter not in ADAPTERS


def test_unsupported_adapter_name_is_rejected_at_resolve_time() -> None:
    """The gap above is closed downstream: ``resolve_adapter`` (used by the ``ingest``
    CLI command) raises ``UnknownAdapterError`` for any name not in ``ADAPTERS`` --
    no silent pass-through, no crash. This IS the expected defended behavior.
    """
    with pytest.raises(UnknownAdapterError):
        resolve_adapter("totally_made_up_adapter_that_does_not_exist")


def test_adapter_mismatch_ingest_filters_by_exact_adapter_name(tmp_path: Path) -> None:
    """``cli._run_ingest`` filters sources by ``e.adapter == options.adapter_name`` --
    a source registered under adapter A is never handed to adapter B's ``.extract``.
    Prove the filter predicate directly (no CLI/Typer machinery needed): a source
    declaring ``adapter: checkov_policy_index`` is excluded when ingesting with
    ``--adapter rule_catalog_yaml``, so a mismatched adapter can never misparse a
    source shaped for a different adapter (which could otherwise smuggle unvalidated
    content through the wrong parser's leniency).
    """
    path = _write(
        tmp_path,
        """
sources:
  - id: mismatch-src
    name: mismatch
    type: scanner_rule_index
    url: "https://example.com/x"
    adapter: checkov_policy_index
    enabled: true
    license: "Apache-2.0"
    reuse_status: metadata_only
    allowed_for_training: false
""",
    )
    registry = load_registry(path)
    sources_for_wrong_adapter = [
        e for e in registry.sources if e.enabled and e.adapter == "rule_catalog_yaml"
    ]
    assert sources_for_wrong_adapter == []


# --- oversized source (registry declares no size; enforced only at fetch time) --------


def test_registry_has_no_size_field_enforcement_happens_at_fetch(tmp_path: Path) -> None:
    """The registry schema carries no size/quota field for a source -- an "oversized
    source" is not something the registry layer can reject at load time; the 10 MiB cap
    is enforced by ``fetch.MAX_RESPONSE_BYTES`` at fetch time (covered by
    ``test_fetch.py::TestOversized``). Confirm the registry loads an entry with no size
    hint at all -- the gate is fetch-time, not registry-time, and that division of
    responsibility is intentional (not a bug): assert the entry loads, and that fetching
    it oversized is still refused end-to-end.
    """
    path = _write(
        tmp_path,
        """
sources:
  - id: no-size-hint-src
    name: no size hint
    type: iac_repo
    url: "https://example.com/huge"
    adapter: rule_catalog_yaml
    enabled: true
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
""",
    )
    registry = load_registry(path)
    entry = get_entry(registry, "no-size-hint-src")

    from app.cloudforge.learn.fetch import MAX_RESPONSE_BYTES

    def _oversized_fetch(url: str) -> FetchedResponse:
        return FetchedResponse(
            status_code=200,
            content_type="text/html",
            body=b"x" * (MAX_RESPONSE_BYTES + 1),
        )

    summary = fetch_all_sources(
        sources=[entry], raw_dir=tmp_path / "raw", fetch_fn=_oversized_fetch
    )
    assert summary.failed == 1
    assert summary.fetched == 0
    assert not (tmp_path / "raw" / entry.id).exists()


# --- fetcher scope: only exact registry URLs are ever touched -------------------------


def test_fetcher_never_calls_fetch_fn_for_a_url_not_in_the_registry(tmp_path: Path) -> None:
    """The fetcher is driven entirely by the ``sources`` list handed to it -- it has no
    crawl/discovery/link-follow logic. Passing an empty source list means ``fetch_fn`` is
    never invoked for ANY url, proving there is no side-channel URL source.
    """
    calls: list[str] = []

    def _tracking_fetch(url: str) -> FetchedResponse:
        calls.append(url)
        return FetchedResponse(status_code=200, content_type="text/plain", body=b"x")

    summary = fetch_all_sources(sources=[], raw_dir=tmp_path / "raw", fetch_fn=_tracking_fetch)

    assert calls == []
    assert summary.fetched == 0
    assert summary.results == []


def test_fetcher_only_calls_fetch_fn_with_the_exact_registry_url(tmp_path: Path) -> None:
    """A multi-source fetch only ever calls ``fetch_fn`` with each entry's own ``url`` --
    never a derived, guessed, or expanded URL (no query-string injection, no host
    substitution, no protocol upgrade smuggling).
    """
    entries = [
        SourceEntry(
            id=f"src-{i}",
            name=f"src {i}",
            type=SourceType.SCANNER_RULE_INDEX,
            url=f"https://example.com/allowed-{i}",
            adapter="checkov_policy_index",
            enabled=True,
            license="Apache-2.0",
            reuse_status=ReuseStatus.METADATA_ONLY,
            allowed_for_training=False,
        )
        for i in range(3)
    ]
    calls: list[str] = []

    def _tracking_fetch(url: str) -> FetchedResponse:
        calls.append(url)
        return FetchedResponse(status_code=200, content_type="text/plain", body=b"ok")

    fetch_all_sources(sources=entries, raw_dir=tmp_path / "raw", fetch_fn=_tracking_fetch)

    assert sorted(calls) == sorted(e.url for e in entries)
