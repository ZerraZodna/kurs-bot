AI agents: ALWAYS read AGENTS.md first for workflow rules.

# Kurs Bot

A chatbot with persistent memory that delivers daily lessons via Telegram and email.

## Prerequisites

### macOS
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install git node python
```

### Ubuntu/Debian
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential python3 python3-venv python3-pip
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs
```

### Windows
```powershell
winget install -e --id Git.Git --id OpenJS.NodeJS.LTS --id Python.Python.3.10
```

### Optional: ngrok (for Telegram webhooks)
```bash
# macOS
brew install ngrok && ngrok config add-authtoken <token>

# Linux
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com/apt stable main" | sudo tee /etc/sources.list.d/ngrok.list
sudo apt update && sudo apt install -y ngrok && ngrok config add-authtoken <token>

# Windows
winget install -e --id ngrok.ngrok && ngrok config add-authtoken <token>
```

## Setup

```bash
git clone https://github.com/ZerraZodna/kurs-bot.git
cd kurs-bot
cp .env.template .env
nano .env # Update TELEGRAM and OLLAMA keys
```

Edit `.env` and add your Telegram bot token:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### Option A: With npm (recommended)
```bash
npm install
npm test
npm start
```

### Option B: Without npm (older Macs)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

> **Note:** Database is auto-initialized on first run.

## Telegram Long-Polling (alternative to ngrok)

Add to `.env`:
```
USE_TELEGRAM_LONG_POLLING=true
```

Useful for: no ngrok account needed, NAT/firewall traversal, simpler setup.

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_TELEGRAM_LONG_POLLING` | false | Enable long-polling |
| `TELEGRAM_POLL_TIMEOUT` | 25 | Poll timeout (seconds) |
| `TELEGRAM_POLL_LIMIT` | 100 | Max updates per request |

## NPM Commands

| Command | Description |
|---------|-------------|
| `npm install` | Install dependencies |
| `npm start` | Start API + ngrok |
| `npm stop` | Stop services |
| `npm run start:ui` | Dev web UI |
| `npm run init_db` | Initialize database |
| `npm run config` | Edit `.env` |
| `npm run test` | Run tests |

## Configuration (.env)

```bash
# Required
TELEGRAM_BOT_TOKEN=      # Get from @BotFather
API_AUTH_TOKEN=          # For API authentication

# Optional
SENDGRID_API_KEY=        # For email
OLLAMA_BASE_URL=         # Default: http://localhost:11434
DATABASE_URL=            # SQLite (dev) / SQL Server (prod)
```

## Tech Stack

- Python 3.10+ / FastAPI / SQLAlchemy
- Node.js (build tooling only)
- SQLite (dev) / SQL Server (prod)

## Project Structure

```
src/
├── api/          # FastAPI routes & webhooks
├── integrations/ # Telegram, email adapters
├── lessons/      # ACIM lesson delivery engine
├── memories/     # Persistent memory & RAG
└── models/       # SQLAlchemy ORM
```

