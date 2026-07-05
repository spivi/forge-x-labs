#!/usr/bin/env bash
# Pre-commit hook: block direct commits to master/main.
branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" = "master" ] || [ "$branch" = "main" ]; then
  echo "ERROR: Direct commits to $branch are blocked. Use a feature branch."
  exit 1
fi
