#!/usr/bin/env python3
"""Vet a single dependency for supply-chain risk before it enters the project.

Standard-library only (urllib/json/difflib) — deliberately zero third-party
imports so the supply-chain gate never has to install a dependency in order to
check a dependency. Queries the public registry for the ecosystem plus OSV.dev
(the unified vulnerability backend for every ecosystem) and prints a structured
risk report. Designed to be called by the dependency-guard skill, but is a
useful standalone CLI.

Usage:
    python vet_dependency.py <ecosystem> <package> [--version X.Y.Z] [--json]

Ecosystems with full registry health checks: python, node, rust.
All ecosystems get OSV CVE lookup (python, node, rust, go, ruby, maven,
packagist, nuget, debian, ubuntu, alpine).

Exit code: 0 = ALLOW, 1 = REVIEW, 2 = BLOCK, 3 = tool/usage error.
The skill is the real gate; this exit code is a convenience for scripting.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

HTTP_TIMEOUT = 8  # seconds — fail fast, the human is waiting

# OSV ecosystem identifiers keyed by our short ecosystem name.
OSV_ECOSYSTEM = {
    "python": "PyPI",
    "node": "npm",
    "rust": "crates.io",
    "go": "Go",
    "ruby": "RubyGems",
    "maven": "Maven",
    "packagist": "Packagist",
    "nuget": "NuGet",
    "debian": "Debian",
    "ubuntu": "Ubuntu",
    "alpine": "Alpine",
}

# Small curated lists of high-traffic packages for typosquat proximity checks.
# Not exhaustive — a near-match to any of these on a package that is NOT itself
# on the list is the classic typosquat signature worth blocking on.
POPULAR = {
    "python": [
        "requests", "urllib3", "numpy", "pandas", "boto3", "setuptools", "pip",
        "certifi", "idna", "charset-normalizer", "python-dateutil", "pyyaml",
        "six", "wheel", "click", "flask", "django", "fastapi", "pydantic",
        "httpx", "aiohttp", "sqlalchemy", "cryptography", "pytest", "scipy",
        "pillow", "matplotlib", "redis", "celery", "jinja2", "werkzeug",
        "beautifulsoup4", "lxml", "tqdm", "rich", "typer", "uvicorn", "openai",
    ],
    "node": [
        "react", "react-dom", "lodash", "axios", "express", "chalk", "commander",
        "debug", "moment", "uuid", "next", "typescript", "webpack", "eslint",
        "jest", "vue", "dotenv", "cors", "body-parser", "mongoose", "socket.io",
        "redux", "rxjs", "node-fetch", "yargs", "inquirer", "semver", "glob",
    ],
    "rust": [
        "serde", "tokio", "clap", "rand", "regex", "log", "syn", "quote",
        "reqwest", "anyhow", "thiserror", "serde_json", "hyper", "futures",
    ],
}


def _get_json(url: str, data: bytes | None = None) -> dict | None:
    """GET/POST JSON with a short timeout. Returns None on any failure."""
    headers = {"User-Agent": "dependency-guard/1.0", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError):
        return None


def _days_since(iso_ts: str | None) -> int | None:
    if not iso_ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = dt.datetime.strptime(iso_ts[:26] if "." in iso_ts else iso_ts, fmt)
            now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
            return (now - parsed).days
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------- #
# Typosquat / name-confusion
# --------------------------------------------------------------------------- #
def check_typosquat(ecosystem: str, name: str, exists: bool) -> dict:
    """Flag names that are suspiciously close to a popular package."""
    popular = POPULAR.get(ecosystem, [])
    lname = name.lower()
    if lname in (p.lower() for p in popular):
        return {"status": "ok", "detail": "exact match to a known popular package"}

    nearest, best = None, 0.0
    for p in popular:
        ratio = SequenceMatcher(None, lname, p.lower()).ratio()
        if ratio > best:
            nearest, best = p, ratio

    # Very close to a popular name but not equal == classic typosquat shape.
    if nearest and best >= 0.85:
        sev = "critical" if not exists else "high"
        return {
            "status": "block",
            "severity": sev,
            "detail": f"name is {best:.0%} similar to popular package '{nearest}'"
            f"{' and does not exist on the registry' if not exists else ''}"
            " — likely typosquat / name confusion",
            "nearest": nearest,
        }
    if not exists:
        return {
            "status": "block",
            "severity": "high",
            "detail": "package does not exist on the registry (dependency-confusion "
            "or typo) — verify the exact name and source",
        }
    return {"status": "ok", "detail": "no close match to known popular packages"}


# --------------------------------------------------------------------------- #
# OSV vulnerability lookup (all ecosystems)
# --------------------------------------------------------------------------- #
def check_osv(ecosystem: str, name: str, version: str | None) -> dict:
    osv_eco = OSV_ECOSYSTEM.get(ecosystem)
    if not osv_eco:
        return {"status": "unknown", "detail": f"no OSV ecosystem mapping for '{ecosystem}'"}
    query: dict = {"package": {"name": name, "ecosystem": osv_eco}}
    if version:
        query["version"] = version
    result = _get_json("https://api.osv.dev/v1/query", json.dumps(query).encode())
    if result is None:
        # Fail closed: a CVE check that could not run must not read as "clean".
        return {"status": "review", "detail": "OSV query failed (network?) — CVE status UNKNOWN"}
    vulns = result.get("vulns", [])
    if not vulns:
        return {"status": "ok", "detail": "no known advisories in OSV", "count": 0}
    ids = [v.get("id", "?") for v in vulns][:10]
    return {
        "status": "block",
        "severity": "critical",
        "detail": f"{len(vulns)} known advisory/advisories: {', '.join(ids)}",
        "count": len(vulns),
        "ids": ids,
    }


# --------------------------------------------------------------------------- #
# Registry health adapters
# --------------------------------------------------------------------------- #
def health_pypi(name: str, version: str | None) -> dict:
    data = _get_json(f"https://pypi.org/pypi/{name}/json")
    if data is None:
        return {"exists": False, "findings": [], "detail": "not found on PyPI"}
    info = data.get("info", {})
    releases = data.get("releases", {})
    findings = []

    target = version or info.get("version")
    files = releases.get(target, []) if target else []
    has_wheel = any(f.get("packagetype") == "bdist_wheel" for f in files)
    has_sdist = any(f.get("packagetype") == "sdist" for f in files)
    if files and has_sdist and not has_wheel:
        findings.append(("review", "sdist-only release — install runs setup.py "
                                    "(arbitrary code execution at install time)"))
    has_attest = any(f.get("attestations") for f in files)
    if not has_attest:
        findings.append(("info", "no PEP 740 attestations / trusted-publishing provenance"))

    upload_times = [f.get("upload_time_iso_8601") for r in releases.values() for f in r]
    upload_times = [t for t in upload_times if t]
    first = min(upload_times) if upload_times else None
    last = max(upload_times) if upload_times else None
    age = _days_since(first)
    if age is not None and age < 90:
        findings.append(("review", f"young package — first release {age} days ago"))
    stale = _days_since(last)
    if stale is not None and stale > 730:
        findings.append(("info", f"possibly unmaintained — last release {stale} days ago"))

    deps = info.get("requires_dist") or []
    runtime = [d for d in deps if "extra ==" not in d]
    if len(runtime) > 20:
        findings.append(("review", f"large blast radius — {len(runtime)} declared "
                                    "runtime dependencies (full transitive count "
                                    "via the resolver)"))

    urls = info.get("project_urls") or {}
    if not urls and not info.get("home_page"):
        findings.append(("info", "no project/source URLs declared"))

    return {
        "exists": True,
        "version": target,
        "release_count": len(releases),
        "first_release_days": age,
        "last_release_days": stale,
        "direct_deps": len(runtime),
        "wheel": has_wheel,
        "sdist_only": has_sdist and not has_wheel,
        "attestations": has_attest,
        "findings": findings,
    }


def health_npm(name: str, version: str | None) -> dict:
    data = _get_json(f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@/')}")
    if data is None:
        return {"exists": False, "findings": [], "detail": "not found on npm"}
    findings = []
    times = data.get("time", {})
    created = times.get("created")
    modified = times.get("modified")
    age = _days_since(created)
    if age is not None and age < 90:
        findings.append(("review", f"young package — created {age} days ago"))
    stale = _days_since(modified)
    if stale is not None and stale > 730:
        findings.append(("info", f"possibly unmaintained — last publish {stale} days ago"))

    maintainers = data.get("maintainers", [])
    if len(maintainers) <= 1:
        findings.append(("info", f"{len(maintainers)} maintainer(s) — account-takeover "
                                 "concentrates risk"))

    target = version or data.get("dist-tags", {}).get("latest")
    vdata = data.get("versions", {}).get(target, {}) if target else {}
    deps = vdata.get("dependencies", {}) or {}
    if len(deps) > 20:
        findings.append(("review", f"large blast radius — {len(deps)} direct dependencies"))
    dist = vdata.get("dist", {})
    has_attest = bool(dist.get("attestations"))
    if not has_attest:
        findings.append(("info", "no npm provenance / sigstore attestation on this version"))

    return {
        "exists": True,
        "version": target,
        "first_release_days": age,
        "last_release_days": stale,
        "maintainers": len(maintainers),
        "direct_deps": len(deps),
        "attestations": has_attest,
        "findings": findings,
    }


def health_crates(name: str, version: str | None) -> dict:
    data = _get_json(f"https://crates.io/api/v1/crates/{name}")
    if data is None:
        return {"exists": False, "findings": [], "detail": "not found on crates.io"}
    findings = []
    crate = data.get("crate", {})
    age = _days_since(crate.get("created_at"))
    if age is not None and age < 90:
        findings.append(("review", f"young crate — created {age} days ago"))
    stale = _days_since(crate.get("updated_at"))
    if stale is not None and stale > 730:
        findings.append(("info", f"possibly unmaintained — last update {stale} days ago"))
    if not crate.get("repository"):
        findings.append(("info", "no source repository declared"))
    return {
        "exists": True,
        "version": version or crate.get("max_stable_version"),
        "first_release_days": age,
        "last_release_days": stale,
        "downloads": crate.get("downloads"),
        "findings": findings,
    }


HEALTH_ADAPTERS = {"python": health_pypi, "node": health_npm, "rust": health_crates}


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def vet(ecosystem: str, name: str, version: str | None) -> dict:
    adapter = HEALTH_ADAPTERS.get(ecosystem)
    health = adapter(name, version) if adapter else {"exists": None, "findings": []}
    exists = health.get("exists")
    # If we have no adapter we cannot prove existence; treat as unknown (True) so
    # the typosquat check still runs its similarity logic without false "missing".
    typo = check_typosquat(ecosystem, name, exists is not False)
    osv = check_osv(ecosystem, name, version or health.get("version"))

    findings = list(health.get("findings", []))
    if typo["status"] == "block":
        findings.append((typo.get("severity", "high"), typo["detail"]))
    if osv["status"] == "block":
        findings.append((osv.get("severity", "critical"), osv["detail"]))
    elif osv["status"] == "review":
        findings.append(("review", osv["detail"]))

    # Verdict: BLOCK on any hard finding; REVIEW on soft flags; else ALLOW.
    if typo["status"] == "block" or osv["status"] == "block" or exists is False:
        verdict = "BLOCK"
    elif any(sev in ("review", "high") for sev, _ in findings) or osv["status"] == "review":
        verdict = "REVIEW"
    else:
        verdict = "ALLOW"

    return {
        "package": name,
        "ecosystem": ecosystem,
        "version": version or health.get("version"),
        "verdict": verdict,
        "checks": {
            "typosquat": typo["status"],
            "cves": osv["status"],
            "health": health.get("exists"),
        },
        "osv": osv,
        "typosquat": typo,
        "health": health,
        "findings": [{"severity": s, "detail": d} for s, d in findings],
    }


def render(report: dict) -> str:
    sym = {"ok": "✓", "block": "✗", "review": "⚠", "unknown": "?", True: "✓", False: "✗", None: "?"}
    c = report["checks"]
    lines = [
        f"## Dependency Guard: {report['package']}@{report.get('version') or '?'} "
        f"({report['ecosystem']})",
        f"Verdict: {report['verdict']}",
        f"Checks: typosquat {sym.get(c['typosquat'], '?')} | "
        f"CVEs {sym.get(c['cves'], '?')} | health {sym.get(c['health'], '?')}",
    ]
    if report["findings"]:
        lines.append("Findings:")
        for f in report["findings"]:
            lines.append(f"  - [{f['severity']}] {f['detail']}")
    else:
        lines.append("Findings: none")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Vet a dependency for supply-chain risk.")
    ap.add_argument("ecosystem", choices=sorted(OSV_ECOSYSTEM), help="package ecosystem")
    ap.add_argument("package", help="package name")
    ap.add_argument("--version", help="specific version to vet (recommended)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    report = vet(args.ecosystem, args.package, args.version)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}[report["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
