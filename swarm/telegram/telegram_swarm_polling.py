"""
Self-contained Telegram polling service for Swarm approval system.

Simple bot that handles approval commands for the 9-step human-in-the-loop workflow:
- /approve - Approve pending swarm request
- /retry "instructions" - Request adjustments to current task
- /decline - Decline pending request
- /help - Show available commands

Does NOT include full features of course bot - just approval workflow
"""

from __future__ import annotations

import asyncio
import httpx
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Set, List
from pydantic_settings import BaseSettings


# Pydantic settings - automatically loads from .env file
class Settings(BaseSettings):
    SWARM_APPROVAL_BOT_TOKEN: str = os.getenv("SWARM_APPROVAL_BOT_TOKEN", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "allow"}


settings = Settings()
logger = logging.getLogger(__name__)

# Global variable to track processed update IDs for Telegram polling
_processed_updates: Set[int] = set()

# Token retrieval with proper error handling
if not settings.SWARM_APPROVAL_BOT_TOKEN:
    # Try fallback to TELEGRAM_BOT_TOKEN
    SWARM_APPROVAL_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
else:
    SWARM_APPROVAL_BOT_TOKEN = settings.SWARM_APPROVAL_BOT_TOKEN

# Validate token availability
if not SWARM_APPROVAL_BOT_TOKEN:
    logger.warning(
        "[swarm-telegram-polling] No bot token available - Please set SWARM_APPROVAL_BOT_TOKEN or TELEGRAM_BOT_TOKEN in .env file"
    )
    SWARM_APPROVAL_BOT_TOKEN = None  # Will cause 404 but allows for testing
else:
    logger.info(
        f"[swarm-telegram-polling] Bot token loaded: {SWARM_APPROVAL_BOT_TOKEN[:10]}...{SWARM_APPROVAL_BOT_TOKEN[-5:]}"
    )

API_BASE = f"https://api.telegram.org/bot{SWARM_APPROVAL_BOT_TOKEN}" if SWARM_APPROVAL_BOT_TOKEN else None


