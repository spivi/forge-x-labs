"""Deterministic domain / weakness-family inference for the normalizer (design §9.1/§6).

Adapters don't carry a full ``domains``/``weakness_family`` on ``RawPatternRecord`` (only
a loose ``category`` string), so the normalizer infers them from ``category`` plus
keyword matches over resource types / title / summary. Purely rule-based lookup
tables — NOT a classifier, NOT ML. Split out of ``normalizer.py`` to keep that module
under the 200-line cap (rules/general.md).

``resolve_weakness_family`` additionally honors a source's explicitly declared
``weakness_family`` over keyword inference, so a seed's own classification is
never over-generalized.
"""

from __future__ import annotations

from contextlib import suppress

from app.cloudforge.learn.pattern_enums import Domain, WeaknessFamily
from app.cloudforge.learn.pattern_models import RawPatternRecord

DEFAULT_DOMAIN = Domain.GOVERNANCE

_DOMAIN_RESOURCE_KEYWORDS: tuple[tuple[str, Domain], ...] = (
    ("s3", Domain.STORAGE),
    ("storage", Domain.STORAGE),
    ("bucket", Domain.STORAGE),
    ("iam", Domain.IAM),
    ("role", Domain.IAM),
    ("policy", Domain.IAM),
    ("security_group", Domain.NETWORK),
    ("vpc", Domain.NETWORK),
    ("subnet", Domain.NETWORK),
    ("network", Domain.NETWORK),
    ("kms", Domain.ENCRYPTION),
    ("key", Domain.ENCRYPTION),
    ("log", Domain.LOGGING),
    ("trail", Domain.LOGGING),
    ("secret", Domain.SECRETS),
    ("rds", Domain.DATABASE),
    ("database", Domain.DATABASE),
    ("lambda", Domain.SERVERLESS),
    ("function", Domain.SERVERLESS),
    ("container", Domain.CONTAINERS),
    ("cluster", Domain.CONTAINERS),
    ("pipeline", Domain.CI_CD),
    ("cicd", Domain.CI_CD),
)

_WEAKNESS_KEYWORDS: tuple[tuple[str, WeaknessFamily], ...] = (
    ("passrole", WeaknessFamily.IAM_PASSROLE_RISK),
    ("privilege", WeaknessFamily.EXCESSIVE_PRIVILEGE),
    ("excessive", WeaknessFamily.EXCESSIVE_PRIVILEGE),
    ("public", WeaknessFamily.PUBLIC_EXPOSURE),
    ("expos", WeaknessFamily.PUBLIC_EXPOSURE),
    ("logging", WeaknessFamily.MISSING_LOGGING),
    ("encrypt", WeaknessFamily.MISSING_ENCRYPTION),
    ("rotation", WeaknessFamily.MISSING_ENCRYPTION),
    ("secret", WeaknessFamily.SECRETS_EXPOSURE),
    ("security_group", WeaknessFamily.WEAK_NETWORK_BOUNDARY),
    ("ingress", WeaknessFamily.WEAK_NETWORK_BOUNDARY),
    ("default", WeaknessFamily.INSECURE_DEFAULTS),
    ("unrestricted", WeaknessFamily.UNRESTRICTED_ACCESS),
)


def _domains_from_resource_types(resource_types: list[str]) -> set[Domain]:
    found: set[Domain] = set()
    for resource_type in resource_types:
        lowered = resource_type.lower()
        for keyword, domain in _DOMAIN_RESOURCE_KEYWORDS:
            if keyword in lowered:
                found.add(domain)
    return found


def infer_domains(raw: RawPatternRecord) -> list[Domain]:
    """Infer domains from ``category`` (if a valid ``Domain``) plus resource-type keywords.

    Always returns a non-empty, sorted list — falls back to ``DEFAULT_DOMAIN`` when
    neither signal matches anything.
    """
    domains: set[Domain] = set()
    if raw.category is not None:
        # category isn't guaranteed to be a Domain value (e.g. a scenario_type) —
        # suppress and fall through to the resource-type signal.
        with suppress(ValueError):
            domains.add(Domain(raw.category))

    domains |= _domains_from_resource_types(raw.resource_types)

    if not domains:
        domains.add(DEFAULT_DOMAIN)
    return sorted(domains, key=lambda d: d.value)


def infer_weakness_family(raw: RawPatternRecord) -> WeaknessFamily:
    """Infer the weakness family from title/summary/category keywords, else ``other``."""
    haystack = " ".join([raw.title, raw.summary, raw.category or ""]).lower()
    for keyword, family in _WEAKNESS_KEYWORDS:
        if keyword in haystack:
            return family
    return WeaknessFamily.OTHER


def resolve_weakness_family(raw: RawPatternRecord, declared: str | None) -> WeaknessFamily:
    """Prefer a source-declared ``weakness_family`` over keyword inference (design §9.1).

    ``declared`` is whatever a source (e.g. the ``rule_catalog_yaml`` seed YAML, via
    ``raw_payload["weakness_family"]``) explicitly names. When it is a valid
    ``WeaknessFamily`` value, USE IT — a seed author's explicit classification is more
    reliable than a keyword scan and must not be over-generalized (#93).
    Falls back to :func:`infer_weakness_family` when absent or not a recognized value.
    """
    if declared:
        with suppress(ValueError):
            return WeaknessFamily(declared)
    return infer_weakness_family(raw)
