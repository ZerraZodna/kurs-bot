#!/usr/bin/env bash
set -euo pipefail

# start-linux.sh — simple developer startup helper for Linux
# Lowercase copy moved into scripts/ per repository convention.

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# repo_root is the workspace root (parent of scripts/)
repo_root="$(cd "$script_root/.." && pwd)"
cd "$repo_root"

ngrok_cmd="ngrok http 8000"

ngrok_out="$script_root/ngrok.out.log"
ngrok_err="$script_root/ngrok.err.log"

# Start ngrok detached if available and not already running
if command -v ngrok >/dev/null 2>&1; then
  if ! pgrep -f "ngrok.*8000" >/dev/null 2>&1; then
    nohup $ngrok_cmd >"$ngrok_out" 2>"$ngrok_err" &
    echo "Started ngrok detached (stdout: $ngrok_out, stderr: $ngrok_err)"
  else
    echo "ngrok already running"
  fi
else
  echo "ngrok not found in PATH; skipping ngrok startup"
fi

# Activate virtualenv if present. Prefer an explicit $VENV, then common names.
if [ -n "${VENV:-}" ] && [ -f "$repo_root/$VENV/bin/activate" ]; then
  # shellcheck source=/dev/null
  . "$repo_root/$VENV/bin/activate"
  echo "Activated virtualenv: $VENV"
else
  for candidate in .venv .ven venv; do
    if [ -f "$repo_root/$candidate/bin/activate" ]; then
      # shellcheck source=/dev/null
      . "$repo_root/$candidate/bin/activate"
      echo "Activated virtualenv: $candidate"
      break
    fi
  done
fi

echo "Starting uvicorn in foreground (Press CTRL-C to stop)"
if command -v uvicorn >/dev/null 2>&1; then
  uvicorn_cmd="uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"
elif python3 -m uvicorn --version >/dev/null 2>&1; then
  uvicorn_cmd="python3 -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"
elif python -m uvicorn --version >/dev/null 2>&1; then
  uvicorn_cmd="python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"
else
  echo "ERROR: uvicorn not found in PATH and 'python -m uvicorn' is unavailable."
  echo "Install uvicorn into the active virtualenv or ensure it's on PATH."
  echo "Example: source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

exec $uvicorn_cmd
