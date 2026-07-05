#!/usr/bin/env bash
set -euo pipefail

# sync.sh — Distribute .dev-context/ to all AI platform directories
# Run from the project root (parent of .dev-context/)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEV_CONTEXT="$PROJECT_ROOT/.dev-context"

cd "$PROJECT_ROOT"

echo "==> Syncing .dev-context/ to platform-specific directories..."

# --- AGENTS.md (generated from CONTEXT.md) ---
echo "  Generating AGENTS.md from CONTEXT.md..."
{
    cat "$DEV_CONTEXT/CONTEXT.md"
    echo ""
    echo "---"
    echo ""
    echo "## Rules"
    echo ""
    echo "The following rules are enforced for this project. Read all before writing code."
    echo ""
    for rule_file in "$DEV_CONTEXT/rules/"*.md; do
        [ -f "$rule_file" ] || continue
        echo ""
        cat "$rule_file"
    done
} > "$PROJECT_ROOT/AGENTS.md"

# --- CLAUDE.md, CODEX.md, and GEMINI.md (symlinks to AGENTS.md) ---
echo "  Creating symlinks: CLAUDE.md, CODEX.md, GEMINI.md → AGENTS.md..."
rm -f "$PROJECT_ROOT/CLAUDE.md" "$PROJECT_ROOT/CODEX.md" "$PROJECT_ROOT/GEMINI.md"
ln -s AGENTS.md "$PROJECT_ROOT/CLAUDE.md"
ln -s AGENTS.md "$PROJECT_ROOT/CODEX.md"
ln -s AGENTS.md "$PROJECT_ROOT/GEMINI.md"

# --- .cursor/rules/ (rules with Cursor frontmatter) ---
echo "  Generating .cursor/rules/ with frontmatter..."
rm -rf "$PROJECT_ROOT/.cursor/rules"
mkdir -p "$PROJECT_ROOT/.cursor/rules"

for rule_file in "$DEV_CONTEXT/rules/"*.md; do
    [ -f "$rule_file" ] || continue
    filename="$(basename "$rule_file")"
    # Extract first heading as description, fallback to filename
    description="$(grep -m1 '^# ' "$rule_file" | sed 's/^# //' || echo "$filename")"
    {
        echo "---"
        echo "description: \"$description\""
        echo "alwaysApply: true"
        echo "---"
        echo ""
        cat "$rule_file"
    } > "$PROJECT_ROOT/.cursor/rules/$filename"
done

# --- .cursor/skills/ (copied from skills/) ---
echo "  Copying skills to .cursor/skills/..."
rm -rf "$PROJECT_ROOT/.cursor/skills"
mkdir -p "$PROJECT_ROOT/.cursor/skills"
cp -r "$DEV_CONTEXT/skills/"* "$PROJECT_ROOT/.cursor/skills/"

# --- .agent/rules/ (plain markdown for Antigravity) ---
echo "  Generating .agent/rules/ (plain markdown)..."
rm -rf "$PROJECT_ROOT/.agent/rules"
mkdir -p "$PROJECT_ROOT/.agent/rules"

for rule_file in "$DEV_CONTEXT/rules/"*.md; do
    [ -f "$rule_file" ] || continue
    cp "$rule_file" "$PROJECT_ROOT/.agent/rules/"
done

# Copy CONTEXT.md as project-knowledge.md for Antigravity
cp "$DEV_CONTEXT/CONTEXT.md" "$PROJECT_ROOT/.agent/rules/project-knowledge.md"

# --- .agent/skills/ (copied from skills/) ---
echo "  Copying skills to .agent/skills/..."
rm -rf "$PROJECT_ROOT/.agent/skills"
mkdir -p "$PROJECT_ROOT/.agent/skills"
cp -r "$DEV_CONTEXT/skills/"* "$PROJECT_ROOT/.agent/skills/"

# --- .claude/skills/ (copied from skills/) ---
echo "  Copying skills to .claude/skills/..."
rm -rf "$PROJECT_ROOT/.claude/skills"
mkdir -p "$PROJECT_ROOT/.claude/skills"
cp -r "$DEV_CONTEXT/skills/"* "$PROJECT_ROOT/.claude/skills/"

# --- Summary ---
echo ""
echo "==> Sync complete!"
echo "  AGENTS.md        : $(wc -c < "$PROJECT_ROOT/AGENTS.md" | tr -d ' ') bytes"
echo "  CLAUDE.md         : symlink → AGENTS.md"
echo "  CODEX.md          : symlink → AGENTS.md"
echo "  GEMINI.md         : symlink → AGENTS.md"
echo "  .cursor/rules/    : $(ls "$PROJECT_ROOT/.cursor/rules/" | wc -l | tr -d ' ') files"
echo "  .cursor/skills/   : $(find "$PROJECT_ROOT/.cursor/skills/" -name "SKILL.md" | wc -l | tr -d ' ') skills"
echo "  .agent/rules/     : $(ls "$PROJECT_ROOT/.agent/rules/" | wc -l | tr -d ' ') files (incl. project-knowledge.md)"
echo "  .agent/skills/    : $(find "$PROJECT_ROOT/.agent/skills/" -name "SKILL.md" | wc -l | tr -d ' ') skills"
echo "  .claude/skills/   : $(find "$PROJECT_ROOT/.claude/skills/" -name "SKILL.md" | wc -l | tr -d ' ') skills"
