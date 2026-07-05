#!/usr/bin/env bash
# setup.sh — Interactive project bootstrapper for dev-template
#
# Usage: ./setup.sh
# Requires: bash 4+, sed, python3, git
#
# This script:
#   1. Prompts for project identity (name, ID, ticket prefix, flavor)
#   2. Replaces all {{PLACEHOLDER}} tokens throughout the template
#   3. Applies the selected flavor (basic / cli / fastapi-modular)
#   4. Creates Python venv and installs dependencies
#   5. Initializes git with pre-commit hooks
#   6. Optionally creates Linear team + Notion space via MCP
#   7. Syncs cross-tool configurations

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================
# COLORS
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# ============================================================
# 1. INTERACTIVE PROMPTS
# ============================================================

echo ""
echo -e "${BOLD}=== Dev Template — Project Setup ===${NC}"
echo ""

# Project Name (snake_case)
read -rp "Project name (snake_case, e.g. my_project): " PROJECT_NAME
if [[ ! "$PROJECT_NAME" =~ ^[a-z][a-z0-9_]*$ ]]; then
  fail "Project name must be snake_case (lowercase letters, digits, underscores)"
fi

# Project ID (3-4 uppercase letters)
DEFAULT_ID=$(echo "$PROJECT_NAME" | tr '[:lower:]' '[:upper:]' | cut -c1-3)
read -rp "Project ID (3-4 uppercase letters, default: $DEFAULT_ID): " PROJECT_ID
PROJECT_ID="${PROJECT_ID:-$DEFAULT_ID}"
if [[ ! "$PROJECT_ID" =~ ^[A-Z]{2,5}$ ]]; then
  fail "Project ID must be 2-5 uppercase letters"
fi

# Linear Team / Ticket Prefix
read -rp "Linear ticket prefix (default: $PROJECT_ID): " TICKET_PREFIX
TICKET_PREFIX="${TICKET_PREFIX:-$PROJECT_ID}"
if [[ ! "$TICKET_PREFIX" =~ ^[A-Z]{2,5}$ ]]; then
  fail "Ticket prefix must be 2-5 uppercase letters"
fi

# Project Description
read -rp "One-line description: " PROJECT_DESCRIPTION
PROJECT_DESCRIPTION="${PROJECT_DESCRIPTION:-A Python project}"

# Author
read -rp "Author name: " AUTHOR_NAME
AUTHOR_NAME="${AUTHOR_NAME:-Developer}"
read -rp "Author email: " AUTHOR_EMAIL
AUTHOR_EMAIL="${AUTHOR_EMAIL:-dev@example.com}"

# Flavor selection
echo ""
echo "Available flavors:"
echo "  1) basic            — Minimal Python project"
echo "  2) cli              — CLI tool with Typer + Rich"
echo "  3) fastapi-modular  — FastAPI + PostgreSQL + Redis"
read -rp "Select flavor [1/2/3] (default: 1): " FLAVOR_NUM
case "${FLAVOR_NUM:-1}" in
  1) FLAVOR="basic" ;;
  2) FLAVOR="cli" ;;
  3) FLAVOR="fastapi-modular" ;;
  *) fail "Invalid flavor selection" ;;
esac

# MCP integrations
echo ""
read -rp "Auto-create Linear team via Claude MCP? (y/N): " CREATE_LINEAR
read -rp "Auto-create Notion workspace via Claude MCP? (y/N): " CREATE_NOTION
read -rp "Configure Google Stitch MCP for UI design? (y/N): " SETUP_STITCH

# ============================================================
# 2. PLACEHOLDER REPLACEMENT
# ============================================================

echo ""
info "Applying configuration..."

# macOS sed requires -i '' (no backup), Linux uses -i
if [[ "$(uname)" == "Darwin" ]]; then
  SED_CMD() { sed -i '' "$@"; }
else
  SED_CMD() { sed -i "$@"; }
fi

# Escape special characters for sed replacement
escape_sed() {
  printf '%s' "$1" | sed 's/[&/\]/\\&/g'
}

ESCAPED_DESC=$(escape_sed "$PROJECT_DESCRIPTION")
ESCAPED_AUTHOR=$(escape_sed "$AUTHOR_NAME")
ESCAPED_EMAIL=$(escape_sed "$AUTHOR_EMAIL")
SETUP_DATE=$(date -u +"%Y-%m-%d")

