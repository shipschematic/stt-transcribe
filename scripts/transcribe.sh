#!/usr/bin/env bash
# Transcribe media from input/ into output/.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Close stale proxy vars: httpx/huggingface_hub cannot parse SOCKS proxies.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy

# ctranslate2 loads CUDA libraries from the virtualenv.
shopt -s nullglob
nv_libs=("$ROOT_DIR"/.venv/lib/python*/site-packages/nvidia/*/lib)
if (( ${#nv_libs[@]} > 0 )); then
    nv_path="$(IFS=:; echo "${nv_libs[*]}")"
    export LD_LIBRARY_PATH="${nv_path}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

env_args=()
if [[ -f .env ]]; then
    env_args=(--env-file .env)
fi

exec uv run --python 3.11 "${env_args[@]}" stt-transcribe "$@"
