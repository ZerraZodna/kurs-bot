"""
Telegram Bot Integration Module for Swarm Human-in-the-Loop System

This module connects the swarm execution with the Telegram approval bot.
It provides hooks to send approval requests at critical points in the workflow:
- Step 2-3: Prompt approval (before code generation)
- Step 8-9: Final approval (before git commit)

CRITICAL UPDATE: Now includes proper workflow synchronization that allows
a swarm to pause and wait for user approval response before continuing or finishing.
"""

import logging
from typing import Dict, Any
import uuid

# Import from telegram polling module
from .telegram_swarm_polling import (
    send_swarm_approval_request,
    state_manager,
)
from .workflow_coordinator import coordinator


# Configure logger
logger = logging.getLogger(__name__)


async def _on_approval_received(status: str):
    """Callback function that runs when approval is received for a request."""
    logger.info(f"[approval-integration] Workflow resumed with status: {status}")


class SwarmTelegramIntegration:
    """
    Integration class that connects swarm execution with Telegram approval bot.

    Usage:
        integration = SwarmTelegramIntegration()

        # When swarm needs approval at Step 2-3:
        await integration.request_prompt_approval(
            chat_id=telegram_chat_id,
            prompt=prompt_text,
            user_id=initiator_user_id
        )

        # When swarm needs approval at Step 8-9:
        await integration.request_final_approval(
            chat_id=telegram_chat_id,
            summary=completion_summary,
            user_id=initiator_user_id
        )
    """

    def __init__(self):
        """Initialize the integration."""
        self.pending_requests: Dict[str, Dict] = {}
        logger.info("[swarm-telegram-integration] Integration initialized with coordinator")

    def generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return f"req-{uuid.uuid4().hex[:12]}"

    async def request_prompt_approval(
        self, chat_id: int, prompt: str, user_id: int, workflow_instance: Any = None, request_id: str | None = None
    ) -> str | None:
        """
        Request approval for a swarm prompt (Step 2-3 in workflow).

        This is called when the swarm needs a human to approve generated
        prompts before proceeding with code generation. The caller will
        BLOCK here until the approval response is received.

        Args:
            chat_id: Telegram chat ID where user can send commands
            prompt: The generated prompt that needs approval
            user_id: ID of the user who initiated the swarm (for authorization)
            workflow_instance: The workflow instance that will resume when approved
            request_id: Optional request ID, will be generated if not provided

        Returns:
            Result status of the approval (approved/declined/retry) or None if failed
        """
        if request_id is None:
            request_id = self.generate_request_id()

        logger.info(f"[swarm-telegram-integration] Requesting prompt approval: {request_id}")

        try:
            # Create a session with the workflow coordinator that will pause execution
            session = await coordinator.create_session(
                request_id=request_id,
                workflow_instance=workflow_instance,
                approval_callback=_on_approval_received,
                timeout=300.0,  # 5 minutes default timeout
            )

            # Send the approval request through existing hooks
            result = await send_swarm_approval_request(
                chat_id=chat_id,
                user_id=user_id,
                request_id=request_id,
                prompt_or_change_summary=prompt,
                approval_stage="start",
            )

            # Track the request in internal tracking
            self.pending_requests[request_id] = {
                "chat_id": chat_id,
                "user_id": user_id,
                "stage": "start",
                "prompt": prompt[:500],  # Store truncated prompt for tracking
                "workflow_instance": workflow_instance,
            }

            logger.info(f"[swarm-telegram-integration] Sent prompt approval request: {request_id}")
            logger.info("[swarm-telegram-integration] WORKFLOW WILL NOW PAUSE AND WAIT for response")

            # BLOCK here until the approval response is received
            result = await coordinator.wait_for_approval(request_id)

            logger.info(f"[swarm-telegram-integration] Prompt approval workflow resumed with result: {result}")
            return result.value  # Return the status as a string
        except Exception as e:
            logger.error(f"[swarm-telegram-integration] Failed to send prompt approval request: {e}")
            return None

    async def request_final_approval(
        self, chat_id: int, summary: str, user_id: int, workflow_instance: Any = None, request_id: str | None = None
    ) -> str | None:
        """
        Request final approval before git commit (Step 8-9 in workflow).

        This is called when the swarm has completed all internal work and needs
        human approval before proceeding with git commit and push operations.
        The caller will BLOCK here until the approval response is received.

        Args:
            chat_id: Telegram chat ID where user can send commands
            summary: Summary of completed work that needs approval
            user_id: ID of the user who initiated the swarm (for authorization)
            workflow_instance: The workflow instance that will resume when approved
            request_id: Optional request ID, will be generated if not provided

        Returns:
            Result status of the approval (approved/declined/retry) or None if failed
        """
        if request_id is None:
            request_id = self.generate_request_id()

        logger.info(f"[swarm-telegram-integration] Requesting final approval: {request_id}")

        try:
            # Create a session with the workflow coordinator that will pause execution
            session = await coordinator.create_session(
                request_id=request_id,
                workflow_instance=workflow_instance,
                approval_callback=_on_approval_received,
                timeout=3600.0,  # 1 hour longer timeout for final approval
            )

            # Send the approval request through existing hooks
            result = await send_swarm_approval_request(
                chat_id=chat_id,
                user_id=user_id,
                request_id=request_id,
                prompt_or_change_summary=summary,
                approval_stage="end",
            )

            # Track the request in internal tracking
            self.pending_requests[request_id] = {
                "chat_id": chat_id,
                "user_id": user_id,
                "stage": "end",
                "summary": summary[:500],  # Store truncated summary for tracking
                "workflow_instance": workflow_instance,
            }

            logger.info(f"[swarm-telegram-integration] Sent final approval request: {request_id}")
            logger.info("[swarm-telegram-integration] WORKFLOW WILL NOW PAUSE AND WAIT for response")

            # BLOCK here until the approval response is received
            result = await coordinator.wait_for_approval(request_id)

            logger.info(f"[swarm-telegram-integration] Final approval workflow resumed with result: {result}")
            return result.value  # Return the status as a string
        except Exception as e:
            logger.error(f"[swarm-telegram-integration] Failed to send final approval request: {e}")
            return None

    def get_request_status(self, request_id: str) -> Dict | None:
        """Get the status of a pending approval request."""
        return self.pending_requests.get(request_id)

    def cleanup_old_requests(self, max_age_hours: float = 24.0) -> int:
        """
        Clean up old approval requests that haven't been processed.

        Args:
            max_age_hours: Maximum age of requests to keep (default: 24 hours)

        Returns:
            Number of requests cleaned up
        """
        # Use the coordinator's synchronous cleanup method
        cleanup_count = coordinator.cleanup_expired_sessions_coroutine(max_age_hours)
        return cleanup_count

    def register_chat_authorization(self, chat_id: int, user_id: int) -> bool:
        """
        Register a chat-user authorization mapping.

        This should be called once per chat when a user initiates a swarm operation.
        It allows the user to send approval commands.

        Args:
            chat_id: Telegram chat ID
            user_id: User ID who is authorized

        Returns:
            True if successful
        """
        try:
            state_manager.register_authorization(chat_id, user_id)
            logger.info(f"[swarm-telegram-integration] Registered authorization: chat {chat_id}, user {user_id}")
            return True
        except Exception as e:
            logger.error(f"[swarm-telegram-integration] Failed to register authorization: {e}")
            return False