# Find all text files (exclude .git, .venv, node_modules, this script)
while IFS= read -r -d '' file; do
  SED_CMD \
    -e "s|{{PROJECT_NAME}}|${PROJECT_NAME}|g" \
    -e "s|{{PROJECT_ID}}|${PROJECT_ID}|g" \
    -e "s|{{TICKET_PREFIX}}|${TICKET_PREFIX}|g" \
    -e "s|{{PROJECT_DESCRIPTION}}|${ESCAPED_DESC}|g" \
    -e "s|{{AUTHOR_NAME}}|${ESCAPED_AUTHOR}|g" \
    -e "s|{{AUTHOR_EMAIL}}|${ESCAPED_EMAIL}|g" \
    -e "s|{{SETUP_DATE}}|${SETUP_DATE}|g" \
    "$file"
done < <(find "$SCRIPT_DIR" \
  -type f \
  \( -name "*.md" -o -name "*.yml" -o -name "*.yaml" -o -name "*.json" \
     -o -name "*.sh" -o -name "*.py" -o -name "*.toml" -o -name "*.cfg" \
     -o -name "*.ini" -o -name "*.csv" -o -name "*.mdc" -o -name "*.txt" \
     -o -name "*.conf" \
     -o -name "Dockerfile" -o -name "Procfile" -o -name ".env.example" \) \
  ! -path "*/.git/*" \
  ! -path "*/.venv/*" \
  ! -path "*/node_modules/*" \
  ! -name "setup.sh" \
  -print0)

ok "Placeholders replaced"

# ============================================================
# 3. APPLY FLAVOR
# ============================================================

info "Applying flavor: $FLAVOR"

# Copy flavor-specific pyproject.toml
cp "$SCRIPT_DIR/flavors/$FLAVOR/pyproject.toml" "$SCRIPT_DIR/pyproject.toml"

# Apply placeholders to the just-copied pyproject.toml
SED_CMD \
  -e "s|{{PROJECT_NAME}}|${PROJECT_NAME}|g" \
  -e "s|{{PROJECT_DESCRIPTION}}|${ESCAPED_DESC}|g" \
  -e "s|{{AUTHOR_NAME}}|${ESCAPED_AUTHOR}|g" \
  -e "s|{{AUTHOR_EMAIL}}|${ESCAPED_EMAIL}|g" \
  "$SCRIPT_DIR/pyproject.toml"

# Copy flavor-specific files
if [[ "$FLAVOR" == "cli" ]]; then
  cp "$SCRIPT_DIR/flavors/cli/app/cli.py" "$SCRIPT_DIR/app/cli.py"
  SED_CMD \
    -e "s|{{PROJECT_NAME}}|${PROJECT_NAME}|g" \
    -e "s|{{PROJECT_DESCRIPTION}}|${ESCAPED_DESC}|g" \
    "$SCRIPT_DIR/app/cli.py"

elif [[ "$FLAVOR" == "fastapi-modular" ]]; then
  cp "$SCRIPT_DIR/flavors/fastapi-modular/app/main.py" "$SCRIPT_DIR/app/main.py"
  mkdir -p "$SCRIPT_DIR/app/core"
  cp "$SCRIPT_DIR/flavors/fastapi-modular/app/core/config.py" "$SCRIPT_DIR/app/core/config.py"
  cp "$SCRIPT_DIR/flavors/fastapi-modular/app/core/database.py" "$SCRIPT_DIR/app/core/database.py"
  cp "$SCRIPT_DIR/flavors/fastapi-modular/alembic.ini" "$SCRIPT_DIR/alembic.ini"
  mkdir -p "$SCRIPT_DIR/alembic"
  cp "$SCRIPT_DIR/flavors/fastapi-modular/alembic/env.py" "$SCRIPT_DIR/alembic/env.py"
  cp "$SCRIPT_DIR/flavors/fastapi-modular/Dockerfile" "$SCRIPT_DIR/Dockerfile"
  cp "$SCRIPT_DIR/flavors/fastapi-modular/docker-compose.yml" "$SCRIPT_DIR/docker-compose.yml"
  cp "$SCRIPT_DIR/flavors/fastapi-modular/Procfile" "$SCRIPT_DIR/Procfile"

  for f in "$SCRIPT_DIR/app/main.py" "$SCRIPT_DIR/app/core/config.py" \
           "$SCRIPT_DIR/docker-compose.yml"; do
    SED_CMD \
      -e "s|{{PROJECT_NAME}}|${PROJECT_NAME}|g" \
      -e "s|{{PROJECT_DESCRIPTION}}|${ESCAPED_DESC}|g" \
      "$f"
  done

  mkdir -p "$SCRIPT_DIR/app/api/v1" "$SCRIPT_DIR/app/models" \
           "$SCRIPT_DIR/app/schemas" "$SCRIPT_DIR/app/services"
  touch "$SCRIPT_DIR/app/api/__init__.py" "$SCRIPT_DIR/app/api/v1/__init__.py" \
        "$SCRIPT_DIR/app/core/__init__.py" "$SCRIPT_DIR/app/models/__init__.py" \
        "$SCRIPT_DIR/app/schemas/__init__.py" "$SCRIPT_DIR/app/services/__init__.py"
