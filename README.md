# Kurs Bot

A chatbot/consultant with persistent memory that delivers daily lessons and interval reminders via DM channels (Telegram, Slack, SMS, Teams) and email.

## Tech Stack
- Python 3.10+
- FastAPI
- SQLAlchemy ORM
- SQLite (for prototyping) / SQL Server (production)
- Alembic (migrations)
- pytest (testing)

## Unified quickstart (all platforms)
Use the npm helper everywhere; it creates `.venv`, installs Python deps, and runs the common scripts. You still need to set secrets and install ngrok yourself.

```bash
git clone https://github.com/ZerraZodna/kurs-bot.git
cd kurs-bot
cp .env.template .env
# Required in .env (npm will NOT set these):
#   TELEGRAM_BOT_TOKEN, SLACK_BOT_TOKEN, API_AUTH_TOKEN, GDPR_ADMIN_TOKEN
# Optional: NGROK_AUTH_TOKEN (or run `ngrok config add-authtoken`)

npm install                      # builds .venv and installs Python deps
npm run init_db -- --db prod     # or --db dev for src/data/dev.db
npm start                        # starts uvicorn + ngrok if present
# Optional dev UI: set DEV_WEB_CLIENT=true in .env, then
npm run start:ui
npm stop                         # stops processes started by npm start
```

What `npm install` does: creates `.venv`, installs project requirements. What it does **not** do: set any tokens/keys, install ngrok, or open firewall ports.

## Platform prerequisites
Install these before running the unified quickstart above.

### Debian/Ubuntu (incl. AWS Debian 12/Ubuntu 20.04+)
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential python3 python3-venv python3-pip
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
# Optional: sudo apt install -y powershell
# ngrok (not installed by npm):
# curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
# echo "deb https://ngrok-agent.s3.amazonaws.com/apt/ stable main" | sudo tee /etc/apt/sources.list.d/ngrok.list
# sudo apt update && sudo apt install -y ngrok
# ngrok config add-authtoken <your-ngrok-token>
```
- CPU-only PyTorch (small/headless servers): `python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.4.1+cpu` before `npm install` if you want to pin the CPU wheel.

### macOS (Apple Silicon)
- Install Node.js 20+ (e.g., `brew install node`).
- Runtime: `npm start` to start the application.

### Windows (npm helper)
```powershell
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Python.Python.3.10
# (optional) winget install -e --id Microsoft.PowerShell
git clone https://github.com/ZerraZodna/kurs-bot.git
cd kurs-bot
copy .env.template .env
npm install
npm run init_db -- --db prod   # or --db dev
# Install ngrok separately (npm does NOT install it):
# choco install ngrok  # or download from https://ngrok.com/download
# ngrok config add-authtoken <your-ngrok-token>
npm start
# optional dev UI (after setting DEV_WEB_CLIENT=true)
npm run start:ui
npm stop
```

Manual fallback (if npm scripts can’t run):
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

## Where to put the ngrok key

- Preferred: authenticate ngrok locally using `ngrok config add-authtoken <token>`; no env var needed.
- Alternative: set `NGROK_AUTH_TOKEN` in `.env` if you want the project to be explicit. Example in your `.env`:

```
NGROK_AUTH_TOKEN=your_ngrok_token_here
```

## Start-up summary (quick)

1. Activate venv: `source .venv/bin/activate`
2. Start app: `uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000`
3. Start ngrok: `ngrok http 8000`
4. Set Telegram webhook to `https://<ngrok-id>.ngrok.io/webhook/telegram`

--

## Development Commands

Use `cli.py` for common development tasks:

```bash
# Database management
python cli.py db status              # Show database status
python cli.py db reset               # Reset dev.db (keeps 365 lessons)
python cli.py db backup              # Create backup
python cli.py db fresh-start         # Complete fresh start (delete + re-import)
python cli.py db info                # Show detailed DB info

# ACIM lessons
python cli.py import-lessons         # Import ACIM lessons from PDF

# Debugging
python cli.py debug memory           # Debug memory extraction
python cli.py debug schedule         # Debug schedule creation

# Production
python cli.py init-prod              # Initialize production database
```

See [docs/SCRIPTS_ORGANIZATION.md](docs/SCRIPTS_ORGANIZATION.md) for full script documentation.

## Local development helper scripts

The repository includes convenience scripts for getting a local development environment running quickly on Windows.

- Start everything (uvicorn, ngrok):
   ```powershell
   .\start_kursbot.ps1 -StartInfra
   ```

## Deployment (production)

This project can be deployed with a standard Python WSGI/ASGI process (uvicorn) and a production SQL database. Key points:

- Infrastructure: use Postgres (or other production SQL) and configure `DATABASE_URL` in environment. Optionally run worker processes for background tasks and a vector index (Faiss or managed vector DB) if required.
- Important environment variables:
   - `DATABASE_URL` — production DB connection string.
   - `OLLAMA_EMBED_URL` and `OLLAMA_EMBED_MODEL` — embedding service endpoint and model (if using Ollama).
   - `EMBEDDING_DIMENSION` — ensure this matches the embed model used.
   - `NGROK_PATH` — local dev only; not required in production.

- Recommended startup order:
   1. Start the database and run migrations (`alembic upgrade head`).
   2. Start background workers (if used).
   3. Start the API: `uvicorn src.api.app:app`.

- Upgrades and reindexing:
   - If changing the embedding model or vector configuration, plan a backfill job to regenerate embeddings during a low-traffic window.
   - Workers should check existing metadata before regenerating to avoid duplicate work.

- CI and local development:
   - CI runs `pytest` against SQLite by default; configure CI to opt-in to real backends if necessary.

- Security & backups:
   - Protect API keys and DB credentials with your secrets manager and follow GDPR/export controls when handling user memories.
   - Implement regular DB backups and vector index dumps if used.

Contact your ops/backend team to finalize sizing, alerting, and other production roll-out tasks.

## Configuration (.env)
- `DATABASE_URL` - Database connection string (default: SQLite for dev)
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `SLACK_BOT_TOKEN` - Slack bot token
- `SENDGRID_API_KEY` - SendGrid API key
- Note: vector-index configuration and runtime toggle have been removed in this branch; vector indexing is disabled by design.

### Semantic Search (RAG mode)

The bot supports RAG (Retrieval Augmented Generation) mode for answering questions about ACIM lessons. This uses Ollama's embedding capabilities via the API - no local embedding models required.

Enable RAG mode in chat by typing `rag on` or prefixing your message with `rag: `.

## Project Structure
- `src/models/database.py` - SQLAlchemy ORM models
- `src/api/app.py` - FastAPI app and webhook handler
- `src/services/` - Business logic (memory, scheduling, etc.)
- `src/integrations/` - Channel integrations (Telegram, Slack, etc.)
- `migrations/` - Alembic migration scripts
- `tests/` - Unit tests

## Purpose
Kurs Bot is designed to help users complete wellness lessons and receive reminders, with persistent memory and multi-channel support.

---
