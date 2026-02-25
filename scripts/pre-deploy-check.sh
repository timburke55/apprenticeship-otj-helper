#!/usr/bin/env bash
# Pre-deploy validation script for the OTJ Helper.
#
# Runs fast checks that catch regressions before a Railway deploy:
#   1. flake8 lint pass over all source files
#   2. pytest smoke suite (app factory, key routes, input validation)
#
# Usage:
#   ./scripts/pre-deploy-check.sh          # run from repo root
#   uv run ./scripts/pre-deploy-check.sh   # explicit uv context

set -euo pipefail

echo "==> OTJ Helper pre-deploy checks"

echo ""
echo "--- 1/2  Lint (flake8) ---"
uv run flake8 src/ --max-line-length=120
echo "    Lint: OK"

echo ""
echo "--- 2/2  Smoke tests (pytest) ---"
uv run pytest tests/ -x -q
echo "    Tests: OK"

echo ""
echo "==> All pre-deploy checks passed."
