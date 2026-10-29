#!/usr/bin/env bash
# Regenerate the README's images in docs/images from a fresh demo workspace.
# Needs vhs (https://github.com/charmbracelet/vhs) and a Chromium for Playwright.
set -euo pipefail

cd "$(dirname "$0")/../.."
uv sync -q
export PATH="$PWD/.venv/bin:$PATH"

DEMO="$(mktemp -d)"
trap 'kill "${SERVER:-}" 2>/dev/null || true; rm -rf "$DEMO"' EXIT
export DEMO

# Screenshots first: the CLI recording changes a task's status.
uv run python docs/demo/workspace.py "$DEMO"
planboard --data "$DEMO/plans" serve --no-open --port 8799 >/dev/null 2>&1 &
SERVER=$!
sleep 2
uv run --with playwright python docs/demo/screenshots.py http://localhost:8799 docs/images
kill "$SERVER"

for theme in light dark; do
  rm -rf "$DEMO" && uv run python docs/demo/workspace.py "$DEMO" >/dev/null
  vhs "docs/demo/demo-$theme.tape"
done
