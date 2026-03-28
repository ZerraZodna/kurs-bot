# Swarm Approval Telegram Bot

## Purpose
Self-contained Telegram bot for handling swarm approval system in the 9-step human-in-the-loop workflow:

- `/approve` - Approve pending swarm request
- `/retry "instructions"` - Request adjustments with feedback
- `/decline` - Decline pending request completely
- `/help` - Show available commands

## Configuration

This bot is separate from the main kurs-bot and requires its own:
- SWARM_APPROVAL_BOT_TOKEN (for the approval bot, not the main coursos bot)

### How to Set Up

1. Create a new bot on Telegram (contact @BotFather)
2. Get the bot's API token
3. Add that token to your `.env` file as:
   ```
   SWARM_APPROVAL_BOT_TOKEN=your_new_token_here
   ```

4. The code checks for SWARM_APPROVAL_BOT_TOKEN first, with TELEGRAM_BOT_TOKEN as fallback for backward compatibility

   For clean separation, recommend using the dedicated SWARM_APPROVAL_BOT_TOKEN to ensure the approval bot is completely separate from the main coursos bot.

## Usage

The bot monitors for approval commands and interacts with the swarm system to:
- Pause for approvals at Step 2-3: Prompt generation approval
- Pause for approvals at Step 8-9: Final commit approval

## Security Notes
- Only respond to approvals from authorized users
- The bot should verify the user requesting approval matches the user who initiated the swarm request
- All approval activity is logged for audit trail

## Integration Points
- `send_swarm_approval_request()`: Called by swarm to initiate approval request
- `send_swarm_complete_notification()`: Called by swarm when finished
- All command handlers implement the approval workflow
