#!/usr/bin/env bash
# PreToolUse gate for the dependency-guard skill. Wired for two matchers:
#   - Bash          : catches dependency add / source-trust commands
#   - Edit|Write|MultiEdit : catches a dependency added by editing a manifest
#
# Reads the hook JSON on stdin and emits an "ask" permission decision when a
# NEW dependency (or package source) is about to enter the project, so the add
# can't land unconsidered. Stays silent (exit 0, no output) otherwise — notably
# for lockfile reinstalls and for manifest edits that don't touch a dependency.
#
# It does not hard-block; the skill itself is the real vet -> pin -> verify gate.
# This is the deterministic trigger, which matters because description-based
# skill triggering under-fires on dependency adds (they look like trivial
# one-step tasks). Fast on purpose — pure bash + grep, degrades without jq.
set -euo pipefail

input="$(cat)"
have_jq() { command -v jq >/dev/null 2>&1; }
jqr() { printf '%s' "$input" | jq -r "$1" 2>/dev/null || true; }

ask() {
  # $1 = permissionDecisionReason (kept on one line; no embedded double quotes)
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"%s"}}\n' "$1"
  exit 0
}

tool=""
have_jq && tool="$(jqr '.tool_name // empty')"

case "$tool" in
  Edit | Write | MultiEdit)
    # Manifest-edit path needs jq to read the file path / changed text.
    have_jq || exit 0
    fp="$(jqr '.tool_input.file_path // empty')"
    [ -z "$fp" ] && exit 0
    manifest='(^|/)(pyproject\.toml|requirements[^/]*\.txt|package\.json|Cargo\.toml|go\.mod|Gemfile|composer\.json|pom\.xml|build\.gradle(\.kts)?|[^/]*\.csproj)$'
    printf '%s' "$fp" | grep -Eq "$manifest" || exit 0

    # Text being introduced (Edit: new_string, Write: content, MultiEdit: all edits).
    changed="$(jqr '.tool_input.new_string // .tool_input.content // ([.tool_input.edits[]?.new_string] | join("\n")) // empty')"
    # A dependency declaration almost always carries a version token. If we
    # can't read the change, fail safe toward asking.
    depline='([\^~][0-9]+\.[0-9]|[\"=> ][0-9]+\.[0-9]+|==[0-9]|>=[0-9]|~>[[:space:]]*[0-9]|"version"[[:space:]]*:|gem[[:space:]]+["'\'']|require[[:space:]]+[^[:space:]]+[[:space:]]+v?[0-9])'
    if [ -z "$changed" ] || printf '%s' "$changed" | grep -Eq "$depline"; then
      ask "dependency-guard: this edits a dependency manifest ($fp) to add or change a dependency — a supply-chain + breaking-update trust decision. Run the dependency-guard skill (vet -> pin -> verify) before applying it."
    fi
    exit 0
    ;;
  Bash | "")
    # Bash path (or no jq: scan the raw payload, which contains the command).
    if have_jq; then
      cmd="$(jqr '.tool_input.command // empty')"
      [ -z "$cmd" ] && cmd="$input"
    else
      cmd="$input"
    fi
    [ -z "$cmd" ] && exit 0

    # Lockfile reinstalls / build-from-manifest — no new dependency enters.
    reinstall='(pip[0-9]* install[[:space:]]+(-r|--requirement|-e[[:space:]]|\.)|npm (ci|(i|install)[[:space:]]*$)|pnpm install[[:space:]]*$|yarn install|bundle install|poetry install|pdm install|cargo build)'
    printf '%s' "$cmd" | grep -Eq "$reinstall" && exit 0

    # Dependency add / source-trust expansion across ecosystems.
    add='(poetry add|uv add|pdm add|yarn add|pnpm add|cargo add|bundle add|gem install|composer require|add-apt-repository|brew tap|brew install|apk add|pacman -S|npm (i|install|add)|pip[0-9]* install|apt(-get)? install|dnf install|yum install|go get)'
    if printf '%s' "$cmd" | grep -Eq "$add"; then
      ask "dependency-guard: this command adds a dependency or package source — a supply-chain + breaking-update trust decision. Run the dependency-guard skill (vet -> pin -> verify) before allowing it. Lockfile reinstalls are exempt."
    fi
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