# Global integration instance
integration = SwarmTelegramIntegration()


def register_swarm_authorization(chat_id: int, user_id: int) -> bool:
    """
    Helper function to register chat-user authorization for a new swarm session.

    This should be called once per chat when a user initiates a swarm operation.
    It allows the user to send approval commands during the workflow.

    Args:
        chat_id: Telegram chat ID
        user_id: User ID who is authorized

    Returns:
        True if successful, False otherwise
    """
    return integration.register_chat_authorization(chat_id, user_id)


async def request_approval(
    chat_id: int,
    user_id: int,
    workflow_instance: Any,
    stage: str = "start",
    summary: str = "",
    request_id: str | None = None,
) -> str | None:
    """
    Convenience function to request approval and BLOCK until response received.

    Args:
        chat_id: Telegram chat ID
        user_id: User ID
        workflow_instance: The workflow instance that will resume when approved
        stage: "start" for prompt approval, "end" for final approval
        summary: Summary of what needs approval
        request_id: Optional request ID

    Returns:
        Result status of approval (approved/declined/retry) or None if error
    """
    if stage == "start":
        return await integration.request_prompt_approval(
            chat_id=chat_id, prompt=summary, user_id=user_id, workflow_instance=workflow_instance, request_id=request_id
        )
    elif stage == "end":
        return await integration.request_final_approval(
            chat_id=chat_id,
            summary=summary,
            user_id=user_id,
            workflow_instance=workflow_instance,
            request_id=request_id,
        )
    else:
        logger.error(f"[swarm-telegram-integration] Invalid stage: {stage}")
        return None


# API hooks for the swarm system to use (these now work with blocking/resume)


async def hook_request_prompt_approval(
    chat_id: int, user_id: int, prompt: str, workflow_instance: Any = None, request_id: str | None = None
) -> str | None:
    """
    Hook function to request prompt approval and pause workflow until response.

    This is called by the swarm graph at Step 2-3 to pause for approval of prompts.
    The workflow calling this will BLOCK until user responds via Telegram.
    """
    try:
        result = await integration.request_prompt_approval(
            chat_id=chat_id, prompt=prompt, user_id=user_id, workflow_instance=workflow_instance, request_id=request_id
        )
        return result
    except Exception as e:
        logger.error(f"[swarm-telegram-integration] Prompt approval hook failed: {e}")
        return None


async def hook_request_final_approval(
    chat_id: int, user_id: int, summary: str, workflow_instance: Any = None, request_id: str | None = None
) -> str | None:
    """
    Hook function to request final approval and pause workflow until response.

    This is called by the swarm graph at Step 8-9 to pause for approval before committing.
    The workflow calling this will BLOCK until user responds via Telegram.
    """
    try:
        result = await integration.request_final_approval(
            chat_id=chat_id,
            summary=summary,
            user_id=user_id,
            workflow_instance=workflow_instance,
            request_id=request_id,
        )
        return result
    except Exception as e:
        logger.error(f"[swarm-telegram-integration] Final approval hook failed: {e}")
        return None


async def hook_send_swarm_complete_notification(chat_id: int, user_id: int, completion_details: str) -> bool:
    """
    Hook function to send completion notification to swarm user.

    This is called by the swarm graph after successful completion.
    """
    try:
        from .telegram_swarm_polling import send_swarm_complete_notification

        return await send_swarm_complete_notification(chat_id, completion_details)
    except Exception as e:
        logger.error(f"[swarm-telegram-integration] Complete notification hook failed: {e}")
        return False


def hook_register_authorization(chat_id: int, user_id: int) -> bool:
    """
    Hook function to register chat-user authorization.

    This should be called once per chat when user initiates swarm.
    """
    return integration.register_chat_authorization(chat_id, user_id)
