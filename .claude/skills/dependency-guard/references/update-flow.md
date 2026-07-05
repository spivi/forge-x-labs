# Update / Upgrade Flow

Upgrading an existing dependency carries both risks at once: the new release is
a fresh supply-chain trust decision (a maintainer account could have been
compromised between versions), and the new behavior can break your build. Run
the full intake vet on the *new version*, plus this breaking-change diligence.

## Steps

1. **Re-vet the target version.** Don't assume "we already trust this package."
   CVEs and provenance are per-version, and the most damaging supply-chain
   incidents are malicious *releases* of previously-legitimate packages
   (event-stream, ua-parser-js, the xz backdoor pattern). Run:
   ```bash
   python3 .claude/skills/dependency-guard/scripts/vet_dependency.py \
       <ecosystem> <pkg> --version <NEW_VERSION> --json
   ```
   Apply the same ALLOW / REVIEW / BLOCK gate. A brand-new release (published
   hours ago) of a critical dependency deserves extra scrutiny — most malicious
   releases are caught and yanked within days, so "let it age" is a valid call.

2. **Classify the version jump (semver).** `MAJOR.MINOR.PATCH`:
   - **Major** (`2.x → 3.x`) — breaking by convention. Expect API changes;
     read the migration guide. Treat as high-risk for breakage.
   - **Minor** (`2.3 → 2.4`) — new features, should be backward-compatible, but
     verify; "minor" is a promise, not a guarantee.
   - **Patch** (`2.3.1 → 2.3.2`) — bug/security fixes; lowest breakage risk and
     often the *reason* you're upgrading (a CVE fix).
   - `0.x` versions: treat every bump as potentially breaking — semver
     guarantees don't apply below 1.0.

3. **Read the changelog / release notes for the diff range.** Look for:
   removed/renamed APIs, changed defaults, dropped runtime versions
   (e.g. "drops Python 3.9"), and new transitive dependencies. The changelog is
   usually in the repo's releases page, `CHANGELOG.md`, or the registry page.

4. **Apply the pin and refresh the lockfile** (see
   `pinning-and-provenance.md`). Confirm hashes regenerated for the new version.

5. **Run the full test suite — this is the breakage gate.**
   ```bash
   PYTHONPATH=. .venv/bin/pytest -q     # or the ecosystem equivalent
   ```
   A red suite after an upgrade is a finding, not a footnote: report exactly
   which tests broke and whether it's an intended API change you must adapt to,
   or a regression in the dependency. Don't "fix" tests to make a breaking
   upgrade pass without understanding why.

6. **Type/lint check where available** — `mypy --strict`, `tsc --noEmit`,
   `cargo check` catch signature-level breakage that tests might miss.

## When the upgrade is itself the CVE fix

Common case: pip-audit / npm audit flags an installed version and the fix is to
upgrade. Then the upgrade is *mandatory*, and the job is to land it with the
least breakage:

- Prefer the **smallest version that clears the advisory** (often a patch
  release on your current major line) to minimize behavioral change.
- If only a major release fixes it, budget for the migration — don't silently
  pull a breaking major just to clear an audit warning.
- Re-run the vet afterward to confirm the advisory is actually resolved in the
  version you landed.