# Placeholder for swarm state management - this would need to be hooked up to the actual swarm system
class SwarmStateManager:
    """
    State management for swarm approval requests.
    Connects Telegram bot with swarm execution state.
    """

    def __init__(self):
        # Dictionary storing pending approvals: {request_id: ApprovalRequest}
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        # Track which chats have active requests
        self.active_chats: Dict[str, str] = {}  # chat_id -> request_id
        # Track authorization mappings
        self.authorization_map: Dict[str, str] = {}  # chat_id -> user_id

    def register_authorization(self, chat_id: str, user_id: str) -> None:
        """Register a chat_id to user_id mapping for authorization."""
        self.authorization_map[str(chat_id)] = str(user_id)

    def is_authorized(self, chat_id: str, user_id: str) -> bool:
        """Verify if a user is authorized to make approval commands."""
        chat_key = str(chat_id)
        if chat_key in self.authorization_map:
            return self.authorization_map[chat_key] == str(user_id)
        return False

    def add_pending_approval(
        self, request_id: str, chat_id: str, user_id: str, stage: str = "start", summary: str = ""
    ) -> None:
        """Add a pending approval request with proper validation."""

        # Verify authorization
        if not self.is_authorized(chat_id, user_id):
            logger.warning(f"[swarm-telegram-polling] Authorization failed for user {user_id} on chat {chat_id}")
            return

        # Create approval request object
        approval_request = ApprovalRequest(
            request_id=request_id,
            chat_id=str(chat_id),
            user_id=str(user_id),
            stage=stage,
            summary=summary[:2000] if summary else "",  # Truncate long summaries
            timestamp=asyncio.get_event_loop().time(),
        )

        # Store the approval request
        self.pending_approvals[request_id] = approval_request

        # Track as active for this chat
        self.active_chats[str(chat_id)] = request_id

        logger.info(f"[swarm-telegram-polling] Added pending approval {request_id} for chat {chat_id}")

    def get_pending_approval(self, request_id: str) -> ApprovalRequest | None:
        """Get a specific pending approval request."""
        return self.pending_approvals.get(request_id)

    def get_pending_approvals_for_chat(self, chat_id: str) -> List[ApprovalRequest]:
        """Get all pending approval requests for a chat."""
        chat_request_id = self.active_chats.get(str(chat_id))
        if chat_request_id:
            return [self.pending_approvals[chat_request_id]]
        return []

    def approve_request(self, request_id: str, user_id: str) -> bool:
        """Process an approval for a request."""
        approval = self.pending_approvals.get(request_id)

        if not approval:
            logger.warning(f"[swarm-telegram-polling] No pending approval found for {request_id}")
            return False

        # Verify authorization
        if not self.is_authorized(approval.chat_id, user_id):
            logger.warning(f"[swarm-telegram-polling] Unauthorized approval attempt for {request_id}")
            return False

        # Mark as approved
        approval.approved = True
        approval.approved_by_user_id = str(user_id)

        logger.info(f"[swarm-telegram-polling] Approved request {request_id} by user {user_id}")

        # Remove from active chats
        if str(approval.chat_id) in self.active_chats:
            del self.active_chats[str(approval.chat_id)]

        # Keep the approval record but mark as processed
        return True

    def decline_request(self, request_id: str, user_id: str) -> bool:
        """Process a decline for a request."""
        approval = self.pending_approvals.get(request_id)

        if not approval:
            logger.warning(f"[swarm-telegram-polling] No pending approval found for {request_id}")
            return False

        # Verify authorization
        if not self.is_authorized(approval.chat_id, user_id):
            logger.warning(f"[swarm-telegram-polling] Unauthorized decline attempt for {request_id}")
            return False

        logger.info(f"[swarm-telegram-polling] Declined request {request_id} by user {user_id}")

        # Remove from active chats
        if str(approval.chat_id) in self.active_chats:
            del self.active_chats[str(approval.chat_id)]

        return True

    def add_retry_feedback(self, request_id: str, user_id: str, feedback: str) -> bool:
        """Add retry feedback to a request."""
        approval = self.pending_approvals.get(request_id)

        if not approval:
            logger.warning(f"[swarm-telegram-polling] No pending approval found for {request_id}")
            return False

        # Verify authorization
        if not self.is_authorized(approval.chat_id, user_id):
            logger.warning(f"[swarm-telegram-polling] Unauthorized retry attempt for {request_id}")
            return False

        approval.retry_feedback = feedback
        logger.info(f"[swarm-telegram-polling] Added retry feedback to request {request_id}")

        return True

    def clear_request(self, request_id: str) -> bool:
        """Clear a request (remove from pending)."""
        if request_id in self.pending_approvals:
            del self.pending_approvals[request_id]

            # Remove from active chats
            for chat_id, req_id in list(self.active_chats.items()):
                if req_id == request_id:
                    del self.active_chats[chat_id]
                    break

            return True
        return False

    def get_approval_stage(self, request_id: str) -> str | None:
        """Get the approval stage for a request."""
        approval = self.pending_approvals.get(request_id)
        return approval.stage if approval else None

    def cleanup_expired_requests(self, max_age_hours: float = 24.0) -> None:
        """Remove approval requests older than max_age_hours."""
        now = asyncio.get_event_loop().time()
        expired_ids = []

        for req_id, approval in self.pending_approvals.items():
            if now - approval.timestamp > max_age_hours:
                expired_ids.append(req_id)

        for req_id in expired_ids:
            logger.warning(f"[swarm-telegram-polling] Removing expired request {req_id}")
            self.clear_request(req_id)

    def get_active_request_ids(self) -> List[str]:
        """Get all active request IDs."""
        return list(self.pending_approvals.keys())


# Global state manager instance (would be replaced by proper DI if this grows)
state_manager = SwarmStateManager()


