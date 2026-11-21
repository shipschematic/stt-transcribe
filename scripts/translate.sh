#!/usr/bin/env bash
# Translate SRT files from output/ (or the paths you pass).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

env_args=()
if [[ -f .env ]]; then
    env_args=(--env-file .env)
fi

exec uv run --python 3.11 "${env_args[@]}" stt-translate "$@"
