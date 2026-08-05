AI agents: ALWAYS read AGENTS.md first for workflow rules.

# Kurs Bot

A chatbot with persistent memory that delivers daily lessons via Telegram and email.

## Prerequisites

- Node.js (for task runner scripts only)
- Python 3.12+

### macOS
```bash
brew install node python
```

### Ubuntu/Debian
```bash
sudo apt install -y git curl build-essential python3 python3-venv nodejs
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

```bash
./run.sh ensure-venv
./run.sh install
./run.sh test
./run.sh start
```

**No npm required.** Uses `./run.sh` (thin wrapper around `scripts/venv.js`) for all tasks. Only needs Node.js and Python 3.12+.

**Note**: Uses modern `pyproject.toml` for dependencies (replaces legacy requirements.txt).

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

## Commands

| Command | Description |
|---------|-------------|
| `./run.sh install` | Install dependencies |
| `./run.sh start` | Start API + ngrok |
| `./run.sh stop` | Stop services |
| `./run.sh start:ui` | Dev web UI |
| `./run.sh init_db` | Initialize database |
| `./run.sh config` | Edit `.env` |
| `./run.sh test` | Run tests |

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
- Python 3.12+ / FastAPI / SQLAlchemy
- Node.js (task runner only)
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

## 📚 Documentation

Organized in docs/:
- [Index](docs/INDEX.md)
- dev/ (architecture, DB, scripts, NPM)
- gdpr/ (compliance docs)
- project/ (onboarding, import, scheduler)
