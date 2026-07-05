# dependency-guard — Design Spec

**Date:** 2026-05-25
**Author:** Alex Spivakovsky (brainstormed with Claude)
**Status:** Approved design → ready to draft

## Purpose

A skill that fires whenever a new dependency is brought into the project or an
existing one is upgraded, and acts as a gate that:

1. **Reduces supply-chain risk** (the primary threat) — typosquatting / name
   confusion, known CVEs, compromised or low-reputation packages, missing
   provenance, oversized transitive trust surface, and untrusted system
   package sources (third-party taps/PPAs/repos).
2. **Reduces operational breakage from updates** (the secondary risk) — by
   pinning per best practice, requiring lockfile hash pinning, and running the
   test suite after the change so a breaking upgrade is caught immediately.

It is the **single-package intake/upgrade gate**, complementary to the existing
`security-review` skill (whole-tree periodic auditor). No trigger overlap.

## Scope

- **Events governed:** dependency **intake** (net-new package) and **updates**
  (bump/upgrade of an existing package). Both are supply-chain events.
- **Out of scope:** whole-tree periodic audits (stays with `security-review`).

## Triggering (two layers)

1. **Description-triggered skill** — consulted whenever the conversation
   involves adding/upgrading a package ("add httpx", "we need redis", "bump
   pydantic", "npm i lodash", running a package-manager add command).
2. **Hook gate** (`.claude/settings.json`, `PreToolUse`) — deterministic
   "whenever" coverage that survives the model forgetting to consult the skill.
   - **Matches** add/install-of-a-named-package and source-trust-expansion
     commands across ecosystems:
     `poetry add`, `uv add`, `pip install <pkg>`, `pdm add`,
     `npm i/install <pkg>`, `yarn add`, `pnpm add`,
     `cargo add`, `go get`, `gem install`, `bundle add`, `composer require`,
     `apt[-get] install`, `add-apt-repository`, `brew install`, `brew tap`,
     `dnf/yum install`, `apk add`, `pacman -S`,
     and edits to `pyproject.toml` / `requirements*.txt` / `package.json` /
     `Cargo.toml` / `go.mod` / `Gemfile` / `composer.json`.
   - **Excludes** lockfile reinstalls (no new trust decision):
     `poetry install`, `pip install -r`, `npm ci`, `npm install` (no args),
     `bundle install`, `cargo build`, `go mod download`, `pnpm install`.

## Decision model

The gate produces one of three verdicts:

- **ALLOW** — clean across all checks → proceed (pin, install, verify).
- **REVIEW** — soft flags (e.g. young package, single maintainer, large
  transitive blast radius) → surface report, recommend, ask the human.
- **BLOCK** — typosquat match, known CVE in the target version, untrusted
  third-party source, or signature-verification bypass → **hard stop, no
  override.** The skill does not perform the install; the human must take over
  manually outside the skill. (Strictest setting, chosen deliberately.)

## Workflow (SKILL.md body)

1. **Detect ecosystem & manager** from manifests/lockfiles present
   (`pyproject.toml`+`poetry.lock`, `requirements.txt`, `uv.lock`, `package.json`,
   `Cargo.toml`, `go.mod`, `Gemfile`, `composer.json`) or from the command that
   triggered the hook.
2. **Vet** — run `scripts/vet_dependency.py <ecosystem> <pkg> [version]` →
   structured risk report (the four checks below). System package managers use
   the trust-event variant.
3. **Decision gate** — ALLOW / REVIEW / BLOCK as above.
4. **Pin** per policy (see Pinning), **perform the add**, **confirm the lockfile
   hash-pins** the resolved artifact(s); flag if hashes are missing.
5. **Verify** — run the project test suite
   (`PYTHONPATH=. .venv/bin/pytest -q` for Python; ecosystem equivalent
   otherwise) to catch breakage; report pass/fail.
6. **Report** — emit the verdict report (format below).

## Vetting checks

### Tier 1 — language registries (full four-check gate)

| Ecosystem | Managers | Registry API | CVE source | Provenance |
|---|---|---|---|---|
| Python | poetry, pip, uv, pdm | PyPI JSON | OSV / pip-audit | PEP 740 attestations |
| Node | npm, yarn, pnpm | npm registry | OSV / npm audit | npm provenance (sigstore) |
| Rust | cargo | crates.io | OSV / cargo-audit | — |
| Go | go mod | deps.dev | OSV / govulncheck | — |
| Ruby | bundler, gem | rubygems | OSV / bundler-audit | — |
| PHP / Java / .NET | composer, maven/gradle, nuget | respective | OSV | — |

The four checks:

1. **Name / typosquat** — exact name exists on the registry; not a typo-neighbor
   of a popular package; not a dependency-confusion shadow of an internal name.
2. **Known CVEs** — OSV query (unified backend across all ecosystems) for the
   target version + transitive deps; shell out to the native auditor
   (`pip-audit`, `npm audit`, `cargo-audit`, …) when available.
3. **Maintainer & release health** — package age, last-release date, cadence,
   yanked releases, maintainer count, project URLs present.
4. **Provenance & transitive blast radius** — PEP 740 / npm provenance
   attestations if present; wheel-vs-sdist (sdist = install-time code-exec risk);
   count of NEW transitive deps introduced.

**OSV.dev is the unifying CVE backend** for every ecosystem (keeps the vet
script DRY). No API keys required for PyPI JSON / npm registry / crates.io / OSV.

### Tier 2 — system / OS package managers (trust-event focus)

For `apt`, `apt-get`, `brew`, `dnf`, `yum`, `apk`, `pacman` the registry-maintainer
model does not apply (curated, signed repos). The gate adapts:

- **Source trust (primary)** — gate hard when a *third-party tap / PPA / custom
  repo* is being added (`brew tap`, `add-apt-repository`, new `.repo` file).
  That is the real supply-chain expansion event.
- **Signature/GPG verification** — BLOCK on bypass flags
  (`--allow-unauthenticated`, `--force`, unsigned repos).
- **CVE lookup** — OSV (Debian / Ubuntu / Alpine ecosystems are in OSV).
- **Version pinning** — recommend a pinned version for reproducibility.
- Plain installs from official signed repos: light OSV CVE check + pin nudge,
  then proceed.

## Pinning policy (auto-detected)

- **Application** (default; service/CLI, not published to a registry):
  exact-pin intent + rely on the committed lockfile for full-tree hash pinning.
  Poetry → ensure `poetry.lock` committed with hashes; pip → `requirements.txt`
  via `pip-compile --generate-hashes`; npm → committed `package-lock.json`.
- **Library** (publishes to a registry / has build-packaging config): keep a
  compatible range (`>=x,<x+1`) in the manifest so consumers can resolve, but
  still lock + hash for dev/CI.
- **Fallback when ambiguous:** app-style (stricter).
- **Always:** hashes required in the lockfile; flag if missing.

## Update / upgrade flow (the #2 risk)

On a version bump, additionally:

- Detect **semver major jump** (breaking by convention).
- Fetch **changelog / release notes** for the diff range.
- **Re-vet the new version** (CVE/provenance can differ per release).
- Run the **full test suite** and report breakage explicitly.

## Output — verdict report

```
## Dependency Guard: <pkg>@<version>  (intake | update)
Ecosystem: <python|node|rust|...|system:apt>
Risk: LOW / MEDIUM / HIGH / CRITICAL
Checks: typosquat ✓ | CVEs ✓ | maintainer/health ⚠ | provenance/blast-radius ✓
Findings:
  - <severity> — <detail> — Action: <fix>
Pin applied: <exact line>   Lockfile hashes: present | MISSING
Tests: <pass/fail summary>
Verdict: ALLOW | REVIEW | BLOCK
```

(Same shape as `security-review` for consistency.)

## Bundled layout

```
dependency-guard/
├── SKILL.md                          # workflow + ecosystem dispatch
├── scripts/
│   └── vet_dependency.py             # registry adapters; OSV unified CVE backend
└── references/
    ├── pinning-and-provenance.md     # per-manager pinning, hash/lock, PEP740 / npm provenance
    ├── system-package-managers.md    # apt/brew/dnf/apk: tap/PPA/repo trust, GPG, pinning
    └── update-flow.md                # semver / changelog / test-breakage playbook
```

Plus a **hook snippet** for `.claude/settings.json` delivered with the skill.

## Relationship to existing skills

- `security-review` — whole-tree periodic auditor (pip-audit/bandit). Unchanged.
- `dependency-guard` — single-package intake/upgrade gate. New. No trigger overlap.

## Validation plan (skill-creator)

Draft SKILL.md → 2–3 realistic test prompts (e.g. "add the `reqests` package"
[typosquat], "bump `pydantic` to v3" [major update], "brew tap a third-party
formula") → run with/without skill → review outputs + benchmark → iterate →
optimize description for triggering.
