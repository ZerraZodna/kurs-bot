# Kurs Bot

A chatbot/consultant with persistent memory that delivers daily lessons and interval reminders via DM channels (Telegram, Slack, SMS, Teams) and email.

## Tech Stack
- Python 3.10+
- FastAPI
- SQLAlchemy ORM
- SQLite (for prototyping) / SQL Server (production)
- Alembic (migrations)
- pytest (testing)

## Setup for Windows:

1. Clone the repo and create a virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   - Copy `.env.template` to `.env` and fill in your secrets (see below).

3. Initialize the database and run migrations:
   ```powershell
   alembic upgrade head
   ```

4. Run the app:
   ```powershell
   .venv\Scripts\activate
   uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
   ```

5. Expose webhook with ngrok:
   ```powershell
   ngrok http 8000
   # then set Telegram webhook to https://<ngrok-id>.ngrok.io/webhook/telegram
   ```

6. Run tests:
   ```powershell
   .\run_tests.ps1
   ```

or:
## Ubuntu Preparation (clean install)

These concise steps target a developer machine or VM (Ubuntu 20.04+). They install Python, create the virtualenv, and explain ngrok options.

1) Update packages and install prerequisites

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential libpq-dev python3 python3-venv python3-pip
```

2) (Optional) Install PowerShell (if you want to use provided PowerShell helpers on Ubuntu):

```bash
# Install Microsoft package repository and pwsh
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/microsoft.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/ubuntu/$(lsb_release -rs)/prod $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/microsoft-prod.list
sudo apt update
sudo apt install -y powershell
# Start PowerShell with: pwsh
```

3) Clone the repository and create a Python virtual environment (step 1 from the Windows script adapted):

```bash

ssh-keygen -t ed25519 -C "your.email@example.com"   # Generate a new SSH key (press Enter for defaults, no passphrase for simplicity)
cat ~/.ssh/id_ed25519.pub                          # Copy the output (this is your public key)
# Go to GitHub.com → Settings → SSH and GPG keys → New SSH key.
# Paste the copied public key and save.
ssh -T git@github.com              # Should say "Hi username! You've successfully authenticated..."

git clone git@github.com:ZerraZodna/kurs-bot.git
cd kurs-bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

## CPU-only install (recommended for small/headless servers)

If you want to avoid installing CUDA/GPU wheels (useful on small servers or CI), install CPU-only PyTorch first, then install the project requirements. Example (with your virtualenv active):

```bash
# Install CPU-only PyTorch wheel first (if your app uses torch). Do NOT install torchvision/torchaudio unless you need image/audio features.
python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch
## AI suggest this torch version, used running tests on GitHub. See ci.yaml
python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.4.1+cpu

# Then senctence-transformers:
python -m pip install --no-cache-dir sentence-transformers hnswlib

# Then install the project requirements (avoids pulling CUDA wheels as dependencies)
python -m pip install --no-cache-dir -r requirements.txt
```

4) Environment variables and ngrok auth:

- Copy the example env and edit secrets:

```bash
cp .env.template .env
# Edit .env and set TELEGRAM_BOT_TOKEN, SLACK_BOT_TOKEN, API_AUTH_TOKEN, GDPR_ADMIN_TOKEN, etc.
nano .env
```

EASY INSTALL Ngrok that FAILS:
sudo snap install ngrok
# authenticate (once)
ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>


- Ngrok: install from https://ngrok.com/download or via snap/apt if available. Authenticate your ngrok client with your authtoken (replace <your-ngrok-token>):

```bash
# example using the official install script
# Add the ngrok signing key
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null

# Add the ngrok repository (adjust "bookworm" if your Ubuntu version differs; works for 22.04/24.04 as of 2026)
echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" \
  | sudo tee /etc/apt/sources.list.d/ngrok.list

# Update packages and install ngrok
sudo apt update
sudo apt install ngrok -y


or:
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com/apt/ stable main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install -y ngrok

ngrok config add-authtoken <your-ngrok-token>
```

- The `NGROK_AUTH_TOKEN` is not required in `.env` for the local client once you run `ngrok config add-authtoken`. If you prefer keeping the token in `.env`, set `NGROK_AUTH_TOKEN` there.

5) Database migrations (alembic):

See scripts/setup_new_host.ps1
.\scripts\setup_new_host.ps1 -Yes -InstallDeps

For GPU edit .env to use:
EMBEDDING_BACKEND=ollama
Then init prod.db:
```pwsh
.\scripts\setup_new_host.ps1 -Yes
```

6) Start the app (development): (Do step 7 first once)
Windows:
\.\scripts\start-windows.ps1

Unix:
chmod +x ./scripts/start-linux.sh
source .venv/bin/activate
./scripts/start-linux.sh

Or totally manual:
```bash
pwsh
./.venv/bin/Activate.ps1
# in another terminal, expose with ngrok
ngrok http 8000
# or as process: see "jobs" & sudo kill 
ngrok http 8000 > ngrok.log 2>&1 &

#Forground
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

#In background developer mode:
nohup .venv/bin/python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000 >uvicorn.log 2>&1 & disown

#To follow log:
tail -n 200 -F uvcorn.log
```

For Production server:
```bash
.venv/bin/pip install uvloop httptools
# or install uvicorn with recommended extras
.venv/bin/pip install "uvicorn[standard]"
nohup python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --workers 2 --loop uvloop --http httptools >/dev/null 2>&1 &
```

7) Example: set Telegram webhook using the ngrok URL returned from `ngrok http 8000`:

Power Shell:
$token = 'xxxxxxxxxxx'
$telegramBot = 'tttttttt'
$webhook = 'https://appeasable-pressuringly-chau.ngrok-free.dev/webhook/telegram/'
Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/setWebhook" -Method Post -Body @{ url = $webhook$telegramBot  }

Does NOT WORK:
```bash
# set TELEGRAM_BOT_TOKEN in .env first
# then call Telegram setWebhook API (substitute <ngrok-url> and token)
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" -d "url=https://<ngrok-id>.ngrok.io/webhook/telegram"
```

Notes:
- The application loads `.env` via `pydantic` settings (see `src/config.py`). Keep secrets in `.env` (do not commit).
- If you prefer PowerShell helper scripts, run them from `pwsh` after installing `powershell` package above.

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

See `DEPLOYMENT.md` for production deployment notes and recommended startup order.

## Configuration (.env)
- `DATABASE_URL` - Database connection string (default: SQLite for dev)
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `SLACK_BOT_TOKEN` - Slack bot token
- `SENDGRID_API_KEY` - SendGrid API key
- Note: vector-index configuration and runtime toggle have been removed in this branch; vector indexing is disabled by design.

### Local embeddings (optional)

This project supports two embedding backends:

- **ollama**: uses a local Ollama HTTP API (`OLLAMA_EMBED_URL`) and models like `nomic-embed-text` (768-dim).
- **local**: uses `sentence-transformers` (default `all-MiniLM-L6-v2`, 384-dim) and an optional `hnswlib` index for fast nearest-neighbor search.

Toggle the backend in your `.env`:

```
EMBEDDING_BACKEND=local
SENTENCE_TRANSFORMERS_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
HNSWLIB_INDEX_PATH=src/data/emb_index.bin
```

To build a local index from lessons in the DB, install the minimal extras and run the helper:

```powershell
# activate your venv first

#  install from the project's requirements file
pip install -r requirements.txt
```

The index builder will read lessons from the configured `DATABASE_URL`, encode them with the specified sentence-transformers model, and save an `hnswlib` index plus a small metadata file. Set `HNSWLIB_INDEX_PATH` in `.env` so runtime code can find it.

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