# Telegram bot polling service
class SwarmTelegramPoller:
    """
    Polling service for the swarm approval Telegram bot.
    Monitors for approval commands and processes them via the state manager.
    """

    def __init__(self):
        self.running = False
        self.poll_interval = 3  # Seconds between polls
        self._client: httpx.AsyncClient | None = None  # Shared HTTP client
        logger.info("[swarm-telegram-polling] Swarm Telegram Poller initialized")

    async def _get_client(self) -> httpx.AsyncClient:
        """Return (or create) the shared httpx.AsyncClient with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                timeout=httpx.Timeout(10.0),
            )
        return self._client

    async def close(self) -> None:
        """Close the shared HTTP client. Call when shutting down."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def process_update(self, update) -> None:
        """
        Process a single Telegram update and handle approval commands.

        Args:
            update: Telegram update dictionary containing message and chat info
        """
        try:
            # Get message and chat info
            message = update.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            user_id = message.get("from", {}).get("id")
            text = message.get("text", "").lower()

            if not chat_id or not user_id:
                return

            # Check authorization
            if not state_manager.is_authorized(chat_id, user_id):
                # Check if this is a help message from an unauthorized user
                if text == "/help":
                    help_text = """
🤖 Swarm Approval Bot

Available commands:
- /approve - Approve pending swarm request
- /retry "instructions" - Request adjustments with feedback
- /decline - Decline pending request completely
- /help - Show this help message

Reply with /approve to continue or /decline to cancel.
"""
                    await send_message(chat_id, help_text)
                return

            # Handle commands
            if text == "/approve":
                # Check for pending requests for this chat
                pending_requests = state_manager.get_pending_approvals_for_chat(chat_id)
                if pending_requests:
                    request_id = pending_requests[0].request_id
                    logger.info(f"[swarm-telegram-polling] Processing approve command for {request_id}")

                    # Process the approval
                    state_manager.approve_request(request_id, user_id)

                    # Send confirmation
                    confirmation = f"""
✅ APPROVAL RECEIVED

Your approval for request {request_id} has been processed.
The swarm workflow will continue.
"""
                    await send_message(chat_id, confirmation)
                else:
                    await send_message(chat_id, "No pending approval requests. Use /help for available commands.")

            elif text == "/decline":
                # Check for pending requests for this chat
                pending_requests = state_manager.get_pending_approvals_for_chat(chat_id)
                if pending_requests:
                    request_id = pending_requests[0].request_id
                    logger.info(f"[swarm-telegram-polling] Processing decline command for {request_id}")

                    # Process the decline
                    state_manager.decline_request(request_id, user_id)

                    # Send confirmation
                    confirmation = f"""
❌ DECLINE RECEIVED

Your decline for request {request_id} has been processed.
The swarm operation has been cancelled.
"""
                    await send_message(chat_id, confirmation)
                else:
                    await send_message(chat_id, "No pending approval requests. Use /help for available commands.")

            elif text.startswith("/retry "):
                # Extract feedback from the command
                feedback = text[6:].strip()  # Remove "/retry " prefix

                # Check for pending requests for this chat
                pending_requests = state_manager.get_pending_approvals_for_chat(chat_id)
                if pending_requests:
                    request_id = pending_requests[0].request_id
                    logger.info(f"[swarm-telegram-polling] Processing retry feedback for {request_id}")

                    # Add retry feedback
                    state_manager.add_retry_feedback(request_id, user_id, feedback)

                    # Send confirmation
                    confirmation = f"""
🔧 FEEDBACK RECEIVED

Your feedback for request {request_id} has been recorded:
"{feedback[:200]}"

The swarm will apply these adjustments.
"""
                    await send_message(chat_id, confirmation)
                else:
                    await send_message(chat_id, "No pending approval requests. Use /help for available commands.")

            elif text == "/help":
                help_text = """
🤖 Swarm Approval Bot

Available commands:
- /approve - Approve pending swarm request
- /retry "instructions" - Request adjustments with feedback
- /decline - Decline pending request completely
- /help - Show this help message

Reply with /approve to continue or /decline to cancel.
"""
                await send_message(chat_id, help_text)
        except Exception as e:
            logger.error(f"[swarm-telegram-polling] Error processing update: {e}")

    async def run(self):
        """
        Start the polling service.
        Continuously checks for new updates and processes approval commands.
        """
        self.running = True
        logger.info("[swarm-telegram-polling] Starting polling service...")

        try:
            while self.running:
                try:
                    # Get new updates
                    result = await self._get_new_updates()

                    if result:
                        for update in result:
                            await self.process_update(update)

                    # Wait before next poll
                    await asyncio.sleep(self.poll_interval)

                except Exception as e:
                    logger.error(f"[swarm-telegram-polling] Error in polling loop: {e}")
                    await asyncio.sleep(self.poll_interval)
        finally:
            await self.close()

    async def _get_new_updates(self) -> list:
        """
        Get new updates since the last processed update ID.

        Returns:
            List of new updates
        """
        try:
            # Get the last update ID we processed
            last_update_id = 0
            if _processed_updates:
                last_update_id = max(_processed_updates)

            # Request updates since last update
            params = {"offset": last_update_id + 1, "limit": 100}
            response = await self._api_call("getUpdates", params)

            if response and "result" in response:
                updates = response["result"]

                # Store processed update IDs
                for update in updates:
                    update_id = update.get("update_id", 0)
                    _processed_updates.add(update_id)

                return updates

            return []

        except Exception as e:
            logger.error(f"[swarm-telegram-polling] Error getting updates: {e}")
            return []

    async def _api_call(self, method: str, params: dict) -> dict:
        """
        Make an API call to the Telegram bot API.

        Args:
            method: API method name
            params: API parameters

        Returns:
            API response
        """
        url = f"{API_BASE}/{method}"
        try:
            client = await self._get_client()
            response = await client.post(url, json=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"[swarm-telegram-polling] API call {method} failed: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"[swarm-telegram-polling] API call {method} error: {e}")
            raise

    def stop(self):
        """Stop the polling service."""
        self.running = False
        logger.info("[swarm-telegram-polling] Stopping polling service...")


# Global poller instance
poller = SwarmTelegramPoller()


async def send_message(chat_id: int, text: str) -> None:
    """
    Send a message to a Telegram chat.

    Args:
        chat_id: Telegram chat ID
        text: Message text to send
    """
    if not API_BASE:
        logger.warning("[swarm-telegram-polling] Cannot send message: no API_BASE configured")
        return
    try:
        url = f"{API_BASE}/sendMessage"
        params = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

        client = await poller._get_client()
        response = await client.post(url, json=params)
        response.raise_for_status()

        logger.info(f"[swarm-telegram-polling] Sent message to chat {chat_id}")
    except Exception as e:
        logger.error(f"[swarm-telegram-polling] Failed to send message: {e}")


# Import SwarmTelegramPoller after defining send_message to avoid circular import


@dataclass
class ApprovalRequest:
    """Data class for tracking approval requests."""

    request_id: str
    chat_id: str
    user_id: str
    stage: str = "start"  # "start" for Step 2-3, "end" for Step 8-9
    summary: str = ""
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    approved: bool = False
    approved_by_user_id: str = ""
    retry_feedback: str = ""

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "stage": self.stage,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "approved": self.approved,
            "approved_by_user_id": self.approved_by_user_id,
            "retry_feedback": self.retry_feedback,
        }


