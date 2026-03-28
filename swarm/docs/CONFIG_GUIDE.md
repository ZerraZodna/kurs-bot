# Telegram Approval Bot - Configuration Guide

> **Quick Start**: See [`SWARM_QUICK_START.md`](../SWARM_QUICK_START.md) for a 3-step setup guide!

## Configuration Guide

This document provides detailed configuration and deployment instructions.

### Quick Reference
| Step | Command |
|------|---------|
| Create bot | `@BotFather` in Telegram |
| Configure | Add `SWARM_APPROVAL_BOT_TOKEN` to `.env` |
| Start | `python3 -m swarm.telegram.telegram_swarm_polling` |
| `TELEGRAM_BOT_TOKEN` | No | Fallback token |
| `TELEGRAM_CHAT_ID` | Optional | Chat ID for approval requests |
| `TELEGRAM_USER_ID` | Optional | User ID for authorization |

### Bot Token Security

⚠️ **Important**: Never share your bot token publicly. Store it in:
- `.env` file (not committed to version control)
- Environment variables
- Secure secret management system

### Chat ID Configuration

To get your Chat ID:
1. Start a private message with your bot
2. Send this command: `@username` (where username is your Telegram username)
3. Check the bot's API logs or use the BotFather info

### User ID Configuration

Your User ID is the same as your Telegram username (in numeric format). You can find it in:
1. BotFather chat info
2. Telegram API logs
3. By sending a message and checking logs

## Testing Without Telegram

For development/testing without Telegram:

1. Set a dummy chat ID and user ID:
   ```bash
   TELEGRAM_CHAT_ID=123456789
   TELEGRAM_USER_ID=987654321
   ```

2. The system will register authorization but won't send real messages

3. Test the authorization flow to ensure it works

## Production Deployment

### Running the Telegram Bot

Option 1: Background process
```bash
nohup python -m swarm.telegram.telegram_swarm_polling > bot.log 2>&1 &
```

Option 2: Systemd service
```ini
[Unit]
Description=Swarm Telegram Approval Bot
After=network.target

[Service]
Type=simple
User=steen
WorkingDirectory=/home/steen/kurs-bot
ExecStart=/usr/bin/python3 -m swarm.telegram.telegram_swarm_polling
Restart=always

[Install]
WantedBy=multi-user.target
```

### Monitoring

```bash
# Check bot logs
tail -f /home/steen/kurs-bot/bot.log

# Check active requests
python -c "from swarm.telegram import integration; print(integration.pending_requests)"
```

## Authorization Flow

### Step-by-Step

1. **Initiation**
   ```python
   initial_state = {
       "telegram_chat_id": 123456789,
       "telegram_user_id": 987654321,
   }
   ```

2. **Registration**
   ```python
   integration.register_chat_authorization(123456789, 987654321)
   ```

3. **Approval Request**
   ```python
   integration.request_final_approval(
       chat_id=123456789,
       user_id=987654321,
       summary="..."
   )
   ```

4. **Command Handling**
   ```python
   # User sends /approve
   # Bot verifies authorization
   # Bot processes approval
   ```

### Authorization Rules

- Only the user who initiated the swarm can approve
- Each chat-user pair is isolated
- Unauthorized attempts are logged and rejected

## Troubleshooting

### Bot Not Responding

1. Check if bot is running:
   ```bash
   ps aux | grep telegram_polling
   ```

2. Check logs:
   ```bash
   tail -f bot.log
   ```

3. Verify token:
   ```bash
   echo $SWARM_APPROVAL_BOT_TOKEN
   ```

### Authorization Fails

1. Ensure chat_id and user_id match:
   ```python
   print(f"Chat: {state['telegram_chat_id']}, User: {state['telegram_user_id']}")
   ```

2. Check authorization was registered:
   ```python
   from swarm.telegram import integration
   print(integration.state_manager.authorization_map)
   ```

### No Approval Request Sent

1. Check if Telegram is configured:
   ```python
   from swarm.telegram import integration
   print(integration.integration.pending_requests)
   ```

2. Verify final decision was APPROVE:
   ```python
   result = graph.invoke(initial_state)
   print(result['final_decision'])
   ```

### Stale Requests

1. Clean up old requests:
   ```python
   from swarm.telegram import integration
   integration.integration.cleanup_old_requests(max_age_hours=24)
   ```

## Security Best Practices

1. **Never commit `.env` files**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use separate bot for approvals**
   - Don't use the main kurs-bot token
   - Keep approval bot isolated

3. **Implement rate limiting**
   - Limit commands per user per hour
   - Prevent abuse

4. **Log all actions**
   ```python
   logger.info(f"Approval by {user_id}: {command}")
   ```

## API Reference

### Integration Functions

```python
from swarm.telegram import integration

# Register authorization
integration.register_chat_authorization(chat_id, user_id)

# Request prompt approval
integration.request_prompt_approval(
    chat_id=123456789,
    user_id=987654321,
    prompt="Your prompt",
    request_id="req-123"
)

# Request final approval
integration.request_final_approval(
    chat_id=123456789,
    user_id=987654321,
    summary="Summary",
    request_id="req-123"
)

# Get request status
status = integration.get_request_status("req-123")
```

### State Manager Functions

```python
from swarm.telegram import state_manager

# Check authorization
state_manager.is_authorized(chat_id, user_id)

# Add pending approval
state_manager.add_pending_approval(
    request_id="req-123",
    chat_id="123456789",
    user_id="987654321",
    stage="start",
    summary="Summary"
)

# Approve request
state_manager.approve_request("req-123", user_id)

# Decline request
state_manager.decline_request("req-123", user_id)

# Add retry feedback
state_manager.add_retry_feedback("req-123", user_id, "Feedback")
```

## Example Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User initiates swarm                                     │
│    python -m swarm.cli "Implement feature X"                │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Swarm executes: Architect → Code Writer → Reviewer       │
│    Internal loops continue automatically                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Review approves, Pre-commit passes                       │
│    final_decision = "APPROVE"                               │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Integration requests final approval via Telegram         │
│    integration.request_final_approval(...)                  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. User receives message in Telegram                        │
│    "SWARM OPERATION COMPLETE - READY FOR COMMIT"            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. User sends /approve                                      │
│    Bot verifies authorization                               │
│    Bot processes approval                                   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Swarm proceeds with git commit and push                  │
│    Operation complete!                                      │
└─────────────────────────────────────────────────────────────┘
```

## Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| Bot token invalid | Re-create bot with @BotFather |
| Authorization fails | Check chat_id and user_id match |
| No request sent | Verify Telegram is configured |
| Stale requests | Run cleanup function |
| Bot not running | Check process is active |

## Next Steps

1. Test with real Telegram bot
2. Configure production deployment
3. Set up monitoring and logging
4. Implement additional security measures
5. Add webhook support for real-time updates

## Support

For issues or questions:
- Check logs: `tail -f bot.log`
- Review INTEGRATION.md
- Contact development team

---

**Version**: 1.0.0
**Last Updated**: 2026-03-28
