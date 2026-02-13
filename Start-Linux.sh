#!/usr/bin/env bash
set -euo pipefail

# Start-Linux.sh — simple developer startup helper for Ubuntu
#
# Usage:
#  - From the project root run: ./Start-Linux.sh
#  - The script will:
#      * start `ngrok` detached (if installed and not already running),
#        writing logs to `ngrok.out.log` and `ngrok.err.log` in the repo root;
#      * activate `.venv` if present; and
#      * exec `uvicorn` in the foreground so Ctrl-C cleanly stops the server.
#  - To run without ngrok, simply run the uvicorn command directly after
#    activating the venv:
#      source .venv/bin/activate && uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_root"

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
if [ -n "${VENV:-}" ] && [ -f "$script_root/$VENV/bin/activate" ]; then
  # shellcheck source=/dev/null
  . "$script_root/$VENV/bin/activate"
  echo "Activated virtualenv: $VENV"
else
  for candidate in .venv .ven venv; do
    if [ -f "$script_root/$candidate/bin/activate" ]; then
      # shellcheck source=/dev/null
      . "$script_root/$candidate/bin/activate"
      echo "Activated virtualenv: $candidate"
      break
    fi
  done
fi

echo "Starting uvicorn in foreground (Press CTRL-C to stop)"
# Determine how to invoke uvicorn. Prefer the executable on PATH, but
# fall back to `python -m uvicorn` if the binary isn't available.
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

# Replace this shell with the selected uvicorn invocation so SIGINT/Ctrl-C
# goes directly to the server process.
exec $uvicorn_cmd
