#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating project environment..."
  python3 -m venv .venv
fi

echo "Checking project dependencies..."
./.venv/bin/python -m pip install -r requirements.txt

echo "Starting Assignment Checker..."
exec ./.venv/bin/python -m checker.cli serve --open
