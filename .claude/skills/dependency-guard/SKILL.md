---
name: dependency-guard
description: "Supply-chain and stability gate for bringing dependencies into the project. Use whenever a new library/package is added OR an existing one is upgraded — across ANY ecosystem: Python (poetry/pip/uv/pdm), Node (npm/yarn/pnpm), Rust (cargo), Go, Ruby (gem/bundler), PHP (composer), Java (maven/gradle), .NET (nuget), and system package managers (apt/brew/dnf/yum/apk/pacman). Triggers on: /dependency-guard, add a dependency, install a package, 'we need <library>', 'npm i', 'poetry add', 'pip install', 'cargo add', 'brew install', 'apt install', 'brew tap', add-apt-repository, bump/upgrade/update a package, new requirement, vet a library, is this package safe. Vets for typosquatting, known CVEs, maintainer/provenance risk, and untrusted sources; pins per best practice; verifies the build still passes."
---

# Dependency Guard

A gate that runs **before** a dependency lands in the project. Two risks, in
priority order:

1. **Supply-chain attack** (primary) — typosquatting / name confusion, known
   CVEs, compromised or low-reputation packages, missing provenance, oversized
   transitive trust surface, untrusted system sources (third-party taps/PPAs/repos).
2. **Operational breakage from updates** (secondary) — pin per best practice,
   require lockfile hash pinning, and run the test suite so a breaking upgrade
   surfaces immediately.

This is the **single-package intake/upgrade gate**. The `security-review` skill
remains the whole-tree periodic auditor — don't duplicate it here.

## When this runs

Either a package-manager add/install command or an edit to a manifest
(`pyproject.toml`, `requirements*.txt`, `package.json`, `Cargo.toml`, `go.mod`,
`Gemfile`, `composer.json`) brought you here. Lockfile *reinstalls*
(`poetry install`, `pip install -r`, `npm ci`, `bundle install`, `cargo build`)
are **not** intake events — no new trust decision — so skip the gate for those
and just let them run.

## Workflow

Work through these in order. Create a todo per step so nothing is skipped.

### 1. Identify the change

- **Ecosystem & manager** — from the command, or from the lockfiles present.
- **Intake or update?** Update = the package already appears in the manifest.
- **Package name + target version.** If no version was given, resolve the
  version you would actually install (latest, or the constraint's ceiling) and
  vet *that* — vetting "latest" abstractly is meaningless.

### 2. Vet (supply-chain)

Run the bundled engine — it queries the registry + OSV.dev (unified CVE backend)
with zero third-party imports:

```bash
python3 .claude/skills/dependency-guard/scripts/vet_dependency.py \
    <ecosystem> <package> --version <X.Y.Z> --json
```

`<ecosystem>` ∈ `python node rust go ruby maven packagist nuget debian ubuntu alpine`.
Full registry-health checks exist for `python`, `node`, `rust`; every ecosystem
gets the OSV CVE lookup and typosquat check.

The script emits a verdict and findings. **It is an input to your judgment, not
the final word** — read the findings and apply the decision gate below.

**Always run the vet — especially when the package looks obviously fine.** A
familiar, popular name is exactly the case where reasoning-from-memory fails:
you cannot know from training data that *this version* shipped a malicious
release, was just yanked, or carries a fresh CVE. The compromised-but-legit
package (event-stream, ua-parser-js, the xz pattern) is the whole reason this
gate exists. "I recognize this package" is not a substitute for the check.

For **system package managers** (apt/brew/dnf/yum/apk/pacman) the registry model
doesn't apply. Read `references/system-package-managers.md` and gate on the
*trust event* (is a third-party tap/PPA/repo being added? is signature
verification being bypassed?) rather than per-package maintainer health.

### 3. Decision gate

| Verdict | Meaning | Action |
|---|---|---|
| **ALLOW** | clean across checks | proceed to pin + install |
| **REVIEW** | soft flags (young pkg, single maintainer, large blast radius, sdist-only, no provenance, OSV unreachable) | surface the report, give your recommendation, **ask the human** before proceeding |
| **BLOCK** | typosquat match, known CVE in target version, package missing from registry, untrusted third-party source, or signature bypass | **HARD STOP. Do not install.** Report and hand back to the human. There is no in-skill override — if they truly need it, they install manually, outside the skill. |

A failed OSV query reads as **REVIEW**, never ALLOW — a CVE check that could not
run is not a clean bill of health.

### 4. Pin (best practice, auto-detected)

Determine **application vs library** (see `references/pinning-and-provenance.md`
for the per-manager mechanics):

- **Application** (a service/CLI, not published to a registry) — default, and
  the fallback when unsure. Express the version intent, then rely on a
  **committed lockfile that hash-pins the full resolved tree**.
- **Library** (publishes to a registry) — keep a **compatible range**
  (`>=x,<x+1`) in the manifest so consumers can resolve, but still lock + hash
  for dev/CI.

Then perform the add with that pin and **confirm the lockfile carries hashes**
for the new artifact(s). If hashes are missing, that's a finding — fix it before
proceeding.

### 5. Verify (stability)

Run the project's test suite to catch breakage the moment it's introduced:

```bash
PYTHONPATH=. .venv/bin/pytest -q   # Python; use the ecosystem equivalent otherwise
```

For an **update**, also do the breaking-change diligence in
`references/update-flow.md` (semver major-jump detection, changelog review,
re-vet the new version). Report test results explicitly — a green suite is part
of the verdict, a red suite is a finding.

### 6. Report

Emit the verdict report (same shape as `security-review` for consistency):

```
## Dependency Guard: <pkg>@<version>  (intake | update)
Ecosystem: <python | node | ... | system:apt>
Risk: LOW / MEDIUM / HIGH / CRITICAL
Checks: typosquat ✓ | CVEs ✓ | maintainer/health ⚠ | provenance/blast-radius ✓
Findings:
  - <severity> — <detail> — Action: <fix>
Pin applied: <exact manifest line>      Lockfile hashes: present | MISSING
Tests: <pass/fail summary>
Verdict: ALLOW | REVIEW | BLOCK
```

## Reference material

- `references/pinning-and-provenance.md` — per-manager pinning + hash/lockfile
  mechanics, PEP 740 / npm provenance, app-vs-library decision.
- `references/system-package-managers.md` — apt/brew/dnf/apk trust-event gating.
- `references/update-flow.md` — semver, changelog, and test-breakage playbook
  for upgrades.

## Hardening the gate

Skills trigger probabilistically, and dependency adds under-fire badly (~22%
recall) because they look like trivial one-step tasks — so a `PreToolUse` hook
is the *primary* enforcement here, not an optional extra. It is already wired in
`.claude/settings.json` via `scripts/depguard_hook.sh`, with two matchers:
`Bash` (catches `poetry add`/`npm i`/`brew tap`/… while exempting lockfile
reinstalls) and `Edit|Write|MultiEdit` (catches a dep added by editing a
manifest directly). It emits an `ask` decision so the add can't land
unconsidered. See `references/pinning-and-provenance.md` (Hook section) for the
detection rules and how to tune them.
