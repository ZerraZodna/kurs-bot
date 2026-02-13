#!/usr/bin/env bash
set -euo pipefail
script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_root"

uvicorn_cmd="uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"
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

# Activate venv if present
if [ -f "$script_root/.venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  . "$script_root/.venv/bin/activate"
fi

echo "Starting uvicorn in foreground (Press CTRL-C to stop)"
# Replace this shell with uvicorn so SIGINT/Ctrl-C goes directly to the server
exec $uvicorn_cmd
