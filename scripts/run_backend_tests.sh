#!/usr/bin/env bash

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if [[ -x "backend/.venv/bin/python" ]]; then
  echo "Running backend tests with backend/.venv/bin/python..."
  exec backend/.venv/bin/python -m pytest backend/tests
fi

if command -v uv >/dev/null 2>&1; then
  echo "Running backend tests with uv..."
  exec uv run --directory backend pytest tests
fi

echo "Unable to run backend tests." >&2
echo "Set up the backend environment first with 'cd backend && uv sync'." >&2
exit 1
