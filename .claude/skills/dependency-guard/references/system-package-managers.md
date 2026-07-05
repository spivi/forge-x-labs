# System Package Managers — Trust-Event Gating

For `apt`, `apt-get`, `brew`, `dnf`, `yum`, `apk`, `pacman` the "malicious
maintainer publishes to a public registry" threat model barely applies — these
install from **curated, cryptographically signed** distribution repositories.
So don't run per-package maintainer-health scoring here; it produces noise.
Instead, gate on the events that actually expand your trust surface.

## The real risk: adding a source, not installing a package

A package from the OS's official signed repo is about as trustworthy as that
distro. The danger is when a command **adds a new, unvetted source** or
**weakens verification**. Those are the BLOCK-worthy events:

| Event | Command shape | Why it's dangerous |
|---|---|---|
| Third-party Homebrew tap | `brew tap <user>/<repo>`, `brew install <user>/<repo>/<f>` | Arbitrary formula from an unreviewed GitHub repo runs install logic on your machine |
| Custom apt PPA / repo | `add-apt-repository ppa:...`, a new file in `/etc/apt/sources.list.d/`, `curl ... | sudo apt-key add -` | Adds a publisher whose GPG key now signs packages you trust implicitly |
| Custom yum/dnf repo | a new `*.repo` under `/etc/yum.repos.d/`, `dnf config-manager --add-repo` | Same: new trusted signer |
| Piped installer | `curl ... | bash`, `wget -O- ... | sh` | No signature, no review, runs as whatever user invoked it — treat as BLOCK |
| Verification bypass | `--allow-unauthenticated`, `--allow-untrusted` (apk), `--nogpgcheck` (dnf/yum), `--force`, `[trusted=yes]` in a source line | Disables the signature check that is the whole security model |

## Gate procedure

1. **Is a new source being added?** (tap / PPA / repo / piped installer)
   - Yes → **BLOCK** by default. Surface: who publishes it, the URL, whether
     it's HTTPS, whether a GPG key is being imported and from where. Hand back
     to the human with the trust question stated plainly. Don't proceed on a
     third-party source without an explicit human decision.
   - No (official repo) → continue.
2. **Is verification being bypassed?** (any flag in the table above) → **BLOCK**.
   The fix is almost always "don't" — find the properly signed package instead.
3. **CVE check** — the package's ecosystem *is* in OSV for the major distros:
   ```bash
   python3 .claude/skills/dependency-guard/scripts/vet_dependency.py \
       debian <pkg> --version <ver>      # or: ubuntu, alpine
   ```
   (RHEL/Arch/Homebrew aren't OSV ecosystems; rely on the distro's own
   advisory feed and `brew audit` there.)
4. **Pin for reproducibility** where it matters — `apt install pkg=1.2.3-1`,
   `apk add pkg=1.2.3-r0`, Brewfile with versions, or pin in your container
   base image / Dockerfile rather than at ad-hoc install time.

## Containers / Dockerfiles

Most system-package risk in real projects lives in Dockerfiles. Apply the same
gate to `RUN apt-get install ...` lines:

- Pin versions (`apt-get install -y pkg=1.2.3`), keep `apt-get update` in the
  same `RUN` layer, and don't add PPAs without the trust review above.
- Never `--allow-unauthenticated` or pipe a remote script to a shell.
- Prefer official base images with a digest pin
  (`FROM debian:12@sha256:...`) — that's the system-level equivalent of a
  hash-pinned lockfile.
