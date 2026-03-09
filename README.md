# Kurs Bot

A chatbot with persistent memory that delivers daily lessons via Telegram, Slack, SMS, and email.

## Prerequisites

### macOS
```bash
# Install Homebrew (if not present)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Git, Node.js
brew install git node

# Install Python 3.10+ (usually comes with Node.js, verify with: python3 --version)

# Install ngrok (optional, for Telegram dev)
brew install ngrok
ngrok config add-authtoken <your-ngrok-token>
```

### Ubuntu/Debian (including AWS)
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential python3 python3-venv python3-pip
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install ngrok (optional, for Telegram dev)
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com/apt/ stable main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install -y ngrok
ngrok config add-authtoken <your-ngrok-token>
```

### Windows
```powershell
# Install winget (comes with Windows 10+)
winget install -e --id Git.Git
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Python.Python.3.10

# Install ngrok (optional, for Telegram dev)
winget install -e --id ngrok.ngrok
ngrok config add-authtoken <your-ngrok-token>
```

## Quick Start

```bash
git clone https://github.com/ZerraZodna/kurs-bot.git
cd kurs-bot
cp .env.template .env
npm install
npm run config   # Add your TELEGRAM_BOT_TOKEN
npm test        # Verify code runs
npm start       # Start API + ngrok
```

That's it! npm handles:
- Creating Python virtual environment (`.venv`)
- Installing Python dependencies
- Starting the API server (uvicorn)
- Starting ngrok (if installed)

## Setup Telegram Bot

1. **Get Bot Token**: Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → follow prompts → copy token

2. **Configure in `.env`**:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```

3. **Test**: Start the bot with `npm start`, then open Telegram and send a message!

## NPM Commands

| Command | Description |
|---------|-------------|
| `npm install` | Install all dependencies |
| `npm start` | Start API + ngrok (if available) |
| `npm stop` | Stop all services |
| `npm run start:ui` | Start dev web UI |
| `npm run init_db` | Initialize database |
| `npm run config` | Create/open `.env` file |
| `npm run ping` | Test Telegram/Ollama connectivity |
| `npm test` | Run tests |

## Configuration (.env)

```bash
# Required
TELEGRAM_BOT_TOKEN=      # Get from @BotFather
API_AUTH_TOKEN=          # For API authentication

# Optional
SLACK_BOT_TOKEN=         # Slack bot token
SENDGRID_API_KEY=        # For email
NGROK_AUTH_TOKEN=        # Or run: ngrok config add-authtoken <token>
OLLAMA_BASE_URL=         # Default: http://localhost:11434
DATABASE_URL=            # SQLite for dev, SQL Server for prod
```

## Tech Stack

- Python 3.10+ / FastAPI / SQLAlchemy
- Node.js (build tooling only)
- SQLite (dev) / SQL Server (prod)

## Project Structure

```
src/
├── api/          # FastAPI routes & webhooks
├── integrations/ # Telegram, Slack, email adapters
├── lessons/      # ACIM lesson delivery engine
├── memories/     # Persistent memory & RAG
└── models/       # SQLAlchemy ORM
```

