# Telegram Approval Bot - Quick Start

## ⚡ Get Started in 3 Steps

### 1️⃣ Activate Virtual Environment

```bash
cd ~/kurs-bot
source .venv/bin/activate
```

### 2️⃣ Create a Bot

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`
3. Give your bot a name (e.g., "Kurs Bot Approver")
4. Copy the **API token** provided

### 3️⃣ Configure `.env`

```bash
# Add to ~/kurs-bot/.env
SWARM_APPROVAL_BOT_TOKEN=123456:ABCDEF...wxyz
```

### 4️⃣ Start the Bot

```bash
python -m swarm.telegram.telegram_swarm_polling
```

✅ **Done!** The bot is now running and waiting for commands.

---

## 🧪 Test It

1. Send `/help` to your bot in Telegram
2. Try `/approve` if you have a pending request

---

## 📝 That's All!

The rest of the docs are for production deployment, monitoring, and advanced configuration. For daily use, you just need these 3 steps.

---

**Full documentation**: See `docs/CONFIG_GUIDE.md`
