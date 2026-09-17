#!/usr/bin/env bash
# commit-msg hook: require the mandated Signed-off-by trailer on every commit.
#
# Require a Signed-off-by trailer. Use `git commit -s`.
#
# Required signer email (first non-empty wins):
#   1. $SIGNOFF_EMAIL
#   2. `git config user.email`
#
# Arg $1 is the path to the commit message file (provided by Git's commit-msg hook).
set -euo pipefail

msg_file="${1:?commit-msg hook expects the commit message file path as argument}"

required_email="${SIGNOFF_EMAIL:-$(git config user.email 2>/dev/null || true)}"

# Escape regex metacharacters in the email (notably the dots) before matching.
escaped_email="$(printf '%s' "$required_email" | sed 's/[.[\*^$()+?{|]/\\&/g')"

if ! grep -qiE '^Signed-off-by: .+ <.+@.+>' "$msg_file"; then
  echo "ERROR: commit message is missing a 'Signed-off-by' trailer." >&2
  echo "       Re-commit with sign-off, e.g.: git commit -s" >&2
  echo "       Policy: every commit needs a Signed-off-by trailer." >&2
  exit 1
fi

# When no required signer is resolvable, accept any well-formed trailer (above).
if [ -n "$required_email" ] && ! grep -qiE "^Signed-off-by: .+ <${escaped_email}>" "$msg_file"; then
  echo "ERROR: 'Signed-off-by' trailer does not match the mandated signer." >&2
  echo "       Required: Signed-off-by: <name> <${required_email}>" >&2
  echo "       Set SIGNOFF_EMAIL or git config user.email to match." >&2
  exit 1
fi

exit 0