fi

rm -rf "$SCRIPT_DIR/flavors"
ok "Flavor '$FLAVOR' applied"

# ============================================================
# 4. PYTHON VENV + DEPS
# ============================================================

info "Creating Python virtual environment..."
python3 -m venv "$SCRIPT_DIR/.venv"
"$SCRIPT_DIR/.venv/bin/pip" install --quiet --upgrade pip

info "Installing dependencies..."
"$SCRIPT_DIR/.venv/bin/pip" install --quiet \
  ruff mypy pre-commit pytest pytest-asyncio pytest-cov pytest-mock

if command -v poetry >/dev/null 2>&1; then
  cd "$SCRIPT_DIR" && poetry install --quiet 2>/dev/null || {
    warn "Poetry install failed, using pip"
    "$SCRIPT_DIR/.venv/bin/pip" install --quiet -e "$SCRIPT_DIR" 2>/dev/null || true
  }
else
  "$SCRIPT_DIR/.venv/bin/pip" install --quiet -e "$SCRIPT_DIR" 2>/dev/null || true
fi

ok "Dependencies installed"

# ============================================================
# 5. GIT INIT + PRE-COMMIT
# ============================================================

info "Initializing git repository..."
if [[ ! -d "$SCRIPT_DIR/.git" ]]; then
  git init "$SCRIPT_DIR" --quiet
  git -C "$SCRIPT_DIR" checkout -b master --quiet 2>/dev/null || true
fi

"$SCRIPT_DIR/.venv/bin/pre-commit" install --quiet 2>/dev/null || \
  warn "Pre-commit hook installation failed (non-critical)"
# commit-msg stage (sign-off enforcement) + pre-push stage (fast tests, scoped gates)
"$SCRIPT_DIR/.venv/bin/pre-commit" install --hook-type commit-msg --hook-type pre-push --quiet 2>/dev/null || \
  warn "commit-msg/pre-push hook installation failed (non-critical)"

# Stamp the sign-off signer into project.conf so check-signoff.sh enforces this identity.
if [[ -n "$AUTHOR_EMAIL" ]]; then
  SED_CMD -e "s|^SIGNOFF_EMAIL=.*|SIGNOFF_EMAIL=${AUTHOR_EMAIL}|" \
    "$SCRIPT_DIR/.dev-context/project.conf" 2>/dev/null || true
fi

ok "Git initialized with pre-commit, commit-msg, and pre-push hooks"

# ============================================================
# 6. LINT + FORMAT (ensure generated code is clean)
# ============================================================

info "Running lint and format on generated code..."
"$SCRIPT_DIR/.venv/bin/ruff" check --fix "$SCRIPT_DIR" 2>/dev/null && \
  ok "Lint checks passed" || \
  warn "Ruff check had issues (run 'ruff check --fix' manually)"

"$SCRIPT_DIR/.venv/bin/ruff" format "$SCRIPT_DIR" 2>/dev/null && \
  ok "Code formatted" || \
  warn "Ruff format had issues (run 'ruff format' manually)"

# ============================================================
# 7. SYNC CROSS-TOOL CONFIGS
# ============================================================

info "Syncing cross-tool configurations..."
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/scripts/sync-tool-configs.py" --sync 2>/dev/null || \
  warn "sync-tool-configs.py failed (non-critical — run manually later)"

# ============================================================
# 8. MCP INTEGRATIONS (OPTIONAL)
# ============================================================

if [[ "${CREATE_LINEAR:-n}" =~ ^[Yy]$ ]]; then
  info "Creating Linear team '${TICKET_PREFIX}'..."
  if command -v claude >/dev/null 2>&1; then
    claude --print \
      "Use the Linear MCP tool to create a new team with identifier/key '${TICKET_PREFIX}' and name '${PROJECT_NAME}'. If the team already exists, just report it. Output only the team ID." \
      2>/dev/null && ok "Linear team created" || \
      warn "Linear team creation failed. Create manually: team key='${TICKET_PREFIX}', name='${PROJECT_NAME}'"
  else
    warn "Claude CLI not found. Create Linear team manually:"
    echo "    Team key: ${TICKET_PREFIX}"
    echo "    Team name: ${PROJECT_NAME}"
  fi
