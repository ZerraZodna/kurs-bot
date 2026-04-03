#!/usr/bin/env python3
"""
Helper script to start the swarm Telegram approval polling bot.

This is DIFFERENT from the main kurs-bot Telegram client.
The swarm polling bot handles /approve, /decline, /retry commands for swarm operations.
"""

import os
import sys
import signal
import logging
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/home/steen/kurs-bot/swarm/telegram/swarm_approval.log')
    ]
)
logger = logging.getLogger(__name__)

from swarm.telegram import telegram_swarm_polling

def sigterm_handler(signum, frame):
    """Handle SIGTERM gracefully."""
    logger.info("\nReceived SIGTERM, shutting down gracefully...")
    sys.exit(0)

def main():
    """Start the swarm Telegram approval polling bot."""
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)
    
    # Verify environment variables
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    user_id = os.getenv("TELEGRAM_USER_ID", "").strip()
    
    if not chat_id or not user_id:
        logger.error("ERROR: TELEGRAM_CHAT_ID and TELEGRAM_USER_ID must be set in .env")
        logger.error("Example .env content:")
        logger.error("TELEGRAM_CHAT_ID=your_chat_id")
        logger.error("TELEGRAM_USER_ID=your_user_id")
        sys.exit(1)
    
    # Check if it's a valid integer
    try:
        int(chat_id)
        int(user_id)
    except ValueError:
        logger.error("ERROR: TELEGRAM_CHAT_ID and TELEGRAM_USER_ID must be integers")
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info("KURS-BOT SWARM TELEGRAM APPROVAL POLLER")
    logger.info("=" * 80)
    logger.info(f"Chat ID: {chat_id}")
    logger.info(f"User ID: {user_id}")
    logger.info("Polling for: /approve, /decline, /retry commands")
    logger.info("This is the SWARM approval bot, NOT the main kurs-bot Telegram")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Starting Telegram polling bot...")
    logger.info("This bot will handle approval requests from swarm operations.")
    logger.info("")
    logger.info("Commands you can send:")
    logger.info("  /approve  - Approve the proposed changes")
    logger.info("  /decline  - Decline and stop the workflow")
    logger.info("  /retry    - Request retry with feedback")
    logger.info("  /help     - Show help")
    logger.info("")
    logger.info("Press Ctrl+C or SIGTERM to stop the bot.")
    logger.info("")
    
    # Start the polling bot
    poller = telegram_swarm_polling.SwarmTelegramPoller()
    
    try:
        poller.run()
    except KeyboardInterrupt:
        logger.info("\nKeyboardInterrupt received, shutting down...")
    except Exception as e:
        logger.error(f"ERROR: {e}")
        logger.error("Check the logs at: /home/steen/kurs-bot/swarm/telegram/swarm_approval.log")
        sys.exit(1)


if __name__ == "__main__":
    main()
