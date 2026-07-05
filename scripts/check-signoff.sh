#!/usr/bin/env bash
# commit-msg hook: require the mandated Signed-off-by trailer on every commit.
#
# Enforces the project sign-off policy (.dev-context/rules/git.md, Commit Sign-off):
# every commit MUST carry a `Signed-off-by: <name> <email>` trailer. Use `git commit -s`
# with `git config user.name`/`user.email` set to that identity.
#
# Required signer email resolution (first non-empty wins):
#   1. $SIGNOFF_EMAIL                     (env override)
#   2. SIGNOFF_EMAIL in project.conf      (set by setup.sh from git config)
#   3. `git config user.email`            (fall back to the committer's own identity)
# Matching on the email (case-insensitive) keys off the stable identity component.
#
# Arg $1 is the path to the commit message file (provided by Git's commit-msg hook).
set -euo pipefail

msg_file="${1:?commit-msg hook expects the commit message file path as argument}"

_conf_value() {
    local conf
    conf="$(git rev-parse --show-toplevel 2>/dev/null)/.dev-context/project.conf"
    [ -f "$conf" ] || return 0
    sed -n "s/^$1=//p" "$conf" 2>/dev/null | head -n1 | sed 's/[[:space:]]*#.*$//; s/^"//; s/"$//'
}

required_email="${SIGNOFF_EMAIL:-$(_conf_value SIGNOFF_EMAIL)}"
required_email="${required_email:-$(git config user.email 2>/dev/null || true)}"

# Escape regex metacharacters in the email (notably the dots) before matching.
escaped_email="$(printf '%s' "$required_email" | sed 's/[.[\*^$()+?{|]/\\&/g')"

if ! grep -qiE '^Signed-off-by: .+ <.+@.+>' "$msg_file"; then
  echo "ERROR: commit message is missing a 'Signed-off-by' trailer." >&2
  echo "       Re-commit with sign-off, e.g.: git commit -s" >&2
  echo "       Policy: .dev-context/rules/git.md (Commit Sign-off)." >&2
  exit 1
fi

# When no required signer is resolvable, accept any well-formed trailer (above).
if [ -n "$required_email" ] && ! grep -qiE "^Signed-off-by: .+ <${escaped_email}>" "$msg_file"; then
  echo "ERROR: 'Signed-off-by' trailer does not match the mandated signer." >&2
  echo "       Required: Signed-off-by: <name> <${required_email}>" >&2
  echo "       Set SIGNOFF_EMAIL in .dev-context/project.conf or fix your git identity." >&2
  exit 1
fi

exit 0