fi

if [[ "${CREATE_NOTION:-n}" =~ ^[Yy]$ ]]; then
  info "Creating Notion workspace..."
  if command -v claude >/dev/null 2>&1; then
    claude --print \
      "Use the Notion MCP to create a new page titled '${PROJECT_NAME} — Development Hub' with sub-pages: 'PRDs', 'Sprint Plans', 'Social Media Content', 'Architecture Notes'. Output only the page URL." \
      2>/dev/null && ok "Notion workspace created" || \
      warn "Notion workspace creation failed. Create manually: '${PROJECT_NAME} — Development Hub'"
  else
    warn "Claude CLI not found. Create Notion page manually:"
    echo "    Title: ${PROJECT_NAME} — Development Hub"
    echo "    Sub-pages: PRDs, Sprint Plans, Social Media Content, Architecture Notes"
  fi
fi

if [[ "${SETUP_STITCH:-n}" =~ ^[Yy]$ ]]; then
  info "Configuring Stitch MCP for UI design generation..."
  MCP_FILE="$SCRIPT_DIR/.claude/mcp.json"
  if [[ -f "$MCP_FILE" ]]; then
    python3 -c "
import json
with open('$MCP_FILE') as f:
    cfg = json.load(f)
cfg.setdefault('mcpServers', {})['stitch'] = {
    'command': 'npx',
    'args': ['@_davideast/stitch-mcp', 'proxy'],
    'env': {'STITCH_API_KEY': '\${STITCH_API_KEY}'}
}
with open('$MCP_FILE', 'w') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')
" && ok "Stitch MCP added to .claude/mcp.json" || \
      warn "Failed to add Stitch MCP. Add manually to .claude/mcp.json"
  else
    warn "No .claude/mcp.json found. Create it first, then add Stitch config."
  fi
  echo ""
  echo -e "  ${YELLOW}ACTION REQUIRED${NC}: Set your Stitch API key:"
  echo "    export STITCH_API_KEY=your_key_here"
  echo "    Get your key at: https://stitch.withgoogle.com/"
fi

# ============================================================
# 9. GITHUB BRANCH PROTECTION (after repo exists)
# ============================================================

# Note: Branch protection is configured AFTER the repo is created and the
# initial commit is pushed. setup.sh prints a reminder in the next steps.

# ============================================================
# 10. SUMMARY
# ============================================================

echo ""
echo -e "${BOLD}=== Setup Complete ===${NC}"
echo ""
echo -e "  Project:      ${GREEN}${PROJECT_NAME}${NC}"
echo -e "  Project ID:   ${GREEN}${PROJECT_ID}${NC}"
echo -e "  Tickets:      ${GREEN}${TICKET_PREFIX}-NNN${NC}"
echo -e "  Flavor:       ${GREEN}${FLAVOR}${NC}"
echo -e "  Venv:         ${GREEN}.venv/${NC}"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo "    1. source .venv/bin/activate"
echo "    2. PYTHONPATH=. pytest              # verify setup"
echo "    3. git add -A && git commit -m 'chore: initialize project from dev-template'"
echo "    4. gh repo create ${PROJECT_NAME} --private --source=. --push"
echo "    5. Enable branch protection on master:"
echo "       gh api repos/{owner}/${PROJECT_NAME}/branches/master/protection -X PUT --input - <<'PROT'"
echo '       {"required_status_checks":{"strict":true,"contexts":["lint-and-type-check","test"]},'
echo '        "enforce_admins":false,"required_pull_request_reviews":{"dismiss_stale_reviews":true,'
echo '        "require_code_owner_reviews":false,"required_approving_review_count":0},'
echo '        "restrictions":null,"allow_force_pushes":false,"allow_deletions":false}'
echo "       PROT"
echo "    6. Set GITHUB_OWNER/GITHUB_REPO in .dev-context/project.conf (enables CI-latency"
echo "       + review capture). Optional gates default safe: SUBAGENT_LEDGER_CAPTURE=on,"
echo "       CI_LATENCY_CAPTURE=on, STATUS_DRIFT_MODE=warn, VIS_UI_GATE=off, subscription"
echo "       quota off (budgets.yml), auto-draft off (auto-draft.yml). Edit to taste."
echo "    7. (Optional) Install the Gemini CLI to enable the harness-efficiency filter"
echo "       (HARNESS_ROUTER=on in project.conf) — condenses long CI/diff output before"
echo "       it enters Claude's context. Fully fail-soft without it. See GEMINI.md."
echo "    8. /develop <your first idea>       # start building!"
echo ""