# API Functions to be used by the swarm system to communicate with the bot


async def send_swarm_approval_request(
    chat_id: int,
    user_id: int,
    request_id: str,
    prompt_or_change_summary: str,
    approval_stage: str = "start",
) -> None:
    """Function to send approval request from swarm to user via Telegram."""
    try:
        # Verify authorization before sending
        if not state_manager.is_authorized(chat_id, user_id):
            logger.warning(
                f"[swarm-telegram-polling] Unauthorized attempt to send approval request: chat {chat_id}, user {user_id}"
            )
            return

        # Register authorization if not already registered
        if str(chat_id) not in state_manager.authorization_map:
            state_manager.register_authorization(chat_id, user_id)

        stage_description = "swarm prompt" if approval_stage == "start" else "completed changes"

        message = f"""
🔄 {stage_description.upper()} PENDING APPROVAL

Current status: Waiting for your approval

Details:
{prompt_or_change_summary[:2000]}

Options:
- /approve - Continue with this {stage_description}
- /retry "feedback here" - Adjust this {stage_description}
- /decline - Cancel the operation
- /help - Show help

Reply with /approve to continue or /decline to cancel.
    """.strip()

        # Add this to pending approvals state
        state_manager.add_pending_approval(
            request_id=request_id,
            chat_id=str(chat_id),
            user_id=str(user_id),
            stage=approval_stage,
            summary=prompt_or_change_summary[:2000],
        )

        await send_message(chat_id, message)
        logger.info(f"[swarm-telegram-polling] Sent approval request {request_id} to chat {chat_id}")
    except Exception as e:
        logger.error(f"[swarm-telegram-polling] Error sending approval request {request_id}: {e}")


async def send_swarm_complete_notification(chat_id: int, completion_details: str) -> None:
    """Send completion notification after successful swarm operation."""
    try:
        message = f"""
✅ SWARM OPERATION COMPLETE

Process finished successfully!

Details:
{completion_details[:2000]}

You may receive further notifications depending on the swarm settings.
    """.strip()

        await send_message(chat_id, message)
        logger.info(f"[swarm-telegram-polling] Sent completion notification to chat {chat_id}")
    except Exception as e:
        logger.error(f"[swarm-telegram-polling] Error sending completion notification: {e}")


if __name__ == "__main__":
    import asyncio

    async def main():
        """Main entry point for the polling service."""
        try:
            await poller.run()
        except KeyboardInterrupt:
            logger.info("[swarm-telegram-polling] Received interrupt signal, stopping...")
            poller.stop()

    asyncio.run(main())
